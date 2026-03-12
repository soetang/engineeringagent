from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "check_guidance_module_locations.py"
    )


def _write_file(project_root: Path, relative_path: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def _run_checker(
    project_root: Path,
    *,
    checker_path: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(checker_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def test_guidance_module_locations_rule_emits_expected_rule_id(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Emit the stable rule id for guidance module locality."""
    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["rule_id"] == "architecture.guidance-module-locations"


def test_guidance_module_locations_rule_passes_for_target_paths(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when guidance code only exists at the target architecture paths."""
    _write_file(
        tmp_path,
        "src/engineeringagent/adapters/documents/filesystem_guidance_topic_repository.py",
    )
    _write_file(tmp_path, "src/engineeringagent/presentation/cli/guidance.py")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []


def test_guidance_module_locations_rule_fails_for_legacy_paths(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the removed guidance package or CLI module returns."""
    _write_file(
        tmp_path,
        "src/engineeringagent/adapters/documents/filesystem_guidance_topic_repository.py",
    )
    _write_file(tmp_path, "src/engineeringagent/presentation/cli/guidance.py")
    _write_file(
        tmp_path,
        "src/engineeringagent/adapters/documents/packaged_guidance_topic_repository.py",
    )
    _write_file(tmp_path, "src/engineeringagent/approach/registry.py")
    _write_file(
        tmp_path,
        "src/engineeringagent/adapters/guidance/filesystem_guidance_topic_repository.py",
    )
    _write_file(tmp_path, "src/engineeringagent/presentation/cli/approach.py")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        "src/engineeringagent/approach/registry.py: legacy guidance architecture path is not allowed; "
        "keep guidance-topic repositories under engineeringagent.adapters.documents and the CLI "
        "surface under engineeringagent.presentation.cli.guidance; do not restore the "
        "legacy engineeringagent.approach package, packaged-guidance module, "
        "adapters.guidance package, or presentation.cli.approach module.",
        "src/engineeringagent/adapters/guidance/filesystem_guidance_topic_repository.py: legacy guidance architecture path is not allowed; "
        "keep guidance-topic repositories under engineeringagent.adapters.documents and the CLI "
        "surface under engineeringagent.presentation.cli.guidance; do not restore the "
        "legacy engineeringagent.approach package, packaged-guidance module, "
        "adapters.guidance package, or presentation.cli.approach module.",
        "src/engineeringagent/adapters/documents/packaged_guidance_topic_repository.py: legacy guidance architecture path is not allowed; "
        "keep guidance-topic repositories under engineeringagent.adapters.documents and the CLI "
        "surface under engineeringagent.presentation.cli.guidance; do not restore the "
        "legacy engineeringagent.approach package, packaged-guidance module, "
        "adapters.guidance package, or presentation.cli.approach module.",
        "src/engineeringagent/presentation/cli/approach.py: legacy guidance architecture path is not allowed; "
        "keep guidance-topic repositories under engineeringagent.adapters.documents and the CLI "
        "surface under engineeringagent.presentation.cli.guidance; do not restore the "
        "legacy engineeringagent.approach package, packaged-guidance module, "
        "adapters.guidance package, or presentation.cli.approach module.",
    ]
