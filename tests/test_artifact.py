from pathlib import Path

from repoguard.artifact import verify_claims


ROOT = Path(__file__).resolve().parents[1]


def test_bundled_artifact_matches_paper_claims():
    report = verify_claims(ROOT)
    failures = {
        name: check for name, check in report["checks"].items()
        if not check["ok"]
    }
    assert failures == {}
