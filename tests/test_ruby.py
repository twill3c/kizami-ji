"""ルビ抽出の検査 — T-033 と残骸ゲート。

ルビは G-01 の**外部の物差し**である。物差しが解析器に依存していたら循環する(SPEC「循環の禁止」)。
また、取りこぼしは件数ではなく**述語**で見る(HC-030 / furigana-keiryo HC-035)——
「基底なし 374 件」は総ルビ 188 万件の 0.02% で、比率にすれば誤差として通せてしまう。
"""

import os
import random
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import ruby as R  # noqa: E402

RAW = os.path.join(ROOT, "..", "aozora-sakuin", "data", "raw")


@pytest.fixture(scope="session")
def works():
    if not os.path.isdir(RAW):
        pytest.skip("aozora-sakuin の raw が見つからない")
    files = sorted(os.listdir(RAW))
    return [os.path.join(RAW, f) for f in random.Random(20260830).sample(files, 120)]


# ---------------------------------------------------------------- 残骸ゲート


@pytest.mark.validation
def test_residual_gate_has_no_kanji_base(works):
    """地の文の残骸に**漢字基底の 《** が一件も無いこと。

    件数ではなく述語で書く。この述語が、外字注記の直後のルビを丸ごと落としていた
    欠陥を掘り出した(loop_004・200 作で 267 件)。
    """
    bad = []
    for p in works:
        _body, _spans, residue = R.extract(open(p, encoding="utf-8", errors="replace").read())
        bad += R.residual_violations(residue)
    assert bad == [], f"漢字基底の残骸が {len(bad)} 件: {bad[:3]}"


@pytest.mark.validation
def test_residual_gate_positive_control():
    """残骸ゲートが本当に働くことの陽性対照。

    捕まえるべき例は**符号位置から組み立てる**。原稿に直接書くと、この原稿を走査する
    検査が自分の対照を撃つ(ai-trilogy HC-002)。
    """
    kanji = chr(0x7B0A)          # 笊
    lb, rb = chr(0x300A), chr(0x300B)
    assert R.residual_violations([f"...{kanji}{lb}ざる{rb}..."]), "陽性対照を捕まえられない"
    assert R.residual_violations([f"...{lb}ざる{rb}..."]) == [], "基底の無い例を誤って撃っている"


@pytest.mark.validation
def test_legend_block_is_stripped(works):
    """凡例ブロックの偽ルビを数えていないこと。

    凡例には 《》 と ｜ の実例が入っている。剥がさないと全作品に同じ偽ルビが乗る。
    """
    stripped = 0
    for p in works:
        raw = open(p, encoding="utf-8", errors="replace").read()
        body = R.split_body(raw)
        if "【テキスト中に現れる記号について】" in raw:
            stripped += 1
            assert "【テキスト中に現れる記号について】" not in body
            assert "：ルビ" not in body
    assert stripped > 10, f"凡例つきの作品が {stripped} 件しか無い ── 検査が働いていない"


# ---------------------------------------------------------------- T-033


@pytest.mark.validation
def test_t033_ruby_extractor_uses_no_analyzer():
    """ルビ抽出が形態素解析に依存していないこと(循環の禁止)。

    禁止語は符号位置から組み立てる。走査対象が空でないことも確かめる。
    """
    src = open(os.path.join(ROOT, "scripts", "ruby.py"), encoding="utf-8").read()
    assert len(src) > 1000, "走査対象が空(検査が働いていない)"
    code = src
    # コメント行を落とす ── 言及は依存ではない
    code = "\n".join(l for l in code.split("\n") if not l.lstrip().startswith("#"))
    code = re.sub(r'"""[\s\S]*?"""', "", code)
    forbidden = [
        "".join(map(chr, [97, 110, 97, 108, 121, 122, 101])),          # analyze
        "".join(map(chr, [115, 104, 105, 112, 100, 105, 99, 116])),    # shipdict
        "".join(map(chr, [102, 117, 103, 97, 115, 104, 105])),         # fugashi
        "".join(map(chr, [105, 112, 97, 100, 105, 99])),               # ipadic
    ]
    hits = [w for w in forbidden if w in code]
    assert hits == [], f"ルビ抽出が解析器に依存している: {hits}"
    # 陽性対照 ── 同じ検査で、依存を足したソースが捕まること
    injected = code + "\nimport " + forbidden[0] + "\n"
    assert [w for w in forbidden if w in injected], "陽性対照が働かない"


# ---------------------------------------------------------------- 括りの性質


@pytest.mark.validation
def test_bar_spans_are_explicit_brackets(works):
    """｜ つきの括りが実在し、自動推定より短いこと。

    自動推定(直前の同一文字クラス連続)は記法上の既定であって人間の区切りではない。
    実測で「処躊躇」「多年斯」のような非語が取れる。｜ は書き手が明示的に括った印である。
    """
    bar = auto = 0
    bar_len = []
    for p in works:
        _b, spans, _r = R.extract(open(p, encoding="utf-8", errors="replace").read())
        for sp in spans:
            if sp.bar:
                bar += 1
                bar_len.append(sp.length)
            else:
                auto += 1
    assert bar > 100, f"｜ つきの括りが {bar} 件しか無い ── 母集団として使えない"
    assert auto > bar, "自動推定のほうが少ない ── 抽出がおかしい"


@pytest.mark.validation
def test_bar_bases_contain_no_annotation_residue(works):
    """基底に注記の生テキストが混ざっていないこと。

    最初は「基底が長すぎないこと」で見ようとして、長さの上限を**観測せずに**書いた。
    実データには 23 文字の正当な基底があった ——
    「早く歸つてね、私の好いお友達大すきなジャネット」にフランス語の読みを振った例である。
    長さは注記混入の代理にすぎない。**述語で書く**(HC-030)。

    この述語は実際に欠陥を掘り出した: ｜ 分岐が注記を素通りさせており、
    ※［＃「罘」の「不」に代えて…］ が丸ごと基底に入っていた(120 作で 47 件)。
    """
    marks = [chr(0xFF3B), chr(0xFF03), chr(0xFF3D), chr(0xFF3B - 0xFF3B + 0x203B)]  # ［ ＃ ］ ※
    bad = []
    checked = 0
    for p in works:
        body, spans, _r = R.extract(open(p, encoding="utf-8", errors="replace").read())
        for sp in spans:
            checked += 1
            base = body[sp.start:sp.end]
            if any(m in base for m in marks):
                bad.append((os.path.basename(p), base[:40]))
    assert checked > 1000, f"検査した括りが {checked} 件しか無い ── 検査が働いていない"
    assert bad == [], f"基底に注記が混ざっている {len(bad)} 件: {bad[:3]}"
    # 陽性対照 ── 述語が本当に働くこと
    probe = "昵" + marks[3] + marks[0] + marks[1] + "…" + marks[2]
    assert any(m in probe for m in marks), "陽性対照が働かない"
    assert not any(m in "浮世小路" for m in marks), "正当な基底を撃っている"
