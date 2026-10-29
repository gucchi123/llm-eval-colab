"""配布用の zip を作る（講師の記録 .cache/llm を含める → 受講者はキー無しで本物の実行と同じ数字を再生できる）。

    python tools/package_kit.py            # → dist/eval_kit.zip、展開して pytest（再生の一致を含む）まで確かめる

含めないもの: .venv/・台帳（費用の明細）・out_mock/・__pycache__/・research/（制作用の調べもの）・dist/
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKIP_DIRS = {".venv", "out_mock", "__pycache__", "research", "dist", ".pytest_cache", "_nbrun"}
SKIP_FILES = {"_api_cost_ledger.jsonl"}


def main():
    dist = os.path.join(ROOT, "dist")
    os.makedirs(dist, exist_ok=True)
    zp = os.path.join(dist, "eval_kit.zip")
    n, key_hits = 0, []
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for d, dirs, files in os.walk(ROOT):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            for fn in files:
                if fn in SKIP_FILES:
                    continue
                full = os.path.join(d, fn)
                rel = os.path.relpath(full, ROOT)
                with open(full, "rb") as f:
                    if re.search(rb"sk-ant-[A-Za-z0-9_\-]{20,}", f.read()):
                        key_hits.append(rel)
                z.write(full, os.path.join("eval_kit", rel))
                n += 1
    if key_hits:
        os.remove(zp)
        print("キーらしい文字列があったので zip を消しました:", key_hits)
        sys.exit(1)
    tmp = tempfile.mkdtemp(prefix="eval_kit_unzip_")
    with zipfile.ZipFile(zp) as z:
        z.extractall(tmp)
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    env.update(PYTHONIOENCODING="utf-8", LLM_PROVIDER="mock", LLM_CACHE_ONLY="1")
    p = subprocess.run([sys.executable, "-m", "pytest", "-rs"], cwd=os.path.join(tmp, "eval_kit"), capture_output=True,
                       text=True, encoding="utf-8", env=env)
    last = [l for l in p.stdout.splitlines() if "passed" in l or "failed" in l]
    print(f"{zp}: {n} ファイル・{os.path.getsize(zp) / 1e6:.1f} MB / 展開して pytest: {last[-1] if last else p.stdout[-300:]}")
    shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(p.returncode)


if __name__ == "__main__":
    main()
