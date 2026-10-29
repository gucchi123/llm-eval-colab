"""lab03-2 請求書からの項目抽出を測る（P3・UC2 ツバクロ少額短期保険・架空）。

    python run_extract.py                                    # 模擬
    python run_extract.py --provider anthropic --all         # 本物（既定 Opus 5.5・high）
    python run_extract.py --provider anthropic --all --model claude-sonnet-5-5

測り方は 2 通り:
- strict     : 出てきた値をそのまま正解と比べる
- normalized : 比べる前に表記をそろえる（全角→半角・空白・「2026-9-2」→「2026-09-02」・「30,000」→ 30000）
差が大きいほど「採点の仕方」で点が変わっている。どちらを使うかは、後ろの業務（システムに入れる値か、人が読む値か）で決める。
"""
from __future__ import annotations

import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import kit, llm as L, metrics as M, stats  # noqa: E402
from common.mockutil import coin, skill  # noqa: E402

FIELDS = ["policy_no", "claimant", "incident_date", "claim_amount", "category", "receipt_attached"]


def norm(field, v):
    if v is None:
        return None
    if field == "claim_amount":
        if isinstance(v, (int, float)):
            return int(v)
        s = unicodedata.normalize("NFKC", str(v)).replace(",", "").replace("円", "").replace("¥", "").strip()
        return int(s) if s.isdigit() else s
    if field == "receipt_attached":
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in ("true", "あり", "yes", "1")
    s = unicodedata.normalize("NFKC", str(v)).strip()
    if field == "incident_date":
        m = re.match(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", s)
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else s
    if field == "claimant":
        return re.sub(r"\s+", "", s)
    return s


def prompt_for(doc):
    with open(os.path.join(HERE, "prompts", "extract.md"), encoding="utf-8") as f:
        return f.read().replace("{doc}", doc["text"])


def mock_for(docs):
    by_text = {d["text"]: d for d in docs}

    def fn(system, messages, tools, model):
        msg = messages[-1]["content"]
        if "保険金の請求書から" not in msg:
            return None
        d = next((v for k, v in by_text.items() if k in msg), None)
        if d is None:
            return None
        g = dict(d["gold"])
        if coin("ext-amt", model, d["id"]) > skill(model):
            g["claim_amount"] = g["claim_amount"] + 10000          # 見積もりの額を取ってしまう、の模擬
        if coin("ext-date", model, d["id"]) > skill(model) + 0.03:
            g["incident_date"] = g["incident_date"].replace("2026-", "2025-")
        if coin("ext-fmt", model, d["id"]) < 0.2:
            g["claim_amount"] = f"{g['claim_amount']:,}"           # 表記ゆれ（strict だけが落とす）
        import json
        return json.dumps(g, ensure_ascii=False)
    return fn


def extract_one(d, args):
    try:
        obj, results = L.call_json(prompt_for(d), provider=args.provider, model=args.model, effort=args.effort,
                                   max_tokens=4000)
    except (L.BudgetExceeded, L.CacheMiss):
        raise   # 予算切れ・記録なしは「無効な出力」に数えない
    except RuntimeError as e:
        obj, results = {}, []
        print(f"   {d['id']}: {e}")
    u = L.usage_of(results)
    return {"id": d["id"], "format": d["format"], "gold": d["gold"], "pred": obj,
            "cost_usd": u["cost_usd"], "seconds": u["seconds"]}


def main(argv=None) -> dict:
    args = kit.parser("lab03 項目抽出", default_limit=8).parse_args(argv)
    kit.banner("lab03-2 請求書の項目抽出", args)
    docs = kit.load_jsonl("claims.jsonl")
    rows = kit.select(docs, args)
    model = L.model_name(args.model)
    with L.mock_handler(mock_for(docs)), L.tag(f"lab03/extract/{kit.slug(model)}"):
        runs = kit.run_parallel(lambda d: extract_one(d, args), rows, workers=args.workers if args.provider == "anthropic" else 1)
    golds = [r["gold"] for r in runs]
    preds = [r["pred"] for r in runs]
    strict = M.field_scores(golds, preds, FIELDS)
    normed = M.field_scores(golds, preds, FIELDS, norm=norm)
    rows_t = [[f, kit.pct(strict["per_field"][f]), kit.pct(normed["per_field"][f])] for f in FIELDS]
    print(kit.table(rows_t, ["項目", "strict", "normalized"]))
    n = len(runs)
    k = round(normed["doc_all_correct"] * n)
    lo, hi = stats.wilson(k, n)
    print(f"全項目が合っていた請求書: strict {kit.pct(strict['doc_all_correct'])} / normalized {kit.pct(normed['doc_all_correct'])} "
          f"95%区間 {kit.ci_str(lo, hi)} (n={n})")
    errs = []
    for r in runs:
        for f in FIELDS:
            if norm(f, r["gold"].get(f)) != norm(f, (r["pred"] or {}).get(f)):
                errs.append({"id": r["id"], "field": f, "gold": r["gold"].get(f), "pred": (r["pred"] or {}).get(f),
                             "format": r["format"]})
    print(f"そろえても合わない値: {len(errs)} 個")
    for e in errs[:10]:
        print(f"   {e['id']} {e['field']}: 正解 {e['gold']!r} / 出力 {e['pred']!r}  ({e['format']})")
    cost = round(sum(r["cost_usd"] for r in runs), 4)
    print(f"費用 {cost} USD / 待ち時間 p50 {stats.percentile([r['seconds'] for r in runs], .5):.1f}s")
    out = kit.out_dir(HERE, args.provider)
    tag = kit.slug(model) + ("" if n == len(docs) else f"_n{n}")
    kit.write_jsonl(os.path.join(out, f"runs_extract_{tag}.jsonl"), runs)
    summary = {"model": model, "effort": L.effort_name(args.effort), "provider": args.provider, "n": n,
               "strict": strict, "normalized": normed, "doc_all_correct_ci": [lo, hi], "errors": errs, "cost_usd": cost}
    kit.write_json(os.path.join(out, f"summary_extract_{tag}.json"), summary)
    return summary


if __name__ == "__main__":
    main()
