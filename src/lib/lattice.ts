/**
 * ラティスの構築と δ(局所)。画面が必要とするものはすべてここから出す。
 *
 * δ_local(p) = (p をまたぐノードを含む最良経路のコスト) − (最小コスト)
 *
 * 0 なら「p で切らなくても同じ値の道がある」。p をまたぐノードが辞書に一つも無ければ ∞。
 *
 * **δ を「危うさ」「間違いやすさ」と結びつけて呼ばないこと**(SPEC F-32b)。
 * G-01 で測ったところ、ルビの括りを跨ぐ率と δ の関係は閾値に届かず、
 * 漢字連続の内部に限ると符号が反転した。δ は「解析器が迷った量」でしかない。
 */

import { Analyzer, codePointAt, type Node as PathNode } from "./analyze";
import { charLen, type Dict, type Token } from "./dict";

export const INF = Number.POSITIVE_INFINITY;

export interface LatticeNode {
  id: number;
  /** ラティス上の開始(直前ノードの終端。前置の空白を含みうる) */
  pos: number;
  /** 表層の開始 */
  start: number;
  end: number;
  surface: string;
  token: Token;
  unknown: boolean;
  /** BOS からこのノードまで(このノードの生起コストを含む)。到達不能なら INF */
  fwd: number;
  /** このノードを出てから EOS まで(出る連接を含む) */
  bwd: number;
}

export interface Boundary {
  /** 本文のバイト位置 */
  at: number;
  /** 文字位置(画面用) */
  charAt: number;
  delta: number;
}

export interface Lattice {
  text: string;
  raw: Uint8Array;
  /** 経路の復元にも連接コストが要るので、辞書はラティスが持つ */
  dict: Dict;
  nodes: LatticeNode[];
  startsAt: number[][];
  endsAt: number[][];
  /** 最小経路(ノード id の列) */
  best: number[];
  cost: number;
  boundaries: Boundary[];
  /** 経路コストの内訳 */
  breakdown: { emission: number; connection: number; eos: number };
  path: PathNode[];
}

export function buildLattice(a: Analyzer, text: string): Lattice | null {
  const d: Dict = a.dict;
  const raw = new TextEncoder().encode(text);
  const n = raw.length;
  const decoder = new TextDecoder();

  const nodes: LatticeNode[] = [];
  const startsAt: number[][] = Array.from({ length: n + 1 }, () => []);
  const endsAt: number[][] = Array.from({ length: n + 1 }, () => []);
  const reachable = new Array<boolean>(n + 1).fill(false);
  reachable[0] = true;

  for (let pos = 0; pos < n; pos++) {
    if (!reachable[pos]) continue;
    if ((raw[pos] & 0xc0) === 0x80) continue;
    for (const c of a.candidates(raw, pos)) {
      const nd: LatticeNode = {
        id: nodes.length,
        pos,
        start: c.start,
        end: c.end,
        surface: decoder.decode(raw.subarray(c.start, c.end)),
        token: c.token,
        unknown: c.unknown,
        fwd: INF,
        bwd: INF,
      };
      nodes.push(nd);
      startsAt[pos].push(nd.id);
      endsAt[nd.end].push(nd.id);
      reachable[nd.end] = true;
    }
  }
  if (endsAt[n].length === 0) return null;

  // 前向き
  for (let pos = 0; pos <= n; pos++) {
    for (const id of startsAt[pos]) {
      const nd = nodes[id];
      let best = pos === 0 ? d.connection(0, nd.token.lc) : INF;
      for (const mid of endsAt[pos]) {
        const m = nodes[mid];
        if (m.fwd === INF) continue;
        const c = m.fwd + d.connection(m.token.rc, nd.token.lc);
        if (c < best) best = c;
      }
      nd.fwd = best === INF ? INF : best + nd.token.cost;
    }
  }
  // 後ろ向き
  for (let pos = n; pos >= 0; pos--) {
    for (const id of endsAt[pos]) {
      const nd = nodes[id];
      if (nd.end === n) {
        nd.bwd = d.connection(nd.token.rc, 0);
        continue;
      }
      let best = INF;
      for (const mid of startsAt[nd.end]) {
        const m = nodes[mid];
        if (m.bwd === INF) continue;
        const c = d.connection(nd.token.rc, m.token.lc) + m.token.cost + m.bwd;
        if (c < best) best = c;
      }
      nd.bwd = best;
    }
  }

  const result = a.analyze(text);
  if (result === null) return null;
  const total = result.cost;

  // 最小経路のノードを id で引き直す(analyze はタイブレークまで MeCab に合わせてある)
  const best: number[] = [];
  for (const pn of result.nodes) {
    const id = endsAt[pn.end].find((i) => {
      const x = nodes[i];
      return x.start === pn.start && x.token.lc === pn.lc && x.token.rc === pn.rc
        && x.token.cost === pn.cost && x.unknown === pn.unknown;
    });
    if (id === undefined) throw new Error(`最小経路のノードがラティスに無い: ${pn.surface}`);
    best.push(id);
  }

  // p をまたぐノードのうち最良のもの
  const spanning = new Map<number, number>();
  for (const nd of nodes) {
    if (nd.fwd === INF || nd.bwd === INF) continue;
    const through = nd.fwd + nd.bwd;
    for (let p = nd.start + 1; p < nd.end; p++) {
      if ((raw[p] & 0xc0) === 0x80) continue;
      const cur = spanning.get(p);
      if (cur === undefined || through < cur) spanning.set(p, through);
    }
  }

  const byteToChar = new Map<number, number>();
  {
    let bp = 0;
    let ci = 0;
    for (const ch of text) {
      byteToChar.set(bp, ci);
      bp += new TextEncoder().encode(ch).length;
      ci += 1;
    }
    byteToChar.set(bp, ci);
  }

  const boundaries: Boundary[] = [];
  for (let i = 0; i < result.nodes.length - 1; i++) {
    const at = result.nodes[i].end;
    const s = spanning.get(at);
    boundaries.push({
      at,
      charAt: byteToChar.get(at) ?? -1,
      delta: s === undefined ? INF : s - total,
    });
  }

  const emission = result.nodes.reduce((s, x) => s + x.cost, 0);
  const connection = result.nodes.reduce((s, x) => s + x.conn, 0);
  const last = result.nodes[result.nodes.length - 1];
  const eos = d.connection(last.rc, 0);

  return {
    text,
    raw,
    dict: d,
    nodes,
    startsAt,
    endsAt,
    best,
    cost: total,
    boundaries,
    breakdown: { emission, connection, eos },
    path: result.nodes,
  };
}

/**
 * 二位の道 —— 最小経路と**分割が異なる**経路のうち最良のもの(SPEC F-04a)。
 * 同じ分割で同表層の別トークンを選んだだけの経路は二位に数えない。
 * δ が最小の境界を跨ぐ道がそれにあたる。
 */
export function secondPath(l: Lattice): { delta: number; nodes: LatticeNode[] } | null {
  let bestAt = -1;
  let bestDelta = INF;
  for (const b of l.boundaries) {
    if (b.delta < bestDelta) {
      bestDelta = b.delta;
      bestAt = b.at;
    }
  }
  if (bestAt < 0 || bestDelta === INF) return null;

  // その境界を跨ぐノードのうち through が最小のものを通る道を復元する
  let via: LatticeNode | null = null;
  let viaThrough = INF;
  for (const nd of l.nodes) {
    if (nd.fwd === INF || nd.bwd === INF) continue;
    if (!(nd.start < bestAt && bestAt < nd.end)) continue;
    const t = nd.fwd + nd.bwd;
    if (t < viaThrough) {
      viaThrough = t;
      via = nd;
    }
  }
  if (via === null) return null;
  return { delta: bestDelta, nodes: reconstructThrough(l, via) };
}

/** ノード via を必ず通る最良経路を復元する。 */
function reconstructThrough(l: Lattice, via: LatticeNode): LatticeNode[] {
  const d = l.nodes;
  const back: LatticeNode[] = [];
  // 前半 —— via の fwd を作った直前ノードを辿る
  let cur = via;
  while (cur.pos > 0) {
    let pick: LatticeNode | null = null;
    for (const mid of l.endsAt[cur.pos]) {
      const m = d[mid];
      if (m.fwd === INF) continue;
      if (m.fwd + connOf(l, m, cur) + cur.token.cost === cur.fwd) {
        pick = m;
        break;
      }
    }
    if (pick === null) break;
    back.push(pick);
    cur = pick;
  }
  back.reverse();

  // 後半 —— via の bwd を作った直後ノードを辿る
  const fwd: LatticeNode[] = [];
  cur = via;
  while (cur.end < l.raw.length) {
    let pick: LatticeNode | null = null;
    for (const mid of l.startsAt[cur.end]) {
      const m = d[mid];
      if (m.bwd === INF) continue;
      if (connOf(l, cur, m) + m.token.cost + m.bwd === cur.bwd) {
        pick = m;
        break;
      }
    }
    if (pick === null) break;
    fwd.push(pick);
    cur = pick;
  }
  return [...back, via, ...fwd];
}

function connOf(l: Lattice, from: LatticeNode, to: LatticeNode): number {
  return l.dict.connection(from.token.rc, to.token.lc);
}

/** 文字位置ごとの δ を引けるようにした補助(画面用)。 */
export function deltaByChar(l: Lattice): Map<number, number> {
  const m = new Map<number, number>();
  for (const b of l.boundaries) m.set(b.charAt, b.delta);
  return m;
}

export { Analyzer, codePointAt, charLen };

/* ------------------------------------------------------------------ 図のためのデータ

   図は**辞書を持たない**素のデータだけで描けるようにする。
   トップページはこれを事前に焼いたものを読むので、辞書を 1 バイトも取らずに済む(F-06)。
   JSON は Infinity を持てないので、δ = ∞ は null で表す。
*/

export interface FigureNode {
  id: number;
  start: number;
  end: number;
  surface: string;
  unknown: boolean;
}

export interface FigureBoundary {
  at: number;
  charAt: number;
  /** null は ∞(跨ぐ語が辞書に一つも無い) */
  delta: number | null;
}

export interface FigureData {
  text: string;
  nodes: FigureNode[];
  best: number[];
  second: number[];
  boundaries: FigureBoundary[];
  /** まとめる前の候補数 */
  nodeCount: number;
  cost: number;
  words: string[];
}

export function figureFromLattice(l: Lattice, second: LatticeNode[] | null): FigureData {
  return {
    text: l.text,
    nodes: l.nodes.map((n) => ({
      id: n.id, start: n.start, end: n.end, surface: n.surface, unknown: n.unknown,
    })),
    best: [...l.best],
    second: (second ?? []).map((n) => n.id),
    boundaries: l.boundaries.map((b) => ({
      at: b.at, charAt: b.charAt, delta: b.delta === INF ? null : b.delta,
    })),
    nodeCount: l.nodes.length,
    cost: l.cost,
    words: l.path.map((n) => n.surface),
  };
}
