"""形態素解析(Python 参照版)。data/dict/ だけを読み、IPADIC の原本には触れない。

TypeScript の出荷実装(loop_003)はこれと同じ手順を踏む。二つが一致することが O-1a/O-1b の片側、
MeCab と一致することがもう片側になる。

    from analyze import Analyzer
    a = Analyzer.load("data/dict")
    r = a.analyze("東京都は日本の首都である")
    r.cost, [n.surface for n in r.nodes]
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import shipdict  # noqa: E402

MAX_GROUPING = 24  # MeCab の DEFAULT_MAX_GROUPING_SIZE


@dataclass
class Node:
    surface: str
    start: int          # 本文のバイト位置(空白を飛ばした後の語頭)
    end: int
    lc: int
    rc: int
    cost: int           # 生起コスト
    conn: int           # 直前ノードからの連接コスト
    pos: tuple
    conj: tuple
    unknown: bool


@dataclass
class Result:
    cost: int
    nodes: list = field(default_factory=list)

    @property
    def words(self):
        return [n.surface for n in self.nodes]


class Analyzer:
    def __init__(self, d: shipdict.ShipDict):
        self.d = d
        self.space_type = 1 << d.categories.index("SPACE")

    @classmethod
    def load(cls, dictdir: str) -> "Analyzer":
        return cls(shipdict.load(dictdir))

    # ------------------------------------------------------------------

    @staticmethod
    def _charlen(b: int) -> int:
        return 1 if b < 0x80 else (2 if b < 0xE0 else (3 if b < 0xF0 else 4))

    def _cp(self, raw: bytes, i: int) -> int:
        return ord(raw[i : i + self._charlen(raw[i])].decode("utf-8", "replace")[:1] or "\0")

    def candidates(self, raw: bytes, pos: int):
        """位置 pos から始まる候補ノードを、MeCab と同じ順序で返す。

        返り値は (終端バイト位置, 語頭バイト位置, Token, 未知語か)。
        順序がタイブレークに効くので、辞書語 → 未知語(group → length)の順を崩さない。
        """
        d = self.d
        n = len(raw)
        # 先頭の SPACE 系文字を読み飛ばす(MeCab の seekToOtherType 相当)
        b2 = pos
        while b2 < n and (d.char_info(self._cp(raw, b2))[0] & self.space_type):
            b2 += self._charlen(raw[b2])
        if b2 >= n:
            return []

        typ, dflt, lng, grp, inv = d.char_info(self._cp(raw, b2))
        out = []
        for blen, si, nt in d.common_prefix(raw, b2):
            for k in range(nt):
                out.append((b2 + blen, b2, d.token(d._tok_start[si] + k), False))

        if out and not inv:
            return out

        b3 = b2 + self._charlen(raw[b2])
        gb3 = -1
        if grp:
            e, cnt = b3, 1
            while e < n and (d.char_info(self._cp(raw, e))[0] & typ):
                e += self._charlen(raw[e])
                cnt += 1
            if cnt <= MAX_GROUPING:
                for t in d.unk_tokens(dflt):
                    out.append((e, b2, t, True))
            gb3 = e
        for _ in range(lng):
            if b3 > n:
                break
            if b3 != gb3:
                for t in d.unk_tokens(dflt):
                    out.append((b3, b2, t, True))
            if b3 >= n or not (d.char_info(self._cp(raw, b3))[0] & typ):
                break
            b3 += self._charlen(raw[b3])
        return out

    # ------------------------------------------------------------------

    def analyze(self, text: str) -> Result | None:
        d = self.d
        raw = text.encode("utf-8")
        n = len(raw)
        # ends[i] = 位置 i で終わるノードごとの最良 (コスト, rc, 手繰り)。
        #
        # **並び順が同点の勝敗を決める。** MeCab は end_node_list へ「先頭挿入」し、
        # 比較は厳密な `<` なので、同点なら**リストの先頭にあるノード**が勝つ。
        # 先頭に来るのは最後に挿入されたもの、すなわち**最も遅く始まったノード**であり、
        # 同じ開始位置の中では**最初に生成されたトークン**(辞書語 → 未知語、同表層は k 昇順)。
        # これを再現するため、位置ごとに作った束を forward のまま前へ差し込む。
        ends = [[] for _ in range(n + 1)]
        ends[0] = [(0, 0, None)]
        for pos in range(n):
            if not ends[pos] or (raw[pos] & 0xC0) == 0x80:
                continue
            fresh = {}
            for (e, s, t, unk) in self.candidates(raw, pos):
                best = None
                for (pc, prc, bk) in ends[pos]:  # 先頭が同点の勝者
                    c = d.connection(prc, t.lc)
                    tot = pc + c + t.cost
                    if best is None or tot < best[0]:
                        best = (tot, t.rc, (pos, bk, s, e, t, unk, c))
                if best:
                    fresh.setdefault(e, []).append(best)
            for e, group in fresh.items():
                ends[e] = group + ends[e]
        if not ends[n]:
            return None
        total, bk = min(((pc + d.connection(prc, 0), bk) for (pc, prc, bk) in ends[n]),
                        key=lambda x: x[0])
        nodes = []
        while bk:
            _pos, prev, s, e, t, unk, conn = bk
            nodes.append(Node(raw[s:e].decode("utf-8", "replace"), s, e,
                              t.lc, t.rc, t.cost, conn, t.pos, t.conj, unk))
            bk = prev
        nodes.reverse()
        return Result(total, nodes)


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    a = Analyzer.load(os.path.join(root, "data", "dict"))
    for s in sys.argv[1:] or ["東京都は日本の首都である", "の北詰まで", "すもももももももものうち"]:
        r = a.analyze(s)
        print(f"{r.cost:8d}  " + " / ".join(
            f"{x.surface}({x.pos[0]}{'・未知語' if x.unknown else ''})" for x in r.nodes))
