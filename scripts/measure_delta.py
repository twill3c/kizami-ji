"""コーパス全体の δ 分布と、完全同点の実例を集める(SPEC F-07)。

出力は `src/data/delta-stats.json`。**閲覧時に辞書を読まずに済むよう、ここで測って焼く。**

δ は「解析器が迷った量」であって、正しさとは結びついていない(SPEC F-32b・G-01 不通過)。
このスクリプトも画面も、δ をそう呼ばない。

    python scripts/measure_delta.py --n 20000 --out src/data/delta-stats.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import check_agreement as ca  # noqa: E402
from analyze import INF, Analyzer, delta_detail  # noqa: E402

#: δ の帯。上限は「その値未満」。最後の ∞ は跨ぐ語が辞書に無い境界
BUCKETS = [
    ("0", 1),
    ("1〜99", 100),
    ("100〜999", 1000),
    ("1,000〜4,999", 5000),
    ("5,000〜19,999", 20000),
    ("20,000 以上", float("inf")),
]


def bucket_of(d: float) -> str:
    for name, hi in BUCKETS:
        if d < hi:
            return name
    return BUCKETS[-1][0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=20260903)
    ap.add_argument("--examples", type=int, default=60)
    ap.add_argument("--out", default=os.path.join(ROOT, "src", "data", "delta-stats.json"))
    args = ap.parse_args()

    a = Analyzer.load(os.path.join(ROOT, "data", "dict"))
    sents = ca.sample_sentences(args.n, seed=args.seed, lo=6, hi=80)
    if len(sents) < args.n:
        raise SystemExit(f"標本が揃わない({len(sents)}/{args.n})")

    hist = Counter()
    total = 0
    inf_n = 0
    zero_n = 0
    sent_with_tie = 0
    ties = {}
    for s in sents:
        try:
            r, d, spans = delta_detail(a, s)
        except AssertionError:
            continue
        if r is None:
            continue
        has_tie = False
        for i, nd in enumerate(r.nodes[:-1]):
            v = d[nd.end]
            total += 1
            if v == INF:
                inf_n += 1
                hist["∞"] += 1
                continue
            hist[bucket_of(v)] += 1
            if v == 0:
                zero_n += 1
                has_tie = True
                left = r.nodes[i].surface
                right = r.nodes[i + 1].surface
                joined = spans.get(nd.end, "")
                key = (left, right, joined)
                if key not in ties and len(ties) < args.examples * 4:
                    ties[key] = {
                        "left": left,
                        "right": right,
                        "joined": joined,
                        "text": s,
                        "cost": r.cost,
                        "words": r.words,
                    }
        if has_tie:
            sent_with_tie += 1

    # 実例は「切った側」と「繋げた側」が両方 2 文字以上のものを優先する(見て分かるため)
    picked = sorted(
        ties.values(),
        key=lambda t: (-(len(t["joined"]) >= 2), len(t["text"])),
    )[: args.examples]

    doc = {
        "note": "δ は解析器が迷った量であり、正しさとは結びついていない(SPEC F-32b)。",
        "corpus": "aozora-sakuin/data/normalized",
        "seed": args.seed,
        "sentences": len(sents),
        "boundaries": total,
        "infinite": inf_n,
        "zero": zero_n,
        "sentences_with_tie": sent_with_tie,
        "histogram": [{"label": k, "count": hist[k]} for k, _ in BUCKETS] + [
            {"label": "∞", "count": hist["∞"]}
        ],
        "ties": picked,
        "tie_kinds": len(ties),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    print(f"文 {len(sents):,} / 境界 {total:,}")
    print(f"  δ = ∞  {inf_n:,}({inf_n / total:.1%})")
    print(f"  δ = 0  {zero_n:,}({zero_n / total:.2%})  同点を含む文 {sent_with_tie:,}"
          f"({sent_with_tie / len(sents):.1%})")
    for k, _ in BUCKETS:
        print(f"  {k:14s} {hist[k]:>8,}")
    print(f"→ {args.out}")


if __name__ == "__main__":
    main()
