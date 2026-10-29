"""講義用ノートブックを、キットの一時コピーで作って実行し、録画に向くかを検める（制作用）。

    <rec venv の python> tools/nb_check.py [名前の先頭 ...]      例: tools/nb_check.py p03 p04

- キットを一時フォルダにコピー（.venv・research・dist・台帳は除く）→ そこで build_notebooks.py → run_notebooks.py --prefer replay
  （LLM_CACHE_ONLY=1。記録に無い依頼は API を呼ばずにエラー）。本物の out/ は書き換えない
- 実行済みのノートブックを _nbrun/replay/ に写す（クリップの切り出しが出力の文字を読む）
- 各コードセルの出力の行数と最大の幅（全角 2）を出し、録画の 1 画面（22 行・幅 110）を超えたら印を付ける
- エラー表示（⚠ エラーで止まりました / Traceback）があれば印を付ける
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "_nbrun", "replay")
MAX_LINES, MAX_W = 22, 110
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def width(s):
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in s)


def main():
    prefixes = sys.argv[1:] or [""]
    tmp = tempfile.mkdtemp(prefix="evnb_")
    work = os.path.join(tmp, "kit")
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".venv", "research", "dist", "_nbrun", "__pycache__",
                                                               "_api_cost_ledger.jsonl", ".pytest_cache", "out_mock"))
    env = dict(os.environ, PYTHONIOENCODING="utf-8", LLM_CACHE_ONLY="1")
    os.makedirs(OUT, exist_ok=True)
    bad = 0
    for pre in prefixes:
        subprocess.run([sys.executable, os.path.join(work, "notebooks", "build_notebooks.py"), pre], check=True, env=env)
        r = subprocess.run([sys.executable, os.path.join(work, "notebooks", "run_notebooks.py"), pre,
                            "--out", os.path.join(tmp, "run"), "--prefer", "replay"], env=env)
        if r.returncode:
            print(f"🔴 {pre}: 実行が止まった (rc={r.returncode})")
            bad += 1
            continue
    run = os.path.join(tmp, "run")
    for name in sorted(os.listdir(run)) if os.path.isdir(run) else []:
        if not name.endswith(".ipynb"):
            continue
        shutil.copy(os.path.join(run, name), os.path.join(OUT, name))
        d = json.load(open(os.path.join(run, name), encoding="utf-8"))
        print(f"\n== {name}")
        for i, c in enumerate(d["cells"]):
            if c["cell_type"] != "code":
                continue
            txt = ""
            for o in c.get("outputs", []):
                txt += "".join(o.get("text", "")) if "text" in o else "".join(o.get("data", {}).get("text/plain", ""))
                if o.get("output_type") == "error":
                    txt += "Traceback\n"
            lines = txt.rstrip("\n").split("\n") if txt.strip() else []
            w = max((width(l) for l in lines), default=0)
            src_lines = len("".join(c["source"]).split("\n"))
            mark = []
            if len(lines) > MAX_LINES:
                mark.append(f"出力 {len(lines)} 行")
            if w > MAX_W:
                mark.append(f"幅 {w}")
            if src_lines > 18:
                mark.append(f"コード {src_lines} 行")
            if "⚠ エラーで止まりました" in txt or "Traceback" in txt:
                mark.append("エラー表示")
            if "sk-ant-" in txt:
                mark.append("キーの形!")
            bad += bool(mark)
            print(f"  c{i:<3d} コード {src_lines:2d} 行 / 出力 {len(lines):2d} 行 幅 {w:3d}  {'🔴 ' + ', '.join(mark) if mark else ''}")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{'🔴 印 ' + str(bad) + ' 件' if bad else '🟢 問題なし'}  → 実行済みの写し {OUT}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
