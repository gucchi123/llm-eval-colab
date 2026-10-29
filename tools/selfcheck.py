"""配布キットの自己検査: キットを一時フォルダにコピーし、記録（.cache）もキーも無い状態で pytest を回す。

    python tools/selfcheck.py

コピーに含めないもの: .venv/・.cache/・台帳・out_mock/・__pycache__/・research/
→ 「受け取ったばかりの人の手元」と同じ（記録の再生のテストは飛ばされる）。結果は SELFCHECK.md。
あわせて、元のキット（記録あり）でも pytest を回し、記録の再生が本物の実行と一致することを確かめる。
"""
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKIP = {".venv", ".cache", "out_mock", "__pycache__", "research", "_api_cost_ledger.jsonl", ".pytest_cache"}


def run(cwd, env):
    t0 = time.time()
    p = subprocess.run([sys.executable, "-m", "pytest", "-rs"], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", env=env, timeout=1800)
    last = [l for l in p.stdout.strip().splitlines() if re.search(r"(passed|failed|skipped|error)", l)]
    return p.returncode, (last[-1] if last else p.stdout[-300:]), time.time() - t0, p.stdout


def main():
    tmp = os.path.join(tempfile.gettempdir(), "eval_selfcheck")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(ROOT, tmp, ignore=lambda d, names: [n for n in names if n in SKIP])
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    env.update(PYTHONIOENCODING="utf-8", LLM_PROVIDER="mock")
    rc1, s1, t1, out1 = run(tmp, env)
    print("clean copy:", s1, flush=True)
    leaked = os.path.exists(os.path.join(tmp, "_api_cost_ledger.jsonl"))
    keyish = []
    for d, _, files in os.walk(tmp):
        for fn in files:
            if fn.endswith((".py", ".md", ".json", ".jsonl", ".txt")):
                with open(os.path.join(d, fn), encoding="utf-8", errors="ignore") as f:
                    if re.search(r"sk-ant-[A-Za-z0-9_\-]{20,}", f.read()):
                        keyish.append(os.path.relpath(os.path.join(d, fn), tmp))
    rc2, s2, t2, out2 = run(ROOT, {**env, "EVAL_OUT_ROOT": tempfile.mkdtemp(prefix="eval_sc_out_")})
    print("with records:", s2, flush=True)
    ok = rc1 == 0 and rc2 == 0 and not leaked and not keyish
    md = ["# SELFCHECK ― 自己検査", "",
          f"- 実行日時: {time.strftime('%Y-%m-%d %H:%M')}",
          f"- 環境: Windows 11 {platform.machine()} / Python {platform.python_version()}",
          "", "| 状態 | 結果 | pytest | 秒 |", "|---|---|---|---:|",
          f"| きれいなコピー（記録なし・キーなし・provider=mock） | {'OK' if rc1 == 0 else 'NG'} | {s1} | {t1:.1f} |",
          f"| 講師の記録あり（再生が本物の実行と一致するか。API は呼ばない） | {'OK' if rc2 == 0 else 'NG'} | {s2} | {t2:.1f} |",
          "", f"- コピー側に API の台帳ができていない（API を呼んでいない）: {'確認' if not leaked else '台帳あり（要確認）'}",
          f"- キーらしい文字列（sk-ant-…）: {'0 件' if not keyish else keyish}",
          "", f"**{'全部 OK' if ok else '失敗あり'}**", ""]
    with open(os.path.join(ROOT, "SELFCHECK.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md))
    if not ok:
        print(out1[-3000:], out2[-3000:])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
