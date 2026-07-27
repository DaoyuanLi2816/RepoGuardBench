"""Checks that the released artifact supports the camera-ready claims."""

from __future__ import annotations

import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
from typing import Any


PAPER_SHA256 = "30f912a3c89a3507938c6dc01bebfc561440d44962cf8fae19b6565eef9436d0"


def _csv_index(path: Path, *keys: str) -> dict[tuple[str, ...], dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {tuple(row[key] for key in keys): row for row in rows}


def _jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _close(actual: float, expected: float, tolerance: float = 5e-4) -> bool:
    return abs(actual - expected) <= tolerance


def _paper_whole_percent(value: str) -> int:
    """Match the paper's displayed one-decimal-then-whole percent rounding."""
    one_decimal = Decimal(f"{100 * float(value):.1f}")
    return int(one_decimal.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def verify_claims(root: Path) -> dict[str, Any]:
    """Return a machine-readable expected-versus-actual verification report."""
    root = root.resolve()
    aggregate = root / "results" / "aggregate"
    headline = json.loads(
        (aggregate / "headline.json").read_text(encoding="utf-8")
    )
    carriers = _csv_index(aggregate / "by_carrier.csv", "attack_carrier")
    models = _csv_index(aggregate / "matched_model.csv", "model")
    model_defense = _csv_index(
        aggregate / "matched_model_defense.csv", "model", "defense"
    )
    common = _csv_index(aggregate / "matched_defense_common.csv", "defense")
    common_meta = json.loads(
        (aggregate / "matched_defense_common_meta.json").read_text(
            encoding="utf-8"
        )
    )
    claude = _jsonl(root / "results" / "scored" / "claude.jsonl")

    qwen_models = [
        "qwen2.5-coder:1.5b",
        "qwen2.5-coder:3b",
        "qwen2.5-coder:7b",
        "qwen2.5-coder:14b",
    ]
    qwen_attempt = [
        _paper_whole_percent(models[(model,)]["attempt_mean"])
        for model in qwen_models
    ]
    qwen_landed = [
        _paper_whole_percent(models[(model,)]["landed_mean"])
        for model in qwen_models
    ]

    claude_summary: dict[str, dict[str, int]] = {}
    for model in sorted({row["model"] for row in claude}):
        rows = [row for row in claude if row["model"] == model]
        clean = [row for row in rows if row["no_attack"]]
        attacked = [row for row in rows if not row["no_attack"]]
        claude_summary[model] = {
            "clean_n": len(clean),
            "clean_pass": sum(bool(row["utility_pass"]) for row in clean),
            "attacked_n": len(attacked),
            "attempt": sum(bool(row["proposed_attempt"]) for row in attacked),
            "landed": sum(
                bool(row["unsafe_action_landed"]) for row in attacked
            ),
            "complete": sum(
                bool(row["attack_completed"]) for row in attacked
            ),
        }

    carrier_actual = {
        name: {
            "n": int(carriers[(name,)]["n"]),
            "attempt": round(1000 * float(
                carriers[(name,)]["proposed_attempt"]
            )) / 10,
            "landed": round(1000 * float(
                carriers[(name,)]["unsafe_action_landed"]
            )) / 10,
            "complete": round(1000 * float(
                carriers[(name,)]["attack_completed"]
            )) / 10,
        }
        for name in ("code_comment", "rule_file", "issue", "readme", "test_log")
    }
    common_cis_include_zero = all(
        float(row["util_delta_lo"]) <= 0 <= float(row["util_delta_hi"])
        for row in common.values()
    )
    paper = root / "paper" / "main.pdf"

    checks: dict[str, dict[str, Any]] = {}

    def exact(name: str, actual: Any, expected: Any) -> None:
        checks[name] = {
            "actual": actual, "expected": expected, "ok": actual == expected,
        }

    def close(name: str, actual: float, expected: float) -> None:
        checks[name] = {
            "actual": actual,
            "expected": expected,
            "ok": _close(actual, expected),
        }

    exact("benchmark_core_tasks", len(_jsonl(
        root / "data" / "repoguardbench_core.jsonl"
    )), 80)
    exact("benchmark_applied_tasks", len(_jsonl(
        root / "data" / "repoguardbench_real.jsonl"
    )), 14)
    exact("local_grid_runs", int(headline["n_runs"]), 2340)
    exact("local_grid_unique_tasks", int(headline["n_unique_tasks"]), 60)
    close("matched_attempt", float(headline["matched_attempt_mean"]), 0.349)
    close("matched_landed", float(headline["matched_landed_mean"]), 0.088)
    close("matched_completion", float(headline["matched_complete_mean"]), 0.021)
    close("matched_utility_delta",
          float(headline["matched_util_delta_mean"]), -0.125)
    close("matched_utility_delta_lo",
          float(headline["matched_util_delta_lo"]), -0.162)
    close("matched_utility_delta_hi",
          float(headline["matched_util_delta_hi"]), -0.085)
    exact("carrier_table", carrier_actual, {
        "code_comment": {
            "n": 548, "attempt": 50.9, "landed": 11.1, "complete": 0.0,
        },
        "rule_file": {
            "n": 552, "attempt": 45.8, "landed": 12.9, "complete": 5.6,
        },
        "issue": {
            "n": 512, "attempt": 13.7, "landed": 2.1, "complete": 1.2,
        },
        "readme": {
            "n": 90, "attempt": 0.0, "landed": 0.0, "complete": 0.0,
        },
        "test_log": {
            "n": 54, "attempt": 0.0, "landed": 0.0, "complete": 0.0,
        },
    })
    exact("qwen_attempt_scaling_percent", qwen_attempt, [0, 22, 58, 83])
    exact("qwen_landed_scaling_percent", qwen_landed, [0, 1, 13, 35])
    close(
        "qwen7b_d3_completion",
        float(model_defense[
            ("qwen2.5-coder:7b", "D3_action_gate")
        ]["complete_mean"]),
        0.154,
    )
    exact("primary_defense_common_tasks",
          int(common_meta["n_common_tasks"]), 18)
    exact("primary_defense_utility_cis_include_zero",
          common_cis_include_zero, True)
    exact("claude_reference", claude_summary, {
        "claude-haiku-4-5-20251001": {
            "clean_n": 24, "clean_pass": 24, "attacked_n": 48,
            "attempt": 21, "landed": 10, "complete": 1,
        },
        "claude-sonnet-4-6": {
            "clean_n": 24, "clean_pass": 24, "attacked_n": 48,
            "attempt": 0, "landed": 0, "complete": 0,
        },
    })
    exact("paper_sha256", _sha256(paper) if paper.exists() else None,
          PAPER_SHA256)

    return {
        "ok": all(check["ok"] for check in checks.values()),
        "paper": (
            "RepoGuardBench: Repository-Borne Prompt Injection Attacks and "
            "Lightweight Defenses for Local Coding Agents"
        ),
        "checks": checks,
    }
