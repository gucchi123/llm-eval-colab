"""架空のデータ一式を作る（乱数固定。何度回しても一字一句同じ）。

    python data/make_data.py          # 作る
    python data/check_data.py         # 作り直して、MANIFEST.json のハッシュと一致するか確かめる

作り方の説明は GENERATION.md。LLM は使っていない（文章はすべて型と乱数で組み立てる）。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "gen"))
sys.path.insert(0, os.path.dirname(HERE))

import agent as g_agent          # noqa: E402
import claims as g_claims        # noqa: E402
import inquiries as g_inq        # noqa: E402
import inquiries_hard as g_hard  # noqa: E402
import policies as g_pol         # noqa: E402
import replies as g_rep          # noqa: E402
import safety as g_safe          # noqa: E402
from common.sampling import stratified_sample  # noqa: E402

SEEDS = {"inquiries": 20261018, "hard": 20261021, "golden": 7, "fewshot": 11, "claims": 20261019, "replies": 20261020}


def _jsonl(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _json(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def _text(path, s):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def build(out_dir: str = HERE) -> dict:
    files = {}
    pool = g_inq.make(seed=SEEDS["inquiries"], n=600)
    golden = stratified_sample(pool, key=lambda r: (r["label"], r["difficulty"]), n=120, min_per_stratum=3,
                               seed=SEEDS["golden"])
    gids = {r["id"] for r in golden}
    import random
    rng = random.Random(SEEDS["fewshot"])
    rest = [r for r in pool if r["id"] not in gids]
    fewshot = []
    for lab in g_inq.LABELS:   # ラベルごとに 2 件。わざと素朴に選ぶ（漏れの点検は lab02 で）
        cand = [r for r in rest if r["label"] == lab]
        fewshot += rng.sample(cand, 2)
    rep = g_rep.make(pool, exclude=gids | {r["id"] for r in fewshot}, seed=SEEDS["replies"])
    outputs = {
        "inquiries_pool.jsonl": ("jsonl", pool),
        "golden_inquiries.jsonl": ("jsonl", golden),
        "fewshot_inquiries.jsonl": ("jsonl", fewshot),
        "golden_inquiries_v2_hard.jsonl": ("jsonl", g_hard.make(seed=SEEDS["hard"])),
        "guide_inquiries.md": ("text", g_inq.GUIDE),
        "claims.jsonl": ("jsonl", g_claims.make(seed=SEEDS["claims"])),
        "policies.json": ("json", g_pol.make()),
        "agent.json": ("json", g_agent.make()),
        "replies.jsonl": ("jsonl", rep["replies"]),
        "pairs.jsonl": ("jsonl", rep["pairs"]),
        "reply_policy.md": ("text", rep["policy"]),
        "safety.json": ("json", g_safe.make()),
    }
    for name, (kind, obj) in outputs.items():
        p = os.path.join(out_dir, name)
        {"jsonl": _jsonl, "json": _json, "text": _text}[kind](p, obj)
        with open(p, "rb") as f:
            files[name] = hashlib.sha256(f.read()).hexdigest()
    return {"seeds": SEEDS, "sha256": files,
            "counts": {"pool": len(pool), "golden": len(golden), "fewshot": len(fewshot), "hard": 48,
                       "claims": len(outputs["claims.jsonl"][1]), "questions": len(outputs["policies.json"][1]["questions"]),
                       "agent_tasks": len(outputs["agent.json"][1]["tasks"]), "replies": len(rep["replies"]),
                       "pairs": len(rep["pairs"]), "safety": len(outputs["safety.json"][1]["items"])}}


if __name__ == "__main__":
    man = build()
    _json(os.path.join(HERE, "MANIFEST.json"), man)
    print(json.dumps(man["counts"], ensure_ascii=False))
