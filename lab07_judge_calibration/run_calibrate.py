"""lab07-1 LLM 判定を人のラベルに合わせる（P7・UC5）。

    python run_calibrate.py                                       # 模擬
    python run_calibrate.py --provider anthropic --model claude-sonnet-5-5 --split dev --prompt v1
    python run_calibrate.py --provider anthropic --model claude-sonnet-5-5 --split dev --prompt v2
    python run_calibrate.py --provider anthropic --model claude-sonnet-5-5 --split test --prompt v2   # 最後に 1 回だけ

手順（Shankar et al. 2024 / apr 講座 lab05 の流れを、件数と区間つきで）
1. 返信 80 件を dev 40 / test 40 に分ける（欠陥の種類で層別、seed 固定）
2. dev で判定の依頼文を直す（v1 → v2）。test は最後まで見ない
3. test で 1 回だけ測る: TPR（不合格を見つける率）・TNR（合格を合格とする率）・κ
4. 判定が数えた不合格率を、TPR/TNR で本当の率に直す（Rogan-Gladen）。区間はブートストラップ
"""
from __future__ import annotations

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import agreement as A, judge as J, kit, llm as L, stats  # noqa: E402


def split(replies, seed=5):
    rng = random.Random(seed)
    by = {}
    for r in replies:
        by.setdefault(r["defect"] or "none", []).append(r)
    dev, test = [], []
    for k in sorted(by):
        v = by[k][:]
        rng.shuffle(v)
        h = len(v) // 2
        dev += v[:h]
        test += v[h:]
    return sorted(dev, key=lambda r: r["id"]), sorted(test, key=lambda r: r["id"])


def main(argv=None) -> dict:
    p = kit.parser("lab07 判定の校正")
    p.add_argument("--prompt", default="v2", choices=["v1", "v2"])
    p.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    args = p.parse_args(argv)
    kit.banner(f"lab07-1 判定を人に合わせる（依頼文 {args.prompt} / {args.split}）", args)
    replies = kit.load_jsonl("replies.jsonl")
    dev, test = split(replies)
    rows = {"dev": dev, "test": test, "all": replies}[args.split]
    rows = kit.select(rows, args)
    template = J.load_prompt(os.path.join(HERE, "prompts", f"pointwise_{args.prompt}.md"))
    policy = kit.load_text("reply_policy.md")
    model = L.model_name(args.model)

    def one(r):
        v, res = J.pointwise(template, inquiry=r["inquiry"], reply=r["reply"], policy=policy, received=r["received"],
                             provider=args.provider, model=args.model, effort=args.effort)
        u = L.usage_of(res)
        return {"id": r["id"], "defect": r["defect"], "label": r["label"], "judge": v, "cost_usd": u["cost_usd"]}

    with L.tag(f"lab07/calib/{args.prompt}/{args.split}/{kit.slug(model)}"):
        runs = kit.run_parallel(one, rows, workers=args.workers if args.provider == "anthropic" else 1)
    truth = [r["label"] for r in runs]
    pred = [r["judge"] for r in runs]
    m = A.tpr_tnr(pred, truth, positive="fail")
    k = A.cohen_kappa(pred, truth)
    print(f"\nn={len(runs)}（不合格 {truth.count('fail')} / 合格 {truth.count('pass')}）")
    print(f"TPR（不合格を見つけた）{m['tp']}/{m['tp'] + m['fn']} = {kit.pct(m['tpr'])} 95%区間 {kit.ci_str(*stats.wilson(m['tp'], m['tp'] + m['fn']))}")
    print(f"TNR（合格を合格とした）{m['tn']}/{m['tn'] + m['fp']} = {kit.pct(m['tnr'])} 95%区間 {kit.ci_str(*stats.wilson(m['tn'], m['tn'] + m['fp']))}")
    print(f"一致 {kit.pct(sum(a == b for a, b in zip(pred, truth)) / len(runs))} / Cohen κ = {k:.3f}（{A.landis_koch(k)}）")
    ref_path = os.path.join(HERE, "out", "adjudicated_reference.json")
    if os.path.exists(ref_path) and args.provider != "mock":
        ref = kit.read_json(ref_path)["reference"]
        mr = A.tpr_tnr(pred, [ref[r["id"]] for r in runs], positive="fail")
        kr = A.cohen_kappa(pred, [ref[r["id"]] for r in runs])
        print(f"（参考）裁定済みの基準（lab07-3）と比べると: TPR {mr['tp']}/{mr['tp'] + mr['fn']}・TNR {mr['tn']}/{mr['tn'] + mr['fp']}・κ {kr:.3f}"
              "　← 作った側のラベルに誤りが 2 件あった（RPL-009・RPL-013）")
    print("\n欠陥の種類ごとの見逃し・誤検出:")
    for d in ["policy_error", "no_next_step", "blame_tone", "false_promise", None]:
        sub = [r for r in runs if r["defect"] == d]
        if sub:
            if d:
                miss = sum(r["judge"] == "pass" for r in sub)
                print(f"   {d:14s} 見逃し {miss}/{len(sub)}")
            else:
                fp = sum(r["judge"] == "fail" for r in sub)
                print(f"   {'(欠陥なし)':14s} 誤って fail {fp}/{len(sub)}")
    # 不合格率の補正: 校正（TPR/TNR）は dev のラベル付きの結果から、補正をかけるのは test の判定（ラベルを見ないふり）
    # dev の結果が無いとき（dev 自身を回したときなど）は同じ組で校正する → 補正値は本当の率と必ず一致する（自明）
    import glob
    cal = None
    if args.split == "test":
        pat = f"runs_calib_{args.prompt}_dev_{kit.slug(model)}*.jsonl"
        cand = sorted(glob.glob(os.path.join(kit.out_dir(HERE, args.provider), pat)))
        if not cand and args.provider != "mock":
            cand = sorted(glob.glob(os.path.join(HERE, "out", pat)))
        if cand:
            cal = kit.read_jsonl(cand[0])
    if cal:
        rg = A.corrected_prevalence_ci([r["judge"] for r in cal], [r["label"] for r in cal], pred, positive="fail", seed=3)
        print(f"\n（校正は dev {len(cal)} 件の TPR/TNR、補正するのは test の判定）")
    else:
        rg = A.corrected_prevalence_ci(pred, truth, pred, positive="fail", seed=3)
        print("\n（同じ組で校正しているので、補正値は本当の率と一致する。本番では別の組で校正する）")
    true_rate = truth.count("fail") / len(truth)
    print(f"判定が数えた不合格率 {kit.pct(rg['observed'])} → 補正 {kit.pct(rg['corrected'])} "
          f"95%区間 {kit.ci_str(rg['lo'], rg['hi'])}（本当の率 {kit.pct(true_rate)}）")
    cost = round(sum(r["cost_usd"] for r in runs), 4)
    print(f"費用 {cost} USD")
    out = kit.out_dir(HERE, args.provider)
    tag = f"{args.prompt}_{args.split}_{kit.slug(model)}" + ("" if not (args.limit or args.only) else f"_n{len(runs)}")
    kit.write_jsonl(os.path.join(out, f"runs_calib_{tag}.jsonl"), runs)
    res = {"model": model, "prompt": args.prompt, "split": args.split, "provider": args.provider,
           "effort": L.effort_name(args.effort), "n": len(runs), **m, "kappa": k, "prevalence": rg,
           "true_rate": true_rate, "cost_usd": cost}
    kit.write_json(os.path.join(out, f"summary_calib_{tag}.json"), res)
    return res


if __name__ == "__main__":
    main()
