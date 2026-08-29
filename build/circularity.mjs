/**
 * O-2 — 循環の禁止の静的検査。
 *
 * 出荷実装(src/)が参照実装(MeCab / fugashi / ipadic / probe/ / scripts/)へ
 * 依存していないことを、import 文と裸の識別子の両方で確かめる。
 *
 * **禁止語をこのファイルに直接書かない。** 書くと、この原稿を走査したときに
 * 自分の対照を撃つ(chikuma-seiki loop_007・次の一字 HC-002 と同型)。
 * 符号位置から実行時に組み立てる。
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

const from = (...codes) => String.fromCharCode(...codes);

/** 禁止する識別子。符号位置から組み立てる。 */
export const FORBIDDEN = [
  from(102, 117, 103, 97, 115, 104, 105), //   f u g a s h i
  from(77, 101, 67, 97, 98), //               M e C a b
  from(109, 101, 99, 97, 98), //               m e c a b
  from(105, 112, 97, 100, 105, 99), //         i p a d i c
];

/** 禁止するパス片(参照実装の置き場)。 */
export const FORBIDDEN_PATHS = [
  from(112, 114, 111, 98, 101, 47), //         p r o b e /
  from(115, 99, 114, 105, 112, 116, 115, 47), // s c r i p t s /
];

/**
 * ソース 1 本を走査して違反を返す。
 * 行コメント・ブロックコメントの中は「言及」であって依存ではないので見逃す。
 */
export function scanSource(text, label = "<source>") {
  const hits = [];
  const stripped = text
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "))
    .replace(/(^|[^:])\/\/[^\n]*/g, (m, p1) => p1 + " ".repeat(m.length - p1.length));
  const lines = stripped.split("\n");
  lines.forEach((line, i) => {
    for (const word of FORBIDDEN) {
      /*
        辞書の**固有名**は依存ではない。`mecab-ipadic 2.7.0-20070801` は閲覧者に見せる文にも、
        NOTICE にも書く必要がある(BSD 系の条件)。一方、参照実装は `fugashi` `MeCab` `ipadic` と
        単体で現れる。**ハイフンに接しているかどうか**が両者を分ける。
      */
      let from = 0;
      for (;;) {
        const at = line.indexOf(word, from);
        if (at < 0) break;
        from = at + 1;
        const before = at > 0 ? line[at - 1] : "";
        const after = at + word.length < line.length ? line[at + word.length] : "";
        if (before === "-" || after === "-") continue;
        hits.push({ file: label, line: i + 1, what: word });
      }
    }
    const imp = line.match(/(?:from|import|require)\s*\(?\s*["'`]([^"'`]+)["'`]/);
    if (imp) {
      for (const p of FORBIDDEN_PATHS) {
        if (imp[1].includes(p)) hits.push({ file: label, line: i + 1, what: imp[1] });
      }
    }
  });
  return hits;
}

/** ディレクトリを再帰的に走査する。戻り値は { hits, files } で、files は走査した本数。 */
export function scanDir(dir, exts = [".ts", ".tsx", ".mjs", ".js"]) {
  const hits = [];
  const files = [];
  const walk = (d) => {
    for (const name of readdirSync(d)) {
      const p = path.join(d, name);
      if (statSync(p).isDirectory()) {
        if (name === "node_modules" || name.startsWith(".")) continue;
        walk(p);
      } else if (exts.includes(path.extname(name))) {
        files.push(p);
        hits.push(...scanSource(readFileSync(p, "utf8"), p));
      }
    }
  };
  walk(dir);
  return { hits, files };
}
