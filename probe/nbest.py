import sys
import os as _os
SP = _os.path.dirname(_os.path.abspath(__file__)).replace("\\", "/")  # MeCab はバックスラッシュをエスケープと解釈する
sys.path.insert(0, SP)
import ref
from ref import SYS, UNK, MAT, LSIZE, cps, tokinfo

def edges(text):
    raw = text.encode("utf8"); N = len(raw)
    E = {}
    for i in range(N):
        try: raw[i:i+1].decode("utf8")
        except Exception: pass
        if (raw[i] & 0xC0) == 0x80: continue
        lst = []
        for ln, ti, nt in cps(SYS, raw, i):
            for k in range(nt):
                lc, rc, pos, wc = tokinfo(SYS, ti + k)
                lst.append((i + ln, raw[i:i+ln].decode("utf8"), lc, rc, wc))
        E[i] = lst
    return raw, N, E

def allpaths(text):
    raw, N, E = edges(text)
    out = []
    def go(pos, prc, cost, path):
        if pos == N:
            out.append((cost + MAT[prc + LSIZE*0], list(path))); return
        for (e, s, lc, rc, wc) in E.get(pos, []):
            c = MAT[prc + LSIZE*lc]
            path.append((s, wc, c)); go(e, rc, cost + c + wc, path); path.pop()
    go(0, 0, 0, [])
    out.sort(key=lambda x: x[0])
    return out

for t in ["北詰まで", "の北詰まで", "どうか", "通りかかった"]:
    ps = allpaths(t)
    print("=== ", t, " paths:", len(ps))
    for tot, path in ps[:3]:
        print(f"  {tot:7d}  " + "  ".join(f"{s}(生{w:+d}/連{c:+d})" for s, w, c in path))
