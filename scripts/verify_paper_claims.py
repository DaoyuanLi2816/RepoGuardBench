"""Verify the camera-ready paper's claims from the bundled artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from repoguard.artifact import verify_claims  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = verify_claims(args.root)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for name, check in report["checks"].items():
            marker = "PASS" if check["ok"] else "FAIL"
            print(f"[{marker}] {name}: {check['actual']!r}")
        print(f"\n[verify-paper] {'PASS' if report['ok'] else 'FAIL'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
