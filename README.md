# 刻み路(kizami-ji)

形態素解析を**ラティス上の最小コスト経路探索**として見せる静的 Web アプリ。

割れた結果ではなく、**割れ方が何によって決まったか**を出す ——
候補ノード、生起コスト、連接コスト、Viterbi の埋まり方、そして一位と二位の差 δ。

対になるアプリは token-hakari(トークン秤)。あれは*統計だけで刻む*(BPE)話で、
こちらは*人が定めた辞書と文法コストで刻む*話。

## 状態

**loop_003 完了。TypeScript の出荷実装まで。画面と本番 URL はまだ無い。**

出荷用に組み直した辞書だけを読む解析器が、青空文庫 10,000 文で MeCab と
**総コスト・分割とも 1 件も食い違わない**(O-1a / O-1b)。タイブレーク規則を
合わせたのは最初に見つかった 7 件の同点を見てのことなので、**別の種・別の作品
5,000 文で外挿も確かめてある**。

TypeScript 実装も同じ 10,000 文で不一致 0 件(**1,340 ms / 1 文あたり 0.13 ms**)。
辞書は生 12.89 MB / gzip 4.27 MB。G-03 の上限 8 MB に対して余裕がある
(ただし実ブラウザでの実測はまだ)。

## 構成(予定)

- Next.js `output: "export"` の静的サイト。**サーバ関数ゼロ・cron ゼロ・API 鍵ゼロ**
- 解析は閲覧者の端末で走る TypeScript 実装。WASM も外部通信も使わない
- 辞書は mecab-ipadic 2.7.0-20070801 を組み直して配る。読み・発音・活用の
  30 MB は使わないので配らない

## ディレクトリ

```
SPEC.md              要求・オラクル・較正ゲート
TEST_SPEC.md         テストケースと期待値の出所
scripts/build_dict.py  IPADIC を出荷用の形式へ組み直す
scripts/shipdict.py    出荷用辞書の読み取り(ipadic を import しない)
scripts/analyze.py     Viterbi。data/dict だけで動く
scripts/check_agreement.py  MeCab との照合(検査専用)
data/dict/           組み直した辞書(生 12.89 MB)
tests/               T-001〜T-004 / T-010〜T-013 / T-020
docs/probe-000.md    先行検証の記録(実測値)
probe/               先行検証のコード。原本の double-array を直接読む
logs/loops/          ループログ
NOTICE               mecab-ipadic の著作権表示
```

## 動かす

```
python scripts/build_dict.py              # IPADIC → data/dict(数分)
python scripts/analyze.py "の北詰まで"     # 解析してみる
python scripts/check_agreement.py --n 10000   # MeCab と照合(約 16 秒)
pytest -q                                  # 全テスト
```

`fugashi` と `ipadic` が入った Python が要る(`.venv` を同梱の手順で作る)。
コーパスは `../aozora-sakuin/data/normalized` を参照する(再取得しない)。

## ライセンス

コードは MIT(`LICENSE`)。辞書と本文の出典・条件は `NOTICE`。
