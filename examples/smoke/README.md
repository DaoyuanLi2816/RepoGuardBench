# Smoke example (no GPU)

The fastest way to confirm the whole pipeline works end-to-end with **no GPU,
no Ollama, and no API**:

```bash
make smoke
# equivalently:
python scripts/smoke.py
```

What it does (deterministic `mock` backend):
1. Materializes a couple of Core tasks (clean + attacked, D0 and D3, two carriers).
2. Drives the strict-JSON ReAct loop; the mock emits a fixed, schema-valid
   action sequence (write a benign note → run tests → finish).
3. Executes actions through the sandbox, applies defenses, and scores.
4. Aggregates (`audit_scoring` → `aggregate_results`).
5. Self-checks the aggregate and prints a one-line summary.

All outputs go under `results/smoke/` and never touch the bundled paper
aggregates in `results/aggregate/`. Because the mock is not a model, smoke runs
report zero attempts/completions — they verify the **harness works**, not that
any bug is fixed or attack succeeds.

For a real (local) model, see Level 2 in
[`../../docs/REPRODUCIBILITY.md`](../../docs/REPRODUCIBILITY.md):
```bash
make smoke-local MODEL=qwen2.5-coder:1.5b
```
