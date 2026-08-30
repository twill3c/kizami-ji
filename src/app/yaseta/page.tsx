import type { Metadata } from "next";

import thin from "@/data/thin-dict.json";

export const metadata: Metadata = { title: "痩せた辞書" };

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

interface Row {
  keep: number;
  kind: string;
  f1: number;
  exact: number;
  unknown_share: number;
  tokens_per_sentence: number;
  inf_share: number | null;
  mean_cost: number;
  dict_tokens: number;
  tokens: number;
}

export default function Yaseta() {
  const rows = thin.rows as Row[];
  const controls = thin.controls as Row[];
  const zero = thin.zero_f1;
  const top1000 = rows.find((r) => r.keep === 1000)!;
  const rnd1000 = controls.find((c) => c.keep === 1000)!;
  const maxF1 = Math.max(...rows.map((r) => r.f1));

  return (
    <>
      <h1>痩せた辞書</h1>
      <p className="lede">
        辞書から語を減らしていくと、解析はどう崩れるか。
        {thin.freq_sentences.toLocaleString("ja-JP")} 文で語の頻度を数え、
        上位だけを残した辞書を作って、<strong>別の {thin.eval_sentences.toLocaleString("ja-JP")} 文</strong>で測った。
      </p>

      <div className="note">
        <span className="note__label">この数が意味しないこと</span>
        <p>
          下の「境界の一致」は<strong>完全辞書との一致度</strong>であって、正しさではない。
          人手の正解とは照合していない。<strong>完全辞書自身が正しいとも限らない</strong> ——
          三つめの例で、完全辞書は <code>學生</code> を <code>學 / 生</code> に割る
          (旧字の <code>學生</code> を持っていないため)。語を 300 まで捨てた辞書のほうが、
          未知語の規則で <code>學生</code> を一語に保っている。
        </p>
      </div>

      <h2>語数ではなく、どの語を持つかが効く</h2>
      <p>
        辞書を<strong>まったく持たない</strong>解析器でも、境界の一致は {zero.toFixed(3)} ある。
        未知語の作り方(文字種が変わるところで切る)だけで、そこまで行く。
        では語を足せば上がるのか —— <strong>足す語による</strong>。
      </p>

      <div className="scroll">
        <table>
          <caption>
            無作為に選んだ語は、辞書に入れても入れなくても変わらない。
            使われていないのではなく、実際に使われたうえで効かない。
          </caption>
          <thead>
            <tr><th>辞書</th><th className="num">境界の一致</th><th className="num">辞書語として使われた</th></tr>
          </thead>
          <tbody>
            <tr>
              <td className="tight">辞書ゼロ(文字種の規則だけ)</td>
              <td className="num">{zero.toFixed(4)}</td>
              <td className="num">—</td>
            </tr>
            {controls.map((c) => (
              <tr key={`r${c.keep}`}>
                <td className="tight">無作為に {c.keep.toLocaleString("ja-JP")} 語</td>
                <td className="num">{c.f1.toFixed(4)}</td>
                <td className="num">
                  {c.dict_tokens.toLocaleString("ja-JP")} / {c.tokens.toLocaleString("ja-JP")}
                </td>
              </tr>
            ))}
            <tr style={{ background: "var(--ai-w)" }}>
              <td className="tight"><strong>頻度上位 {top1000.keep.toLocaleString("ja-JP")} 語</strong></td>
              <td className="num"><strong>{top1000.f1.toFixed(4)}</strong></td>
              <td className="num">
                {top1000.dict_tokens.toLocaleString("ja-JP")} / {top1000.tokens.toLocaleString("ja-JP")}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p>
        無作為に選んだ 1,000 語は、<strong>使われてはいる</strong>
        ({rnd1000.dict_tokens.toLocaleString("ja-JP")} トークン)。
        それでも一致は {rnd1000.f1.toFixed(4)} で、辞書ゼロの {zero.toFixed(4)} と
        <strong>差が {Math.abs(rnd1000.f1 - zero).toFixed(4)}</strong> しかない。
        同じ 1,000 語でも、頻度で選べば {top1000.f1.toFixed(4)} ——
        <strong>{(top1000.f1 - zero).toFixed(3)} 上がる</strong>。
      </p>
      <p className="meter">
        頻度上位から順に: {thin.top_words.join(" ")} …… 助詞と句読点である。
      </p>

      <h2>減らしていくと</h2>
      <div className="scroll">
        <table>
          <caption>
            辞書 {thin.surface_total.toLocaleString("ja-JP")} 種のうち、
            {thin.freq_sentences.toLocaleString("ja-JP")} 文で実際に選ばれたのは
            {thin.surface_used.toLocaleString("ja-JP")} 種({pct(thin.surface_used / thin.surface_total)})だけだった。
          </caption>
          <thead>
            <tr>
              <th className="num">語数</th><th className="num">境界の一致</th>
              <th className="num">文まるごと一致</th><th className="num">未知語率</th>
              <th className="num">δ = ∞</th><th className="num">平均コスト</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.keep}>
                <td className="num">{r.keep === 0 ? "0" : r.keep.toLocaleString("ja-JP")}</td>
                <td className="num">
                  <span
                    style={{
                      display: "inline-block", height: "0.6rem", marginRight: "0.4rem",
                      width: `${Math.max(2, ((r.f1 - 0.7) / (maxF1 - 0.7)) * 44)}px`,
                      background: "var(--ai)", borderRadius: "2px", verticalAlign: "middle",
                    }}
                  />
                  {r.f1.toFixed(3)}
                </td>
                <td className="num">{pct(r.exact)}</td>
                <td className="num">{pct(r.unknown_share)}</td>
                <td className="num">{r.inf_share === null ? "—" : pct(r.inf_share)}</td>
                <td className="num">{r.mean_cost.toLocaleString("ja-JP")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p>
        <strong>境界と「文まるごと」で崩れ方がまるで違う。</strong>
        語数を {rows[0].keep.toLocaleString("ja-JP")} から 1,000 へ落としても境界の一致は
        {rows[0].f1.toFixed(3)} → {top1000.f1.toFixed(3)} としか下がらないのに、
        文がまるごと一致する率は {pct(rows[0].exact)} → {pct(top1000.exact)} に落ちる。
        1 文あたり 20 個以上ある境界のどれか一つが動けば、文としては不一致になるからだ。
      </p>
      <p>
        そして<strong>平均コストは膨れ上がる</strong>
        ({rows[0].mean_cost.toLocaleString("ja-JP")} → {rows[rows.length - 1].mean_cost.toLocaleString("ja-JP")})。
        語彙が無いぶん、解析器は高い道を通るしかない。
        δ = ∞ の割合も上がる —— 跨ぐ語がますます無くなる。
      </p>

      <h2>同じ文が崩れていく</h2>
      <p className="meter">
        いちばん上が完全辞書({thin.surface_total.toLocaleString("ja-JP")} 種)。
        以下は頻度上位から残した語数。<span style={{ color: "var(--shu)" }}>朱</span>は未知語。
      </p>

      {thin.showcase.map((sc) => (
        <section className="panel" key={sc.text}>
          <h3 style={{ fontFamily: "var(--serif)", fontWeight: 400 }}>{sc.text}</h3>
          <div className="scroll">
            <table>
              <thead>
                <tr><th className="num">語数</th><th>分割</th><th className="num">コスト</th></tr>
              </thead>
              <tbody>
                {sc.steps.map((st) => (
                  <tr key={st.keep} style={st.full ? { background: "var(--ai-w)" } : undefined}>
                    <td className="num tight">
                      {st.full ? "完全辞書" : st.keep === 0 ? "0" : st.keep.toLocaleString("ja-JP")}
                    </td>
                    <td style={{ fontFamily: "var(--serif)" }}>
                      {st.words.map((w, i) => (
                        <span key={`${w}-${i}`}>
                          {i > 0 && <span style={{ color: "var(--line)" }}> / </span>}
                          <span style={st.unknown[i] ? { color: "var(--shu)" } : undefined}>{w}</span>
                        </span>
                      ))}
                    </td>
                    <td className="num">{st.cost.toLocaleString("ja-JP")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      <div className="note caution">
        <span className="note__label" style={{ color: "var(--shu)" }}>減らすと直ることがある</span>
        <p>
          二つめの例で <code>首都</code> を追うと、完全辞書は一語に保つのに、
          {(3000).toLocaleString("ja-JP")} 語まで刈ると <code>首 / 都</code> に割れ、
          さらに 300 語まで刈ると<strong>また一語に戻る</strong>。
          途中の辞書は <code>首</code> と <code>都</code> を持っていて、
          それを繋いだ道のほうが安かった。語彙を失った辞書はその選択肢ごと失い、
          未知語の規則(漢字は 2 字でまとめる)が代わりに拾っている。
          <strong>単調に悪くなるわけではない。</strong>
        </p>
      </div>

      <h2>測り方</h2>
      <ul>
        <li>
          <strong>頻度を取る文と、測る文を分けた。</strong>同じ文で頻度を取って同じ文で測れば
          「使った語は残る」ので、何も分からない。A 群 {thin.freq_sentences.toLocaleString("ja-JP")} 文と
          B 群 {thin.eval_sentences.toLocaleString("ja-JP")} 文は互いに素で、重なりが無いことを毎回検算している
        </li>
        <li>
          刈るのは<strong>語彙だけ</strong>。連接表・文字種の規則・未知語の定義はそのまま。
          変えた条件を一つに絞らないと、何が効いたか分からない
        </li>
        <li>
          <strong>対照を二つ置いた。</strong>辞書ゼロ(下限)と、無作為に同数を残した辞書。
          無作為の語が実際に使われていることも確かめてある —— 使われずに効かないのでは対照にならない
        </li>
        <li>
          この表は事前に焼いてある。<strong>刈った辞書は配っていない</strong>ので、
          このページは辞書を 1 バイトも読み込まない
        </li>
        <li>乱数種 {thin.seed}、6〜80 字の文。コーパスは青空文庫({thin.corpus})</li>
      </ul>
    </>
  );
}
