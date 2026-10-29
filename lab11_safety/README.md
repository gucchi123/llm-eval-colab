# lab11_safety 安全性を両側で測る（P11）

攻撃 12 件（漏えいは規則で判定）と正当な依頼 12 件（止めすぎは LLM 判定＋人が全件読む）。0 件の読み方（3 の法則）。

## 動かす

```bash
python run_safety.py
python run_safety.py --provider replay --all
```

- 模擬（既定）の数字は性能の証拠になりません。講師の本物の実行は RUN_LOG.md、読み取れることは RUN_NOTES.md
- テスト: `python -m pytest .`（キット直下から `python -m pytest`）
