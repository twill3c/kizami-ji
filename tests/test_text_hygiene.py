"""T-050 / T-051 — 日本語本文へのキリル文字混入検査(フリート共通)。

字形が似ていて目視では気づけない(`с` と `с`)。senoto-mori の text-hygiene 準拠。

**走査範囲は「本文」に限る。** ソースの文字クラス定義まで撃つと、
青空文庫にギリシャ・キリル基底のルビが実在する(`γ《ガムマア》` `Л《エル》`)ぶんを
表現できなくなる。最初にアドホックで走らせたときはここで誤検出した(HC-002)。
"""

import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CYRILLIC = re.compile(r"[Ѐ-ӿ]")
GREEK = re.compile(r"[Ͱ-Ͽ]")
#: 数式・統計の記号として意図的に使うギリシャ文字。これ以外は混入とみなす
ALLOWED_GREEK = set("δΣαμσλβγΔρ")

#: 本文が入る場所。scripts/ は本文ではないので入れない(文字クラス定義がある)
PROSE_GLOBS = ("*.md", "docs/*.md", "src/**/*.ts", "src/**/*.tsx",
               "app/**/*.tsx", "content/**/*.md", "content/**/*.mdx")


def prose_files():
    import glob
    out = []
    for pat in PROSE_GLOBS:
        out += glob.glob(os.path.join(ROOT, pat), recursive=True)
    return sorted(set(out))


def prose_only(text: str, path: str) -> str:
    """引用・コード片を落として、**地の文**だけにする。

    キリル・ギリシャを**論じている文**は、その文字を引用せざるを得ない ——
    TEST_SPEC は `Л《エル》` を例として挙げているし、docs も同じ。
    それを混入と数えると、この検査は「混入について書けない」検査になる。
    落とすのは引用の印がある部分だけ(コード柵・バッククォート・ソースのコメント)で、
    地の文に裸で現れるキリルは今までどおり撃つ。
    """
    if path.endswith((".ts", ".tsx")):
        text = re.sub(r"/\*[\s\S]*?\*/", " ", text)
        text = re.sub(r"(^|[^:])//[^\n]*", r"\1 ", text, flags=re.M)
        return text
    text = re.sub(r"```[\s\S]*?```", " ", text)      # コード柵
    text = re.sub(r"`[^`\n]*`", " ", text)            # バッククォート
    return text


@pytest.mark.validation
def test_t050_no_cyrillic_in_prose():
    files = prose_files()
    assert len(files) > 5, f"走査対象が {len(files)} 件しか無い ── 検査が働いていない"
    hits = []
    for p in files:
        body = prose_only(open(p, encoding="utf-8").read(), p)
        for i, line in enumerate(body.splitlines(), 1):
            if CYRILLIC.search(line):
                hits.append((os.path.relpath(p, ROOT), i, line.strip()[:50]))
    assert hits == [], f"キリル文字の混入 {len(hits)} 件: {hits[:3]}"


@pytest.mark.validation
def test_t050b_no_unexpected_greek_in_prose():
    hits = []
    for p in prose_files():
        body = prose_only(open(p, encoding="utf-8").read(), p)
        for i, line in enumerate(body.splitlines(), 1):
            for m in GREEK.finditer(line):
                if m.group() not in ALLOWED_GREEK:
                    hits.append((os.path.relpath(p, ROOT), i, m.group()))
    assert hits == [], f"許可していないギリシャ文字 {len(hits)} 件: {hits[:5]}"


@pytest.mark.validation
def test_t051_positive_and_negative_controls():
    """検査器そのものの対照。混入例は**符号位置から組み立てる**(原稿に書くと自分を撃つ)。"""
    leak = "с" + "о" + "ba"          # キリルの с о + ラテン
    assert CYRILLIC.search(leak), "陽性対照を捕まえられない"
    assert not CYRILLIC.search("そばの北詰まで"), "正当な日本語を撃っている"
    omega = "ω"
    assert GREEK.search(omega) and omega not in ALLOWED_GREEK, "許可外ギリシャの陽性対照が働かない"
    assert all(g in ALLOWED_GREEK for g in "δΣαρ"), "許可リストが機能していない"

    # 引用の落とし方が緩すぎないこと ── 地の文に裸で現れたキリルは残る
    md_bare = "そば" + leak + "の話"
    assert CYRILLIC.search(prose_only(md_bare, "x.md")), "地の文のキリルまで落としている"
    # 引用の中は落ちること
    md_quoted = "例として `" + leak + "` を挙げる"
    assert not CYRILLIC.search(prose_only(md_quoted, "x.md")), "引用が落ちていない"
    ts_comment = "// 例として " + leak + " を挙げる\nexport const a = 1;"
    assert not CYRILLIC.search(prose_only(ts_comment, "x.ts")), "コメントが落ちていない"


@pytest.mark.validation
def test_greek_and_cyrillic_in_ruby_source_are_class_definitions():
    """`scripts/ruby.py` のギリシャ・キリルは**文字クラス定義**であって混入ではない。

    除外を作ったら、除外した対象が実在し、かつ想定した形をしていることを確かめる
    (緩める側だけを用意すると検査は静かに骨抜きになる)。
    """
    path = os.path.join(ROOT, "scripts", "ruby.py")
    lines = open(path, encoding="utf-8").read().splitlines()
    found = [(i, l) for i, l in enumerate(lines, 1)
             if CYRILLIC.search(l) or any(m.group() not in ALLOWED_GREEK
                                          for m in GREEK.finditer(l))]
    assert found, "ruby.py にギリシャ・キリルが無い ── 除外の前提が崩れている"
    # 正当な現れ方は二つだけ:
    #   (a) 文字クラスの定義そのもの
    #   (b) その定義の根拠として実例を書いたコメント(γ《ガムマア》 Л《エル》)
    defs = [(i, l) for i, l in found if "re.compile(" in l]
    notes = [(i, l) for i, l in found if l.lstrip().startswith("#")]
    for i, line in found:
        ok = "re.compile(" in line or line.lstrip().startswith("#")
        assert ok, f"{path}:{i} が文字クラス定義でもコメントでもない: {line.strip()[:60]}"
    # 除外が「コメントなら何でも通る」に崩れていないこと ── 定義側も実在すること
    assert defs, "文字クラス定義が見つからない ── 除外がコメントだけを通している"
    assert notes, "根拠のコメントが見つからない ── 除外の前提が変わっている"
