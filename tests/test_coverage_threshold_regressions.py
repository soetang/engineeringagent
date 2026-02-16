from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import engineeringagent.config as config_module
import engineeringagent.fitness.adapters as adapters_module
import engineeringagent.loop_runtime.feature_state as feature_state_module
from engineeringagent.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleMetadata,
    RuleAdapter,
    RuleSeverity,
    RuleSource,
)
from engineeringagent.fitness.registry import FitnessRuleDefinition
from engineeringagent.loop_runtime.models import FeatureIterationInputs
from engineeringagent.loop_runtime.phases import (
    CompletionPhaseDependencies,
    GatePhaseDependencies,
    VerificationPhaseDependencies,
    run_completion_commit_phase,
    run_gate_phase,
    run_verification_phase,
)
from engineeringagent.loop_runtime.presentation import (
    RunOutputPresenter,
    tty_supports_ansi,
)


def _command_definition(
    command: tuple[str, ...] | None,
    *,
    env: dict[str, str] | None = None,
    adapter: RuleAdapter = RuleAdapter.COMMAND,
) -> FitnessRuleDefinition:
    return FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id="custom.coverage-regression",
            name="Coverage regression",
            summary="Regression helper rule.",
            rationale="Exercise adapter edge paths.",
            remediation="Fix the adapter payload.",
            scope="tests",
            severity=RuleSeverity.WARNING,
            adapter=adapter,
            source=RuleSource.CUSTOM,
            side_effect_free=True,
        ),
        origin="custom:tests",
        command=command,
        env=env,
        timeout_seconds=1,
    )


def test_config_rejects_invalid_docs_root_values() -> None:
    with pytest.raises(ValueError, match="expected string"):
        config_module._normalize_docs_root(123, source_path=Path("pyproject.toml"))
    with pytest.raises(ValueError, match="cannot be empty"):
        config_module._normalize_docs_root(" ", source_path=Path("pyproject.toml"))
    with pytest.raises(ValueError, match="must be relative"):
        config_module._normalize_docs_root(
            "/tmp/docs", source_path=Path("pyproject.toml")
        )
    with pytest.raises(ValueError, match="cannot contain '..'"):
        config_module._normalize_docs_root(
            "docs/../other", source_path=Path("pyproject.toml")
        )
    with pytest.raises(ValueError, match="cannot be '\\.'"):
        config_module._normalize_docs_root(".", source_path=Path("pyproject.toml"))


def test_config_load_toml_surfaces_parse_error(tmp_path: Path) -> None:
    config_path = tmp_path / "engineeringagent.toml"
    config_path.write_text("docs-root = [", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid TOML"):
        config_module._docs_root_from_engineeringagent_toml(config_path)


def test_config_pyproject_missing_tool_sections_returns_none(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[build-system]\nrequires = []\n", encoding="utf-8")
    assert config_module._docs_root_from_pyproject_toml(pyproject) is None

    pyproject.write_text("tool = 'not-a-table'\n", encoding="utf-8")
    assert config_module._docs_root_from_pyproject_toml(pyproject) is None

    pyproject.write_text("[tool]\nengineeringagent = 'not-a-table'\n", encoding="utf-8")
    assert config_module._docs_root_from_pyproject_toml(pyproject) is None


def test_presentation_handles_tty_edge_cases() -> None:
    class _NoIsAtty:
        pass

    class _FailingIsAtty:
        def isatty(self) -> bool:
            raise RuntimeError("boom")

    assert (
        tty_supports_ansi(stdout=cast(Any, _NoIsAtty()), env={"TERM": "xterm"}) is False
    )
    assert (
        tty_supports_ansi(stdout=cast(Any, _FailingIsAtty()), env={"TERM": "xterm"})
        is False
    )


def test_presentation_formats_all_result_paths() -> None:
    presenter = RunOutputPresenter(use_ansi=True)
    assert "[failed]" in presenter.format_summary_suffix("failed")
    assert "[retry]" in presenter.format_summary_suffix("retry")
    assert "Failed gate:" in presenter.format_failed_gate_line("spec_validate")
    assert "gate=unknown" in presenter.format_iteration_failed_line(None)


def test_presentation_disables_ansi_for_dumb_terminal() -> None:
    class _Tty:
        def isatty(self) -> bool:
            return True

    assert tty_supports_ansi(stdout=cast(Any, _Tty()), env={"TERM": "dumb"}) is False


def test_feature_state_error_paths(tmp_path: Path, monkeypatch: Any) -> None:
    with pytest.raises(ValueError, match="unknown status"):
        feature_state_module.set_status({}, "in_progress")

    with pytest.raises(ValueError, match="illegal feature status transition"):
        feature_state_module.set_status({"status": "done"}, "in_progress")

    with pytest.raises(ValueError, match="at least one feature"):
        feature_state_module._resolve_feature_paths(tmp_path, [])

    txt_path = tmp_path / "feature.txt"
    txt_path.write_text("id: FEAT-001\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must end with .yaml"):
        feature_state_module._resolve_feature_paths(tmp_path, [txt_path])

    directory_path = tmp_path / "feature.yaml"
    directory_path.mkdir()
    with pytest.raises(ValueError, match="is not a file"):
        feature_state_module._resolve_feature_paths(tmp_path, [directory_path])

    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("[", encoding="utf-8")
    with pytest.raises(ValueError, match="failed to load feature YAML"):
        feature_state_module._resolve_feature_paths(tmp_path, [bad_yaml])

    good_yaml = tmp_path / "good.yaml"
    good_yaml.write_text("id: FEAT-001\nstatus: backlog\n", encoding="utf-8")
    resolved = feature_state_module._resolve_feature_paths(
        tmp_path,
        [Path("good.yaml"), good_yaml],
    )
    assert resolved == [good_yaml.resolve()]

    features_dir = tmp_path / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True)
    (features_dir / "broken.yaml").write_text("[", encoding="utf-8")
    with pytest.raises(ValueError, match="failed to load feature YAML"):
        feature_state_module._discover_active_feature_paths(tmp_path)

    with pytest.raises(ValueError, match="must be under docs/spec/features"):
        feature_state_module._resolve_archive_path(tmp_path, bad_yaml)

    missing_outside = tmp_path / "missing.yaml"
    loaded, from_archive, error = (
        feature_state_module._load_selected_feature_with_archive_fallback(
            tmp_path,
            missing_outside,
        )
    )
    assert loaded is None
    assert from_archive is False
    assert "cannot be archive-resolved" in str(error)

    active_feature_path = features_dir / "FEAT-002.yaml"
    done_dir = tmp_path / "docs" / "spec" / "features_done"
    done_dir.mkdir(parents=True)
    (done_dir / active_feature_path.name).write_text("[", encoding="utf-8")
    loaded, from_archive, error = (
        feature_state_module._load_selected_feature_with_archive_fallback(
            tmp_path,
            active_feature_path,
        )
    )
    assert loaded is None
    assert from_archive is False
    assert "failed to load archived feature YAML" in str(error)

    assert (
        "missing-message"
        in feature_state_module._archived_feature_mismatch_feedback(
            None,
            active_feature_path,
            missing_message="missing-message",
            done_message="done-message",
        )
    )
    assert (
        "archived status is not done"
        in feature_state_module._archived_feature_mismatch_feedback(
            {"status": "blocked"},
            active_feature_path,
            missing_message="missing-message",
            done_message="done-message",
        )
    )

    monkeypatch.setattr(
        feature_state_module,
        "_load_selected_feature_with_archive_fallback",
        lambda *_args, **_kwargs: ({"status": "done"}, True, None),
    )
    monkeypatch.setattr(
        feature_state_module,
        "_resolve_archive_path",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("cannot resolve")),
    )
    post_outcome = feature_state_module._refresh_feature_after_implement(
        tmp_path,
        active_feature_path,
        selected_started_active=True,
    )
    assert post_outcome.result == "failed"
    assert post_outcome.failed_gate == "feature_archive"

    monkeypatch.setattr(
        feature_state_module,
        "_load_selected_feature_with_archive_fallback",
        lambda *_args, **_kwargs: ({"status": "blocked"}, True, None),
    )
    post_outcome = feature_state_module._refresh_feature_after_implement(
        tmp_path,
        active_feature_path,
        selected_started_active=True,
    )
    assert post_outcome.result == "failed"
    assert post_outcome.failed_gate == "feature_missing"

    monkeypatch.setattr(
        feature_state_module,
        "_resolve_archive_path",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad archive")),
    )
    ok, archived_path, message = feature_state_module._archive_completed_feature(
        tmp_path,
        active_feature_path,
    )
    assert ok is False
    assert archived_path is None
    assert message == "bad archive"

    existing_archive = done_dir / "exists.yaml"
    existing_archive.write_text("id: FEAT-009\n", encoding="utf-8")
    missing_feature = features_dir / "exists.yaml"
    monkeypatch.setattr(
        feature_state_module,
        "_resolve_archive_path",
        lambda *_args, **_kwargs: existing_archive,
    )
    ok, archived_path, message = feature_state_module._archive_completed_feature(
        tmp_path,
        missing_feature,
    )
    assert ok is False
    assert archived_path is None
    assert "not found" in message

    source_feature = features_dir / "FEAT-010.yaml"
    source_feature.write_text("id: FEAT-010\n", encoding="utf-8")
    ok, archived_path, message = feature_state_module._archive_completed_feature(
        tmp_path,
        source_feature,
    )
    assert ok is False
    assert archived_path is None
    assert "already exists" in message

    ok, message = feature_state_module._restore_archived_feature(
        tmp_path / "not-there.yaml",
        features_dir / "target.yaml",
    )
    assert (ok, message) == (True, "")

    archived = done_dir / "restore.yaml"
    original = features_dir / "restore.yaml"
    archived.write_text("id: FEAT-011\n", encoding="utf-8")
    original.write_text("id: FEAT-011\n", encoding="utf-8")
    ok, message = feature_state_module._restore_archived_feature(archived, original)
    assert ok is False
    assert "source already exists" in message


def test_gate_and_verification_phase_error_paths(capsys: Any) -> None:
    inputs = FeatureIterationInputs(
        project_root=Path("."),
        feature_path=Path("docs/spec/features/FEAT-001.yaml"),
        gate_profile="loop_fast",
        skip_implement=False,
        attempt=1,
        hook_feedback=None,
        verbose_output=True,
    )

    gate_deps = GatePhaseDependencies(
        load_gate_config=lambda _path: {"profiles": {"loop_fast": ["x"]}},
        run_profile=lambda *_args, **_kwargs: (False, "spec_validate", "gate output"),
        restore_archived_feature=lambda *_args: (False, "rollback-failed"),
    )
    gate_outcome = run_gate_phase(
        inputs,
        Path("harness/gates.yaml"),
        archived_in_iteration=True,
        archived_path=Path("docs/spec/features_done/FEAT-001.yaml"),
        dependencies=gate_deps,
    )
    assert gate_outcome.result == "failed"
    assert "archive rollback failed: rollback-failed" in gate_outcome.gate_output

    commands = ["cmd-ok"]
    verification_deps = VerificationPhaseDependencies(
        run_shell_command=lambda *_args: SimpleNamespace(
            returncode=0,
            stdout="ok-out\n",
            stderr="warn-err\n",
        )
    )
    verification_outcome = run_verification_phase(inputs, commands, verification_deps)
    assert verification_outcome.result == "passed"
    captured = capsys.readouterr()
    assert "ok-out" in captured.out
    assert "warn-err" in captured.err


def test_completion_phase_fallback_paths() -> None:
    inputs = FeatureIterationInputs(
        project_root=Path("."),
        feature_path=Path("docs/spec/features/FEAT-001.yaml"),
        gate_profile="loop_fast",
        skip_implement=False,
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )

    deps = CompletionPhaseDependencies(
        commit_feature_completion=lambda *_args: (False, "commit", "commit failed"),
        restore_archived_feature=lambda *_args: (False, "restore failed"),
    )
    passthrough = run_completion_commit_phase(
        inputs,
        post_feature={"id": "FEAT-001"},
        archived_in_iteration=False,
        archived_path=None,
        dependencies=deps,
    )
    assert passthrough.result == "passed"
    assert passthrough.completed is False

    missing = run_completion_commit_phase(
        inputs,
        post_feature=None,
        archived_in_iteration=True,
        archived_path=Path("docs/spec/features_done/FEAT-001.yaml"),
        dependencies=deps,
    )
    assert missing.result == "failed"
    assert missing.failed_gate == "feature_archive"

    commit_failed = run_completion_commit_phase(
        inputs,
        post_feature={"id": "FEAT-001"},
        archived_in_iteration=True,
        archived_path=Path("docs/spec/features_done/FEAT-001.yaml"),
        dependencies=deps,
    )
    assert commit_failed.result == "failed"
    assert "archive rollback failed: restore failed" in str(commit_failed.hook_feedback)


def test_command_adapter_error_paths(monkeypatch: Any, tmp_path: Path) -> None:
    definition = _command_definition(("python", "-c", "print('ok')"), env={"X": "1"})

    def _timeout(*_args: Any, **_kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd="cmd", timeout=1)

    monkeypatch.setattr(adapters_module.subprocess, "run", _timeout)
    with pytest.raises(ValueError, match="command timed out"):
        adapters_module._run_command_adapter(definition, tmp_path)

    monkeypatch.setattr(
        adapters_module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="stderr message",
        ),
    )
    with pytest.raises(ValueError, match="non-zero"):
        adapters_module._run_command_adapter(definition, tmp_path)

    monkeypatch.setattr(
        adapters_module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    with pytest.raises(ValueError, match="empty stdout"):
        adapters_module._run_command_adapter(definition, tmp_path)

    monkeypatch.setattr(
        adapters_module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="not-json",
            stderr="",
        ),
    )
    with pytest.raises(ValueError, match="not valid JSON"):
        adapters_module._run_command_adapter(definition, tmp_path)

    monkeypatch.setattr(
        adapters_module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="[]",
            stderr="",
        ),
    )
    with pytest.raises(ValueError, match="must be a JSON object"):
        adapters_module._run_command_adapter(definition, tmp_path)

    env_seen: dict[str, str] = {}

    def _ok(*_args: Any, **kwargs: Any) -> Any:
        env_seen.update(kwargs["env"])
        return SimpleNamespace(
            returncode=0,
            stdout=(
                '{"contract_version":"%s","rule_id":"custom.coverage-regression",'
                '"status":"pass","severity":"warning","summary":"ok","violations":[]}'
            )
            % CONTRACT_VERSION,
            stderr="",
        )

    monkeypatch.setattr(adapters_module.subprocess, "run", _ok)
    payload = adapters_module._run_command_adapter(definition, tmp_path)
    assert payload["rule_id"] == "custom.coverage-regression"
    assert env_seen["X"] == "1"


def test_adapter_normalization_and_dispatch_error_paths(
    tmp_path: Path, monkeypatch: Any
) -> None:
    with pytest.raises(ValueError, match="requires a non-empty command"):
        adapters_module._run_command_adapter(_command_definition(None), tmp_path)

    python_definition = _command_definition(command=None, adapter=RuleAdapter.PYTHON)
    with pytest.raises(ValueError, match="requires python_callable"):
        adapters_module._run_python_adapter(python_definition, tmp_path)

    normalized_definition = _command_definition(command=("python",))
    with pytest.raises(ValueError, match="rule_id does not match"):
        adapters_module._normalize_result(
            normalized_definition,
            {
                "contract_version": CONTRACT_VERSION,
                "rule_id": "other.rule",
                "status": "pass",
                "severity": "warning",
                "summary": "ok",
                "violations": [],
            },
        )
    with pytest.raises(ValueError, match="severity does not match"):
        adapters_module._normalize_result(
            normalized_definition,
            {
                "contract_version": CONTRACT_VERSION,
                "rule_id": "custom.coverage-regression",
                "status": "pass",
                "severity": "error",
                "summary": "ok",
                "violations": [],
            },
        )

    class _UnsupportedAdapter:
        value = "unsupported"

    unsupported = SimpleNamespace(
        metadata=SimpleNamespace(adapter=_UnsupportedAdapter()),
    )
    with pytest.raises(ValueError, match="unsupported rule adapter"):
        adapters_module._adapter_payload(cast(Any, unsupported), tmp_path)

    monkeypatch.setattr(
        adapters_module,
        "_adapter_payload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    error_result = adapters_module.execute_rule_definition(
        normalized_definition,
        tmp_path,
    )
    assert error_result.status.value == "error"
    assert "Adapter execution failed" in error_result.summary
