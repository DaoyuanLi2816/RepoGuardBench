"""Benchmark task model and materialization onto a Workspace."""
from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..sandbox.workspace import Workspace
from ..utils.io import read_jsonl, write_jsonl


@dataclass
class Task:
    task_id: str
    tier: str               # "core" or "real"
    title: str
    issue_text: str
    files: Dict[str, str]   # repo-relative path -> file contents
    target_test_node: str   # e.g. "tests/test_x.py::test_y"
    expected_patch_hint: str = ""
    target_py: str = ""     # the buggy source file (for code-comment injection)
    tags: List[str] = field(default_factory=list)
    difficulty: str = "easy"
    description: str = ""

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Task":
        return Task(
            task_id=d["task_id"], tier=d["tier"], title=d["title"],
            issue_text=d["issue_text"], files=d["files"],
            target_test_node=d["target_test_node"],
            expected_patch_hint=d.get("expected_patch_hint", ""),
            target_py=d.get("target_py", ""), tags=list(d.get("tags", [])),
            difficulty=d.get("difficulty", "easy"),
            description=d.get("description", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def load_tasks(path: str | Path) -> List[Task]:
    return [Task.from_dict(row) for row in read_jsonl(path)]


def save_tasks(path: str | Path, tasks: List[Task]) -> int:
    return write_jsonl(path, [t.to_dict() for t in tasks])


def materialize_task(task: Task,
                     workspace: Workspace,
                     extra_files: Optional[Dict[str, str]] = None,
                     plant_canary: bool = True) -> None:
    """Write all of `task.files` (plus optional overrides) into `workspace`."""
    files = dict(task.files)
    if extra_files:
        files.update(extra_files)
    # Always include conftest disabling cache writes to home and capturing stdout.
    if "conftest.py" not in files:
        files["conftest.py"] = textwrap.dedent("""
            import sys, os, pathlib
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            sys.path.insert(0, str(pathlib.Path(__file__).parent / 'src'))
        """).lstrip()
    if "pytest.ini" not in files:
        files["pytest.ini"] = "[pytest]\naddopts = -p no:cacheprovider\n"
    for rel, content in files.items():
        workspace.write_file(rel, content)
    if plant_canary:
        workspace.plant_canary()
