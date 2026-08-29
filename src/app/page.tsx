import type { Metadata } from "next";
import { NAV } from "@/data/site";

export const metadata: Metadata = { title: "刻み路" };

export default function Home() {
  return (
    <>
      <h1>形態素解析は、決まった答えを返しているわけではない</h1>
      <p className="lede">
        日本語を単語に分ける処理は、辞書を引いて候補を並べ(ラティス)、
        その上を通る道のうち<strong>合計コストが最小のもの</strong>を選んでいる。
        出てくるのは「正解」ではなく「一番安い道」である。
      </p>
      <p>
        このサイトは、割れた結果ではなく<strong>割れ方が何によって決まったか</strong>を出す ——
        候補ノード、語そのものの値段(生起コスト)、品詞の並びやすさ(連接コスト)、
        そして一位と二位の差。
      </p>

      <div className="note">
        <span className="note__label">この画面から先で起きること</span>
        <p>
          解析はすべて閲覧者の端末の中で走る。入力した文はどこへも送られない。
          サーバ側の処理は一つも無く、辞書(12.9 MB)は「刻む」を最初に押したときだけ取りに行く。
          <strong>このページは辞書を 1 バイトも読み込まない。</strong>
        </p>
      </div>

      <h2>ページ</h2>
      <ul>
        {NAV.slice(1).map((n) => (
          <li key={n.href}><a href={n.href}>{n.label}</a></li>
        ))}
      </ul>

      <h2>使っている辞書</h2>
      <p>
        mecab-ipadic 2.7.0-20070801(392,126 語)。読み・発音・活用形の文字列は
        このサイトでは使わないので配っていない。<strong>2007 年で更新が止まっている辞書</strong>なので、
        近年の語は未知語として扱われる。それは欠陥ではなく前提である。
      </p>
    </>
  );
}
