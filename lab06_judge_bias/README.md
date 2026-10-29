# lab06_judge_bias LLM 判定の偏り（P6・UC5）

位置（入れ替えて 2 回）・長さ（中身が同じで長いだけ）・長いが誤り・自己贔屓（書き手 2 × 判定役 2）。依頼文は prompts/ に。

## 動かす

```bash
python run_bias.py --all
python run_bias.py --provider replay --all --model claude-sonnet-5-5
python run_bias.py --provider replay --all --model claude-sonnet-5-5 --prompt naive --kinds equal,length
python run_selfpref.py --provider replay --limit 10
```

- 模擬（既定）の数字は性能の証拠になりません。講師の本物の実行は RUN_LOG.md、読み取れることは RUN_NOTES.md
- テスト: `python -m pytest .`（キット直下から `python -m pytest`）
