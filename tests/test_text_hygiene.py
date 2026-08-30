"""日本語本文への別字種・制御文字の混入検査。

**検査器の正本はフリートの `harness/text_hygiene.py`**(HC-072・scaffold 管理)。
このファイルは (1) その道具を実際に走らせる (2) 道具自身の自己対照が通ることを確かめる
(3) このプロジェクト固有の除外(`scripts/ruby.py` の文字クラス定義)が
緩みすぎていないことを見張る、の三つだけを持つ。

loop_005 では**同じ検査を自前で書き直していた**。フリートが配っている道具に気づかず、
走査範囲の違いから偽陽性を二度出した(数式記号の δ・Σ・α と、字種を論じる文書の引用)。
検査を書く前に、配られている道具を探すこと。
"""

import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "harness", "text_hygiene.py")

CYRILLIC = re.compile(r"[Ѐ-ӿԀ-ԯ]")  # text-hygiene:allow
ALLOW_MARKER = "text-hygiene:allow"


def run_tool(*args):
    return subprocess.run([sys.executable, TOOL, *args], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8")


@pytest.mark.validation
def test_t050_fleet_tool_finds_no_contamination():
    """T-050 —— 配られている検査器を実際に走らせ、違反 0 件であること。"""
    assert os.path.exists(TOOL), "harness/text_hygiene.py が無い(scaffold の update が要る)"
    r = run_tool()
    assert r.returncode == 0, f"混入がある:\n{r.stdout}\n{r.stderr}"
    assert "走査" in r.stdout, f"走査したことを報告していない: {r.stdout!r}"
    scanned = int(re.search(r"走査 (\d+) ファイル", r.stdout).group(1))
    assert scanned > 20, f"走査したのが {scanned} ファイルしかない ── 検査が働いていない"


@pytest.mark.validation
def test_t051_fleet_tool_self_test_passes():
    """T-051 —— 検査器自身の陽性・陰性対照が通ること。

    「違反 0 件」は「検査した」を意味しない。検査器が死んでいても同じ 0 件が出る。
    """
    r = run_tool("--self-test")
    assert r.returncode == 0, f"自己対照が落ちている:\n{r.stdout}\n{r.stderr}"
    assert "自己対照 OK" in r.stdout, r.stdout


@pytest.mark.validation
def test_t051b_ruby_source_exemptions_are_narrow():
    """T-051b —— `scripts/ruby.py` の allow 印が、必要な行にだけ付いていること。

    青空文庫にはギリシャ・キリル基底のルビが実在するので、その文字クラス定義と
    根拠のコメントには印が要る。**除外を作ったら、緩みすぎを止める仕掛けを対で置く。**
    印の付いた行が (a) 文字クラス定義 (b) その根拠のコメント のどちらでもなければ落とす。
    """
    path = os.path.join(ROOT, "scripts", "ruby.py")
    lines = open(path, encoding="utf-8").read().splitlines()
    marked = [(i, l) for i, l in enumerate(lines, 1) if ALLOW_MARKER in l]
    assert marked, "ruby.py に allow 印が無い ── 除外の前提が変わっている"
    defs, notes = [], []
    for i, line in marked:
        if "re.compile(" in line:
            defs.append(i)
        elif line.lstrip().startswith("#"):
            notes.append(i)
        else:
            pytest.fail(f"{path}:{i} の allow 印が定義でもコメントでもない: {line.strip()[:60]}")
    assert defs, "文字クラス定義に印が無い ── 除外がコメントだけを通している"
    assert notes, "根拠のコメントに印が無い ── 除外の前提が変わっている"

    # 印が本当に効いていること、かつ印の無い同じ内容は捕まること(検査器の挙動を確かめる)
    leak = chr(0x0441) + chr(0x043E) + "ba"
    assert CYRILLIC.search(leak), "陽性対照が働かない"
    assert not CYRILLIC.search("そばの北詰まで"), "正当な日本語を撃っている"
