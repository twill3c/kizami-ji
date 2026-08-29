import type { Metadata } from "next";

// 測定の正本は data/ にある。写しを作るとずれるので、そのまま読む
import g01 from "../../../data/g01.json";
import stats from "@/data/delta-stats.json";

export const metadata: Metadata = { title: "方法と限界" };

const f = (n: number, d = 3) => n.toFixed(d);
const pct = (n: number, d: number) => `${((n / d) * 100).toFixed(1)}%`;

export default function Houhou() {
  const p = g01.primary;
  const k = g01.kanji_only;
  return (
    <>
      <h1>方法と限界</h1>
      <p className="lede">
        このサイトが何を測り、何を測れなかったかを書く。
        <strong>捨てた主張のほうを先に書く。</strong>
      </p>

      <h2>目玉にするつもりだった主張は、落ちた</h2>
      <p>
        当初の目玉は「δ が小さい箇所は、解析器が薄氷を踏んでいる」だった。
        これを IPADIC の分割で採点したら循環する ── 辞書が自分の自信を自分で採点することになる。
        そこで<strong>青空文庫のルビ</strong>を外部の物差しにした。
        ルビが振られた漢字列は、人間がそこをひとまとまりと見た証拠であり、辞書とは無関係に存在する。
      </p>
      <p>
        <strong>閾値は測る前に決めてある</strong>:
        δ の下位四分位と上位四分位で「ルビの括りを跨いだ境界」の率の比が 1.5 倍以上、
        かつ順位相関が負で α = 0.05。結果は次のとおり。
      </p>

      <div className="scroll">
        <table>
          <thead><tr><th>測ったもの</th><th className="num">値</th><th>閾値</th></tr></thead>
          <tbody>
            <tr>
              <td>境界の数</td>
              <td className="num">{p.n.toLocaleString("ja-JP")}</td>
              <td>—</td>
            </tr>
            <tr>
              <td>Q1(δ 小)の違反率</td>
              <td className="num">{(p.q1_rate * 100).toFixed(3)}%</td>
              <td>—</td>
            </tr>
            <tr>
              <td>Q4(δ 大)の違反率</td>
              <td className="num">{(p.q4_rate * 100).toFixed(3)}%</td>
              <td>—</td>
            </tr>
            <tr>
              <td><strong>Q1 / Q4 の比</strong></td>
              <td className="num" style={{ color: "var(--shu)" }}>
                <strong>{f(p.ratio_q1_over_q4)}</strong>
              </td>
              <td>1.5 以上</td>
            </tr>
            <tr>
              <td>Spearman の順位相関</td>
              <td className="num">{f(p.spearman_rho, 4)}</td>
              <td>負で有意</td>
            </tr>
            <tr>
              <td>δ をシャッフルした対照の経験 p</td>
              <td className="num">{f(p.empirical_p)}</td>
              <td>α = 0.05</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p>
        <strong>向きは正しく、大きさが足りない。</strong>これがいちばん厄介な落ち方で、
        「有意だから効いている」と言いたくなる。経験 p が 0 なのは標本が 40 万あるからで、
        効果の大きさとは別の話である。40 万件あれば 1.19 倍でも「偶然ではない」と言えてしまう。
      </p>

      <h2>交絡を測ったら、効果は消えた</h2>
      <p>
        δ が小さい境界は<strong>漢字の連続の内部に多い</strong>。漢字熟語は辞書に載っているので、
        跨ぐ候補が出るからだ。そしてルビもまた漢字に付く。
        つまり「δ が小さいほどルビを跨ぐ」は、<strong>両方が漢字らしさの関数であるだけ</strong>でも成立しうる。
      </p>
      <div className="scroll">
        <table>
          <thead><tr><th /><th className="num">Q1(δ 小)</th><th className="num">Q4(δ 大)</th></tr></thead>
          <tbody>
            <tr>
              <td>境界が漢字連続の内部にある率</td>
              <td className="num">{pct(p.kanji_run_share_q1, 1)}</td>
              <td className="num">{pct(p.kanji_run_share_q4, 1)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p>
        二倍の開きがある。そこで<strong>漢字連続の内部に限った部分集団</strong>
        ({k.n.toLocaleString("ja-JP")} 境界)で同じ検定をすると、比は{" "}
        <strong style={{ color: "var(--shu)" }}>{f(k.ratio_q1_over_q4)}</strong>、
        順位相関は <strong>{f(k.spearman_rho, 4)}</strong> ──{" "}
        <strong>符号が反転する</strong>。漢字らしさを揃えると、δ が大きい境界のほうがむしろルビを跨ぐ。
        全体で見えた {f(p.ratio_q1_over_q4)} 倍は、漢字らしさの影だったと考えるのが自然である。
      </p>

      <h2>だから、こう決めた</h2>
      <ul>
        <li>δ は出す。ただし<strong>「解析器が迷った量」という内部量</strong>としてのみ提示する</li>
        <li><code>「δ が小さい ⇒ 間違いやすい」</code> とは書かない。<strong>測って、そうならなかった</strong></li>
        <li>当初つけていた <code>「危うい文」</code> というページ名をやめ、<a href="/kinsa/">僅差の文</a>に改めた</li>
        <li>
          同点・僅差が<strong>実在すること</strong>は測れている(
          {stats.boundaries.toLocaleString("ja-JP")} 本中 {stats.zero} 本)。そこは主張として立つ
        </li>
      </ul>

      <h2>途中で物差しを取り替えた</h2>
      <p>
        最初はルビの基底を<strong>自動推定</strong>(直前の同一文字クラスの連続)で取っていた。
        これは青空文庫の記法どおりだが、実例を見ると「処躊躇」「多年斯」のような非語が取れる。
        ルビは 躊躇 / 斯 にだけ付いていて、推定が直前の漢字を巻き込んでいた。
        これを「人間が一語と見た証拠」として使っていたのだから、物差しのほうが壊れていた。
      </p>
      <p>
        そこで <strong>｜ で明示的に括られた基底だけ</strong>を人間の区切りとみなす形に替えた。
        <strong>結果を見てから替えたことは隠さない。</strong>替えた理由は結果と独立で
        (「処躊躇」が語でないことは数字を見なくても分かる)、替えたあと一度だけ測って、それでも落ちた。
        <strong>どちらの物差しでも結論は同じだった</strong>(自動推定版は比 1.057、漢字連続内では 0.503)。
      </p>

      <h2>解析器そのものは、MeCab と一致している</h2>
      <p>
        このサイトの解析器は IPADIC のバイナリだけを読む独立実装で、MeCab の出力を一切参照していない。
        青空文庫 10,000 文で、<strong>総コスト・分割とも 1 件も食い違わない</strong>。
        タイブレーク規則(同点のときどちらに倒すか)を MeCab に合わせて初めて成立するもので、
        規則は最初に見つかった 7 件の同点を見て決めたため、
        <strong>別の種・別の作品 5,000 文で外挿も確かめてある</strong>。
      </p>

      <h2>言えないこと</h2>
      <ul>
        <li>
          <strong>δ は正しさではない。</strong>解析器がどれだけ迷ったかであって、
          人間の判断と一致する保証は無い。上のとおり、測っても出なかった
        </li>
        <li>
          <strong>IPADIC は 2007 年で更新が止まっている。</strong>近年の語は未知語になる。
          それは欠陥ではなく前提である
        </li>
        <li>
          <strong>単位は IPADIC の単位。</strong>UniDic なら「北詰」の扱いも変わる。
          ここで見えるのは日本語ではなく、この辞書の日本語観である
        </li>
        <li>
          <strong>読み・発音は出せない。</strong>辞書の該当部分(30 MB)を配っていないため、
          原理的にできない
        </li>
      </ul>

      <h2>費用</h2>
      <p>
        静的サイトのみ。サーバ側の処理・定期実行・API 鍵は一つも無く、実行時に外へ出る通信も無い。
        入力した文はどこへも送られない。辞書は「刻む」で最初に解析するときだけ取りに行く
        (実測 5.11 MB)。それ以外のページは辞書を 1 バイトも読まない。
      </p>
    </>
  );
}
