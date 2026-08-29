/**
 * 焼いた図(src/data/top-lattice.json)が、出荷実装が今その場で作る図と一致すること。
 *
 * 生成物をコミットする以上、**実装が動いたのに図が古いまま**という食い違いが起こりうる。
 * 図と本文が別のデータを描く故障(HC-045)はテストが緑のまま通るので、ここで照合する。
 */
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { buildTopFigure, TOP_TEXT } from "../../scripts/topFigure.mts";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

describe("トップの焼いた図", () => {
  it("今の実装が作る図と一致する", async () => {
    const baked = JSON.parse(
      await readFile(path.join(ROOT, "src", "data", "top-lattice.json"), "utf8"),
    );
    const fresh = await buildTopFigure(ROOT);
    expect(baked).toEqual(fresh);
  });

  it("図が主張している中身が実際に入っている", async () => {
    const fig = await buildTopFigure(ROOT);
    expect(fig.text).toBe(TOP_TEXT);
    expect(fig.words).toEqual(["の", "北", "詰", "まで"]);
    expect(fig.cost).toBe(12965);
    // 完全同点の境界が一つあること ── これがトップで見せたいもの
    expect(fig.boundaries.filter((b: { delta: number | null }) => b.delta === 0)).toHaveLength(1);
    // 二位の道が一位と違う分割であること
    const bestSet = new Set(fig.best);
    expect(fig.second.some((id: number) => !bestSet.has(id))).toBe(true);
  });
});
