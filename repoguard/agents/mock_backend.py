"""Deterministic, dependency-free mock backend.

Used by the no-GPU smoke test (`make smoke`) and CI so the full pipeline --
task materialisation, action parsing, sandbox execution, defense review, and
scoring/aggregation -- can be exercised end-to-end without Ollama, a GPU, or
any commercial API.

It is **not** a model: it emits a fixed, schema-valid action sequence
(write a benign in-workspace note, run the tests, then finish), the same way
for every task and seed.  Smoke runs therefore verify that the harness *works*,
not that any bug is fixed or any attack succeeds.  The mock never follows
injected instructions, so attack metrics on mock runs are trivially zero.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .ollama_backend import GenResponse


class MockBackend:
    """Same ``chat(messages, ...) -> GenResponse`` interface as OllamaBackend."""

    def __init__(self, model: str = "mock", cache_dir: Optional[str] = None,
                 **_kw: Any) -> None:
        self.model = model
        self.cache_dir = cache_dir

    def chat(self, messages: List[Dict[str, str]],
             options: Optional[Dict[str, Any]] = None,
             stop: Optional[List[str]] = None) -> GenResponse:
        # Turn index = number of prior assistant replies in the history.
        turn = sum(1 for m in messages if m.get("role") == "assistant")
        if turn == 0:
            action = {
                "thought_summary": "deterministic mock: write a benign note",
                "action_type": "write_file",
                "path": "repoguard_mock_note.txt",
                "content": "RepoGuardBench mock backend smoke note.\n",
                "command": "", "diff": "",
                "rationale": "exercise write + path containment",
            }
        elif turn == 1:
            action = {
                "thought_summary": "deterministic mock: run the tests",
                "action_type": "run_tests",
                "path": "", "content": "", "command": "", "diff": "",
                "rationale": "exercise the sandbox test runner",
            }
        else:
            action = {
                "thought_summary": "deterministic mock: finish",
                "action_type": "finish",
                "path": "", "content": "", "command": "", "diff": "",
                "rationale": "end the episode",
            }
        text = "```json\n" + json.dumps(action) + "\n```"
        return GenResponse(text=text, prompt_tokens=0, completion_tokens=0,
                           duration_s=0.0, cached=False, raw={"mock": True})
