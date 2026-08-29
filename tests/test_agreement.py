"""T-010〜T-013 / T-020 — 出荷用辞書だけで動く解析器を MeCab と突き合わせる。

期待値の出所: fugashi + ipadic(**外部権威**)。出荷実装はこれを一切参照しない(O-2)。
件数は定数で書かず「不一致が無い」という不変量で書く(HC-016)。
"""

import os
import random
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import check_agreement as ca  # noqa: E402
from analyze import Analyzer  # noqa: E402

DICT = os.path.join(ROOT, "data", "dict")


@pytest.fixture(scope="session")
def analyzer():
    return Analyzer.load(DICT)


@pytest.fixture(scope="session")
def tagger():
    return ca.make_tagger()


@pytest.fixture(scope="session")
def corpus():
    if not os.path.isdir(ca.CORPUS):
        pytest.skip("aozora-sakuin のコーパスが見つからない")
    s = ca.sample_sentences(10000)
    assert len(s) == 10000, f"標本が揃っていない({len(s)} 文)"
    return s


# ---------------------------------------------------------------- T-010 / T-011


@pytest.mark.validation
def test_t010_t011_agreement_with_mecab(analyzer, tagger, corpus):
    """総コスト(O-1a)と分割(O-1b)が MeCab と一致する。

    どちらも閾値は 100.0000% ── 1 件でも不一致なら不合格(SPEC §4)。
    """
    cost_bad, seg_bad, no_path = [], [], []
    for s in corpus:
        r = analyzer.analyze(s)
        if r is None:
            no_path.append(s)
            continue
        mt, mw = ca.mecab_parse(tagger, s)
        if mt != r.cost:
            cost_bad.append((s, mt, r.cost))
        if mw != r.words:
            seg_bad.append((s, mw, r.words))
    assert no_path == [], f"経路が見つからない文が {len(no_path)} 件"
    assert cost_bad == [], f"O-1a 総コスト不一致 {len(cost_bad)} 件: {cost_bad[:2]}"
    assert seg_bad == [], f"O-1b 分割不一致 {len(seg_bad)} 件: {seg_bad[:2]}"


@pytest.mark.validation
def test_t011b_agreement_out_of_sample(analyzer, tagger):
    """タイブレーク規則は 7 件の同点を見て決めた。別の種・別の作品で外挿を確かめる。

    同じ標本で合わせた規則を同じ標本で検証すれば循環する(SPEC「循環の禁止」)。
    """
    if not os.path.isdir(ca.CORPUS):
        pytest.skip("aozora-sakuin のコーパスが見つからない")
    sents = ca.sample_sentences(5000, seed=20260830)
    bad = []
    for s in sents:
        r = analyzer.analyze(s)
        mt, mw = ca.mecab_parse(tagger, s)
        if r is None or mt != r.cost or mw != r.words:
            bad.append(s)
    assert bad == [], f"外挿で {len(bad)} 件不一致: {bad[:2]}"


# ---------------------------------------------------------------- T-012


@pytest.mark.validation
def test_t012_exact_tie_exists(analyzer):
    """完全同点が実在する(SPEC §6 / docs/probe-000.md・実測 2026-08-29)。

    タイブレーク規則を揃えた後は、同点は「MeCab との食い違い」としては現れない。
    δ = 0 として現れることを、全経路列挙で直接示す。
    """
    from itertools import count  # noqa: F401

    text = "の北詰まで"
    paths = enumerate_paths(analyzer, text)
    assert len(paths) > 1, "経路が 1 本しかない ── 検査対象になっていない"
    best = paths[0][0]
    second_split = next((p for p in paths if p[1] != paths[0][1]), None)
    assert second_split is not None, "分割の異なる第二の経路が無い"
    assert second_split[0] == best, (
        f"δ = {second_split[0] - best} ── 完全同点になっていない")
    # 上位二つの分割は「北詰」と「北 / 詰」であること
    assert {tuple(paths[0][1]), tuple(second_split[1])} == {
        ("の", "北詰", "まで"), ("の", "北", "詰", "まで")}


def enumerate_paths(a, text):
    """短い文の全経路を (総コスト, 語列) で列挙し、コスト昇順に返す(検査用)。"""
    d = a.d
    raw = text.encode("utf-8")
    n = len(raw)
    out = []

    def go(pos, prc, cost, path):
        if pos == n:
            out.append((cost + d.connection(prc, 0), list(path)))
            return
        for (e, s, t, _unk) in a.candidates(raw, pos):
            path.append(raw[s:e].decode("utf-8"))
            go(e, t.rc, cost + d.connection(prc, t.lc) + t.cost, path)
            path.pop()

    go(0, 0, 0, [])
    out.sort(key=lambda x: x[0])
    return out


# ---------------------------------------------------------------- T-013


@pytest.mark.validation
def test_t013_unknown_nodes_match_mecab(analyzer, tagger):
    """未知語ノードの範囲と未知語判定が MeCab と一致する。

    MeCab の %s は 0=既知語 / 1=未知語。表層の切れ目と合わせて突き合わせる。
    """
    if not os.path.isdir(ca.CORPUS):
        pytest.skip("aozora-sakuin のコーパスが見つからない")
    import fugashi
    import ipadic

    d = ipadic.DICDIR.replace("\\", "/")
    rc = os.path.join(ROOT, "probe", "mecabrc").replace("\\", "/")
    # fugashi は引数を空白で分割するので、-E に空文字は渡せない。番兵を置いて後で落とす
    tg = fugashi.GenericTagger(" ".join(["-r", rc, "-d", d, "-F%m@%s|", "-E", "EOS@9|"]))
    sents = [s for s in ca.sample_sentences(3000, seed=20260831)]
    # 未知語を含む文だけを対象にする(対象が空でないことを検算する)
    targets, bad = [], []
    for s in sents:
        parts = [p for p in tg.parse(s).split("|") if p]
        assert parts[-1] == "EOS@9", f"番兵が期待どおりに出ていない: {parts[-1]!r}"
        want = [(p.rsplit("@", 1)[0], p.rsplit("@", 1)[1] == "1") for p in parts[:-1]]
        if not any(u for _, u in want):
            continue
        targets.append(s)
        r = analyzer.analyze(s)
        got = [(x.surface, x.unknown) for x in r.nodes]
        if got != want:
            bad.append((s, want, got))
    assert len(targets) > 100, f"未知語を含む文が少なすぎる({len(targets)})── 検査が働いていない"
    assert bad == [], f"未知語の扱いが {len(bad)} 件食い違う: {bad[:1]}"


# ---------------------------------------------------------------- T-020(陰性対照)


@pytest.mark.validation
def test_t020_shuffled_matrix_breaks_agreement(analyzer, tagger):
    """連接表をシャッフルした辞書では O-1a が崩れる。

    崩れなければ T-010 は何も検査していない(HC-041 / HC-051)。
    """
    import array
    import copy

    broken = copy.copy(analyzer)
    m = array.array("h", analyzer.d.matrix)
    rnd = random.Random(20260830)
    rnd.shuffle(m)
    broken.d = copy.copy(analyzer.d)
    broken.d.matrix = m

    sents = ca.sample_sentences(200, seed=20260829)
    assert sents, "対象が空"
    disagree = 0
    for s in sents:
        mt, mw = ca.mecab_parse(tagger, s)
        r = broken.analyze(s)
        if r is None or r.cost != mt or r.words != mw:
            disagree += 1
    assert disagree > len(sents) * 0.5, (
        f"連接表を壊しても {disagree}/{len(sents)} しか崩れない ── 検査が連接表を見ていない")

    # 陽性側: 壊していない辞書では同じ標本が全て一致する
    ok = sum(1 for s in sents
             if (lambda r, mv: r is not None and r.cost == mv[0] and r.words == mv[1])(
                 analyzer.analyze(s), ca.mecab_parse(tagger, s)))
    assert ok == len(sents), f"正常な辞書で {len(sents) - ok} 件不一致"
