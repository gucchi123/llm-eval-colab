"""lab09-1 「候補」の変更を試験セットで回す（P9）。

想定: 費用を下げるために、誰かが分類の依頼文を短くした（prompts/classify_trimmed.md）。
手引きの R0（用件が複数のとき）と「仕様（故障ではない）」の一覧が消えている。これを本番に出してよいかを gate.py が決める。

    python run_candidate.py                                                       # 模擬
    python run_candidate.py --provider anthropic --all --set v2 --model claude-sonnet-5-5
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import kit, llm as L  # noqa: E402
from common.mockutil import coin, skill  # noqa: E402

LABELS = ["返品・交換", "修理・故障", "配送", "請求・支払い", "使い方", "会員・解約"]


def render(r):
    ch = {"web": "Web フォーム", "mail": "メール", "phone": "電話"}[r["channel"]]
    return f"受付日: {r['received']}\n窓口: {ch}\n---\n{r['text']}"


def mock_for(rows):
    by = {render(r): r for r in rows}

    def fn(system, messages, tools, model):
        if not system or "ラベル: 返品・交換" not in system:
            return None
        r = by.get(messages[-1]["content"])
        if r is None:
            return None
        weak = r["facts"]["scenario"] in ("hedged_spec", "normal_behavior", "buried_money", "lookalike")
        ok = coin("cand", model, r["id"]) < skill(model) - (0.35 if weak else 0)
        lab = r["label"] if ok else ("修理・故障" if r["label"] != "修理・故障" else "返品・交換")
        return f'{{"label": "{lab}", "rule": "-", "confidence": 90}}'
    return fn


def main(argv=None):
    p = kit.parser("lab09 候補を回す", default_limit=12)
    p.add_argument("--set", default="v2", choices=["v1", "v2"])
    args = p.parse_args(argv)
    kit.banner(f"lab09-1 候補（短くした依頼文）を試験セット {args.set} で回す", args)
    rows_all = kit.load_jsonl("golden_inquiries.jsonl" if args.set == "v1" else "golden_inquiries_v2_hard.jsonl")
    rows = kit.select(rows_all, args)
    with open(os.path.join(HERE, "prompts", "classify_trimmed.md"), encoding="utf-8") as f:
        system = f.read()
    model = L.model_name(args.model)

    def one(r):
        try:
            obj, res = L.call_json(render(r), system=system, provider=args.provider, model=args.model, effort=args.effort,
                                   validate=lambda o: None if o.get("label") in LABELS else "label", max_tokens=4000)
            pred = obj["label"]
        except (L.BudgetExceeded, L.CacheMiss):
            raise   # 予算切れ・記録なしは「無効な出力」に数えない
        except RuntimeError:
            pred, res = "(無効)", []
        u = L.usage_of(res)
        return {"id": r["id"], "label": r["label"], "pred": pred, "correct": int(pred == r["label"]),
                "difficulty": r["difficulty"], "scenario": r["facts"]["scenario"], "cost_usd": u["cost_usd"],
                "seconds": u["seconds"]}

    with L.mock_handler(mock_for(rows_all)), L.tag(f"lab09/candidate/{args.set}/{kit.slug(model)}"):
        runs = kit.run_parallel(one, rows, workers=args.workers if args.provider == "anthropic" else 1)
    k = sum(r["correct"] for r in runs)
    print(f"\n候補の正答 {k}/{len(runs)}、費用 {sum(r['cost_usd'] for r in runs):.4f} USD")
    out = kit.out_dir(HERE, args.provider)
    tag = f"{args.set}_{kit.slug(model)}" + ("" if len(runs) == len(rows_all) else f"_n{len(runs)}")
    path = os.path.join(out, f"runs_candidate_{tag}.jsonl")
    kit.write_jsonl(path, runs)
    print(f"→ {os.path.relpath(path, HERE)}")
    return runs


if __name__ == "__main__":
    main()
