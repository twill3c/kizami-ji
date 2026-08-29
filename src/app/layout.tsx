import type { Metadata } from "next";
import { FOOTER, NAV, SITE } from "@/data/site";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE.origin),
  title: { default: `${SITE.name} — ${SITE.tagline}`, template: `%s — ${SITE.name}` },
  description:
    "形態素解析は決まった答えを返す処理に見えて、実体はラティスの上の最小コスト経路探索である。候補ノード・生起コスト・連接コスト・二位との差を、閲覧者の端末の中だけで見せる。入力した文はどこへも送られない。",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>
        <header className="masthead">
          <div className="wrap">
            <a className="masthead__name" href="/">{SITE.name}</a>
            <span className="masthead__reading">{SITE.reading}</span>
            <nav aria-label="ページ">
              {NAV.map((i) => <a key={i.href} href={i.href}>{i.label}</a>)}
            </nav>
          </div>
        </header>

        <main className="wrap">{children}</main>

        {/* fleet: fixed footer。共通規約の 5 項目・この並び・下部固定 */}
        <footer className="site-footer">
          <div className="site-footer__inner">
            <a href={FOOTER.license}>MIT License</a>
            <span className="site-footer__copy">© 2026 坂田哲朗</span>
            <a href={FOOTER.repository}>GitHub</a>
            <a href={FOOTER.guide}>刻み路の歩き方</a>
            <a href={FOOTER.blueprint}>刻み路の設計図</a>
            <a href={FOOTER.appMenu}>App Menu</a>
          </div>
        </footer>
      </body>
    </html>
  );
}
