/**
 * T-021 / T-022 / T-023 — 循環の禁止(O-2)の静的検査と、その対照。
 *
 * 検出系のテストは、対象に違反が無いときと検査そのものが壊れているときとで
 * まったく同じ緑を返す。だから陽性対照(必ず捕まえるべき例)と
 * 陰性対照(撃ってはならない例)、走査対象が空でないことを対で置く(HC-041)。
 */

import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { scanDir, scanSource, FORBIDDEN, FORBIDDEN_PATHS } from "../../build/circularity.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

const from = (...codes: number[]) => String.fromCharCode(...codes);

describe("O-2 循環の禁止", () => {
  it("T-021 出荷実装が参照実装へ依存していない", () => {
    const { hits } = scanDir(path.join(ROOT, "src"));
    expect(hits, `違反 ${hits.length} 件: ${JSON.stringify(hits.slice(0, 3))}`).toEqual([]);
  });

  it("T-023 走査対象が空でない", () => {
    const { files } = scanDir(path.join(ROOT, "src"));
    expect(files.length).toBeGreaterThan(1);
    expect(files.some((f: string) => f.endsWith("analyze.ts"))).toBe(true);
  });

  it("T-022 陽性対照 — 禁止の import を捕まえる", () => {
    // 禁止語は符号位置から組み立てる。原稿に直接書くと、この原稿の走査が自分を撃つ
    const bad =
      "import { Tagger } from " +
      JSON.stringify(from(102, 117, 103, 97, 115, 104, 105)) +
      ";\nexport const x = 1;\n";
    const hits = scanSource(bad, "<positive-control>");
    expect(hits.length).toBeGreaterThan(0);
  });

  it("T-022b 陽性対照 — 参照実装ディレクトリからの import を捕まえる", () => {
    const bad =
      "import { analyze } from " +
      JSON.stringify("../../" + from(115, 99, 114, 105, 112, 116, 115, 47) + "analyze") +
      ";\n";
    const hits = scanSource(bad, "<positive-control-path>");
    expect(hits.length).toBeGreaterThan(0);
  });

  it("T-022e 陰性対照 — 辞書の固有名は依存ではない", () => {
    // mecab-ipadic は閲覧者に見せる文にも NOTICE にも書く。ハイフンで参照実装と分かれる
    const prose =
      "export const x = <p>辞書は " +
      from(109, 101, 99, 97, 98) + "-" + from(105, 112, 97, 100, 105, 99) +
      " 2.7.0-20070801(392,126 語)。</p>;";
    expect(scanSource(prose, "<dictionary-name>")).toEqual([]);
  });

  it("T-022f 陽性対照 — ハイフンが無ければ捕まる", () => {
    const dep = "const t = new " + from(77, 101, 67, 97, 98) + "();";
    expect(scanSource(dep, "<bare-identifier>").length).toBeGreaterThan(0);
  });

  it("T-022c 陰性対照 — 正当なソースを撃たない", () => {
    const good = [
      'import { charLen } from "./dict";',
      "export function f(x: number) { return charLen(x); }",
      "// 辞書の出所は NOTICE に書いてある",
    ].join("\n");
    expect(scanSource(good, "<negative-control>")).toEqual([]);
  });

  it("T-022d 陰性対照 — コメント中の言及は依存ではない", () => {
    const mention = "// " + FORBIDDEN[0] + " と突き合わせる\nexport const y = 2;\n";
    expect(scanSource(mention, "<comment>")).toEqual([]);
  });

  it("検査器そのものが空回りしていない", () => {
    expect(FORBIDDEN.length).toBeGreaterThan(2);
    expect(FORBIDDEN_PATHS.length).toBeGreaterThan(1);
    for (const w of FORBIDDEN) {
      expect(scanSource(`const a = ${JSON.stringify(w)};`, "<self>").length).toBeGreaterThan(0);
    }
  });
});
