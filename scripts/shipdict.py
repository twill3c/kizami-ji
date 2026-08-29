"""出荷用辞書の読み取り実装(Python 参照版)。

**このモジュールは ipadic / fugashi / MeCab を import しない。**
data/dict/ に置かれたファイルだけで解析が成立することが、そのまま出荷可能性の証明になる。
TypeScript の出荷実装はこのモジュールと同じ形式を読む(loop_003)。

形式は scripts/build_dict.py が書き出す。meta.json の `format` が版。
"""

from __future__ import annotations

import array
import json
import os
from dataclasses import dataclass

FORMAT = 1


@dataclass(frozen=True)
class Token:
    lc: int
    rc: int
    cost: int
    pos: tuple
    conj: tuple


class ShipDict:
    def __init__(self, meta, surf, surf_idx, tok, matrix, chars):
        self.meta = meta
        self._surf = surf
        self._sidx = surf_idx
        self._tok_start, self._tok_count, self._lc, self._rc, self._cost, self._pos, self._cf = tok
        self.matrix = matrix
        self.lsize = meta["lsize"]
        self.rsize = meta["rsize"]
        self._chars = chars  # (starts array, infos array)
        self.pos_table = [tuple(x) for x in meta["pos"]]
        self.conj_table = [tuple(x) for x in meta["conj"]]
        self.categories = meta["categories"]
        self.surface_count = len(self._sidx) - 1
        self.token_count = len(self._lc)
        self._space_type = 1 << self.categories.index("SPACE")

    # -------------------------------------------------------------- 表層

    def surface(self, i: int) -> bytes:
        # _surf は bytes。array('B') のままだと slice ごとに配列を作り直して桁違いに遅い
        return self._surf[self._sidx[i] : self._sidx[i + 1]]

    def all_surfaces(self):
        for i in range(self.surface_count):
            yield self.surface(i)

    def _lower_bound(self, prefix: bytes, lo: int, hi: int) -> int:
        while lo < hi:
            mid = (lo + hi) // 2
            if self.surface(mid) < prefix:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def _upper_bound_prefix(self, prefix: bytes, lo: int, hi: int) -> int:
        n = len(prefix)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.surface(mid)[:n] <= prefix:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def common_prefix(self, key: bytes, start: int):
        """key[start:] の接頭辞になっている表層を、短い順に (バイト長, 表層 index, token 数) で返す。

        MeCab の commonPrefixSearch と同じ順序(長さ昇順)で返す。順序はタイブレークに効く。
        """
        out = []
        lo, hi = 0, self.surface_count
        i = start
        n = len(key)
        while i < n:
            c = key[i]
            step = 1 if c < 0x80 else (2 if c < 0xE0 else (3 if c < 0xF0 else 4))
            i += step
            prefix = key[start:i]
            lo = self._lower_bound(prefix, lo, hi)
            hi = self._upper_bound_prefix(prefix, lo, hi)
            if lo >= hi:
                break
            if self.surface(lo) == prefix:
                out.append((i - start, lo, self._tok_count[lo]))
        return out

    def find(self, surf: bytes) -> int:
        lo = self._lower_bound(surf, 0, self.surface_count)
        if lo < self.surface_count and self.surface(lo) == surf:
            return lo
        return -1

    # -------------------------------------------------------------- token

    def token(self, ti: int) -> Token:
        return Token(
            self._lc[ti],
            self._rc[ti],
            self._cost[ti],
            self.pos_table[self._pos[ti]],
            self.conj_table[self._cf[ti]],
        )

    def tokens_at(self, surface_index: int):
        s = self._tok_start[surface_index]
        return [self.token(s + k) for k in range(self._tok_count[surface_index])]

    def tokens_for(self, surf: bytes):
        i = self.find(surf)
        return [] if i < 0 else self.tokens_at(i)

    def connection(self, right_id_prev: int, left_id_next: int) -> int:
        return self.matrix[right_id_prev + self.lsize * left_id_next]

    # -------------------------------------------------------------- 文字種

    def char_info_raw(self, cp: int) -> int:
        starts, infos = self._chars
        lo, hi = 0, len(starts)
        while lo < hi:
            mid = (lo + hi) // 2
            if starts[mid] <= cp:
                lo = mid + 1
            else:
                hi = mid
        return infos[lo - 1]

    def char_info(self, cp: int):
        """(type ビット列, 既定カテゴリ, length, group, invoke)"""
        v = self.char_info_raw(cp if cp < 0xFFFF else 0)
        return (v & 0x3FFFF, (v >> 18) & 0xFF, (v >> 26) & 0xF, (v >> 30) & 1, (v >> 31) & 1)

    def category_rule(self, name: str):
        """char.def と同じ (invoke, group, length) を返す。"""
        return tuple(self.meta["category_rules"][name])

    def unk_tokens(self, category_index: int):
        raw = self.meta["unk"][self.categories[category_index]]
        return [Token(t[0], t[1], t[2], self.pos_table[t[3]], self.conj_table[t[4]]) for t in raw]

    # -------------------------------------------------------------- 検査用

    def with_corrupted_surfaces(self) -> "ShipDict":
        """索引を壊した写しを返す(陽性対照専用)。原本には触れない。"""
        surf = bytearray(self._surf)
        for i in range(0, len(surf), 7):
            surf[i] = (surf[i] + 1) & 0x7F
        surf = bytes(surf)
        return ShipDict(
            self.meta,
            surf,
            self._sidx,
            (self._tok_start, self._tok_count, self._lc, self._rc, self._cost, self._pos, self._cf),
            self.matrix,
            self._chars,
        )


def _read(path, typecode):
    a = array.array(typecode)
    with open(path, "rb") as f:
        a.frombytes(f.read())
    if a.itemsize > 1:
        import sys as _s

        if _s.byteorder != "little":
            a.byteswap()
    return a


def load(dictdir: str) -> ShipDict:
    meta = json.load(open(os.path.join(dictdir, "meta.json"), encoding="utf-8"))
    if meta["format"] != FORMAT:
        raise SystemExit(f"辞書形式の版が違う: {meta['format']} != {FORMAT}")
    j = lambda n: os.path.join(dictdir, n)  # noqa: E731
    surf = open(j("surf.bin"), "rb").read()
    sidx = _read(j("surf_idx.bin"), "I")
    tok = (
        _read(j("tok_start.bin"), "I"),
        _read(j("tok_count.bin"), "B"),
        _read(j("tok_lc.bin"), "H"),
        _read(j("tok_rc.bin"), "H"),
        _read(j("tok_cost.bin"), "h"),
        _read(j("tok_pos.bin"), "B"),
        _read(j("tok_cf.bin"), "H"),
    )
    matrix = _read(j("matrix.bin"), "h")
    ch = _read(j("chars.bin"), "I")
    half = len(ch) // 2
    chars = (ch[:half], ch[half:])
    return ShipDict(meta, surf, sidx, tok, matrix, chars)
