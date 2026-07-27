# Changelog

All notable changes to RepoGuardBench are documented here. This project
adheres to [Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-07-26

Reproducibility and workflow-hardening release.

### Added
- Executable verification of the camera-ready headline, carrier, scaling,
  defense, closed-model-reference, benchmark-size, and paper-hash claims.
- Paper-to-artifact map and regression tests for release workflows.
- Cross-platform Python selection for the full experiment driver.

### Fixed
- No-GPU smoke and subset scoring now keep audit outputs beside the requested
  scored file instead of overwriting the committed paper audit.

Published benchmark definitions, scored streams, aggregates, and paper numbers
are unchanged.

## [1.0.0] — 2026-06-17

Initial public release: the camera-ready artifact for the DL4C @ ICML 2026
paper *RepoGuardBench: Repository-Borne Prompt Injection Attacks and
Lightweight Defenses for Local Coding Agents*.

### Included
- Local coding-agent harness (strict-JSON ReAct loop) and Ollama backend.
- Sandbox with path containment, command allow/block-list, env scrubbing.
- Five repository-borne attack carriers and five inert attack goals.
- Defenses D0–D5 plus silent variants D3np/D5np.
- Goal-specific scorers, the seven independent run metrics, and matched
  aggregation with Wilson / bootstrap confidence intervals.
- Benchmark definitions: 80 Core (single-source-file) + 14 Applied
  (multi-file) tasks, with datasheet.
- Aggregate results behind every reported table/figure, plus scripts to
  regenerate the paper's tables and figures.
- Deterministic `mock` backend + no-GPU smoke test + GitHub Actions CI.
- Optional, **non-local** Claude reference adapter (excluded from the primary
  local headline aggregate; requires your own commercial access).

### Not included (by design)
- Model weights / Ollama blobs, raw per-call generations, model caches,
  credentials, private logs, or exploit-ready payloads.
