"""pytest の共通設定: キーを消し、模擬（mock）で動かす。API は絶対に呼ばない。"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
for _d in sorted(os.listdir(ROOT)):           # ラボのモジュール名はすべて一意なので、全部を import パスに入れる
    if _d.startswith("lab") and os.path.isdir(os.path.join(ROOT, _d)):
        sys.path.insert(1, os.path.join(ROOT, _d))


@pytest.fixture(autouse=True)
def _no_api(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_CACHE_ONLY", "1")          # replay のテストでも API に行かない
    monkeypatch.setenv("LLM_LEDGER", str(tmp_path / "ledger.jsonl"))
    from common import llm as L
    monkeypatch.setattr(L, "_api_key", lambda: None)   # Windows のレジストリからも読まない
    yield


def run_lab(lab: str, module: str, argv=None):
    """ラボのフォルダを import パスに入れて main(argv) を呼ぶ。"""
    import importlib
    d = os.path.join(ROOT, lab)
    if d not in sys.path:
        sys.path.insert(0, d)
    mod = importlib.import_module(module)
    return mod.main(argv or [])
