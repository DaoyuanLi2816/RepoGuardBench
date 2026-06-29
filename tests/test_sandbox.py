"""Unit tests for the workspace sandbox.

These exercise the security-critical surfaces: path containment, command
allow-/block-list, environment scrubbing.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import pytest

from repoguard.sandbox.workspace import Workspace, SandboxError


def test_resolve_blocks_absolute_path():
    # Platform-appropriate absolute path (absolute on both Windows and POSIX).
    abs_path = r"C:\Windows\System32\drivers\etc\hosts" if os.name == "nt" \
        else "/etc/hosts"
    with Workspace.create(task_id="t1") as ws:
        with pytest.raises(SandboxError):
            ws.write_file(abs_path, "X")


def test_resolve_blocks_parent_escape():
    with Workspace.create(task_id="t2") as ws:
        with pytest.raises(SandboxError):
            ws.write_file("../escape.txt", "X")


def test_write_and_read_round_trip():
    with Workspace.create(task_id="t3") as ws:
        ws.write_file("src/m.py", "x = 1\n")
        assert ws.read_file("src/m.py") == "x = 1\n"


def test_shell_blocks_network():
    with Workspace.create(task_id="t4") as ws:
        cr = ws.attempt_shell("curl http://example.com")
        assert cr.blocked is True
        assert "hard_block" in cr.block_reason


def test_shell_blocks_unknown_binary():
    with Workspace.create(task_id="t5") as ws:
        cr = ws.attempt_shell("rm -rf /")
        assert cr.blocked is True


def test_shell_allows_safe_listing():
    with Workspace.create(task_id="t6") as ws:
        ws.write_file("a.txt", "x")
        cr = ws.attempt_shell("dir" if sys.platform == "win32" else "ls")
        # Either executed or blocked because dir/ls is a shell builtin -
        # the important thing is we didn't classify it as hard-block.
        assert "hard_block" not in cr.block_reason


def test_shell_scrubbed_env_strips_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "real-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "real-secret-2")
    with Workspace.create(task_id="t7") as ws:
        env = ws._scrubbed_env()
        assert "OPENAI_API_KEY" not in env
        assert "ANTHROPIC_API_KEY" not in env


def test_canary_plant_and_visibility():
    with Workspace.create(task_id="t8") as ws:
        p = ws.plant_canary()
        assert p.exists()
        text = ws.read_file(ws.canary_filename)
        assert "REPOGUARD-CANARY-t8" in text


def test_attack_log_detection():
    with Workspace.create(task_id="t9") as ws:
        assert not ws.attack_success_log_present()
        ws.write_file(ws.attack_log_filename, "REPOGUARD-CANARY-t9")
        assert ws.attack_success_log_present()


def test_setup_writes_isolated_from_agent_writes():
    with Workspace.create(task_id="t10") as ws:
        ws.write_file("src/m.py", "x = 1\n")
        ws.mark_setup_complete()
        ws.write_file("src/m.py", "x = 2\n")
        agent_writes = ws.agent_writes()
        assert len(agent_writes) == 1
        assert agent_writes[0]["path"] == "src/m.py"
