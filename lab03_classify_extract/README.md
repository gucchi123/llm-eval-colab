# lab03_classify_extract 分類と抽出を測る（P3・UC1/UC2）

混同行列・ラベル別の適合率/再現率・マクロ F1・Wilson 区間・本番の割合に戻した正答率・ECE。抽出は strict と normalized。本物の実行は v1・v2 とも満点（飽和）→ RUN_LOG 参照。

## 動かす

```bash
python run_classify.py
python run_classify.py --provider anthropic --all
python run_classify.py --provider anthropic --all --model claude-sonnet-5-5
python run_classify.py --provider replay --all --set v2 --model claude-sonnet-5-5
python run_extract.py --provider replay --all --model claude-sonnet-5-5
python run_classify.py --provider anthropic --only HRD-019,HRD-025 --set v2   # デモ（2 件）
```

- 模擬（既定）の数字は性能の証拠になりません。講師の本物の実行は RUN_LOG.md、読み取れることは RUN_NOTES.md
- テスト: `python -m pytest .`（キット直下から `python -m pytest`）
