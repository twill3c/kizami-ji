/**
 * 焼いた図を src/data/top-lattice.json に書く。生成物はコミットする。
 * ずれていないことは tests/ts/topfigure.test.ts が毎回作り直して照合する。
 *
 *   npx vite-node scripts/make_top_figure.mts
 */
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { buildTopFigure } from "./topFigure.mts";

const fig = await buildTopFigure();
const out = path.join(process.cwd(), "src", "data", "top-lattice.json");
mkdirSync(path.dirname(out), { recursive: true });
writeFileSync(out, `${JSON.stringify(fig, null, 1)}\n`, "utf8");
console.log(`${fig.nodeCount} 候補 / ${fig.words.join(" / ")} / 総コスト ${fig.cost} → ${out}`);
