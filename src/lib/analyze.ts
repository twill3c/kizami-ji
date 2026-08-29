/**
 * 形態素解析(TypeScript・出荷実装)。
 *
 * ラティスを組み、Viterbi で最小コスト経路を選ぶ。scripts/analyze.py と同じ手順を踏み、
 * MeCab と分割・総コストが完全一致することを T-014 で検査する。
 * **参照実装を一切参照しない**(SPEC O-2)。
 */

import { charLen, type Dict, type Token } from "./dict";

/** MeCab の DEFAULT_MAX_GROUPING_SIZE。未知語をまとめ上げる上限文字数。 */
export const MAX_GROUPING = 24;

export interface Node {
  surface: string;
  /** 本文のバイト位置(前置の空白を飛ばした後の語頭) */
  start: number;
  end: number;
  lc: number;
  rc: number;
  /** 生起コスト */
  cost: number;
  /** 直前ノードからの連接コスト */
  conn: number;
  pos: string[];
  conj: string[];
  unknown: boolean;
}

export interface Result {
  /** 経路の総コスト(BOS から EOS まで) */
  cost: number;
  nodes: Node[];
}

export interface Candidate {
  end: number;
  start: number;
  token: Token;
  unknown: boolean;
}

/** バイト列の位置 i にある文字の符号位置を返す。 */
export function codePointAt(raw: Uint8Array, i: number): number {
  const b = raw[i];
  if (b < 0x80) return b;
  if (b < 0xe0) return ((b & 0x1f) << 6) | (raw[i + 1] & 0x3f);
  if (b < 0xf0) return ((b & 0x0f) << 12) | ((raw[i + 1] & 0x3f) << 6) | (raw[i + 2] & 0x3f);
  return (
    ((b & 0x07) << 18) |
    ((raw[i + 1] & 0x3f) << 12) |
    ((raw[i + 2] & 0x3f) << 6) |
    (raw[i + 3] & 0x3f)
  );
}

export class Analyzer {
  constructor(readonly dict: Dict) {}

  /**
   * 位置 pos から始まる候補ノードを MeCab と同じ順序で返す。
   * 辞書語(長さ昇順)→ 未知語(group → length)の順。順序はタイブレークに効く。
   */
  candidates(raw: Uint8Array, pos: number): Candidate[] {
    const d = this.dict;
    const n = raw.length;

    // 先頭の SPACE 系文字を読み飛ばす(MeCab の seekToOtherType 相当)
    let b2 = pos;
    while (b2 < n && (d.charInfo(codePointAt(raw, b2)).type & d.spaceType) !== 0) {
      b2 += charLen(raw[b2]);
    }
    if (b2 >= n) return [];

    const ci = d.charInfo(codePointAt(raw, b2));
    const out: Candidate[] = [];
    for (const hit of d.commonPrefix(raw, b2)) {
      for (let k = 0; k < hit.count; k++) {
        out.push({ end: hit.end, start: b2, token: d.tokenAt(hit.surfaceIndex, k), unknown: false });
      }
    }
    if (out.length > 0 && ci.invoke === 0) return out;

    let b3 = b2 + charLen(raw[b2]);
    let groupEnd = -1;
    if (ci.group === 1) {
      let e = b3;
      let cnt = 1;
      while (e < n && (d.charInfo(codePointAt(raw, e)).type & ci.type) !== 0) {
        e += charLen(raw[e]);
        cnt++;
      }
      if (cnt <= MAX_GROUPING) {
        for (const t of d.unkTokens(ci.defaultType)) {
          out.push({ end: e, start: b2, token: t, unknown: true });
        }
      }
      groupEnd = e;
    }
    for (let i = 0; i < ci.length; i++) {
      if (b3 > n) break;
      if (b3 !== groupEnd) {
        for (const t of d.unkTokens(ci.defaultType)) {
          out.push({ end: b3, start: b2, token: t, unknown: true });
        }
      }
      if (b3 >= n || (d.charInfo(codePointAt(raw, b3)).type & ci.type) === 0) break;
      b3 += charLen(raw[b3]);
    }
    return out;
  }

  analyze(text: string): Result | null {
    const d = this.dict;
    const raw = new TextEncoder().encode(text);
    const n = raw.length;

    /**
     * ends[i] = 位置 i で終わるノードごとの最良経路。
     *
     * **並び順が同点の勝敗を決める。** MeCab は end_node_list へ先頭挿入し、比較は厳密な `<`
     * なので、同点ならリストの先頭が勝つ。先頭に来るのは最後に挿入されたもの、すなわち
     * **最も遅く始まったノード**であり、同じ開始位置の中では**最初に生成されたトークン**。
     * これを再現するため、位置ごとに作った束を forward のまま前へ差し込む(SPEC F-02a)。
     */
    type Entry = { cost: number; rc: number; back: Back | null };
    type Back = {
      prev: Back | null;
      start: number;
      end: number;
      token: Token;
      unknown: boolean;
      conn: number;
    };

    const ends: Entry[][] = Array.from({ length: n + 1 }, () => []);
    ends[0] = [{ cost: 0, rc: 0, back: null }];

    for (let pos = 0; pos < n; pos++) {
      if (ends[pos].length === 0) continue;
      if ((raw[pos] & 0xc0) === 0x80) continue;
      const fresh = new Map<number, Entry[]>();
      for (const c of this.candidates(raw, pos)) {
        let best: Entry | null = null;
        for (const e of ends[pos]) {
          const conn = d.connection(e.rc, c.token.lc);
          const total = e.cost + conn + c.token.cost;
          if (best === null || total < best.cost) {
            best = {
              cost: total,
              rc: c.token.rc,
              back: {
                prev: e.back,
                start: c.start,
                end: c.end,
                token: c.token,
                unknown: c.unknown,
                conn,
              },
            };
          }
        }
        if (best !== null) {
          const g = fresh.get(c.end);
          if (g) g.push(best);
          else fresh.set(c.end, [best]);
        }
      }
      for (const [e, group] of fresh) {
        ends[e] = group.concat(ends[e]);
      }
    }

    if (ends[n].length === 0) return null;
    let bestCost = Infinity;
    let bestBack: Back | null = null;
    for (const e of ends[n]) {
      const total = e.cost + d.connection(e.rc, 0);
      if (total < bestCost) {
        bestCost = total;
        bestBack = e.back;
      }
    }

    const decoder = new TextDecoder();
    const nodes: Node[] = [];
    for (let b = bestBack; b !== null; b = b.prev) {
      nodes.push({
        surface: decoder.decode(raw.subarray(b.start, b.end)),
        start: b.start,
        end: b.end,
        lc: b.token.lc,
        rc: b.token.rc,
        cost: b.token.cost,
        conn: b.conn,
        pos: d.pos(b.token.posId),
        conj: d.conj(b.token.conjId),
        unknown: b.unknown,
      });
    }
    nodes.reverse();
    return { cost: bestCost, nodes };
  }
}
