"""T-014b — δ の二実装照合フィクスチャ。Python 側の δ_local を書き出す。

解の出所は Python 実装(MeCab と分割・総コストが完全一致することを T-010/T-011 で確認済み)。
TypeScript 実装はこれと δ まで完全一致しなければならない(SPEC T-014)。
"""
from __future__ import annotations
import argparse, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import check_agreement as ca  # noqa: E402
from analyze import INF, Analyzer, delta_local  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=800)
ap.add_argument("--seed", type=int, default=20260902)
ap.add_argument("--out", default=os.path.join(ROOT, "tests", "fixtures", "delta.json"))
args = ap.parse_args()

a = Analyzer.load(os.path.join(ROOT, "data", "dict"))
cases = []
for s in ca.sample_sentences(args.n, seed=args.seed, lo=4, hi=60):
    r, ds = delta_local(a, s)
    if r is None:
        raise SystemExit(f"経路が見つからない文がある: {s}")
    cases.append({
        "text": s,
        "cost": r.cost,
        "words": r.words,
        "emission": sum(x.cost for x in r.nodes),
        "connection": sum(x.conn for x in r.nodes),
        # δ は境界のバイト位置順。∞ は null で書く
        "deltas": [None if ds[x.end] == INF else ds[x.end] for x in r.nodes[:-1]],
    })
os.makedirs(os.path.dirname(args.out), exist_ok=True)
with open(args.out, "w", encoding="utf-8", newline="\n") as f:
    json.dump({"note": "解の出所は Python 実装(MeCab と一致済み)。TS はこれと δ まで一致すること",
               "seed": args.seed, "count": len(cases), "cases": cases}, f, ensure_ascii=False)
print(f"{len(cases)} 文 → {args.out} ({os.path.getsize(args.out)/1048576:.2f} MB)")
