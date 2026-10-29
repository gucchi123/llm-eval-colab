"""データの読み込み・出力先・引数など、全ラボで同じにしたいもの。"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DATA = os.path.join(ROOT, "data")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def load_jsonl(name: str) -> list[dict]:
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_json(name: str):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def load_text(name: str) -> str:
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return f.read()


def parser(desc: str, default_limit: int | None = None) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--provider", default=os.environ.get("LLM_PROVIDER", "mock"), choices=["mock", "replay", "anthropic"])
    p.add_argument("--model", default=None, help="既定は LLM_MODEL か claude-opus-5-5。比較は claude-sonnet-5-5 など")
    p.add_argument("--effort", default=None, help="既定は LLM_EFFORT か high")
    p.add_argument("--limit", type=int, default=default_limit, help="先頭の何件だけ回すか（デモ用）")
    p.add_argument("--all", action="store_true", help="全件を回す")
    p.add_argument("--only", default=None, help="ID をカンマ区切りで（デモ用）")
    p.add_argument("--workers", type=int, default=4, help="並列の数（API のとき）")
    return p


def select(rows: list[dict], args) -> list[dict]:
    if args.only:
        want = set(args.only.split(","))
        return [r for r in rows if r["id"] in want]
    if args.limit and not args.all:
        return rows[: args.limit]
    return rows


def out_dir(lab_dir: str, provider: str) -> str:
    """講師の本物の実行（anthropic / replay）は out/、模擬（mock）は out_mock/。混ぜない。"""
    d = os.path.join(lab_dir, "out" if provider in ("anthropic", "replay") else "out_mock")
    if os.environ.get("EVAL_OUT_ROOT"):   # 検査用: 講師の out/ を上書きしないよう、別の場所へ書く
        d = os.path.join(os.environ["EVAL_OUT_ROOT"], os.path.basename(lab_dir), os.path.basename(d))
    os.makedirs(d, exist_ok=True)
    return d


def slug(model: str) -> str:
    return model.replace("claude-", "").replace(".", "-")


def write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def write_jsonl(path: str, rows) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def banner(title: str, args=None) -> None:
    from common import llm as L
    line = f"== {title}"
    if args is not None:
        prov = args.provider
        line += f"  [provider={prov}"
        if prov != "mock":
            line += f" model={L.model_name(args.model)} effort={L.effort_name(args.effort)}"
        else:
            line += " ← 模擬。数字は性能の証拠にならない"
        line += "]"
    print(line)
    print(f"   {time.strftime('%Y-%m-%d %H:%M')}")


def pct(x: float, digits: int = 1) -> str:
    return "-" if x != x else f"{100 * x:.{digits}f}%"


def ci_str(lo: float, hi: float) -> str:
    return f"[{100 * lo:.1f}, {100 * hi:.1f}]"


def table(rows: list[list], header: list[str]) -> str:
    """幅をそろえた簡単な表（全角は 2 文字として数える）。"""
    def w(s):
        return sum(2 if ord(ch) > 0x2E80 else 1 for ch in str(s))
    cols = [header] + [[str(c) for c in r] for r in rows]
    widths = [max(w(r[i]) for r in cols) for i in range(len(header))]
    def fmt(r):
        return "  ".join(str(c) + " " * (widths[i] - w(c)) for i, c in enumerate(r))
    return "\n".join([fmt(header), "  ".join("-" * x for x in widths)] + [fmt(r) for r in cols[1:]])


def run_parallel(fn, items, workers: int = 4):
    """API のときだけ並列。順番は入力どおりに返す。"""
    if workers <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, items))
