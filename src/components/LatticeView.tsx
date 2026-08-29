/**
 * ラティスの図。素のデータだけで描く純粋な描画なので "use client" を付けない。
 * トップページ(サーバ側で静的に書き出す)では JS を一切配らずに済む。
 *
 * ラティスの図。候補ノードを段に並べ、最小経路と二位の道を重ねる。
 *
 * **図に添える文字は、図を描いたのと同じデータから出す**(HC-045)。
 * 座標も内容も決め打ちしない —— ノードの位置は start/end から、
 * δ の値は boundaries から、そのまま引く。
 */

import type { FigureData } from "@/lib/lattice";

const RH = 30;      // 1 段の高さ
const PAD_L = 46;   // BOS の分
const PAD_R = 46;   // EOS の分
const TOP = 34;     // 本文の帯

export interface Props {
  figure: FigureData;
  /** DP の段階表示。この文字位置までのノードだけを濃く描く。null なら全部 */
  upto: number | null;
}

/** バイト位置 → 文字位置の対応表を本文から作る。 */
function charIndex(text: string): Map<number, number> {
  const m = new Map<number, number>();
  const enc = new TextEncoder();
  let bp = 0;
  let ci = 0;
  for (const ch of text) {
    m.set(bp, ci);
    bp += enc.encode(ch).length;
    ci += 1;
  }
  m.set(bp, ci);
  return m;
}

export default function LatticeView({ figure, upto }: Props) {
  const text = figure.text;
  const chars = [...text];
  const idx = charIndex(text);
  const bestIds = new Set(figure.best);
  const secondIds = new Set(figure.second);

  /*
    同じ範囲・同じ表層の候補(同表層の別トークン)は**一つの枠にまとめる**。
    まとめないと「の」だけで 5 段を使い、5 文字の文が 28 段の細い柱になって読めない
    (loop_005 の目視検品で判明)。候補の全量は下の表に出してあるので、
    図では枠に「×n」を添えて、まとめたことが分かるようにする。
  */
  interface Span {
    key: string;
    c0: number;
    c1: number;
    surface: string;
    ids: number[];
    unknown: boolean;
    row: number;
  }
  const bySpan = new Map<string, Span>();
  for (const nd of figure.nodes) {
    const c0 = idx.get(nd.start);
    const c1 = idx.get(nd.end);
    if (c0 === undefined || c1 === undefined) continue;
    const key = `${c0}-${c1}-${nd.surface}-${nd.unknown ? "u" : "d"}`;
    const hit = bySpan.get(key);
    if (hit) hit.ids.push(nd.id);
    else bySpan.set(key, { key, c0, c1, surface: nd.surface, ids: [nd.id], unknown: nd.unknown, row: -1 });
  }
  // 段の割り当て —— 開始位置の昇順に、重ならない一番上の段へ置く
  const rowEnds: number[] = [];
  const placed = [...bySpan.values()].sort((a, b) => a.c0 - b.c0 || a.c1 - b.c1);
  for (const sp of placed) {
    let row = rowEnds.findIndex((e) => e <= sp.c0);
    if (row < 0) {
      row = rowEnds.length;
      rowEnds.push(0);
    }
    rowEnds[row] = sp.c1;
    sp.row = row;
  }

  const rows = Math.max(1, rowEnds.length);
  // 短い文では字幅を広げて図を使い切る。長い文では詰める(横スクロールに逃がす)
  const CW = Math.max(26, Math.min(56, Math.round(640 / Math.max(1, chars.length))));
  const width = PAD_L + chars.length * CW + PAD_R;
  const height = TOP + rows * RH + 34;
  const x = (c: number) => PAD_L + c * CW;
  const y = (r: number) => TOP + r * RH;

  const pathOf = (ids: Set<number>) =>
    placed
      .filter((n) => n.ids.some((i) => ids.has(i)))
      .sort((a, b) => a.c0 - b.c0)
      .map((n) => ({ x: x(n.c0) + (x(n.c1) - x(n.c0)) / 2, y: y(n.row) + RH / 2 - 3 }));

  const line = (pts: { x: number; y: number }[]) =>
    pts.length < 2 ? "" : pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${p.y}`).join(" ");

  const bestPts = pathOf(bestIds);
  const secondPts = pathOf(secondIds);

  return (
    <div className="scroll">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        role="img"
        aria-label={`「${text}」のラティス。候補 ${figure.nodeCount} 個を ${placed.length} 枠にまとめた。最小経路は ${figure.words.join(" / ")}`}
      >
        {/* 文字の帯 */}
        {chars.map((ch, i) => (
          <g key={`c${i}`}>
            <line x1={x(i)} y1={20} x2={x(i)} y2={height - 26} stroke="var(--line)" strokeWidth={1} />
            <text
              x={x(i) + CW / 2}
              y={15}
              textAnchor="middle"
              fontFamily="var(--serif)"
              fontSize={15}
              fill="var(--ink-2)"
            >
              {ch}
            </text>
          </g>
        ))}
        <line x1={x(chars.length)} y1={20} x2={x(chars.length)} y2={height - 26} stroke="var(--line)" strokeWidth={1} />

        <text x={8} y={y(0) + RH / 2} fontFamily="var(--mono)" fontSize={10} fill="var(--muted)">BOS</text>
        <text x={width - PAD_R + 6} y={y(0) + RH / 2} fontFamily="var(--mono)" fontSize={10} fill="var(--muted)">EOS</text>

        {/* 二位の道 → 最小経路の順に重ねる(最小経路が上に来る) */}
        {secondPts.length > 1 && (
          <path d={line(secondPts)} fill="none" stroke="var(--shu)" strokeWidth={2} strokeDasharray="5 3" opacity={0.85} />
        )}
        {bestPts.length > 1 && (
          <path d={line(bestPts)} fill="none" stroke="var(--ai)" strokeWidth={2.2} />
        )}

        {/* 候補ノード */}
        {placed.map((n) => {
          const isBest = n.ids.some((i) => bestIds.has(i));
          const isSecond = !isBest && n.ids.some((i) => secondIds.has(i));
          const dim = upto !== null && n.c1 > upto;
          const fill = isBest ? "var(--ai-w)" : isSecond ? "var(--shu-w)" : "var(--card)";
          const stroke = isBest ? "var(--ai)" : isSecond ? "var(--shu)" : "var(--line)";
          const label = n.surface.length > 6 ? `${n.surface.slice(0, 6)}…` : n.surface;
          return (
            <g key={n.key} opacity={dim ? 0.22 : 1}>
              <rect
                x={x(n.c0) + 2}
                y={y(n.row) + 2}
                width={x(n.c1) - x(n.c0) - 4}
                height={RH - 7}
                rx={4}
                fill={fill}
                stroke={stroke}
                strokeWidth={isBest || isSecond ? 1.4 : 1}
                strokeDasharray={n.unknown ? "3 2" : undefined}
              />
              <text
                x={x(n.c0) + (x(n.c1) - x(n.c0)) / 2}
                y={y(n.row) + RH / 2 - 1}
                textAnchor="middle"
                fontFamily="var(--serif)"
                fontSize={12}
                fill={isBest ? "var(--ai)" : isSecond ? "var(--shu)" : "var(--ink-2)"}
              >
                {label}
              </text>
              {n.ids.length > 1 && (
                <text
                  x={x(n.c1) - 6}
                  y={y(n.row) + 10}
                  textAnchor="end"
                  fontFamily="var(--mono)"
                  fontSize={8}
                  fill="var(--muted)"
                >
                  ×{n.ids.length}
                </text>
              )}
            </g>
          );
        })}

        {/* 境界ごとの δ */}
        {figure.boundaries.map((b) => (
          <text
            key={`b${b.at}`}
            x={x(b.charAt)}
            y={height - 10}
            textAnchor="middle"
            fontFamily="var(--mono)"
            fontSize={9.5}
            fill={b.delta === 0 ? "var(--shu)" : "var(--muted)"}
          >
            {b.delta === null ? "∞" : b.delta.toLocaleString("ja-JP")}
          </text>
        ))}
        <text x={4} y={height - 10} fontFamily="var(--mono)" fontSize={9} fill="var(--muted)">δ</text>
      </svg>
    </div>
  );
}
