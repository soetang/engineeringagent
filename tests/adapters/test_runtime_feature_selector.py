from __future__ import annotations

from pathlib import Path
from typing import Any

from engineeringagent.adapters.agents.contracts import (
    AgentBackendError,
    AgentBackendFailureDetails,
)
import engineeringagent.adapters.runtime.feature_selector as selector_module


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


def test_choose_feature_with_selector_returns_single_pending_without_selector_call() -> (
    None
):
    """Skip selector execution when only one candidate exists."""
    pending = [(Path("docs/spec/features/solo/spec.yaml"), {"id": "FEAT-999"})]

    def _should_not_run(*_: Any, **__: Any) -> Any:
        raise AssertionError("selector should not run with one candidate")

    chosen_path, chosen_feature = selector_module.choose_feature_with_selector(
        Path("."),
        pending,
        build_selector_prompt_fn=lambda _pending: "prompt",
        run_agent_fn=_should_not_run,
    )

    assert chosen_path == pending[0][0]
    assert chosen_feature == pending[0][1]


def test_choose_feature_with_selector_uses_selector_output_when_parse_succeeds() -> None:
    """Use selector output when parsing identifies one pending feature."""
    pending = _pending_features()

    def _run_agent(*_: Any, **__: Any) -> str:
        return "FEAT-150"

    chosen_path, chosen_feature = selector_module.choose_feature_with_selector(
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
    """Fall back deterministically when the configured backend is missing."""
    pending = _pending_features()
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "opencode"\n',
        encoding="utf-8",
    )

    def _run_agent(*_: Any, **__: Any) -> str:
        raise FileNotFoundError("opencode")

    chosen_path, chosen_feature = selector_module.choose_feature_with_selector(
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
    """Fall back deterministically when selector execution fails."""
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

    chosen_path, chosen_feature = selector_module.choose_feature_with_selector(
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
    """Log the selector step using the configured action description."""
    pending = _pending_features()
    monkeypatch.setattr(
        selector_module,
        "describe_action",
        lambda *_args, **_kwargs: "custom run selector",
        raising=False,
    )

    def _run_agent(*_: Any, **__: Any) -> str:
        raise FileNotFoundError("custom")

    selector_module.choose_feature_with_selector(
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
    """Use codex-specific selector labels and deterministic fallback on failure."""
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

    chosen_path, chosen_feature = selector_module.choose_feature_with_selector(
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
