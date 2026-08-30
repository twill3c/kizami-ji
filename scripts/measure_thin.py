"""F-10a 痩せた辞書 —— 語彙を刈った辞書での劣化を測り、事前に焼く。

**閾値は SPEC §F-10a に書いてある(G-04a/b/c)。ここでは動かさない。**

循環の禁止: 語の頻度は A 群から取り、劣化は B 群で測る(互いに素)。
同じ文で頻度を取って同じ文で測れば「使った語は残る」ので何も分からない。

指標の性格: 境界 F1 は**完全辞書との一致度**であって、正しさではない。
人手の正解とは照合していない。画面にもそう書く。

    python scripts/measure_thin.py --out src/data/thin-dict.json
"""

from __future__ import annotations

import argparse
import array
import collections
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import check_agreement as ca  # noqa: E402
import shipdict  # noqa: E402
from analyze import INF, Analyzer, delta_local  # noqa: E402

#: 残す語数。A 群で使われた全部(可変)を先頭に足す
LEVELS = [10000, 3000, 1000, 300, 100, 30, 0]

#: 画面で段階的に崩れる様子を見せる文。すべて青空文庫の実文(作例は使わない)
SHOWCASE = [
    "親譲りの無鉄砲で小供の時から損ばかりしている。",
    "東京都は日本の首都である",
    "そして今朝がたのリユクサツクの學生を思ひ出した。",
]


def prune(d: shipdict.ShipDict, keep) -> shipdict.ShipDict:
    """表層 index の集合 keep だけを残した辞書を作る。連接表・文字種・未知語は触らない。"""
    ks = sorted(keep)
    blob = bytearray()
    sidx = [0]
    tstart, tcount = [], []
    lc, rc, cost, pos, cf = [], [], [], [], []
    for i in ks:
        blob += d.surface(i)
        sidx.append(len(blob))
        tstart.append(len(lc))
        n = d._tok_count[i]
        tcount.append(n)
        s0 = d._tok_start[i]
        for k in range(n):
            lc.append(d._lc[s0 + k])
            rc.append(d._rc[s0 + k])
            cost.append(d._cost[s0 + k])
            pos.append(d._pos[s0 + k])
            cf.append(d._cf[s0 + k])
    tok = (
        array.array("I", tstart), array.array("B", tcount), array.array("H", lc),
        array.array("H", rc), array.array("h", cost), array.array("B", pos),
        array.array("H", cf),
    )
    return shipdict.ShipDict(d.meta, bytes(blob), array.array("I", sidx), tok,
                             d.matrix, d._chars)


def boundaries(r):
    return {n.end for n in r.nodes[:-1]}


def evaluate(pa: Analyzer, reference: dict, with_delta: bool):
    tp = fp = fn = 0
    exact = unk = toks = 0
    n_inf = n_b = 0
    costs = []
    used = 0
    for s, rf in reference.items():
        r = pa.analyze(s)
        if r is None:
            continue
        bf, bp = boundaries(rf), boundaries(r)
        tp += len(bf & bp)
        fp += len(bp - bf)
        fn += len(bf - bp)
        if r.words == rf.words:
            exact += 1
        for n in r.nodes:
            toks += 1
            if n.unknown:
                unk += 1
            else:
                used += 1
        costs.append(r.cost)
        if with_delta:
            _r, ds = delta_local(pa, s)
            n_inf += sum(1 for v in ds.values() if v == INF)
            n_b += len(ds)
    f1 = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
    return {
        "f1": round(f1, 4),
        "exact": round(exact / len(reference), 4),
        "unknown_share": round(unk / max(1, toks), 4),
        "dict_tokens": used,
        "tokens": toks,
        "tokens_per_sentence": round(toks / len(reference), 2),
        "inf_share": round(n_inf / n_b, 4) if n_b else None,
        "mean_cost": round(sum(costs) / max(1, len(costs))),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freq", type=int, default=20000)
    ap.add_argument("--eval", dest="ev", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=20260904)
    ap.add_argument("--out", default=os.path.join(ROOT, "src", "data", "thin-dict.json"))
    args = ap.parse_args()

    d = shipdict.load(os.path.join(ROOT, "data", "dict"))
    a = Analyzer(d)
    sents = ca.sample_sentences(args.freq + args.ev + 2000, seed=args.seed, lo=6, hi=80)
    # 同じ文字列の文が複数の作品に現れる(「紀久ちゃん!」など)。
    # 重複を残したまま前後で切ると A 群と B 群に同じ文が入り、循環の禁止に反する。
    # 実測では 26,000 文中 42 種・のべ 109、A と B の重なりは 17 文だった(loop_010)
    seen = set()
    uniq = []
    for x in sents:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    A = uniq[: args.freq]
    B = uniq[args.freq : args.freq + args.ev]
    overlap = set(A) & set(B)
    if overlap:
        raise SystemExit(f"A 群と B 群が重なっている({len(overlap)} 文)。循環の禁止に反する")
    if len(B) < args.ev:
        raise SystemExit(f"B 群が {len(B)} 文しか取れない(要求 {args.ev})")

    print(f"A 群 {len(A):,} 文(頻度)/ B 群 {len(B):,} 文(評価)")
    use = collections.Counter()
    for s in A:
        r = a.analyze(s)
        if r is None:
            continue
        raw = s.encode("utf-8")
        for n in r.nodes:
            if n.unknown:
                continue
            i = d.find(raw[n.start : n.end])
            if i >= 0:
                use[i] += 1
    order = [i for i, _ in use.most_common()]
    print(f"表層 {d.surface_count:,} 種のうち A 群で使われたのは {len(order):,} 種"
          f"({len(order) / d.surface_count:.1%})")

    reference = {}
    for s in B:
        r = a.analyze(s)
        if r is not None:
            reference[s] = r
    print(f"基準(完全辞書)で解析できた B 群の文: {len(reference):,}")

    rnd = random.Random(args.seed)
    rows = []
    levels = [len(order)] + [k for k in LEVELS if k < len(order)]
    for K in levels:
        pa = Analyzer(prune(d, set(order[:K])))
        m = evaluate(pa, reference, with_delta=True)
        m["keep"] = K
        m["kind"] = "frequency"
        rows.append(m)
        print(f"  頻度上位 {K:>7,}  F1 {m['f1']:.4f}  完全一致 {m['exact']:.1%}"
              f"  未知語 {m['unknown_share']:.1%}  δ=∞ {m['inf_share']:.1%}")

    controls = []
    for K in (1000, 100):
        pool = range(d.surface_count)
        pa = Analyzer(prune(d, set(rnd.sample(list(pool), K))))
        m = evaluate(pa, reference, with_delta=False)
        m["keep"] = K
        m["kind"] = "random"
        controls.append(m)
        print(f"  無作為   {K:>7,}  F1 {m['f1']:.4f}  辞書語として使われた "
              f"{m['dict_tokens']:,} / {m['tokens']:,}")

    zero = next(r for r in rows if r["keep"] == 0)

    # 画面で段階的に崩れる様子を見せる。
    # **先頭は完全辞書**にする。刈った辞書の最上位(A 群で使われた全部)を先頭に置くと、
    # 読み手はそれを完全辞書の結果だと受け取る ── 実際には「首都」のように
    # A 群に出なかった語が既に落ちている(loop_010 の目視で気づいた)
    show_levels = [None, len(order), 3000, 300, 30, 0]
    showcase = []
    for text in SHOWCASE:
        steps = []
        for K in show_levels:
            pa = a if K is None else Analyzer(prune(d, set(order[:K])))
            r = pa.analyze(text)
            if r is None:
                continue
            steps.append({
                "keep": d.surface_count if K is None else K,
                "full": K is None,
                "words": r.words,
                "unknown": [n.unknown for n in r.nodes],
                "cost": r.cost,
            })
        showcase.append({"text": text, "steps": steps})

    doc = {
        "note": "境界 F1 は完全辞書との一致度であって、正しさではない(人手の正解とは照合していない)。",
        "corpus": "aozora-sakuin/data/normalized",
        "seed": args.seed,
        "freq_sentences": len(A),
        "eval_sentences": len(reference),
        "surface_total": d.surface_count,
        "surface_used": len(order),
        "top_words": [d.surface(i).decode("utf-8", "replace") for i in order[:12]],
        "rows": rows,
        "controls": controls,
        "zero_f1": zero["f1"],
        "showcase": showcase,
        "show_levels": [d.surface_count if k is None else k for k in show_levels],
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    # ---- G-04 の判定(閾値は SPEC に測る前から書いてある)
    r1000 = next(r for r in rows if r["keep"] == 1000)
    c1000 = next(c for c in controls if c["keep"] == 1000)
    print("\n── G-04")
    print(f"  a) 無作為 1,000 と辞書ゼロの差 {abs(c1000['f1'] - zero['f1']):.4f} < 0.01 …… "
          f"{'通過' if abs(c1000['f1'] - zero['f1']) < 0.01 else '不通過'}")
    print(f"  b) 頻度上位 1,000 − 辞書ゼロ {r1000['f1'] - zero['f1']:.4f} >= 0.15 …… "
          f"{'通過' if r1000['f1'] - zero['f1'] >= 0.15 else '不通過'}")
    print(f"  c) 無作為辞書の使用トークン {c1000['dict_tokens']:,} > 0 …… "
          f"{'通過' if c1000['dict_tokens'] > 0 else '不通過'}")
    print(f"\n→ {args.out}")


if __name__ == "__main__":
    main()
