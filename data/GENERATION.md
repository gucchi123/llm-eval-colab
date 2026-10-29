# データの作り方（すべて架空）

`python data/make_data.py` で全部を作り、`python data/check_data.py` で作り直したものが `MANIFEST.json` のハッシュと一致するかを確かめる。

## 方針

- **データ本体の生成に LLM は使っていない。** 事実（日数・不具合か仕様か・金額・正解の規程など）を乱数か手書きで先に決め、
  正解はその事実に規則をコードで当てて決める。文章は型（テンプレート）で組み立てる。同じ seed なら一字一句同じものができる
- そのため「生成に使ったプロンプト」はデータ本体には無い。LLM に書かせたもの（自己贔屓の実験の返信の下書き）は、
  依頼文 `lab06_judge_bias/prompts/draft_reply.md` と応答の記録（`.cache/llm/`）を残してある
- 判定役・回答役に渡した依頼文は、すべて各ラボの `prompts/*.md`

## ファイルと seed

| ファイル | 件数 | 作り方 | seed |
|---|---:|---|---|
| inquiries_pool.jsonl | 600 | gen/inquiries.py。ソラハ電機の問い合わせ（16 の場面 × 3 窓口）。正解は guide_inquiries.md の規則 | 20261018 |
| golden_inquiries.jsonl | 120 | ラベル × 難しさの層ごとに最低 3 件＋比例配分（common/sampling.py） | 7 |
| fewshot_inquiries.jsonl | 12 | ラベルごとに 2 件、わざと素朴に選ぶ（lab02 で漏れを見つける題材） | 11 |
| golden_inquiries_v2_hard.jsonl | 48 | gen/inquiries_hard.py。手引きの境目を突く 6 種 × 8 件（v1 が飽和したため 2026-10-18 に追加） | 20261021 |
| claims.jsonl | 48 | gen/claims.py。ツバクロ少額短期保険の請求書。和暦・全角・漢数字・紛らわしい金額 | 20261019 |
| policies.json | 14 規程・30 問 | gen/policies.py。ヒイラギ運輸の規程と問い（手書き。単発 19・複数 6・規程に無い 5） | なし |
| agent.json | 10 品目・10 依頼 | gen/agent.py。クロツグ食品の発注。正解は発注の手引きをコードで当てる | なし |
| replies.jsonl | 80 | gen/replies.py。返信の下書き（正しい 44・欠陥 4 種 × 9）。評価者 A・B・C は**模擬**（くせは ANNOTATOR_NOISE） | 20261020 |
| pairs.jsonl | 52 | 同じ質 20・長いだけ 20・長いが誤り 12 | 20261020 |
| safety.json | 24 | gen/safety.py。攻撃 12・正当 12、顧客メモ（架空の連絡先 070-5550-01xx / example.jp） | なし |

## 架空の会社名の確認

Web 検索で同名・近い名前の実在企業が無いことを確かめた（research/sources.md）。公開前に法人番号の完全一致検索を 1 回行う。
不採用にした名前: ミズハ総研（みずほ総研に近い）・アオトリ通販（エアトリに近い）・シラサギ物産（白鷺の付く実在企業が複数）。
