"""No-GPU smoke test (Level 1).

Exercises the full pipeline -- task materialisation, action parsing, sandbox
execution, defense review, scoring, and aggregation -- end to end with the
deterministic ``mock`` backend.  Requires NO GPU, NO Ollama, and NO commercial
API.  All outputs are written under ``results/smoke/`` so the bundled paper
aggregates in ``results/aggregate/`` are never touched.

Usage:
    python scripts/smoke.py                       # mock backend (default)
    python scripts/smoke.py --model qwen2.5-coder:1.5b   # local Ollama (Level 2)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _py() -> str:
    venv = REPO / ".venv" / "Scripts" / "python.exe"
    return str(venv) if venv.exists() else sys.executable


def _audit_command(py: str, raw: Path, scored: Path,
                   smoke: Path) -> list[str]:
    """Build an audit command whose side outputs stay inside the smoke dir."""
    return [
        py, str(REPO / "scripts" / "audit_scoring.py"),
        "--raw", str(raw),
        "--out", str(scored),
        "--audit", str(smoke / "scoring_audit.csv"),
        "--report", str(smoke / "scoring_audit.md"),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mock",
                    help="backend model; 'mock' (default) needs no GPU/API")
    ap.add_argument("--limit-core", type=int, default=2)
    args = ap.parse_args()
    py = _py()
    t0 = time.time()

    smoke = REPO / "results" / "smoke"
    smoke.mkdir(parents=True, exist_ok=True)
    raw = smoke / "raw.jsonl"
    scored = smoke / "scored.jsonl"
    agg = smoke / "aggregate"
    for p in (raw, scored):
        if p.exists():
            p.unlink()

    core = REPO / "data" / "repoguardbench_core.jsonl"
    if not core.exists():
        subprocess.run([py, str(REPO / "scripts" / "build_benchmark.py"),
                        "--n-core", "10", "--n-real", "5"], check=True)

    # 1) Run a tiny grid (clean + attacked) with the chosen backend.
    subprocess.run([
        py, str(REPO / "scripts" / "run_experiments.py"),
        "--models", args.model,
        "--defenses", "D0_none", "D3_action_gate",
        "--carriers", "code_comment", "rule_file",
        "--tier", "core", "--limit-core", str(args.limit_core),
        "--max-turns", "4",
        "--out", str(raw),
        "--cache-dir", str(smoke / "cache"),
        "--logs", str(smoke / "runner.jsonl"),
    ], check=True)

    # 2) Score (adds the seven independent metrics).
    subprocess.run(_audit_command(py, raw, scored, smoke), check=True)

    # 3) Aggregate (matched + marginal pivots, Wilson/bootstrap CIs).
    subprocess.run([py, str(REPO / "scripts" / "aggregate_results.py"),
                    "--scored", str(scored), "--outdir", str(agg)], check=True)

    # 4) Self-check.
    head = json.loads((agg / "headline.json").read_text(encoding="utf-8"))
    n = int(head.get("n_runs", 0))
    if n <= 0:
        print(f"[smoke] FAILED: aggregate produced n_runs={n}")
        return 1
    elapsed = time.time() - t0
    print(f"[smoke] OK in {elapsed:.0f}s  backend={args.model}  "
          f"n_runs={n}  unique_tasks={head.get('n_unique_tasks')}  "
          f"attempt_rate={head.get('overall_attempt_rate')}")
    print(f"[smoke] outputs under {smoke}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
