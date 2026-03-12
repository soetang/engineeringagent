from __future__ import annotations

from pathlib import Path

import yaml
import pytest

from engineeringagent.adapters.quality.validation.validator import validate
from tests.meta.validator_support import write_bundled_feature_spec, write_plan_artifact


@pytest.mark.parametrize("suffix", [".yaml", ".yml"])
def test_bundled_only_validate_rejects_flat_feature_entrypoints(
    tmp_path: Path,
    suffix: str,
) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "specifications" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    feature_path = features_dir / f"FEAT-903-contract-errors{suffix}"
    feature_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-903",
                "title": "Contract violations",
                "type": "feature",
                "expected_commit_subject": "feat: enforce contract violations fixture",
                "status": "doing",
                "priority": "high",
                "objective": "Force strict contract failures.",
                "acceptance": ["Validator reports strict errors."],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages == [
        f"{feature_path}: feature specs must use bundled spec.yaml entrypoints"
    ]


def test_validate_reports_bundled_contract_errors(tmp_path: Path) -> None:
    project_root = tmp_path
    feature_root = (
        project_root
        / "docs"
        / "specifications"
        / "features"
        / "FEAT-903-contract-errors"
    )
    write_bundled_feature_spec(
        feature_root,
        extra_fields={
            "status": "doing",
            "unknown_field": True,
        },
    )

    messages = validate(project_root=project_root)

    assert messages
    assert any(
        "spec.yaml:status" in message and "Input should be 'backlog'" in message
        for message in messages
    )
    assert any(
        "spec.yaml:unknown_field" in message
        and "Extra inputs are not permitted" in message
        for message in messages
    )


def test_bundled_only_validate_rejects_flat_feature_multiline_fixture_by_entrypoint(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "specifications" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    feature_path = features_dir / "FEAT-920-multiline-verification.yaml"
    feature_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-920",
                "title": "Multiline verification command",
                "type": "chore",
                "expected_commit_subject": "chore: reject multiline verification",
                "status": "backlog",
                "priority": "high",
                "objective": "Ensure validator rejects multiline verification commands.",
                "acceptance": ["validate reports multiline verification commands."],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert len(messages) == 1
    assert messages[0] == (
        f"{feature_path}: feature specs must use bundled spec.yaml entrypoints"
    )


def test_validate_allows_multiline_verification_commands_in_done_specs(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_done_dir = project_root / "docs" / "specifications" / "features_done"
    feature_root = features_done_dir / "FEAT-921-multiline-verification-done"
    write_bundled_feature_spec(
        feature_root,
        feature_id="FEAT-921",
        extra_fields={"status": "done"},
    )
    (feature_root / "plan.md").write_text(
        "\n".join(
            [
                "---",
                "plan_id: FEAT-921",
                "feature_id: FEAT-921",
                "status: done",
                "source_spec: spec.yaml",
                "planning_tier: planned",
                "phases:",
                "  - id: P1",
                "    title: Archived done phase",
                "    status: done",
                "    verification:",
                "      - |",
                "        echo one",
                "        echo two",
                "---",
                "",
                "# Plan",
                "",
            ]
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert all(
        "verification commands must be single-line strings" not in message
        for message in messages
    )


@pytest.mark.parametrize("suffix", [".yaml", ".yml"])
def test_bundled_only_validate_rejects_flat_done_feature_entrypoints(
    tmp_path: Path,
    suffix: str,
) -> None:
    project_root = tmp_path
    features_done_dir = project_root / "docs" / "specifications" / "features_done"
    features_done_dir.mkdir(parents=True, exist_ok=True)

    done_path = features_done_dir / f"FEAT-921-flat-done{suffix}"
    done_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-921",
                "title": "Flat done spec",
                "type": "spec",
                "expected_commit_subject": "spec: reject flat done spec",
                "planning_tier": "direct",
                "status": "done",
                "priority": "high",
                "objective": "Reject flat archived feature entrypoints.",
                "acceptance": ["Bundled archived specs are the only supported layout."],
                "artifacts": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages == [
        f"{done_path}: feature specs must use bundled spec.yaml entrypoints"
    ]


def test_validate_rejects_multiline_bundled_plan_phase_verification_commands(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    feature_root = (
        project_root
        / "docs"
        / "specifications"
        / "features"
        / "FEAT-922-multiline-bundled-phase-verification"
    )
    write_bundled_feature_spec(feature_root, feature_id="FEAT-922")
    plan_path = write_plan_artifact(feature_root, feature_id="FEAT-922")
    plan_path.write_text(
        "\n".join(
            [
                "---",
                "plan_id: FEAT-922",
                "feature_id: FEAT-922",
                "status: pending",
                "source_spec: spec.yaml",
                "planning_tier: planned",
                "phases:",
                "  - id: P1",
                "    title: First phase",
                "    status: pending",
                "    verification:",
                "      - |",
                "        echo one",
                "        echo two",
                "---",
                "",
                "# Plan",
                "",
            ]
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert len(messages) == 1
    assert messages[0].startswith(f"{plan_path}:phases[0].verification[0]:")
    assert "verification commands must be single-line strings" in messages[0]
    assert "no \\n or \\r" in messages[0]
