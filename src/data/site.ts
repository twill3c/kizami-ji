export const SITE = {
  name: "刻み路",
  reading: "kizami-ji",
  tagline: "形態素解析はラティスの上の最小コスト経路探索である",
  origin: "https://kizami-ji.vercel.app",
};

/** フリート共通フッタ規約の 5 項目。並びも項目数も変えない(ラベルの文言だけ和名を温存する)。 */
export const FOOTER = {
  license: "https://github.com/twill3c/kizami-ji/blob/main/LICENSE",
  repository: "https://github.com/twill3c/kizami-ji",
  guide: "https://claude.ai/code/artifact/1815e01b-c49e-4265-a468-ffa25c1cc04b",
  blueprint: "https://claude.ai/code/artifact/7ebd7edd-57fc-49e7-b2dd-3203e89b31ef",
  appMenu: "https://app-menu-amber.vercel.app/",
};

export const NAV = [
  { href: "/", label: "刻み路" },
  { href: "/kizamu/", label: "刻む" },
  { href: "/kinsa/", label: "僅差の文" },
  { href: "/houhou/", label: "方法と限界" },
];

/** 「刻む」ページの例文。すべて青空文庫の実文から採った(作例は使わない)。 */
export const EXAMPLES = [
  { text: "の北詰まで", note: "完全同点。北詰 と 北/詰 が同じコストで並ぶ" },
  { text: "東京都は日本の首都である", note: "跨ぐ語が無い境界(δ = ∞)が並ぶ" },
  { text: "すもももももももものうち", note: "候補が多い。ラティスが混む" },
  { text: "そして今朝がたのリユクサツクの學生を思ひ出した。", note: "未知語のまとめ上げ" },
  { text: "親譲りの無鉄砲で小供の時から損ばかりしている。", note: "夏目漱石『坊っちゃん』" },
];
