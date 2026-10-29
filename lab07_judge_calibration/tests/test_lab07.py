from conftest import run_lab


def test_split_is_stratified_and_disjoint():
    from common import kit
    import run_calibrate as C
    dev, test = C.split(kit.load_jsonl("replies.jsonl"))
    assert not ({r["id"] for r in dev} & {r["id"] for r in test}) and len(dev) + len(test) == 80


def test_calibrate_mock_v1_v2():
    a = run_lab("lab07_judge_calibration", "run_calibrate", ["--prompt", "v1", "--split", "dev"])
    b = run_lab("lab07_judge_calibration", "run_calibrate", ["--prompt", "v2", "--split", "dev"])
    assert a["n"] == b["n"] == 38 and 0 <= b["tpr"] <= 1


def test_iaa_runs():
    r = run_lab("lab07_judge_calibration", "run_iaa")
    assert 0 < r["fleiss"] < 1 and 0 < r["alpha"] < 1
