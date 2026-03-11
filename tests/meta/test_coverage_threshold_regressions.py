from __future__ import annotations

# Tests intentionally exercise private helper functions.
# pylint: disable=protected-access

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import ValidationError

import engineeringagent.config as config_module
import engineeringagent.checks.fitness.adapters as adapters_module
from engineeringagent.loop_runtime import feature_plan_state
import engineeringagent.loop_runtime.feature_state as feature_state_module
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleMetadata,
    RuleAdapter,
    RuleSeverity,
    RuleSource,
)
from engineeringagent.checks.fitness.registry import FitnessRuleDefinition
from engineeringagent.loop_runtime.models import FeatureIterationInputs
from engineeringagent.checks.changed_paths import ChangedPathsResult
from engineeringagent.loop_runtime.phases import (
    CompletionPhaseDependencies,
    GatePhaseDependencies,
    run_completion_commit_phase,
    run_gate_phase,
    run_verification_phase,
)
from engineeringagent.presentation.presenters.terminal import (
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
            """Simulate a broken isatty implementation."""
            raise RuntimeError("boom")

    assert tty_supports_ansi(stdout=cast(Any, _NoIsAtty())) is False
    assert tty_supports_ansi(stdout=cast(Any, _FailingIsAtty())) is False


def test_presentation_formats_all_result_paths() -> None:
    presenter = RunOutputPresenter(use_ansi=True)
    assert "[failed]" in presenter.format_summary_suffix("failed")
    assert "[retry]" in presenter.format_summary_suffix("retry")
    assert "Failed gate:" in presenter.format_failed_gate_line("spec_validate")
    assert "gate=unknown" in presenter.format_iteration_failed_line(None)


def test_presentation_ignores_env_keys_for_ansi_decision(
    monkeypatch: Any,
) -> None:
    class _Tty:
        def isatty(self) -> bool:
            """Pretend stdout is a TTY."""
            return True

    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "dumb")

    assert tty_supports_ansi(stdout=cast(Any, _Tty())) is True


def test_feature_state_plan_loader_compatibility_shim() -> None:
    assert (
        feature_state_module._load_plan_document_and_frontmatter
        is feature_plan_state.load_plan_document_and_frontmatter
    )


def test_feature_plan_progress_update_config_uses_pydantic_model_boundary() -> None:
    config = feature_plan_state._PlanProgressUpdateConfig(
        allow_done_feature=False,
        feature_transitions={"in_progress": {"done"}},
        mutate_frontmatter=lambda _frontmatter: False,
    )

    assert hasattr(config, "model_dump")
    with pytest.raises(ValidationError, match="frozen"):
        config.allow_done_feature = True


def test_feature_state_error_paths(tmp_path: Path, monkeypatch: Any) -> None:
    with pytest.raises(ValueError, match="unknown status"):
        feature_state_module.set_status({}, "in_progress")

    with pytest.raises(ValueError, match="illegal feature status transition"):
        feature_state_module.set_status({"status": "done"}, "in_progress")

    with pytest.raises(ValueError, match="at least one feature"):
        feature_state_module.resolve_feature_paths(tmp_path, [])

    txt_path = tmp_path / "feature.txt"
    txt_path.write_text("id: FEAT-001\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must end with .yaml"):
        feature_state_module.resolve_feature_paths(tmp_path, [txt_path])

    directory_path = tmp_path / "feature.yaml"
    directory_path.mkdir()
    with pytest.raises(ValueError, match="is not a file"):
        feature_state_module.resolve_feature_paths(tmp_path, [directory_path])

    flat_yaml = tmp_path / "flat.yaml"
    flat_yaml.write_text("id: FEAT-001\nstatus: backlog\n", encoding="utf-8")
    with pytest.raises(
        ValueError, match="feature specs must use bundled spec.yaml entrypoints"
    ):
        feature_state_module.resolve_feature_paths(tmp_path, [flat_yaml])

    bad_yaml_root = tmp_path / "docs" / "spec" / "features" / "FEAT-000-bad"
    bad_yaml_root.mkdir(parents=True)
    bad_yaml = bad_yaml_root / "spec.yaml"
    bad_yaml.write_text("[", encoding="utf-8")
    with pytest.raises(ValueError, match="failed to load feature YAML"):
        feature_state_module.resolve_feature_paths(tmp_path, [bad_yaml])

    bundled_root = tmp_path / "docs" / "spec" / "features" / "FEAT-001-good"
    bundled_root.mkdir(parents=True)
    good_yaml = bundled_root / "spec.yaml"
    good_yaml.write_text("id: FEAT-001\nstatus: backlog\n", encoding="utf-8")
    resolved = feature_state_module.resolve_feature_paths(
        tmp_path,
        [good_yaml.relative_to(tmp_path), good_yaml],
    )
    assert resolved == [good_yaml.resolve()]

    features_dir = tmp_path / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)
    (features_dir / "broken.yaml").write_text("[", encoding="utf-8")
    with pytest.raises(ValueError, match="failed to load feature YAML"):
        feature_state_module.discover_active_feature_paths(tmp_path)

    outside_bundle = tmp_path / "elsewhere" / "FEAT-999-outside" / "spec.yaml"
    outside_bundle.parent.mkdir(parents=True)
    outside_bundle.write_text("id: FEAT-999\nstatus: backlog\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be under docs/spec/features"):
        feature_state_module._resolve_archive_path(tmp_path, outside_bundle)

    missing_outside = tmp_path / "missing.yaml"
    loaded, error = feature_state_module._load_selected_feature(missing_outside)
    assert loaded is None
    assert "disappeared during loop iteration" in str(error)

    active_root = features_dir / "FEAT-002-broken"
    active_root.mkdir(parents=True, exist_ok=True)
    active_feature_path = active_root / "spec.yaml"
    done_dir = tmp_path / "docs" / "spec" / "features_done"
    done_dir.mkdir(parents=True)
    active_feature_path.write_text("[", encoding="utf-8")
    loaded, error = feature_state_module._load_selected_feature(active_feature_path)
    assert loaded is None
    assert "failed to load selected feature YAML" in str(error)

    active_feature_path.write_text("id: FEAT-002\nstatus: done\n", encoding="utf-8")
    loaded, error = feature_state_module._load_selected_feature(active_feature_path)
    assert loaded is not None
    assert error is None

    monkeypatch.setattr(
        feature_state_module,
        "_load_selected_feature",
        lambda *_args, **_kwargs: (None, "load-failed"),
    )
    post_outcome = feature_state_module.refresh_feature_after_implement(
        tmp_path,
        active_feature_path,
    )
    assert post_outcome.result == "failed"
    assert post_outcome.failed_gate == "feature_missing"
    assert post_outcome.feedback == "load-failed"

    monkeypatch.setattr(
        feature_state_module,
        "_load_selected_feature",
        lambda *_args, **_kwargs: ({"status": "blocked"}, None),
    )
    post_outcome = feature_state_module.refresh_feature_after_implement(
        tmp_path,
        active_feature_path,
    )
    assert post_outcome.result == "passed"
    assert post_outcome.failed_gate is None

    monkeypatch.setattr(
        "engineeringagent.loop_runtime.feature_state.resolve_feature_package_paths",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad archive")),
    )
    ok, archived_path, message = feature_state_module.archive_completed_feature(
        tmp_path,
        active_feature_path,
    )
    assert ok is False
    assert archived_path is None
    assert message == "bad archive"

    existing_archive = done_dir / "exists" / "spec.yaml"
    existing_archive.parent.mkdir(parents=True, exist_ok=True)
    existing_archive.write_text("id: FEAT-009\n", encoding="utf-8")
    missing_feature = features_dir / "exists" / "spec.yaml"
    monkeypatch.setattr(
        "engineeringagent.loop_runtime.feature_state.resolve_feature_package_paths",
        lambda *_args, **_kwargs: SimpleNamespace(
            active_root=missing_feature.parent,
            active_spec_path=missing_feature,
            archive_root=existing_archive.parent,
            archive_spec_path=existing_archive,
        ),
    )
    ok, archived_path, message = feature_state_module.archive_completed_feature(
        tmp_path,
        missing_feature,
    )
    assert ok is False
    assert archived_path is None
    assert "not found" in message

    source_feature = features_dir / "FEAT-010" / "spec.yaml"
    source_feature.parent.mkdir(parents=True, exist_ok=True)
    source_feature.write_text("id: FEAT-010\n", encoding="utf-8")
    ok, archived_path, message = feature_state_module.archive_completed_feature(
        tmp_path,
        source_feature,
    )
    assert ok is False
    assert archived_path is None
    assert "already exists" in message

    ok, message = feature_state_module.restore_archived_feature(
        tmp_path / "not-there" / "spec.yaml",
        features_dir / "target" / "spec.yaml",
    )
    assert (ok, message) == (True, "")

    archived = done_dir / "restore" / "spec.yaml"
    original = features_dir / "restore" / "spec.yaml"
    archived.parent.mkdir(parents=True, exist_ok=True)
    original.parent.mkdir(parents=True, exist_ok=True)
    archived.write_text("id: FEAT-011\n", encoding="utf-8")
    original.write_text("id: FEAT-011\n", encoding="utf-8")
    ok, message = feature_state_module.restore_archived_feature(archived, original)
    assert ok is False
    assert "source already exists" in message


def test_touch_active_feature_for_iteration_promotes_bundled_plan_phase_statuses(
    tmp_path: Path,
) -> None:
    feature_root = tmp_path / "docs" / "spec" / "features" / "FEAT-330-bundled-touch"
    feature_root.mkdir(parents=True)
    feature_path = feature_root / "spec.yaml"
    feature_path.write_text(
        "\n".join(
            [
                "id: FEAT-330",
                "title: Promote bundled plan phase statuses",
                "type: feature",
                "expected_commit_subject: 'feat: promote bundled plan phase statuses'",
                "planning_tier: planned",
                "status: backlog",
                "priority: high",
                "objective: Promote plan progress into in_progress state.",
                "acceptance:",
                "  - Ensure iteration touch updates plan phase status metadata.",
                "artifacts:",
                "  plan: plan.md",
                "updated_at: '2026-03-09T00:00:00Z'",
                "",
            ]
        ),
        encoding="utf-8",
    )
    plan_path = feature_root / "plan.md"
    plan_path.write_text(
        "\n".join(
            [
                "---",
                "plan_id: FEAT-330",
                "feature_id: FEAT-330",
                "status: pending",
                "source_spec: spec.yaml",
                "planning_tier: planned",
                "phases:",
                "  - id: P1",
                "    title: Finish prior work",
                "    status: done",
                "  - id: P2",
                "    title: Start next bundled phase",
                "    status: pending",
                "    verification:",
                "      - uv run pytest -q tests/test_bundled_phase_touch.py",
                "---",
                "",
                "# FEAT-330 Plan",
                "",
            ]
        ),
        encoding="utf-8",
    )

    feature = feature_state_module.load_yaml(feature_path)
    feature_state_module.touch_active_feature_for_iteration(feature, feature_path)

    refreshed_feature = feature_state_module.load_yaml(feature_path)
    assert refreshed_feature["status"] == "in_progress"
    assert refreshed_feature["updated_at"] != "2026-03-09T00:00:00Z"

    loaded_plan = feature_state_module._load_plan_document_and_frontmatter(plan_path)
    assert loaded_plan is not None
    _, frontmatter = loaded_plan
    assert frontmatter["status"] == "in_progress"
    phases = frontmatter["phases"]
    assert phases[0]["status"] == "done"
    assert phases[1]["status"] == "in_progress"


def test_touch_active_feature_for_iteration_preserves_blocked_bundled_plan_phase(
    tmp_path: Path,
) -> None:
    feature_root = tmp_path / "docs" / "spec" / "features" / "FEAT-331-bundled-touch"
    feature_root.mkdir(parents=True)
    feature_path = feature_root / "spec.yaml"
    feature_path.write_text(
        "\n".join(
            [
                "id: FEAT-331",
                "title: Preserve blocked bundled plan phase statuses",
                "type: feature",
                "expected_commit_subject: 'feat: preserve blocked bundled plan phase statuses'",
                "planning_tier: planned",
                "status: blocked",
                "priority: high",
                "objective: Keep blocked phase state stable during iteration touch.",
                "acceptance:",
                "  - Ensure iteration touch does not overwrite blocked plan phase metadata.",
                "artifacts:",
                "  plan: plan.md",
                "updated_at: '2026-03-09T00:00:00Z'",
                "",
            ]
        ),
        encoding="utf-8",
    )
    plan_path = feature_root / "plan.md"
    plan_path.write_text(
        "\n".join(
            [
                "---",
                "plan_id: FEAT-331",
                "feature_id: FEAT-331",
                "status: pending",
                "source_spec: spec.yaml",
                "planning_tier: planned",
                "phases:",
                "  - id: P1",
                "    title: Blocked bundled phase",
                "    status: blocked",
                "  - id: P2",
                "    title: Later bundled phase",
                "    status: pending",
                "---",
                "",
                "# FEAT-331 Plan",
                "",
            ]
        ),
        encoding="utf-8",
    )

    feature = feature_state_module.load_yaml(feature_path)
    feature_state_module.touch_active_feature_for_iteration(feature, feature_path)

    refreshed_feature = feature_state_module.load_yaml(feature_path)
    assert refreshed_feature["status"] == "blocked"
    assert refreshed_feature["updated_at"] != "2026-03-09T00:00:00Z"

    loaded_plan = feature_state_module._load_plan_document_and_frontmatter(plan_path)
    assert loaded_plan is not None
    _, frontmatter = loaded_plan
    assert frontmatter["status"] == "blocked"
    phases = frontmatter["phases"]
    assert phases[0]["status"] == "blocked"
    assert phases[1]["status"] == "pending"


def test_touch_active_feature_for_iteration_syncs_feature_status_from_blocked_plan(
    tmp_path: Path,
) -> None:
    feature_root = tmp_path / "docs" / "spec" / "features" / "FEAT-332-bundled-touch"
    feature_root.mkdir(parents=True)
    feature_path = feature_root / "spec.yaml"
    feature_path.write_text(
        "\n".join(
            [
                "id: FEAT-332",
                "title: Sync feature status from blocked bundled plan",
                "type: feature",
                "expected_commit_subject: 'feat: sync feature status from blocked bundled plan'",
                "planning_tier: planned",
                "status: in_progress",
                "priority: high",
                "objective: Keep spec status aligned with blocked plan phases during iteration touch.",
                "acceptance:",
                "  - Ensure iteration touch syncs spec status from blocked bundled plan metadata.",
                "artifacts:",
                "  plan: plan.md",
                "updated_at: '2026-03-09T00:00:00Z'",
                "",
            ]
        ),
        encoding="utf-8",
    )
    plan_path = feature_root / "plan.md"
    plan_path.write_text(
        "\n".join(
            [
                "---",
                "plan_id: FEAT-332",
                "feature_id: FEAT-332",
                "status: pending",
                "source_spec: spec.yaml",
                "planning_tier: planned",
                "phases:",
                "  - id: P1",
                "    title: Blocked bundled phase",
                "    status: blocked",
                "  - id: P2",
                "    title: Later bundled phase",
                "    status: pending",
                "---",
                "",
                "# FEAT-332 Plan",
                "",
            ]
        ),
        encoding="utf-8",
    )

    feature = feature_state_module.load_yaml(feature_path)
    feature_state_module.touch_active_feature_for_iteration(feature, feature_path)

    refreshed_feature = feature_state_module.load_yaml(feature_path)
    assert refreshed_feature["status"] == "blocked"
    assert refreshed_feature["updated_at"] != "2026-03-09T00:00:00Z"

    loaded_plan = feature_state_module._load_plan_document_and_frontmatter(plan_path)
    assert loaded_plan is not None
    _, frontmatter = loaded_plan
    assert frontmatter["status"] == "blocked"
    phases = frontmatter["phases"]
    assert phases[0]["status"] == "blocked"
    assert phases[1]["status"] == "pending"


def _setup_archived_selected_counterpart(
    tmp_path: Path,
    *,
    feature_dir_name: str,
    archived_lines: list[str] | None = None,
) -> tuple[Path, Path]:
    features_dir = tmp_path / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True)
    archived_dir = tmp_path / "docs" / "spec" / "features_done"
    archived_dir.mkdir(parents=True)

    active_feature_path = features_dir / feature_dir_name / "spec.yaml"
    archived_feature_path = archived_dir / feature_dir_name / "spec.yaml"
    archived_feature_path.parent.mkdir(parents=True, exist_ok=True)
    archived_feature_path.write_text(
        "\n".join([*(archived_lines or []), ""]),
        encoding="utf-8",
    )
    return active_feature_path, archived_feature_path


def _write_bundled_feature_package(
    package_dir: Path,
    *,
    status: str,
    extra_files: dict[str, str] | None = None,
) -> Path:
    package_dir.mkdir(parents=True, exist_ok=True)
    spec_path = package_dir / "spec.yaml"
    feature_prefix, feature_number, *_rest = package_dir.name.split("-", 2)
    spec_path.write_text(
        "\n".join(
            [
                f"id: {feature_prefix}-{feature_number}",
                f"status: {status}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    for relative_path, contents in (extra_files or {}).items():
        target = package_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")
    return spec_path


def test_feature_state_supports_bundled_package_discovery_and_archive_flow(
    tmp_path: Path,
) -> None:
    features_dir = tmp_path / "docs" / "spec" / "features"
    active_spec = _write_bundled_feature_package(
        features_dir / "FEAT-320-active-bundle",
        status="backlog",
    )
    done_spec = _write_bundled_feature_package(
        features_dir / "FEAT-321-done-bundle",
        status="done",
        extra_files={"plan.md": "# plan\n"},
    )

    active_paths = feature_state_module.discover_active_feature_paths(tmp_path)
    assert active_paths == [active_spec]

    ok, archived_path, message = feature_state_module.archive_completed_feature(
        tmp_path,
        done_spec,
    )

    assert (ok, message) == (True, "")
    assert archived_path == (
        tmp_path
        / "docs"
        / "spec"
        / "features_done"
        / "FEAT-321-done-bundle"
        / "spec.yaml"
    )
    assert archived_path is not None
    assert archived_path.exists()
    assert (archived_path.parent / "plan.md").exists()
    assert done_spec.exists() is False


def test_feature_state_refresh_and_restore_support_bundled_archives(
    tmp_path: Path,
) -> None:
    features_dir = tmp_path / "docs" / "spec" / "features"
    active_spec = features_dir / "FEAT-322-refresh-bundle" / "spec.yaml"
    archived_spec = _write_bundled_feature_package(
        tmp_path / "docs" / "spec" / "features_done" / "FEAT-322-refresh-bundle",
        status="done",
        extra_files={"plan.md": "# archived plan\n"},
    )

    post_outcome = feature_state_module.refresh_feature_after_implement(
        tmp_path,
        active_spec,
    )

    assert post_outcome.result == "passed"
    assert post_outcome.archived_in_iteration is True
    assert post_outcome.archived_path == archived_spec

    ok, message = feature_state_module.restore_archived_feature(
        archived_spec,
        active_spec,
    )

    assert (ok, message) == (True, "")
    assert active_spec.exists()
    assert (active_spec.parent / "plan.md").exists()
    assert archived_spec.exists() is False


def test_post_implement_refresh_rejects_archived_bundles_with_open_plan_phases(
    tmp_path: Path,
) -> None:
    features_dir = tmp_path / "docs" / "spec" / "features"
    active_spec = features_dir / "FEAT-323-refresh-bundle" / "spec.yaml"
    archived_root = (
        tmp_path / "docs" / "spec" / "features_done" / "FEAT-323-refresh-bundle"
    )
    archived_spec = archived_root / "spec.yaml"
    archived_root.mkdir(parents=True, exist_ok=True)
    archived_spec.write_text(
        "\n".join(
            [
                "id: FEAT-323",
                "status: done",
                "planning_tier: planned",
                "artifacts:",
                "  plan: plan.md",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (archived_root / "plan.md").write_text(
        "\n".join(
            [
                "---",
                "plan_id: FEAT-323",
                "feature_id: FEAT-323",
                "status: in_progress",
                "source_spec: spec.yaml",
                "planning_tier: planned",
                "phases:",
                "  - id: P1",
                "    title: Archived bundle still has an open phase",
                "    status: pending",
                "---",
                "",
                "# Plan",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    post_outcome = feature_state_module.refresh_feature_after_implement(
        tmp_path,
        active_spec,
    )

    assert post_outcome.result == "failed"
    assert post_outcome.failed_gate == "feature_missing"
    assert post_outcome.archived_in_iteration is False
    assert post_outcome.archived_path is None
    assert archived_spec.exists()


def test_post_implement_refresh_recovers_selected_archived_done_feature(
    tmp_path: Path,
) -> None:
    active_feature_path, archived_feature_path = _setup_archived_selected_counterpart(
        tmp_path,
        feature_dir_name="FEAT-200-archived",
        archived_lines=[
            "id: FEAT-200",
            "status: done",
        ],
    )

    post_outcome = feature_state_module.refresh_feature_after_implement(
        tmp_path,
        active_feature_path,
    )

    assert post_outcome.result == "passed"
    assert post_outcome.failed_gate is None
    assert post_outcome.archived_in_iteration is True
    assert post_outcome.archived_path == archived_feature_path
    assert post_outcome.feature is not None
    assert post_outcome.feature.get("status") == "done"


def test_post_implement_refresh_rejects_non_done_archived_counterpart(
    tmp_path: Path,
) -> None:
    active_feature_path, _archived_feature_path = _setup_archived_selected_counterpart(
        tmp_path,
        feature_dir_name="FEAT-201-archived",
        archived_lines=[
            "id: FEAT-201",
            "status: in_progress",
        ],
    )

    post_outcome = feature_state_module.refresh_feature_after_implement(
        tmp_path,
        active_feature_path,
    )

    assert post_outcome.result == "failed"
    assert post_outcome.failed_gate == "feature_missing"
    assert post_outcome.archived_in_iteration is False
    assert post_outcome.archived_path is None


def test_post_implement_refresh_does_not_fallback_to_non_matching_archived_feature(
    tmp_path: Path,
) -> None:
    features_dir = tmp_path / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True)
    archived_dir = tmp_path / "docs" / "spec" / "features_done"
    archived_dir.mkdir(parents=True)

    active_feature_path = features_dir / "FEAT-202.yaml"
    unrelated_archived_path = archived_dir / "FEAT-999.yaml"
    unrelated_archived_path.write_text(
        "\n".join(
            [
                "id: FEAT-999",
                "status: done",
                "",
            ]
        ),
        encoding="utf-8",
    )

    post_outcome = feature_state_module.refresh_feature_after_implement(
        tmp_path,
        active_feature_path,
    )

    assert post_outcome.result == "failed"
    assert post_outcome.failed_gate == "feature_missing"
    assert post_outcome.archived_in_iteration is False
    assert post_outcome.archived_path is None


def test_gate_and_verification_phase_error_paths(
    tmp_path: Path,
    capsys: Any,
    monkeypatch: Any,
) -> None:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  failing:",
                "    type: command",
                "    command: python -c 'raise SystemExit(1)'",
                "",
            ]
        ),
        encoding="utf-8",
    )

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=True,
        attempt=1,
        feedback=None,
        verbose_output=True,
    )

    gate_deps = GatePhaseDependencies(
        restore_archived_feature=lambda *_args: (False, "rollback-failed"),
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=None,
        ),
    )
    gate_outcome = run_gate_phase(
        inputs,
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-001.yaml",
        dependencies=gate_deps,
    )
    assert gate_outcome.result == "failed"
    assert "archive rollback failed: rollback-failed" in gate_outcome.gate_output

    commands = ["cmd-ok"]
    monkeypatch.setattr(
        "engineeringagent.loop_runtime.phases.run_shell_command",
        lambda *_args: SimpleNamespace(
            returncode=0,
            stdout="ok-out\n",
            stderr="warn-err\n",
        ),
    )
    verification_outcome = run_verification_phase(inputs, commands)
    assert verification_outcome.result == "passed"
    captured = capsys.readouterr()
    assert "ok-out" in captured.out
    assert "warn-err" in captured.err


def test_completion_phase_fallback_paths() -> None:
    inputs = FeatureIterationInputs(
        project_root=Path("."),
        feature_path=Path("docs/spec/features/FEAT-001/spec.yaml"),
        attempt=1,
        feedback=None,
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
        archived_path=Path("docs/spec/features_done/FEAT-001/spec.yaml"),
        dependencies=deps,
    )
    assert missing.result == "failed"
    assert missing.failed_gate == "feature_archive"

    commit_failed = run_completion_commit_phase(
        inputs,
        post_feature={"id": "FEAT-001"},
        archived_in_iteration=True,
        archived_path=Path("docs/spec/features_done/FEAT-001/spec.yaml"),
        dependencies=deps,
    )
    assert commit_failed.result == "failed"
    assert "archive rollback failed: restore failed" in commit_failed.completion_output
    assert commit_failed.feedback is not None
    assert '"kind":"command_failure"' in commit_failed.feedback


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
