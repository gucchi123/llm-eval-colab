# LLM・エージェントの評価 ― ラボ一式

> **この教材に登場する会社・人物・製品・数値・文書はすべて架空のものです。実在の企業・団体・個人とは関係ありません。**
> 架空の会社: ソラハ電機（サポート窓口）/ ツバクロ少額短期保険（請求書）/ ヒイラギ運輸（社内規程）/ クロツグ食品（発注）

講座「LLM・エージェントの評価 ― 何を測り、どう自動化し、どこで人が見るか」で使うラボです。
分類・抽出・RAG・エージェント・LLM 判定・安全性を、**件数と区間つきで**測り、変更を通すかを関門（CI ゲート）で決め、
本番での見張りと「人が見るところ」までを、実際に動かしながら扱います。

## 動かし方

### Google Colab（いちばん手軽）

1. [DEMOS.md](DEMOS.md) の表から開きたいノートブックを選ぶ（`https://colab.research.google.com/github/gucchi123/llm-eval-colab/blob/main/notebooks/<名前>.ipynb`）
2. 上から順に実行する。0-1 のセルがこのリポジトリを `/content/llm-eval-kit` に取得し、`anthropic` を入れて、そこに移ります
3. 本物のモデルで動かすときだけ、左の鍵のアイコン（シークレット）に `ANTHROPIC_API_KEY` を登録し、ノートブックからのアクセスを許可する。キーが無ければ講師の記録を再生します（費用 0）

### 手元の Jupyter / コマンド

- Python 3.11 以上（Windows 11 ARM64 / Python 3.13.14 で確認）
- Windows では、深いフォルダに置くと `pip install` が「パスが長すぎる」で失敗することがあります（anthropic のファイル名が長いため）。`C:\work\llm-eval-kit` のような浅い場所に置いてください
- `python -m venv .venv` → `.venv/Scripts/python -m pip install -r requirements.txt`（anthropic と pytest だけ。統計は標準ライブラリで自作）。macOS / Linux は `.venv/bin/python`
- ノートブックは `notebooks/` から開きます（`python -m pip install jupyter` → `jupyter notebook notebooks/`）
- 各ラボはそのフォルダに入ってから実行します（`cd lab03_classify_extract && python run_classify.py`）

## 🔴 API キーは各自で用意する

- 本物のモデル（Anthropic の Claude）で動かすには、**ご自身で用意した API キー**が必要です。キーはコードに書かず、環境変数 `ANTHROPIC_API_KEY` に置いてください。
- キットはキーを画面にもファイルにも出しません（記録・台帳・例外の文にも入りません）。
- キーが無くても、模擬（mock）で最後まで動きます。講師の実行記録（`.cache/llm/`）があれば、それを再生（replay）して本物の実行と同じ数字を出せます（費用 0）。

## AI の呼び先を切り替える

| provider | 必要なもの | 中身 |
|---|---|---|
| `mock`（既定） | なし | 決まった筋書きで答える模擬。自己検査で使う。🔴 **数字は性能の証拠にならない**（出力は `out_mock/`） |
| `replay` | `.cache/llm/`（講師の記録・同梱） | 講師が API で回した応答（1,646 件）を再生。費用 0・キー不要。出力は本物の実行と同じ（`out/`）。RESULTS.md の数字はすべてこれで再現できる |
| `anthropic` | `ANTHROPIC_API_KEY` | 本物の Claude。同じ依頼の記録があればそれを返す（費用 0） |

- モデルは `--model`（既定 `claude-opus-5-5`）。**Sonnet と Opus を比べる**ときは `--model claude-sonnet-5-5`。考える深さは `--effort`（既定 high）
- 費用は呼ぶたびに `_api_cost_ledger.jsonl` に 1 行残り、合計が `LLM_BUDGET_USD`（既定 5）に近づくと止まります（講師の実行は全部で 10.42 USD。後半は上限を 12 にして実行）
- `LLM_CACHE_ONLY=1` なら、記録に無い依頼は API を呼ばずに止まります（費用が絶対に出ない）
- 予算切れ・記録なしは「モデルの無効な出力」に数えずに止まります（lab09 の RUN_LOG に、取り違えた実例があります）

## ラボと講座のパート

| P | 題 | ラボ | LLM |
|---|---|---|---|
| 2 | 何を測るか・ゴールデンセット | `lab02_golden_set`（層別の抜き取り・重み・件数と幅・漏れ・データカード） | なし |
| 3 | 分類・抽出の指標 | `lab03_classify_extract`（混同行列・マクロ F1・ECE・strict/normalized） | あり |
| 4 | RAG の評価 | `lab04_rag_eval`（recall@k・MRR・nDCG・要素の照合・断る率・忠実さ） | あり |
| 5 | エージェントと軌跡 | `lab05_agent_trajectory`（結果と軌跡・pass@k / pass^k・道具の数） | あり |
| 6 | LLM 判定と偏り | `lab06_judge_bias`（位置・長さ・自己贔屓） | あり |
| 7 | 判定を人に合わせる | `lab07_judge_calibration`（TPR/TNR・κ・dev/test・Rogan-Gladen・模擬の判定者 4 人とガイドラインの改訂・裁定） | あり |
| 8 | 差は本物か | `lab08_stats`（Wilson・McNemar・対のブートストラップ・塊の SE・必要な件数・Holm） | なし |
| 9 | 回帰の関門 | `lab09_ci_gate`（非劣性・層の床・CI で止める） | あり |
| 10 | 本番での評価 | `lab10_online_eval`（シャドー・カナリアと SRM・ずれ・抜き取り・費用と待ち時間） | なし |
| 11 | 安全性の評価 | `lab11_safety`（漏えいと止めすぎの両側） | あり |
| 12 | 業務ユースケース | `lab12_usecases`（5 本の評価カード） | なし |

各ラボに `README.md`（手順）・`RUN_LOG.md`（講師の本物の実行の出力・日時・費用）・`tests/`（模擬で通る自己検査）・`out/`（講師の実行結果）があります。
全体のまとめは `RESULTS.md`。

## 自己検査

```bash
.venv/Scripts/python -m pytest              # 全ラボ（模擬・キーなし。記録があれば再生の一致も確かめる）
python tools/selfcheck.py                   # キットを一時フォルダにコピーし、記録もキーも無い状態で pytest → SELFCHECK.md
python data/check_data.py                   # データを作り直して、ハッシュが一致するか
```

## フォルダ

```
common/   llm.py（呼び先・記録・台帳）, stats.py, agreement.py, metrics.py, judge.py, sampling.py, kit.py, mockutil.py
data/     架空のデータと作り方（make_data.py / gen/ / GENERATION.md / MANIFEST.json）
lab02〜12/ ラボ
notebooks/ 講義のノートブック p01〜p12（一覧は DEMOS.md）と、その作り方（build_*.py）・まとめて回す run_notebooks.py
tests/    キット全体の自己検査（模擬・再生の一致）
tools/    selfcheck.py, capture_runlogs.py（RUN_LOG を記録の再生で作る）
.cache/llm/ 講師の応答の記録（1,646 件・再生に使う）
```

## 既知の制約

- データは小さく（120 件・48 件・30 問・10 件など）、型から作った文なので本物より言い回しの幅が狭い。区間が広いことを数字と一緒に必ず言う
- 正解ラベルは「作った側が知っている正解」。裁定で 2 件の誤りが見つかった（RESULTS.md）。データは直さず、誤りを見つける過程を教材にしている
- lab07-2・lab07-3 の判定者は**模擬**（乱数のくせ / LLM に人物像を与えたもの）。人の κ の代わりにはならない
- LLM の出力は揺れる。講師の記録は 1 回の実行（エージェントは 3 回）
- 自分の業務データで試すときは、社外秘の情報を外部の AI に送ってよいか、所属先の規程を先に確かめてください
