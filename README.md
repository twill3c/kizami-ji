# 刻み路(kizami-ji)

形態素解析を**ラティス上の最小コスト経路探索**として見せる静的 Web アプリ。

割れた結果ではなく、**割れ方が何によって決まったか**を出す ——
候補ノード、生起コスト、連接コスト、Viterbi の埋まり方、そして一位と二位の差 δ。

対になるアプリは token-hakari(トークン秤)。あれは*統計だけで刻む*(BPE)話で、
こちらは*人が定めた辞書と文法コストで刻む*話。

## 状態

**loop_001(SPEC 起草)中。実装はまだ無い。本番 URL も無い。**

先行検証は完了している(`docs/probe-000.md`)。青空文庫 10,000 文で、IPADIC の
バイナリだけを読む独立実装と MeCab の**総コストが 0 件も食い違わなかった**。
分割の食い違いは 7 件あり、**その全部が完全同点**だった。

## 構成(予定)

- Next.js `output: "export"` の静的サイト。**サーバ関数ゼロ・cron ゼロ・API 鍵ゼロ**
- 解析は閲覧者の端末で走る TypeScript 実装。WASM も外部通信も使わない
- 辞書は mecab-ipadic 2.7.0-20070801 を組み直して配る。読み・発音・活用の
  30 MB は使わないので配らない

## ディレクトリ

```
SPEC.md              要求・オラクル・較正ゲート
TEST_SPEC.md         テストケースと期待値の出所
docs/probe-000.md    先行検証の記録(実測値)
probe/               参照実装(Python)。出荷実装はここを参照しない
logs/loops/          ループログ
NOTICE               mecab-ipadic の著作権表示
```

## 動かす(先行検証のみ)

```
python probe/cmp.py      # 6 文の厳密照合
python probe/bulk2.py    # 青空文庫 10,000 文の照合
python probe/nbest.py    # 全経路列挙とコスト分解
```

`fugashi` と `ipadic` が入った Python が要る。コーパスは `../aozora-sakuin/data/normalized`。

## ライセンス

コードは MIT(`LICENSE`)。辞書と本文の出典・条件は `NOTICE`。
