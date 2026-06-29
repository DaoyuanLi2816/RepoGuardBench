"""OPTIONAL, NON-LOCAL Claude reference backend.

This adapter drives a separately installed ``claude`` CLI in headless
(``-p/--print``) mode and exposes the SAME ``chat()`` interface as
``OllamaBackend``, so the existing ``run_agent`` loop, defenses, sandbox, and
scorer drive it unchanged.  It is the closed-model reference point reported in
the paper and is **excluded from the primary local headline aggregate**.

Important:
  * This backend is NOT part of the default (local, reproducible) workflow.
  * Re-running it requires the user's OWN commercial access / CLI install; no
    credentials, account identifiers, or provider metadata are bundled here.
    The adapter reads no API keys and stores none.
  * All agent tools are disabled (``--disallowedTools``) so the model only
    emits one RepoGuardBench JSON action per turn; the harness (not the model)
    executes those actions through the sandbox.  This evaluates a commercial
    coding agent constrained to the action schema, not a raw-weight comparison.

Responses are cached on disk keyed by (model, messages) so reruns are free and
resumable, like the Ollama cache.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Mirror OllamaBackend.GenResponse so downstream code is backend-agnostic.
from .ollama_backend import GenResponse

# Tools we forbid so Claude cannot touch the filesystem / network and instead
# just emits the next JSON action as text.
_DISALLOWED_TOOLS = [
    "Bash", "Read", "Write", "Edit", "NotebookEdit", "Glob", "Grep",
    "WebFetch", "WebSearch", "Task", "TodoWrite",
]


def _find_claude() -> str:
    exe = shutil.which("claude")
    if exe:
        return exe
    # Common Windows install location fallback.
    for cand in (
        os.path.expandvars(r"%APPDATA%\npm\claude.cmd"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\claude\claude.exe"),
    ):
        if os.path.exists(cand):
            return cand
    raise RuntimeError("claude CLI not found on PATH")


def _flatten_messages(messages: List[Dict[str, str]]) -> tuple[str, str]:
    """Split into (system_prompt, conversation_prompt).

    The system message goes to --append-system-prompt; the user/assistant
    history is reconstructed into a single prompt string that ends with the
    latest user turn, so the model has the same context an API chat call
    would receive.
    """
    system_parts: List[str] = []
    convo: List[str] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            system_parts.append(content)
        elif role == "assistant":
            convo.append(f"[PREVIOUS ASSISTANT ACTION]\n{content}")
        else:  # user
            convo.append(content)
    system_prompt = "\n\n".join(system_parts).strip()
    conversation = "\n\n".join(convo).strip()
    return system_prompt, conversation


@dataclass
class ClaudeCLIBackend:
    model: str
    cache_dir: Optional[str] = None
    timeout_s: float = 240.0
    default_options: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        self._claude = _find_claude()
        if self.cache_dir:
            Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

    # -- caching ---------------------------------------------------------
    def _cache_key(self, messages: List[Dict[str, str]]) -> str:
        h = hashlib.sha256()
        h.update(("claude_cli|" + self.model + "|").encode("utf-8"))
        h.update(json.dumps(messages, ensure_ascii=False, sort_keys=False).encode("utf-8"))
        return h.hexdigest()

    def _cache_path(self, key: str) -> Optional[Path]:
        if not self.cache_dir:
            return None
        return Path(self.cache_dir) / f"claude_{key}.json"

    # -- main entry ------------------------------------------------------
    def chat(self, messages: List[Dict[str, str]],
             options: Optional[Dict[str, Any]] = None,
             stop: Optional[List[str]] = None) -> GenResponse:
        key = self._cache_key(messages)
        cpath = self._cache_path(key)
        if cpath and cpath.exists():
            try:
                d = json.loads(cpath.read_text(encoding="utf-8"))
                return GenResponse(text=d["text"], prompt_tokens=d.get("prompt_tokens", 0),
                                   completion_tokens=d.get("completion_tokens", 0),
                                   duration_s=d.get("duration_s", 0.0), cached=True,
                                   raw=d.get("raw", {}))
            except Exception:
                pass

        system_prompt, conversation = _flatten_messages(messages)
        cmd = [self._claude, "-p", conversation,
               "--model", self.model,
               "--output-format", "json",
               "--disallowedTools", *_DISALLOWED_TOOLS]
        if system_prompt:
            cmd += ["--append-system-prompt", system_prompt]

        t0 = time.time()
        proc = subprocess.run(
            cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=self.timeout_s,
            shell=False,
        )
        dt = time.time() - t0
        out = (proc.stdout or "").strip()
        if not out:
            raise RuntimeError(f"claude CLI empty output (rc={proc.returncode}): "
                               f"{(proc.stderr or '')[:300]}")
        # Output is a single JSON object (result envelope).
        try:
            env = json.loads(out)
        except json.JSONDecodeError:
            # Some shells prepend warnings; grab the last JSON object.
            start = out.rfind("{")
            env = json.loads(out[start:]) if start >= 0 else {}
        text = env.get("result", "") or ""
        pt = ct = 0
        mu = (env.get("modelUsage") or {}).get(self.model) or {}
        if mu:
            pt = int(mu.get("inputTokens", 0) or 0)
            ct = int(mu.get("outputTokens", 0) or 0)
        else:
            usage = env.get("usage") or {}
            pt = int(usage.get("input_tokens", 0) or 0)
            ct = int(usage.get("output_tokens", 0) or 0)
        resp = GenResponse(text=text, prompt_tokens=pt, completion_tokens=ct,
                           duration_s=dt, cached=False,
                           raw={"cost_usd": env.get("total_cost_usd"),
                                "stop_reason": env.get("stop_reason"),
                                "is_error": env.get("is_error")})
        if cpath:
            try:
                cpath.write_text(json.dumps({
                    "text": text, "prompt_tokens": pt, "completion_tokens": ct,
                    "duration_s": dt, "raw": resp.raw,
                }, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        return resp
