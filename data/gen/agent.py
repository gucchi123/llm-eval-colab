"""UC4 クロツグ食品（架空）の発注担当エージェント。品目・仕入先と、担当者からの依頼 10 件。

正しい結果（どの品目を・何個・どこから発注するか、承認が要るか）は、発注の手引き（RULES）を
コードで当てて決める（expected()）。エージェントの評価は、この結果と、道具の呼び方（軌跡）の両方で行う。
"""
from __future__ import annotations

RULES = """# クロツグ食品 発注の手引き（架空）
1. 発注する前に、必ず get_stock でその品目の在庫を確かめる。
2. 在庫が発注点「以下」のときだけ発注する。発注数は「目標在庫 − 現在の在庫」。
3. 仕入先は get_suppliers で調べ、納期が期限（依頼に書かれていなければ 7 日）以内の中で単価が最も安いところ。
   単価が同じなら納期が短い方。
4. 発注金額（単価 × 発注数）が 100,000 円以上なら、create_order の前に request_approval を呼ぶ。
   approved のときだけ発注し、rejected なら発注しない。
5. 販売終了の品目は発注しない。
6. 品目名がはっきりしないときは search_items で探す。
7. 最後に、何をしたか（発注した品目・数・仕入先、しなかった品目とその理由）を担当者向けに短く報告する。
"""

# code: name, aliases, stock, reorder_point, target, discontinued, suppliers[(name, unit_price, lead_days)]
ITEMS = {
    "K-101": ("白だし 1L", ["白だし"], 12, 20, 60, False, [("ミノワ商店", 520, 3), ("タカセ食品卸", 495, 5), ("北浜物流", 540, 2)]),
    "K-102": ("濃口醤油 1.8L", ["醤油", "しょうゆ"], 45, 30, 80, False, [("ミノワ商店", 610, 3), ("タカセ食品卸", 590, 4)]),
    "K-103": ("業務用ごま油 1.65kg", ["ごま油"], 3, 10, 30, True, [("タカセ食品卸", 1980, 4)]),
    "K-104": ("かつお節パック 500g", ["かつお節", "削り節"], 8, 15, 60, False, [("ミノワ商店", 2450, 3), ("北浜物流", 2380, 6)]),
    "K-105": ("米酢 20L", ["米酢", "酢"], 2, 5, 12, False, [("タカセ食品卸", 3900, 5), ("ミノワ商店", 4150, 3), ("北浜物流", 4300, 2)]),
    "K-106": ("みりん風調味料 18L", ["みりん"], 4, 10, 120, False, [("北浜物流", 2950, 3), ("タカセ食品卸", 3010, 2)]),
    "K-107": ("乾燥わかめ 1kg", ["わかめ"], 6, 10, 25, False, [("ミノワ商店", 1680, 4), ("タカセ食品卸", 1720, 3)]),
    "K-108": ("焼きのり 全形 100 枚", ["のり", "海苔"], 9, 12, 30, False, [("北浜物流", 1450, 5), ("ミノワ商店", 1490, 2)]),
    "K-109": ("つゆの素 業務用 1.8L", ["めんつゆ", "そばつゆ"], 15, 18, 50, False, [("タカセ食品卸", 760, 4), ("ミノワ商店", 760, 2)]),
    "K-110": ("中ざら 5kg", ["ざらめ", "砂糖"], 20, 20, 40, False, [("北浜物流", 2100, 3), ("タカセ食品卸", 2050, 8)]),
}

APPROVAL_LIMIT = 300_000   # これを超える申請は承認者が却下する（環境の決まり。エージェントには見せない）

TASKS = [
    ("T01", "白だし 1L の在庫を確認して、必要なら補充しておいてください。", None),
    ("T02", "濃口醤油 1.8L も減ってきた気がします。必要なら補充をお願いします。", None),
    ("T03", "業務用ごま油の在庫が少ないので補充してください。", None),
    ("T04", "かつお節パック 500g の補充をお願いします。", None),
    ("T05", "米酢 20L を補充してください。3 日以内に届くようにしてください。", 3),
    ("T06", "みりん風調味料を補充してください。", None),
    ("T07", "乾燥わかめと焼きのりを補充してください。", None),
    ("T08", "めんつゆ（業務用）の在庫を見て、必要なら発注してください。", None),
    ("T09", "中ざらの在庫が発注点まで減ったと聞きました。確認して対応してください。", None),
    ("T10", "かつお節と白だしをまとめて補充してください。5 日以内に届くものでお願いします。", 5),
]

TASK_ITEMS = {"T01": ["K-101"], "T02": ["K-102"], "T03": ["K-103"], "T04": ["K-104"], "T05": ["K-105"],
              "T06": ["K-106"], "T07": ["K-107", "K-108"], "T08": ["K-109"], "T09": ["K-110"],
              "T10": ["K-104", "K-101"]}


def expected(task_id: str) -> dict:
    """手引きをコードで当てた正解。orders: {code: (qty, supplier)}、approvals: 承認が要る品目、rejected: 却下される品目。"""
    deadline = dict((t, d) for t, _, d in TASKS)[task_id] or 7
    orders, approvals, rejected, skipped = {}, [], [], {}
    for code in TASK_ITEMS[task_id]:
        name, _, stock, rop, target, disc, sups = ITEMS[code]
        if disc:
            skipped[code] = "販売終了"
            continue
        if stock > rop:
            skipped[code] = "在庫が発注点より多い"
            continue
        qty = target - stock
        ok = [s for s in sups if s[2] <= deadline]
        sup = sorted(ok, key=lambda s: (s[1], s[2]))[0]
        amount = sup[1] * qty
        if amount >= 100_000:
            approvals.append(code)
            if amount > APPROVAL_LIMIT:
                rejected.append(code)
                skipped[code] = "承認が却下された"
                continue
        orders[code] = (qty, sup[0])
    return {"orders": orders, "approvals": approvals, "rejected": rejected, "skipped": skipped, "deadline": deadline}


def make() -> dict:
    items = [{"code": c, "name": v[0], "aliases": v[1], "stock": v[2], "reorder_point": v[3], "target": v[4],
              "discontinued": v[5], "suppliers": [{"name": s[0], "unit_price": s[1], "lead_days": s[2]} for s in v[6]]}
             for c, v in ITEMS.items()]
    tasks = []
    for t, text, d in TASKS:
        e = expected(t)
        tasks.append({"id": t, "request": text, "deadline_days": d, "items": TASK_ITEMS[t],
                      "expected": {"orders": {k: {"qty": q, "supplier": s} for k, (q, s) in e["orders"].items()},
                                   "approvals": e["approvals"], "rejected": e["rejected"], "skipped": e["skipped"]}})
    return {"items": items, "tasks": tasks, "rules": RULES, "approval_limit": APPROVAL_LIMIT}
