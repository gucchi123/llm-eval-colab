"""lab05 エージェントを結果と軌跡で測る（P5・UC4 クロツグ食品・架空）。

    python run_agent.py                                          # 模擬（キー不要）
    python run_agent.py --provider anthropic --all --k 3         # 本物。10 件 × 3 回
    python run_agent.py --provider anthropic --only T04 --k 1    # デモ（1 件）
    python run_agent.py --provider replay --all --k 3            # 講師の記録を再生

見るところ
- pass@1（1 回で通る率）と pass@k（k 回のうち 1 回でも）と pass^k（k 回とも通る）。業務で要るのはたいてい pass^k
- 結果（発注の中身）は合っているのに、軌跡（承認を飛ばした・在庫を見ずに発注した）で落ちるもの
- 1 件あたりの費用・道具の数（最短との比）・往復の数
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from agent import run_episode  # noqa: E402
from common import kit, llm as L, metrics as M, stats  # noqa: E402
from common.mockutil import coin, skill  # noqa: E402
from score import minimal_calls, score  # noqa: E402


def mock_for(data):
    """模擬のエージェント: 手引きどおりの手順を 1 手ずつ返す。腕前の確率で、承認を飛ばす・期限を無視する。"""
    tasks = {t["request"]: t for t in data["tasks"]}
    items = {i["code"]: i for i in data["items"]}

    def plan(task, model):
        exp = task["expected"]
        steps = []
        if task["id"] == "T08":
            steps.append(("search_items", {"query": "めんつゆ"}))
        for code in task["items"]:
            steps.append(("get_stock", {"code": code}))
            if code in exp["skipped"] and exp["skipped"][code] != "承認が却下された":
                continue
            steps.append(("get_suppliers", {"code": code}))
            it = items[code]
            qty = it["target"] - it["stock"]
            ok = [s for s in it["suppliers"] if s["lead_days"] <= exp.get("deadline", task["deadline_days"] or 7)]
            if coin("deadline", model, task["id"]) > skill(model) + 0.03:
                ok = it["suppliers"]                       # 期限を見落とす、の模擬
            sup = sorted(ok, key=lambda s: (s["unit_price"], s["lead_days"]))[0]
            amount = sup["unit_price"] * qty
            if amount >= 100_000 and coin("approval", model, task["id"]) < skill(model):
                steps.append(("request_approval", {"code": code, "qty": qty, "supplier": sup["name"], "amount": amount}))
                if code in exp["rejected"]:
                    continue
            steps.append(("create_order", {"code": code, "qty": qty, "supplier": sup["name"]}))
        return steps

    def fn(system, messages, tools, model):
        if not tools or "発注担当" not in (system or ""):
            return None
        task = tasks.get(messages[0]["content"])
        if task is None:
            return None
        steps = plan(task, model)
        i = sum(1 for m in messages if m["role"] == "assistant")
        if i < len(steps):
            name, args = steps[i]
            return [{"type": "tool_use", "id": f"mock_{i}", "name": name, "input": args}]
        return "（模擬）手引きに従って処理しました。"
    return fn


def main(argv=None) -> dict:
    p = kit.parser("lab05 エージェントの評価", default_limit=4)
    p.add_argument("--k", type=int, default=2, help="1 件を何回試すか")
    args = p.parse_args(argv)
    kit.banner(f"lab05 エージェント（結果と軌跡、k={args.k}）", args)
    data = kit.load_json("agent.json")
    tasks = kit.select(data["tasks"], args)
    model = L.model_name(args.model)
    jobs = [(t, k) for t in tasks for k in range(args.k)]
    with L.mock_handler(mock_for(data)), L.tag(f"lab05/agent/{kit.slug(model)}"):
        eps = kit.run_parallel(lambda job: run_episode(job[0], data, provider=args.provider, model=args.model,
                                                       effort=args.effort, trial=job[1]),
                               jobs, workers=args.workers if args.provider == "anthropic" else 1)
    by_task = {t["id"]: t for t in tasks}
    rows, per_task = [], {}
    for ep in eps:
        s = score(ep, by_task[ep["task"]], data)
        ep["score"] = s
        d = per_task.setdefault(ep["task"], {"n": 0, "c": 0, "outcome_only": 0, "violations": [], "cost": 0.0,
                                             "calls": [], "turns": []})
        d["n"] += 1
        d["c"] += s["pass"]
        d["outcome_only"] += s["outcome_ok"] and not s["trajectory_ok"]
        d["violations"] += s["violations"]
        d["cost"] += ep["cost_usd"]
        d["calls"].append(s["tool_calls"])
        d["turns"].append(ep["turns"])
    k = args.k
    for tid, d in per_task.items():
        t = by_task[tid]
        rows.append([tid, f"{d['c']}/{d['n']}", f"{M.pass_at_k(d['n'], d['c'], k):.2f}", f"{M.pass_hat_k(d['n'], d['c'], k):.2f}",
                     d["outcome_only"], f"{sum(d['calls']) / len(d['calls']):.1f}/{minimal_calls(t)}",
                     f"{d['cost'] / d['n']:.4f}", (d["violations"][0] if d["violations"] else "")[:34]])
    print(kit.table(rows, ["依頼", "成功", f"pass@{k}", f"pass^{k}", "結果だけ合格", "道具/最短", "費用/回", "最初の違反"]))
    n_ep = len(eps)
    c_all = sum(e["score"]["pass"] for e in eps)
    lo, hi = stats.wilson(c_all, n_ep)
    p1 = sum(M.pass_hat_k(d["n"], d["c"], 1) for d in per_task.values()) / len(per_task)
    pk = sum(M.pass_at_k(d["n"], d["c"], k) for d in per_task.values()) / len(per_task)
    phk = sum(M.pass_hat_k(d["n"], d["c"], k) for d in per_task.values()) / len(per_task)
    outcome = sum(e["score"]["outcome_ok"] for e in eps)
    cost = sum(e["cost_usd"] for e in eps)
    print(f"\n回ごとの合格 {c_all}/{n_ep} = {kit.pct(c_all / n_ep)} 95%区間 {kit.ci_str(lo, hi)}"
          f"（結果だけなら {outcome}/{n_ep}）")
    print(f"pass^1 {p1:.3f} / pass@{k} {pk:.3f} / pass^{k} {phk:.3f}（依頼ごとに出して平均）")
    print(f"費用 合計 {cost:.4f} USD・1 回あたり {cost / n_ep:.4f} USD・合格 1 回あたり "
          f"{(cost / c_all if c_all else float('nan')):.4f} USD / 待ち時間 p50 {stats.percentile([e['seconds'] for e in eps], .5):.1f}s")
    out = kit.out_dir(HERE, args.provider)
    tag = kit.slug(model) + f"_k{k}" + ("" if len(tasks) == len(data["tasks"]) else f"_n{len(tasks)}")
    kit.write_jsonl(os.path.join(out, f"episodes_{tag}.jsonl"), eps)
    summary = {"model": model, "effort": L.effort_name(args.effort), "provider": args.provider, "k": k,
               "episodes": n_ep, "pass": c_all, "outcome_ok": outcome, "ci": [lo, hi], "pass_hat_1": p1,
               f"pass_at_{k}": pk, f"pass_hat_{k}": phk, "cost_usd": round(cost, 4),
               "per_task": {t: {kk: v for kk, v in d.items()} for t, d in per_task.items()}}
    kit.write_json(os.path.join(out, f"summary_agent_{tag}.json"), summary)
    return summary


if __name__ == "__main__":
    main()
