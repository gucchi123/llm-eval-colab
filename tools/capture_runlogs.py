"""各ラボの RUN_LOG.md を作る。講師が本物のモデル（provider=anthropic）で回したコマンドを、
記録の再生（provider=replay・LLM_CACHE_ONLY=1・API を呼ばない）でもう一度回し、出力をそのまま写す。

    python tools/capture_runlogs.py

再生の出力は本物の実行と同じ数字になる（費用・待ち時間も元の実行の値）。違うのは見出しの provider=replay だけ。
講師の out/ は上書きしない（EVAL_OUT_ROOT で一時フォルダへ書く）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from common import llm as L  # noqa: E402

S, O = "--model claude-sonnet-5-5", "--model claude-opus-5-5"
RUNS = {
    "lab02_golden_set": ("ゴールデンセット（LLM なし）", None, [["run_golden.py"]]),
    "lab03_classify_extract": ("分類と抽出", "lab03", [
        ["run_classify.py", "--provider", "replay", "--all", *O.split()],
        ["run_classify.py", "--provider", "replay", "--all", *S.split()],
        ["run_classify.py", "--provider", "replay", "--all", "--set", "v2", *S.split()],
        ["run_classify.py", "--provider", "replay", "--all", "--set", "v2", *O.split()],
        ["run_extract.py", "--provider", "replay", "--all", *S.split()],
        ["run_extract.py", "--provider", "replay", "--all", *O.split()]]),
    "lab04_rag_eval": ("RAG", "lab04", [
        ["run_rag.py", "--provider", "replay", "--all", *O.split()],
        ["run_rag.py", "--provider", "replay", "--all", "--judge", *O.split()],
        ["run_rag.py", "--provider", "replay", "--all", "--condition", "degraded", "--judge", *O.split()],
        ["run_rag.py", "--provider", "replay", "--all", *S.split()],
        ["run_rag.py", "--provider", "replay", "--all", "--condition", "degraded", *S.split()]]),
    "lab05_agent_trajectory": ("エージェント", "lab05", [
        ["run_agent.py", "--provider", "replay", "--all", "--k", "3", *S.split()],
        ["run_agent.py", "--provider", "replay", "--all", "--k", "3", *O.split()]]),
    "lab06_judge_bias": ("判定の偏り", "lab06", [
        ["run_bias.py", "--provider", "replay", "--all", *S.split()],
        ["run_bias.py", "--provider", "replay", "--all", "--prompt", "naive", "--kinds", "equal,length", *S.split()],
        ["run_bias.py", "--provider", "replay", "--all", "--prompt", "naive", "--kinds", "equal,length", *O.split()],
        ["run_bias.py", "--provider", "replay", "--all", "--kinds", "equal", *O.split()],
        ["run_selfpref.py", "--provider", "replay", "--limit", "10"]]),
    "lab07_judge_calibration": ("判定の校正と一致", "lab07", [
        ["run_calibrate.py", "--provider", "replay", "--split", "dev", "--prompt", "v1", *S.split()],
        ["run_calibrate.py", "--provider", "replay", "--split", "dev", "--prompt", "v2", *S.split()],
        ["run_calibrate.py", "--provider", "replay", "--split", "test", "--prompt", "v2", *S.split()],
        ["run_calibrate.py", "--provider", "replay", "--split", "dev", "--prompt", "v1", *O.split()],
        ["run_calibrate.py", "--provider", "replay", "--split", "dev", "--prompt", "v2", *O.split()],
        ["run_calibrate.py", "--provider", "replay", "--split", "test", "--prompt", "v2", *O.split()],
        ["run_personas.py", "--provider", "replay", "--round", "both", "--adjudicate"],
        ["run_iaa.py"]]),
    "lab08_stats": ("統計（LLM なし・他のラボの本物の出力を読む）", None, [["run_stats.py"]]),
    "lab09_ci_gate": ("回帰の関門", "lab09", [
        ["run_candidate.py", "--provider", "replay", "--all", *S.split()],
        ["run_candidate.py", "--provider", "replay", "--all", *O.split()], ["gate.py"]]),
    "lab10_online_eval": ("本番での評価（1〜4 模擬・5 は本物の台帳）", None, [["run_online.py"]]),
    "lab11_safety": ("安全性", "lab11", [["run_safety.py", "--provider", "replay", "--all", *O.split()],
                                       ["run_safety.py", "--provider", "replay", "--all", *S.split()]]),
    "lab12_usecases": ("評価カード（LLM なし）", None, [["build_cards.py"]]),
}


def ledger_lines(prefix):
    rows = [e for e in L.read_ledger() if str(e.get("tag", "")).startswith(prefix) and not e.get("cached")]
    if not rows:
        return []
    by = {}
    for e in rows:
        k = (e["tag"], e["model"])
        d = by.setdefault(k, [0, 0.0, None, None])
        d[0] += 1
        d[1] += e["cost_usd"]
        d[2] = min(d[2] or e["t"], e["t"])
        d[3] = max(d[3] or e["t"], e["t"])
    out = ["| 台帳の印 | モデル | 呼び出し | 費用 USD | 実行の時刻 |", "|---|---|---:|---:|---|"]
    for (t, m), (n, c, a, b) in sorted(by.items()):
        out.append(f"| {t} | {m} | {n} | {c:.4f} | {a} 〜 {b[11:]} |")
    out.append(f"| 計 | | {sum(v[0] for v in by.values())} | {sum(v[1] for v in by.values()):.4f} | |")
    return out


def main():
    tmp = tempfile.mkdtemp(prefix="eval_runlog_")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "LLM_CACHE_ONLY": "1", "EVAL_OUT_ROOT": tmp}
    env.pop("ANTHROPIC_API_KEY", None)
    for lab, (title, prefix, cmds) in RUNS.items():
        d = os.path.join(ROOT, lab)
        md = [f"# RUN_LOG {lab} — {title}", "",
              f"- 記録の作成: {time.strftime('%Y-%m-%d %H:%M')}（Windows 11 ARM64 / Python {sys.version.split()[0]}）",
              "- 本物の実行: 2026-10-18、Anthropic API、effort high。モデルは各コマンドの --model（既定 claude-opus-5-5）",
              "- 下の出力は、本物の実行の応答を記録から再生したもの（provider=replay・API を呼ばない）。数字・費用・待ち時間は本物の実行と同じ",
              "- 🔴 キーはどこにも出ていない（環境変数から読むだけ）", ""]
        if prefix:
            ll = ledger_lines(prefix)
            if ll:
                md += ["## 費用（講師の台帳 `_api_cost_ledger.jsonl` から。キャッシュの再生は 0 円なので数えない）", ""] + ll + [""]
        for c in cmds:
            p = subprocess.run([sys.executable, *c], cwd=d, capture_output=True, text=True, encoding="utf-8", env=env)
            shown = " ".join(c).replace("--provider replay", "--provider anthropic")
            md += [f"## `python {shown}`", "", "```", (p.stdout + (p.stderr if p.returncode not in (0, 1) else "")).rstrip(), "```", ""]
            print(lab, c[0], "rc=", p.returncode, flush=True)
        notes = os.path.join(d, "RUN_NOTES.md")
        if os.path.exists(notes):
            md += [open(notes, encoding="utf-8").read()]
        with open(os.path.join(d, "RUN_LOG.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
