"""講義用ノートブックを作る部品（build_notebooks.py と build_pNN.py が使う）。

どのノートブックも Colab と手元の Jupyter の両方でそのまま動く:
  - 0-1 のセルが実行場所を見分ける（Colab ならキットを取得し、手元なら何もしない）
  - 0-2 のセルが API キーを探す（Colab のシークレット → 環境変数 → Windows のユーザー環境変数）。
    無ければ講師の記録の再生（replay）、記録も無ければ mock

セルの書き方の決まり（録画して講義で見せるため）:
  - 1 つのコードセルの出力は 1 画面（だいたい 22 行）に収める。長い表は分けるか、先頭だけ見せる
  - 見出し（md）→ コード、の組にする。見出しの 1 行目がクリップの題になる
  - ラボの本物のコードは nb.show(関数) / nb.show_file(パス) で、その場でファイルから表示する
  - 呼び先は PROVIDER（0-2 で決めたもの）を使う。mock の数字を性能として出さない
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DISCLAIMER = "この教材に登場する会社・人物・製品・数値・文書はすべて架空のものです。実在の企業・団体・個人とは関係ありません。"

SETUP = '''# 0-1. 実行場所を見分けて、キットのフォルダに移る（Colab のときだけ取得とインストールをする）
import os, sys, subprocess
REPO_URL = "https://github.com/gucchi123/llm-eval-colab.git"
try:
    import google.colab  # noqa: F401
    IN_COLAB = True
except ImportError:
    IN_COLAB = False
if IN_COLAB:
    KIT = "/content/llm-eval-kit"
    if not os.path.exists(KIT):
        subprocess.run(["git", "clone", "-q", REPO_URL, KIT], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "anthropic"], check=True)
else:  # 手元: notebooks/ から開いた前提。キットの根（common/ がある所）を探す
    KIT = os.path.abspath(".." if os.path.exists("../common/llm.py") else ".")
os.chdir(KIT)
sys.path.insert(0, KIT)
print("実行場所:", "Colab" if IN_COLAB else "手元の Jupyter", "/ キットの根:", os.path.basename(KIT))'''

PROVIDER = '''# 0-2. AI の呼び先を決める（キーは表示しない）
from common import nb
from common.nb import choose_provider, safe, show, show_file, lab
PROVIDER = choose_provider(IN_COLAB)'''


def nb(title, intro, cells):
    out = [("md", f"# {title}\n\n> **{DISCLAIMER}**\n\n{intro}\n\n"
                  "- 上から順に実行します。0 のセルは準備です（Colab でも手元の Jupyter でも同じ）。\n"
                  "- API キーが無ければ講師の記録の再生（replay）で、本物の実行と同じ数字が出ます（費用 0）。\n"
                  "- 🔴 データはすべて架空の会社・文書です。"),
           ("md", "## 0. 準備"), ("code", SETUP), ("code", PROVIDER)]
    out += cells
    return out


def cell(kind, src):
    c = {"cell_type": "markdown" if kind == "md" else "code", "metadata": {}, "source": src.strip("\n").splitlines(True)}
    if kind == "code":
        c.update(execution_count=None, outputs=[])
    return c


def save(name, cells):
    cs = [cell(k, s) for k, s in cells]
    for i, c in enumerate(cs):
        c["id"] = f"c{i:02d}"  # nbformat 4.5 はセルに id が要る（決まった値にして差分を小さく）
    doc = {"cells": cs, "nbformat": 4, "nbformat_minor": 5,
           "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                        "language_info": {"name": "python"}, "colab": {"provenance": []}}}
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    code_idx = [i for i, (k, _) in enumerate(cells) if k == "code"]
    print("wrote", name, len(cells), "cells / code cells at", code_idx)


M, C = "md", "code"
