"""青空文庫の生テキストから本文とルビの括りを取り出す。

**形態素解析を一切使わない**(SPEC G-01 / T-033)。基底の推定は文字クラスの連続だけで行う。
これが「循環の禁止」の要 —— ルビは辞書と無関係に存在する人間の区切りでなければ、
δ を採点する物差しにならない。

規則は furigana-keiryo の `lib/aozora/{document,notation}.rb` を Python へ移したもの。
あちらで実測から判明した形(凡例ブロックの偽ルビ・入れ子注記・記号基底)をそのまま引き継ぐ。

    from ruby import extract
    body, spans = extract(open(path, encoding="utf-8").read())
    # spans は body 上の [start, end) 文字位置(基底の範囲)
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

RULE = re.compile(r"^-{20,}$")
COLOPHON = re.compile(r"^底本[：:]")

# 基底の推定に使う文字クラス。同一クラスの連続を基底とみなす。
# 記号・ギリシャ・キリルまで入れるのは、furigana-keiryo が残骸を実例まで見て見つけた形
#   ＭＲ《ミスタ》(051250) / γ《ガムマア》(001058) / Л《エル》(051847) / ＋《よこじゅうじ》(001317)
_CLASS_PATTERNS = [
    # 〓 は外字注記の置き換え。外字の直後にルビが来る形が実在するので、
    # 〓 を漢字クラスに入れないと基底が取れず、そのルビが丸ごと残骸へ落ちる(残骸ゲートで発見)
    re.compile(r"[一-鿿々〆ヶヵ〓豈-﫿㐀-䶵]"),  # 漢字・々・〆・ヶヵ
    re.compile(r"[ァ-ヺーー]"),                                     # カタカナ
    re.compile(r"[ぁ-ゟ]"),                                             # ひらがな
    re.compile(r"[A-Za-zＡ-Ｚａ-ｚ]"),
    re.compile(r"[0-9０-９]"),
    re.compile(r"[Ͱ-Ͽ]"),                                             # ギリシャ
    re.compile(r"[Ѐ-ӿ]"),                                             # キリル
]
KANJI = re.compile(r"[一-鿿々〆ヶヵ]")
GETA = "〓"  # 外字注記の置き換え。落として詰めると隣り合わなかった漢字がくっつく


@dataclass
class Span:
    start: int
    end: int
    reading: str
    #: ｜ で明示的に括られた基底か。
    #: 括りが無い場合、基底は「直前の同一文字クラスの連続」という**記法上の既定**で決まる。
    #: これは青空文庫の規則どおりだが、**人間が一語と見た証拠ではない** ——
    #: 実測で「処躊躇」「多年斯」「至大艱難」のような非語が取れる(loop_004)。
    #: 人間の区切りを物差しにしたいときは bar=True のものだけを使う。
    bar: bool = False

    @property
    def length(self) -> int:
        return self.end - self.start


def split_body(raw: str) -> str:
    """凡例ブロックと奥付を落として本文だけにする。

    凡例には 《》 と ｜ の**実例**が入っている(お葉《えふ》)。剥がさずに数えると
    全作品に同じ偽のルビが乗る。本文切り出しは前処理ではなく計量の一部である。
    """
    lines = raw.split("\n")
    rules = [i for i, l in enumerate(lines) if RULE.match(l.strip())]
    if len(rules) >= 2 and rules[1] < 60:
        first = rules[1] + 1
    else:
        i = 0
        while i < len(lines) and lines[i].strip():
            i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        first = i
    last = next((i for i in range(first, len(lines)) if COLOPHON.match(lines[i].strip())),
                len(lines))
    return "\n".join(lines[first:last]).strip()


def _scan_annotation(src: str, i: int) -> int:
    """［＃ … ］ を 1 件読み飛ばす。**括弧の深さを数える。**

    入れ子は実在する(001805): ［＃「小笊《こざる》」は底本では「小※［＃…］《こざる》」］
    入れ子を許さない ［＃[^］]*］ は内側の ］ で閉じ、残りが地の文へ落ちる。
    落ちた残骸には 笊《 のような**漢字基底のルビが含まれる**ので、計量が静かに狂う。
    """
    depth = 0
    while i < len(src):
        if src.startswith("［＃", i):
            depth += 1
            i += 2
        elif src[i] == "］":
            depth -= 1
            i += 1
            if depth == 0:
                return i
        else:
            i += 1
    return len(src)


def _take_base(buf: list) -> int:
    """buf の末尾から基底として取り込める文字数を返す(同一文字クラスの連続)。"""
    if not buf:
        return 0
    last = buf[-1]
    cls = next((p for p in _CLASS_PATTERNS if p.match(last)), None)
    if cls is None:
        return 0
    n = 0
    while n < len(buf) and cls.match(buf[-1 - n]):
        n += 1
    return n


def extract(raw: str):
    """(本文, ルビの括り一覧, 残骸) を返す。

    残骸は「基底が取れずに地の文へ戻した 《》」の前後文脈。HC-035 のとおり、
    **件数ではなく述語で見る** —— 地の文の残骸に漢字基底の 《 が一件も無いこと。
    """
    src = split_body(raw)
    out: list = []
    spans: list = []
    residue: list = []
    i = 0
    n = len(src)
    while i < n:
        if src.startswith("※［＃", i):
            j = _scan_annotation(src, i + 1)
            out.append(GETA)
            i = j
        elif src.startswith("［＃", i):
            i = _scan_annotation(src, i)
        elif src[i] == "｜":
            # ｜ 以降・次の 《 までが基底。**この途中にも注記が入る**ので、
            # 素朴に ｜([^《》｜]*)《 で取ると注記の生テキストが基底に混ざり、本文を汚す
            # (実測: ※［＃「罘」の「不」に代えて…］昵※［＃…］ が 61 文字の基底になっていた)
            base: list = []
            j = i + 1
            while j < len(src) and src[j] not in "《》｜":
                if src.startswith("※［＃", j):
                    k = _scan_annotation(src, j + 1)
                    base.append(GETA)
                    j = k
                elif src.startswith("［＃", j):
                    j = _scan_annotation(src, j)
                else:
                    base.append(src[j])
                    j += 1
            m = re.compile(r"《([^》]*)》").match(src, j) if j < len(src) else None
            if m:
                if base:
                    spans.append(Span(len(out), len(out) + len(base), m.group(1), True))
                out.extend(base)
                i = m.end()
            else:
                # 《 が来なければ ｜ は地の文の記号。読み直させる
                out.append("｜")
                i += 1
        elif src[i] == "《":
            m = re.compile(r"《([^》]*)》").match(src, i)
            if m:
                k = _take_base(out)
                if k == 0:
                    residue.append(src[max(0, i - 12): i + 12])
                    out.extend(m.group(0))
                else:
                    spans.append(Span(len(out) - k, len(out), m.group(1), False))
                i = m.end()
            else:
                out.append(src[i])
                i += 1
        else:
            out.append(src[i])
            i += 1
    return "".join(out), spans, residue


def residual_violations(residue: list) -> list:
    """残骸のうち**漢字基底のルビ**を含むもの。これが 0 件であることがゲート(HC-030/HC-035)。

    件数で報告してはならない ── 総ルビ数に対する比率にすれば、どんな取りこぼしも誤差に見える。
    """
    pat = re.compile(r"[一-鿿々〆ヶヵ]《")
    return [r for r in residue if pat.search(r)]
