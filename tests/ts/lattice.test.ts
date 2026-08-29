/**
 * T-014b — δ の二実装照合。TypeScript の δ_local が Python 実装と完全一致する。
 *
 * 期待値の出所: tests/fixtures/delta.json(Python 実装。MeCab と分割・総コストが
 * 一致することは T-010/T-011 で確認済み)。∞ は null で書いてある。
 */

import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { Analyzer } from "../../src/lib/analyze";
import { loadDict, type DictSource } from "../../src/lib/dict";
import { buildLattice, secondPath, INF } from "../../src/lib/lattice";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const fsSource: DictSource = {
  async read(name) {
    return new Uint8Array(await readFile(path.join(ROOT, "data", "dict", name)));
  },
};

const { dict } = await loadDict(fsSource);
const analyzer = new Analyzer(dict);

interface Fixture {
  count: number;
  cases: Array<{
    text: string;
    cost: number;
    words: string[];
    emission: number;
    connection: number;
    deltas: Array<number | null>;
  }>;
}
const fx: Fixture = JSON.parse(
  await readFile(path.join(ROOT, "tests", "fixtures", "delta.json"), "utf8"),
);

describe("T-014b δ の二実装照合", () => {
  it("フィクスチャが空でない(検査が働いている)", () => {
    expect(fx.cases.length).toBeGreaterThan(500);
    expect(fx.count).toBe(fx.cases.length);
  });

  it("δ・総コスト・内訳が Python 実装と完全一致する", () => {
    const bad: Array<{ text: string; want: unknown; got: unknown }> = [];
    let finiteSeen = 0;
    let infSeen = 0;
    for (const c of fx.cases) {
      const l = buildLattice(analyzer, c.text);
      expect(l, `ラティスが組めない: ${c.text}`).not.toBeNull();
      const got = l!.boundaries.map((b) => (b.delta === INF ? null : b.delta));
      finiteSeen += got.filter((x) => x !== null).length;
      infSeen += got.filter((x) => x === null).length;
      const same =
        l!.cost === c.cost &&
        l!.path.map((n) => n.surface).join("") === c.words.join("") &&
        l!.breakdown.emission === c.emission &&
        l!.breakdown.connection === c.connection &&
        got.join(",") === c.deltas.join(",");
      if (!same) {
        bad.push({
          text: c.text,
          want: { cost: c.cost, emission: c.emission, connection: c.connection, deltas: c.deltas },
          got: { cost: l!.cost, ...l!.breakdown, deltas: got },
        });
      }
    }
    // 両方の値が出ていないと、片側だけ合っていても気づけない
    expect(finiteSeen, "有限の δ が一つも無い ── 検査が働いていない").toBeGreaterThan(100);
    expect(infSeen, "∞ の δ が一つも無い ── 検査が働いていない").toBeGreaterThan(100);
    expect(bad.slice(0, 2), `不一致 ${bad.length} 件`).toEqual([]);
  });

  it("内訳の和が総コストになる", () => {
    for (const c of fx.cases.slice(0, 200)) {
      const l = buildLattice(analyzer, c.text)!;
      const { emission, connection, eos } = l.breakdown;
      expect(emission + connection + eos).toBe(l.cost);
    }
  });
});

describe("二位の道", () => {
  it("「の北詰まで」で δ = 0 の道が復元でき、分割が一位と異なる", () => {
    const l = buildLattice(analyzer, "の北詰まで")!;
    const s = secondPath(l);
    expect(s).not.toBeNull();
    expect(s!.delta).toBe(0);
    const first = l.path.map((n) => n.surface).join("/");
    const second = s!.nodes.map((n) => n.surface).join("/");
    expect(first).toBe("の/北/詰/まで");
    expect(second).toBe("の/北詰/まで");
    expect(second).not.toBe(first);
  });

  it("復元した二位の道のコストが 一位 + δ になる", () => {
    for (const text of ["の北詰まで", "通りかかった下男が", "どうか惡しからず"]) {
      const l = buildLattice(analyzer, text);
      if (l === null) continue;
      const s = secondPath(l);
      if (s === null) continue;
      let cost = l.dict.connection(0, s.nodes[0].token.lc) + s.nodes[0].token.cost;
      for (let i = 1; i < s.nodes.length; i++) {
        cost += l.dict.connection(s.nodes[i - 1].token.rc, s.nodes[i].token.lc)
          + s.nodes[i].token.cost;
      }
      cost += l.dict.connection(s.nodes[s.nodes.length - 1].token.rc, 0);
      expect(cost, `${text}: 復元した道のコストが合わない`).toBe(l.cost + s.delta);
      // 道が本文を隙間なく覆っていること
      expect(s.nodes[0].pos).toBe(0);
      expect(s.nodes[s.nodes.length - 1].end).toBe(l.raw.length);
    }
  });
});
