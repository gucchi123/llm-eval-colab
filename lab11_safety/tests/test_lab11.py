from conftest import run_lab


def test_safety_mock_and_leak_rule():
    r = run_lab("lab11_safety", "run_safety", ["--all"])
    assert r["attack_n"] == 12 and r["benign_n"] == 12
    from common import kit
    markers = kit.load_json("safety.json")["leak_markers"]
    assert any(m in "朝比奈様の番号は 070-5550-0142 です" for m in markers)
    assert not any(m in "会員サイトのマイページから変更できます。" for m in markers)
