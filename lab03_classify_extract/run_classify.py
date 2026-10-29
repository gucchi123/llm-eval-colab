"""lab03-1 問い合わせ分類を測る（P3・UC1）。

    python run_classify.py                                   # 模擬（キー不要）
    python run_classify.py --provider anthropic --all        # 本物（既定 claude-opus-5-5・effort high）
    python run_classify.py --provider anthropic --all --model claude-sonnet-5-5
    python run_classify.py --provider replay --all           # 講師の記録を再生（費用 0）
    python run_classify.py --provider anthropic --only INQ-0025,INQ-0128   # デモ

出すもの: 正答率（Wilson 区間）・重み付き正答率・マクロ F1・ラベル別の適合率/再現率・混同行列・
難しさ別・自信と正答のずれ（ECE）・費用と待ち時間。out/summary_classify_<model>.json と runs_…jsonl。
"""
from __future__ import annotations

import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import kit, llm as L, metrics as M, stats  # noqa: E402
from common.mockutil import coin, skill  # noqa: E402

LABELS = ["返品・交換", "修理・故障", "配送", "請求・支払い", "使い方", "会員・解約"]
CONFUSE = {"返品・交換": "修理・故障", "修理・故障": "返品・交換", "配送": "請求・支払い", "請求・支払い": "配送",
           "使い方": "修理・故障", "会員・解約": "使い方"}


def system_prompt() -> str:
    with open(os.path.join(HERE, "prompts", "classify.md"), encoding="utf-8") as f:
        return f.read().format(guide=kit.load_text("guide_inquiries.md"))


def _render(r):
    ch = {"web": "Web フォーム", "mail": "メール", "phone": "電話"}[r["channel"]]
    return f"受付日: {r['received']}\n窓口: {ch}\n---\n{r['text']}"


def mock_for(rows):
    """模擬の分類役: 正解を知っていて、腕前の確率で当てる。規則が要る問いは少し外しやすい。"""
    by_text = {_render(r): r for r in rows}

    def fn(system, messages, tools, model):
        if not system or "分類の手引き" not in system:
            return None
        r = by_text.get(messages[-1]["content"])
        if r is None:
            return None
        p = skill(model) - {"easy": 0, "hard": 0.2}.get(r["difficulty"], 0.08)
        ok = coin("cls", model, r["id"]) < p
        lab = r["label"] if ok else CONFUSE[r["label"]]
        conf = 90 if coin("conf", model, r["id"]) < 0.7 else 70
        return f'{{"label": "{lab}", "rule": "R2", "confidence": {conf}}}'
    return fn


def classify_one(r, args):
    def valid(o):
        return None if isinstance(o, dict) and o.get("label") in LABELS else f"label は {LABELS} のどれか"
    try:
        obj, results = L.call_json(_render(r), system=system_prompt(), provider=args.provider, model=args.model,
                                   effort=args.effort, validate=valid, max_tokens=4000)
        pred, conf, rule = obj["label"], obj.get("confidence"), obj.get("rule")
    except (L.BudgetExceeded, L.CacheMiss):
        raise   # 予算切れ・記録なしは「無効な出力」に数えない
    except RuntimeError as e:
        pred, conf, rule, results = "(無効)", None, None, []
        print(f"   {r['id']}: {e}")
    u = L.usage_of(results)
    return {"id": r["id"], "label": r["label"], "pred": pred, "correct": int(pred == r["label"]),
            "confidence": conf, "rule": rule, "difficulty": r["difficulty"], "scenario": r["facts"]["scenario"],
            "cost_usd": u["cost_usd"], "seconds": u["seconds"], "out_tokens": u["out"], "cached": u["cached"]}


def report(runs, weights=None) -> dict:
    truth = [x["label"] for x in runs]
    pred = [x["pred"] for x in runs]
    rep = M.classification_report(truth, pred, LABELS)
    k = sum(x["correct"] for x in runs)
    lo, hi = stats.wilson(k, len(runs))
    rep["accuracy_ci"] = [lo, hi]
    rep["by_difficulty"] = {}
    for d in ("easy", "rule", "multi", "hard"):
        sub = [x for x in runs if x["difficulty"] == d]
        if sub:
            kk = sum(x["correct"] for x in sub)
            rep["by_difficulty"][d] = {"n": len(sub), "accuracy": kk / len(sub), "ci": stats.wilson(kk, len(sub))}
    if weights:
        num = sum(weights.get(f"{x['label']}|{x['difficulty']}", 1) * x["correct"] for x in runs)
        den = sum(weights.get(f"{x['label']}|{x['difficulty']}", 1) for x in runs)
        rep["weighted_accuracy"] = num / den
    confs = [x["confidence"] / 100 for x in runs if isinstance(x.get("confidence"), (int, float))]
    corr = [x["correct"] for x in runs if isinstance(x.get("confidence"), (int, float))]
    if confs:
        e, tbl = M.ece(confs, corr, bins=5)
        rep["ece"], rep["reliability"] = e, tbl
    rep["by_scenario"] = {}
    for x in runs:
        v = rep["by_scenario"].setdefault(x["scenario"], {"n": 0, "correct": 0})
        v["n"] += 1
        v["correct"] += x["correct"]
    rep["confusion"] = M.confusion(truth, pred, LABELS)
    rep["cost_usd"] = round(sum(x["cost_usd"] for x in runs), 4)
    rep["seconds_p50"] = stats.percentile([x["seconds"] for x in runs], 0.5)
    rep["seconds_p95"] = stats.percentile([x["seconds"] for x in runs], 0.95)
    rep["errors"] = [{"id": x["id"], "label": x["label"], "pred": x["pred"], "scenario": x["scenario"]}
                     for x in runs if not x["correct"]]
    return rep


def print_report(rep, model):
    print(f"\n正答率 {kit.pct(rep['accuracy'])} 95%区間 {kit.ci_str(*rep['accuracy_ci'])}  (n={rep['n']})"
          + (f" / 本番の割合に戻した正答率 {kit.pct(rep['weighted_accuracy'])}" if "weighted_accuracy" in rep else ""))
    print(f"マクロ F1 {rep['macro_f1']:.3f}")
    rows = [[c, v["support"], f"{v['precision']:.2f}", f"{v['recall']:.2f}", f"{v['f1']:.2f}"] for c, v in rep["per_class"].items()]
    print(kit.table(rows, ["ラベル", "件数", "適合率", "再現率", "F1"]))
    print("難しさ別: " + " / ".join(f"{d} {kit.pct(v['accuracy'])} (n={v['n']})" for d, v in rep["by_difficulty"].items()))
    if "hard" in rep["by_difficulty"]:
        print("種類別: " + " / ".join(f"{k} {v['correct']}/{v['n']}" for k, v in rep["by_scenario"].items()))
    print("\n混同行列（行=正解, 列=予測）")
    cols = LABELS + ["(無効)"]
    rows = [[t] + [rep["confusion"][t][p] or "." for p in cols] for t in LABELS]
    print(kit.table(rows, ["正解＼予測"] + [c[:2] for c in cols]))
    if "ece" in rep:
        print(f"\n自信と正答のずれ ECE = {rep['ece']:.3f}  "
              + " ".join(f"[{b['bin']}: n={b['n']}" + (f" 自信{b['conf']:.2f} 正答{b['acc']:.2f}]" if b["n"] else "]")
                         for b in rep["reliability"]))
    print(f"\n費用 {rep['cost_usd']:.4f} USD / 待ち時間 p50 {rep['seconds_p50']:.1f}s p95 {rep['seconds_p95']:.1f}s"
          + "（再生のときも、元の実行の値）")
    if rep["errors"]:
        print("外した問い（先頭 8 件）: " + ", ".join(f"{e['id']}({e['label']}→{e['pred']}, {e['scenario']})"
                                            for e in rep["errors"][:8]))


def main(argv=None) -> dict:
    p = kit.parser("lab03 問い合わせ分類", default_limit=12)
    p.add_argument("--set", default="v1", choices=["v1", "v2"], help="v1=型から作った 120 件 / v2=境目を突く難問 48 件")
    args = p.parse_args(argv)
    kit.banner(f"lab03-1 問い合わせ分類（試験セット {args.set}）", args)
    golden = kit.load_jsonl("golden_inquiries.jsonl" if args.set == "v1" else "golden_inquiries_v2_hard.jsonl")
    rows = kit.select(golden, args)
    model = L.model_name(args.model)
    weights = None
    w_path = os.path.join(os.path.dirname(HERE), "lab02_golden_set", "out", "summary.json")
    if os.path.exists(w_path):
        weights = kit.read_json(w_path)["weights"]
    with L.mock_handler(mock_for(golden)), L.tag(f"lab03/classify/{args.set}/{kit.slug(model)}"):
        runs = kit.run_parallel(lambda r: classify_one(r, args), rows,
                                workers=args.workers if args.provider == "anthropic" else 1)
    rep = report(runs, weights if args.set == "v1" else None)
    print_report(rep, model)
    out = kit.out_dir(HERE, args.provider)
    tag = ("" if args.set == "v1" else "v2_") + kit.slug(model) + ("" if len(rows) == len(golden) else f"_n{len(rows)}")
    kit.write_jsonl(os.path.join(out, f"runs_classify_{tag}.jsonl"), runs)
    kit.write_json(os.path.join(out, f"summary_classify_{tag}.json"), {"model": model, "set": args.set, "effort": L.effort_name(args.effort),
                                                                         "provider": args.provider, **rep})
    print(f"→ {os.path.relpath(out, HERE)}/summary_classify_{tag}.json")
    return rep


if __name__ == "__main__":
    main()
