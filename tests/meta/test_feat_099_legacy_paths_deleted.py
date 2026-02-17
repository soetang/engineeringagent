from __future__ import annotations

from pathlib import Path


def test_legacy_harness_checks_runtime_module_path_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    legacy_path = repo_root / "src" / "engineeringagent" / "harness_checks_runtime.py"

    assert not legacy_path.exists(), (
        "expected legacy checks runtime module to be deleted: "
        f"{legacy_path.relative_to(repo_root).as_posix()}"
    )


def test_legacy_validator_module_path_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    legacy_path = repo_root / "src" / "engineeringagent" / "validator.py"

    assert not legacy_path.exists(), (
        "expected legacy validator module to be deleted: "
        f"{legacy_path.relative_to(repo_root).as_posix()}"
    )
