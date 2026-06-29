# Contributing

Thanks for your interest in RepoGuardBench. This repository accompanies a
workshop paper; contributions that improve reproducibility, add benchmark
tasks/defenses, or fix bugs are welcome.

## Ground rules

1. **Keep payloads inert.** New attack carriers/goals must stay
   workspace-local and non-exploitable, consistent with
   [`docs/SECURITY_AND_ETHICS.md`](docs/SECURITY_AND_ETHICS.md). No real
   secrets, network exfiltration, or destructive commands.
2. **No credentials or private data** in code, configs, tests, or results.
   Run `make check-release` before opening a PR.
3. **Local-first.** The default test/smoke path must run with **no GPU, no
   Ollama, and no commercial API** (use the `mock` backend).

## Dev workflow

```bash
make setup        # install deps + package (editable)
make test         # unit tests
make smoke        # no-GPU end-to-end smoke (mock backend)
make check-release
```

## Pull requests

- Keep changes focused; add/adjust unit tests for new behavior.
- Do not change committed numerical results unless you are correcting a
  documented bug; explain any change in the PR description.
- CI (GitHub Actions) must pass: unit tests, mock smoke, table regeneration,
  and the release scan.

## Reporting security issues

See [`SECURITY.md`](SECURITY.md) — report privately, do not post exploit-ready
content publicly.
