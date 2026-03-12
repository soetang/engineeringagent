from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_checker_module(repo_root: Path) -> ModuleType:
    script_path = (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "check_scaffold_template_locality.py"
    )
    spec = importlib.util.spec_from_file_location(
        "check_scaffold_template_locality",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_module(project_root: Path, relative_path: str, body: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _configure_checker_for_synthetic_templates(
    checker: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checker, "_SOURCE_PACKAGE_ROOT", Path("src/engineeringagent"))
    monkeypatch.setattr(
        checker,
        "_SCAFFOLD_TEMPLATE_ROOT",
        Path("src/engineeringagent/scaffold_templates"),
    )
    monkeypatch.setattr(
        checker,
        "_SCAFFOLD_TEMPLATE_ALLOWED_ROOT",
        Path("src/engineeringagent/scaffold_templates"),
    )
    monkeypatch.setattr(
        checker,
        "_REQUIRED_SCAFFOLD_TEMPLATES",
        ("template.a.txt", "template.b.txt"),
    )
    monkeypatch.setattr(
        checker,
        "_SCAFFOLD_TEMPLATE_CANARY_TOKENS",
        (("alpha", "canary"), ("beta", "canary")),
    )
    monkeypatch.setattr(
        checker,
        "_DEPRECATED_SCAFFOLD_GUIDANCE_TEMPLATES",
        ("deprecated-template.md",),
    )


def _write_templates(project_root: Path, *, template_a: str, template_b: str) -> None:
    _write_module(
        project_root,
        "src/engineeringagent/scaffold_templates/template.a.txt",
        template_a,
    )
    _write_module(
        project_root,
        "src/engineeringagent/scaffold_templates/template.b.txt",
        template_b,
    )


def test_scaffold_template_locality_checker_emits_expected_rule_id(
    repo_root: Path,
) -> None:
    """Emit the stable rule id from the harness command adapter."""
    checker = _load_checker_module(repo_root)
    assert checker.RULE_ID == "architecture.scaffold-template-locality"


def test_scaffold_template_locality_rule_fails_when_template_directory_missing(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail with deterministic diagnostics when scaffold template directory is absent."""
    checker = _load_checker_module(repo_root)
    _configure_checker_for_synthetic_templates(checker, monkeypatch)

    violations = checker._scaffold_template_locality_violations(tmp_path)

    assert violations == sorted(violations)
    assert any("missing scaffold template directory" in item for item in violations)


def test_scaffold_template_locality_rule_fails_when_required_template_is_missing(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail when one configured required template file is missing."""
    checker = _load_checker_module(repo_root)
    _configure_checker_for_synthetic_templates(checker, monkeypatch)

    _write_module(
        tmp_path,
        "src/engineeringagent/scaffold_templates/template.a.txt",
        "alpha canary\n",
    )

    violations = checker._scaffold_template_locality_violations(tmp_path)

    assert any(
        "missing required scaffold template 'template.b.txt'" in item
        for item in violations
    )


def test_scaffold_template_locality_rule_fails_when_required_template_is_empty(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail when required scaffold templates exist but contain only whitespace."""
    checker = _load_checker_module(repo_root)
    _configure_checker_for_synthetic_templates(checker, monkeypatch)

    _write_templates(tmp_path, template_a="\n\t\n", template_b="beta canary\n")
    violations = checker._scaffold_template_locality_violations(tmp_path)

    assert any(
        "required scaffold template 'template.a.txt' is empty" in item
        for item in violations
    )


def test_scaffold_template_locality_rule_fails_on_canary_leakage_outside_templates(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail when scaffold template canary content appears in non-template modules."""
    checker = _load_checker_module(repo_root)
    _configure_checker_for_synthetic_templates(checker, monkeypatch)

    _write_templates(tmp_path, template_a="alpha canary\n", template_b="beta canary\n")
    _write_module(
        tmp_path,
        "src/engineeringagent/loop.py",
        "SCAFFOLD = 'this string includes alpha canary tokens'\n",
    )

    violations = checker._scaffold_template_locality_violations(tmp_path)
    assert any(
        "contains scaffold template canary 'alpha canary'" in item
        for item in violations
    )


def test_scaffold_template_locality_rule_passes_for_localized_templates(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass when scaffold template content remains in scaffold template assets."""
    checker = _load_checker_module(repo_root)
    _configure_checker_for_synthetic_templates(checker, monkeypatch)

    _write_templates(tmp_path, template_a="alpha canary\n", template_b="beta canary\n")
    _write_module(
        tmp_path,
        "src/engineeringagent/bootstrap/init_scaffold.py",
        "def render() -> str:\n    return 'ok'\n",
    )

    violations = checker._scaffold_template_locality_violations(tmp_path)
    assert not violations


def test_scaffold_template_locality_rule_fails_when_deprecated_guidance_template_exists(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail when deprecated guidance template mirrors are kept in scaffold templates."""
    checker = _load_checker_module(repo_root)
    _configure_checker_for_synthetic_templates(checker, monkeypatch)

    _write_templates(tmp_path, template_a="alpha canary\n", template_b="beta canary\n")
    _write_module(
        tmp_path,
        "src/engineeringagent/scaffold_templates/deprecated-template.md",
        "legacy guidance mirror\n",
    )

    violations = checker._scaffold_template_locality_violations(tmp_path)
    assert any(
        "deprecated guidance template 'deprecated-template.md' must not be present"
        in item
        for item in violations
    )
