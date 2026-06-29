"""Tests for the JSON-action parser."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from repoguard.agents.agent_loop import parse_action


def test_parses_triple_backtick_json():
    text = '```json\n{"action_type": "finish"}\n```'
    p = parse_action(text)
    assert p is not None and p["action_type"] == "finish"


def test_parses_single_backtick_fence_used_by_small_models():
    text = '`json\n{"action_type": "read_file", "path": "x"}\n`'
    p = parse_action(text)
    assert p is not None and p["action_type"] == "read_file"


def test_parses_bare_object_without_fence():
    text = 'Sure, here is the next action: {"action_type": "run_tests"}'
    p = parse_action(text)
    assert p is not None and p["action_type"] == "run_tests"


def test_structural_fallback_for_python_triple_quoted_content():
    text = ('```json\n{\n'
            '"action_type": "write_file",\n'
            '"path": "src/m.py",\n'
            "\"content\": '''def f():\n    pass'''\n"
            '}\n```')
    p = parse_action(text)
    assert p is not None
    assert p["action_type"] == "write_file"
    assert p["path"] == "src/m.py"
    assert "def f" in p["content"]


def test_returns_none_on_empty():
    assert parse_action("") is None
    assert parse_action(None) is None  # type: ignore[arg-type]
