"""G-01 — δ を外部の物差し(青空文庫のルビ)で採点する。

**閾値は SPEC §4 に測る前から書いてある。ここでは動かさない。**
  下位四分位と上位四分位で違反率の比が 1.5 倍以上、かつ Spearman が負で α = 0.05 で有意。
  対照は δ シャッフル(seed 20260830・2,000 回)の帰無分布。

母集団 : 最小経路が引いた内部境界すべて(ルビを含む文の中)
ラベル : その境界が 2 文字以上のルビの括りの内部に落ちているか(= 境界違反)
予測子 : δ_local(その境界)

**括りの取り方を loop_004 の途中で替えた。** 当初は基底の自動推定(直前の同一文字クラス連続)を
使っていたが、これは青空文庫の記法上の既定であって人間の区切りではない ——
実例で「処躊躇」「多年斯」「至大艱難」のような非語が基底として取れる。
以後は **｜ で明示的に括られた基底だけ**を人間の区切りとみなす(--spans bar)。
比較のため自動推定版も走らせられるようにしてある(--spans auto)。どちらの結果も残す。

    python scripts/measure_g01.py --works 600 --out data/g01.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from analyze import INF, Analyzer, delta_local  # noqa: E402
from ruby import extract, residual_violations  # noqa: E402

RAW = os.path.join(ROOT, "..", "aozora-sakuin", "data", "raw")
KANJI = re.compile(r"[一-鿿々〆ヶヵ〓]")


def sentences_with_spans(body: str, spans, lo=6, hi=100):
    """本文を文に切り、各文に含まれるルビの括りを文内座標へ写す。"""
    out = []
    pos = 0
    for piece in re.split(r"(?<=[。！？])", body):
        start, end = pos, pos + len(piece)
        pos = end
        t = piece.strip()
        if not (lo <= len(t) <= hi):
            continue
        off = start + piece.index(t) if t in piece else start
        local = [(sp.start - off, sp.end - off) for sp in spans
                 if sp.start >= off and sp.end <= off + len(t)]
        out.append((t, local))
    return out


def collect(works: int, seed: int, max_sentences: int, span_kind: str = "bar"):
    a = Analyzer.load(os.path.join(ROOT, "data", "dict"))
    files = sorted(os.listdir(RAW))
    rnd = random.Random(seed)
    picks = rnd.sample(files, works)

    rows = []           # (delta, violation, in_kanji_run)
    residue_bad = 0
    ruby_total = 0
    sent_used = 0
    for f in picks:
        raw = open(os.path.join(RAW, f), encoding="utf-8", errors="replace").read()
        body, spans, residue = extract(raw)
        residue_bad += len(residual_violations(residue))
        if span_kind == "bar":
            spans = [sp for sp in spans if sp.bar]
        ruby_total += len(spans)
        for text, local in sentences_with_spans(body, spans):
            if not local:
                continue          # ルビの無い文は違反が定義できないので母集団に入れない
            try:
                result, deltas = delta_local(a, text)
            except AssertionError:
                continue
            if result is None:
                continue
            sent_used += 1
            # 文内のバイト位置 → 文字位置
            b2c = {}
            bp = 0
            for ci, ch in enumerate(text):
                b2c[bp] = ci
                bp += len(ch.encode("utf-8"))
            b2c[bp] = len(text)
            covers = [(s, e) for (s, e) in local if e - s >= 2]
            for bpos, d in deltas.items():
                cp = b2c.get(bpos)
                if cp is None or cp == 0 or cp == len(text):
                    continue
                viol = any(s < cp < e for (s, e) in covers)
                in_kanji = bool(KANJI.match(text[cp - 1]) and KANJI.match(text[cp]))
                rows.append((d, viol, in_kanji))
            if sent_used >= max_sentences:
                break
        if sent_used >= max_sentences:
            break
    return rows, dict(works=len(picks), ruby_total=ruby_total,
                      residual_violations=residue_bad, sentences=sent_used)


def ranks(xs):
    """同順位は平均順位。∞ は最大側にまとめて並ぶ。"""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(xs, ys):
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = math.sqrt(sum((v - mx) ** 2 for v in rx))
    dy = math.sqrt(sum((v - my) ** 2 for v in ry))
    return num / (dx * dy) if dx and dy else 0.0


def quartile_split(deltas):
    """下位四分位と上位四分位の添字を返す。∞ は最大側。"""
    order = sorted(range(len(deltas)), key=lambda i: deltas[i])
    q = len(order) // 4
    return order[:q], order[-q:]


def analyse(rows, label, shuffles, seed):
    if len(rows) < 100:
        return {"label": label, "n": len(rows), "error": "標本が少なすぎる"}
    ds = [r[0] for r in rows]
    vs = [1 if r[1] else 0 for r in rows]
    lo_idx, hi_idx = quartile_split(ds)
    rate = lambda idx: sum(vs[i] for i in idx) / len(idx)  # noqa: E731
    r_lo, r_hi = rate(lo_idx), rate(hi_idx)
    ratio = (r_lo / r_hi) if r_hi > 0 else float("inf")
    rho = spearman(ds, vs)

    # 対照: δ をシャッフルして比の帰無分布を作る。
    #
    # δ を並べ替えて毎回ソートし直すのと、**四分位の枠を固定してラベルを並べ替える**のは
    # 同じ帰無分布になる(枠の大きさが変わらないため)。後者なら並べ替えも合計も C 側で済み、
    # 2,000 回が 11 分から数秒になる。事前登録した帰無分布そのものは変えていない。
    rnd = random.Random(seed)
    order = sorted(range(len(ds)), key=lambda i: ds[i])
    q = len(order) // 4
    vs_ord = [vs[i] for i in order]
    null_ratio = []
    for _ in range(shuffles):
        rnd.shuffle(vs_ord)
        a2 = sum(vs_ord[:q]) / q
        b2 = sum(vs_ord[-q:]) / q
        null_ratio.append((a2 / b2) if b2 > 0 else float("inf"))
    p_emp = sum(1 for x in null_ratio if x >= ratio) / len(null_ratio)

    return {
        "label": label,
        "n": len(rows),
        "violations": sum(vs),
        "violation_rate": sum(vs) / len(vs),
        "inf_share": sum(1 for d in ds if d == INF) / len(ds),
        "q1_rate": r_lo,
        "q4_rate": r_hi,
        "ratio_q1_over_q4": ratio,
        "spearman_rho": rho,
        "empirical_p": p_emp,
        "shuffles": shuffles,
        "kanji_run_share_q1": sum(1 for i in lo_idx if rows[i][2]) / len(lo_idx),
        "kanji_run_share_q4": sum(1 for i in hi_idx if rows[i][2]) / len(hi_idx),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--works", type=int, default=600)
    ap.add_argument("--sentences", type=int, default=40000)
    ap.add_argument("--seed", type=int, default=20260830)
    ap.add_argument("--shuffles", type=int, default=2000)
    ap.add_argument("--spans", choices=["bar", "auto"], default="bar")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "g01.json"))
    args = ap.parse_args()

    rows, meta = collect(args.works, args.seed, args.sentences, args.spans)
    meta["span_kind"] = args.spans
    print(json.dumps(meta, ensure_ascii=False))
    if meta["residual_violations"] != 0:
        raise SystemExit(f"ルビ抽出の残骸ゲートが落ちている({meta['residual_violations']} 件)。"
                         "測定に入ってはならない")

    primary = analyse(rows, "母集団全体(事前登録)", args.shuffles, args.seed)
    kanji_only = analyse([r for r in rows if r[2]], "漢字連続の内部に限る(交絡検査)",
                         args.shuffles, args.seed)
    doc = {"meta": meta, "span_kind": args.spans, "primary": primary, "kanji_only": kanji_only,
           "threshold": {"ratio": 1.5, "alpha": 0.05, "spearman_sign": "negative"}}
    for r in (primary, kanji_only):
        print("\n──", r["label"])
        for k, v in r.items():
            if k == "label":
                continue
            print(f"   {k:22s} {v}")
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"\n→ {args.out}")


if __name__ == "__main__":
    main()
