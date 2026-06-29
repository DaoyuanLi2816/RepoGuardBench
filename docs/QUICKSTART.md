# Quickstart

## Requirements
- Python 3.10–3.12. No GPU, Ollama, or API key is needed for the default path.

## Install
```bash
git clone https://github.com/DaoyuanLi2816/RepoGuardBench.git
cd RepoGuardBench
make setup            # or: pip install -r requirements.txt && pip install -e .
```

## Verify (no GPU)
```bash
make test             # unit tests
make smoke            # deterministic mock backend: full pipeline in seconds
```
Expected: tests pass; smoke prints `[smoke] OK ... backend=mock n_runs=12 ...`
and writes outputs under `results/smoke/` (the bundled paper aggregates in
`results/aggregate/` are never touched).

## Reproduce paper tables/figures (from bundled aggregates)
```bash
make reproduce-tables     # -> reproduced/tables/*.tex
make reproduce-figures    # -> reproduced/figures/*.pdf
```

## Run with a local model (optional, needs Ollama + GPU)
```bash
ollama pull qwen2.5-coder:1.5b
make smoke-local MODEL=qwen2.5-coder:1.5b
```

See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for the three reproduction levels
and full-scale requirements.
