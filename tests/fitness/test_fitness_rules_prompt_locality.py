from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import cast


def _script_path(repo_root: Path) -> Path:
    return repo_root / "harness" / "fitness-functions" / "check_prompt_locality.py"


def _write_module(project_root: Path, relative_path: str, body: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _write_prompt_templates(project_root: Path) -> None:
    template_root = project_root / "src" / "engineeringagent" / "prompts" / "templates"
    template_root.mkdir(parents=True, exist_ok=True)
    (template_root / "loop_selector.md").write_text("selector", encoding="utf-8")
    (template_root / "loop_implementation.md").write_text(
        "implementation", encoding="utf-8"
    )
    (template_root / "loop_retry_feedback.md").write_text("retry", encoding="utf-8")


def _violations(result: dict[str, object]) -> list[str]:
    return cast(list[str], result["violations"])


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


def test_prompt_locality_checker_emits_expected_rule_id(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Emit the stable rule id from the harness command adapter."""
    _write_prompt_templates(tmp_path)

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.prompt-locality"


def test_prompt_locality_rule_fails_when_required_templates_are_missing(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail with deterministic diagnostics when template artifacts are absent."""
    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert isinstance(violations, list)
    assert violations == sorted(violations)
    assert any(
        "src/engineeringagent/prompts/templates:1 missing prompt template directory"
        in violation
        for violation in violations
    )


def test_prompt_locality_rule_fails_when_required_template_is_empty(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when required templates exist but contain only whitespace."""
    _write_prompt_templates(tmp_path)
    retry_template = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "prompts"
        / "templates"
        / "loop_retry_feedback.md"
    )
    retry_template.write_text(" \n\t\n", encoding="utf-8")

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any(
        "loop_retry_feedback.md:1 required prompt template "
        "'loop_retry_feedback.md' is empty" in violation
        for violation in violations
    )


def test_prompt_locality_rule_fails_on_canonical_builder_definition(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when canonical prompt-builder names appear outside prompts modules."""
    _write_prompt_templates(tmp_path)
    _write_module(
        tmp_path,
        "src/engineeringagent/loop.py",
        "def build_ralph_opencode_prompt() -> str:\n    return 'ok'\n",
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any(
        "src/engineeringagent/loop.py:1 defines canonical prompt builder "
        "'build_ralph_opencode_prompt'" in violation
        for violation in violations
    )


def test_prompt_locality_rule_fails_on_template_reads_outside_prompt_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when non-approved modules read template markdown files."""
    _write_prompt_templates(tmp_path)
    _write_module(
        tmp_path,
        "src/engineeringagent/loop.py",
        "def read_template() -> str:\n"
        "    with open('src/engineeringagent/prompts/templates/loop_selector.md',"
        " encoding='utf-8') as handle:\n"
        "        return handle.read()\n",
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any(
        "src/engineeringagent/loop.py:2 reads prompt template markdown" in violation
        for violation in violations
    )


def test_prompt_locality_rule_fails_on_normalized_canary_leakage(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when canary phrases leak with punctuation/whitespace variation."""
    _write_prompt_templates(tmp_path)
    _write_module(
        tmp_path,
        "src/engineeringagent/loop.py",
        "PROMPT = 'Read... and use this feature spec from disk!!!'\n",
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any(
        "src/engineeringagent/loop.py:1 contains canonical prompt canary "
        "'read and use this feature spec from disk'" in violation
        for violation in violations
    )


def test_prompt_locality_rule_passes_for_localized_templates_and_prompts(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when prompt assets remain confined to approved prompts modules."""
    _write_prompt_templates(tmp_path)
    _write_module(
        tmp_path,
        "src/engineeringagent/prompts/renderer.py",
        "from importlib.resources import files\n"
        "\n"
        "def load() -> str:\n"
        "    return files('engineeringagent.prompts.templates')"
        ".joinpath('loop_selector.md').read_text(encoding='utf-8')\n",
    )
    _write_module(
        tmp_path,
        "src/engineeringagent/loop.py",
        "def run() -> None:\n    return None\n",
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert not _violations(result)


def test_prompt_locality_rule_reports_sorted_path_line_diagnostics(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Emit stable sorted path:line diagnostics across mixed violations."""
    _write_prompt_templates(tmp_path)
    _write_module(
        tmp_path,
        "src/engineeringagent/alpha.py",
        "PROMPT = 'Read and use this feature spec from disk.'\n",
    )
    _write_module(
        tmp_path,
        "src/engineeringagent/zeta.py",
        "def build_ralph_opencode_prompt() -> str:\n    return 'ok'\n",
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert violations == sorted(violations)
    assert violations[0].startswith("src/engineeringagent/alpha.py:1")
    assert any(
        violation.startswith("src/engineeringagent/zeta.py:1")
        and "build_ralph_opencode_prompt" in violation
        for violation in violations
    )
