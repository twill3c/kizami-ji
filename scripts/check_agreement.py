"""O-1a / O-1b — 出荷用辞書だけで動く解析器を MeCab と突き合わせる。

MeCab(fugashi + ipadic)は**外部権威**であり、出荷実装はこれを一切参照しない(O-2)。
本スクリプトは検査専用で、出荷物には含まれない。

    python scripts/check_agreement.py --n 10000
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from analyze import Analyzer  # noqa: E402

CORPUS = os.path.join(ROOT, "..", "aozora-sakuin", "data", "normalized")


def make_tagger():
    import fugashi
    import ipadic

    # MeCab はバックスラッシュをエスケープとして食う。dicdir は必ず / に直す(HC-038 と同型)
    d = ipadic.DICDIR.replace("\\", "/")
    rc = os.path.join(ROOT, "probe", "mecabrc").replace("\\", "/")
    return fugashi.GenericTagger(" ".join(["-r", rc, "-d", d, "-F%m@%pc|", "-E", "EOS@%pc|"]))


def mecab_parse(tagger, s):
    parts = [p for p in tagger.parse(s).split("|") if p]
    return int(parts[-1].split("@")[1]), [p.split("@")[0] for p in parts[:-1]]


def sample_sentences(n, seed=20260829, works=400, lo=4, hi=120):
    files = sorted(os.listdir(CORPUS))
    rnd = random.Random(seed)
    picks = rnd.sample(files, works)
    sents = []
    for f in picks:
        t = open(os.path.join(CORPUS, f), encoding="utf-8", errors="replace").read()
        for s in re.split(r"(?<=[。！？])", t):
            s = s.strip()
            if lo <= len(s) <= hi:
                sents.append(s)
    rnd.shuffle(sents)
    return sents[:n]


def run(n, seed=20260829, verbose=False):
    a = Analyzer.load(os.path.join(ROOT, "data", "dict"))
    tagger = make_tagger()
    sents = sample_sentences(n, seed)
    cost_mismatch, seg_mismatch, ties, no_path = [], [], [], []
    for s in sents:
        r = a.analyze(s)
        if r is None:
            no_path.append(s)
            continue
        mt, mw = mecab_parse(tagger, s)
        if mt != r.cost:
            cost_mismatch.append((s, mt, r.cost))
        if mw != r.words:
            seg_mismatch.append((s, mt, mw, r.cost, r.words))
            if mt == r.cost:
                ties.append(s)
    out = dict(
        sentences=len(sents),
        cost_mismatch=len(cost_mismatch),
        seg_mismatch=len(seg_mismatch),
        exact_ties=len(ties),
        no_path=len(no_path),
    )
    if verbose:
        for s, mt, mw, vt, vw in seg_mismatch[:8]:
            print("\nNG", s[:70])
            print("  mecab", mt, "/".join(mw)[:110])
            print("  ship ", vt, "/".join(vw)[:110])
    return out, dict(cost=cost_mismatch, seg=seg_mismatch, ties=ties, no_path=no_path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260829)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    summary, detail = run(args.n, args.seed, verbose=True)
    print("\n" + json.dumps(summary, ensure_ascii=False))
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"summary": summary, "ties": detail["ties"]}, f, ensure_ascii=False, indent=1)
