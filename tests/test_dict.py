"""T-001〜T-004 — 出荷用に組み直した辞書が、IPADIC の原本と等価であることの検査。

期待値の出所(TEST_SPEC「オラクルの出所」):
  - lexsize / 表層数        … sys.dic ヘッダの lexsize(コーパス自身が持つ件数オラクル・HC-012)
  - 文字種定義              … IPADIC 同梱 char.def(外部権威)
  - 共通接頭辞検索の正解    … sys.dic の double-array(外部権威)
  - token の 4 値           … sys.dic の token 配列(外部権威)

件数は定数で書かない。「集合が一致する」「取りこぼしが無い」の形で書く(HC-016)。
"""

import os
import random
import struct
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import shipdict  # noqa: E402  出荷側の読み取り実装(ipadic を import しないことが要件)


# ---------------------------------------------------------------- 原本(オラクル)


@pytest.fixture(scope="session")
def origin():
    """IPADIC の原本を直接読む。出荷物と突き合わせるためだけに使う。"""
    import ipadic

    d = ipadic.DICDIR
    buf = open(os.path.join(d, "sys.dic"), "rb").read()
    h = struct.unpack("<10I", buf[:40])
    lexsize, dsize, tsize, fsize = h[3], h[6], h[7], h[8]
    o = 72
    da = buf[o : o + dsize]
    o += dsize
    tok = buf[o : o + tsize]
    o += tsize
    feat = buf[o : o + fsize]
    import array

    ib = array.array("i")
    ib.frombytes(da)
    uc = array.array("I")
    uc.frombytes(da)
    return dict(dicdir=d, lexsize=lexsize, tok=tok, feat=feat, base=ib, chk=uc, n=dsize // 8)


def da_walk(o):
    """double-array を全走査して (表層 bytes, token 開始, token 数) を返す。"""
    out = []
    stack = [(o["base"][0], b"")]
    n, ib, uc = o["n"], o["base"], o["chk"]
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


@pytest.fixture(scope="session")
def origin_surfaces(origin):
    return da_walk(origin)


@pytest.fixture(scope="session")
def ship():
    return shipdict.load(os.path.join(ROOT, "data", "dict"))


# ---------------------------------------------------------------- T-001


@pytest.mark.validation
def test_t001_token_total_matches_lexsize(origin, origin_surfaces, ship):
    """復元したトークン総数が sys.dic ヘッダの lexsize と一致する。

    取りこぼしがあれば総数が合わない ── これが件数オラクルとして働く。
    定数ではなくヘッダの値と突き合わせる。
    """
    assert sum(n for _, _, n in origin_surfaces) == origin["lexsize"]
    assert ship.token_count == origin["lexsize"]


@pytest.mark.validation
def test_t001b_surface_sets_are_identical(origin_surfaces, ship):
    """出荷索引の表層集合が原本の表層集合と完全に一致する(件数ではなく集合で見る)。"""
    a = {s for s, _, _ in origin_surfaces}
    b = set(ship.all_surfaces())
    assert a == b, f"差分 原本のみ={len(a - b)} 出荷のみ={len(b - a)}"


# ---------------------------------------------------------------- T-002


@pytest.mark.validation
def test_t002_char_categories_match_char_def(origin, ship):
    """char.bin から復元した文字種定義が IPADIC 同梱 char.def と一致する。

    char.def は外部権威。`#` 以降を落とし、カテゴリ定義行だけを比較する。
    """
    path = os.path.join(origin["dicdir"], "char.def")
    if not os.path.exists(path):
        pytest.skip("char.def が dicdir に無い(pip 版はコンパイル済みのみ)")
    want = {}
    for line in open(path, encoding="euc-jp", errors="replace"):
        line = line.split("#")[0].strip()
        if not line or line.startswith("0x"):
            continue
        f = line.split()
        if len(f) == 4 and f[0].isupper():
            want[f[0]] = (int(f[1]), int(f[2]), int(f[3]))
    assert want, "char.def からカテゴリ定義を 1 件も読めていない(検査が働いていない)"
    got = {name: ship.category_rule(name) for name in want}
    assert got == want


@pytest.mark.validation
def test_t002b_known_category_rules(ship):
    """char.def が同梱されない環境でも効く固定検査。

    期待値の出所: IPADIC 2.7.0-20070801 の char.def(実測 2026-08-29・docs/probe-000.md)。
    """
    assert ship.category_rule("KATAKANA") == (1, 1, 2)
    assert ship.category_rule("HIRAGANA") == (0, 1, 2)
    assert ship.category_rule("KANJI") == (0, 0, 2)
    assert ship.category_rule("SPACE") == (0, 1, 0)


@pytest.mark.validation
def test_t002c_codepoint_categories_match_origin(ship):
    """符号位置ごとの文字種が原本の char.bin と一致する(BMP 全域)。"""
    import ipadic

    cb = open(os.path.join(ipadic.DICDIR, "char.bin"), "rb").read()
    csize = struct.unpack_from("<I", cb, 0)[0]
    import array

    m = array.array("I")
    m.frombytes(cb[4 + 32 * csize : 4 + 32 * csize + 4 * 0xFFFF])
    mism = [cp for cp in range(0xFFFF) if ship.char_info_raw(cp) != m[cp]]
    assert mism == [], f"不一致 {len(mism)} 件(先頭 {mism[:5]})"


# ---------------------------------------------------------------- T-003


@pytest.mark.validation
def test_t003_common_prefix_search_matches_double_array(origin, origin_surfaces):
    """自前索引の共通接頭辞検索が、double-array の検索結果と集合として一致する。

    走査対象は原本の表層からランダムに作った文字列。乱数種を固定する。
    """
    ship_dict = shipdict.load(os.path.join(ROOT, "data", "dict"))
    surfaces = sorted(s for s, _, _ in origin_surfaces)
    rnd = random.Random(20260830)
    samples = []
    for _ in range(400):
        # 表層を 2〜4 個つないだ文字列 ── 途中で切れる候補が多く出る
        s = b"".join(rnd.choice(surfaces) for _ in range(rnd.randint(2, 4)))
        samples.append(s)
    assert samples, "走査対象が空(検査が働いていない)"

    def da_cps(key, start):
        out = []
        b = origin["base"][0]
        n, ib, uc = origin["n"], origin["base"], origin["chk"]
        for i in range(start, len(key)):
            q = b + key[i] + 1
            if not (0 <= q < n) or uc[q * 2 + 1] != b:
                break
            b = ib[q * 2]
            if 0 <= b < n and uc[b * 2 + 1] == b and ib[b * 2] < 0:
                out.append(i + 1 - start)
        return out

    checked = 0
    for s in samples:
        for p in range(len(s)):
            if (s[p] & 0xC0) == 0x80:
                continue
            want = sorted(da_cps(s, p))
            got = sorted(ln for ln, _, _ in ship_dict.common_prefix(s, p))
            assert got == want, f"位置 {p} で不一致: got={got} want={want}"
            checked += 1
    assert checked > 1000, f"検査した位置が少なすぎる({checked})"


# ---------------------------------------------------------------- T-004


@pytest.mark.validation
def test_t004_token_fields_match_origin(origin, origin_surfaces, ship):
    """組み直した token 表の (lcAttr, rcAttr, wcost, 品詞四つ組) が原本と全件一致する。"""
    tok = origin["tok"]
    feat = origin["feat"]

    def origin_token(i):
        lc, rc, pos, wc, foff = struct.unpack_from("<HHHhI", tok, i * 16)
        f = feat[foff : feat.index(b"\0", foff)].decode("utf8").split(",")
        return lc, rc, wc, tuple(f[:4]), (f[4], f[5])

    mism = 0
    for surf, ti, nt in origin_surfaces:
        got = ship.tokens_for(surf)
        assert len(got) == nt, f"{surf!r}: token 数 {len(got)} != {nt}"
        for k in range(nt):
            o_lc, o_rc, o_wc, o_pos, o_cf = origin_token(ti + k)
            g = got[k]
            if (g.lc, g.rc, g.cost, g.pos, g.conj) != (o_lc, o_rc, o_wc, o_pos, o_cf):
                mism += 1
    assert mism == 0, f"{mism} 件のトークンが原本と食い違う"


# ---------------------------------------------------------------- 陰性対照


@pytest.mark.validation
def test_controls_detect_a_broken_index(ship):
    """検査器そのものが働くことの陽性対照。

    索引を壊した写しを作り、共通接頭辞検索が「壊れた」と分かることを確かめる。
    壊し方は符号位置から組み立て、原稿に正解を直接書かない。
    """
    key = "東京都".encode("utf8")
    ok = ship.common_prefix(key, 0)
    assert ok, "正当な入力で候補が 0 件 ── 検査対象が動いていない"
    broken = ship.with_corrupted_surfaces()
    assert broken.common_prefix(key, 0) != ok, "索引を壊しても同じ結果 ── 検査が働いていない"
