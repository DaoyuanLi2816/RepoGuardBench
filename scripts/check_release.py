"""Deterministic release scanner for RepoGuardBench.

Walks the repository and flags content that must never be published:
secrets/credentials, private keys, local filesystem paths, non-public email
addresses, model weights, reviewer/decision text, oversized files, and
escaping symlinks.  Exits non-zero on any HIGH-severity finding so it can gate
CI and `make check-release`.

Usage: python scripts/check_release.py [ROOT]   (default: repo root)
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ALLOWED_EMAILS = {"li002504@umn.edu"}
ALLOWED_EMAIL_DOMAINS = {"example.com", "example.org", "test.com", "domain.com",
                         "email.com", "noreply.github.com"}

SKIP_DIRS = {".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
             ".mypy_cache", ".ruff_cache", "reproduced", "node_modules"}
SKIP_REL = {"results/smoke", "results/cache", "results/raw"}
# Scanner skips itself so its own pattern strings are not flagged.
SELF = "check_release.py"

WEIGHT_EXT = {".gguf", ".bin", ".safetensors", ".pt", ".pth", ".onnx",
              ".ckpt", ".h5", ".pb"}
BINARY_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".gz", ".ico"}

HIGH_PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("github-pat", re.compile(r"github_pat_[A-Za-z0-9_]{40,}")),
    ("openai-key", re.compile(r"sk-(?:ant-)?[A-Za-z0-9_\-]{20,}")),
    ("aws-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("cred-assignment", re.compile(
        r"(?i)(?:anthropic|openai|aws|hf|hugging|api|access|secret|bearer)[\w-]*"
        r"(?:key|token|secret|password)\s*[:=]\s*['\"][A-Za-z0-9/+_\-]{16,}['\"]")),
    ("win-user-path", re.compile(r"[A-Za-z]:\\Users\\")),
    ("onedrive-path", re.compile(r"OneDrive")),
    ("posix-home", re.compile(r"/home/[a-z][a-z0-9_-]+")),
    ("macos-home", re.compile(r"/Users/[a-z][a-z0-9_-]+")),
]
WARN_PATTERNS = [
    ("reviewer-text", re.compile(
        r"Recommend For Best Paper|Official Review|Reviewer [A-Za-z0-9]{3,}|"
        r"Rating:\s*\d|Confidence:\s*\d")),
]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def iter_files(root: Path):
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        rel_dir = Path(dp).relative_to(root).as_posix()
        if any(rel_dir == s or rel_dir.startswith(s + "/") for s in SKIP_REL):
            continue
        for fn in fns:
            yield Path(dp) / fn


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    high, warn = [], []

    for f in iter_files(root):
        rel = f.relative_to(root).as_posix()
        if f.name == SELF:
            continue
        # symlink check
        if f.is_symlink():
            target = os.path.realpath(f)
            if not str(target).startswith(str(root)):
                high.append((rel, "symlink-escape", str(target)))
            else:
                warn.append((rel, "symlink", str(target)))
            continue
        # size + weight-extension checks
        try:
            size = f.stat().st_size
        except OSError:
            continue
        if f.suffix.lower() in WEIGHT_EXT:
            high.append((rel, "model-weight-file", f"{size} bytes"))
        if size > 10 * 1024 * 1024:
            warn.append((rel, "large-file>10MB", f"{size} bytes"))
        if f.suffix.lower() in BINARY_EXT or f.suffix.lower() in WEIGHT_EXT:
            continue
        # text scan
        try:
            text = f.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        for name, rx in HIGH_PATTERNS:
            if rx.search(text):
                m = rx.search(text)
                high.append((rel, name, m.group(0)[:60]))
        for name, rx in WARN_PATTERNS:
            if rx.search(text):
                warn.append((rel, name, rx.search(text).group(0)[:60]))
        for em in set(EMAIL_RE.findall(text)):
            dom = em.split("@", 1)[1].lower()
            if em.lower() in ALLOWED_EMAILS or dom in ALLOWED_EMAIL_DOMAINS:
                continue
            high.append((rel, "non-public-email", em))

    print(f"[check-release] scanned root: {root}")
    if warn:
        print(f"\n[check-release] {len(warn)} WARNING(s):")
        for rel, kind, ev in warn:
            print(f"  WARN  {kind:20s} {rel}  :: {ev}")
    if high:
        print(f"\n[check-release] {len(high)} HIGH-severity finding(s):")
        for rel, kind, ev in high:
            print(f"  HIGH  {kind:20s} {rel}  :: {ev}")
        print("\n[check-release] FAILED: high-severity content must be removed.")
        return 1
    print("\n[check-release] PASS: no secrets, local paths, non-public emails, "
          "or model weights found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
