# lab05_agent_trajectory エージェントを結果と軌跡で測る（P5・UC4）

env.py（発注システムの模型）・agent.py（素の SDK の道具ループ）・score.py（結果と軌跡の採点）。pass@k / pass^k・結果だけ合格・道具の数/最短・費用。

## 動かす

```bash
python run_agent.py --all --k 3          # 模擬（失敗の型が出る）
python run_agent.py --provider replay --all --k 3 --model claude-sonnet-5-5
python run_agent.py --provider anthropic --only T04 --k 1   # デモ
```

- 模擬（既定）の数字は性能の証拠になりません。講師の本物の実行は RUN_LOG.md、読み取れることは RUN_NOTES.md
- テスト: `python -m pytest .`（キット直下から `python -m pytest`）
