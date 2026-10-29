# lab07_judge_calibration 判定を人のラベルに合わせる（P7・UC5）

dev で依頼文を直し、test は最後に 1 回。TPR・TNR・κ・欠陥の種類ごとの見逃し・Rogan-Gladen の補正。評価者どうしの一致の計算（評価者は模擬。人ではない）。模擬の判定者 4 人とガイドラインの改訂（lab07-3）。

## 動かす

```bash
python run_calibrate.py --prompt v1 --split dev
python run_calibrate.py --provider replay --model claude-sonnet-5-5 --split dev --prompt v1
python run_calibrate.py --provider replay --model claude-sonnet-5-5 --split dev --prompt v2
python run_calibrate.py --provider replay --model claude-sonnet-5-5 --split test --prompt v2
python run_iaa.py
python run_personas.py                                        # 模擬の判定者（mock）
python run_personas.py --provider replay --round both --adjudicate   # 講師の記録（Sonnet の判定者 4 人・Opus の裁定）
```

- 模擬（既定）の数字は性能の証拠になりません。講師の本物の実行は RUN_LOG.md、読み取れることは RUN_NOTES.md
- テスト: `python -m pytest .`（キット直下から `python -m pytest`）
- lab07-3（run_personas.py）: 🔴 判定者は LLM に人物像を与えた**模擬**。ガイドライン v1 → v2（prompts/guideline_v*.md、出典つき）で一致がどう変わるか、割れた返信を別のモデルが裁定する。人の κ とは呼ばない
