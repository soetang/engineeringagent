from __future__ import annotations

from pathlib import Path
from typing import cast

from engineeringagent.fitness.builtin_rules import evaluate_scaffold_template_locality
from engineeringagent.fitness.registry import builtin_rule_definitions


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


def test_builtin_rule_definitions_include_scaffold_template_locality_rule() -> None:
    """Expose scaffold template locality as a registered built-in rule."""
    rule_ids = {
        definition.metadata.rule_id for definition in builtin_rule_definitions()
    }
    assert "architecture.scaffold-template-locality" in rule_ids


def test_scaffold_template_locality_rule_fails_when_required_templates_are_missing(
    tmp_path: Path,
) -> None:
    """Fail with deterministic diagnostics when scaffold template assets are absent."""
    result = evaluate_scaffold_template_locality(tmp_path)
    violations = _violations(result)

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

    result = evaluate_scaffold_template_locality(tmp_path)
    violations = _violations(result)

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

    result = evaluate_scaffold_template_locality(tmp_path)
    violations = _violations(result)

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

    result = evaluate_scaffold_template_locality(tmp_path)

    assert result["status"] == "pass"
    assert _violations(result) == []
