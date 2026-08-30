"use client";

import { useCallback, useMemo, useState } from "react";

import LatticeView from "@/components/LatticeView";
import { EXAMPLES } from "@/data/site";
import { Analyzer } from "@/lib/analyze";
import { getDict } from "@/lib/browserDict";
import {
  buildLattice, figureFromLattice, secondPath, INF,
  type Lattice, type LatticeNode,
} from "@/lib/lattice";

const MAX_LATTICE_CHARS = 40;

export default function Kizamu() {
  const [text, setText] = useState(EXAMPLES[0].text);
  const [analyzer, setAnalyzer] = useState<Analyzer | null>(null);
  const [bytes, setBytes] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lattice, setLattice] = useState<Lattice | null>(null);
  const [second, setSecond] = useState<{ delta: number; nodes: LatticeNode[] } | null>(null);
  const [upto, setUpto] = useState<number | null>(null);
  const [progress, setProgress] = useState("");

  const run = useCallback(
    async (input: string) => {
      setError(null);
      setBusy(true);
      try {
        let a = analyzer;
        if (a === null) {
          const { dict, bytes: got } = await getDict((p) =>
            setProgress(`辞書を読み込み中 ${p.loaded} / ${p.total}`),
          );
          a = new Analyzer(dict);
          setAnalyzer(a);
          setBytes(got);
          setProgress("");
        }
        const l = buildLattice(a, input);
        if (l === null) {
          setLattice(null);
          setSecond(null);
          setError("経路が組めなかった。文字が空か、扱えない文字が含まれている。");
          return;
        }
        setLattice(l);
        setSecond(secondPath(l));
        setUpto(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [analyzer],
  );

  const chars = useMemo(() => (lattice ? [...lattice.text].length : 0), [lattice]);
  const tooLong = chars > MAX_LATTICE_CHARS;

  return (
    <>
      <h1>刻む</h1>
      <p className="lede">
        入力した文からラティスを組み、最小コスト経路を選ぶ。候補も、コストの内訳も、
        二位との差も出す。<strong>解析は全部この画面の中で走る</strong>ので、
        入力した文はどこへも送られない。
      </p>

      <div className="form">
        <label htmlFor="src" className="meter">解析する文</label>
        <textarea
          id="src"
          value={text}
          onChange={(e) => setText(e.target.value)}
          spellCheck={false}
          placeholder="日本語の文を入れる"
        />
        <div className="form__row">
          <button type="button" onClick={() => void run(text)} disabled={busy || text.trim() === ""}>
            {busy ? "解析中…" : "刻む"}
          </button>
          {analyzer === null ? (
            <span className="meter">{progress || "初回は辞書を読み込む(12.9 MB・圧縮転送)"}</span>
          ) : (
            <span className="meter">
              辞書は読み込み済み ── <b>{(bytes / 1048576).toFixed(2)} MB</b> を受け取った(実測)
            </span>
          )}
        </div>
        <ul className="examples">
          {EXAMPLES.map((e) => (
            <li key={e.text}>
              <button type="button" title={e.note} onClick={() => { setText(e.text); void run(e.text); }}>
                {e.text.length > 14 ? `${e.text.slice(0, 14)}…` : e.text}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {error !== null && (
        <div className="note" style={{ borderLeftColor: "var(--shu)" }}>
          <span className="note__label" style={{ color: "var(--shu)" }}>解析できなかった</span>
          <p>{error}</p>
        </div>
      )}

      {lattice !== null && (
        <>
          <section className="panel">
            <h3>刻んだ結果</h3>
            <ul className="words">
              {lattice.path.map((n, i) => (
                <li key={`${n.start}-${i}`} className={`word${n.unknown ? " is-unknown" : ""}`}>
                  <span className="word__surface">{n.surface}</span>
                  <span className="word__pos">{n.unknown ? "未知語" : n.pos[0]}</span>
                </li>
              ))}
            </ul>
            <p className="legend">
              <span><span className="swatch swatch--plain" />辞書にある語</span>
              <span><span className="swatch swatch--shu" />辞書に無い語(文字種の規則で作った)</span>
            </p>
          </section>

          <section className="panel">
            <h3>コストの内訳</h3>
            <dl className="ledger">
              <dt>Σ 生起コスト(語そのものの値段)</dt>
              <dd>{lattice.breakdown.emission.toLocaleString("ja-JP")}</dd>
              <dt>Σ 連接コスト(品詞の並びやすさ)</dt>
              <dd>{lattice.breakdown.connection.toLocaleString("ja-JP")}</dd>
              <dt>EOS へ</dt>
              <dd>{lattice.breakdown.eos.toLocaleString("ja-JP")}</dd>
              <div className="total" style={{ display: "contents" }}>
                <dt>総コスト</dt>
                <dd>{lattice.cost.toLocaleString("ja-JP")}</dd>
              </div>
            </dl>
          </section>

          <section className="panel">
            <h3>ラティスと道</h3>
            {tooLong ? (
              <p className="meter">
                {chars} 文字。図は {MAX_LATTICE_CHARS} 文字までしか描かない(読めなくなるため)。
                下の表と内訳はそのまま使える。
              </p>
            ) : (
              <>
                <LatticeView figure={figureFromLattice(lattice, second?.nodes ?? null)} upto={upto} />
                <p className="legend">
                  <span><span className="swatch swatch--ai" />最小経路</span>
                  <span><span className="swatch swatch--shu" />二位の道(分割が異なる最良)</span>
                  <span><b>破線の枠</b> 未知語</span>
                  <span><b>δ</b> その境界で切らずに済ませたときの追加コスト</span>
                </p>
                <div className="form__row" style={{ marginTop: "0.7rem" }}>
                  <label htmlFor="dp" className="meter">DP の進み</label>
                  <input
                    id="dp"
                    type="range"
                    min={0}
                    max={chars}
                    value={upto === null ? chars : upto}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setUpto(v >= chars ? null : v);
                    }}
                  />
                  <span className="meter">
                    {upto === null ? `${chars} 文字目まで(全部)` : `${upto} 文字目まで`}
                  </span>
                </div>
              </>
            )}
          </section>

          <section className="panel">
            <h3>境界ごとの δ</h3>
            <p className="meter" style={{ marginBottom: "0.6rem" }}>
              δ は「その境界で切らずに済ませる道を選んだとき、総コストがいくら増えるか」。
              δ = 0 は同じ値の道が並んでいることを、∞ はその境界を跨ぐ語が辞書に一つも無いことを意味する。
              <strong>これは解析器が迷った量であって、正しさとは結びついていない</strong>
              (測った結果は「方法と限界」に書いた)。
            </p>
            <div className="scroll">
              <table id="delta-table">
                <thead>
                  <tr><th>境界</th><th className="tight">直前 / 直後</th><th className="num">δ</th></tr>
                </thead>
                <tbody>
                  {lattice.boundaries.map((b, i) => (
                    <tr key={b.at}>
                      <td className="num">{b.charAt}</td>
                      <td className="tight">
                        {lattice.path[i].surface} ／ {lattice.path[i + 1].surface}
                      </td>
                      <td className="num" style={{ color: b.delta === 0 ? "var(--shu)" : undefined }}>
                        {b.delta === INF ? "∞" : b.delta.toLocaleString("ja-JP")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {second !== null && (
              <p style={{ marginTop: "0.8rem" }}>
                二位の道は <strong>{second.nodes.map((n) => n.surface).join(" / ")}</strong>{" "}
                で、総コストの差は <strong>{second.delta.toLocaleString("ja-JP")}</strong>。
                {second.delta === 0 && "── 完全同点である。どちらが出るかは辞書の走査順で決まっている。"}
              </p>
            )}
          </section>

          <section className="panel">
            <h3>候補ノード</h3>
            <p className="meter" style={{ marginBottom: "0.6rem" }}>
              {lattice.nodes.length} 個。最小経路に選ばれたものだけを太字にした。
            </p>
            <div className="scroll">
              <table id="node-table">
                <thead>
                  <tr>
                    <th className="tight">表層</th><th className="tight">品詞</th><th className="num">生起</th>
                    <th className="num">左文脈</th><th className="num">右文脈</th>
                    <th className="num">通ったときの総コスト</th>
                  </tr>
                </thead>
                <tbody>
                  {lattice.nodes.slice(0, 200).map((n) => {
                    const on = lattice.best.includes(n.id);
                    const through = n.fwd === INF || n.bwd === INF ? INF : n.fwd + n.bwd;
                    return (
                      <tr key={n.id} style={{ fontWeight: on ? 600 : 400 }}>
                        <td className="tight">{n.surface}</td>
                        <td className="tight">{n.unknown ? "未知語" : n.token.posId >= 0 ? posName(lattice, n) : "—"}</td>
                        <td className="num">{n.token.cost.toLocaleString("ja-JP")}</td>
                        <td className="num">{n.token.lc}</td>
                        <td className="num">{n.token.rc}</td>
                        <td className="num">{through === INF ? "—" : through.toLocaleString("ja-JP")}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {lattice.nodes.length > 200 && (
              <p className="meter">先頭 200 個だけを表に出した(残り {lattice.nodes.length - 200} 個)。</p>
            )}
          </section>
        </>
      )}
    </>
  );
}

function posName(l: Lattice, n: LatticeNode): string {
  const p = l.dict.pos(n.token.posId);
  return p ? p.filter((x) => x !== "*").join("・") : "—";
}
