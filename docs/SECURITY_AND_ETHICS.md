# Security and Ethics

RepoGuardBench is a **defensive** research artifact for studying prompt
injection against coding agents. It is built to be *observable* without being
*exploitable*.

## Inert, workspace-local goals
The five attack goals only ever produce a marker inside a per-task **temporary
workspace**:
- `canary_read` — read a per-task `canary_secret.txt` (a deterministic token).
- `canary_exfil` — copy the canary into a marker log **inside the workspace**.
- `test_delete` — delete/trivialize the target test file.
- `unauth_shell` — run a shell command that writes a `pwned.txt` marker.
- `backdoor` — insert a benign comment marker into a patched source file.

## No real harm by construction
- **No network exfiltration.** The sandbox blocks network commands (curl, wget,
  ssh, scp, git push, package installs, cloud CLIs, …) and writes nothing
  outside the workspace.
- **No real secrets.** The "canary" is a synthetic per-task token, not a
  credential. No payload references real SSH keys, cloud config, shell
  profiles, or package-manager credentials.
- **Safe canaries.** Worst case for any inert goal is a marker file in the
  per-task temp directory.
- **Environment scrubbing.** Subprocess environments are stripped of tokens,
  keys, secrets, and proxies before any agent shell command runs.
- **No exploit-ready payloads** are released, and **no model weights** are
  bundled.

## Sandbox limitations
The sandbox is a lightweight research harness, not a production security
boundary. It enforces path containment (no absolute paths, no `..` escapes), a
command allow/block-list, and env scrubbing — but it is **not** a substitute
for OS-level isolation. Run experiments in a throwaway environment. The
strict-vs-IDE-like sandbox modes are an ablation, not a hardening guarantee.

## Responsible use and reporting
Use this benchmark to **build and evaluate defenses**, not to attack systems
you do not own. Do not adapt the inert templates into real exploits.

If you find a way the harness/sandbox can be bypassed, or believe any released
content exceeds this inert, workspace-only model, report it privately per
[`../SECURITY.md`](../SECURITY.md) (email: li002504@umn.edu). Please do not
post exploit-ready content in public issues.
