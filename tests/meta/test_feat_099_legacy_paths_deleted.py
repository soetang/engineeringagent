from __future__ import annotations

from pathlib import Path


def test_legacy_harness_checks_runtime_module_path_deleted() -> None:
    """Legacy checks runtime shim stays deleted."""
    repo_root = Path(__file__).resolve().parents[2]
    legacy_path = repo_root / "src" / "engineeringagent" / "harness_checks_runtime.py"

    assert not legacy_path.exists(), (
        "expected legacy checks runtime module to be deleted: "
        f"{legacy_path.relative_to(repo_root).as_posix()}"
    )


def test_legacy_validator_module_path_deleted() -> None:
    """Legacy validator shim stays deleted."""
    repo_root = Path(__file__).resolve().parents[2]
    legacy_path = repo_root / "src" / "engineeringagent" / "validator.py"

    assert not legacy_path.exists(), (
        "expected legacy validator module to be deleted: "
        f"{legacy_path.relative_to(repo_root).as_posix()}"
    )


def test_legacy_port_module_paths_deleted() -> None:
    """Legacy pluralized port modules stay deleted."""
    repo_root = Path(__file__).resolve().parents[2]
    legacy_paths = (
        repo_root / "src" / "engineeringagent" / "ports" / "guidance_topics.py",
        repo_root / "src" / "engineeringagent" / "ports" / "prompt_definitions.py",
    )

    existing = [
        path.relative_to(repo_root).as_posix() for path in legacy_paths if path.exists()
    ]
    assert existing == [], (
        "expected legacy port modules to be deleted:\n" + "\n".join(existing)
    )


def test_legacy_repository_adapter_module_paths_deleted() -> None:
    """Legacy repository adapter module paths stay deleted."""
    repo_root = Path(__file__).resolve().parents[2]
    legacy_paths = (
        repo_root
        / "src"
        / "engineeringagent"
        / "adapters"
        / "guidance"
        / "packaged_guidance_topics.py",
        repo_root
        / "src"
        / "engineeringagent"
        / "adapters"
        / "prompts"
        / "bundled_prompt_definitions.py",
        repo_root
        / "src"
        / "engineeringagent"
        / "adapters"
        / "prompts"
        / "filesystem_prompt_definitions.py",
        repo_root
        / "src"
        / "engineeringagent"
        / "adapters"
        / "prompts"
        / "project_prompt_definitions.py",
    )

    existing = [
        path.relative_to(repo_root).as_posix() for path in legacy_paths if path.exists()
    ]
    assert existing == [], (
        "expected legacy repository adapter modules to be deleted:\n"
        + "\n".join(existing)
    )
