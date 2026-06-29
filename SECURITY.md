# Security Policy

RepoGuardBench is a **defensive** security-research artifact. All attack
payloads it ships are inert and workspace-local (see
[`docs/SECURITY_AND_ETHICS.md`](docs/SECURITY_AND_ETHICS.md)): they read a
deterministic per-task canary, write a marker file, delete a test, run an
`echo`, or insert a benign comment. There are no real exploits, no network
exfiltration, and no real secrets.

## Reporting a vulnerability or concern

If you find a security issue in the harness/sandbox, or believe any released
content exceeds the inert, workspace-only threat model described in the paper,
please report it **privately** by email:

- **Daoyuan Li** — li002504@umn.edu

Please do **not** open a public issue containing exploit-ready content. Use a
clear subject (e.g., "RepoGuardBench security"), describe the issue, and allow
reasonable time for a fix before any public disclosure.

## Scope

In scope: sandbox/path-containment bypass, command allow/block-list bypass,
environment-scrubbing gaps, or released material that could be weaponized.
Out of scope: the intentionally inert benchmark payloads themselves, and the
optional non-local Claude reference adapter (which requires your own
commercial access and bundles no credentials).
