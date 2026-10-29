"""LLM 判定（LLM-as-a-judge）の共通部品。プロンプトは prompts/ のファイルに置き、ここでは呼び方と読み取りだけ。

- pairwise(): 2 つの返信を A/B で比べる。swap=True で順番を入れ替えた 2 回目も聞き、両方の結論をそろえて返す
- pointwise(): 1 つの返信を pass / fail で判定する
模擬の判定役は「先に出た方を少しひいきする」「長い方を少しひいきする」くせを持たせてある（測り方の練習用）。
"""
from __future__ import annotations

import json
import os

from common import llm as L
from common.mockutil import coin

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def load_prompt(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def fill(template: str, **kw) -> str:
    out = template
    for k, v in kw.items():
        out = out.replace("{" + k + "}", str(v))
    return out


# ---------------------------------------------------------------- 模擬の判定役
def mock_pairwise_judge(system, messages, tools, model):
    msg = messages[-1]["content"] if messages else ""
    if not isinstance(msg, str) or "【返信 A】" not in msg:
        return None
    a = msg.split("【返信 A】")[1].split("【返信 B】")[0]
    b = msg.split("【返信 B】")[1].split("【出力】")[0]
    bad = ("特別に", "30 日以内の不具合", "お詫びとして", "すべて当社で負担", "ご確認不足", "よくお読み", "変更できません",
           "自動で取り消し", "返金はできかねます", "有料", "郵送でのみ", "翌月の請求で相殺", "初期不良と考えられ")
    sa = -3 * sum(w in a for w in bad) + 0.004 * len(a) + 0.35   # 先に出た方へのひいき
    sb = -3 * sum(w in b for w in bad) + 0.004 * len(b)
    sa += coin("pj", model, a[:40], b[:40]) - 0.5
    w = "A" if sa > sb + 0.15 else "B" if sb > sa + 0.15 else "tie"
    return json.dumps({"winner": w, "reason": "（模擬）"}, ensure_ascii=False)


def mock_pointwise_judge(system, messages, tools, model):
    msg = messages[-1]["content"] if messages else ""
    if not isinstance(msg, str) or "【判定する返信】" not in msg:
        return None
    body = msg.split("【判定する返信】")[1]
    bad = ("特別に", "30 日以内の不具合", "お詫びとして", "すべて当社で負担", "ご確認不足", "よくお読み", "変更できません",
           "自動で取り消し", "返金はできかねます", "有料", "郵送でのみ", "翌月の請求で相殺", "初期不良と考えられ",
           "日数にかかわらず", "発送後の変更")
    strict = "決まり" in msg   # 手引きつきの判定（v2）の方が見つけやすい、という模擬
    hit = any(w in body for w in bad)
    miss_next = "返信" not in body.split("\n\n")[1] if "\n\n" in body else False
    p_detect = 0.9 if strict else 0.6
    fail = (hit and coin("pw", model, body[:50]) < p_detect) or (miss_next and strict and coin("pn", model, body[:50]) < 0.5)
    if not hit and coin("fp", model, body[:60]) < (0.05 if strict else 0.12):
        fail = True
    return json.dumps({"verdict": "fail" if fail else "pass", "reason": "（模擬）"}, ensure_ascii=False)


L.MOCK_HANDLERS.extend([mock_pairwise_judge, mock_pointwise_judge])


# ---------------------------------------------------------------- 呼び方
def _winner(obj) -> str:
    w = str(obj.get("winner", "")).strip().upper()
    return {"A": "A", "B": "B", "TIE": "tie", "同等": "tie"}.get(w, "tie" if "TIE" in w or "同" in w else w)


def pairwise_once(template: str, inquiry: str, first: str, second: str, **kw) -> tuple[str, list]:
    prompt = fill(template, inquiry=inquiry, a=first, b=second)
    obj, results = L.call_json(prompt, validate=lambda o: None if _winner(o) in ("A", "B", "tie") else "winner は A/B/tie",
                               max_tokens=4000, **kw)
    return _winner(obj), results


def pairwise(template: str, inquiry: str, x: str, y: str, **kw) -> dict:
    """x と y を、x を先にした回と y を先にした回の 2 回比べる。"""
    w1, r1 = pairwise_once(template, inquiry, x, y, **kw)       # x が A
    w2, r2 = pairwise_once(template, inquiry, y, x, **kw)       # y が A
    v1 = {"A": "x", "B": "y", "tie": "tie"}[w1]
    v2 = {"A": "y", "B": "x", "tie": "tie"}[w2]
    final = v1 if v1 == v2 else "tie"           # 入れ替えて結論が変わったら引き分け（Wang et al. 2023 の考え方）
    return {"first_order": v1, "swapped": v2, "consistent": v1 == v2, "final": final,
            "first_pos_won": [w1 == "A", w2 == "A"], "results": r1 + r2}


def pointwise(template: str, **kw_and_fields) -> tuple[str, list]:
    fields = {k: v for k, v in kw_and_fields.items() if k in ("inquiry", "reply", "policy", "received")}
    kw = {k: v for k, v in kw_and_fields.items() if k not in fields}
    prompt = fill(template, **fields)
    obj, results = L.call_json(prompt, validate=lambda o: None if o.get("verdict") in ("pass", "fail") else "verdict は pass/fail",
                               max_tokens=4000, **kw)
    return obj["verdict"], results
