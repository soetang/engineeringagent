from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from engineeringagent.domain.quality import ChangedPathsResult
from engineeringagent.checks import run_checks
from engineeringagent.application.checks.runtime import (
    ChecksRunResult,
    _call_collect_changed_paths,
    _extract_command_invocation,
    _resolve_changed_paths,
    run_checks as run_checks_impl,
)
from engineeringagent.checks.request_normalization import build_run_checks_request
from engineeringagent.checks.strategy_contracts import (
    CheckDecision,
    CheckExecutionRecord,
    build_strategy_registry,
    strategy_run_decisions,
)
from engineeringagent.presentation.presenters.prompt_feedback import normalize_prompt_feedback
from engineeringagent.domain.quality import HarnessCheckPhase

from tests.checks.run_checks_contract_support import StubStrategy, write_checks_yaml


def test_run_checks_defaults_to_validate_commands_and_fitness(tmp_path: Path) -> None:
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "  fit_all:",
                "    type: fitness",
                "    scope: all",
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end", dry_run=True)
    assert result.ok
    assert [decision["check_type"] for decision in result.decisions] == [
        "validate",
        "command",
        "fitness",
    ]
    assert result.executions == ()


def test_run_checks_direct_mode_ignores_on_change_for_phase_matched_checks(
    tmp_path: Path,
) -> None:
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  cmd_on_change:",
                "    type: command",
                "    command: echo ok",
                "    when:",
                "      phase: feature_done",
                "      on_change:",
                "        - src/**/*.py",
                "  fit_on_change:",
                "    type: fitness",
                "    scope: all",
                "    when:",
                "      phase: feature_done",
                "      on_change:",
                "        - src/**/*.py",
                "  doc_review:",
                "    type: reviewer",
                "    prompt_file: harness/reviewers/prompts/doc_review.md",
                "    when:",
                "      phase: feature_done",
                "      on_change:",
                "        - src/**/*.py",
                "",
            ]
        ),
    )
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "doc_review.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("# reviewer", encoding="utf-8")

    result = run_checks(
        tmp_path,
        phase="feature_done",
        checks=["commands", "fitness", "reviewers"],
        feature_path="docs/spec/features/FEAT-175/spec.yaml",
        dry_run=True,
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=("README.md",),
            run_all=False,
            reason=None,
        ),
    )

    assert result.ok
    assert [decision["check_id"] for decision in result.decisions] == [
        "cmd_on_change",
        "fit_on_change",
        "doc_review",
    ]
    assert {decision["decision"] for decision in result.decisions} == {"run"}


def test_run_checks_loop_runtime_mode_still_honors_on_change(tmp_path: Path) -> None:
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  cmd_on_change:",
                "    type: command",
                "    command: echo ok",
                "    when:",
                "      phase: iteration_end",
                "      on_change:",
                "        - src/**/*.py",
                "  fit_on_change:",
                "    type: fitness",
                "    scope: all",
                "    when:",
                "      phase: iteration_end",
                "      on_change:",
                "        - src/**/*.py",
                "",
            ]
        ),
    )

    result = run_checks(
        tmp_path,
        phase="iteration_end",
        dry_run=True,
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=("README.md",),
            run_all=False,
            reason=None,
        ),
    )

    assert result.ok
    decisions = [d for d in result.decisions if d["check_type"] in {"command", "fitness"}]
    assert [decision["decision"] for decision in decisions] == ["skip", "skip"]
    assert [decision["reason"] for decision in decisions] == [
        "no_on_change_match",
        "no_on_change_match",
    ]


def test_run_checks_direct_mode_runs_manual_phase_checks(tmp_path: Path) -> None:
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  manual_cmd:",
                "    type: command",
                "    command: echo ok",
                "    when:",
                "      phase: manual",
                "      on_change:",
                "        - src/**/*.py",
                "",
            ]
        ),
    )

    result = run_checks(
        tmp_path,
        phase="manual",
        checks=["commands"],
        dry_run=True,
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=("README.md",),
            run_all=False,
            reason=None,
        ),
    )

    assert result.ok
    assert len(result.decisions) == 1
    assert result.decisions[0]["check_id"] == "manual_cmd"
    assert result.decisions[0]["decision"] == "run"
    assert result.decisions[0]["reason"] == "phase_only_policy"


def test_run_checks_group_order_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_checks_yaml(
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
        "engineeringagent.application.checks.runtime.collect_changed_paths",
        lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=None,
        ),
        raising=True,
    )
    monkeypatch.setattr(
        "engineeringagent.checks.strategies.run_shell_command",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="ok\n", stderr=""),
        raising=True,
    )

    result = run_checks_impl(tmp_path, phase="iteration_end", checks=["fitness", "commands"])

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
        _call_collect_changed_paths(cast(Any, _collector), tmp_path, base="main", head=None)


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
        _call_collect_changed_paths(cast(Any, _collector), tmp_path, base="main", head=None)


def test_call_collect_changed_paths_passes_kwargs_to_var_keyword_collector(
    tmp_path: Path,
) -> None:
    calls: list[tuple[Path, dict[str, str | None]]] = []

    def _collector(project_root: Path, **kwargs: str | None) -> object:
        calls.append((project_root, kwargs))
        return {"ok": True}

    result = _call_collect_changed_paths(_collector, tmp_path, base="main", head="feature")

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
        return ChangedPathsResult(paths=("src/example.py",), run_all=False, reason=None)

    _, request = build_run_checks_request(
        tmp_path,
        phase=HarnessCheckPhase.ITERATION_END,
        checks=["commands"],
        kwargs={
            "base": "main",
            "head": "feature",
            "collect_changed_paths": _collector,
        },
    )

    result = _resolve_changed_paths(tmp_path, request)
    assert result == ChangedPathsResult(paths=("src/example.py",), run_all=False, reason=None)
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
    assert normalize_prompt_feedback("\n  ### Checks Failure\n- item\n  ") == "### Checks Failure\n- item"


def test_normalize_prompt_feedback_rejects_blank_or_non_string_values() -> None:
    assert normalize_prompt_feedback("\n  ") is None
    assert normalize_prompt_feedback(None) is None


def test_build_strategy_registry_rejects_invalid_check_type() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        build_strategy_registry([StubStrategy(" ")])


def test_build_strategy_registry_rejects_duplicate_registration() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        build_strategy_registry([StubStrategy("command"), StubStrategy("command")])


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
        run_checks(tmp_path, phase="iteration_end", checks=["commands"], schema_only=True)


def test_run_checks_check_id_filters_to_single_check(tmp_path: Path) -> None:
    write_checks_yaml(
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

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"], check_id="b")
    assert result.ok
    assert [decision["check_id"] for decision in result.decisions] == ["b"]
    assert [record.check_id for record in result.executions] == ["b"]


def test_run_checks_unknown_check_id_is_deterministic_failure(tmp_path: Path) -> None:
    write_checks_yaml(
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

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"], check_id="missing")
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
