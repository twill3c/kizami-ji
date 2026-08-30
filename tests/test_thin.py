"""T-060〜T-063 — 痩せた辞書(F-10a)の測定結果と、その判定を固定する。

閾値は SPEC §F-10a(G-04a/b/c)に測る前から書いてある。ここでは動かさない。
テストが守るのは「効果があること」ではなく、**測定結果とそこから導いた主張**である。
"""

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

THIN = os.path.join(ROOT, "src", "data", "thin-dict.json")


@pytest.fixture(scope="session")
def thin():
    if not os.path.exists(THIN):
        pytest.skip("src/data/thin-dict.json が無い(scripts/measure_thin.py を先に走らせる)")
    return json.load(open(THIN, encoding="utf-8"))


def row(doc, keep, kind="frequency"):
    src = doc["rows"] if kind == "frequency" else doc["controls"]
    hit = next((r for r in src if r["keep"] == keep), None)
    assert hit is not None, f"{kind} の {keep} 語の行が無い"
    return hit


# ---------------------------------------------------------------- G-04


@pytest.mark.validation
def test_t060_random_words_do_not_help(thin):
    """G-04a —— 無作為に選んだ 1,000 語は、辞書ゼロと実質同じ。

    実測 2026-08-31: 辞書ゼロ 0.7265 / 無作為 1,000 語 0.7264(差 0.0001)。
    """
    zero = thin["zero_f1"]
    rnd = row(thin, 1000, "random")
    assert abs(rnd["f1"] - zero) < 0.01, (
        f"無作為 1,000 語が辞書ゼロと {abs(rnd['f1'] - zero):.4f} 違う。"
        "効くようになったなら SPEC F-10a の主張を見直すこと")


@pytest.mark.validation
def test_t061_frequent_words_do_help(thin):
    """G-04b —— 頻度上位 1,000 語は、辞書ゼロより 0.15 以上高い。

    実測 2026-08-31: 0.9099 − 0.7265 = 0.1834。
    """
    zero = thin["zero_f1"]
    top = row(thin, 1000)
    assert top["f1"] - zero >= 0.15, (
        f"頻度上位 1,000 語の上積みが {top['f1'] - zero:.4f} しかない")


@pytest.mark.validation
def test_t062_random_control_is_not_idle(thin):
    """G-04c —— 無作為辞書の語が**実際に使われている**こと。

    使われずに効かないのでは対照にならない(検査が空回りしているのと区別がつかない)。
    実測: 無作為 1,000 語は 85,249 トークン中 460 に使われた。
    """
    for k in (1000, 100):
        c = row(thin, k, "random")
        assert c["dict_tokens"] > 0, f"無作為 {k} 語が一度も使われていない ── 対照が空回り"
        assert c["tokens"] > 10_000, "評価に使ったトークンが少なすぎる"


# ---------------------------------------------------------------- 測定の健全性


@pytest.mark.validation
def test_t063_curve_is_monotonic_in_f1(thin):
    """語数を減らすほど、境界の一致は下がる(単調)。

    ここが崩れたら、刈り方か測り方が壊れている。
    ただし**個々の語の切れ方は単調ではない**(T-064 が実例で押さえる)。
    """
    rows = sorted(thin["rows"], key=lambda r: -r["keep"])
    f1s = [r["f1"] for rows_ in [rows] for r in rows_]
    assert f1s == sorted(f1s, reverse=True), f"F1 が単調でない: {f1s}"
    assert rows[-1]["keep"] == 0 and rows[-1]["unknown_share"] == 1.0, (
        "辞書ゼロの行で未知語率が 100% になっていない")


@pytest.mark.validation
def test_t064_showcase_matches_the_text_on_the_page(thin):
    """画面が名指ししている実例が、焼いたデータのとおりであること(HC-045)。

    ページは (a) 完全辞書が「學生」を割ること (b) 300 語まで刈ると一語に戻ること
    (c)「首都」が途中で割れて戻ること、の三つを本文で名指ししている。
    データが変わったら本文も直す必要があるので、ここで縛る。
    """
    sc = next((x for x in thin["showcase"] if "學生" in x["text"]), None)
    assert sc is not None, "「學生」を含む実例が焼かれていない"
    full = next(s for s in sc["steps"] if s.get("full"))
    small = next(s for s in sc["steps"] if s["keep"] == 300)
    assert "學生" not in full["words"], "完全辞書が「學生」を一語にしている ── 本文の説明と違う"
    assert "學" in full["words"] and "生" in full["words"]
    assert "學生" in small["words"], "300 語の辞書が「學生」を一語にしていない ── 本文の説明と違う"

    sc2 = next((x for x in thin["showcase"] if "首都" in x["text"]), None)
    assert sc2 is not None
    by = {s["keep"]: s["words"] for s in sc2["steps"]}
    full2 = next(s for s in sc2["steps"] if s.get("full"))
    assert "首都" in full2["words"], "完全辞書が「首都」を一語にしていない"
    assert "首都" not in by[3000], "3,000 語で「首都」が割れていない ── 非単調の実例が消えた"
    assert "首都" in by[300], "300 語で「首都」が戻っていない ── 非単調の実例が消えた"


@pytest.mark.validation
def test_t065_groups_are_disjoint(thin):
    """頻度を取る群と測る群が分かれていること(循環の禁止)。

    件数だけで確かめられることは限られるが、少なくとも両方が空でないこと、
    測定側が十分な大きさであることは押さえる。分割そのものの検算は
    scripts/measure_thin.py が実行時に行い、重なりがあれば落ちる。
    """
    assert thin["freq_sentences"] >= 10_000
    assert thin["eval_sentences"] >= 3_000
    assert thin["surface_used"] < thin["surface_total"], "刈る余地が無い"
