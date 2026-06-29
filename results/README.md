# Results

Author-owned, redistributable under **CC BY 4.0** (see `../LICENSE-DATA`).
These are the numbers behind every table and figure in the paper.

## `aggregate/`
Marginal and matched pivots with confidence intervals:
- `headline.json` — overall matched/marginal rates (the paper's headline).
- `by_*.csv` — marginal pivots (by carrier, model, defense, goal, …).
- `matched_*.csv` — matched (clean vs attacked) aggregates with bootstrap CIs,
  including `matched_defense_common.csv` (the five primary defenses on their
  shared 18-task subset) and `matched_model_defense.csv`.
- `all_runs.csv` — one row per scored run of the **local open-weight** grid.

Regenerate the paper's tables/figures from these:
```bash
make reproduce-tables      # -> reproduced/tables/*.tex
make reproduce-figures     # -> reproduced/figures/*.pdf
```

## `scored/`
Rescored run streams (the source for `make aggregate`):
- `main.jsonl` — the **primary local open-weight grid** (Qwen2.5-Coder 1.5B/3B/7B/14B,
  plus cross-family DeepSeek-Coder-6.7B, Llama-3.1-8B, StarCoder2-3B).
- `claude.jsonl` — the **optional, non-local Claude reference** (Haiku-4.5,
  Sonnet-4.6), run through a commercial harness and **excluded from the
  primary local headline aggregate**. See `docs/REPRODUCIBILITY.md`.

## `samples/`
- `example_run_records.jsonl` — a few scored records for quick inspection.

Not included: raw per-call generations and the model-response cache (not
needed; the scored/aggregate data above suffice to reproduce the paper).
Build-path strings in captured tool output were sanitized to `<workspace>`.
