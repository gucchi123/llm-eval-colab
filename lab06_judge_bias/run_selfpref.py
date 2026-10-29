"""lab06-2 自己贔屓（self-preference）を測る（P6・UC5）。

    python run_selfpref.py                                    # 模擬
    python run_selfpref.py --provider anthropic --limit 10    # 本物: 10 件（下書き 20 本・判定 40 回）

手順
1. 同じ問い合わせに、Opus 5.5 と Sonnet 5.5 がそれぞれ返信を書く（prompts/draft_reply.md）
2. その 2 本を、Opus と Sonnet の両方が判定役として比べる（順番を入れ替えて 2 回ずつ）
3. 「Opus の返信が勝った割合」を判定役ごとに出す。Opus 判定役の方が高ければ、Opus は自分の返信をひいきしている疑い
   🔴 件数が少ないので、差が出ても出なくても区間は広い。結論ではなく「測り方」を持ち帰る
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import judge as J, kit, llm as L, stats  # noqa: E402
from common.mockutil import coin  # noqa: E402

WRITERS = ["claude-opus-5-5", "claude-sonnet-5-5"]


def mock_draft(system, messages, tools, model):
    msg = messages[-1]["content"] if messages else ""
    if not isinstance(msg, str) or "次の問い合わせへの返信を" not in msg:
        return None
    extra = "詳しい手順はこのメールへの返信でご案内します。" if "opus" in model else ""
    return f"お客様様\n\nソラハ電機 サポート窓口です。\nお問い合わせの件、承りました。{extra}\n\nソラハ電機 サポート窓口"


def main(argv=None) -> dict:
    p = kit.parser("lab06 自己贔屓", default_limit=4)
    args = p.parse_args(argv)
    kit.banner("lab06-2 自己贔屓（書き手 2 × 判定役 2）", args)
    policy = kit.load_text("reply_policy.md")
    draft_t = J.load_prompt(os.path.join(HERE, "prompts", "draft_reply.md"))
    judge_t = J.load_prompt(os.path.join(HERE, "prompts", "pairwise.md"))
    src = [x for x in kit.load_jsonl("pairs.jsonl") if x["kind"] == "equal"]
    rows = kit.select(src, args)

    def draft(x, writer):
        prompt = J.fill(draft_t, policy=policy, received=x["received"], inquiry=x["inquiry"])
        r = L.call(prompt, provider=args.provider, model=writer, effort=args.effort, max_tokens=4000)
        return r.text.strip(), r

    def one(x):
        texts, res = {}, []
        for w in WRITERS:
            t, r = draft(x, w)
            texts[w] = t
            res.append(r)
        inq = f"受付日: {x['received']}\n{x['inquiry']}"
        verdicts = {}
        for judge_model in WRITERS:
            v = J.pairwise(judge_t, inq, texts[WRITERS[0]], texts[WRITERS[1]], provider=args.provider,
                           model=judge_model, effort=args.effort)
            res += v.pop("results")
            verdicts[judge_model] = v
        u = L.usage_of(res)
        return {"id": x["id"], "drafts": texts, "verdicts": verdicts, "cost_usd": u["cost_usd"],
                "len": {w: len(t) for w, t in texts.items()}}

    with L.mock_handler(mock_draft), L.tag("lab06/selfpref"):
        runs = kit.run_parallel(one, rows, workers=args.workers if args.provider == "anthropic" else 1)

    print("")
    summary = {}
    for jm in WRITERS:
        # 1 回ごとの判定で数える（入れ替えた 2 回とも）。x = Opus の返信、y = Sonnet の返信
        votes = [v for r in runs for v in (r["verdicts"][jm]["first_order"], r["verdicts"][jm]["swapped"])]
        ox, sy, tie = votes.count("x"), votes.count("y"), votes.count("tie")
        score = (ox + 0.5 * tie) / len(votes)
        dec = ox + sy
        summary[jm] = {"opus_wins": ox, "sonnet_wins": sy, "ties": tie, "opus_score": score,
                       "opus_win_rate_decided": ox / dec if dec else float("nan"),
                       "ci_decided": stats.wilson(ox, dec) if dec else [0, 1],
                       "consistent": sum(r["verdicts"][jm]["consistent"] for r in runs)}
        print(f"判定役 {jm}: Opus の返信の勝ち {ox} / Sonnet の返信の勝ち {sy} / 引き分け {tie}（{len(votes)} 回）"
              f" → Opus の得点 {score:.2f}（引き分けは 0.5）")
    a, b = summary[WRITERS[0]]["opus_score"], summary[WRITERS[1]]["opus_score"]
    print(f"\n自己贔屓の目安 = Opus 判定役の Opus 得点 − Sonnet 判定役の Opus 得点 = {a - b:+.2f}")
    # 同じ問いで 2 人の判定役の点を比べる（対応あり）
    pa = [sum({"x": 1, "tie": .5, "y": 0}[v] for v in (r["verdicts"][WRITERS[0]]["first_order"], r["verdicts"][WRITERS[0]]["swapped"])) / 2 for r in runs]
    pb = [sum({"x": 1, "tie": .5, "y": 0}[v] for v in (r["verdicts"][WRITERS[1]]["first_order"], r["verdicts"][WRITERS[1]]["swapped"])) / 2 for r in runs]
    pbs = stats.paired_bootstrap(pb, pa, seed=1)
    print(f"   問いごとの差の 95%区間 [{pbs['lo']:+.2f}, {pbs['hi']:+.2f}]（n={len(runs)}。0 をまたげば、この件数では言えない）")
    lens = {w: sum(r["len"][w] for r in runs) / len(runs) for w in WRITERS}
    print("   返信の平均の長さ: " + " / ".join(f"{w} {v:.0f} 字" for w, v in lens.items()))
    cost = round(sum(r["cost_usd"] for r in runs), 4)
    print(f"費用 {cost} USD")
    out = kit.out_dir(HERE, args.provider)
    kit.write_jsonl(os.path.join(out, f"runs_selfpref_n{len(runs)}.jsonl"), runs)
    result = {"judges": summary, "self_pref": a - b, "diff_ci": [pbs["lo"], pbs["hi"]], "avg_len": lens,
              "n": len(runs), "cost_usd": cost, "provider": args.provider, "effort": L.effort_name(args.effort)}
    kit.write_json(os.path.join(out, f"summary_selfpref_n{len(runs)}.json"), result)
    return result


if __name__ == "__main__":
    main()
