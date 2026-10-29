# lab04_rag_eval RAG を検索と回答に分けて測る（P4・UC3）

検索の recall@k・MRR・nDCG、回答の要素の照合（v1 と、v1 の誤りを直した v2）、根拠を抜いたときに断るか、忠実さ（回答者と別のモデルで判定）。

## 動かす

```bash
python run_rag.py
python run_rag.py --provider replay --all
python run_rag.py --provider replay --all --condition degraded --judge
python run_rag.py --provider anthropic --only Q11,Q22   # デモ
```

- 模擬（既定）の数字は性能の証拠になりません。講師の本物の実行は RUN_LOG.md、読み取れることは RUN_NOTES.md
- テスト: `python -m pytest .`（キット直下から `python -m pytest`）
