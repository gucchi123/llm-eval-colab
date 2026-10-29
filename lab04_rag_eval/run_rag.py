"""lab04 RAG を検索と回答に分けて測る（P4・UC3 ヒイラギ運輸・架空）。

    python run_rag.py                                                 # 模擬
    python run_rag.py --provider anthropic --all                      # 本物: 通常の検索で 30 問
    python run_rag.py --provider anthropic --all --condition degraded --judge --judge-model claude-sonnet-5-5

条件
- normal   : BM25 の上位 3 件を渡す
- degraded : 上位から「正解の根拠の規程」を抜いた 3 件を渡す（検索が外れたときに、わからないと言えるか）
- oracle   : 正解の根拠の規程だけを渡す（検索が完璧なら回答はどこまで行くか）

測るもの
- 検索: recall@k・MRR・nDCG@k（LLM なし。規程の番号の正解との照合）
- 回答: 要素の照合（答えに入るべき数字・語）・断るべき問いで断ったか・引用の番号が渡した規程の中にあるか
- 忠実さ（--judge）: 回答を主張に分け、渡した文書から導けるか（RAGAS の faithfulness と同じ考え方）。判定役は回答者と別のモデル
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from common import judge as J, kit, llm as L, metrics as M, stats  # noqa: E402
from common.mockutil import coin, skill  # noqa: E402
from retriever import BM25  # noqa: E402


def contexts(q, bm, docs, cond, k=3):
    by = {d["id"]: d for d in docs}
    if cond == "oracle":
        ids = q["gold_docs"] or [i for i, _ in bm.search(q["question"], k)]
    else:
        ranked = [i for i, _ in bm.search(q["question"], len(docs))]
        if cond == "degraded":
            ranked = [i for i in ranked if i not in q["gold_docs"]]
        ids = ranked[:k]
    return ids, "\n".join(f"[{i}] {by[i]['title']}: {by[i]['text']}" for i in ids)


def check_answer(ans, q, abstain):
    abst = abstain in ans
    if q["kind"] == "unanswerable":
        return {"correct": abst, "abstained": abst}
    ok = all(any(alt in ans for alt in group) for group in q["must"])
    return {"correct": ok and not abst, "abstained": abst}


# 照合 v2: 本物の実行で v1 の照合が誤った 3 問（2026-10-18）を見てから直したもの。
# - 「断った」は、答えが断りの文で始まるか、断りだけのときに限る（答えたうえで一部に「記載がありません」と添えた回答を落とさない）
# - 別表記を足す（「事前」＝「前に」）
EXTRA_ALIASES = {"事前": ["前に", "あらかじめ"]}


def check_answer_v2(ans, q, abstain):
    a = ans.strip()
    abst = a.startswith(abstain) or (abstain in a and len(a) < len(abstain) + 25)
    if q["kind"] == "unanswerable":
        return {"correct_v2": abstain in a, "abstained_v2": abst}
    ok = all(any(alt in a for g in group for alt in [g] + EXTRA_ALIASES.get(g, [])) for group in q["must"])
    return {"correct_v2": ok and not abst, "abstained_v2": abst}


def mock_for(pol):
    qs = {q["question"]: q for q in pol["questions"]}

    def fn(system, messages, tools, model):
        msg = messages[-1]["content"] if messages else ""
        if not isinstance(msg, str):
            return None
        if "社内規程について社員の質問に答える" in msg:
            q = next((v for k, v in qs.items() if k in msg), None)
            if q is None:
                return None
            have = all(f"[{d}]" in msg for d in q["gold_docs"]) and q["gold_docs"]
            if q["kind"] == "unanswerable" or not have:
                if coin("halluc", model, q["id"]) > skill(model):
                    return f"おそらく 5,000 円です。[{q['gold_docs'][0] if q['gold_docs'] else 'D01'}]"
                return pol["abstain"]
            parts = [g[0] for g in q["must"]]
            return "、".join(parts) + "です。" + "".join(f"[{d}]" for d in q["gold_docs"])
        if "主張に分け" in msg:
            sup = "おそらく" not in msg
            return '{"claims": [{"claim": "（模擬）", "supported": ' + ("true" if sup else "false") + "}]}"
        return None
    return fn


def main(argv=None) -> dict:
    p = kit.parser("lab04 RAG の評価")
    p.add_argument("--condition", default="normal", choices=["normal", "degraded", "oracle"])
    p.add_argument("--judge", action="store_true", help="忠実さを LLM で判定する")
    p.add_argument("--judge-model", default="claude-sonnet-5-5")
    args = p.parse_args(argv)
    kit.banner(f"lab04 RAG（条件 {args.condition}）", args)
    pol = kit.load_json("policies.json")
    docs, qs, abstain = pol["docs"], pol["questions"], pol["abstain"]
    bm = BM25(docs)

    # 1. 検索だけの評価（LLM なし）
    rk = [q for q in qs if q["gold_docs"]]
    r1 = sum(M.recall_at_k([i for i, _ in bm.search(q["question"], 5)], set(q["gold_docs"]), 1) for q in rk) / len(rk)
    r3 = sum(M.recall_at_k([i for i, _ in bm.search(q["question"], 5)], set(q["gold_docs"]), 3) for q in rk) / len(rk)
    mrr = sum(M.mrr([i for i, _ in bm.search(q["question"], 14)], set(q["gold_docs"])) for q in rk) / len(rk)
    nd = sum(M.ndcg_at_k([i for i, _ in bm.search(q["question"], 5)], set(q["gold_docs"]), 3) for q in rk) / len(rk)
    print(f"\n検索（BM25・根拠のある {len(rk)} 問）: recall@1 {r1:.3f} / recall@3 {r3:.3f} / MRR {mrr:.3f} / nDCG@3 {nd:.3f}")
    miss3 = [q["id"] for q in rk if M.recall_at_k([i for i, _ in bm.search(q["question"], 3)], set(q["gold_docs"]), 3) < 1]
    print(f"   上位 3 件に根拠が全部は入らなかった問い: {', '.join(miss3) or 'なし'}")

    rows = kit.select(qs if args.condition != "degraded" else [q for q in qs if q["gold_docs"]], args)
    template = J.load_prompt(os.path.join(HERE, "prompts", "answer.md"))
    ftemp = J.load_prompt(os.path.join(HERE, "prompts", "faithfulness.md"))
    model = L.model_name(args.model)

    def one(q):
        ids, ctx = contexts(q, bm, docs, args.condition)
        r = L.call(J.fill(template, abstain=abstain, context=ctx, question=q["question"]), provider=args.provider,
                   model=args.model, effort=args.effort, max_tokens=4000)
        ans = r.text.strip()
        c = check_answer(ans, q, abstain)
        c.update(check_answer_v2(ans, q, abstain))
        cited = sorted(set(re.findall(r"\[(D\d\d)\]", ans)))
        row = {"id": q["id"], "kind": q["kind"], "ctx": ids, "answer": ans, **c, "cited": cited,
               "cite_in_ctx": all(x in ids for x in cited), "cost_usd": r.cost_usd, "seconds": r.seconds}
        if args.judge and not c["abstained"]:
            obj, res = L.call_json(J.fill(ftemp, context=ctx, answer=ans), provider=args.provider,
                                   model=args.judge_model, effort=args.effort, max_tokens=4000)
            claims = obj.get("claims", [])
            row["claims"] = claims
            row["faithfulness"] = (sum(1 for x in claims if x.get("supported")) / len(claims)) if claims else None
            row["cost_usd"] += L.usage_of(res)["cost_usd"]
        return row

    with L.mock_handler(mock_for(pol)), L.tag(f"lab04/rag/{args.condition}/{kit.slug(model)}"):
        runs = kit.run_parallel(one, rows, workers=args.workers if args.provider == "anthropic" else 1)

    print("")
    tbl = []
    for kind in ("single", "multi", "unanswerable"):
        sub = [r for r in runs if r["kind"] == kind]
        if sub:
            k = sum(r["correct"] for r in sub)
            tbl.append([kind, len(sub), f"{k}/{len(sub)}", sum(r["abstained"] for r in sub)])
    print(kit.table(tbl, ["種類", "問", "正答", "断った"]))
    k = sum(r["correct"] for r in runs)
    lo, hi = stats.wilson(k, len(runs))
    print(f"正答 {k}/{len(runs)} = {kit.pct(k / len(runs))} 95%区間 {kit.ci_str(lo, hi)}")
    k2 = sum(r["correct_v2"] for r in runs)
    changed = [r["id"] for r in runs if r["correct"] != r["correct_v2"]]
    print(f"照合 v2（断りの判定と別表記を直したもの）: 正答 {k2}/{len(runs)} = {kit.pct(k2 / len(runs))}"
          f"　v1 と判定が変わった問い: {', '.join(changed) or 'なし'}")
    bad_cite = [r["id"] for r in runs if not r["cite_in_ctx"]]
    print(f"渡していない規程を引用した回答: {', '.join(bad_cite) or 'なし'}")
    if args.condition == "degraded":
        answered = [r for r in runs if not r["abstained"]]
        print(f"根拠を抜いた {len(runs)} 問のうち、断らずに答えた {len(answered)} 問: {', '.join(r['id'] for r in answered) or 'なし'}")
    faith = [r["faithfulness"] for r in runs if r.get("faithfulness") is not None]
    if faith:
        print(f"忠実さ（判定役 {args.judge_model}・断らなかった {len(faith)} 問）: 平均 {sum(faith) / len(faith):.3f}、"
              f"導けない主張を含む回答 {sum(1 for f in faith if f < 1)} 問")
        for r in runs:
            if r.get("faithfulness") is not None and r["faithfulness"] < 1:
                bad = [c["claim"] for c in r["claims"] if not c.get("supported")]
                print(f"   {r['id']}: {r['answer'][:70]!r} → 導けない: {bad[:2]}")
    wrong = [r for r in runs if not r["correct"]]
    for r in (wrong[:6] if args.condition != "degraded" else []):
        print(f"   × {r['id']} ({r['kind']}): {r['answer'][:90]!r}")
    cost = round(sum(r["cost_usd"] for r in runs), 4)
    print(f"費用 {cost} USD")
    out = kit.out_dir(HERE, args.provider)
    tag = f"{args.condition}_{kit.slug(model)}" + ("" if len(runs) in (30, 26) else f"_n{len(runs)}")
    kit.write_jsonl(os.path.join(out, f"runs_rag_{tag}.jsonl"), runs)
    res = {"model": model, "condition": args.condition, "provider": args.provider, "effort": L.effort_name(args.effort),
           "retrieval": {"recall@1": r1, "recall@3": r3, "mrr": mrr, "ndcg@3": nd, "miss@3": miss3},
           "n": len(runs), "correct": k, "ci": [lo, hi], "correct_v2": k2, "checker_changed": changed, "abstained": sum(r["abstained"] for r in runs),
           "faithfulness_mean": (sum(faith) / len(faith)) if faith else None, "cost_usd": cost}
    kit.write_json(os.path.join(out, f"summary_rag_{tag}.json"), res)
    return res


if __name__ == "__main__":
    main()
