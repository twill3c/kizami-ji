"""T-030 / T-031 / T-032 / T-034 — δ の定義と、G-01 が落ちたという決定の固定。

G-01 は 2026-08-30 に**不通過**だった(SPEC F-32b・docs/g01-findings.md)。
ここのテストは「効果があること」ではなく、**測定結果と、それに基づく決定**を守る。
落ちたゲートを黙って復活させないための錠前である。
"""

import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from analyze import INF, Analyzer, delta_local  # noqa: E402

DICT = os.path.join(ROOT, "data", "dict")
G01 = os.path.join(ROOT, "data", "g01.json")


@pytest.fixture(scope="session")
def analyzer():
    return Analyzer.load(DICT)


def _spanning(a, raw, p):
    """位置 p を内側に含む候補ノードを集める。

    **文字境界からしか候補を作らない。** UTF-8 の継続バイトから candidates() を呼ぶと、
    実装が想定しない位置の偽の候補が出る(analyze() は 0xC0 マスクで弾いている)。
    """
    out = []
    for pos in range(len(raw)):
        if (raw[pos] & 0xC0) == 0x80:
            continue
        out += [c for c in a.candidates(raw, pos) if c[1] < p < c[0]]
    return out


@pytest.fixture(scope="session")
def g01():
    if not os.path.exists(G01):
        pytest.skip("data/g01.json が無い(scripts/measure_g01.py を先に走らせる)")
    return json.load(open(G01, encoding="utf-8"))


# ---------------------------------------------------------------- T-030


@pytest.mark.validation
def test_t030_delta_is_local_and_means_a_different_split(analyzer):
    """δ_local(p) は「p をまたぐノードを含む最良経路」との差である。

    したがって δ が有限な境界には、必ず**分割の異なる**経路が存在する。
    期待値の出所: SPEC F-04a と §6 の実測(2026-08-29)。
    """
    r, d = delta_local(analyzer, "の北詰まで")
    raw = "の北詰まで".encode("utf-8")
    # 「の北」の後ろ(バイト 6)は 北詰 が跨ぐので δ = 0(完全同点)
    assert d[6] == 0
    # 「の」の後ろは跨ぐ語が無いので ∞
    assert d[3] == INF
    assert r.words == ["の", "北", "詰", "まで"]

    # δ が有限なら、その境界を跨ぐ分割が実在する
    text = "東京都は日本の首都である"
    r2, d2 = delta_local(analyzer, text)
    finite = [p for p, v in d2.items() if v != INF]
    assert finite, "有限の δ を持つ境界が一つも無い ── 検査対象になっていない"
    raw2 = text.encode("utf-8")
    for p in finite:
        assert _spanning(analyzer, raw2, p), f"δ が有限なのに位置 {p} を跨ぐ候補が無い"


@pytest.mark.validation
def test_t030b_infinite_delta_means_no_spanning_word(analyzer):
    """δ = ∞ の境界には、跨ぐ候補が本当に一つも無い(陰性側の検算)。"""
    text = "東京都は日本の首都である"
    raw = text.encode("utf-8")
    _r, d = delta_local(analyzer, text)
    infs = [p for p, v in d.items() if v == INF]
    assert infs, "∞ の境界が一つも無い ── 検査対象になっていない"
    for p in infs:
        got = _spanning(analyzer, raw, p)
        assert not got, f"∞ なのに位置 {p} を跨ぐ候補がある: {got[:1]}"


# ---------------------------------------------------------------- T-031 / T-032


@pytest.mark.validation
def test_t031_g01_did_not_meet_the_threshold(g01):
    """G-01 は閾値に届かなかった。**この事実を固定する。**

    届くようになったら、このテストが落ちる ── そのときは SPEC F-32b を見直すこと。
    実測 2026-08-30: 比 1.193(閾値 1.5)/ Spearman −0.0295 / 境界 400,456 件。
    """
    p = g01["primary"]
    assert p["n"] > 100_000, f"標本が少なすぎる({p['n']})"
    assert g01["threshold"]["ratio"] == 1.5
    assert p["ratio_q1_over_q4"] < 1.5, (
        f"比が閾値に届いている({p['ratio_q1_over_q4']:.3f})── "
        "G-01 が通ったなら SPEC F-32b の決定を見直すこと")
    assert abs(p["spearman_rho"]) < 0.05, "相関が無視できない大きさになった。再判定が要る"


@pytest.mark.validation
def test_t032_effect_reverses_inside_kanji_runs(g01):
    """交絡検査 —— 漢字連続の内部に限ると効果が反転する。

    全体で見えたわずかな効果が「漢字らしさ」の影であることの記録。
    """
    p, k = g01["primary"], g01["kanji_only"]
    assert k["n"] > 10_000
    assert k["ratio_q1_over_q4"] < 1.0, "部分集団で効果が反転していない。再判定が要る"
    # 交絡そのもの: δ 小の境界は漢字連続の内部に多い
    assert p["kanji_run_share_q1"] > p["kanji_run_share_q4"] * 1.5


@pytest.mark.validation
def test_t032b_shuffle_control_was_run(g01):
    """δ シャッフルの対照が実際に走っていること(対照の不在を緑にしない)。"""
    assert g01["primary"]["shuffles"] >= 2000
    assert "empirical_p" in g01["primary"]


# ---------------------------------------------------------------- T-034


def _shipped_text_files():
    """出荷物の本文が入る場所。まだ無いディレクトリは飛ばす。"""
    out = []
    for sub in ("src", "app", "content"):
        d = os.path.join(ROOT, sub)
        if not os.path.isdir(d):
            continue
        for base, dirs, names in os.walk(d):
            dirs[:] = [x for x in dirs if x not in ("node_modules", ".next")]
            for nm in names:
                if os.path.splitext(nm)[1] in (".ts", ".tsx", ".md", ".mdx", ".json"):
                    out.append(os.path.join(base, nm))
    return out


def _forbidden_words():
    """δ を正しさと結びつける語。符号位置から組み立てる(原稿に書くと自分を撃つ)。"""
    return [
        "".join(map(chr, [0x5371, 0x3046])),                    # 危う
        "".join(map(chr, [0x9593, 0x9055, 0x3044, 0x3084])),    # 間違いや
        "".join(map(chr, [0x8AA4, 0x308A, 0x3084])),            # 誤りや
        "".join(map(chr, [0x8AA4, 0x89E3, 0x6790])),            # 誤解析
    ]


@pytest.mark.validation
def test_t034_shipped_text_does_not_call_delta_dangerous():
    """G-01 が落ちている間、出荷物の本文が δ を「危うさ」と結びつけていないこと(F-32b)。

    走査対象が空でないこと、および検査器が本当に働くことを対で確かめる(HC-041)。
    """
    files = _shipped_text_files()
    assert files, "走査対象が空 ── 検査が働いていない"
    words = _forbidden_words()
    hits = []
    for p in files:
        try:
            text = open(p, encoding="utf-8").read()
        except UnicodeDecodeError:
            continue
        for w in words:
            if w in text:
                hits.append((os.path.relpath(p, ROOT), w))
    assert hits == [], f"出荷物の本文に禁止語がある(SPEC F-32b): {hits}"

    # 陽性対照 ── 検査器が語を見つけられること
    probe = "この境界は" + words[0] + "い。"
    assert any(w in probe for w in words), "陽性対照が働かない"
    # 陰性対照 ── 正当な本文を撃たない
    ok = "δ は解析器が迷った量である。正しさとは結びつけない。"
    assert not any(w in ok for w in words), "正当な本文を撃っている"
