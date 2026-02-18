from __future__ import annotations

from pathlib import Path

import pytest

from pydantic import BaseModel


def _write_checks_yaml(tmp_path: Path, content: str) -> Path:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text(content, encoding="utf-8")
    return checks_path


def test_run_checks_defaults_to_commands_and_fitness(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end")
    assert result.ok
    assert "[check:smoke]" in result.output


def test_run_checks_group_order_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from engineeringagent.checks.api import ChecksRunResult
    from engineeringagent.checks.api import _GroupRunResult
    from engineeringagent.checks.api import run_checks as run_checks_impl

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
    )

    calls: list[str] = []

    def _commands(*_args: object, **_kwargs: object) -> _GroupRunResult:
        calls.append("commands")
        return _GroupRunResult(ok=True, failed_check_id=None, output="commands-out")

    def _fitness(*_args: object, **_kwargs: object) -> _GroupRunResult:
        calls.append("fitness")
        return _GroupRunResult(ok=True, failed_check_id=None, output="fitness-out")

    monkeypatch.setattr(
        "engineeringagent.checks.api._run_commands_group",
        _commands,
    )
    monkeypatch.setattr(
        "engineeringagent.checks.api._run_fitness_group",
        _fitness,
    )

    result = run_checks_impl(
        tmp_path,
        phase="iteration_end",
        checks=["fitness", "commands"],
    )
    assert isinstance(result, ChecksRunResult)
    assert result.ok
    assert calls == ["commands", "fitness"]
    assert result.output == "commands-out\nfitness-out"


def test_call_collect_changed_paths_falls_back_when_kwargs_unexpected(
    tmp_path: Path,
) -> None:
    from engineeringagent.checks.api import _call_collect_changed_paths

    calls: list[tuple[str, Path]] = []

    def _collector(project_root: Path) -> object:
        calls.append(("one-arg", project_root))
        return {"ok": True}

    result = _call_collect_changed_paths(
        _collector,
        tmp_path,
        base="main",
        head=None,
    )
    assert result == {"ok": True}
    assert calls == [("one-arg", tmp_path)]


def test_call_collect_changed_paths_does_not_swallow_internal_type_errors(
    tmp_path: Path,
) -> None:
    from engineeringagent.checks.api import _call_collect_changed_paths

    def _collector(
        project_root: Path,
        *,
        base: str | None = None,
        head: str | None = None,
    ) -> object:
        _ = head
        if base is not None:
            raise TypeError("collector internal error")
        return {"ok": True}

    with pytest.raises(TypeError, match="collector internal error"):
        _call_collect_changed_paths(
            _collector,
            tmp_path,
            base="main",
            head=None,
        )


def test_run_checks_check_id_filters_to_single_check(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  a:",
                "    type: command",
                '    command: "python -c \\"print(\'a\')\\""',
                "  b:",
                "    type: command",
                '    command: "python -c \\"print(\'b\')\\""',
                "",
            ]
        ),
    )

    result = run_checks(
        tmp_path,
        phase="iteration_end",
        checks=["commands"],
        check_id="b",
    )
    assert result.ok
    assert "[check:b]" in result.output
    assert "[check:a]" not in result.output


def test_run_checks_unknown_check_id_is_deterministic_failure(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
    )

    result = run_checks(
        tmp_path,
        phase="iteration_end",
        checks=["commands"],
        check_id="missing",
    )
    assert not result.ok
    assert result.failed_check_id == "missing"
    assert "unknown" in result.output


def test_run_checks_reviewers_requires_feature_path(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    with pytest.raises(ValueError, match="feature_path"):
        run_checks(tmp_path, phase="iteration_end", checks=["reviewers"])


def test_run_checks_invalid_group_is_a_value_error(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    with pytest.raises(ValueError, match="unknown checks groups"):
        run_checks(tmp_path, phase="iteration_end", checks=["nope"])


def test_run_checks_invalid_phase_is_a_value_error(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    with pytest.raises(ValueError, match="unknown phase"):
        run_checks(tmp_path, phase="not-a-phase", checks=[])


def test_run_checks_missing_checks_yaml_is_config_failure(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])
    assert not result.ok
    assert result.failed_group == "config"
    assert "missing harness/checks.yaml" in result.output


def test_run_checks_check_id_without_harness_doc_fails_deterministically(
    tmp_path: Path,
) -> None:
    from engineeringagent.checks import run_checks

    result = run_checks(
        tmp_path,
        phase="iteration_end",
        checks=["validate"],
        check_id="smoke",
    )
    assert not result.ok
    assert result.failed_group == "selection"
    assert result.failed_check_id == "smoke"


def test_run_checks_reviewers_returns_not_implemented_result(
    tmp_path: Path,
) -> None:
    from engineeringagent.checks import run_checks

    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "doc_review.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("Please review. $responseformat\n", encoding="utf-8")

    feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml"
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_path.write_text("id: FEAT-001\n", encoding="utf-8")

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  doc_review:",
                "    type: reviewer",
                "    prompt_file: harness/reviewers/prompts/doc_review.md",
                "    when:",
                "      phase: feature_done",
                "",
            ]
        ),
    )

    calls: list[tuple[Path, str]] = []

    def _run_agent(
        execution_root: Path,
        prompt: str,
        *,
        output_type: type[BaseModel],
        backend: object = None,
        max_validation_retries: int = 2,
    ) -> BaseModel:
        del backend
        del max_validation_retries
        calls.append((execution_root, prompt))
        return output_type.model_validate(
            {
                "decision": "approve",
                "summary": "ok",
                "required_actions": [],
            }
        )

    result = run_checks(
        tmp_path,
        phase="feature_done",
        checks=["reviewers"],
        feature_path=feature_path,
        run_agent_fn=_run_agent,
    )
    assert result.ok
    assert result.failed_group is None
    assert "[reviewer:doc_review] decision=approve" in result.output
    assert len(calls) == 1


def test_run_checks_reviewers_request_changes_fails_deterministically(
    tmp_path: Path,
) -> None:
    from engineeringagent.checks import run_checks

    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "doc_review.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("Please review. $responseformat\n", encoding="utf-8")

    feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml"
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_path.write_text("id: FEAT-001\n", encoding="utf-8")

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  doc_review:",
                "    type: reviewer",
                "    prompt_file: harness/reviewers/prompts/doc_review.md",
                "    when:",
                "      phase: feature_done",
                "",
            ]
        ),
    )

    def _run_agent(
        _execution_root: Path,
        _prompt: str,
        *,
        output_type: type[BaseModel],
        backend: object = None,
        max_validation_retries: int = 2,
    ) -> BaseModel:
        del backend
        del max_validation_retries
        return output_type.model_validate(
            {
                "decision": "request_changes",
                "summary": "nope",
                "required_actions": ["fix"],
            }
        )

    result = run_checks(
        tmp_path,
        phase="feature_done",
        checks=["reviewers"],
        feature_path=feature_path,
        run_agent_fn=_run_agent,
    )
    assert not result.ok
    assert result.failed_group == "reviewers"
    assert result.failed_check_id == "doc_review"
    assert "decision=request_changes" in result.output


def test_run_checks_check_id_must_match_enabled_groups(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
    )

    result = run_checks(
        tmp_path,
        phase="iteration_end",
        checks=["fitness"],
        check_id="smoke",
    )
    assert not result.ok
    assert result.failed_group == "selection"
    assert result.failed_check_id == "smoke"


def test_run_checks_validate_group_executes(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    # Validate-group contract: it should be runnable independent of the full repo.
    (tmp_path / "docs" / "spec" / "features").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "spec" / "features" / ".gitkeep").write_text(
        "",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "spec" / "features_done").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "spec" / "features_done" / ".gitkeep").write_text(
        "",
        encoding="utf-8",
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["validate"])
    assert result.ok


def test_run_checks_accepts_harness_phase_enum(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks
    from engineeringagent.specs import HarnessCheckPhase

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
    )

    result = run_checks(
        tmp_path,
        phase=HarnessCheckPhase.ITERATION_END,
    )
    assert result.ok
