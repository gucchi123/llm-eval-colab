"""模擬（mock）用の決まった乱れ。🔴 ここで作る数字は性能の証拠にしない（コードの通り道を確かめるためのもの）。"""
from __future__ import annotations

import hashlib


def coin(*parts) -> float:
    """同じ引数なら必ず同じ 0〜1 の値。"""
    h = hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def skill(model: str) -> float:
    """模擬モデルの「腕前」。名前で少し変える（比較の通り道を確かめるため）。"""
    m = model.lower()
    if "opus" in m:
        return 0.92
    if "sonnet" in m:
        return 0.87
    return 0.85
