"""素の Anthropic SDK の道具呼び出しループ（フレームワークを使わない。評価の考え方を見えやすくするため）。"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import llm as L  # noqa: E402
from env import TOOLS, OrderEnv  # noqa: E402

MAX_TURNS = 14


def system_prompt(rules: str) -> str:
    return ("あなたはクロツグ食品（架空）の発注担当のアシスタントです。担当者の依頼を、道具を使って処理してください。\n"
            "必ず次の手引きに従ってください。\n\n" + rules)


def run_episode(task: dict, data: dict, *, provider, model=None, effort=None, trial: int = 0) -> dict:
    env = OrderEnv(data)
    messages = [{"role": "user", "content": task["request"]}]
    results = []
    final = ""
    stop = "max_turns"
    for turn in range(MAX_TURNS):
        r = L.chat(messages, system=system_prompt(data["rules"]), tools=TOOLS, provider=provider, model=model,
                   effort=effort, max_tokens=8000, trial=trial)
        results.append(r)
        messages.append({"role": "assistant", "content": r.content or [{"type": "text", "text": r.text or "(空)"}]})
        if not r.tool_calls:
            final = r.text
            stop = "end_turn"
            break
        outs = [{"type": "tool_result", "tool_use_id": tc["id"], "content": env.call(tc["name"], tc["input"])}
                for tc in r.tool_calls]
        messages.append({"role": "user", "content": outs})
    u = L.usage_of(results)
    return {"task": task["id"], "trial": trial, "trace": env.trace, "orders": env.orders, "approvals": env.approvals,
            "final": final, "stop": stop, "turns": len(results), **{k: u[k] for k in ("cost_usd", "seconds", "in", "out")}}
