from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import cast

import yaml


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "check_iteration_pipeline_observer_decoupling.py"
    )


def _write_iteration_module(project_root: Path, body: str) -> None:
    path = (
        project_root
        / "src/engineeringagent/application/feature_iteration_pipeline.py"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


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


def _violations(result: dict[str, object]) -> list[str]:
    return cast(list[str], result["violations"])


def test_iteration_pipeline_observer_decoupling_rule_configuration() -> None:
    """Verify the observer-decoupling rule is registered in the manifest."""
    manifest_path = Path("harness/fitness_functions/rules.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    rules = manifest["rules"]
    configured = [
        rule
        for rule in rules
        if isinstance(rule, dict)
        and rule.get("rule_id") == "architecture.iteration-pipeline-observer-decoupling"
    ]

    assert len(configured) == 1
    rule = configured[0]
    assert rule["adapter"] == "command"
    assert rule["severity"] == "error"
    assert rule["command"] == [
        "uv",
        "run",
        "python",
        "harness/fitness_functions/rules/check_iteration_pipeline_observer_decoupling.py",
    ]


def test_iteration_pipeline_observer_decoupling_rule_passes_without_side_effect_calls(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when the pipeline module avoids console and telemetry sinks."""
    _write_iteration_module(
        tmp_path,
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "def run_feature_iteration_pipeline() -> str:",
                "    return 'ok'",
            ]
        )
        + "\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.iteration-pipeline-observer-decoupling"
    assert payload["status"] == "pass"
    assert not _violations(payload)


def test_iteration_pipeline_observer_decoupling_rule_fails_on_console_and_telemetry_calls(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the pipeline module performs observer side effects directly."""
    _write_iteration_module(
        tmp_path,
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "def run_feature_iteration_pipeline(dependencies) -> None:",
                "    print('debug')",
                "    dependencies.print_summary('x', 'passed', None, 1, 'continue_same_feature')",
                "    dependencies.write_iteration_telemetry('payload', None)",
            ]
        )
        + "\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    violations = _violations(payload)
    assert len(violations) == 3
    assert any(
        "src/engineeringagent/application/feature_iteration_pipeline.py:4 invokes console output sink 'print'"
        in violation
        for violation in violations
    )
    assert any(
        "src/engineeringagent/application/feature_iteration_pipeline.py:5 invokes console output sink 'print_summary'"
        in violation
        for violation in violations
    )
    assert any(
        "src/engineeringagent/application/feature_iteration_pipeline.py:6 invokes telemetry sink 'write_iteration_telemetry'"
        in violation
        for violation in violations
    )
