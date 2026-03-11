from __future__ import annotations

from pathlib import Path
from typing import Any

from engineeringagent.agents import AgentBackendError, AgentBackendFailureDetails
from engineeringagent.loop_runtime import selection


def _pending_features() -> list[tuple[Path, dict[str, Any]]]:
    return [
        (
            Path("docs/spec/features/FEAT-200-third-feature/spec.yaml"),
            {"id": "FEAT-200", "status": "backlog", "priority": "low"},
        ),
        (
            Path("docs/spec/features/FEAT-100-first-feature/spec.yaml"),
            {"id": "FEAT-100", "status": "in_progress", "priority": "high"},
        ),
        (
            Path("docs/spec/features/FEAT-150-second-feature/spec.yaml"),
            {"id": "FEAT-150", "status": "backlog", "priority": "medium"},
        ),
    ]


def _bundled_pending_features() -> list[tuple[Path, dict[str, Any]]]:
    return [
        (
            Path("docs/spec/features/FEAT-320-first-bundle/spec.yaml"),
            {"id": "FEAT-320", "status": "backlog", "priority": "medium"},
        ),
        (
            Path("docs/spec/features/FEAT-321-second-bundle/spec.yaml"),
            {"id": "FEAT-321", "status": "in_progress", "priority": "high"},
        ),
    ]


def test_deterministic_feature_choice_prefers_status_then_priority_then_id() -> None:
    chosen_path, chosen_feature = selection.deterministic_feature_choice(
        _pending_features()
    )

    assert chosen_path == Path("docs/spec/features/FEAT-100-first-feature/spec.yaml")
    assert chosen_feature["id"] == "FEAT-100"


def test_parse_selector_output_matches_full_path_fragment() -> None:
    pending = _pending_features()

    selected = selection.parse_selector_output(
        "pick docs/spec/features/FEAT-150-second-feature/spec.yaml", pending
    )

    assert selected == Path("docs/spec/features/FEAT-150-second-feature/spec.yaml")


def test_parse_selector_output_uses_unique_directory_name_and_id_tokens() -> None:
    pending = _pending_features()

    selected_by_name = selection.parse_selector_output(
        "`FEAT-150-second-feature`", pending
    )
    selected_by_id = selection.parse_selector_output("choose FEAT-300", pending)

    assert selected_by_name == Path("docs/spec/features/FEAT-150-second-feature/spec.yaml")
    assert selected_by_id is None


def test_parse_selector_output_uses_unique_feature_id_tokens() -> None:
    pending = _pending_features()

    selected_by_id = selection.parse_selector_output("choose FEAT-150", pending)

    assert selected_by_id == Path("docs/spec/features/FEAT-150-second-feature/spec.yaml")


def test_parse_selector_output_uses_unique_bundled_package_directory_tokens() -> None:
    pending = _bundled_pending_features()

    selected = selection.parse_selector_output("pick FEAT-321-second-bundle", pending)

    assert selected == Path("docs/spec/features/FEAT-321-second-bundle/spec.yaml")


def test_parse_selector_output_normalizes_multiline_punctuated_tokens() -> None:
    pending = _bundled_pending_features()

    selected = selection.parse_selector_output(
        "pick\n`FEAT-320-first-bundle`, please",
        pending,
    )

    assert selected == Path("docs/spec/features/FEAT-320-first-bundle/spec.yaml")


def test_parse_selector_output_returns_none_for_empty_or_ambiguous_tokens() -> None:
    pending = [
        (Path("docs/spec/features/dup-a/spec.yaml"), {"id": "FEAT-401"}),
        (Path("tmp/dup-b/spec.yaml"), {"id": "FEAT-402"}),
    ]

    assert selection.parse_selector_output("", pending) is None
    assert selection.parse_selector_output("spec.yaml", pending) is None
    assert selection.parse_selector_output("not-a-feature", pending) is None


def test_choose_feature_with_selector_returns_single_pending_without_selector_call() -> (
    None
):
    pending = [(Path("docs/spec/features/solo/spec.yaml"), {"id": "FEAT-999"})]

    def _should_not_run(*_: Any, **__: Any) -> Any:
        raise AssertionError("selector should not run with one candidate")

    chosen_path, chosen_feature = selection.choose_feature_with_selector(
        Path("."),
        pending,
        build_selector_prompt_fn=lambda _pending: "prompt",
        run_agent_fn=_should_not_run,
    )

    assert chosen_path == pending[0][0]
    assert chosen_feature == pending[0][1]


def test_choose_feature_with_selector_uses_selector_output_when_parse_succeeds(
) -> None:
    pending = _pending_features()

    def _run_agent(*_: Any, **__: Any) -> str:
        return "FEAT-150"  # token parsed via feature id

    chosen_path, chosen_feature = selection.choose_feature_with_selector(
        Path("."),
        pending,
        build_selector_prompt_fn=lambda _pending: "prompt",
        run_agent_fn=_run_agent,
    )

    assert chosen_path == Path("docs/spec/features/FEAT-150-second-feature/spec.yaml")
    assert chosen_feature["id"] == "FEAT-150"


def test_choose_feature_with_selector_falls_back_when_opencode_missing(
    tmp_path: Path, capsys: Any
) -> None:
    pending = _pending_features()
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "opencode"\n',
        encoding="utf-8",
    )

    def _run_agent(*_: Any, **__: Any) -> str:
        raise FileNotFoundError("opencode")

    chosen_path, chosen_feature = selection.choose_feature_with_selector(
        tmp_path,
        pending,
        build_selector_prompt_fn=lambda _pending: "prompt",
        run_agent_fn=_run_agent,
    )

    output = capsys.readouterr().out
    assert "Selector step: opencode run --agent engineeringagent" in output
    assert "Selector fallback: agent_missing" in output
    assert chosen_path == Path("docs/spec/features/FEAT-100-first-feature/spec.yaml")
    assert chosen_feature["id"] == "FEAT-100"


def test_choose_feature_with_selector_falls_back_on_parse_or_command_failure(
    tmp_path: Path, capsys: Any
) -> None:
    pending = _pending_features()
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "opencode"\n',
        encoding="utf-8",
    )

    def _run_agent(*_: Any, **__: Any) -> str:
        raise AgentBackendError(
            backend="opencode",
            message="opencode run failed",
            process=AgentBackendFailureDetails(
                returncode=2,
                stdout="",
                stderr="boom",
            ),
        )

    chosen_path, chosen_feature = selection.choose_feature_with_selector(
        tmp_path,
        pending,
        build_selector_prompt_fn=lambda _pending: "prompt",
        run_agent_fn=_run_agent,
    )

    output = capsys.readouterr().out
    assert "Selector step: opencode run --agent engineeringagent" in output
    assert "Selector fallback: opencode_build" in output
    assert chosen_path == Path("docs/spec/features/FEAT-100-first-feature/spec.yaml")
    assert chosen_feature["id"] == "FEAT-100"


def test_choose_feature_with_selector_logs_backend_agnostic_step_label(
    monkeypatch: Any, capsys: Any
) -> None:
    pending = _pending_features()
    monkeypatch.setattr(
        selection,
        "describe_action",
        lambda *_args, **_kwargs: "custom run selector",
        raising=False,
    )

    def _run_agent(*_: Any, **__: Any) -> str:
        raise FileNotFoundError("custom")

    selection.choose_feature_with_selector(
        Path("."),
        pending,
        build_selector_prompt_fn=lambda _pending: "prompt",
        run_agent_fn=_run_agent,
    )

    output = capsys.readouterr().out
    assert "Selector step: custom run selector" in output


def test_choose_feature_with_selector_uses_configured_codex_backend(
    tmp_path: Path,
    capsys: Any,
) -> None:
    pending = _pending_features()
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "codex"\n',
        encoding="utf-8",
    )

    def _run_agent(*_: Any, **__: Any) -> str:
        raise AgentBackendError(
            backend="codex",
            message="codex run failed",
            process=AgentBackendFailureDetails(
                returncode=1,
                stdout="",
                stderr="boom",
            ),
        )

    chosen_path, chosen_feature = selection.choose_feature_with_selector(
        tmp_path,
        pending,
        build_selector_prompt_fn=lambda _pending: "prompt",
        run_agent_fn=_run_agent,
    )

    output = capsys.readouterr().out
    assert "Selector step: codex run selector" in output
    assert "Selector fallback: codex_build" in output
    assert chosen_path == Path("docs/spec/features/FEAT-100-first-feature/spec.yaml")
    assert chosen_feature["id"] == "FEAT-100"
