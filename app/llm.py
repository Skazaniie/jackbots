"""Client for any OpenAI-compatible API, focused on low latency.

- one persistent keep-alive connection per provider + warm-up before the game;
- streaming: for one-line answers generation is cut at the first line break;
- self-tuning: if the model doesn't accept max_tokens/temperature, remember that and retry.
"""
import asyncio
import json
import re
import time

import httpx

from .lang import ui


class LLMError(Exception):
    pass


class LLM:
    def __init__(self):
        self._clients = {}
        self._quirks = {}  # (base_url, model) -> set("max_completion_tokens", "no_temperature", "no_stream")

    def _client(self, p):
        key = (p["base_url"].rstrip("/"), p.get("api_key", ""), json.dumps(p.get("headers") or {}, sort_keys=True))
        c = self._clients.get(key)
        if c is None or c.is_closed:
            headers = {"Content-Type": "application/json"}
            if p.get("api_key"):
                headers["Authorization"] = f"Bearer {p['api_key']}"
            headers.update(p.get("headers") or {})
            c = httpx.AsyncClient(base_url=key[0] + "/", headers=headers,
                                  limits=httpx.Limits(max_keepalive_connections=8, keepalive_expiry=300),
                                  timeout=httpx.Timeout(float(p.get("timeout") or 15), connect=5.0))
            self._clients[key] = c
        return c

    async def close(self):
        for c in self._clients.values():
            await c.aclose()

    async def warmup(self, p):
        """Open the TLS connection in advance so the first answer in the game doesn't spend time on it."""
        try:
            await self._client(p).get("models", timeout=5)
        except Exception:
            pass

    async def list_models(self, p):
        t0 = time.perf_counter()
        r = await self._client(p).get("models")
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code >= 400:
            raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        items = data.get("data", data.get("models", [])) if isinstance(data, dict) else data
        ids = sorted({(m.get("id") or m.get("name", "")).removeprefix("models/") for m in items if isinstance(m, dict)})
        return [i for i in ids if i], ms

    def _body(self, p, model, messages, temperature, max_tokens, stream, extra_body=None):
        q = self._quirks.get((p["base_url"], model), set())
        body = {"model": model, "messages": messages}
        if temperature is not None and "no_temperature" not in q:
            body["temperature"] = temperature
        if max_tokens:
            body["max_completion_tokens" if "max_completion_tokens" in q else "max_tokens"] = max_tokens
        if stream and "no_stream" not in q:
            body["stream"] = True
        body.update(p.get("extra_body") or {})
        body.update(extra_body or {})  # settings of a specific bot/model, e.g. reasoning_effort
        return body

    def _learn(self, p, model, text):
        t = text.lower()
        q = self._quirks.setdefault((p["base_url"], model), set())
        before = set(q)
        if "max_tokens" in t and ("max_completion_tokens" in t or "not supported" in t or "unsupported" in t):
            q.add("max_completion_tokens")
        if "temperature" in t and ("support" in t or "only the default" in t):
            q.add("no_temperature")
        if "stream" in t and ("support" in t or "verify" in t):
            q.add("no_stream")
        return q != before

    async def chat(self, p, model, messages, temperature=0.9, max_tokens=60, one_line=True, deadline_s=None,
                   extra_body=None):
        """Returns dict(text, ms, ttft, tokens). Raises LLMError."""
        stream = bool(p.get("stream", True))
        if p.get("max_tokens"):
            max_tokens = int(p["max_tokens"])
        attempts = 3 if p.get("retry", True) else 1
        t0 = time.perf_counter()
        last = None
        for _ in range(attempts + 2):  # +2 attempts for parameter self-tuning
            if deadline_s and time.perf_counter() - t0 > deadline_s:
                break
            try:
                return await self._chat_once(p, model, messages, temperature, max_tokens, stream, one_line, t0,
                                             extra_body)
            except LLMError as e:
                last = e
                if self._learn(p, model, str(e)):
                    continue
                attempts -= 1
                if attempts <= 0 or "HTTP 4" in str(e) and "HTTP 429" not in str(e):
                    break
                await asyncio.sleep(0.3)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last = LLMError(ui("network: {e}", e=type(e).__name__))
                attempts -= 1
                if attempts <= 0:
                    break
        raise last or LLMError(ui("timed out"))

    async def _chat_once(self, p, model, messages, temperature, max_tokens, stream, one_line, t0, extra_body=None):
        c = self._client(p)
        body = self._body(p, model, messages, temperature, max_tokens, stream, extra_body)
        if not body.get("stream"):
            r = await c.post("chat/completions", json=body)
            if r.status_code >= 400:
                raise LLMError(f"HTTP {r.status_code}: {r.text[:400]}")
            d = r.json()
            ms = int((time.perf_counter() - t0) * 1000)
            msg = (d.get("choices") or [{}])[0].get("message") or {}
            text = msg.get("content") or ""
            tok = (d.get("usage") or {}).get("completion_tokens", 0)
            return {"text": _clean(text, one_line), "ms": ms, "ttft": ms, "tokens": tok}
        text, ttft, chunks = "", None, 0
        async with c.stream("POST", "chat/completions", json=body) as r:
            if r.status_code >= 400:
                raw = (await r.aread()).decode("utf-8", "replace")
                raise LLMError(f"HTTP {r.status_code}: {raw[:400]}")
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    d = json.loads(data)
                except ValueError:
                    continue
                if d.get("error"):
                    raise LLMError(str(d["error"])[:400])
                for ch in d.get("choices") or []:
                    piece = (ch.get("delta") or {}).get("content") or ""
                    if piece:
                        if ttft is None:
                            ttft = int((time.perf_counter() - t0) * 1000)
                        text += piece
                        chunks += 1
                if one_line and "\n" in _strip_think(text).strip():
                    break  # the one-line answer is ready, don't wait for the tail
        ms = int((time.perf_counter() - t0) * 1000)
        return {"text": _clean(text, one_line), "ms": ms, "ttft": ttft or ms, "tokens": chunks}


# "thinking" blocks in the answer text: <think> (DeepSeek/Qwen), <thinking>, <mm:think> (MiniMax)
_THINK_BLOCK = re.compile(r"<((?:mm:)?think(?:ing)?)>.*?</\1>", re.S)
_THINK_OPEN = re.compile(r"<(?:mm:)?think(?:ing)?>")


def _strip_think(t):
    t = _THINK_BLOCK.sub("", t)
    m = _THINK_OPEN.search(t)  # unclosed block: the model is still thinking, no answer yet
    return t[:m.start()] if m else t


def _clean(t, one_line):
    t = _strip_think(t).strip()
    if one_line:
        t = next((ln.strip() for ln in t.splitlines() if ln.strip()), "")
    t = t.strip().strip('"«»“”„\'`*').strip()
    for pre in ("Ответ:", "ответ:", "Answer:"):
        if t.startswith(pre):
            t = t[len(pre):].strip().strip('"«»')
    return t
