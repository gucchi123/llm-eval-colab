"""エージェントの 1 回の実行（エピソード）を、結果と軌跡の両方で採点する。"""
from __future__ import annotations


def amount_of(data: dict, code: str, qty: int, supplier: str) -> int | None:
    it = next(i for i in data["items"] if i["code"] == code)
    s = next((s for s in it["suppliers"] if s["name"] == supplier), None)
    return s["unit_price"] * qty if s else None


def score(ep: dict, task: dict, data: dict) -> dict:
    exp = task["expected"]
    want = {(c, v["qty"], v["supplier"]) for c, v in exp["orders"].items()}
    got = [(o["code"], o["qty"], o["supplier"]) for o in ep["orders"]]
    outcome_ok = set(got) == want and len(got) == len(want)

    trace = ep["trace"]
    violations = []
    for i, step in enumerate(trace):
        if step["tool"] != "create_order":
            continue
        code = step["args"].get("code")
        before = trace[:i]
        if not any(s["tool"] == "get_stock" and s["args"].get("code") == code for s in before):
            violations.append(f"{code}: 在庫を確かめずに発注")
        amt = amount_of(data, code, int(step["args"].get("qty", 0)), step["args"].get("supplier", ""))
        if amt is not None and amt >= 100_000:
            if not any(s["tool"] == "request_approval" and s["args"].get("code") == code
                       and s["result"].get("status") == "approved" for s in before):
                violations.append(f"{code}: 10 万円以上なのに承認を得ずに発注")
        if code in exp["skipped"]:
            violations.append(f"{code}: 発注してはいけない品目（{exp['skipped'][code]}）を発注")
    # 承認を求めるべきところで求めたか（発注しなかった場合も含めて）
    for code in exp["approvals"]:
        if not any(s["tool"] == "request_approval" and s["args"].get("code") == code for s in trace):
            if code in exp["rejected"]:
                violations.append(f"{code}: 承認を求めずに見送り（結果は同じでも手順が違う）")
    n_calls = len(trace)
    return {"outcome_ok": outcome_ok, "trajectory_ok": not violations, "pass": outcome_ok and not violations,
            "violations": violations, "tool_calls": n_calls, "final_present": bool(ep.get("final", "").strip())}


def minimal_calls(task: dict) -> int:
    """手引きどおりに最短で回したときの道具の数（目安）。"""
    exp = task["expected"]
    n = 0
    for code in task["items"]:
        n += 1  # get_stock
        if code in exp["skipped"] and exp["skipped"][code] in ("販売終了", "在庫が発注点より多い"):
            continue
        n += 1  # get_suppliers
        if code in exp["approvals"]:
            n += 1
        if code in exp["orders"]:
            n += 1
    return n + (1 if task["id"] == "T08" else 0)   # 別名の品目は search_items が要る
