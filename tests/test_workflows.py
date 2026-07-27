from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_audit_outputs_are_isolated(tmp_path):
    smoke = _load_script("smoke.py")
    command = smoke._audit_command(
        sys.executable, tmp_path / "raw.jsonl",
        tmp_path / "scored.jsonl", tmp_path,
    )
    audit = Path(command[command.index("--audit") + 1])
    report = Path(command[command.index("--report") + 1])
    assert audit.parent == tmp_path
    assert report.parent == tmp_path


def test_main_driver_uses_an_existing_python():
    run_main = _load_script("run_main.py")
    assert Path(run_main.python_executable()).exists()
