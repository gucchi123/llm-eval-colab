"""データを一時フォルダに作り直し、MANIFEST.json のハッシュと一致するかを確かめる（再現性の点検）。"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_data  # noqa: E402


def main() -> int:
    with open(os.path.join(HERE, "MANIFEST.json"), encoding="utf-8") as f:
        want = json.load(f)["sha256"]
    with tempfile.TemporaryDirectory() as d:
        got = make_data.build(d)["sha256"]
    bad = [k for k in want if want[k] != got.get(k)]
    # 配布物の data/ が手で書き換えられていないか
    import hashlib
    edited = []
    for k, h in want.items():
        with open(os.path.join(HERE, k), "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() != h:
                edited.append(k)
    print("再生成の不一致:", bad or "なし")
    print("data/ の書き換え:", edited or "なし")
    return 1 if bad or edited else 0


if __name__ == "__main__":
    sys.exit(main())
