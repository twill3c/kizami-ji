import type { Metadata } from "next";

import stats from "@/data/delta-stats.json";

export const metadata: Metadata = { title: "僅差の文" };

const pct = (n: number, d: number) => `${((n / d) * 100).toFixed(1)}%`;

export default function Kinsa() {
  const max = Math.max(...stats.histogram.map((h) => h.count));
  return (
    <>
      <h1>僅差の文</h1>
      <p className="lede">
        青空文庫の <strong>{stats.sentences.toLocaleString("ja-JP")} 文</strong>を刻み、
        引かれた <strong>{stats.boundaries.toLocaleString("ja-JP")} 本</strong>の境界すべてについて
        δ を測った。δ は「その境界で切らずに済ませる道を選んだとき、総コストがいくら増えるか」である。
      </p>

      <div className="note">
        <span className="note__label">δ が意味しないこと</span>
        <p>
          δ が小さいことと、分割が誤っていることは<strong>結びついていない</strong>。
          外部の物差し(青空文庫のルビ)で測ったが、関係は閾値に届かず、
          漢字の連続に限ると符号が反転した。<a href="/houhou/">方法と限界</a>に顛末を書いた。
          ここに出すのは<strong>解析器が迷った量</strong>の分布であって、正しさの分布ではない。
        </p>
      </div>

      <h2>大半の境界は、迷っていない</h2>
      <div className="scroll">
        <table>
          <thead><tr><th>δ</th><th className="num">境界</th><th>割合</th></tr></thead>
          <tbody>
            {stats.histogram.map((h) => (
              <tr key={h.label}>
                <td>{h.label}</td>
                <td className="num">{h.count.toLocaleString("ja-JP")}</td>
                <td>
                  <span
                    style={{
                      display: "inline-block",
                      height: "0.65rem",
                      width: `${Math.max(1, (h.count / max) * 100)}%`,
                      background: h.label === "0" ? "var(--shu)" : "var(--ai)",
                      borderRadius: "2px",
                      verticalAlign: "middle",
                    }}
                  />
                  <span className="meter" style={{ marginLeft: "0.5rem" }}>
                    {pct(h.count, stats.boundaries)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p>
        <strong>{pct(stats.infinite, stats.boundaries)}</strong> は δ = ∞ —— その境界を跨ぐ語が
        辞書に一つも無い。境界は「解析器が切ることを選んだ場所」にしか存在しないので、
        跨ぐ語があって安ければ、そもそも境界は引かれない。つまり<strong>分割の大半は、
        迷った末の判断ではなく、語彙がそこにしか道を残していないという事実の反映</strong>である。
      </p>

      <h2>完全同点は、実在する</h2>
      <p>
        δ = 0 の境界は <strong>{stats.zero} 本</strong>
        ({stats.boundaries.toLocaleString("ja-JP")} 本中)、
        含む文は <strong>{stats.sentences_with_tie} 文</strong>
        ({stats.sentences.toLocaleString("ja-JP")} 文中)。おおよそ<strong>千文に一つ</strong>である。
        そこでは二つの分割が同じ総コストで並んでいて、どちらが出るかは
        <strong>辞書の走査順</strong>で決まっている ── モデルではなく、実装の都合で決まっている。
      </p>
      <p className="meter">
        以下は実際に見つかった {stats.ties.length} 通り。作例ではなく、すべて青空文庫の本文から出た。
      </p>

      <div className="scroll">
        <table>
          <thead>
            <tr><th>切った側</th><th>繋げた側</th><th>出どころ</th></tr>
          </thead>
          <tbody>
            {stats.ties.map((t, i) => (
              <tr key={`${t.left}-${t.right}-${i}`}>
                <td style={{ fontFamily: "var(--serif)" }}>
                  {t.left} <span style={{ color: "var(--shu)" }}>|</span> {t.right}
                </td>
                <td style={{ fontFamily: "var(--serif)" }}>{t.joined}</td>
                <td className="meter">{t.text.length > 40 ? `${t.text.slice(0, 40)}…` : t.text}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>測り方</h2>
      <ul>
        <li>コーパスは青空文庫({stats.corpus})。乱数種 {stats.seed}、6〜80 字の文</li>
        <li>δ_local(p) = (p をまたぐノードを含む最良経路のコスト) − (最小コスト)</li>
        <li>「二位」は<strong>分割が異なる</strong>経路に限る。同じ分割で同表層の別トークンを選んだだけの道は数えない</li>
        <li>この表は事前に焼いてある。このページは辞書を読み込まない</li>
      </ul>
    </>
  );
}
