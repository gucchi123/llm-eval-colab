# lab09_ci_gate 回帰の関門（P9）

候補（短くした依頼文）と基準を同じ問いで比べる。非劣性（片側 95% 下限 > −3 ポイント）・層の床（25 ポイント）・無効な出力 0。設定は gate_config.json。ci_example.yml は GitHub Actions に入れる例（有効にはしていない）。

## 動かす

```bash
python run_candidate.py --provider replay --all --model claude-sonnet-5-5
python gate.py; echo $?      # 1 なら止める
python -m pytest tests     # CI に入れる形の例
```

- 模擬（既定）の数字は性能の証拠になりません。講師の本物の実行は RUN_LOG.md、読み取れることは RUN_NOTES.md
- テスト: `python -m pytest .`（キット直下から `python -m pytest`）
