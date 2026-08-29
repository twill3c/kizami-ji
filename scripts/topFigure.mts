/**
 * トップページの図を、**出荷実装と同じ経路で**組む。
 * 画面が描くものと焼いた図が食い違わないように、ここ以外で作らない(HC-045)。
 */
import { readFile } from "node:fs/promises";
import path from "node:path";

import { Analyzer } from "../src/lib/analyze";
import { loadDict, type DictSource } from "../src/lib/dict";
import { buildLattice, figureFromLattice, secondPath, type FigureData } from "../src/lib/lattice";

export const TOP_TEXT = "の北詰まで";

export async function buildTopFigure(root = process.cwd()): Promise<FigureData> {
  const src: DictSource = {
    async read(name) {
      return new Uint8Array(await readFile(path.join(root, "data", "dict", name)));
    },
  };
  const { dict } = await loadDict(src);
  const a = new Analyzer(dict);
  const l = buildLattice(a, TOP_TEXT);
  if (l === null) throw new Error("トップの例文でラティスが組めない");
  return figureFromLattice(l, secondPath(l)?.nodes ?? null);
}
