// data/dict → public/dict。next build の前に走る(package.json の prebuild)。
//
// public/dict は .gitignore にある。辞書の正本は data/dict で、そちらがコミットされている。
// 写しそこねると画面が黙って空になるので、**ファイル数とバイト数を検算して落とす**。
import { copyFileSync, existsSync, mkdirSync, readdirSync, rmSync, statSync } from "node:fs";
import path from "node:path";

const SRC = path.resolve("data/dict");
const DST = path.resolve("public/dict");
const REQUIRED = [
  "meta.json", "surf.bin", "surf_len.bin", "tok_count.bin",
  "tok_lc.bin", "tok_rc.bin", "tok_cost.bin", "tok_pos.bin", "tok_cf.bin",
  "matrix.bin", "chars.bin",
];
// 形式 1 の置き土産。残っていると public/ から古いものが配られ続ける
const STALE = ["surf_idx.bin", "tok_start.bin"];

mkdirSync(DST, { recursive: true });
const have = new Set(readdirSync(SRC));
const missing = REQUIRED.filter((f) => !have.has(f));
if (missing.length) {
  console.error(`data/dict に不足: ${missing.join(", ")}  — python scripts/build_dict.py を先に走らせる`);
  process.exit(1);
}
let bytes = 0;
for (const f of REQUIRED) {
  copyFileSync(path.join(SRC, f), path.join(DST, f));
  const a = statSync(path.join(SRC, f)).size;
  const b = statSync(path.join(DST, f)).size;
  if (a !== b) {
    console.error(`写しのサイズが違う: ${f} ${a} != ${b}`);
    process.exit(1);
  }
  bytes += b;
}
for (const f of STALE) {
  const q = path.join(DST, f);
  if (existsSync(q)) {
    rmSync(q);
    console.log(`古い形式の置き土産を削除: ${f}`);
  }
}
console.log(`辞書を写した: ${REQUIRED.length} ファイル / ${(bytes / 1048576).toFixed(2)} MB`);
