from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from pydantic import BaseModel, ValidationError

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.checks import run_checks
from engineeringagent.checks.api import (
    ChecksRunResult,
    _RunChecksRequest,
    _call_collect_changed_paths,
    _extract_command_invocation,
    _resolve_changed_paths,
    run_checks as run_checks_impl,
)
from engineeringagent.prompt_feedback import normalize_prompt_feedback
from engineeringagent.checks.reviewers.runtime import FALLBACK_REMEDIATION_GUIDANCE
from engineeringagent.checks.config_loader import load_harness_checks_document
from engineeringagent.checks.strategy_contracts import (
    CheckDecision,
    CheckExecutionRecord,
    build_strategy_registry,
    strategy_run_decisions,
)
from engineeringagent.specs import HarnessCheckPhase


def _write_checks_yaml(tmp_path: Path, content: str) -> Path:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text(content, encoding="utf-8")
    return checks_path


class _StubStrategy:
    def __init__(self, check_type: str) -> None:
        self.check_type = check_type

    def plan(self, *, context: Any) -> tuple[Any, ...]:
        _ = context
        return ()

    def execute(self, *, context: Any, decisions: tuple[Any, ...]) -> tuple[Any, ...]:
        _ = (context, decisions)
        return ()

    def render_prompt_feedback(self, *, failed_record: Any) -> str | None:
        _ = failed_record
        return None


def test_run_checks_defaults_to_commands_and_fitness(tmp_path: Path) -> None:
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
    assert [decision["check_id"] for decision in result.decisions] == ["smoke"]
    assert [record.check_id for record in result.executions] == ["smoke"]


def test_run_checks_group_order_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo ok",
                "  fit_all:",
                "    type: fitness",
                "    scope: all",
                "",
            ]
        ),
    )
    monkeypatch.setattr(
        "engineeringagent.changed_paths.collect_changed_paths",
        lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=None,
        ),
        raising=True,
    )
    monkeypatch.setattr(
        "engineeringagent.checks.strategies.run_shell_command",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout="ok\n", stderr=""
        ),
        raising=True,
    )

    result = run_checks_impl(
        tmp_path,
        phase="iteration_end",
        checks=["fitness", "commands"],
    )
    assert isinstance(result, ChecksRunResult)
    assert result.ok
    assert [item["check_type"] for item in result.decisions] == ["command", "fitness"]
    assert [record.check_type for record in result.executions] == ["command", "fitness"]


def test_call_collect_changed_paths_raises_on_incompatible_signature(
    tmp_path: Path,
) -> None:
    def _collector(project_root: Path) -> object:
        _ = project_root
        return {"ok": True}

    with pytest.raises(TypeError, match="unexpected keyword argument 'base'"):
        _call_collect_changed_paths(
            cast(Any, _collector),
            tmp_path,
            base="main",
            head=None,
        )


def test_call_collect_changed_paths_does_not_swallow_internal_type_errors(
    tmp_path: Path,
) -> None:
    def _collector(
        project_root: Path,
        *,
        base: str | None = None,
        head: str | None = None,
    ) -> object:
        _ = (project_root, head)
        if base is not None:
            raise TypeError("collector internal error")
        return {"ok": True}

    with pytest.raises(TypeError, match="collector internal error"):
        _call_collect_changed_paths(
            cast(Any, _collector),
            tmp_path,
            base="main",
            head=None,
        )


def test_call_collect_changed_paths_passes_kwargs_to_var_keyword_collector(
    tmp_path: Path,
) -> None:
    calls: list[tuple[Path, dict[str, str | None]]] = []

    def _collector(project_root: Path, **kwargs: str | None) -> object:
        calls.append((project_root, kwargs))
        return {"ok": True}

    result = _call_collect_changed_paths(
        _collector,
        tmp_path,
        base="main",
        head="feature",
    )

    assert result == {"ok": True}
    assert calls == [(tmp_path, {"base": "main", "head": "feature"})]


def test_resolve_changed_paths_uses_request_collector_with_base_head(
    tmp_path: Path,
) -> None:
    calls: list[tuple[Path, str | None, str | None]] = []

    def _collector(
        project_root: Path,
        *,
        base: str | None = None,
        head: str | None = None,
    ) -> object:
        calls.append((project_root, base, head))
        return ChangedPathsResult(
            paths=("src/example.py",),
            run_all=False,
            reason=None,
        )

    request = _RunChecksRequest(
        phase=HarnessCheckPhase.ITERATION_END,
        ordered_groups=("commands",),
        check_id=None,
        feature_path=None,
        verbose_output=False,
        base="main",
        head="feature",
        run_agent_fn=None,
        feedback=None,
        schema_only=False,
        dry_run=False,
        collect_changed_paths_fn=_collector,
    )

    result = _resolve_changed_paths(tmp_path, request)
    assert result == ChangedPathsResult(
        paths=("src/example.py",),
        run_all=False,
        reason=None,
    )
    assert calls == [(tmp_path, "main", "feature")]


def test_extract_command_invocation_ignores_non_dict_payload() -> None:
    record = CheckExecutionRecord(
        check_id="cmd",
        check_type="command",
        ok=False,
        output="",
        timing={"command_invocation": "not-a-dict"},
    )

    assert _extract_command_invocation(record) is None


def test_extract_command_invocation_ignores_invalid_record_shape() -> None:
    record = CheckExecutionRecord(
        check_id="cmd",
        check_type="command",
        ok=False,
        output="",
        timing={"command_invocation": {"check_id": "cmd"}},
    )

    assert _extract_command_invocation(record) is None


def test_normalize_prompt_feedback_strips_markdown_feedback() -> None:
    assert normalize_prompt_feedback("\n  ### Checks Failure\n- item\n  ") == (
        "### Checks Failure\n- item"
    )


def test_normalize_prompt_feedback_rejects_blank_or_non_string_values() -> None:
    assert normalize_prompt_feedback("\n  ") is None
    assert normalize_prompt_feedback(None) is None


def test_build_strategy_registry_rejects_invalid_check_type() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        build_strategy_registry([_StubStrategy(" ")])


def test_build_strategy_registry_rejects_duplicate_registration() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        build_strategy_registry([_StubStrategy("command"), _StubStrategy("command")])


def test_strategy_run_decisions_filters_run_entries_in_order() -> None:
    decisions: tuple[CheckDecision, ...] = (
        CheckDecision(
            check_id="cmd_a",
            check_type="command",
            phase="iteration_end",
            decision="run",
            reason="always",
        ),
        CheckDecision(
            check_id="fit_a",
            check_type="fitness",
            phase="iteration_end",
            decision="run",
            reason="always",
        ),
        CheckDecision(
            check_id="cmd_b",
            check_type="command",
            phase="iteration_end",
            decision="skip",
            reason="no_change_match",
        ),
    )

    result = strategy_run_decisions(decisions)
    assert [entry["check_id"] for entry in result] == ["cmd_a", "fit_a"]
    assert [entry["decision"] for entry in result] == ["run", "run"]


def test_run_checks_schema_only_requires_validate_group(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="schema_only requires"):
        run_checks(
            tmp_path, phase="iteration_end", checks=["commands"], schema_only=True
        )


def test_run_checks_check_id_filters_to_single_check(tmp_path: Path) -> None:
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
    assert [decision["check_id"] for decision in result.decisions] == ["b"]
    assert [record.check_id for record in result.executions] == ["b"]


def test_run_checks_unknown_check_id_is_deterministic_failure(tmp_path: Path) -> None:
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
    with pytest.raises(ValueError, match="feature_path"):
        run_checks(tmp_path, phase="iteration_end", checks=["reviewers"])


def test_run_checks_invalid_group_is_a_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown checks groups"):
        run_checks(tmp_path, phase="iteration_end", checks=["nope"])


def test_run_checks_invalid_phase_is_a_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown phase"):
        run_checks(tmp_path, phase="not-a-phase", checks=[])


def test_run_checks_missing_checks_yaml_is_config_failure(tmp_path: Path) -> None:
    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])
    assert not result.ok
    assert result.failed_check_id is None
    assert "missing harness/checks.yaml" in result.output


def test_shared_loader_missing_file_returns_actionable_error(tmp_path: Path) -> None:
    doc, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
    )

    assert doc is None
    assert error is not None
    assert error.startswith("checks config error:")
    assert "missing harness/checks.yaml" in error
    assert "Remediation: run `engineeringagent init`." in error


def test_shared_loader_includes_missing_context_when_provided(tmp_path: Path) -> None:
    doc, error = load_harness_checks_document(
        tmp_path,
        error_prefix="run config error",
        missing_context=" (required for --all)",
    )

    assert doc is None
    assert error is not None
    assert error.startswith("run config error:")
    assert "missing harness/checks.yaml" in error
    assert "(required for --all)" in error
    assert "Remediation: run `engineeringagent init`." in error


def test_shared_loader_failed_load_is_deterministic(tmp_path: Path) -> None:
    _write_checks_yaml(tmp_path, "- list\n")

    doc, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
    )

    assert doc is None
    assert error is not None
    assert error.startswith("checks config error: failed to load harness/checks.yaml:")


def test_shared_loader_contract_issues_are_rendered_deterministically(
    tmp_path: Path,
) -> None:
    _write_checks_yaml(tmp_path, "checks: {}\n")

    doc, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
    )

    assert doc is None
    assert error is not None
    assert "checks config error: invalid harness/checks.yaml" in error
    assert "harness/checks.yaml:contract_version" in error


def test_shared_loader_returns_document_on_valid_config(tmp_path: Path) -> None:
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "echo ok"',
                "",
            ]
        ),
    )

    doc, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
    )

    assert error is None
    assert doc is not None
    assert "smoke" in doc.checks


def test_shared_loader_model_validation_error_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "echo ok"',
                "",
            ]
        ),
    )

    class _ValidationProbe(BaseModel):
        value: int

    validation_error: ValidationError | None = None
    try:
        _ValidationProbe.model_validate({"value": "invalid"})
    except ValidationError as exc:
        validation_error = exc
    assert validation_error is not None

    def _raise_validation_error(_payload: object) -> object:
        raise validation_error

    monkeypatch.setattr(
        "engineeringagent.checks.config_loader.checks_contract_issues",
        lambda *_args, **_kwargs: [],
        raising=True,
    )
    monkeypatch.setattr(
        "engineeringagent.checks.config_loader.HarnessChecksDocument.model_validate",
        _raise_validation_error,
        raising=True,
    )

    doc, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
    )
    assert doc is None
    assert error is not None
    assert "checks config error: failed to validate harness/checks.yaml:" in error


def test_run_checks_check_id_without_harness_doc_fails_deterministically(
    tmp_path: Path,
) -> None:
    result = run_checks(
        tmp_path,
        phase="iteration_end",
        checks=["validate"],
        check_id="smoke",
    )
    assert not result.ok
    assert result.failed_check_id == "smoke"


def test_run_checks_reviewers_returns_not_implemented_result(
    tmp_path: Path,
) -> None:
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
    assert result.failed_check_id is None
    assert [decision["check_id"] for decision in result.decisions] == ["doc_review"]
    assert [record.check_id for record in result.executions] == ["doc_review"]
    assert len(calls) == 1


def test_run_checks_reviewers_request_changes_fails_deterministically(
    tmp_path: Path,
) -> None:
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
    assert result.failed_check_id == "doc_review"
    assert [decision["check_id"] for decision in result.decisions] == ["doc_review"]
    assert [record.check_id for record in result.executions] == ["doc_review"]


def test_run_checks_reviewers_verbose_output_surfaces_full_payload(
    tmp_path: Path,
) -> None:
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
                "summary": "needs follow-up",
                "required_actions": ["fix"],
                "scope_notes": "tests only",
            }
        )

    result = run_checks(
        tmp_path,
        phase="feature_done",
        checks=["reviewers"],
        feature_path=feature_path,
        verbose_output=True,
        run_agent_fn=_run_agent,
    )
    assert not result.ok
    assert (
        '[reviewer:doc_review] payload={"decision":"request_changes",'
        '"required_actions":["fix"],"scope_notes":"tests only",'
        '"summary":"needs follow-up"}'
    ) in result.output


def test_run_checks_reviewers_adds_fallback_remediation_when_actions_missing(
    tmp_path: Path,
) -> None:
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
                "summary": "needs follow-up",
                "required_actions": [],
                "scope_notes": "tests only",
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
    assert (
        f"[reviewer:doc_review] remediation={FALLBACK_REMEDIATION_GUIDANCE}"
        in result.output
    )
    assert result.prompt_feedback is not None


def test_run_checks_reviewers_treats_blank_actions_as_missing_for_prompt_feedback(
    tmp_path: Path,
) -> None:
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
                "summary": "needs follow-up",
                "required_actions": [" ", "\t", ""],
                "scope_notes": "tests only",
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
    assert (
        f"[reviewer:doc_review] remediation={FALLBACK_REMEDIATION_GUIDANCE}"
        in result.output
    )
    assert result.prompt_feedback is not None


def test_run_checks_check_id_must_match_enabled_groups(tmp_path: Path) -> None:
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
    assert result.failed_check_id == "smoke"


def test_run_checks_validate_group_executes(tmp_path: Path) -> None:
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


def test_run_checks_rejects_run_shell_command_kwarg(tmp_path: Path) -> None:
    untyped_run_checks = cast(Any, run_checks)
    with pytest.raises(
        TypeError, match="unexpected keyword argument 'run_shell_command'"
    ):
        untyped_run_checks(
            tmp_path,
            phase="iteration_end",
            run_shell_command=lambda _root, _command: SimpleNamespace(returncode=0),
        )


def test_run_checks_reports_parse_failures_without_raising(tmp_path: Path) -> None:
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo hi | cat",
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])

    assert not result.ok
    assert "[check:smoke] returncode=2" in result.output
    assert "shell syntax is not supported" in result.output
    assert "Remediation: provide a plain argv-style command" in result.output


def test_run_checks_allows_literal_shell_like_command_arguments(
    tmp_path: Path,
) -> None:
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo $HOME ${HOME} `uname`",
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])

    assert result.ok
    assert "[check:smoke] returncode=0" in result.output
    stdout = result.output.split("[check:smoke] returncode=0", 1)[1].lstrip()
    stdout_line = stdout.splitlines()[0]
    assert stdout_line == "$HOME ${HOME} `uname`"


def test_run_checks_rejects_shell_chaining_without_partial_execution(
    tmp_path: Path,
) -> None:
    marker_path = tmp_path / "checks-shell-chaining-marker.txt"
    command = f"touch {marker_path.as_posix()} && echo should-not-run"
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                f"    command: {command}",
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])

    assert not result.ok
    assert "[check:smoke] returncode=2" in result.output
    assert "shell syntax is not supported" in result.output
    assert "Remediation: provide a plain argv-style command" in result.output
    assert not marker_path.exists()


def test_run_checks_rejects_shell_redirection_without_partial_execution(
    tmp_path: Path,
) -> None:
    marker_path = tmp_path / "checks-shell-redirection-marker.txt"
    redirected_path = tmp_path / "checks-shell-redirection.out"
    command = f"touch {marker_path.as_posix()} > {redirected_path.as_posix()}"
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                f"    command: {command}",
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])

    assert not result.ok
    assert "[check:smoke] returncode=2" in result.output
    assert "shell syntax is not supported" in result.output
    assert "Remediation: provide a plain argv-style command" in result.output
    assert not marker_path.exists()
    assert not redirected_path.exists()


def test_run_checks_reports_missing_executable_without_raising(tmp_path: Path) -> None:
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: missing-executable-for-feat-159",
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])

    assert not result.ok
    assert "[check:smoke] returncode=127" in result.output
    assert "command executable not found: missing-executable-for-feat-159" in result.output
    assert "Remediation: install the executable" in result.output


def test_run_checks_command_prompt_feedback_includes_command_returncode_and_excerpt(
    tmp_path: Path,
) -> None:
    command = 'python -c "print(1); import sys; sys.exit(3)"'
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                f"    command: '{command}'",
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])

    assert not result.ok
    assert result.prompt_feedback is not None
    assert f"- command: `{command}`" in result.prompt_feedback
    assert "- returncode: 3" in result.prompt_feedback
    assert "- failure_output_excerpt:" in result.prompt_feedback
    assert "  1" in result.prompt_feedback


def test_run_checks_exposes_structured_command_invocations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo hi",
                "",
            ]
        ),
    )

    def _run_shell_command(_root: Path, _command: str) -> object:
        return SimpleNamespace(returncode=0, stdout="hi\n", stderr="")

    monkeypatch.setattr(
        "engineeringagent.checks.strategies.run_shell_command",
        _run_shell_command,
        raising=True,
    )

    result = run_checks(
        tmp_path,
        phase="iteration_end",
        checks=["commands"],
    )
    assert result.ok
    assert len(result.command_invocations) == 1
    invocation = result.command_invocations[0]
    assert invocation.check_id == "smoke"
    assert invocation.command == "echo hi"
    assert invocation.returncode == 0
    assert invocation.duration_ms >= 0


def test_run_checks_dry_run_is_decisions_only_and_side_effect_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo hi",
                "",
            ]
        ),
    )

    def _should_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("command execution must not happen in dry-run")

    monkeypatch.setattr(
        "engineeringagent.checks.strategies.run_shell_command",
        _should_not_run,
        raising=True,
    )

    result = run_checks(
        tmp_path,
        phase="iteration_end",
        checks=["commands"],
        dry_run=True,
    )

    assert result.ok
    assert result.dry_run is True
    assert len(result.decisions) == 1
    assert result.decisions[0]["check_id"] == "smoke"
    assert result.executions == ()
    assert result.failed_check_id is None
