"""IPADIC を出荷用の形式へ組み直す。

読む   : ipadic の dicdir(sys.dic / matrix.bin / char.bin / unk.dic)
書く   : data/dict/ 以下(shipdict.py が読む形式)

捨てるもの: double-array(索引)と feature 文字列のうち読み・発音・原形。
残すもの  : 表層・生起コスト・左右文脈 ID・品詞四つ組・活用型/活用形・連接表・文字種・未知語。

    python scripts/build_dict.py [--out data/dict]
"""

from __future__ import annotations

import argparse
import array
import json
import os
import struct
import sys

FORMAT = 1


def read_dic(path):
    buf = open(path, "rb").read()
    h = struct.unpack("<10I", buf[:40])
    lexsize, lsize, rsize, dsize, tsize, fsize = h[3], h[4], h[5], h[6], h[7], h[8]
    o = 72
    da = buf[o : o + dsize]
    o += dsize
    tok = buf[o : o + tsize]
    o += tsize
    feat = buf[o : o + fsize]
    ib = array.array("i")
    ib.frombytes(da)
    uc = array.array("I")
    uc.frombytes(da)
    return dict(lexsize=lexsize, lsize=lsize, rsize=rsize, tok=tok, feat=feat,
                base=ib, chk=uc, n=dsize // 8)


def feature(d, i):
    off = struct.unpack_from("<HHHhI", d["tok"], i * 16)[4]
    return d["feat"][off : d["feat"].index(b"\0", off)].decode("utf-8").split(",")


def token_fields(d, i):
    lc, rc, pos, wc = struct.unpack_from("<HHHh", d["tok"], i * 16)
    return lc, rc, wc


def walk(d):
    """double-array を全走査して (表層 bytes, token 開始, token 数) を集める。

    darts の check は「親の添字」ではなく「親の base 値」を持つ。ここを取り違えると空を返す。
    """
    out = []
    stack = [(d["base"][0], b"")]
    n, ib, uc = d["n"], d["base"], d["chk"]
    while stack:
        b, pre = stack.pop()
        if 0 <= b < n and uc[b * 2 + 1] == b:
            v = ib[b * 2]
            if v < 0:
                v = -v - 1
                out.append((pre, v >> 8, v & 0xFF))
        for c in range(256):
            q = b + c + 1
            if 0 <= q < n and uc[q * 2 + 1] == b:
                stack.append((ib[q * 2], pre + bytes([c])))
    return out


def exact(d, entries, key: bytes):
    for surf, ti, nt in entries:
        if surf == key:
            return ti, nt
    return None


def write_array(path, typecode, values):
    a = array.array(typecode, values)
    if sys.byteorder != "little":
        a.byteswap()
    with open(path, "wb") as f:
        a.tofile(f)
    return os.path.getsize(path)


def main():
    import ipadic

    ap = argparse.ArgumentParser()
    ap.add_argument("--dicdir", default=ipadic.DICDIR)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "data", "dict"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    sysd = read_dic(os.path.join(args.dicdir, "sys.dic"))
    unkd = read_dic(os.path.join(args.dicdir, "unk.dic"))

    print("走査中 …")
    entries = walk(sysd)
    total = sum(n for _, _, n in entries)
    if total != sysd["lexsize"]:
        raise SystemExit(f"件数オラクル不一致: 復元 {total} != lexsize {sysd['lexsize']}")
    print(f"  表層 {len(entries):,} 種 / トークン {total:,}(lexsize と一致)")

    # ---- 品詞・活用の表を作る(posid が四つ組を一意に決めることを検算する)
    pos_of = {}
    for i in range(sysd["lexsize"]):
        _, _, pid, _ = struct.unpack_from("<HHHh", sysd["tok"], i * 16)
        q = tuple(feature(sysd, i)[:4])
        if pos_of.setdefault(pid, q) != q:
            raise SystemExit(f"posid {pid} が品詞四つ組を一意に決めていない")
    pos_table = [pos_of[k] for k in sorted(pos_of)]
    pos_index = {q: n for n, q in enumerate(pos_table)}

    conj_index = {}
    conj_table = []

    def conj_id(pair):
        if pair not in conj_index:
            conj_index[pair] = len(conj_table)
            conj_table.append(pair)
        return conj_index[pair]

    # ---- 表層を整列して列指向に書き出す
    entries.sort(key=lambda e: e[0])
    surf_blob = bytearray()
    surf_idx = [0]
    tok_start, tok_count = [], []
    lc_a, rc_a, cost_a, pos_a, cf_a = [], [], [], [], []
    for surf, ti, nt in entries:
        surf_blob += surf
        surf_idx.append(len(surf_blob))
        tok_start.append(len(lc_a))
        tok_count.append(nt)
        for k in range(nt):
            lc, rc, wc = token_fields(sysd, ti + k)
            f = feature(sysd, ti + k)
            lc_a.append(lc)
            rc_a.append(rc)
            cost_a.append(wc)
            pos_a.append(pos_index[tuple(f[:4])])
            cf_a.append(conj_id((f[4], f[5])))

    # ---- 文字種(char.bin)を連長圧縮する
    cb = open(os.path.join(args.dicdir, "char.bin"), "rb").read()
    csize = struct.unpack_from("<I", cb, 0)[0]
    cnames = [cb[4 + 32 * i : 4 + 32 * (i + 1)].split(b"\0")[0].decode() for i in range(csize)]
    cmap = array.array("I")
    cmap.frombytes(cb[4 + 32 * csize : 4 + 32 * csize + 4 * 0xFFFF])
    starts, infos = [], []
    for cp in range(0xFFFF):
        if not infos or cmap[cp] != infos[-1]:
            starts.append(cp)
            infos.append(cmap[cp])

    def rule(name):
        """char.def と同じ (invoke, group, length) を復元する。

        length/group/invoke は「既定カテゴリの定義」が符号位置ごとに写されている。
        KANJINUMERIC のように type ビットを複数持つ文字があるので、
        既定カテゴリが一致する符号位置を探す(type ビットの一致は要求しない)。
        規則が符号位置ごとにばらけていないことも同時に確かめる。
        """
        k = cnames.index(name)
        seen = set()
        for cp in range(0xFFFF):
            v = cmap[cp]
            if ((v >> 18) & 0xFF) == k:
                seen.add(((v >> 31) & 1, (v >> 30) & 1, (v >> 26) & 0xF))
        if not seen:
            raise SystemExit(f"カテゴリ {name} を既定に持つ符号位置が見つからない")
        if len(seen) > 1:
            raise SystemExit(f"カテゴリ {name} の規則が符号位置ごとに違う: {seen}")
        return seen.pop()

    # ---- 未知語(unk.dic はカテゴリ名を表層に持つ辞書)
    unk_entries = walk(unkd)
    unk = {}
    for name in cnames:
        hit = exact(unkd, unk_entries, name.encode())
        if hit is None:
            unk[name] = []
            continue
        ti, nt = hit
        rows = []
        for k in range(nt):
            lc, rc, wc = token_fields(unkd, ti + k)
            f = feature(unkd, ti + k)
            rows.append([lc, rc, wc, pos_index[tuple(f[:4])], conj_id((f[4], f[5]))])
        unk[name] = rows

    # ---- 連接表
    mb = open(os.path.join(args.dicdir, "matrix.bin"), "rb").read()
    ml, mr = struct.unpack("<HH", mb[:4])
    if (ml, mr) != (sysd["lsize"], sysd["rsize"]):
        raise SystemExit("matrix.bin の次元が sys.dic のヘッダと合わない")
    matrix = array.array("h")
    matrix.frombytes(mb[4 : 4 + ml * mr * 2])

    # ---- 書き出し
    j = lambda n: os.path.join(args.out, n)  # noqa: E731
    sizes = {}
    with open(j("surf.bin"), "wb") as f:
        f.write(surf_blob)
    sizes["surf.bin"] = os.path.getsize(j("surf.bin"))
    sizes["surf_idx.bin"] = write_array(j("surf_idx.bin"), "I", surf_idx)
    sizes["tok_start.bin"] = write_array(j("tok_start.bin"), "I", tok_start)
    sizes["tok_count.bin"] = write_array(j("tok_count.bin"), "B", tok_count)
    sizes["tok_lc.bin"] = write_array(j("tok_lc.bin"), "H", lc_a)
    sizes["tok_rc.bin"] = write_array(j("tok_rc.bin"), "H", rc_a)
    sizes["tok_cost.bin"] = write_array(j("tok_cost.bin"), "h", cost_a)
    sizes["tok_pos.bin"] = write_array(j("tok_pos.bin"), "B", pos_a)
    sizes["tok_cf.bin"] = write_array(j("tok_cf.bin"), "H", cf_a)
    sizes["matrix.bin"] = write_array(j("matrix.bin"), "h", matrix)
    sizes["chars.bin"] = write_array(j("chars.bin"), "I", starts + infos)

    meta = {
        "format": FORMAT,
        "dict": "mecab-ipadic-2.7.0-20070801",
        "surface_count": len(entries),
        "token_count": len(lc_a),
        "lsize": ml,
        "rsize": mr,
        "pos": [list(x) for x in pos_table],
        "conj": [list(x) for x in conj_table],
        "categories": cnames,
        "category_rules": {n: list(rule(n)) for n in cnames},
        "unk": unk,
        "char_runs": len(starts),
    }
    with open(j("meta.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    sizes["meta.json"] = os.path.getsize(j("meta.json"))

    print("\n書き出し:")
    for k, v in sorted(sizes.items(), key=lambda kv: -kv[1]):
        print(f"  {v/1048576:8.2f} MB  {k}")
    print(f"  {sum(sizes.values())/1048576:8.2f} MB  合計(無圧縮)")


if __name__ == "__main__":
    main()
