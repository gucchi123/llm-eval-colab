"""LLM 呼び出しを 1 か所にまとめる（評価講座の全ラボで共通）。

GraphRAG 講座の common/llm.py と同じ約束で作り、道具呼び出し（エージェントのラボ用）を足した。

  provider
  - mock      : 決まった筋書きで答える（既定）。API キーもネットも不要。🔴 数字は性能の証拠にしない
  - replay    : 講師が API で回したときの応答（.cache/llm/）だけを返す。記録に無ければエラー。費用 0
  - anthropic : Anthropic API（ANTHROPIC_API_KEY）。同じ依頼の記録があればそれを返す（費用 0）

  モデルと考える深さ
  - LLM_MODEL（既定 claude-opus-5-5）。各スクリプトの --model でも替えられる（Sonnet と Opus の比較用）
  - LLM_EFFORT（既定 high）。output_config={"effort": ...} で渡す
  - 応答キャッシュ: 同じ依頼（モデル・effort・本文・道具）は 2 回目から API を呼ばない
  - 費用台帳: _api_cost_ledger.jsonl に 1 呼び出し 1 行。合計が LLM_BUDGET_USD（既定 5）に近づくと止まる
  - LLM_CACHE_ONLY=1 なら記録に無い依頼は API を呼ばずにエラー（費用が絶対に出ない）

🔴 キーは画面・ファイル・例外文に出さない。キャッシュの鍵にも入れない。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"


class BudgetExceeded(RuntimeError):
    pass


class CacheMiss(RuntimeError):
    pass


@dataclass
class Result:
    text: str
    provider: str
    model: str = ""
    seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    cached: bool = False
    stop_reason: str = ""
    content: list = field(default_factory=list)   # 道具呼び出しを含む生のブロック（dict）

    @property
    def tool_calls(self) -> list[dict]:
        return [b for b in self.content if b.get("type") == "tool_use"]


def provider_name(provider: str | None = None) -> str:
    return provider or os.environ.get("LLM_PROVIDER", "mock")


def model_name(model: str | None = None) -> str:
    return model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)


def effort_name(effort: str | None = None) -> str:
    return effort or os.environ.get("LLM_EFFORT", DEFAULT_EFFORT)


# ---------------------------------------------------------------- mock
# MOCK_HANDLERS に fn(system, messages, tools, model) -> str | list[dict] | None を足す。
# 文字列なら本文、リストならブロック（道具呼び出しなど）として返す。最初に None 以外を返したものを使う。
MOCK_HANDLERS: list[Callable[..., Any]] = []


def _mock(system, messages, tools, model) -> Result:
    for fn in MOCK_HANDLERS:
        out = fn(system, messages, tools, model)
        if out is None:
            continue
        if isinstance(out, str):
            content = [{"type": "text", "text": out}]
        else:
            content = out
        text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
        stop = "tool_use" if any(b.get("type") == "tool_use" for b in content) else "end_turn"
        return Result(text=text, provider="mock", model=f"mock:{model}", content=content, stop_reason=stop)
    last = messages[-1]["content"] if messages else ""
    head = last if isinstance(last, str) else json.dumps(last, ensure_ascii=False)
    return Result(text=f"[mock] {head[:60]}", provider="mock", model=f"mock:{model}",
                  content=[{"type": "text", "text": f"[mock] {head[:60]}"}], stop_reason="end_turn")


@contextmanager
def mock_handler(fn):
    """with mock_handler(fn): の間だけ fn を最優先の筋書きにする。"""
    MOCK_HANDLERS.insert(0, fn)
    try:
        yield
    finally:
        MOCK_HANDLERS.remove(fn)


# ---------------------------------------------------------------- 単価・台帳・予算
# USD / 100 万トークン: (入力, 出力, キャッシュ読み)。キャッシュ書きは入力の 1.25 倍。
# 2026-10 時点の公式単価（研究メモ research/sources.md で確認）。
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10),
    "claude-haiku-4-5": (1.0, 5.0, 0.10),
}


def price(model: str) -> tuple[float, float, float]:
    for k, v in PRICES.items():
        if model.startswith(k):
            return v
    return (5.0, 25.0, 0.5)   # 知らないモデルは高めに見積もる


def cost_of(model: str, inp: int, out: int, cache_read: int = 0, cache_write: int = 0) -> float:
    pin, pout, pcr = price(model)
    return (inp * pin + out * pout + cache_read * pcr + cache_write * pin * 1.25) / 1_000_000


def _ledger_path() -> str:
    return os.environ.get("LLM_LEDGER", os.path.join(ROOT, "_api_cost_ledger.jsonl"))


def _cache_dir() -> str:
    return os.environ.get("LLM_CACHE_DIR", os.path.join(ROOT, ".cache", "llm"))


def _budget() -> float:
    return float(os.environ.get("LLM_BUDGET_USD", "5"))


_lock = threading.Lock()
_TAG = {"v": ""}   # 並列（スレッド）の呼び出しにも同じ印が付くよう、スレッドごとではなく 1 つにする


@contextmanager
def tag(name: str):
    """台帳でラボ・実験を分ける印。with L.tag("lab03/opus"): ..."""
    old = _TAG["v"]
    _TAG["v"] = name
    try:
        yield
    finally:
        _TAG["v"] = old


def current_tag() -> str:
    return _TAG["v"]


def read_ledger() -> list[dict]:
    p = _ledger_path()
    rows = []
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    return rows


def spent() -> float:
    return sum(float(e.get("cost_usd", 0)) for e in read_ledger())


def _record(entry: dict) -> None:
    with _lock:
        with open(_ledger_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def ledger_summary(since: str | None = None, tag_prefix: str | None = None) -> dict:
    s = {"calls": 0, "cached_calls": 0, "cost_usd": 0.0, "in": 0, "out": 0, "seconds": 0.0}
    for e in read_ledger():
        if since and e.get("t", "") < since:
            continue
        if tag_prefix and not str(e.get("tag", "")).startswith(tag_prefix):
            continue
        if e.get("cached"):
            s["cached_calls"] += 1
            continue
        s["calls"] += 1
        s["cost_usd"] += float(e.get("cost_usd", 0))
        s["in"] += int(e.get("in", 0))
        s["out"] += int(e.get("out", 0))
        s["seconds"] += float(e.get("seconds", 0))
    s["cost_usd"] = round(s["cost_usd"], 4)
    s["seconds"] = round(s["seconds"], 1)
    return s


# ---------------------------------------------------------------- 応答キャッシュ
def _key(model, effort, system, messages, tools, max_tokens) -> str:
    blob = json.dumps({"m": model, "e": effort, "s": system or "", "msg": messages, "t": tools or [],
                       "mt": max_tokens}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> str:
    return os.path.join(_cache_dir(), key[:2], key + ".json")


def _cache_get(key: str) -> dict | None:
    p = _cache_path(key)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def _cache_put(key: str, data: dict) -> None:
    p = _cache_path(key)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = f"{p}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    try:
        os.replace(tmp, p)
    except PermissionError:
        os.remove(tmp)


# ---------------------------------------------------------------- Anthropic
def _api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key or os.name != "nt":
        return key
    try:  # Windows: ユーザー環境変数に保存したキーを読む（値は表示しない）
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, "ANTHROPIC_API_KEY")[0]
    except OSError:
        return None


def has_key() -> bool:
    return bool(_api_key())


_client = None


def _anthropic_client():
    global _client
    if _client is None:
        import anthropic
        key = _api_key()
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY が見つかりません（環境変数に置いてください。キーは表示しません）")
        _client = anthropic.Anthropic(api_key=key, max_retries=5, timeout=900)
    return _client


def _block_to_dict(b) -> dict:
    t = getattr(b, "type", "")
    if t == "text":
        return {"type": "text", "text": b.text}
    if t == "tool_use":
        return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
    return {"type": t}   # thinking などは中身を持ち回らない（記録を小さく保つ）


def _anthropic(system, messages, tools, model, effort, max_tokens) -> Result:
    if spent() + 0.25 >= _budget():
        raise BudgetExceeded(f"予算 {_budget()} USD に近づいたので止めます（使用済み {spent():.2f} USD）")
    client = _anthropic_client()
    kwargs: dict[str, Any] = dict(model=model, max_tokens=max_tokens, messages=messages)
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools
    if effort:
        kwargs["output_config"] = {"effort": effort}
    t0 = time.time()
    try:
        with client.messages.stream(**kwargs) as stream:
            msg = stream.get_final_message()
    except Exception as e:  # 例外文にキーが混ざらないよう、型と短い文だけを出す
        msg_txt = re.sub(r"sk-ant-[A-Za-z0-9_\-]+", "sk-ant-***", str(e))[:300]
        raise RuntimeError(f"API 呼び出しに失敗しました: {type(e).__name__}: {msg_txt}") from None
    secs = time.time() - t0
    content = [_block_to_dict(b) for b in msg.content]
    content = [b for b in content if b["type"] in ("text", "tool_use")]
    text = "".join(b.get("text", "") for b in content if b["type"] == "text")
    u = msg.usage
    cr = int(getattr(u, "cache_read_input_tokens", 0) or 0)
    cw = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
    cost = cost_of(msg.model, u.input_tokens, u.output_tokens, cr, cw)
    return Result(text=text, provider="anthropic", model=msg.model, seconds=secs, input_tokens=u.input_tokens,
                  output_tokens=u.output_tokens, cache_read_tokens=cr, cache_write_tokens=cw, cost_usd=cost,
                  stop_reason=str(msg.stop_reason), content=content)


# ---------------------------------------------------------------- 公開 API
def chat(messages: list[dict], *, system: str | None = None, tools: list[dict] | None = None,
         provider: str | None = None, model: str | None = None, effort: str | None = None,
         max_tokens: int | None = None, trial: int = 0) -> Result:
    """会話（messages）で 1 回呼ぶ。道具を渡せば Result.tool_calls に呼び出しが入る。

    trial: 同じ依頼を何度も試す（揺れを測る）ときの番号。API には送らず、記録の鍵だけを変える。
    """
    p = provider_name(provider)
    model = model_name(model)
    if p == "mock":
        return _mock(system, messages, tools, model if not trial else f"{model}#{trial}")
    effort = effort_name(effort)
    max_tokens = max_tokens or int(os.environ.get("LLM_MAX_TOKENS", "16000"))
    key = _key(model, effort, system, messages, tools, max_tokens)
    if trial:
        key = hashlib.sha256(f"{key}#trial{trial}".encode()).hexdigest()
    cache_only = os.environ.get("LLM_CACHE_ONLY", "0") == "1"
    use_cache = os.environ.get("LLM_CACHE", "1") != "0"
    t = current_tag()
    if use_cache:
        hit = _cache_get(key)
        if hit:
            if not cache_only:
                _record({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": hit.get("model"), "in": 0, "out": 0,
                         "seconds": 0, "cost_usd": 0.0, "cached": True, "tag": t})
            return Result(text=hit["text"], provider=p, model=hit.get("model", model), cached=True,
                          input_tokens=hit.get("in", 0), output_tokens=hit.get("out", 0),
                          seconds=hit.get("seconds", 0.0), cost_usd=hit.get("cost_usd", 0.0),
                          stop_reason=hit.get("stop", ""), content=hit.get("content", []))
    if p == "replay" or cache_only:
        raise CacheMiss(f"記録がありません（tag={t}）。replay / LLM_CACHE_ONLY=1 なので API は呼びません")
    if p != "anthropic":
        raise ValueError(f"未知の provider: {p}")
    r = _anthropic(system, messages, tools, model, effort, max_tokens)
    _record({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": r.model, "in": r.input_tokens,
             "out": r.output_tokens, "cache_read": r.cache_read_tokens, "cache_write": r.cache_write_tokens,
             "seconds": round(r.seconds, 2), "cost_usd": round(r.cost_usd, 6), "stop": r.stop_reason,
             "effort": effort, "tag": t})
    if use_cache and r.stop_reason in ("end_turn", "stop_sequence", "tool_use", "refusal"):   # 断りも記録（再生で同じ結果になる）
        # 元の呼び出しの時間・費用も残す（再生時に「本物の実行ではいくらかかったか」を表に出せる）
        _cache_put(key, {"text": r.text, "model": r.model, "in": r.input_tokens, "out": r.output_tokens,
                         "seconds": round(r.seconds, 2), "cost_usd": round(r.cost_usd, 6),
                         "stop": r.stop_reason, "content": r.content, "t": time.strftime("%Y-%m-%dT%H:%M:%S")})
    return r


def call(prompt: str, **kwargs) -> Result:
    """1 問 1 答の近道。"""
    return chat([{"role": "user", "content": prompt}], **kwargs)


def extract_json(text: str) -> Any:
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except ValueError:
            pass
    i, j = text.find("{"), text.rfind("}")
    if i >= 0 and j > i:
        return json.loads(text[i:j + 1])
    raise ValueError("JSON が見つかりません")


def call_json(prompt: str, *, validate: Callable[[Any], str | None] | None = None, retries: int = 1,
              **kwargs) -> tuple[Any, list[Result]]:
    """JSON で答えさせる。読めない・validate が文句を返したら 1 回だけ頼み直す。"""
    results: list[Result] = []
    p, err = prompt, ""
    for attempt in range(retries + 1):
        r = call(p, **kwargs)
        results.append(r)
        try:
            obj = extract_json(r.text)
            err = validate(obj) if validate else None
            if not err:
                return obj, results
        except ValueError as e:
            err = f"JSON として読めません: {e}"
        p = prompt + f"\n\n（再試行: 前回の出力に問題がありました: {str(err)[:200]}。JSON だけを出し直してください）"
    raise RuntimeError(f"JSON の出力が {retries + 1} 回とも不正でした: {err}")


def usage_of(results: list[Result]) -> dict:
    """呼び出し群の費用・時間・トークン（キャッシュ再生でも元の実行の値を返す）。"""
    return {"calls": len(results), "cost_usd": round(sum(r.cost_usd for r in results), 6),
            "seconds": round(sum(r.seconds for r in results), 2),
            "in": sum(r.input_tokens for r in results), "out": sum(r.output_tokens for r in results),
            "cached": sum(1 for r in results if r.cached)}
