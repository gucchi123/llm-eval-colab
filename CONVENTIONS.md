# ラボ実装の決まり（評価講座）

LangGraph 講座・GraphRAG 講座のキットと同じ約束。違うのは、フレームワークを使わず素の Anthropic SDK で書くこと（評価の考え方を見えやすくするため）。

## 1. フォルダの形

```
labNN_<英小文字の名前>/
  README.md        手順（コマンドの例を 3〜6 個）
  run_<名前>.py    実行の入口。common.kit.parser() で --provider / --model / --effort / --limit / --all / --only / --workers
  prompts/*.md     LLM に渡す依頼文は必ずファイルに置く（台本・スライドで見せる・版を管理する）
  tests/test_labNN.py  模擬だけで通る pytest（API キー無し・記録無しで動くこと。ファイル名はラボごとに一意）
  RUN_NOTES.md     講師が本物の実行を見て書いた「読み取れること」（勝たなかった・飽和した結果も書く）
  RUN_LOG.md       tools/capture_runlogs.py が作る（本物の実行の出力を記録の再生で写したもの＋台帳の費用）
  out/             講師の本物の実行（anthropic / replay）。out_mock/ は模擬（配布しない）
```

- 共通部品は `common/`。他のラボのコードを import しない（他のラボの `out/` を読むのはよい: lab08・lab09・lab12）
- データは `common.kit.load_*()` で読む。`data/` を直接書き換えない（直すなら `data/gen/*.py` を直して `make_data.py && check_data.py`）

## 2. モデルの呼び方

- `common.llm.call()` / `call_json()` / `chat()`（道具つき）だけを使う。SDK を直接呼ばない（記録・台帳・予算が効かなくなる）
- 既定は `claude-opus-5-5`・effort high（output_config で渡す。Opus 5.5 の既定は medium なので明示する）。比較は `--model claude-sonnet-5-5`
- 台帳の印は `with L.tag("labNN/<実験>/<モデル>")`
- 模擬の筋書き（`L.mock_handler(fn)`）を必ず用意する。🔴 模擬の数字は性能の証拠にしない（RUN_LOG・台本・LP に書かない）
- 同じ依頼を何度も試す（揺れ・pass^k）ときは `trial=` を使う（API には送らず記録の鍵だけを変える）
- 予算切れ（BudgetExceeded）・記録なし（CacheMiss）を「無効な出力」として握りつぶさない

## 3. 本物のモデルで回す

1. 模擬で pytest が通ってから、`--provider anthropic` で回す（キーは環境変数・Windows のユーザー環境変数から読む。表示しない）
2. `--provider replay` で同じ数字が出ることを確かめる（`tests/test_replay.py`）
3. `RUN_NOTES.md` を書き、`python tools/capture_runlogs.py` で RUN_LOG を作り直す
4. 予算: 既定 5 USD（受講者向け）。講師の実行は 2026-10-18 に前半 4.79 USD、ユーザー承認で上限 12 USD に上げて後半 5.63 USD、計 10.42 USD。判定役・模擬の判定者は Sonnet にして費用を下げた
5. 模擬の判定者（LLM に人物像を与えたもの）の一致を「人の κ」と呼ばない

## 4. してはいけないこと

- キーをコード・ログ・RUN_LOG に書く／表示する
- 実在の会社・人物・勤務先の話を入れる（架空の 4 社だけ）
- 模擬の数字を性能として語る / 回していないモデルの結果を書く
- 公開・アップロード（ユーザー確認の後）
