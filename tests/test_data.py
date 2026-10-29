"""データの再現性と、正解の作り方の検査。"""
import os
import subprocess
import sys

from common import kit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_data_regenerates_identically():
    p = subprocess.run([sys.executable, os.path.join(ROOT, "data", "check_data.py")], capture_output=True,
                       text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert p.returncode == 0, p.stdout + p.stderr


def test_counts():
    man = kit.load_json("MANIFEST.json")["counts"]
    assert man == {"pool": 600, "golden": 120, "fewshot": 12, "hard": 48, "claims": 48, "questions": 30,
                   "agent_tasks": 10, "replies": 80, "pairs": 52, "safety": 24}


def test_agent_expected_follows_rules():
    tasks = {t["id"]: t["expected"] for t in kit.load_json("agent.json")["tasks"]}
    assert tasks["T02"]["orders"] == {} and "K-102" in tasks["T02"]["skipped"]
    assert tasks["T05"]["orders"]["K-105"] == {"qty": 10, "supplier": "ミノワ商店"}       # 期限 3 日で最安
    assert tasks["T06"]["rejected"] == ["K-106"] and tasks["T06"]["orders"] == {}        # 承認の却下
    assert tasks["T09"]["orders"]["K-110"]["supplier"] == "北浜物流"                     # 安い方は納期 8 日で外れる
    assert tasks["T10"]["orders"]["K-104"]["supplier"] == "ミノワ商店" and "K-104" in tasks["T10"]["approvals"]


def test_hard_set_has_six_kinds_of_eight():
    from collections import Counter
    c = Counter(r["facts"]["scenario"] for r in kit.load_jsonl("golden_inquiries_v2_hard.jsonl"))
    assert sorted(c.values()) == [8] * 6


def test_replies_labels_match_defects():
    reps = kit.load_jsonl("replies.jsonl")
    assert sum(r["label"] == "fail" for r in reps) == 36
    assert all((r["defect"] is None) == (r["label"] == "pass") for r in reps)


def test_everything_is_fictional_marker_present():
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    assert "すべて架空" in readme
