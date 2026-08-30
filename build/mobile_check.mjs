import { chromium, devices } from "playwright";
/**
 * 実機幅の検品。狭い画面で本文が横に溢れていないこと、ページが縦に伸びすぎていないことを見る。
 * 表の列が潰れて一文字ずつ折り返すと、緑のまま 16,000px の縦棒ができる(loop_007 で実測)。
 *
 *   node build/mobile_check.mjs                  # 本番
 *   node build/mobile_check.mjs http://127.0.0.1:PORT
 */
const base = process.argv[2] ?? "https://kizami-ji.vercel.app";
const b = await chromium.launch();
const ctx = await b.newContext({ ...devices["iPhone 13"] });
const page = await ctx.newPage();
let bad = 0;
for (const [name, p] of [["top","/"],["kizamu","/kizamu/"],["kinsa","/kinsa/"],
                        ["yaseta","/yaseta/"],["houhou","/houhou/"]]) {
  await page.goto(base + p, { waitUntil: "networkidle" });
  if (p === "/kizamu/") {
    await page.getByRole("button", { name: "刻む", exact: true }).click();
    await page.locator(".words .word").first().waitFor({ timeout: 120000 });
  }
  const over = await page.evaluate(() => ({
    doc: document.documentElement.scrollWidth,
    win: window.innerWidth,
  }));
  const tall = await page.evaluate(() => document.documentElement.scrollHeight);
  const okWide = over.doc <= over.win + 1;
  // 縦に伸びすぎていないか。表の列が潰れて一文字ずつ折り返すとここで捕まる
  const okTall = tall < 12000;
  if (!okWide || !okTall) bad++;
  console.log(
    `${okWide && okTall ? "OK " : "NG "} ${p} 横 ${over.doc}px / 画面 ${over.win}px・縦 ${tall}px`,
  );
  await page.screenshot({ path: `build/shots/m-${name}.png`, fullPage: true });
}
await b.close();
process.exit(bad ? 1 : 0);
