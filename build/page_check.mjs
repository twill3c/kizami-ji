/**
 * 実ブラウザ検品。T-043 / T-044 / T-045 と G-03 の実測。
 *
 * **道具そのものが壊れていないかを疑う**(HC-041)。取得に失敗した画面を撮っても
 * 「撮影しました」と出るので、この道具は失敗を**終了コード**で知らせる。
 * 期待した要素が出るまで待ち、出なければ落ちる。
 *
 *   node build/page_check.mjs              # out/ をローカルで配って検品
 *   node build/page_check.mjs --url https://kizami-ji.vercel.app   # 本番に向ける
 */

import { createReadStream, existsSync, statSync } from "node:fs";
import { createGzip } from "node:zlib";
import { createServer } from "node:http";
import path from "node:path";
import { chromium } from "playwright";

const args = process.argv.slice(2);
const urlArg = args.includes("--url") ? args[args.indexOf("--url") + 1] : null;
const OUT = path.resolve("out");

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".bin": "application/octet-stream",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
};

function serve() {
  return new Promise((resolve) => {
    const server = createServer((req, res) => {
      const clean = decodeURIComponent(req.url.split("?")[0]);
      let file = path.join(OUT, clean);
      if (existsSync(file) && statSync(file).isDirectory()) file = path.join(file, "index.html");
      if (!existsSync(file) && existsSync(`${file}.html`)) file = `${file}.html`;
      if (!existsSync(file)) {
        res.writeHead(404);
        res.end("not found");
        return;
      }
      // Vercel は静的資産を圧縮して配る。ローカルで無圧縮のまま測ると
      // 「閲覧者が実際に落とす量」より大きい数字が出て、G-03 の判定が意味を失う。
      // ここでも gzip で配り、本番へ向けたときと同じ土俵で測る。
      const type = TYPES[path.extname(file)] ?? "application/octet-stream";
      const accepts = (req.headers["accept-encoding"] ?? "").includes("gzip");
      if (accepts) {
        res.writeHead(200, { "content-type": type, "content-encoding": "gzip", vary: "accept-encoding" });
        createReadStream(file).pipe(createGzip({ level: 9 })).pipe(res);
      } else {
        res.writeHead(200, { "content-type": type });
        createReadStream(file).pipe(res);
      }
    });
    server.listen(0, "127.0.0.1", () => resolve({ server, port: server.address().port }));
  });
}

const fail = (msg) => {
  console.error(`NG  ${msg}`);
  process.exitCode = 1;
};
const ok = (msg) => console.log(`OK  ${msg}`);

let base = urlArg;
let server = null;
if (base === null) {
  if (!existsSync(OUT)) {
    console.error("out/ が無い。npm run build を先に走らせる");
    process.exit(1);
  }
  const s = await serve();
  server = s.server;
  base = `http://127.0.0.1:${s.port}`;
}
console.log(`検品先 ${base}`);

const browser = await chromium.launch();
const ctx = await browser.newContext();
const page = await ctx.newPage();

/**
 * **回線を通った実バイト数**を数える。
 *
 * `response.body()` は伸長後の中身なので、圧縮転送だと実際の転送量より大きく出る
 * (最初この道具はそれで 12.89 MB と報告し、G-03 を落とした)。
 * `request().sizes().responseBodySize` が符号化後の長さを返す。
 * Content-Length は当てにしない —— Vercel は HEAD に返さないことがある。
 */
const seen = [];
page.on("response", async (res) => {
  let size = 0;
  let raw = 0;
  try {
    const s = await res.request().sizes();
    size = s.responseBodySize ?? 0;
  } catch {
    size = 0;
  }
  try {
    raw = (await res.body()).length;
  } catch {
    raw = 0;
  }
  seen.push({ url: res.url(), status: res.status(), size, raw });
});

const origin = new URL(base).origin;
const dictBytes = () =>
  seen.filter((r) => r.url.includes("/dict/")).reduce((a, b) => a + b.size, 0);
const dictRaw = () =>
  seen.filter((r) => r.url.includes("/dict/")).reduce((a, b) => a + b.raw, 0);
const foreign = () => seen.filter((r) => !r.url.startsWith(origin) && !r.url.startsWith("data:"));

// ---------------------------------------------------------------- トップ

await page.goto(`${base}/`, { waitUntil: "networkidle" });
const h1 = await page.locator("h1").first().textContent();
if (!h1 || h1.trim().length < 5) fail(`トップの見出しが取れない: ${JSON.stringify(h1)}`);
else ok(`トップの見出し: ${h1.trim().slice(0, 30)}`);

// T-044 / F-06 — トップは辞書を 1 バイトも取らない
if (dictBytes() !== 0) fail(`トップが辞書を ${dictBytes()} バイト読んでいる(F-06 違反)`);
else ok("トップの辞書取得 0 バイト");

const footerLinks = await page.locator(".site-footer a").allTextContents();
if (footerLinks.length !== 5) fail(`フッタのリンクが ${footerLinks.length} 本(規約は 5)`);
else ok(`フッタ 5 項目: ${footerLinks.join(" / ")}`);

// ---------------------------------------------------------------- 刻む

seen.length = 0;
await page.goto(`${base}/kizamu/`, { waitUntil: "networkidle" });
if (dictBytes() !== 0) fail(`「刻む」を開いただけで辞書を ${dictBytes()} バイト読んでいる`);
else ok("「刻む」を開いた時点の辞書取得 0 バイト");

await page.getByRole("button", { name: "刻む", exact: true }).click();
await page.locator(".words .word").first().waitFor({ timeout: 120_000 });

const words = await page.locator(".words .word__surface").allTextContents();
if (words.join("/") !== "の/北詰/まで" && words.join("/") !== "の/北/詰/まで") {
  fail(`「の北詰まで」の分割が想定外: ${words.join("/")}`);
} else {
  ok(`分割: ${words.join(" / ")}`);
}

const total = await page.locator(".ledger .total dd").first().textContent();
if ((total ?? "").replace(/,/g, "") !== "12965") fail(`総コストが 12,965 でない: ${total}`);
else ok(`総コスト ${total}`);

// δ の表だけを見る。表を指定しないと候補ノードの表まで拾い、
// 総コストの並びを δ と読み違える(最初この道具はそれで 3 境界の文に 31 個の δ を数えた)
const deltas = await page.locator("#delta-table tbody tr td.num:last-child").allTextContents();
if (deltas.length !== 3) fail(`「の北詰まで」の境界は 3 つのはずが ${deltas.length} 個`);
else ok(`境界 ${deltas.length} 個`);
if (!deltas.includes("0")) fail(`δ = 0 の境界が画面に出ていない: ${deltas.join(",")}`);
else ok(`δ の並び: ${deltas.join(" ")}`);

const svg = await page.locator("svg[role=img]").count();
if (svg !== 1) fail(`ラティス図が ${svg} 枚(1 枚のはず)`);
else ok("ラティス図が 1 枚描かれている");

// G-03 / T-043 — 初回解析までの実測転送量
const dict = dictBytes();
console.log(`    辞書の転送量(符号化後)${(dict / 1048576).toFixed(2)} MB / 伸長後 ${(dictRaw() / 1048576).toFixed(2)} MB`);
if (dict === 0) fail("辞書を 1 バイトも読んでいない(解析が走っていない疑い)");
else if (dict >= 8 * 1048576) fail(`初回解析までの転送が ${(dict / 1048576).toFixed(2)} MB(G-03 は 8 MB 未満)`);
else ok(`G-03 初回解析までの転送 ${(dict / 1048576).toFixed(2)} MB < 8 MB`);

// T-045 — 自オリジン以外へ出ていないこと
const out = foreign();
if (out.length > 0) fail(`外部への通信が ${out.length} 件: ${out.slice(0, 3).map((r) => r.url).join(", ")}`);
else ok("外部への通信 0 件");

// 目視検品用の画面。図が読めるかどうかは自動化しないと決めてある(HC-041)ので、
// 撮って人が見る。撮影に失敗したら落とす —— 取れていない画面を「撮りました」と言わせない
const shot = "build/shots/kizamu.png";
await page.locator("svg[role=img]").scrollIntoViewIfNeeded();
await page.screenshot({ path: shot, fullPage: true });
if (!existsSync(shot) || statSync(shot).size < 10_000) fail(`画面を撮れていない: ${shot}`);
else ok(`画面を撮った ${shot}(${(statSync(shot).size / 1024).toFixed(0)} KB)`);

await browser.close();
if (server !== null) server.close();

if (process.exitCode === 1) {
  console.error("\n検品は不合格。");
} else {
  console.log("\n検品は合格。");
}
