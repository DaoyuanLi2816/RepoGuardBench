# Benchmark data

Author-owned, redistributable under **CC BY 4.0** (see `../LICENSE-DATA`).

| File | Description |
|---|---|
| `repoguardbench_core.jsonl` | **Core** tier: 80 synthetic Python micro-repositories with a single-source-file bug fix, generated from 10 archetypes across many module names. Each task ships a README, LICENSE, `pyproject`, source layout, and a target failing test. |
| `repoguardbench_real.jsonl` | **Applied** tier: 14 hand-curated multi-file repair tasks inspired by issue patterns in popular pure-Python libraries. |
| `benchmark_datasheet.md` | Datasheet (motivation, composition, construction, known biases, limitations). |
| `exclusion_log.csv` | Tasks removed by the fail-before / pass-after verification. |
| `samples/example_core_task.json` | One pretty-printed Core task for quick inspection. |

Each task record contains the clean repository `files`, the `issue_text`, the
`target_test_node`, the buggy `target_py`, and an `expected_patch_hint`.
Attacks are **not** baked into these files: a carrier+goal is injected at
runtime by `repoguard/attacks/carriers.py`. The embedded `canary` is a
deterministic per-task token, not a real secret.

Both tiers are verified twice during construction: the target test must fail
on the shipped code, and a hand-written reference patch must make it pass.

> The `Applied` tasks are **hand-curated**, not scraped from real GitHub
> issues; do not use them to claim ecological validity for real repositories.
