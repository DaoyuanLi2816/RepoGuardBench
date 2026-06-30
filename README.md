# RepoGuardBench

**A benchmark for repository-borne prompt injection against local coding agents — does an open-weight coder stay on its bug-fix task when the repository is poisoned?**

[![CI](https://github.com/DaoyuanLi2816/RepoGuardBench/actions/workflows/ci.yml/badge.svg)](https://github.com/DaoyuanLi2816/RepoGuardBench/actions/workflows/ci.yml)
[![Paper (OpenReview)](https://img.shields.io/badge/paper-OpenReview-blue)](https://openreview.net/forum?id=58AGMTgU3L)
[![License: MIT](https://img.shields.io/badge/code-MIT-green.svg)](LICENSE)
[![Data: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-green.svg)](LICENSE-DATA)

RepoGuardBench jointly measures **bug-fix utility** and **prompt-injection
robustness** for **local open-weight** coding agents. An attacker plants
instructions in a repository artifact (README, issue, code comment, test log,
or agent-rule file); a local coding agent reads that content while trying to
fix a real bug; the harness scores whether the agent stays on task. It runs
fully locally on a single consumer GPU — **no data leaves your machine** —
and ships a deterministic, GPU-free smoke test so you can verify the whole
pipeline in seconds.

- **Paper:** *RepoGuardBench: Repository-Borne Prompt Injection Attacks and Lightweight Defenses for Local Coding Agents* — Daoyuan Li (University of Minnesota Twin Cities). Accepted at the **5th Deep Learning for Code (DL4C) Workshop at ICML 2026** (non-archival).
- **OpenReview:** https://openreview.net/forum?id=58AGMTgU3L
- **Try it now (no GPU, no API):** `make setup && make smoke`

## Key findings

| Finding | Evidence (from the paper's matched analysis) |
|---|---|
| **Code comments and agent-rule files are the highest-risk carriers** | Marginal proposed-attempt by carrier: code comment **50.9%** > rule file **45.8%** > issue **13.7%** ≫ README / test log **0%**. |
| **Susceptibility scales with model capability** | Matched proposed-attempt across Qwen2.5-Coder: **0%** (1.5B) → **22%** (3B) → **58%** (7B) → **83%** (14B); landed unsafe actions rise in step. |
| **Strict-sandbox attack completion is low but nonzero** | **2.1%** matched completion, dominated by one pattern: rule-file → test deletion. |
| **Path-based action gates miss *semantic* test deletion** | The D3 path-prefix gate allows `tests/` writes (legitimate in repair), so rule-file → `TEST_DELETE` completes **15.4%** on Qwen2.5-Coder-7B under D3. |

Defenses (context-side D1/D2, action-side D3/D5) fail in different ways; among
the five primary defenses (D0–D3, D5) on their shared 18-task subset, all
matched utility-delta confidence intervals include zero — no statistically
clear utility winner. A non-local **Claude** reference is far more capable and
more robust on these carriers, indicating commercial alignment/harnessing can
break the open-model capability–risk trend (reported separately; see scope).

## Architecture

```
attacker writes a carrier  ─►  local coding agent (strict-JSON ReAct loop)
                                  │  reads poisoned repo context
   optional defense (D0–D5) ◄─────┤  proposes one JSON action / turn
                                  ▼
            sandbox: path containment + command allow/block-list + env scrub
                                  ▼
            per-task workspace + scorer  ─►  7 independent metrics
                                  ▼
            matched aggregation (Wilson / bootstrap CIs)  ─►  tables & figures
```

All arrows run locally on one GPU. The optional Claude reference is a separate,
non-local path (see [Local vs non-local scope](#local-vs-non-local-scope)).

## Repository layout

```
repoguard/      core library: agents/ attacks/ benchmark/ defenses/ sandbox/ scoring/ utils/
scripts/        build / run / score / aggregate / make_tables / make_figures / smoke / check_release
configs/        experiment grid + model configs
tests/          unit tests (sandbox, scorers, parsing, aggregation)
data/           benchmark task definitions (Core + Applied) + datasheet + samples
results/        aggregate CSV/JSON behind the paper + sanitized scored streams + samples
docs/           QUICKSTART, REPRODUCIBILITY, BENCHMARK, THREAT_MODEL, SECURITY_AND_ETHICS, RESULTS
paper/          final camera-ready PDF + citation
```

## Quick start

```bash
make setup        # install deps + the repoguard package (editable)
make test         # unit tests (no GPU, no network)
make smoke        # full pipeline end-to-end with a deterministic MOCK backend
```

`make smoke` requires **no GPU, no Ollama, and no commercial API**: it
materializes tasks, parses actions, runs the sandbox, scores, and aggregates
using a built-in deterministic mock model, in seconds.

### Local-GPU smoke (Level 2)
With a user-installed [Ollama](https://ollama.com) model:
```bash
ollama pull qwen2.5-coder:1.5b
make smoke-local MODEL=qwen2.5-coder:1.5b
```

### Reproduce the paper's tables and figures (from bundled aggregates)
```bash
make reproduce-tables     # -> reproduced/tables/*.tex
make reproduce-figures    # -> reproduced/figures/*.pdf
```

### Reproduce a limited experiment subset (local GPU)
```bash
python scripts/run_experiments.py --models qwen2.5-coder:3b \
    --defenses D0_none D3_action_gate --carriers code_comment rule_file \
    --tier core --limit-core 12 --out results/raw/subset.jsonl
python scripts/audit_scoring.py --raw results/raw/subset.jsonl --out results/scored/subset.jsonl
python scripts/aggregate_results.py --scored results/scored/subset.jsonl --outdir results/aggregate_subset
```

### Full reproduction
Paper-scale replication runs a balanced fractional grid (four Qwen2.5-Coder
sizes × eight defenses × five carriers + cross-family pilots) on a single
**RTX 4080-class (16 GB) GPU**. It is time-consuming (hours) and requires
locally pulled Ollama models. See [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md).

## Local vs non-local scope

- **Primary experiments are local-only and single-GPU.** Qwen2.5-Coder
  (1.5B/3B/7B/14B) and cross-family open models (StarCoder2-3B,
  DeepSeek-Coder-6.7B, Llama-3.1-8B) run via Ollama; no remote API is called.
- The **Claude reference is optional and non-local.** It runs through a
  commercial coding-agent harness, is **excluded from the primary local
  headline aggregate**, requires *your own* commercial access, and bundles
  **no credentials**. It is reported only to contextualize the open-model
  results.

## Benchmark & data

80 **Core** synthetic tasks (single-source-file fixes, 10 archetypes) and 14
hand-curated **Applied** multi-file tasks, five carriers, five inert goals.
Tasks are verified fail-before / pass-after. See [`data/README.md`](data/README.md)
and [`docs/BENCHMARK.md`](docs/BENCHMARK.md). Licensed CC BY 4.0.

## Safety & responsible use

Every payload is **inert and workspace-local**: read a deterministic canary,
write a marker file, delete a test, run `echo`, or insert a benign comment.
No real exploits, no network exfiltration, no real secrets, no model weights.
See [`docs/SECURITY_AND_ETHICS.md`](docs/SECURITY_AND_ETHICS.md) and
[`SECURITY.md`](SECURITY.md). This is a defensive research artifact.

## Testing & CI

GitHub Actions runs unit tests, the no-GPU mock smoke, table regeneration from
bundled aggregates, and a secret/path/PII release scan (`make check-release`)
across Python 3.10–3.12 — with no model weights and no secrets.

## Citation

See [`CITATION.cff`](CITATION.cff) / [`paper/citation.bib`](paper/citation.bib):

```bibtex
@misc{li2026repoguardbench,
  title  = {RepoGuardBench: Repository-Borne Prompt Injection Attacks and
            Lightweight Defenses for Local Coding Agents},
  author = {Li, Daoyuan},
  year   = {2026},
  note   = {Accepted at the 5th Deep Learning for Code (DL4C) Workshop at ICML 2026}
}
```
DL4C is non-archival — please cite as a workshop presentation, **not** as a
PMLR / ICML main-conference proceedings entry.

## Licenses

- **Code** (`repoguard/`, `scripts/`, `tests/`, configs): MIT — [`LICENSE`](LICENSE).
- **Data & results** (`data/`, `results/`): CC BY 4.0 — [`LICENSE-DATA`](LICENSE-DATA).

## Known limitations

The Applied tier is small (14 tasks) and Core tasks are single-file "easy"
fixes (controlled probe, not ecological difficulty). Payloads are inert and
non-adaptive. Primary evidence is the Qwen2.5-Coder family with smaller
cross-family pilots; the Claude reference is a single non-local point through
a different harness. Defenses are lightweight baselines, not state-of-the-art.
See the paper's Limitations section.
