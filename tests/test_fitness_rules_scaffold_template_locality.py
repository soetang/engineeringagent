from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import cast


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "harness"
    / "fitness-functions"
    / "check_scaffold_template_locality.py"
)


def _write_module(project_root: Path, relative_path: str, body: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _write_scaffold_templates(project_root: Path) -> None:
    template_root = project_root / "src" / "engineeringagent" / "scaffold_templates"
    template_root.mkdir(parents=True, exist_ok=True)
    (template_root / "AGENTS.md").write_text("Agent operating guide", encoding="utf-8")
    (template_root / "precommit.core.yaml").write_text("repos:\n", encoding="utf-8")
    (template_root / "precommit.python_uv.yaml").write_text(
        "repos:\n", encoding="utf-8"
    )
    (template_root / "reference.docs-architecture-llms.md").write_text(
        "Audience Split", encoding="utf-8"
    )
    (template_root / "reference.workflow-llms.md").write_text(
        "Loop workflow", encoding="utf-8"
    )


def _violations(result: dict[str, object]) -> list[str]:
    return cast(list[str], result["violations"])


def _run_checker(
    project_root: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def test_scaffold_template_locality_checker_emits_expected_rule_id(
    tmp_path: Path,
) -> None:
    """Emit the stable rule id from the harness command adapter."""
    _write_scaffold_templates(tmp_path)

    proc, payload = _run_checker(tmp_path)

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.scaffold-template-locality"


def test_scaffold_template_locality_rule_fails_when_required_templates_are_missing(
    tmp_path: Path,
) -> None:
    """Fail with deterministic diagnostics when scaffold template assets are absent."""
    proc, result = _run_checker(tmp_path)
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert violations == sorted(violations)
    assert any(
        "src/engineeringagent/scaffold_templates:1 missing scaffold template "
        "directory" in violation
        for violation in violations
    )


def test_scaffold_template_locality_rule_fails_when_required_template_is_empty(
    tmp_path: Path,
) -> None:
    """Fail when required scaffold templates exist but contain only whitespace."""
    _write_scaffold_templates(tmp_path)
    agents_template = (
        tmp_path / "src" / "engineeringagent" / "scaffold_templates" / "AGENTS.md"
    )
    agents_template.write_text("\n\t\n", encoding="utf-8")

    proc, result = _run_checker(tmp_path)
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any(
        "src/engineeringagent/scaffold_templates/AGENTS.md:1 required scaffold "
        "template 'AGENTS.md' is empty" in violation
        for violation in violations
    )


def test_scaffold_template_locality_rule_fails_on_canary_leakage_outside_templates(
    tmp_path: Path,
) -> None:
    """Fail when scaffold template canary content appears in non-template modules."""
    _write_scaffold_templates(tmp_path)
    _write_module(
        tmp_path,
        "src/engineeringagent/loop.py",
        "SCAFFOLD = 'Agent operating guide for this repository.'\n",
    )

    proc, result = _run_checker(tmp_path)
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any(
        "src/engineeringagent/loop.py:1 contains scaffold template canary "
        "'agent operating guide for this repository'" in violation
        for violation in violations
    )


def test_scaffold_template_locality_rule_passes_for_localized_templates(
    tmp_path: Path,
) -> None:
    """Pass when scaffold template content remains in scaffold template assets."""
    _write_scaffold_templates(tmp_path)
    _write_module(
        tmp_path,
        "src/engineeringagent/init_scaffold.py",
        "def render() -> str:\n    return 'ok'\n",
    )

    proc, result = _run_checker(tmp_path)

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert _violations(result) == []
