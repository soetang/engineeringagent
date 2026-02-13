from __future__ import annotations

from pathlib import Path

from engineeringagent.fitness.builtin_rules import evaluate_dependency_directionality
from engineeringagent.fitness.registry import builtin_rule_definitions


def _write_module(project_root: Path, module_path: str, body: str) -> None:
    path = project_root / "src" / "engineeringagent" / module_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _write_directionality_fixture(project_root: Path) -> None:
    _write_module(project_root, "cli.py", "")
    _write_module(project_root, "loop.py", "")
    _write_module(project_root, "gates.py", "")
    _write_module(project_root, "validator.py", "from .specs import FeatureSpec\n")
    _write_module(project_root, "specs.py", "")


def test_builtin_rule_definitions_include_directionality_rule() -> None:
    """Expose dependency directionality as a registered built-in rule."""
    rule_ids = {
        definition.metadata.rule_id for definition in builtin_rule_definitions()
    }
    assert "architecture.dep-directionality" in rule_ids


def test_directionality_rule_reports_blocked_import(tmp_path: Path) -> None:
    """Fail when a protected module imports a blocked dependency."""
    _write_directionality_fixture(tmp_path)
    _write_module(tmp_path, "specs.py", "import engineeringagent.loop\n")

    result = evaluate_dependency_directionality(tmp_path)
    violations = result["violations"]

    assert result["status"] == "fail"
    assert isinstance(violations, list)
    assert any(
        "engineeringagent.specs imports blocked dependency engineeringagent.loop"
        in violation
        for violation in violations
    )
