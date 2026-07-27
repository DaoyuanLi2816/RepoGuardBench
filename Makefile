# RepoGuardBench --- public artifact Makefile
# All default targets are GPU-free and need no network / API / model weights.

PY ?= python
MODEL ?= qwen2.5-coder:1.5b

.PHONY: help setup test smoke smoke-local build-benchmark aggregate \
        reproduce-tables reproduce-figures verify-paper check-release clean

help:
	@echo "Targets:"
	@echo "  setup              install deps + package (editable)"
	@echo "  test               run unit tests (no GPU/network)"
	@echo "  smoke              no-GPU end-to-end smoke (deterministic mock backend)"
	@echo "  smoke-local        smoke with a local Ollama model (MODEL=...)"
	@echo "  reproduce-tables   regenerate paper tables from bundled aggregates"
	@echo "  reproduce-figures  regenerate paper figures from bundled aggregates"
	@echo "  verify-paper       verify paper headline claims from bundled results"
	@echo "  aggregate          rebuild aggregates from results/scored/main.jsonl"
	@echo "  check-release      run the secret/path/PII release scanner"
	@echo "  clean              remove regenerated outputs"

setup:
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -e .

test:
	$(PY) -m pytest -q

# No GPU, no Ollama, no API: uses the deterministic mock backend.
smoke:
	$(PY) scripts/smoke.py

# Level 2: requires a user-installed Ollama model, e.g. MODEL=qwen2.5-coder:1.5b
smoke-local:
	$(PY) scripts/smoke.py --model $(MODEL)

build-benchmark:
	$(PY) scripts/build_benchmark.py --n-core 80 --n-real 14

aggregate:
	$(PY) scripts/aggregate_results.py --scored results/scored/main.jsonl \
	      --outdir results/aggregate

reproduce-tables:
	$(PY) scripts/make_tables.py --agg results/aggregate --out reproduced/tables

reproduce-figures:
	$(PY) scripts/make_figures.py --agg results/aggregate --out reproduced/figures

verify-paper:
	$(PY) scripts/verify_paper_claims.py

check-release:
	$(PY) scripts/check_release.py .

clean:
	rm -rf reproduced results/smoke results/cache .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
