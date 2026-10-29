# DEMOS ― ノートブックと、そこで見るもの

> **この教材に登場する会社・人物・製品・数値・文書はすべて架空のものです。実在の企業・団体・個人とは関係ありません。**

各ノートブックは上から順に実行します。0 のセルは準備です（Colab でも手元の Jupyter でも同じ）。
API キーが無ければ講師の実行記録（`.cache/llm/`）を再生します（費用 0）。記録と違う依頼（入力を変えたなど）はエラーで止まります。
P10 の一部（シャドー運転・SRM・ずれ・抜き取り）は手順を見せるための**模擬**です。模擬の数字は性能の証拠になりません。

Colab で開く: `https://colab.research.google.com/github/gucchi123/llm-eval-colab/blob/main/notebooks/<名前>.ipynb`

| ノートブック | 部 | 見るもの |
|---|---|---|
| [p01_providers](https://colab.research.google.com/github/gucchi123/llm-eval-colab/blob/main/notebooks/p01_providers.ipynb) | P1 三つの呼び先 | 同じコードを模擬（mock）・講師の記録の再生（replay）・本物の API（anthropic）で動かし分け、120 件の再生が RESULTS.md の数字と一致することを確かめる |
| [p02_golden_set](https://colab.research.google.com/github/gucchi123/llm-eval-colab/blob/main/notebooks/p02_golden_set.ipynb) | P2 ゴールデンセット | 層別の抜き取り・層の重み・件数と区間の幅・お手本からの漏れ・似た文の塊・データカード（LLM なし） |
| [p03_classify_extract](https://colab.research.google.com/github/gucchi123/llm-eval-colab/blob/main/notebooks/p03_classify_extract.ipynb) | P3 分類と抽出の指標 | 混同行列・適合率と再現率・マクロ F1・自信の較正（ECE）・strict と normalized の照合、満点で飽和した試験の読み方 |
| [p04_rag_eval](https://colab.research.google.com/github/gucchi123/llm-eval-colab/blob/main/notebooks/p04_rag_eval.ipynb) | P4 RAG の評価 | 検索（再現率・逆順位・nDCG）と回答を分けて測る、要素の照合・断る率・忠実さの判定、照合そのものの誤り |
| [p05_agent_trajectory](https://colab.research.google.com/github/gucchi123/llm-eval-colab/blob/main/notebooks/p05_agent_trajectory.ipynb) | P5 エージェントと軌跡 | 発注エージェントを結果と軌跡で採点、pass@k と pass^k、道具の数・費用・待ち時間、失敗 0 件の上限 |
| [p06_judge_bias](https://colab.research.google.com/github/gucchi123/llm-eval-colab/blob/main/notebooks/p06_judge_bias.ipynb) | P6 LLM 判定の偏り | 入れ替えて 2 回聞く、位置・長さ・自分びいきの偏り、基準つきの依頼文 |
| [p07_judge_calibration](https://colab.research.google.com/github/gucchi123/llm-eval-colab/blob/main/notebooks/p07_judge_calibration.ipynb) | P7 判定を人に合わせる | 真陽性率と真陰性率・dev と test・Rogan-Gladen・κ と α、模擬の判定者 4 人（人ではない）とガイドラインの改訂・裁定 |
| [p08_stats](https://colab.research.google.com/github/gucchi123/llm-eval-colab/blob/main/notebooks/p08_stats.ipynb) | P8 差は本物か | Wilson の区間・3 の法則・McNemar・対のブートストラップ・塊の標準誤差・必要な件数・Holm（LLM なし） |
| [p09_ci_gate](https://colab.research.google.com/github/gucchi123/llm-eval-colab/blob/main/notebooks/p09_ci_gate.ipynb) | P9 回帰の関門 | 非劣性・層の床・無効な出力の 3 つの決まりで候補を止める、終了コードで CI を止める、予算切れを「無効」と数えない |
| [p10_online_eval](https://colab.research.google.com/github/gucchi123/llm-eval-colab/blob/main/notebooks/p10_online_eval.ipynb) | P10 本番での評価 | シャドー運転・SRM・χ² と PSI・人が見る抜き取り（模擬）、費用と待ち時間の中央値と 95 パーセント点（本物の記録から） |
| [p11_safety](https://colab.research.google.com/github/gucchi123/llm-eval-colab/blob/main/notebooks/p11_safety.ipynb) | P11 安全性の評価 | 攻撃 12 件と正当な依頼 12 件で、漏えい（規則で判定）と止めすぎ（LLM 判定＋人が全件読む）の両側を測る |
| [p12_usecases](https://colab.research.google.com/github/gucchi123/llm-eval-colab/blob/main/notebooks/p12_usecases.ipynb) | P12 ユースケース | 5 つの業務の評価カードと、Sonnet と Opus の全ラボの比較表（LLM なし） |
