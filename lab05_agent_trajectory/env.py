"""クロツグ食品（架空）の発注システムの模型。エージェントはこの道具だけを通して在庫・仕入先・承認・発注に触れる。

道具の呼び出しはすべて trace に残る（軌跡の評価に使う）。発注は記録されるだけで、在庫は変わらない。
"""
from __future__ import annotations

import json

TOOLS = [
    {"name": "search_items", "description": "品目名の一部や別名から、品目コードと正式名を探す。",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "get_stock", "description": "品目コードの現在の在庫・発注点・目標在庫・販売終了かどうかを返す。",
     "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
    {"name": "get_suppliers", "description": "品目コードの仕入先ごとの単価（円）と納期（日）を返す。",
     "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
    {"name": "request_approval", "description": "発注金額が 100,000 円以上の発注について、上長の承認を求める。approved か rejected を返す。",
     "input_schema": {"type": "object", "properties": {"code": {"type": "string"}, "qty": {"type": "integer"},
                                                       "supplier": {"type": "string"}, "amount": {"type": "integer"}},
                      "required": ["code", "qty", "supplier", "amount"]}},
    {"name": "create_order", "description": "発注を確定する。取り消しはできない。",
     "input_schema": {"type": "object", "properties": {"code": {"type": "string"}, "qty": {"type": "integer"},
                                                       "supplier": {"type": "string"}}, "required": ["code", "qty", "supplier"]}},
]


class OrderEnv:
    def __init__(self, data: dict):
        self.items = {it["code"]: it for it in data["items"]}
        self.limit = data["approval_limit"]
        self.trace: list[dict] = []
        self.orders: list[dict] = []
        self.approvals: dict[str, str] = {}

    def call(self, name: str, args: dict) -> str:
        try:
            out = getattr(self, "_" + name)(**args)
        except KeyError as e:
            out = {"error": f"品目コード {e} は見つかりません"}
        except TypeError as e:
            out = {"error": f"引数が正しくありません: {e}"}
        except AttributeError:
            out = {"error": f"道具 {name} はありません"}
        self.trace.append({"tool": name, "args": args, "result": out})
        return json.dumps(out, ensure_ascii=False)

    def _search_items(self, query: str):
        q = query.strip()
        hits = [{"code": c, "name": it["name"]} for c, it in self.items.items()
                if q in it["name"] or any(a in q or q in a for a in it["aliases"])]
        return {"items": hits}

    def _get_stock(self, code: str):
        it = self.items[code]
        return {"code": code, "name": it["name"], "stock": it["stock"], "reorder_point": it["reorder_point"],
                "target": it["target"], "discontinued": it["discontinued"]}

    def _get_suppliers(self, code: str):
        return {"code": code, "suppliers": self.items[code]["suppliers"]}

    def _request_approval(self, code: str, qty: int, supplier: str, amount: int):
        self.items[code]  # 品目が無ければ KeyError
        status = "approved" if int(amount) <= self.limit else "rejected"
        self.approvals[code] = status
        return {"status": status, "code": code, "amount": amount}

    def _create_order(self, code: str, qty: int, supplier: str):
        self.items[code]
        self.orders.append({"code": code, "qty": int(qty), "supplier": supplier})
        return {"status": "ordered", "order_no": f"PO-{len(self.orders):03d}"}
