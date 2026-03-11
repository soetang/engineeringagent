from __future__ import annotations

from pathlib import Path


_HARNESS_COMMAND_SCRIPT_NAMES = (
    "validate_yaml.py",
    "permission_probe.py",
    "validate_commit_messages.py",
)

_LEGACY_HARNESS_ROOT_SCRIPT_COMMANDS = (
    "uv run python harness/validate_yaml.py",
    "uv run python harness/permission_probe.py",
    "uv run python harness/validate_commit_messages.py",
)


def _collect_stale_legacy_script_command_references(
    archived_specs_root: Path, repo_root: Path
) -> list[str]:
    stale_references: list[str] = []
    for spec_path in sorted(archived_specs_root.rglob("*.yaml")):
        contents = spec_path.read_text(encoding="utf-8")
        for legacy_command in _LEGACY_HARNESS_ROOT_SCRIPT_COMMANDS:
            if legacy_command in contents:
                stale_references.append(
                    f"{spec_path.relative_to(repo_root)}::{legacy_command}"
                )
    return stale_references


def test_harness_command_scripts_live_under_fitness_functions(repo_root: Path) -> None:
    harness_root = repo_root / "harness"
    fitness_functions_root = harness_root / "fitness_functions"
    assert not (harness_root / "fitness-functions").exists()

    for script_name in _HARNESS_COMMAND_SCRIPT_NAMES:
        assert not (harness_root / script_name).exists()
        assert (fitness_functions_root / script_name).is_file()


def test_docs_specs_do_not_reference_legacy_harness_root_script_commands(
    repo_root: Path,
) -> None:
    archived_specs_root = repo_root / "docs" / "spec" / "features_done"

    stale_references = _collect_stale_legacy_script_command_references(
        archived_specs_root, repo_root
    )
    assert not stale_references, "\n".join(stale_references)
