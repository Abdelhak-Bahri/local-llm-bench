"""Minimal OpenAI-compatible streaming client. Stdlib only, so the harness
runs on a clean machine with nothing but Python 3.10+.

Timing is taken on the client from the SSE stream, not from any server-side
field, so the numbers mean the same thing whichever server you point it at.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field


@dataclass
class Result:
    ok: bool
    content: str = ""
    reasoning: str = ""
    tool_calls: list = field(default_factory=list)
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    chunks: int = 0                # content+reasoning delta events seen
    t_start: float = 0.0
    t_first: float | None = None   # first token of any kind (reasoning or content)
    t_first_content: float | None = None
    t_end: float = 0.0
    error: str | None = None
    timings: dict | None = None    # llama.cpp's own timings block, if sent

    @property
    def ttft(self) -> float | None:
        return None if self.t_first is None else self.t_first - self.t_start

    @property
    def total(self) -> float:
        return self.t_end - self.t_start

    @property
    def out_tokens(self) -> int:
        return self.completion_tokens if self.completion_tokens is not None else self.chunks

    @property
    def decode_tps(self) -> float | None:
        """Tokens/s after the first token. Excludes prefill entirely."""
        if self.t_first is None or self.out_tokens < 2:
            return None
        dt = self.t_end - self.t_first
        return (self.out_tokens - 1) / dt if dt > 0 else None

    @property
    def prefill_tps(self) -> float | None:
        if not self.prompt_tokens or not self.ttft:
            return None
        return self.prompt_tokens / self.ttft

    def summary(self) -> dict:
        return {
            "ok": self.ok, "error": self.error, "finish_reason": self.finish_reason,
            "prompt_tokens": self.prompt_tokens, "completion_tokens": self.out_tokens,
            "ttft_s": self.ttft, "total_s": self.total,
            "decode_tps": self.decode_tps, "prefill_tps": self.prefill_tps,
            "server_timings": self.timings,
        }


class Client:
    def __init__(self, base_url: str, api_key: str | None, model: str | None = None,
                 timeout: float = 900):
        self.base = base_url.rstrip("/")
        self.key = api_key
        self.model = model
        self.timeout = timeout

    def _req(self, path: str, body: dict | None = None):
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        data = json.dumps(body).encode() if body is not None else None
        return urllib.request.Request(self.base + path, data=data, headers=headers,
                                      method="POST" if body is not None else "GET")

    def models(self) -> list[str]:
        with urllib.request.urlopen(self._req("/models"), timeout=30) as r:
            return [m["id"] for m in json.load(r)["data"]]

    def pick_model(self, needle: str) -> str:
        ids = self.models()
        hits = [m for m in ids if needle.lower() in m.lower()]
        if not hits:
            raise SystemExit(f"No model matching {needle!r}. Server offers: {ids}")
        self.model = hits[0]
        return self.model

    def chat(self, messages: list, **params) -> Result:
        body = {"model": self.model, "messages": messages, "stream": True,
                "stream_options": {"include_usage": True}, **params}
        res = Result(ok=False, t_start=time.perf_counter())
        tool_acc: dict[int, dict] = {}
        try:
            with urllib.request.urlopen(self._req("/chat/completions", body),
                                        timeout=self.timeout) as r:
                for raw in r:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        ev = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    now = time.perf_counter()
                    if ev.get("usage"):
                        u = ev["usage"]
                        res.prompt_tokens = u.get("prompt_tokens", res.prompt_tokens)
                        res.completion_tokens = u.get("completion_tokens", res.completion_tokens)
                    if ev.get("timings"):
                        res.timings = ev["timings"]
                    for ch in ev.get("choices") or []:
                        d = ch.get("delta") or {}
                        rc = d.get("reasoning_content") or d.get("reasoning")
                        c = d.get("content")
                        if rc:
                            res.reasoning += rc
                        if c:
                            res.content += c
                            if res.t_first_content is None:
                                res.t_first_content = now
                        for tc in d.get("tool_calls") or []:
                            slot = tool_acc.setdefault(tc.get("index", 0),
                                                       {"name": "", "arguments": ""})
                            fn = tc.get("function") or {}
                            slot["name"] += fn.get("name") or ""
                            slot["arguments"] += fn.get("arguments") or ""
                        if rc or c or d.get("tool_calls"):
                            res.chunks += 1
                            if res.t_first is None:
                                res.t_first = now
                        if ch.get("finish_reason"):
                            res.finish_reason = ch["finish_reason"]
            res.ok = True
        except urllib.error.HTTPError as e:
            res.error = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}"
        except Exception as e:  # noqa: BLE001 - a benchmark records failures, it doesn't crash on them
            res.error = f"{type(e).__name__}: {e}"
        res.t_end = time.perf_counter()
        res.tool_calls = [tool_acc[i] for i in sorted(tool_acc)]
        return res


def load_key(path: str | None) -> str | None:
    if os.environ.get("BENCH_API_KEY"):
        return os.environ["BENCH_API_KEY"].strip()
    if path:
        with open(os.path.expanduser(path)) as f:
            return f.read().strip()
    return None


def strip_thinking(text: str) -> str:
    """Some chat templates inline reasoning as <think>...</think> in content.
    An unclosed <think> (generation cut off mid-thought) leaves no answer."""
    import re
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return re.sub(r"<think>.*", "", text, flags=re.S).strip()


def studio_busy(client: "Client") -> int | None:
    """Unsloth Studio only: how many generations are running right now (UI
    chats included). None if the endpoint doesn't exist on this server."""
    root = client.base.rsplit("/v1", 1)[0]
    req = urllib.request.Request(root + "/api/inference/active-generations",
                                 headers={"Authorization": f"Bearer {client.key}"} if client.key else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return int(json.load(r).get("count", 0))
    except Exception:
        return None


def wait_idle(client: "Client", max_wait: float = 900, log=print) -> float:
    """Block until nothing else is generating, so timings aren't polluted by
    someone chatting in the UI. Returns seconds waited."""
    t0 = time.perf_counter()
    warned = False
    while (n := studio_busy(client)):
        if time.perf_counter() - t0 > max_wait:
            log(f"!! server still busy ({n}) after {max_wait}s, measuring anyway")
            break
        if not warned:
            log(f"server busy with {n} other generation(s), waiting...")
            warned = True
        time.sleep(3)
    return time.perf_counter() - t0
