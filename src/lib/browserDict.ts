/**
 * ブラウザ側の辞書読み込み。**同一オリジンの public/dict からしか取らない**(SPEC N-02)。
 *
 * 実際に読んだバイト数を数えて返す。画面に出すのは見積もりではなく実測(SPEC F-08)。
 * `Content-Length` は当てにしない —— 圧縮転送だと生の長さが返るとは限らないし、
 * Vercel は HEAD に content-length を返さないことがある(kototoi-do の実測)。
 * ここでは**受け取った本体の長さ**を数える。
 */

import { FILES, loadDict, type DictSource, type LoadResult } from "./dict";

export interface Progress {
  loaded: number;
  total: number;
  name: string;
}

export function createSource(
  base = "/dict",
  onProgress?: (p: Progress) => void,
): DictSource {
  let done = 0;
  const total = FILES.length + 1; // meta.json を含む
  return {
    async read(name: string): Promise<Uint8Array> {
      const res = await fetch(`${base}/${name}`, { cache: "force-cache" });
      if (!res.ok) throw new Error(`辞書を読めない: ${name} (${res.status})`);
      const buf = new Uint8Array(await res.arrayBuffer());
      done += 1;
      onProgress?.({ loaded: done, total, name });
      return buf;
    },
  };
}

let cached: Promise<LoadResult> | null = null;

/** 一度だけ読む。二度目からは同じ約束を返す。 */
export function getDict(onProgress?: (p: Progress) => void): Promise<LoadResult> {
  if (cached === null) cached = loadDict(createSource("/dict", onProgress));
  return cached;
}
