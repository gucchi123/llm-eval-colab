"""ノートブック（Colab と手元の Jupyter の両方）で使う準備と、画面に見せるための小さな道具。

- API キーの探し方: Colab のシークレット → 環境変数 → （Windows）HKCU\\Environment。
  見つからなければ講師の記録の再生（replay）、記録も無ければ mock
- キーは画面にもファイルにも出さない。エラー文にキーらしい文字列があれば伏せ字にする
- show() / show_file(): ラボの本物のコードや依頼文を、その場でファイルから読んで表示する（写しを貼らない）
"""
from __future__ import annotations

import importlib
import inspect
import os
import re
import sys
import traceback
from contextlib import contextmanager

_SECRET = re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _find_key(in_colab: bool) -> str | None:
    if in_colab:
        try:
            from google.colab import userdata
            k = userdata.get("ANTHROPIC_API_KEY")
            if k:
                return k
        except Exception:  # シークレットが無い・ノートブックに許可していない
            pass
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k:
        return k
    if os.environ.get("LLM_NO_KEY") == "1":  # 自己検査用: キーを持たない人の手元を再現する
        return None
    if os.name == "nt":  # Jupyter のカーネルがユーザー環境変数を引き継いでいないことがある
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
                return winreg.QueryValueEx(h, "ANTHROPIC_API_KEY")[0]
        except OSError:
            return None
    return None


def _has_records() -> bool:
    d = os.path.join(ROOT, ".cache", "llm")
    return os.path.isdir(d) and any(os.scandir(d))


def choose_provider(in_colab: bool, prefer: str | None = None) -> str:
    """キーがあれば anthropic（記録があれば再生・費用 0）、無ければ講師の記録の再生（replay）、記録も無ければ mock。

    prefer に "mock" / "replay" / "anthropic" を渡すと、それを使う（キーが要る anthropic でキーが無ければ replay）。
    """
    key = _find_key(in_colab)
    has_rec = _has_records()
    want = (prefer or os.environ.get("LLM_PROVIDER_PREFER") or "").lower()
    if key and want in ("", "anthropic"):
        os.environ["ANTHROPIC_API_KEY"] = key  # SDK が読む場所に置くだけ。表示しない
        os.environ["LLM_PROVIDER"] = "anthropic"
        print("API キーが見つかりました（表示しません）→ provider = anthropic")
        print("  同じ依頼の記録が .cache/llm/ にあれば、それを返します（費用 0・すぐ終わる）")
    elif has_rec and want in ("", "anthropic", "replay"):
        os.environ["LLM_PROVIDER"] = "replay"
        print(("講師の実行記録を再生します" if key else "API キーが見つからないので、講師の実行記録を再生します")
              + " → provider = replay（費用 0）")
        print("  記録と違う依頼（入力を変えたなど）はエラーで止まります。自分で試すときはキーを登録してください。")
    else:
        os.environ["LLM_PROVIDER"] = "mock"
        print("mock で動かします（API を呼びません）。")
        print("  mock の答えは決まった筋書きです。正答率などの数字は性能の証拠になりません。")
    del key
    return os.environ["LLM_PROVIDER"]


def use_lab(name: str):
    """ラボのフォルダ（例: lab03_classify_extract）を import できるようにする。"""
    d = os.path.join(ROOT, name)
    if d not in sys.path:
        sys.path.insert(0, d)
    return d


def lab(module: str, lab_dir: str):
    """ラボのモジュールを読む（例: lab("run_classify", "lab03_classify_extract")）。"""
    use_lab(lab_dir)
    return importlib.import_module(module)


def show(obj, start: int | None = None, end: int | None = None) -> None:
    """関数・クラスの本物のソースを、ファイルから読んで表示する（行番号つき）。"""
    src, first = inspect.getsourcelines(obj)
    path = os.path.relpath(inspect.getsourcefile(obj), ROOT).replace(os.sep, "/")
    lines = src[(start or 0):end]
    print(f"# {path}  {first + (start or 0)} 行目から")
    for i, line in enumerate(lines, first + (start or 0)):
        print(f"{i:4d}  {line.rstrip()}")


def show_file(rel: str, start: int = 1, end: int | None = None, grep: str | None = None) -> None:
    """キットのファイル（依頼文・設定など）を、行番号つきで表示する。grep を渡すとその語を含む行だけ。"""
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        lines = f.read().splitlines()
    print(f"# {rel}")
    for i, line in enumerate(lines[start - 1:end], start):
        if grep and grep not in line:
            continue
        print(f"{i:4d}  {line}")


def redact(s: str) -> str:
    return _SECRET.sub("[伏せ字]", s)


@contextmanager
def safe():
    """セルの中のエラーを短く表示する（キーらしい文字列は伏せる）。"""
    try:
        yield
    except Exception as e:  # noqa: BLE001
        msg = redact(f"{type(e).__name__}: {e}")[:300]
        print(f"⚠ エラーで止まりました: {msg}")
        lines = traceback.format_exc().splitlines()
        tb = redact(lines[-3] if len(lines) >= 3 else "")
        if tb:
            print("  場所:", tb.strip()[:200])
