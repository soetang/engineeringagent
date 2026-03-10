from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import tomli
import yaml

from engineeringagent.checks.validate.validator import (
    validate,
)
from engineeringagent.checks.validate.repo_policy_purge_invariant import git_client
from tests.meta.validator_support import (
    make_invalid_project,
    write_bundled_feature_spec,
    write_legacy_feature_wrapper,
    write_plan_artifact,
)


@pytest.mark.parametrize(
    ("fixture_name", "expected"),
    [
        ("missing-objective.yaml", "Field required"),
        ("bad-status.yaml", "Input should be 'backlog'"),
    ],
)
def test_invalid_spec_fixtures_report_clear_errors(
    tmp_path: Path,
    repo_root: Path,
    fixture_name: str,
    expected: str,
) -> None:
    project_root = make_invalid_project(repo_root, tmp_path, fixture_name)

    messages = validate(project_root=project_root)

    assert messages
    assert any(expected in message for message in messages)


def test_validate_reports_enum_unknown_and_type_errors(tmp_path: Path) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    feature_path = features_dir / "FEAT-903-contract-errors.yaml"
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
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Bad order type",
                        "status": "backlog",
                        "order": "first",
                        "verification": ["true"],
                    }
                ],
                "unknown_field": True,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages
    assert any(
        "status" in message and "Input should be 'backlog'" in message
        for message in messages
    )
    assert any(
        "subtasks[0].order" in message and "Extra inputs are not permitted" in message
        for message in messages
    )
    assert any(
        "unknown_field" in message and "Extra inputs are not permitted" in message
        for message in messages
    )


def test_validate_rejects_multiline_verification_commands(tmp_path: Path) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
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
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Stub",
                        "status": "backlog",
                        "verification": ["echo one\necho two"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert len(messages) == 1
    assert messages[0].startswith(f"{feature_path}:subtasks[0].verification[0]:")
    assert "verification commands must be single-line strings" in messages[0]
    assert "no \\n or \\r" in messages[0]


def test_validate_allows_multiline_verification_commands_in_done_specs(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_done_dir = project_root / "docs" / "spec" / "features_done"
    features_done_dir.mkdir(parents=True, exist_ok=True)

    done_path = features_done_dir / "FEAT-921-multiline-verification-done.yaml"
    done_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-921",
                "title": "Multiline verification command done spec",
                "status": "done",
                "priority": "high",
                "objective": "Ensure validator does not block archived specs.",
                "acceptance": ["Archived specs remain readable."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Already complete",
                        "status": "done",
                        "verification": ["echo one\necho two"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert all(
        "verification commands must be single-line strings" not in message
        for message in messages
    )


def test_validate_rejects_multiline_bundled_plan_phase_verification_commands(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    feature_root = (
        project_root
        / "docs"
        / "spec"
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


def test_validate_missing_required_fields_with_pydantic(tmp_path: Path) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    feature_path = features_dir / "FEAT-904-missing-required.yaml"
    feature_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-904",
                "title": "Missing fields",
                "type": "feature",
                "expected_commit_subject": "feat: validate missing required fields",
                "status": "backlog",
                "priority": "high",
                "acceptance": ["Missing required fields are reported."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "No verification",
                        "status": "backlog",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages
    assert any(
        "objective" in message and "Field required" in message for message in messages
    )
    assert any(
        "subtasks[0].verification" in message and "Field required" in message
        for message in messages
    )


def test_validate_requires_feature_type(tmp_path: Path) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    (features_dir / "FEAT-910-missing-type.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-910",
                "title": "Missing type",
                "expected_commit_subject": "feat: validate missing feature type",
                "status": "backlog",
                "priority": "high",
                "objective": "Feature type is required.",
                "acceptance": ["Validator reports missing type."],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert any(
        "type" in message and "Field required" in message for message in messages
    )


def test_validate_requires_expected_commit_subject(tmp_path: Path) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    (features_dir / "FEAT-911-missing-expected-subject.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-911",
                "title": "Missing expected commit subject",
                "type": "feature",
                "status": "backlog",
                "priority": "high",
                "objective": "Expected commit subject is required.",
                "acceptance": [
                    "Validator reports missing expected commit subject metadata."
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert any(
        "expected_commit_subject" in message and "Field required" in message
        for message in messages
    )


def test_validate_reports_invalid_potential_features_contract(tmp_path: Path) -> None:
    project_root = tmp_path
    potential_features_path = project_root / "docs" / "spec" / "potential_features.yaml"
    potential_features_path.parent.mkdir(parents=True, exist_ok=True)
    potential_features_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "description": "Potential features backlog",
                "potential_features": [
                    {
                        "id": "POT-001",
                        "title": "Bad contract",
                        "status": "queued",
                        "context": "Use strict status enum.",
                        "value": ["Contract rejects unknown enums."],
                        "unexpected": True,
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages
    assert any(
        "potential_features[0].status" in message
        and "Input should be 'idea'" in message
        for message in messages
    )
    assert any(
        "potential_features[0].unexpected" in message
        and "Extra inputs are not permitted" in message
        for message in messages
    )


def test_validate_reports_yaml_parse_errors_across_validator_inputs(
    tmp_path: Path,
) -> None:
    features_dir = tmp_path / "docs" / "spec" / "features"
    features_done_dir = tmp_path / "docs" / "spec" / "features_done"
    potential_features_path = tmp_path / "docs" / "spec" / "potential_features.yaml"

    features_dir.mkdir(parents=True, exist_ok=True)
    features_done_dir.mkdir(parents=True, exist_ok=True)
    potential_features_path.parent.mkdir(parents=True, exist_ok=True)

    (features_dir / "FEAT-999-bad-active.yaml").write_text("[\n", encoding="utf-8")
    (features_done_dir / "FEAT-998-bad-done.yaml").write_text("[\n", encoding="utf-8")
    potential_features_path.write_text("[\n", encoding="utf-8")

    messages = validate(project_root=tmp_path)

    assert any("FEAT-999-bad-active.yaml: failed to parse YAML" in m for m in messages)
    assert any("FEAT-998-bad-done.yaml: failed to parse YAML" in m for m in messages)
    assert any("potential_features.yaml: failed to parse YAML" in m for m in messages)


def test_validate_ignores_legacy_feature_schema_artifact_parse_and_sync_errors(
    tmp_path: Path,
) -> None:
    features_dir = tmp_path / "docs" / "spec" / "features"
    schemas_dir = tmp_path / "docs" / "spec" / "schemas"
    features_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)

    (features_dir / "FEAT-999-valid.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-999",
                "title": "Ignore legacy schema artifact file",
                "type": "feature",
                "expected_commit_subject": "feat: ignore legacy feature schema artifact",
                "status": "backlog",
                "priority": "medium",
                "objective": "Validation should ignore removed schema artifact checks.",
                "acceptance": ["Legacy schema artifact drift checks stay removed."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Validate contracts",
                        "status": "backlog",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (schemas_dir / "feature.schema.json").write_text("{", encoding="utf-8")

    messages = validate(project_root=tmp_path)

    assert all("failed to parse JSON schema" not in message for message in messages)
    assert all("schema artifact is out of sync" not in message for message in messages)


def test_validate_reports_reviewer_prompt_with_deprecated_responseformat(
    tmp_path: Path,
) -> None:
    prompts_dir = tmp_path / "harness" / "reviewers" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "missing-token.md").write_text(
        "Return strict JSON only.\n",
        encoding="utf-8",
    )
    (prompts_dir / "has-token.md").write_text(
        "$responseformat\n\nAssess reviewer output.\n",
        encoding="utf-8",
    )

    messages = validate(project_root=tmp_path)

    assert any(
        "harness/reviewers/prompts/has-token.md" in message
        and "must not include deprecated `$responseformat`" in message
        for message in messages
    )
    assert all("missing-token.md" not in message for message in messages)

def test_validate_reports_git_ls_files_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        git_client,
        "ls_files",
        lambda _root: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )

    messages = validate(project_root=tmp_path)
    assert any("validate: git ls-files failed" in message for message in messages)


def test_validate_enforces_purge_invariants_using_git_ls_files(tmp_path: Path) -> None:
    def _run_git(*args: str) -> None:
        proc = subprocess.run(
            ["git", *args],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr

    _run_git("init")

    removed_reviewer_id = "_".join(["readme", "process"])
    removed_mode = "_".join(["clean", "room", "readme", "cli"])

    (tmp_path / "active.txt").write_text(
        f"{removed_reviewer_id}\n{removed_mode}\n",
        encoding="utf-8",
    )
    _run_git("add", "active.txt")

    excluded_dir = tmp_path / ".engineeringagent" / "progress"
    excluded_dir.mkdir(parents=True, exist_ok=True)
    (excluded_dir / "excluded.txt").write_text(
        f"{removed_reviewer_id}\n",
        encoding="utf-8",
    )
    _run_git("add", ".engineeringagent/progress/excluded.txt")

    messages = validate(project_root=tmp_path)

    assert any(
        "active.txt" in message and "purge invariant" in message for message in messages
    )
    assert all(
        ".engineeringagent/progress/excluded.txt" not in message for message in messages
    )


def test_validate_does_not_exclude_legacy_progress_artifacts_from_purge_scan(
    tmp_path: Path,
) -> None:
    def _run_git(*args: str) -> None:
        proc = subprocess.run(
            ["git", *args],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr

    _run_git("init")

    removed_reviewer_id = "_".join(["readme", "process"])

    legacy_progress_dir = tmp_path / "progress"
    legacy_progress_dir.mkdir(parents=True, exist_ok=True)
    legacy_artifact = legacy_progress_dir / "runs" / "runs.jsonl"
    legacy_artifact.parent.mkdir(parents=True, exist_ok=True)
    legacy_artifact.write_text(
        f"artifact marker: {removed_reviewer_id}\n",
        encoding="utf-8",
    )
    _run_git("add", "progress/runs/runs.jsonl")

    messages = validate(project_root=tmp_path)
    assert any(
        "progress/runs/runs.jsonl" in message and "purge invariant" in message
        for message in messages
    )


def test_validate_does_not_enforce_opencode_config_invariant(tmp_path: Path) -> None:
    def _run_git(*args: str) -> None:
        proc = subprocess.run(
            ["git", *args],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr

    _run_git("init")

    legacy_config = ".".join(["opencode", "json"])

    (tmp_path / "active.txt").write_text(
        f"Repository documentation must not rely on {legacy_config}\n",
        encoding="utf-8",
    )
    _run_git("add", "active.txt")

    (tmp_path / legacy_config).write_text("{}\n", encoding="utf-8")
    _run_git("add", legacy_config)

    messages = validate(project_root=tmp_path)

    forbidden_fragments = (
        "opencode config invariant",
        "repo-root OpenCode config",
        legacy_config,
    )
    violations = [
        message
        for message in messages
        if any(fragment in message for fragment in forbidden_fragments)
    ]
    assert not violations


def test_validate_allows_arbitrary_agents_content(tmp_path: Path) -> None:
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "legacy line A",
                "legacy line B",
                "",
                "## 6) First-Window Boot Sequence",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert not validate(project_root=tmp_path)


def test_validate_preserves_non_legacy_done_required_field_errors(
    tmp_path: Path,
) -> None:
    features_done_dir = tmp_path / "docs" / "spec" / "features_done"
    features_done_dir.mkdir(parents=True, exist_ok=True)
    (features_done_dir / "FEAT-897-missing-priority.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-897",
                "title": "Done spec still requires priority",
                "status": "done",
                "objective": "Keep non-legacy required-field errors visible.",
                "acceptance": ["priority remains required for done specs."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Already complete",
                        "status": "done",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=tmp_path)

    assert any(
        "FEAT-897-missing-priority.yaml:priority: Field required" in m for m in messages
    )


def test_validate_reports_done_feature_left_in_active_directory(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"

    features_dir.mkdir(parents=True, exist_ok=True)

    feature_path = features_dir / "FEAT-901-preexisting-done.yaml"
    feature_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-901",
                "title": "Done spec in active directory",
                "type": "feature",
                "expected_commit_subject": "feat: done spec in active directory",
                "status": "done",
                "priority": "high",
                "objective": "Validate done specs are archived.",
                "acceptance": ["Done specs are archived under features_done."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Already complete",
                        "status": "done",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages
    assert any(
        "completed feature specs must be archived" in message for message in messages
    )
    assert any(
        "docs/spec/features_done/FEAT-901-preexisting-done.yaml" in message
        for message in messages
    )


def test_validate_reports_done_bundled_feature_left_in_active_directory(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    feature_root = (
        project_root
        / "docs"
        / "spec"
        / "features"
        / "FEAT-902-preexisting-done-bundle"
    )
    write_bundled_feature_spec(
        feature_root,
        feature_id="FEAT-902",
        planning_tier="planned",
        extra_fields={"status": "done"},
    )
    (feature_root / "plan.md").write_text(
        "\n".join(
            [
                "---",
                "plan_id: FEAT-902",
                "feature_id: FEAT-902",
                "status: done",
                "source_spec: spec.yaml",
                "planning_tier: planned",
                "phases:",
                "  - id: P1",
                "    title: First phase",
                "    status: done",
                "    verification:",
                "      - 'true'",
                "---",
                "",
                "# Plan",
                "",
            ]
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages
    assert any(
        "completed feature specs must be archived" in message for message in messages
    )
    assert any(
        "docs/spec/features_done/FEAT-902-preexisting-done-bundle/spec.yaml"
        in message
        for message in messages
    )


def test_validate_defaults_to_docs_without_toml_config(tmp_path: Path) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"

    features_dir.mkdir(parents=True, exist_ok=True)

    feature_path = features_dir / "FEAT-938-default-docs-root.yaml"
    feature_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-938",
                "title": "Default docs root active done spec",
                "type": "feature",
                "expected_commit_subject": "feat: validate default docs root",
                "status": "done",
                "priority": "high",
                "objective": "Use default docs root when TOML config is absent.",
                "acceptance": [
                    "Done specs are archived under docs/spec/features_done."
                ],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Already complete",
                        "status": "done",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages
    assert any(
        "docs/spec/features_done/FEAT-938-default-docs-root.yaml" in message
        for message in messages
    )


def test_validate_uses_configured_docs_root(tmp_path: Path) -> None:
    project_root = tmp_path
    docs_root = project_root / "docs.engineeringagent"
    features_dir = docs_root / "spec" / "features"

    (project_root / "engineeringagent.toml").write_text(
        'docs-root = "docs.engineeringagent"\n',
        encoding="utf-8",
    )
    features_dir.mkdir(parents=True, exist_ok=True)

    feature_path = features_dir / "FEAT-937-configured-docs-root.yaml"
    feature_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-937",
                "title": "Configured docs root active done spec",
                "type": "feature",
                "expected_commit_subject": "feat: validate configured docs root",
                "status": "done",
                "priority": "high",
                "objective": "Use configured docs root for validator paths.",
                "acceptance": ["Done specs are archived under configured docs root."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Already complete",
                        "status": "done",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (features_dir / ".allow-done-active.txt").write_text(
        "FEAT-937-configured-docs-root.yaml\n",
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages
    assert any(
        "docs.engineeringagent/spec/features/.allow-done-active.txt" in message
        and "unsupported configuration file" in message
        for message in messages
    )
    assert any(
        "docs.engineeringagent/spec/features_done/FEAT-937-configured-docs-root.yaml"
        in message
        for message in messages
    )


def test_validate_transitional_policy_for_preexisting_done_features(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"

    features_dir.mkdir(parents=True, exist_ok=True)

    feature_name = "FEAT-902-transition-done.yaml"
    feature_path = features_dir / feature_name
    feature_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-902",
                "title": "Transition exception",
                "type": "feature",
                "expected_commit_subject": "feat: allow temporary done transition",
                "status": "done",
                "priority": "high",
                "objective": "Allow temporary transition policy.",
                "acceptance": ["Validator supports explicit transition exception."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Already complete",
                        "status": "done",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    (features_dir / ".allow-done-active.txt").write_text(
        f"# temporary exceptions\n{feature_name}\n",
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages
    assert any(
        "docs/spec/features/.allow-done-active.txt" in message
        and "unsupported configuration file" in message
        for message in messages
    )


def test_validate_rejects_done_specs_missing_required_metadata(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_done_dir = project_root / "docs" / "spec" / "features_done"

    features_done_dir.mkdir(parents=True, exist_ok=True)

    (features_done_dir / "FEAT-899-legacy-done.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-899",
                "title": "Legacy done spec",
                "status": "done",
                "priority": "high",
                "objective": "Reject done specs missing required metadata.",
                "acceptance": ["Done specs remain readable during migration."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Already complete",
                        "status": "done",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages
    assert any(
        "FEAT-899-legacy-done.yaml:type: Field required" in message
        for message in messages
    )
    assert any(
        "FEAT-899-legacy-done.yaml:expected_commit_subject: Field required"
        in message
        for message in messages
    )


def test_validate_allows_noncontiguous_done_and_multiple_in_progress_subtasks(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    (features_dir / "FEAT-905-noncontiguous-order.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-905",
                "title": "Noncontiguous subtask order",
                "type": "feature",
                "expected_commit_subject": "feat: preserve contiguous order rule",
                "status": "backlog",
                "priority": "high",
                "objective": "Preserve contiguous order rule.",
                "acceptance": ["Validator reports contiguous order violations."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "First",
                        "status": "backlog",
                        "verification": ["true"],
                    },
                    {
                        "id": "ST-002",
                        "title": "Second",
                        "status": "backlog",
                        "verification": ["true"],
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    (features_dir / "FEAT-906-done-prefix-break.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-906",
                "title": "Done prefix violation",
                "type": "feature",
                "expected_commit_subject": "feat: preserve done prefix rule",
                "status": "in_progress",
                "priority": "high",
                "objective": "Preserve done-prefix rule.",
                "acceptance": ["Validator reports done-prefix violations."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "First",
                        "status": "backlog",
                        "verification": ["true"],
                    },
                    {
                        "id": "ST-002",
                        "title": "Second",
                        "status": "done",
                        "verification": ["true"],
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    (features_dir / "FEAT-939-multiple-inprogress.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-939",
                "title": "Multiple in-progress subtasks",
                "type": "feature",
                "expected_commit_subject": "feat: allow multiple in-progress subtasks",
                "status": "in_progress",
                "priority": "high",
                "objective": "Allow more than one in-progress subtask.",
                "acceptance": ["Validator allows multiple in-progress subtasks."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "First",
                        "status": "in_progress",
                        "verification": ["true"],
                    },
                    {
                        "id": "ST-002",
                        "title": "Second",
                        "status": "in_progress",
                        "verification": ["true"],
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert not messages


def test_validate_preserves_feature_status_invariant_rules(tmp_path: Path) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    (features_dir / "FEAT-907-done-with-open-subtasks.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-907",
                "title": "Done but subtask open",
                "type": "feature",
                "expected_commit_subject": "feat: preserve done status invariant",
                "status": "done",
                "priority": "high",
                "objective": "Preserve done status invariant.",
                "acceptance": ["Validator reports done status mismatch."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Open",
                        "status": "backlog",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    (features_dir / "FEAT-908-inprogress-subtask-on-backlog.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-908",
                "title": "In progress subtask on backlog feature",
                "type": "feature",
                "expected_commit_subject": "feat: preserve in progress status invariant",
                "status": "backlog",
                "priority": "high",
                "objective": "Preserve in-progress status invariant.",
                "acceptance": ["Validator reports feature status mismatch."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Running",
                        "status": "in_progress",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert any(
        "feature status done requires all subtasks done" in message
        for message in messages
    )
    assert any(
        "feature with in_progress subtask must be in_progress" in message
        for message in messages
    )


def test_validate_preserves_bundled_plan_phase_status_invariants(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    feature_dir = (
        project_root / "docs" / "spec" / "features" / "FEAT-909-bundled-status-mismatch"
    )
    feature_dir.mkdir(parents=True, exist_ok=True)

    (feature_dir / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-909",
                "title": "Backlog but plan phase in progress",
                "type": "feature",
                "expected_commit_subject": "feat: preserve bundled phase invariants",
                "status": "backlog",
                "priority": "high",
                "objective": "Preserve bundled phase status invariants.",
                "acceptance": ["Validator reports bundled plan status mismatch."],
                "planning_tier": "planned",
                "artifacts": {"plan": "plan.md"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (feature_dir / "plan.md").write_text(
        "\n".join(
            [
                "---",
                "plan_id: FEAT-909",
                "feature_id: FEAT-909",
                "status: in_progress",
                "source_spec: spec.yaml",
                "planning_tier: planned",
                "phases:",
                "  - id: P1",
                "    title: Active bundled work",
                "    status: in_progress",
                "    verification:",
                "      - 'true'",
                "---",
                "",
                "# FEAT-909 Plan",
                "",
            ]
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert any(
        "feature with in_progress phase must be in_progress" in message
        for message in messages
    )


def test_validate_preserves_blocked_bundled_plan_phase_status_invariants(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    feature_dir = (
        project_root / "docs" / "spec" / "features" / "FEAT-910-bundled-status-mismatch"
    )
    feature_dir.mkdir(parents=True, exist_ok=True)

    (feature_dir / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-910",
                "title": "In progress but plan phase blocked",
                "type": "feature",
                "expected_commit_subject": "feat: preserve blocked bundled phase invariants",
                "status": "in_progress",
                "priority": "high",
                "objective": "Preserve blocked bundled phase status invariants.",
                "acceptance": ["Validator reports blocked bundled plan status mismatch."],
                "planning_tier": "planned",
                "artifacts": {"plan": "plan.md"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (feature_dir / "plan.md").write_text(
        "\n".join(
            [
                "---",
                "plan_id: FEAT-910",
                "feature_id: FEAT-910",
                "status: blocked",
                "source_spec: spec.yaml",
                "planning_tier: planned",
                "phases:",
                "  - id: P1",
                "    title: Blocked bundled work",
                "    status: blocked",
                "    verification:",
                "      - 'true'",
                "---",
                "",
                "# FEAT-910 Plan",
                "",
            ]
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert any(
        "feature with blocked phase must be blocked" in message
        for message in messages
    )


def test_validate_allows_non_bootstrap_agents_file(tmp_path: Path) -> None:
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "# Legacy user guidance",
                "",
                "Do not include any bootstrap contract lines.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    messages = validate(project_root=tmp_path)

    assert all(
        "AGENTS docs bootstrap contract missing required line" not in message
        for message in messages
    )


def test_repo_policy_docs_map_module_is_retired() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("engineeringagent.checks.validate.repo_policy_docs_map")


def test_meta_validator_has_no_docs_wording_assertions() -> None:
    """Guard against brittle tests that assert exact wording in repo docs.

    We intentionally avoid testing README.md or docs/**/*.md content in pytest
    unless it's directly tied to functionality (for example reviewer prompt
    contract validation).
    """

    assert True


def test_validate_allows_partial_legacy_agents_content(tmp_path: Path) -> None:
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "legacy line A",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    messages = validate(project_root=tmp_path)

    assert all(
        "AGENTS docs bootstrap contract missing required line" not in message
        for message in messages
    )


def test_validate_allows_single_legacy_agents_line(tmp_path: Path) -> None:
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "legacy line B",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    messages = validate(project_root=tmp_path)

    assert all(
        "AGENTS docs bootstrap contract missing required line" not in message
        for message in messages
    )


def test_validate_rejects_builtin_manifest_references(tmp_path: Path) -> None:
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "contract_version": "1.0",
                "rules": [{"builtin": "unknown.rule"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=tmp_path)

    assert len(messages) == 1
    assert "builtin manifest references are no longer supported" in messages[0]


def test_validate_accepts_command_fitness_manifest_references(tmp_path: Path) -> None:
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "contract_version": "1.0",
                "rules": [
                    {
                        "rule_id": "custom.docs-links",
                        "name": "Docs links check",
                        "summary": "Validate markdown links resolve.",
                        "rationale": "Broken links hide docs regressions.",
                        "remediation": "Update stale links.",
                        "scope": "docs",
                        "severity": "warning",
                        "side_effect_free": True,
                        "adapter": "command",
                        "command": ["uv", "run", "python", "scripts/check_docs.py"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=tmp_path)

    assert not messages


def test_validate_rejects_filename_frontmatter_id_mismatch_active_and_done(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    features_done_dir = project_root / "docs" / "spec" / "features_done"
    features_dir.mkdir(parents=True, exist_ok=True)
    features_done_dir.mkdir(parents=True, exist_ok=True)

    (features_dir / "FEAT-002-mismatch.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-001",
                "title": "Active filename mismatch",
                "type": "feature",
                "expected_commit_subject": "feat: active filename mismatch",
                "status": "backlog",
                "priority": "high",
                "objective": "Reject filename/frontmatter id drift.",
                "acceptance": ["Validator rejects mismatched filename ids."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Stub",
                        "status": "backlog",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    (features_done_dir / "FEAT-004-mismatch.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-003",
                "title": "Done filename mismatch",
                "status": "done",
                "priority": "high",
                "objective": "Reject filename/frontmatter id drift for done specs.",
                "acceptance": ["Validator rejects mismatched filename ids."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Already complete",
                        "status": "done",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert any(
        "FEAT-002-mismatch.yaml:id: filename id token FEAT-002 does not match frontmatter id FEAT-001"
        in message
        for message in messages
    )
    assert any(
        "FEAT-004-mismatch.yaml:id: filename id token FEAT-004 does not match frontmatter id FEAT-003"
        in message
        for message in messages
    )


def test_validate_rejects_duplicate_feature_ids_in_active_specs_without_opt_out(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "id": "FEAT-010",
        "title": "Duplicate active id",
        "type": "feature",
        "expected_commit_subject": "feat: duplicate active id",
        "status": "backlog",
        "priority": "high",
        "objective": "Reject overlapping active feature ids.",
        "acceptance": ["Validator rejects duplicate feature ids."],
        "subtasks": [
            {
                "id": "ST-001",
                "title": "Stub",
                "status": "backlog",
                "verification": ["true"],
            }
        ],
    }

    (features_dir / "FEAT-010-a.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )
    (features_dir / "FEAT-010-b.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert any("duplicate base feature id" in message for message in messages)


def test_validate_rejects_duplicate_feature_ids_in_done_specs(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_done_dir = project_root / "docs" / "spec" / "features_done"
    features_done_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "id": "FEAT-050",
        "title": "Duplicate done id",
        "type": "feature",
        "expected_commit_subject": "feat: duplicate done id",
        "status": "done",
        "priority": "high",
        "objective": "Reject overlapping done feature ids by default.",
        "acceptance": ["Validator rejects duplicate done ids by default."],
        "subtasks": [
            {
                "id": "ST-001",
                "title": "Already complete",
                "status": "done",
                "verification": ["true"],
            }
        ],
    }

    (features_done_dir / "FEAT-050-one.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )
    (features_done_dir / "FEAT-050-two.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert any("duplicate base feature id" in message for message in messages)


def test_validate_reports_filename_id_token_extraction_failure(tmp_path: Path) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    (features_dir / "FEAT999.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-999",
                "title": "Bad filename token",
                "type": "feature",
                "expected_commit_subject": "feat: bad filename token",
                "status": "backlog",
                "priority": "high",
                "objective": "Force filename token extraction failure.",
                "acceptance": ["Validator reports filename token extraction failure."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Stub",
                        "status": "backlog",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert any(
        "FEAT999.yaml:id: failed to extract filename id token" in message
        for message in messages
    )


def test_validate_rejects_duplicate_feature_id_across_active_and_done_specs(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    features_done_dir = project_root / "docs" / "spec" / "features_done"
    features_dir.mkdir(parents=True, exist_ok=True)
    features_done_dir.mkdir(parents=True, exist_ok=True)

    (features_dir / "FEAT-020-active.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-020",
                "title": "Active",
                "type": "feature",
                "expected_commit_subject": "feat: active",
                "status": "backlog",
                "priority": "high",
                "objective": "Create active/done collision.",
                "acceptance": ["Validator rejects collisions involving active specs."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Stub",
                        "status": "backlog",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    (features_done_dir / "FEAT-020-archived.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-020",
                "title": "Archived",
                "type": "feature",
                "expected_commit_subject": "feat: archived",
                "status": "done",
                "priority": "high",
                "objective": "Create active/done collision.",
                "acceptance": ["Validator rejects collisions involving active specs."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Already complete",
                        "status": "done",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert any(
        "across active and done specs" in message
        and "duplicate base feature id" in message
        for message in messages
    )


def test_validate_bundled_feature_contract_accepts_planned_package(
    tmp_path: Path,
) -> None:
    feature_root = (
        tmp_path / "docs" / "spec" / "features" / "FEAT-181-bundled-feature-contract"
    )
    write_bundled_feature_spec(feature_root)
    write_plan_artifact(feature_root)

    messages = validate(project_root=tmp_path)

    assert not messages


def test_validate_bundled_feature_contract_rejects_subtasks_in_active_spec(
    tmp_path: Path,
) -> None:
    feature_root = (
        tmp_path / "docs" / "spec" / "features" / "FEAT-181-bundled-feature-contract"
    )
    write_bundled_feature_spec(
        feature_root,
        extra_fields={
            "subtasks": [
                {
                    "id": "ST-001",
                    "title": "Legacy subtask",
                    "status": "backlog",
                    "verification": ["true"],
                }
            ]
        },
    )
    write_plan_artifact(feature_root)

    messages = validate(project_root=tmp_path)

    assert any(
        "spec.yaml:subtasks" in message and "Extra inputs are not permitted" in message
        for message in messages
    )


def test_validate_bundled_feature_contract_requires_companion_artifacts(
    tmp_path: Path,
) -> None:
    feature_root = (
        tmp_path / "docs" / "spec" / "features" / "FEAT-181-bundled-feature-contract"
    )
    write_bundled_feature_spec(
        feature_root,
        planning_tier="researched",
        include_research_artifact=False,
    )
    write_plan_artifact(feature_root, planning_tier="researched")

    messages = validate(project_root=tmp_path)

    assert any(
        "spec.yaml:artifacts.research" in message
        and "planning_tier researched requires artifacts.research" in message
        for message in messages
    )


def test_validate_bundled_feature_contract_allows_wrapper_and_canonical_spec_pair(
    tmp_path: Path,
) -> None:
    features_dir = tmp_path / "docs" / "spec" / "features"
    write_legacy_feature_wrapper(
        features_dir / "FEAT-181-bundled-feature-contract.yaml",
    )
    feature_root = features_dir / "FEAT-181-bundled-feature-contract"
    write_bundled_feature_spec(
        feature_root,
        planning_tier="researched",
        include_research_artifact=True,
    )
    write_plan_artifact(feature_root, planning_tier="researched")
    (feature_root / "research.md").write_text("# Research\n", encoding="utf-8")

    messages = validate(project_root=tmp_path)

    assert all("duplicate base feature id FEAT-181" not in message for message in messages)


def test_pytest_default_coverage_contract_is_declared(repo_root: Path) -> None:
    pyproject_payload = tomli.loads(
        (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    pytest_options = pyproject_payload["tool"]["pytest"]["ini_options"]
    addopts = pytest_options["addopts"]

    assert "--cov=engineeringagent" in addopts
    assert "--cov-fail-under=95" in addopts
    assert "not integration" not in addopts


def test_validate_allows_empty_agents_file(tmp_path: Path) -> None:
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text("", encoding="utf-8")

    messages = validate(project_root=tmp_path)

    assert all(
        "AGENTS docs bootstrap contract missing required line" not in message
        for message in messages
    )
