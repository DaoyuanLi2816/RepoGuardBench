"""Thin HTTP client for the local Ollama daemon.

This backend talks only to the local Ollama daemon; it confirms at
construction time that the model is present locally, and records every
request/response hash to the cache so identical inputs do not re-run the
model.  (The separate Claude reference backend is the only non-local path.)
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from ..utils.io import cache_key, read_json, write_json


DEFAULT_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


class BackendError(RuntimeError):
    pass


@dataclass
class GenResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    duration_s: float
    cached: bool
    raw: Dict[str, Any]


class OllamaBackend:
    def __init__(self, model: str, base_url: str = DEFAULT_BASE_URL,
                 cache_dir: Optional[str] = None,
                 default_options: Optional[Dict[str, Any]] = None) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_options = default_options or {
            "temperature": 0.0,
            "top_p": 0.95,
            "num_predict": 1536,
            "num_ctx": 8192,
            "seed": 7,
            "repeat_penalty": 1.05,
        }
        self._verify_local()

    def _verify_local(self) -> None:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=8)
            r.raise_for_status()
        except Exception as exc:
            raise BackendError(f"cannot reach Ollama at {self.base_url}: {exc}")
        names = {m.get("name") for m in r.json().get("models", [])}
        if self.model not in names:
            raise BackendError(
                f"model {self.model!r} not present locally. ollama list returns {sorted(names)}"
            )

    def _cache_path(self, key: str) -> Optional[Path]:
        return self.cache_dir / f"{key}.json" if self.cache_dir else None

    def chat(self, messages: List[Dict[str, str]],
             options: Optional[Dict[str, Any]] = None,
             stop: Optional[List[str]] = None) -> GenResponse:
        opts = dict(self.default_options)
        if options:
            opts.update(options)
        if stop:
            opts["stop"] = stop
        payload = {
            "model": self.model,
            "messages": messages,
            "options": opts,
            "stream": False,
            "keep_alive": "10m",
        }
        key = cache_key("chat", self.model, messages, opts, stop)
        cp = self._cache_path(key)
        if cp is not None and cp.exists():
            obj = read_json(cp)
            return GenResponse(
                text=obj["text"],
                prompt_tokens=obj.get("prompt_tokens", 0),
                completion_tokens=obj.get("completion_tokens", 0),
                duration_s=obj.get("duration_s", 0.0),
                cached=True,
                raw=obj.get("raw", {}),
            )
        t0 = time.time()
        try:
            r = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=600)
            r.raise_for_status()
        except Exception as exc:
            raise BackendError(f"ollama chat failed: {exc}")
        data = r.json()
        text = (data.get("message") or {}).get("content", "")
        out = GenResponse(
            text=text,
            prompt_tokens=int(data.get("prompt_eval_count", 0)),
            completion_tokens=int(data.get("eval_count", 0)),
            duration_s=time.time() - t0,
            cached=False,
            raw=data,
        )
        if cp is not None:
            write_json(cp, {
                "text": out.text,
                "prompt_tokens": out.prompt_tokens,
                "completion_tokens": out.completion_tokens,
                "duration_s": out.duration_s,
                "raw": {k: data.get(k) for k in ("model", "done", "total_duration",
                                                  "load_duration", "eval_count",
                                                  "prompt_eval_count")},
            })
        return out
