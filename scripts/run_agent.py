"""Run the RepoGuardBench agent on a single task, without scoring across the grid.

Useful for debugging or for ad-hoc experiments outside the main grid.

Example::

  python scripts/run_agent.py \\
      --task-id core-000-packy \\
      --model qwen2.5-coder:3b \\
      --carrier issue \\
      --defense D0_none
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from repoguard.agents.agent_loop import run_agent
from repoguard.agents.ollama_backend import OllamaBackend
from repoguard.attacks.carriers import inject_attack
from repoguard.benchmark.task import load_tasks, materialize_task, Task
from repoguard.defenses.registry import make_defense
from repoguard.sandbox.workspace import Workspace
from repoguard.scoring.scorer import score_run
from scripts.run_experiments import _build_repo_context, _user_task_text, DEFAULT_CARRIER_GOAL


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", default=str(REPO / "data" / "repoguardbench_core.jsonl"))
    ap.add_argument("--real", default=str(REPO / "data" / "repoguardbench_real.jsonl"))
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--model", default="qwen2.5-coder:3b")
    ap.add_argument("--carrier", default=None,
                    help="one of readme, issue, code_comment, test_log, rule_file; omit for no attack")
    ap.add_argument("--goal", default=None)
    ap.add_argument("--defense", default="D0_none")
    ap.add_argument("--max-turns", type=int, default=4)
    args = ap.parse_args()

    tasks = {t.task_id: t for t in load_tasks(args.core)}
    tasks.update({t.task_id: t for t in load_tasks(args.real)})
    if args.task_id not in tasks:
        print(f"unknown task {args.task_id}", file=sys.stderr); return 2
    task: Task = tasks[args.task_id]
    issue_text = task.issue_text
    files = dict(task.files)
    if args.carrier:
        goal = args.goal or DEFAULT_CARRIER_GOAL[args.carrier]
        files, issue_text, _ = inject_attack(carrier=args.carrier, goal=goal,
                                              repo_files=files, issue_text=issue_text,
                                              target_py=task.target_py)
    backend = OllamaBackend(model=args.model)
    defense = make_defense(args.defense, backend=backend if args.defense == "D4_task_align" else None)
    context = _build_repo_context(task, issue_text)
    with Workspace.create(task_id=task.task_id) as ws:
        materialize_task(Task(**{**task.to_dict(), "files": files}), ws)
        ws.mark_setup_complete()
        t0 = time.time()
        ar = run_agent(backend=backend, workspace=ws,
                        user_task=_user_task_text(task),
                        repo_context=context, defense=defense,
                        max_turns=args.max_turns,
                        target_test_node=task.target_test_node)
        wall = time.time() - t0
        rec = score_run(task_id=task.task_id, tier=task.tier, model=args.model,
                         inference_backend="ollama",
                         attack_carrier=(args.carrier or "none"),
                         attack_goal=(args.goal or DEFAULT_CARRIER_GOAL.get(args.carrier, "none")
                                       if args.carrier else "none"),
                         defense=args.defense, seed=7,
                         no_attack=(args.carrier is None),
                         agent_result=ar, workspace=ws,
                         target_test_node=task.target_test_node,
                         wall_clock_s=wall)
        print(json.dumps({
            "task_id": rec.task_id, "model": rec.model, "defense": rec.defense,
            "carrier": rec.attack_carrier, "goal": rec.attack_goal,
            "utility_pass": rec.utility_pass,
            "attack_attempted": rec.attack_attempted,
            "attack_completed": rec.attack_completed,
            "turns_used": rec.turns_used,
            "wall_clock_s": rec.wall_clock_s,
        }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
