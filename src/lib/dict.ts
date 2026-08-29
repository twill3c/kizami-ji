/**
 * 出荷用辞書の読み取り(TypeScript・出荷実装)。
 *
 * scripts/build_dict.py が書き出した data/dict/ をそのまま読む。
 * **参照実装(MeCab / fugashi / scripts/ 配下)を一切参照しない**(SPEC O-2)。
 *
 * ファイルは全てリトルエンディアン。読み込み時に実行環境の並びを確かめる。
 */

export const FORMAT = 1;

export interface DictSource {
  /** ファイル名を渡すと中身を返す。ブラウザでは fetch、Node では fs。 */
  read(name: string): Promise<Uint8Array>;
}

export interface Meta {
  format: number;
  dict: string;
  surface_count: number;
  token_count: number;
  lsize: number;
  rsize: number;
  pos: string[][];
  conj: string[][];
  categories: string[];
  category_rules: Record<string, [number, number, number]>;
  unk: Record<string, number[][]>;
  char_runs: number;
}

export interface Token {
  lc: number;
  rc: number;
  cost: number;
  posId: number;
  conjId: number;
}

/** 文字種の情報。char.bin の 32 bit を解いたもの。 */
export interface CharInfo {
  type: number;
  defaultType: number;
  length: number;
  group: number;
  invoke: number;
}

function isLittleEndian(): boolean {
  const b = new ArrayBuffer(2);
  new Uint16Array(b)[0] = 1;
  return new Uint8Array(b)[0] === 1;
}

/** Uint8Array から型付き配列を作る。byteOffset がそろわない場合があるので必ず複製する。 */
function view<T>(b: Uint8Array, ctor: new (buf: ArrayBuffer) => T): T {
  const copy = b.slice();
  return new ctor(copy.buffer);
}

export class Dict {
  readonly meta: Meta;
  private readonly surf: Uint8Array;
  private readonly sidx: Uint32Array;
  private readonly tokStart: Uint32Array;
  private readonly tokCount: Uint8Array;
  private readonly tokLc: Uint16Array;
  private readonly tokRc: Uint16Array;
  private readonly tokCost: Int16Array;
  private readonly tokPos: Uint8Array;
  private readonly tokCf: Uint16Array;
  readonly matrix: Int16Array;
  private readonly charStarts: Uint32Array;
  private readonly charInfos: Uint32Array;

  readonly surfaceCount: number;
  readonly tokenCount: number;
  readonly lsize: number;
  readonly spaceType: number;

  constructor(meta: Meta, files: Record<string, Uint8Array>) {
    if (meta.format !== FORMAT) throw new Error(`辞書形式の版が違う: ${meta.format} != ${FORMAT}`);
    this.meta = meta;
    this.surf = files["surf.bin"]!;
    this.sidx = view(files["surf_idx.bin"]!, Uint32Array);
    this.tokStart = view(files["tok_start.bin"]!, Uint32Array);
    this.tokCount = files["tok_count.bin"]!;
    this.tokLc = view(files["tok_lc.bin"]!, Uint16Array);
    this.tokRc = view(files["tok_rc.bin"]!, Uint16Array);
    this.tokCost = view(files["tok_cost.bin"]!, Int16Array);
    this.tokPos = files["tok_pos.bin"]!;
    this.tokCf = view(files["tok_cf.bin"]!, Uint16Array);
    this.matrix = view(files["matrix.bin"]!, Int16Array);
    const ch = view(files["chars.bin"]!, Uint32Array);
    const half = ch.length / 2;
    this.charStarts = ch.subarray(0, half);
    this.charInfos = ch.subarray(half);

    this.surfaceCount = this.sidx.length - 1;
    this.tokenCount = this.tokLc.length;
    this.lsize = meta.lsize;
    this.spaceType = 1 << meta.categories.indexOf("SPACE");

    if (this.surfaceCount !== meta.surface_count) {
      throw new Error(`表層数が meta と合わない: ${this.surfaceCount} != ${meta.surface_count}`);
    }
    if (this.tokenCount !== meta.token_count) {
      throw new Error(`トークン数が meta と合わない: ${this.tokenCount} != ${meta.token_count}`);
    }
  }

  // ---------------------------------------------------------------- 表層

  surfaceBytes(i: number): Uint8Array {
    return this.surf.subarray(this.sidx[i], this.sidx[i + 1]);
  }

  surfaceLength(i: number): number {
    return this.sidx[i + 1] - this.sidx[i];
  }

  /** surface(i) と key[from, to) を辞書順で比べる。負 / 0 / 正。 */
  private cmp(i: number, key: Uint8Array, from: number, to: number): number {
    const a = this.sidx[i];
    const alen = this.sidx[i + 1] - a;
    const blen = to - from;
    const n = alen < blen ? alen : blen;
    for (let k = 0; k < n; k++) {
      const d = this.surf[a + k] - key[from + k];
      if (d !== 0) return d;
    }
    return alen - blen;
  }

  /** surface(i) の先頭 (to-from) バイトと key[from, to) を比べる(接頭辞比較)。 */
  private cmpPrefix(i: number, key: Uint8Array, from: number, to: number): number {
    const a = this.sidx[i];
    const alen = this.sidx[i + 1] - a;
    const blen = to - from;
    const n = alen < blen ? alen : blen;
    for (let k = 0; k < n; k++) {
      const d = this.surf[a + k] - key[from + k];
      if (d !== 0) return d;
    }
    // 表層のほうが短ければ、接頭辞として一致していない = 小さい側
    return alen < blen ? -1 : 0;
  }

  private lowerBound(key: Uint8Array, from: number, to: number, lo: number, hi: number): number {
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      if (this.cmp(mid, key, from, to) < 0) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }

  private upperBoundPrefix(key: Uint8Array, from: number, to: number, lo: number, hi: number): number {
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      if (this.cmpPrefix(mid, key, from, to) <= 0) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }

  /**
   * key[start:] の接頭辞になっている表層を、**短い順**に返す。
   * 順序は MeCab の commonPrefixSearch と同じで、同点の勝敗に効く(SPEC F-02a)。
   */
  commonPrefix(key: Uint8Array, start: number): Array<{ end: number; surfaceIndex: number; count: number }> {
    const out: Array<{ end: number; surfaceIndex: number; count: number }> = [];
    let lo = 0;
    let hi = this.surfaceCount;
    let i = start;
    const n = key.length;
    while (i < n) {
      i += charLen(key[i]);
      lo = this.lowerBound(key, start, i, lo, hi);
      hi = this.upperBoundPrefix(key, start, i, lo, hi);
      if (lo >= hi) break;
      if (this.surfaceLength(lo) === i - start) {
        out.push({ end: i, surfaceIndex: lo, count: this.tokCount[lo] });
      }
    }
    return out;
  }

  // ---------------------------------------------------------------- token

  tokenAt(surfaceIndex: number, k: number): Token {
    const t = this.tokStart[surfaceIndex] + k;
    return {
      lc: this.tokLc[t],
      rc: this.tokRc[t],
      cost: this.tokCost[t],
      posId: this.tokPos[t],
      conjId: this.tokCf[t],
    };
  }

  pos(posId: number): string[] {
    return this.meta.pos[posId];
  }

  conj(conjId: number): string[] {
    return this.meta.conj[conjId];
  }

  connection(rightIdPrev: number, leftIdNext: number): number {
    return this.matrix[rightIdPrev + this.lsize * leftIdNext];
  }

  // ---------------------------------------------------------------- 文字種

  charInfoRaw(cp: number): number {
    const c = cp < 0xffff ? cp : 0;
    let lo = 0;
    let hi = this.charStarts.length;
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      if (this.charStarts[mid] <= c) lo = mid + 1;
      else hi = mid;
    }
    return this.charInfos[lo - 1];
  }

  charInfo(cp: number): CharInfo {
    const v = this.charInfoRaw(cp);
    return {
      type: v & 0x3ffff,
      defaultType: (v >>> 18) & 0xff,
      length: (v >>> 26) & 0xf,
      group: (v >>> 30) & 1,
      invoke: (v >>> 31) & 1,
    };
  }

  categoryRule(name: string): [number, number, number] {
    return this.meta.category_rules[name];
  }

  unkTokens(categoryIndex: number): Token[] {
    const rows = this.meta.unk[this.meta.categories[categoryIndex]] ?? [];
    return rows.map((r) => ({ lc: r[0], rc: r[1], cost: r[2], posId: r[3], conjId: r[4] }));
  }
}

export const FILES = [
  "surf.bin",
  "surf_idx.bin",
  "tok_start.bin",
  "tok_count.bin",
  "tok_lc.bin",
  "tok_rc.bin",
  "tok_cost.bin",
  "tok_pos.bin",
  "tok_cf.bin",
  "matrix.bin",
  "chars.bin",
] as const;

/** UTF-8 の先頭バイトから文字のバイト数を返す。 */
export function charLen(b: number): number {
  return b < 0x80 ? 1 : b < 0xe0 ? 2 : b < 0xf0 ? 3 : 4;
}

export interface LoadResult {
  dict: Dict;
  /** 実際に読んだバイト数。画面に出す(SPEC F-08)。 */
  bytes: number;
}

export async function loadDict(src: DictSource): Promise<LoadResult> {
  if (!isLittleEndian()) {
    throw new Error("辞書はリトルエンディアン固定。この環境では読めない");
  }
  const metaRaw = await src.read("meta.json");
  let bytes = metaRaw.byteLength;
  const meta = JSON.parse(new TextDecoder().decode(metaRaw)) as Meta;
  const files: Record<string, Uint8Array> = {};
  for (const name of FILES) {
    const b = await src.read(name);
    bytes += b.byteLength;
    files[name] = b;
  }
  return { dict: new Dict(meta, files), bytes };
}
