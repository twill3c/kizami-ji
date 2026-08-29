import os, struct, array, ipadic

D = ipadic.DICDIR
MAX_GROUPING = 24

def load_dic(name):
    b = open(os.path.join(D, name), "rb").read()
    h = struct.unpack("<10I", b[:40])
    lexsize, lsize, rsize, dsize, tsize = h[3], h[4], h[5], h[6], h[7]
    o = 72
    da = b[o:o+dsize]; o += dsize
    tk = b[o:o+tsize]
    ib = array.array("i"); ib.frombytes(da)
    uc = array.array("I"); uc.frombytes(da)
    return dict(base=ib, chk=uc, n=dsize//8, tok=tk, lsize=lsize)

SYS, UNK = load_dic("sys.dic"), load_dic("unk.dic")
LSIZE = SYS["lsize"]

mb = open(os.path.join(D, "matrix.bin"), "rb").read()
ml, mr = struct.unpack("<HH", mb[:4])
MAT = array.array("h"); MAT.frombytes(mb[4:4+ml*mr*2])

cb = open(os.path.join(D, "char.bin"), "rb").read()
CSZ = struct.unpack_from("<I", cb, 0)[0]
CNAMES = [cb[4+32*i:4+32*(i+1)].split(b"\0")[0].decode() for i in range(CSZ)]
CMAP = array.array("I"); CMAP.frombytes(cb[4+32*CSZ: 4+32*CSZ+4*0xffff])
SPACE_TYPE = 1 << CNAMES.index("SPACE")

def cinfo(cp):
    v = CMAP[cp] if cp < 0xffff else CMAP[0]
    return (v & 0x3ffff, (v >> 18) & 0xff, (v >> 26) & 0xf, (v >> 30) & 1, (v >> 31) & 1)

def tokinfo(d, i):
    return struct.unpack_from("<HHHh", d["tok"], i*16)

def cps(d, key, start, limit=None):
    out, b, n, ib, uc = [], d["base"][0], d["n"], d["base"], d["chk"]
    end = len(key) if limit is None else limit
    for i in range(start, end):
        q = b + key[i] + 1
        if not (0 <= q < n) or uc[q*2+1] != b: break
        b = ib[q*2]
        if 0 <= b < n and uc[b*2+1] == b:
            v = ib[b*2]
            if v < 0: out.append((i+1-start, (-v-1) >> 8, (-v-1) & 0xff))
    return out

def exact(d, key):
    r = cps(d, key, 0)
    for ln, ti, nt in r:
        if ln == len(key): return ti, nt
    return None

UNKCAT = {i: exact(UNK, CNAMES[i].encode()) for i in range(CSZ)}

def analyze(text):
    raw = text.encode("utf8")
    N = len(raw)
    # char starts: byte index -> (codepoint, bytelen)
    ch = {}
    i = 0
    while i < N:
        c = raw[i]
        L = 1 if c < 0x80 else (2 if c < 0xE0 else (3 if c < 0xF0 else 4))
        ch[i] = (int(raw[i:i+L].decode("utf8", "replace")[0:1].encode("utf8") and ord(raw[i:i+L].decode("utf8","replace"))), L)
        i += L

    def ci(p): return cinfo(ch[p][0])
    def clen(p): return ch[p][1]

    ends = [[] for _ in range(N+1)]
    ends[0] = [(0, 0, None)]
    for pos in range(N):
        if not ends[pos] or pos not in ch: continue
        # skip SPACE-kind chars
        b2 = pos
        while b2 < N and (ci(b2)[0] & SPACE_TYPE): b2 += clen(b2)
        if b2 >= N: continue
        typ, dflt, lng, grp, inv = ci(b2)
        cand = []
        for ln, ti, nt in cps(SYS, raw, b2):
            for k in range(nt): cand.append((b2 + ln, SYS, ti + k))
        if not (cand and not inv):
            b3 = b2 + clen(b2)
            gb3 = -1
            if grp:
                e, cnt = b3, 1
                while e < N and e in ch and (ci(e)[0] & typ): e += clen(e); cnt += 1
                if cnt <= MAX_GROUPING:
                    u = UNKCAT[dflt]
                    if u:
                        for k in range(u[1]): cand.append((e, UNK, u[0] + k))
                gb3 = e
            for _ in range(lng):
                if b3 > N: break
                if b3 != gb3:
                    u = UNKCAT[dflt]
                    if u:
                        for k in range(u[1]): cand.append((b3, UNK, u[0] + k))
                if b3 >= N or b3 not in ch or not (ci(b3)[0] & typ): break
                b3 += clen(b3)
        for (e, d, ti) in cand:
            lc, rc, _p, wc = tokinfo(d, ti)
            best = None
            for (pc, prc, bk) in ends[pos]:
                c = pc + MAT[prc + LSIZE * lc] + wc
                if best is None or c < best[0]: best = (c, rc, (pos, bk, d is UNK, ti, b2, e))
            if best: ends[e].append(best)
    if not ends[N]: return None
    total, bk = min(((pc + MAT[prc], bk) for (pc, prc, bk) in ends[N]), key=lambda x: x[0])
    out = []
    while bk:
        p, prev, isunk, ti, s, e = bk
        out.append(raw[s:e].decode("utf8", "replace"))
        bk = prev
    return total, out[::-1]
