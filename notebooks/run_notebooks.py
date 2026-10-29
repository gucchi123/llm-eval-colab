"""ノートブックを手元のカーネルで上から順に実行する（1 本ずつ）。キットのノートブックは書き換えない。

    python notebooks/run_notebooks.py --out ../_nbrun/replay --prefer replay        # 講師の記録の再生だけで
    python notebooks/run_notebooks.py --out ../_nbrun/mock --prefer mock p02        # mock で、名前の先頭で絞る

- 実行した写しを --out に保存し、各セルの秒数を <out>/TIMINGS.md に書く
- 出力に API キーらしい文字列が無いかを調べ、あれば保存せずに止める
必要: pip install nbclient ipykernel nbformat
"""
import argparse
import datetime as dt
import json
import os
import re
import time

import nbformat
from nbclient import NotebookClient

HERE = os.path.dirname(os.path.abspath(__file__))
SECRET = re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")


def secs(cell):
    t = cell.get("metadata", {}).get("execution", {})
    a, b = t.get("iopub.status.busy"), t.get("iopub.status.idle")
    if not (a and b):
        return None
    f = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
    return (f(b) - f(a)).total_seconds()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("only", nargs="?", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefer", choices=["mock", "replay", "anthropic"], default="replay")
    a = ap.parse_args()
    os.environ["LLM_PROVIDER_PREFER"] = a.prefer
    if a.prefer != "anthropic":
        os.environ["LLM_CACHE_ONLY"] = "1"      # 念のため: 記録に無い依頼で API を呼ばない
    os.makedirs(a.out, exist_ok=True)
    names = sorted(n for n in os.listdir(HERE) if n.endswith(".ipynb") and n.startswith(a.only))
    rows = []
    for name in names:
        nb = nbformat.read(os.path.join(HERE, name), as_version=4)
        t0 = time.time()
        NotebookClient(nb, timeout=1800, kernel_name="python3", record_timing=True,
                       resources={"metadata": {"path": HERE}}, allow_errors=False).execute()
        text = json.dumps(nb, ensure_ascii=False)
        if SECRET.search(text):
            raise SystemExit(f"{name}: 出力にキーらしい文字列があるので保存しません")
        warn = [o.get("text", "") for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", [])
                if "⚠ エラーで止まりました" in "".join(o.get("text", ""))]
        nbformat.write(nb, os.path.join(a.out, name))
        ts = [secs(c) or 0.0 for c in nb.cells if c.cell_type == "code"]
        rows.append((name, time.time() - t0, ts, len(warn)))
        print(f"{name}: {time.time() - t0:.1f}s / セル最長 {max(ts):.1f}s / エラー表示 {len(warn)}")
    with open(os.path.join(a.out, "TIMINGS.md"), "w", encoding="utf-8") as f:
        f.write(f"# 実行時間（prefer={a.prefer}, {dt.datetime.now():%Y-%m-%d %H:%M}）\n\n| ノートブック | 合計秒 | 各コードセルの秒 | エラー表示 |\n|---|---:|---|---:|\n")
        for n, t, ts, w in rows:
            f.write(f"| {n} | {t:.1f} | {' / '.join(f'{x:.1f}' for x in ts)} | {w} |\n")


if __name__ == "__main__":
    main()
