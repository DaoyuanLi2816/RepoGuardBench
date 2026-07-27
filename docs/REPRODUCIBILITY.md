# Reproducibility

Three levels, from instant to paper-scale.

## Level 1 — No-GPU smoke (seconds, no dependencies beyond Python)
```bash
make smoke
make verify-paper
```
Uses the deterministic `mock` backend. Verifies the full pipeline:
task construction/materialization, strict-JSON action parsing (incl. the
fallback parser), sandbox path-containment and command policy, defense review,
goal scoring, and matched aggregation. Also runs in CI on every push.
No GPU, no Ollama, no commercial API, no large download.
`verify-paper` separately checks that the bundled task definitions, scored
streams, aggregate CSV/JSON, and final PDF support the camera-ready claims.

## Level 2 — Local-model pilot (minutes, single GPU)
A small number of tasks with a user-installed Ollama model:
```bash
ollama pull qwen2.5-coder:1.5b           # or 3b / 7b / 14b
make smoke-local MODEL=qwen2.5-coder:1.5b
# or a targeted subset:
python scripts/run_experiments.py --models qwen2.5-coder:3b \
    --defenses D0_none D3_action_gate --carriers code_comment rule_file \
    --tier core --limit-core 12 --out results/raw/subset.jsonl
python scripts/audit_scoring.py --raw results/raw/subset.jsonl --out results/scored/subset.jsonl
python scripts/aggregate_results.py --scored results/scored/subset.jsonl --outdir results/aggregate_subset
```

`audit_scoring.py` places its audit CSV and Markdown report next to `--out` by
default, so a subset or smoke run cannot overwrite the committed paper audit.

## Level 3 — Paper-scale reproduction (hours, single GPU)
- **Hardware:** a single **RTX 4080-class GPU (16 GB VRAM)** is sufficient;
  the paper's grid was produced on one such GPU.
- **Models:** Qwen2.5-Coder 1.5B/3B/7B/14B (Q4_K_M) via Ollama, plus
  cross-family StarCoder2-3B, DeepSeek-Coder-6.7B-Instruct, Llama-3.1-8B.
  Disk: the 14B model alone is ~9 GB; budget tens of GB total.
- **Runtime:** the balanced fractional grid takes **on the order of hours**
  (most of it is local LLM inference). It is resumable: re-running skips cells
  already present in the output JSONL (deterministic cell key).
- **Driver:** `scripts/run_main.py` defines the experiment phases; results are
  scored (`audit_scoring.py`) and aggregated (`aggregate_results.py`), then
  tables/figures are regenerated (`make reproduce-tables`, `make reproduce-figures`).

The bundled `results/aggregate/` and `results/scored/main.jsonl` already
contain the reported numbers, so tables/figures reproduce **without** rerunning
any model.

See [PAPER_TO_ARTIFACT.md](PAPER_TO_ARTIFACT.md) for the exact file and command
behind each paper table, figure, and headline.

## Determinism
Local runs use temperature 0.0, fixed seed 7, `num_ctx` 8192. Aggregation uses
a fixed bootstrap seed. Exact landed/completion counts can vary slightly with
the Ollama build/quantization; aggregate trends are stable.

## Local vs non-local scope (important)
- The **primary experiments are local and reproducible** on a single
  RTX 4080-class GPU, with **no remote API**.
- Full replication is **time-consuming**.
- The **Claude reference is optional, non-local, and excluded from the primary
  headline aggregate**. Reproducing it needs your **own** commercial access /
  CLI; the adapter (`repoguard/agents/claude_cli_backend.py`) bundles **no
  credentials**. Its scored stream (`results/scored/claude.jsonl`) is provided
  for transparency.
- **No credentials are bundled** anywhere in this repository.
