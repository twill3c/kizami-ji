import type { Metadata } from "next";

import LatticeView from "@/components/LatticeView";
import stats from "@/data/delta-stats.json";
import top from "@/data/top-lattice.json";
import { NAV } from "@/data/site";
import type { FigureData } from "@/lib/lattice";

export const metadata: Metadata = { title: "刻み路" };

const fig = top as FigureData;
const pct = (n: number, d: number) => `${((n / d) * 100).toFixed(1)}%`;

export default function Home() {
  const tie = fig.boundaries.find((b) => b.delta === 0);
  return (
    <>
      <h1>形態素解析は、決まった答えを返しているわけではない</h1>
      <p className="lede">
        日本語を単語に分ける処理は、辞書を引いて候補を並べ(ラティス)、
        その上を通る道のうち<strong>合計コストが最小のもの</strong>を選んでいる。
        出てくるのは「正解」ではなく「一番安い道」である。
      </p>

      <section className="panel">
        <h3>「{fig.text}」を刻むと</h3>
        <LatticeView figure={fig} upto={null} />
        <p className="legend">
          <span><span className="swatch swatch--ai" />最小経路</span>
          <span><span className="swatch swatch--shu" />二位の道</span>
          <span><b>δ</b> その境界で切らずに済ませたときの追加コスト</span>
        </p>
        <p style={{ marginTop: "0.9rem" }}>
          候補は <strong>{fig.nodeCount} 個</strong>。選ばれたのは{" "}
          <strong>{fig.words.join(" / ")}</strong> で、総コストは{" "}
          <strong>{fig.cost.toLocaleString("ja-JP")}</strong>。
          {tie && (
            <>
              {" "}ところが <strong>「北詰」を一語にした道も、同じ 12,965</strong> である。
              語の値段の差 3,103 を、品詞の並びやすさの差がちょうど打ち消している。
              どちらが出るかは、辞書をどちらから見たかで決まっている。
            </>
          )}
        </p>
        <p className="meter">
          永井荷風「地下鉄道は既に京橋の北詰まで開鑿せられ」より。
        </p>
      </section>

      <p>
        このサイトは、割れた結果ではなく<strong>割れ方が何によって決まったか</strong>を出す ——
        候補ノード、語そのものの値段(生起コスト)、品詞の並びやすさ(連接コスト)、
        そして一位と二位の差 δ。
      </p>

      <h2>測って分かったこと</h2>
      <div className="scroll">
        <table>
          <tbody>
            <tr>
              <td>境界のうち、跨ぐ語が辞書に<strong>一つも無い</strong>もの</td>
              <td className="num">{pct(stats.infinite, stats.boundaries)}</td>
            </tr>
            <tr>
              <td>完全同点(δ = 0)の境界</td>
              <td className="num">{stats.zero.toLocaleString("ja-JP")} / {stats.boundaries.toLocaleString("ja-JP")}</td>
            </tr>
            <tr>
              <td>同点を含む文</td>
              <td className="num">{stats.sentences_with_tie} / {stats.sentences.toLocaleString("ja-JP")}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p>
        分割の大半は、迷った末の判断ではない。<strong>語彙がそこにしか道を残していない</strong>という
        事実の反映である。詳しくは<a href="/kinsa/">僅差の文</a>に。
      </p>

      <div className="note">
        <span className="note__label">この画面から先で起きること</span>
        <p>
          解析はすべて閲覧者の端末の中で走る。入力した文はどこへも送られない。
          サーバ側の処理は一つも無く、辞書は<a href="/kizamu/">刻む</a>で最初に「刻む」を
          押したときだけ取りに行く。<strong>このページは辞書を 1 バイトも読み込まない</strong>
          (上の図は焼いてある)。
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
