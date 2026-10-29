"""講義用のノートブック（P1〜P12）を作る。

    python notebooks/build_notebooks.py            # 全部
    python notebooks/build_notebooks.py p03        # 名前の先頭で絞る

中身は build_pNN.py の BOOKS（{ファイル名: セルの並び}）。部品は _nbkit.py。
実行して出力つきで保存するのは run_notebooks.py（講師の記録の再生で、費用 0）。
"""
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _nbkit import save  # noqa: E402

PARTS = ["build_p01_p04", "build_p05_p07", "build_p08_p12"]


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    for mod in PARTS:
        if not os.path.exists(os.path.join(HERE, mod + ".py")):
            print("（まだ無い）", mod)
            continue
        books = importlib.import_module(mod).BOOKS
        for name, cells in books.items():
            if name.startswith(only):
                save(name, cells)


if __name__ == "__main__":
    main()
