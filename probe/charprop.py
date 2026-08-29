import os, struct, array, ipadic

D = ipadic.DICDIR
cb = open(os.path.join(D, "char.bin"), "rb").read()
csize = struct.unpack_from("<I", cb, 0)[0]
names = [cb[4 + 32*i: 4 + 32*(i+1)].split(b"\0")[0].decode() for i in range(csize)]
moff = 4 + 32*csize
cmap = array.array("I"); cmap.frombytes(cb[moff: moff + 4*0xffff])

def info(cp):
    v = cmap[cp] if cp < 0xffff else cmap[0]
    return dict(type=v & 0x3ffff, default=(v >> 18) & 0xff,
                length=(v >> 26) & 0xf, group=(v >> 30) & 1, invoke=(v >> 31) & 1)

if __name__ == "__main__":
    print(csize, names)
    for ch in "あアー漢A1 、":
        i = info(ord(ch))
        cats = [names[k] for k in range(csize) if i["type"] >> k & 1]
        print(repr(ch), cats, "default=", names[i["default"]],
              "len=", i["length"], "group=", i["group"], "invoke=", i["invoke"])
