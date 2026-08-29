import sys, fugashi, ipadic
import os as _os
SP = _os.path.dirname(_os.path.abspath(__file__)).replace("\\", "/")  # MeCab はバックスラッシュをエスケープと解釈する
sys.path.insert(0, SP)
from ref import analyze

d = ipadic.DICDIR.replace("\\", "/")
tg = fugashi.GenericTagger(" ".join(["-r", SP + "/mecabrc", "-d", d, "-F%m@%pc|", "-E", "EOS@%pc|"]))

def mecab(s):
    parts = [p for p in tg.parse(s).split("|") if p]
    words = [p.split("@")[0] for p in parts[:-1]]
    return int(parts[-1].split("@")[1]), words

def run(tests, verbose=True):
    ok = unk = 0
    for s in tests:
        r = analyze(s)
        if r is None:
            unk += 1; continue
        mt, mw = mecab(s)
        vt, vw = r[0], r[1]
        same = (mt == vt and mw == vw)
        ok += same
        if verbose:
            print("OK " if same else "NG ", s)
        if not same:
            print("   mecab", mt, mw)
            print("   mine ", vt, vw)
    return ok, unk, len(tests)

if __name__ == "__main__":
    tests = ["すもももももももものうち", "くるまでまつ", "にわにはにわにわとりがいる",
             "東京都は日本の首都である", "吾輩は猫である。名前はまだ無い。",
             "親譲りの無鉄砲で小供の時から損ばかりしている。"]
    ok, unk, n = run(tests)
    print(f"agree {ok}/{n}  unk-skipped {unk}")
