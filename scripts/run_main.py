"""Drive the paper experiment phases.

All phases share the same JSONL so the aggregator just reads one file.
Each phase is resumable.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


PHASES = [
    {
        "name": "phase1_primary",
        "models": ["qwen2.5-coder:3b"],
        "defenses": ["D0_none", "D1_spotlight", "D2_strip", "D3_action_gate", "D5_human_confirm"],
        "carriers": ["readme", "issue", "code_comment", "rule_file"],
        "tier": "core",
        "limit_core": 18,
        "limit_real": 0,
        "max_turns": 4,
    },
    {
        "name": "phase2_models",
        "models": ["qwen2.5-coder:1.5b", "qwen2.5-coder:7b"],
        "defenses": ["D0_none", "D3_action_gate"],
        "carriers": ["issue", "rule_file"],
        "tier": "core",
        "limit_core": 8,
        "limit_real": 0,
        "max_turns": 4,
    },
    {
        "name": "phase3_real",
        "models": ["qwen2.5-coder:3b"],
        "defenses": ["D0_none", "D3_action_gate"],
        "carriers": ["issue", "rule_file"],
        "tier": "real",
        "limit_core": 0,
        "limit_real": 10,
        "max_turns": 4,
    },
    {
        "name": "phase4_carrier_extra",
        "models": ["qwen2.5-coder:3b"],
        "defenses": ["D0_none"],
        "carriers": ["test_log"],
        "tier": "core",
        "limit_core": 18,
        "limit_real": 0,
        "max_turns": 4,
    },
    {
        "name": "phase5_d4_judge",
        "models": ["qwen2.5-coder:3b"],
        "defenses": ["D4_task_align"],
        "carriers": ["issue", "rule_file", "code_comment"],
        "tier": "core",
        "limit_core": 10,
        "limit_real": 0,
        "max_turns": 3,
    },
    {
        "name": "phase6_test_log_fixed",
        "models": ["qwen2.5-coder:3b"],
        "defenses": ["D0_none", "D1_spotlight", "D3_action_gate"],
        "carriers": ["test_log"],
        "tier": "core",
        "limit_core": 18,
        "limit_real": 0,
        "max_turns": 4,
    },
    {
        "name": "phase7_nonpriming",
        "models": ["qwen2.5-coder:3b", "qwen2.5-coder:7b"],
        "defenses": ["D3np_action_gate_silent", "D5np_confirm_silent"],
        "carriers": ["issue", "code_comment", "rule_file"],
        "tier": "core",
        "limit_core": 12,
        "limit_real": 0,
        "max_turns": 4,
    },
    {
        "name": "phase8_core_expand",
        "models": ["qwen2.5-coder:3b"],
        "defenses": ["D0_none", "D3_action_gate"],
        "carriers": ["issue", "code_comment"],
        "tier": "core",
        "limit_core": 40,
        "limit_real": 0,
        "max_turns": 4,
    },
    {
        "name": "phase9_turns8",
        "models": ["qwen2.5-coder:7b"],
        "defenses": ["D0_none", "D3_action_gate"],
        "carriers": ["issue", "code_comment"],
        "tier": "core",
        "limit_core": 8,
        "limit_real": 0,
        "max_turns": 8,
    },
    # ----- R3 phases ----------------------------------------------------
    {
        "name": "r3_d3np_expand",
        "models": ["qwen2.5-coder:3b", "qwen2.5-coder:7b"],
        "defenses": ["D3_action_gate", "D3np_action_gate_silent",
                      "D5_human_confirm", "D5np_confirm_silent"],
        "carriers": ["code_comment", "rule_file", "issue"],
        "tier": "core",
        "limit_core": 30,
        "limit_real": 0,
        "max_turns": 4,
    },
    {
        "name": "r3_ide_relaxed",
        "models": ["qwen2.5-coder:7b", "qwen2.5-coder:3b"],
        "defenses": ["D0_none", "D3_action_gate", "D3np_action_gate_silent"],
        "carriers": ["code_comment", "rule_file", "issue"],
        "tier": "core",
        "limit_core": 12,
        "limit_real": 0,
        "max_turns": 4,
        "sandbox_mode": "ide_like_marker",
        "run_tag": "ide_relaxed",
    },
    {
        "name": "r3_turns12",
        "models": ["qwen2.5-coder:7b"],
        "defenses": ["D0_none", "D3_action_gate"],
        "carriers": ["code_comment", "issue"],
        "tier": "core",
        "limit_core": 8,
        "limit_real": 0,
        "max_turns": 12,
        "run_tag": "turns12",
    },
    {
        "name": "r3_cross_family",
        "models": ["starcoder2:3b", "deepseek-coder:6.7b-instruct"],
        "defenses": ["D0_none", "D3_action_gate"],
        "carriers": ["code_comment", "rule_file"],
        "tier": "core",
        "limit_core": 12,
        "limit_real": 0,
        "max_turns": 4,
    },
]


def python_executable() -> str:
    """Use an active interpreter on every OS, preferring a local virtualenv."""
    candidates = [
        REPO / ".venv" / "Scripts" / "python.exe",
        REPO / ".venv" / "bin" / "python",
    ]
    return str(next((path for path in candidates if path.exists()),
                    Path(sys.executable)))


def run_phase(p: dict, out_path: Path, logs_path: Path) -> None:
    py = python_executable()
    cmd = [py, str(REPO / "scripts" / "run_experiments.py"),
           "--out", str(out_path),
           "--logs", str(logs_path),
           "--models", *p["models"],
           "--defenses", *p["defenses"],
           "--carriers", *p["carriers"],
           "--tier", p["tier"],
           "--max-turns", str(p["max_turns"])]
    if p.get("limit_core"):
        cmd += ["--limit-core", str(p["limit_core"])]
    if p.get("limit_real"):
        cmd += ["--limit-real", str(p["limit_real"])]
    if p.get("sandbox_mode"):
        cmd += ["--sandbox-mode", p["sandbox_mode"]]
    if p.get("run_tag"):
        cmd += ["--run-tag", p["run_tag"]]
    print(f"[phase {p['name']}] starting", flush=True)
    t0 = time.time()
    res = subprocess.run(cmd, check=False)
    print(f"[phase {p['name']}] done rc={res.returncode} elapsed={time.time() - t0:.0f}s", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "results" / "raw" / "main.jsonl"))
    ap.add_argument("--logs", default=str(REPO / "logs" / "main.jsonl"))
    ap.add_argument("--phases", nargs="+", default=None,
                    help="if set, only run phases with these names")
    args = ap.parse_args()
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    logs = Path(args.logs); logs.parent.mkdir(parents=True, exist_ok=True)
    chosen = args.phases or [p["name"] for p in PHASES]
    for p in PHASES:
        if p["name"] in chosen:
            run_phase(p, out, logs)
    print("[all phases complete]", flush=True)


if __name__ == "__main__":
    main()
