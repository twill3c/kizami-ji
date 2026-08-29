"""二実装照合(T-014)のフィクスチャを作る。

出力する解は **MeCab(外部権威)のもの**。Python 実装と一致することを生成時に検算し、
一致しない文はフィクスチャに入れない ── ではなく、**そこで落とす**。
片方に都合の悪い文を黙って捨てると、フィクスチャが自分の合格条件を選んだことになる。

    python scripts/make_fixture.py --n 2000 --out tests/fixtures/agreement.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import check_agreement as ca  # noqa: E402
from analyze import Analyzer  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--out", default=os.path.join(ROOT, "tests", "fixtures", "agreement.json"))
    args = ap.parse_args()

    a = Analyzer.load(os.path.join(ROOT, "data", "dict"))
    tagger = ca.make_tagger()
    sents = ca.sample_sentences(args.n, seed=args.seed)
    if len(sents) < args.n:
        raise SystemExit(f"標本が揃わない({len(sents)}/{args.n})")

    cases = []
    for s in sents:
        mt, mw = ca.mecab_parse(tagger, s)
        r = a.analyze(s)
        if r is None or r.cost != mt or r.words != mw:
            raise SystemExit(
                f"Python 実装が MeCab と食い違う文がある。フィクスチャを作る前に直すこと:\n"
                f"  {s}\n  mecab {mt} {mw}\n  ship  {None if r is None else r.cost} "
                f"{None if r is None else r.words}")
        cases.append({
            "text": s,
            "cost": mt,
            "words": mw,
            "unknown": [n.unknown for n in r.nodes],
            "pos": [n.pos[0] for n in r.nodes],
        })

    doc = {
        "note": "解の出所は MeCab(fugashi + mecab-ipadic-2.7.0-20070801)。生成時に Python 実装と "
                "全件一致することを確認済み。TypeScript 実装はこれと完全一致しなければならない(T-014)。",
        "corpus": "aozora-sakuin/data/normalized",
        "seed": args.seed,
        "count": len(cases),
        "cases": cases,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False)
    print(f"{len(cases)} 文 → {args.out}  ({os.path.getsize(args.out)/1048576:.2f} MB)")


if __name__ == "__main__":
    main()
