"""lab09-2 回帰の関門（CI ゲート）。基準（いまの本番）と候補を、同じ問いで比べて「出してよいか」を決める。

    python gate.py                         # 既定の組（講師の実行があれば out/、無ければ模擬）
    python gate.py --baseline <runs.jsonl> --candidate <runs.jsonl>

決まり（gate_config.json）
1. 非劣性: 候補 − 基準 の正答率の差の下限（片側 95%）が −margin より上
   食い違いが 0 件のときも「差は 0」とは言わず、3 の法則に近い Wilson の上限で幅を付ける
2. 層の床: どの種類（scenario）も、基準より floor ポイント以上は落ちない（4 件以上ある種類だけ）
3. 無効な出力（ラベル以外）が 0 件
1 つでも満たさなければ終了コード 1（CI ならそこで止まる）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from common import kit, stats  # noqa: E402


def load(path):
    return {r["id"]: r for r in kit.read_jsonl(path)}


def evaluate(base: dict, cand: dict, cfg: dict) -> dict:
    ids = sorted(set(base) & set(cand))
    a = [base[i]["correct"] for i in ids]
    b = [cand[i]["correct"] for i in ids]
    n = len(ids)
    only_base, only_cand = stats.discordant(a, b)
    diff = (sum(b) - sum(a)) / n
    if only_base + only_cand:
        lo = stats.paired_bootstrap(a, b, conf=0.90, seed=0)["lo"]
    else:
        lo = -stats.wilson(0, n, conf=0.90)[1]
    p = stats.mcnemar_exact(only_base, only_cand)
    checks = []
    checks.append({"name": f"非劣性（差の下限 > −{cfg['margin']:.2f}）", "ok": lo > -cfg["margin"],
                   "detail": f"差 {diff:+.3f}、片側95%下限 {lo:+.3f}、基準だけ正解 {only_base} / 候補だけ正解 {only_cand}、McNemar p={p:.3g}"})
    worst = []
    scen = sorted({base[i]["scenario"] for i in ids})
    for s in scen:
        sid = [i for i in ids if base[i]["scenario"] == s]
        if len(sid) < cfg["min_slice"]:
            continue
        ab = sum(base[i]["correct"] for i in sid) / len(sid)
        cb = sum(cand[i]["correct"] for i in sid) / len(sid)
        worst.append((s, len(sid), ab, cb))
    bad = [w for w in worst if w[2] - w[3] > cfg["floor"]]
    checks.append({"name": f"層の床（どの種類も {int(cfg['floor'] * 100)} ポイント超は落ちない）", "ok": not bad,
                   "detail": "; ".join(f"{s} {ab:.0%}→{cb:.0%} (n={k})" for s, k, ab, cb in (bad or worst[:3]))})
    invalid = sum(1 for i in ids if cand[i]["pred"] == "(無効)")
    checks.append({"name": "無効な出力 0 件", "ok": invalid == 0, "detail": f"{invalid} 件"})
    cost_b = sum(base[i].get("cost_usd", 0) for i in ids)
    cost_c = sum(cand[i].get("cost_usd", 0) for i in ids)
    return {"n": n, "base_acc": sum(a) / n, "cand_acc": sum(b) / n, "diff": diff, "lower": lo, "mcnemar_p": p,
            "checks": checks, "pass": all(c["ok"] for c in checks), "cost_base": cost_b, "cost_cand": cost_c,
            "slices": worst}


def default_pairs():
    """講師の本物の実行があればそれ、無ければ模擬の出力の組。"""
    l3 = os.path.join(ROOT, "lab03_classify_extract")
    real = [("短くした依頼文（Sonnet・v2 難問）",
             os.path.join(l3, "out", "runs_classify_v2_sonnet-5-5.jsonl"), os.path.join(HERE, "out", "runs_candidate_v2_sonnet-5-5.jsonl")),
            ("短くした依頼文（Opus・v2 難問）",
             os.path.join(l3, "out", "runs_classify_v2_opus-5-5.jsonl"), os.path.join(HERE, "out", "runs_candidate_v2_opus-5-5.jsonl")),
            ("Opus → Sonnet に替える（v1 120 件）",
             os.path.join(l3, "out", "runs_classify_opus-5-5.jsonl"), os.path.join(l3, "out", "runs_classify_sonnet-5-5.jsonl"))]
    have = [x for x in real if os.path.exists(x[1]) and os.path.exists(x[2])]
    if have:
        return have, "out"
    mock = [("短くした依頼文（模擬）", os.path.join(l3, "out_mock", "runs_classify_v2_opus-5-5.jsonl"),
             os.path.join(HERE, "out_mock", "runs_candidate_v2_opus-5-5.jsonl"))]
    return [x for x in mock if os.path.exists(x[1]) and os.path.exists(x[2])], "out_mock"


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline")
    p.add_argument("--candidate")
    p.add_argument("--config", default=os.path.join(HERE, "gate_config.json"))
    args = p.parse_args(argv)
    cfg = kit.read_json(args.config)
    pairs, where = ([("指定の組", args.baseline, args.candidate)], "out") if args.baseline else default_pairs()
    if not pairs:
        print("比べる組がありません。先に lab03 の run_classify.py と run_candidate.py を回してください")
        return 2
    kit.banner(f"lab09-2 回帰の関門（{where}）")
    results, all_ok = [], True
    for name, b, c in pairs:
        r = evaluate(load(b), load(c), cfg)
        print(f"\n■ {name}  n={r['n']}  基準 {kit.pct(r['base_acc'])} → 候補 {kit.pct(r['cand_acc'])}"
              f"  費用 {r['cost_base']:.4f} → {r['cost_cand']:.4f} USD")
        for ch in r["checks"]:
            print(f"   {'✓' if ch['ok'] else '✗'} {ch['name']}: {ch['detail']}")
        print(f"   判定: {'通す' if r['pass'] else '止める'}")
        results.append({"name": name, "baseline": os.path.relpath(b, ROOT), "candidate": os.path.relpath(c, ROOT), **r})
        all_ok &= r["pass"]
    os.makedirs(os.path.join(HERE, where), exist_ok=True)
    kit.write_json(os.path.join(HERE, where, "gate_result.json"), results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
