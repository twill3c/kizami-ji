import type { NextConfig } from "next";

// 静的書き出しのみ。サーバ関数を一つも持たない(SPEC N-01)。
// 辞書はビルド前に data/dict から public/dict へ写し、同一オリジンから配る(N-02/N-04)。
// next build は build_dict.py を呼ばない —— 呼べば Vercel 上に Python と ipadic が要る。
const nextConfig: NextConfig = {
  output: "export",
  reactStrictMode: true,
  trailingSlash: true,
};

export default nextConfig;
