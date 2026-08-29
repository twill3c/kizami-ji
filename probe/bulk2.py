import sys, os, re, random, collections
import os as _os
SP = _os.path.dirname(_os.path.abspath(__file__)).replace("\\", "/")  # MeCab はバックスラッシュをエスケープと解釈する
sys.path.insert(0, SP)
from cmp import mecab
from ref import analyze

ND = "C:/_ClaudeCode/aozora-sakuin/data/normalized"
files = sorted(os.listdir(ND))
random.seed(20260829)
picks = random.sample(files, 400)
sents = []
for f in picks:
    t = open(os.path.join(ND, f), encoding="utf8", errors="replace").read()
    for s in re.split(r"(?<=[。！？])", t):
        s = s.strip()
        if 4 <= len(s) <= 120: sents.append(s)
random.shuffle(sents)
sents = sents[:10000]

agree = 0; bad = []; none = 0
for s in sents:
    r = analyze(s)
    if r is None: none += 1; continue
    mt, mw = mecab(s)
    if mt == r[0] and mw == r[1]: agree += 1
    else: bad.append((s, mt, mw, r[0], r[1]))
n = len(sents)
print(f"sentences {n}  agree {agree}  disagree {len(bad)}  no-path {none}")
print(f"exact agreement (segmentation + total cost): {agree/n:.6%}")
for s, mt, mw, vt, vw in bad[:6]:
    print("\nNG", s[:70])
    print("  mecab", mt, "/".join(mw)[:110])
    print("  mine ", vt, "/".join(vw)[:110])
