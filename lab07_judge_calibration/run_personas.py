"""lab07-3 模擬の判定者（ペルソナ）で、判定の一致とガイドラインの改訂を確かめる（P7）。

🔴 ここの判定者は人ではありません。LLM に「人物像」と「ガイドライン」を与えて判定させた**模擬の判定者**です。
   この結果を「人の κ」と呼ばないこと。言えるのは「この人物像の書き方とガイドラインで、LLM の判定がどれだけそろうか」まで。
   人の判定者の本当のばらつき（疲れ・経験・文化・解釈の幅）の代わりにはならない（Wang et al. 2025 / Pavlick & Kwiatkowski 2019）。

    python run_personas.py                                         # 模擬（キー不要）
    python run_personas.py --provider anthropic --round v1         # 本物: 4 人 × 80 件（10 件ずつ）・ガイドライン v1
    python run_personas.py --provider anthropic --round v2 --adjudicate   # 改訂版 v2 で付け直し、割れた返信を裁定

手順（MATTER の「注釈 → 評価 → 改訂」の 1 周）
1. 初版のガイドライン v1 で、4 人の模擬判定者が 80 件に pass/fail を付ける
2. 割れた返信（dev の 38 件）を読み、公開の指針（特定商取引法の返品特約・ISO 10002・QA の評価項目・COPC）で v2 に書き直す
3. v2 で全員が付け直す。一致（Fleiss κ・Krippendorff α・2 人ずつの κ）が dev と test でどう変わるか
4. 割れた返信を、別のモデル（Opus）が v2 に照らして裁定 → 「裁定済みの基準」。各判定者・作った側のラベルと比べる
"""
from __future__ import annotations

import glob
import itertools
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from common import agreement as A, judge as J, kit, llm as L  # noqa: E402
from common.mockutil import coin  # noqa: E402
from run_calibrate import split  # noqa: E402

CODE = {"policy_error": "a", "no_next_step": "b", "blame_tone": "c", "false_promise": "d", None: "none"}
BATCH = 10


def personas():
    out = {}
    for p in sorted(glob.glob(os.path.join(HERE, "prompts", "personas", "P*.md"))):
        out[os.path.basename(p)[:-3]] = J.load_prompt(p)
    return out


def render(items):
    return "\n\n".join(f"### {r['id']}（受付日 {r['received']}）\n【問い合わせ】\n{r['inquiry']}\n【返信】\n{r['reply']}" for r in items)


def mock_persona(by_id):
    """模擬: 人物ごとのくせ（見逃しやすい欠陥・厳しさ）を、ガイドライン v2 では弱める。"""
    miss = {"P1": {"no_next_step": .5}, "P2": {"policy_error": .6, "false_promise": .3}, "P3": {}, "P4": {"policy_error": .5, "false_promise": .6}}
    strict = {"P1": .02, "P2": .02, "P3": .2, "P4": .05}

    def fn(system, messages, tools, model):
        msg = messages[-1]["content"] if messages else ""
        if not isinstance(msg, str) or "人物になりきり" not in msg:
            return None
        who = msg.split("# 判定者:")[0]
        pid = next((k for k in ("P1", "P2", "P3", "P4") if k in msg.split("使うガイドライン")[0]), None)
        if pid is None:
            for k, word in (("P1", "ベテラン"), ("P2", "新人"), ("P3", "コンプライアンス"), ("P4", "顧客体験")):
                if word in msg.split("使うガイドライン")[0]:
                    pid = k
        v2 = "改訂版" in msg
        labels = []
        for rid in [l.split("（")[0][4:] for l in msg.splitlines() if l.startswith("### RPL-")]:
            r = by_id[rid]
            d = r["defect"]
            m = miss[pid].get(d, 0) * (0.3 if v2 else 1)
            s = strict[pid] * (0.4 if v2 else 1)
            if d and coin("pm", pid, rid, v2) >= m:
                labels.append({"id": rid, "verdict": "fail", "reason_code": CODE[d], "note": "（模擬）"})
            elif not d and coin("ps", pid, rid, v2) < s:
                labels.append({"id": rid, "verdict": "fail", "reason_code": "b", "note": "（模擬）"})
            else:
                labels.append({"id": rid, "verdict": "pass", "reason_code": "none", "note": "（模擬）"})
        return json.dumps({"labels": labels}, ensure_ascii=False)
    return fn


def mock_adjudicator(system, messages, tools, model):
    msg = messages[-1]["content"] if messages else ""
    if not isinstance(msg, str) or "裁定する品質責任者" not in msg:
        return None
    fails = msg.split("【判定者の判断】")[1].count(": fail")
    return json.dumps({"verdict": "fail" if fails >= 2 else "pass", "reason_code": "none", "why": "（模擬）"}, ensure_ascii=False)


def label_round(reps, rnd, args, plist):
    guide = J.load_prompt(os.path.join(HERE, "prompts", f"guideline_{rnd}.md"))
    tmpl = J.load_prompt(os.path.join(HERE, "prompts", "annotate_batch.md"))
    jobs = []
    for pid, ptxt in plist.items():
        order = reps[:]
        random.Random(f"{pid}-order").shuffle(order)          # 人ごとに読む順番を変える（順番の影響を固定しない）
        for i in range(0, len(order), BATCH):
            jobs.append((pid, ptxt, order[i:i + BATCH]))

    def one(job):
        pid, ptxt, items = job
        prompt = J.fill(tmpl, persona=ptxt, guideline=guide, n=len(items), items=render(items))
        want = {r["id"] for r in items}

        def valid(o):
            got = {x.get("id") for x in o.get("labels", []) if x.get("verdict") in ("pass", "fail")}
            return None if got == want else f"10 件すべてに pass/fail を付けること（足りない: {sorted(want - got)[:3]}）"
        obj, res = L.call_json(prompt, provider=args.provider, model=args.model, effort=args.effort, validate=valid,
                               max_tokens=8000)
        return pid, obj["labels"], L.usage_of(res)["cost_usd"]

    with L.tag(f"lab07/personas/{rnd}/{kit.slug(L.model_name(args.model))}"):
        outs = kit.run_parallel(one, jobs, workers=args.workers if args.provider == "anthropic" else 1)
    labels, cost = {pid: {} for pid in plist}, 0.0
    for pid, labs, c in outs:
        cost += c
        for x in labs:
            labels[pid][x["id"]] = {"verdict": x["verdict"], "code": x.get("reason_code", "none"), "note": x.get("note", "")}
    return labels, cost


def agreement_report(labels, reps, ids, title):
    pids = sorted(labels)
    rows = []
    for a, b in itertools.combinations(pids, 2):
        k = A.cohen_kappa([labels[a][i]["verdict"] for i in ids], [labels[b][i]["verdict"] for i in ids])
        rows.append([f"{a[:2]}-{b[:2]}", f"{k:.2f}"])
    fk = A.fleiss_kappa([[labels[p][i]["verdict"] for p in pids] for i in ids])
    al = A.krippendorff_alpha([[labels[p][i]["verdict"] for p in pids] for i in ids])
    unan = sum(1 for i in ids if len({labels[p][i]["verdict"] for p in pids}) == 1)
    by = {r["id"]: r for r in reps}
    vs = {p[:2]: A.cohen_kappa([labels[p][i]["verdict"] for i in ids], [by[i]["label"] for i in ids]) for p in pids}
    print(f"   {title}: Fleiss κ {fk:.3f} / α {al:.3f} / 全員一致 {unan}/{len(ids)} / 2 人ずつ " + " ".join(f"{a}:{b}" for a, b in rows))
    return {"fleiss": fk, "alpha": al, "unanimous": unan, "n": len(ids), "pairwise": dict(rows), "vs_construction": vs}


def main(argv=None) -> dict:
    p = kit.parser("lab07 模擬の判定者")
    p.add_argument("--round", default="both", choices=["v1", "v2", "both"])
    p.add_argument("--adjudicate", action="store_true")
    p.add_argument("--adj-model", default="claude-opus-5-5")
    args = p.parse_args(argv)
    if args.model is None:
        args.model = "claude-sonnet-5-5"          # 判定者は Sonnet（費用）。裁定は別のモデル（Opus）
    kit.banner("lab07-3 模擬の判定者（🔴 人ではない）", args)
    reps = kit.load_jsonl("replies.jsonl")
    by_id = {r["id"]: r for r in reps}
    dev, test = split(reps)
    plist = personas()
    rounds = ["v1", "v2"] if args.round == "both" else [args.round]
    out = kit.out_dir(HERE, args.provider)
    res = {"model": L.model_name(args.model), "provider": args.provider, "personas": list(plist), "rounds": {}}
    with L.mock_handler(mock_persona(by_id)), L.mock_handler(mock_adjudicator):
        for rnd in rounds:
            labels, cost = label_round(reps, rnd, args, plist)
            kit.write_json(os.path.join(out, f"persona_labels_{rnd}.json"), labels)
            print(f"\n■ ガイドライン {rnd}（費用 {cost:.4f} USD）")
            r = {"dev": agreement_report(labels, reps, [x["id"] for x in dev], "dev 38"),
                 "test": agreement_report(labels, reps, [x["id"] for x in test], "test 42"),
                 "all": agreement_report(labels, reps, [x["id"] for x in reps], "全 80"), "cost_usd": cost}
            print("   作った側のラベルとの κ: " + " / ".join(f"{k} {v:.2f}" for k, v in r["all"]["vs_construction"].items()))
            print("   欠陥の種類ごとに fail を付けた人数（4 人中、平均）:")
            for d in ["policy_error", "no_next_step", "blame_tone", "false_promise", None]:
                sub = [x for x in reps if x["defect"] == d]
                avg = sum(sum(labels[pp][x["id"]]["verdict"] == "fail" for pp in plist) for x in sub) / len(sub)
                per = " ".join(f"{pp[:2]}:{sum(labels[pp][x['id']]['verdict'] == 'fail' for x in sub)}/{len(sub)}" for pp in plist)
                print(f"     {str(d or '(欠陥なし)'):14s} {avg:.2f}   {per}")
            res["rounds"][rnd] = r
            if args.adjudicate and rnd == rounds[-1]:
                res["adjudication"] = adjudicate(labels, reps, args, out)
    if os.path.exists(os.path.join(out, "persona_labels_v1.json")) and os.path.exists(os.path.join(out, "persona_labels_v2.json")):
        l1 = kit.read_json(os.path.join(out, "persona_labels_v1.json"))
        l2 = kit.read_json(os.path.join(out, "persona_labels_v2.json"))
        ids = [x["id"] for x in reps]
        f1 = A.fleiss_kappa([[l1[pp][i]["verdict"] for pp in sorted(l1)] for i in ids])
        f2 = A.fleiss_kappa([[l2[pp][i]["verdict"] for pp in sorted(l2)] for i in ids])
        print(f"\n改める工程の前後: Fleiss κ（全 80）{f1:.3f} → {f2:.3f}")
        res["fleiss_v1_to_v2"] = [f1, f2]
    kit.write_json(os.path.join(out, "summary_personas.json"), res)
    return res


def adjudicate(labels, reps, args, out):
    guide = J.load_prompt(os.path.join(HERE, "prompts", "guideline_v2.md"))
    tmpl = J.load_prompt(os.path.join(HERE, "prompts", "adjudicate.md"))
    pids = sorted(labels)
    split_ids = [r for r in reps if len({labels[p][r["id"]]["verdict"] for p in pids}) > 1]

    def one(r):
        votes = "\n".join(f"- {p}: {labels[p][r['id']]['verdict']}（{labels[p][r['id']]['code']}）{labels[p][r['id']]['note']}" for p in pids)
        obj, res = L.call_json(J.fill(tmpl, guideline=guide, received=r["received"], inquiry=r["inquiry"], reply=r["reply"], votes=votes),
                               provider=args.provider, model=args.adj_model, effort=args.effort, max_tokens=4000,
                               validate=lambda o: None if o.get("verdict") in ("pass", "fail") else "verdict")
        return r["id"], obj, L.usage_of(res)["cost_usd"]

    with L.tag(f"lab07/adjudicate/{kit.slug(args.adj_model)}"):
        outs = kit.run_parallel(one, split_ids, workers=args.workers if args.provider == "anthropic" else 1)
    adj = {i: o for i, o, _ in outs}
    cost = sum(c for _, _, c in outs)
    ref = {}
    for r in reps:
        vs = {labels[p][r["id"]]["verdict"] for p in pids}
        ref[r["id"]] = vs.pop() if len(vs) == 1 else adj[r["id"]]["verdict"]
    ids = [r["id"] for r in reps]
    by = {r["id"]: r for r in reps}
    print(f"\n■ 裁定（{args.adj_model}、割れた {len(split_ids)} 件、費用 {cost:.4f} USD）→ 裁定済みの基準")
    vs = {}
    for p in pids:
        vs[p[:2]] = A.cohen_kappa([labels[p][i]["verdict"] for i in ids], [ref[i] for i in ids])
    print("   各判定者と裁定済みの基準の κ: " + " / ".join(f"{k} {v:.2f}" for k, v in vs.items()))
    kc = A.cohen_kappa([ref[i] for i in ids], [by[i]["label"] for i in ids])
    diff = [i for i in ids if ref[i] != by[i]["label"]]
    print(f"   裁定済みの基準と、作った側のラベル: κ {kc:.3f}、食い違い {len(diff)} 件")
    for i in diff:
        print(f"     {i}（作った欠陥 {by[i]['defect']}・作った側 {by[i]['label']} → 裁定 {ref[i]}）: {adj.get(i, {}).get('why', '全員一致')}")
    # lab07-1 の LLM 判定（依頼文 v2）とも比べる
    llm = {}
    for f in sorted(glob.glob(os.path.join(HERE, "out", "runs_calib_v2_*_sonnet-5-5*.jsonl"))):
        for x in kit.read_jsonl(f):
            llm[x["id"]] = x["judge"]
    kl = None
    if len(llm) == len(ids):
        kl = A.cohen_kappa([llm[i] for i in ids], [ref[i] for i in ids])
        print(f"   lab07-1 の自動判定（Sonnet・依頼文 v2）と裁定済みの基準: κ {kl:.3f}")
    kit.write_json(os.path.join(out, "adjudicated_reference.json"),
                   {"reference": ref, "adjudications": adj, "split_ids": [r["id"] for r in split_ids]})
    return {"split": len(split_ids), "cost_usd": cost, "vs_reference": vs, "ref_vs_construction": kc,
            "ref_vs_construction_diff": diff, "llm_judge_vs_reference": kl}


if __name__ == "__main__":
    main()
