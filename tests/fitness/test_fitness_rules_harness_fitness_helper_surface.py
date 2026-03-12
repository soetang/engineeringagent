from __future__ import annotations

import importlib.util
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
        / "check_harness_fitness_helper_surface.py"
    )


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
    return proc, json.loads(proc.stdout)


def _load_checker_module(repo_root: Path):
    checker_path = _script_path(repo_root)
    spec = importlib.util.spec_from_file_location(
        "engineeringagent_tests.harness_fitness_helper_surface_checker",
        checker_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checker_passes_when_manifest_scripts_use_adapter_owned_helpers(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow manifest-declared harness scripts that use adapter-owned helpers."""
    harness_root = tmp_path / "harness" / "fitness_functions"
    harness_root.mkdir(parents=True)
    (harness_root / "rules.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "rules:",
                "  - rule_id: architecture.tmp",
                "    command:",
                "      - uv",
                "      - run",
                "      - python",
                "      - harness/fitness_functions/check_ok.py",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (harness_root / "check_ok.py").write_text(
        "\n".join(
            [
                "from engineeringagent.adapters.quality.fitness import emit_fitness_result",
                "",
                "def run() -> None:",
                "    _ = emit_fitness_result",
                "",
            ]
        ),
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []


def test_checker_flags_legacy_checks_facade_and_local_helper_imports(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject restored legacy checks facade imports and local envelope helpers."""
    harness_root = tmp_path / "harness" / "fitness_functions"
    harness_root.mkdir(parents=True)
    (harness_root / "rules.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "rules:",
                "  - rule_id: architecture.tmp",
                "    command:",
                "      - uv",
                "      - run",
                "      - python",
                "      - harness/fitness_functions/check_bad.py",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (harness_root / "result_envelope.py").write_text("", encoding="utf-8")
    (harness_root / "check_bad.py").write_text(
        "\n".join(
            [
                "from engineeringagent.checks import emit_fitness_result",
                "from result_envelope import emit_result_envelope",
                "",
                "def run() -> None:",
                "    _ = emit_fitness_result",
                "    _ = emit_result_envelope",
                "",
            ]
        ),
        encoding="utf-8",
    )

    checker = _load_checker_module(repo_root)
    violations = checker._collect_violations(tmp_path)

    assert violations == [
        "harness/fitness_functions/check_bad.py:1 imports from legacy helper module engineeringagent.checks; harness fitness rules must use engineeringagent.adapters.quality.fitness.emit_fitness_result and adapter-owned helpers instead of the legacy engineeringagent.checks facade or local result_envelope helpers",
        "harness/fitness_functions/check_bad.py:2 imports legacy helper module result_envelope.emit_result_envelope; harness fitness rules must use engineeringagent.adapters.quality.fitness.emit_fitness_result and adapter-owned helpers instead of the legacy engineeringagent.checks facade or local result_envelope helpers",
        "harness/fitness_functions/result_envelope.py: legacy local result envelope helper must remain absent; harness fitness rules must use engineeringagent.adapters.quality.fitness.emit_fitness_result and adapter-owned helpers instead of the legacy engineeringagent.checks facade or local result_envelope helpers",
    ]
