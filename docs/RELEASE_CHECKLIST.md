# Release Checklist (sanitized summary)

This repository is a **curated fresh export** — not the private development
tree or its git history. A deterministic scanner
(`scripts/check_release.py`, also run in CI and via `make check-release`)
verifies the release before publication.

## Security scan result
`make check-release` → **PASS**: no secrets/credentials, no API keys/tokens,
no private keys, no `.env`, no local filesystem paths (Windows user
directories, personal cloud-sync folders, or POSIX/macOS home directories),
no non-public email addresses (only the public contact `li002504@umn.edu`),
no model weights/caches, and no
oversized/binary debris. Symlinks: none.

## Included
- Source code (`repoguard/`, curated `scripts/`, `tests/`, `configs/`).
- Benchmark definitions (Core + Applied) + datasheet (CC BY 4.0).
- Aggregate results + sanitized scored streams behind the paper (CC BY 4.0).
- Deterministic mock backend, no-GPU smoke, CI, and the release scanner.
- Final camera-ready paper PDF + citation.
- Optional, **non-local** Claude reference adapter (no credentials) +
  documentation that it is excluded from the primary local aggregate.

## Excluded (by design)
- Private git history; `.venv`, caches, `__pycache__`, `.pytest_cache`.
- Raw per-call generations, the model-response cache, smoke scratch outputs.
- Model weights / Ollama blobs.
- Internal logs, progress notes, decision/triage docs, and any
  reviewer/self-review material; the OpenReview page dump.
- Old/anonymized PDFs, LaTeX build artifacts, stale packages/backups.
- Third-party template files (ICML style) whose redistribution is not ours to
  grant — obtain them from the official source.
- Exploit-ready payloads (none exist; all benchmark goals are inert and
  workspace-local — see [SECURITY_AND_ETHICS.md](SECURITY_AND_ETHICS.md)).

If a file's redistribution status was uncertain, it was excluded.
