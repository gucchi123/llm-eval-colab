"""lab06-1 LLM 判定の偏りを測る（P6・UC5）。位置と長さ。

    python run_bias.py                                              # 模擬
    python run_bias.py --provider anthropic --all --model claude-sonnet-5-5               # 判定役 = Sonnet
    python run_bias.py --provider anthropic --all --model claude-sonnet-5-5 --prompt naive # 素朴な依頼文

組（data/pairs.jsonl、52 組）
- equal (20)      : 中身が同じで言い回しだけ違う。公平なら、先に出た方が勝つ割合は 50% 前後で、引き分けが多いはず
- length (20)     : 中身が同じで、片方に中身の無い定型文を 4 文足しただけ。公平なら長い方が勝つ理由は無い
- long_wrong (12) : 長いが規程を誤っている vs 短く正しい。正しい方を選べるか
どの組も、順番を入れ替えて 2 回判定する（入れ替えて結論が変わったら引き分け扱い）。
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import judge as J, kit, llm as L, stats  # noqa: E402


def main(argv=None) -> dict:
    p = kit.parser("lab06 判定の偏り", default_limit=None)
    p.add_argument("--prompt", default="careful", choices=["careful", "naive"])
    p.add_argument("--kinds", default="equal,length,long_wrong")
    args = p.parse_args(argv)
    kit.banner(f"lab06-1 判定の偏り（依頼文 {args.prompt}）", args)
    template = J.load_prompt(os.path.join(HERE, "prompts", "pairwise.md" if args.prompt == "careful" else "pairwise_naive.md"))
    kinds = args.kinds.split(",")
    pairs = [x for x in kit.load_jsonl("pairs.jsonl") if x["kind"] in kinds]
    if args.limit and not args.all:   # 種類ごとに先頭 limit 組
        pairs = [x for k in kinds for x in [y for y in pairs if y["kind"] == k][: args.limit]]
    pairs = kit.select(pairs, argparse_ns_all(args))
    model = L.model_name(args.model)

    def one(x):
        inq = f"受付日: {x['received']}\n{x['inquiry']}"
        r = J.pairwise(template, inq, x["a"], x["b"], provider=args.provider, model=args.model, effort=args.effort)
        u = L.usage_of(r.pop("results"))
        return {"id": x["id"], "kind": x["kind"], **r, "cost_usd": u["cost_usd"]}

    with L.tag(f"lab06/bias/{args.prompt}/{kit.slug(model)}"):
        runs = kit.run_parallel(one, pairs, workers=args.workers if args.provider == "anthropic" else 1)

    res = {}
    for kind in kinds:
        sub = [r for r in runs if r["kind"] == kind]
        if not sub:
            continue
        judg = [w for r in sub for w in r["first_pos_won"]]
        decided = [r for r in sub for v in (r["first_order"], r["swapped"]) if v != "tie"]
        first_wins = sum(1 for r in sub for i, v in enumerate((r["first_order"], r["swapped"]))
                         if v != "tie" and r["first_pos_won"][i])
        n_dec = len(decided)
        cons = sum(r["consistent"] for r in sub)
        fin = {k: sum(1 for r in sub if r["final"] == k) for k in ("x", "y", "tie")}
        res[kind] = {"pairs": len(sub), "judgments": len(judg), "decided": n_dec, "first_pos_wins": first_wins,
                     "first_pos_rate": first_wins / n_dec if n_dec else float("nan"),
                     "first_pos_ci": stats.wilson(first_wins, n_dec) if n_dec else [0, 1],
                     "consistent": cons, "final": fin,
                     "per_order_y": sum(1 for r in sub for v in (r["first_order"], r["swapped"]) if v == "y")}
    print("")
    if "equal" in res:
        e = res["equal"]
        print(f"[位置] 同じ質の組 {e['pairs']} 組 × 2 回: 勝ち負けを付けた {e['decided']} 回のうち、先に出た方が勝った {e['first_pos_wins']} 回 "
              f"= {kit.pct(e['first_pos_rate'])} 95%区間 {kit.ci_str(*e['first_pos_ci'])}（公平なら 50%）")
        print(f"       入れ替えても同じ結論 {e['consistent']}/{e['pairs']}、最終の引き分け {e['final']['tie']}/{e['pairs']}")
    if "length" in res:
        e = res["length"]
        n = e["judgments"]
        print(f"[長さ] 中身が同じで長いだけの組 {e['pairs']} 組 × 2 回: 長い方を選んだ {e['per_order_y']}/{n} 回 = "
              f"{kit.pct(e['per_order_y'] / n)} 95%区間 {kit.ci_str(*stats.wilson(e['per_order_y'], n))}")
        print(f"       最終（2 回そろったとき）: 長い方 {e['final']['y']} / 短い方 {e['final']['x']} / 引き分け {e['final']['tie']}")
    if "long_wrong" in res:
        e = res["long_wrong"]
        print(f"[長いが誤り] {e['pairs']} 組: 短く正しい方を選んだ {e['final']['x']} / 長く誤った方 {e['final']['y']} / 引き分け {e['final']['tie']}"
              f"（1 回ごとでは誤った方を選んだのが {e['per_order_y']}/{e['judgments']} 回）")
    cost = round(sum(r["cost_usd"] for r in runs), 4)
    print(f"費用 {cost} USD（判定 {2 * len(runs)} 回）")
    out = kit.out_dir(HERE, args.provider)
    tag = f"{args.prompt}_{kit.slug(model)}" + ("" if len(runs) == 52 or args.kinds != "equal,length,long_wrong" else f"_n{len(runs)}")
    kit.write_jsonl(os.path.join(out, f"runs_bias_{tag}.jsonl"), runs)
    kit.write_json(os.path.join(out, f"summary_bias_{tag}.json"), {"model": model, "prompt": args.prompt, "provider": args.provider,
                                                                     "effort": L.effort_name(args.effort), "result": res, "cost_usd": cost})
    return res


def argparse_ns_all(args):
    """--limit は上で種類ごとに使ったので、ここでは --only だけを効かせる。"""
    class _A:
        only = args.only
        limit = None
        all = True
    return _A()


if __name__ == "__main__":
    main()
