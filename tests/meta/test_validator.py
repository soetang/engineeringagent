from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import tomli
import yaml

from engineeringagent.checks.validate.validator import (
    validate,
)
from engineeringagent.checks.validate import repo_validators


def _invalid_spec_fixtures_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures" / "specs" / "invalid"


def _make_invalid_project(repo_root: Path, tmp_path: Path, fixture_name: str) -> Path:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"

    features_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        _invalid_spec_fixtures_dir(repo_root) / fixture_name,
        features_dir / f"{fixture_name}",
    )

    return project_root


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
    project_root = _make_invalid_project(repo_root, tmp_path, fixture_name)

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
        repo_validators.git_client,
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

    excluded_dir = tmp_path / "progress"
    excluded_dir.mkdir(parents=True, exist_ok=True)
    (excluded_dir / "excluded.txt").write_text(
        f"{removed_reviewer_id}\n",
        encoding="utf-8",
    )
    _run_git("add", "progress/excluded.txt")

    messages = validate(project_root=tmp_path)

    assert any(
        "active.txt" in message and "purge invariant" in message for message in messages
    )
    assert all("progress/excluded.txt" not in message for message in messages)


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


def test_validate_accepts_agents_docs_map_glob_when_it_matches(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "exists.md").write_text("ok\n", encoding="utf-8")

    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "## 5) Documentation Layout Reference",
                "- `docs/*.md`",
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


def test_validate_allows_legacy_done_specs_missing_new_metadata(
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
                "objective": "Allow transitional done validation.",
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

    assert not messages


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


def test_agents_docs_map_extraction_scoped_to_docs_layout_section(
    tmp_path: Path,
) -> None:
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "- `docs/ignored-before-map.md`",
                "",
                "## 5) Documentation Layout Reference",
                "- `docs/kept-from-map.md`",
                "",
                "## 6) First-Window Boot Sequence",
                "- `docs/ignored-after-map.md`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    references = repo_validators.iter_agents_docs_map_references(tmp_path)

    assert references == [(6, "docs/kept-from-map.md")]


def test_agents_docs_map_extraction_allows_section_renumbering(tmp_path: Path) -> None:
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "## 9) Documentation Layout Reference",
                "- `docs/kept-after-renumbering.md`",
                "",
                "## 10) First-Window Boot Sequence",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    references = repo_validators.iter_agents_docs_map_references(tmp_path)

    assert references == [(4, "docs/kept-after-renumbering.md")]


def test_agents_docs_map_extraction_is_deterministic(tmp_path: Path) -> None:
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "## 5) Documentation Layout Reference",
                "- `docs/z-last.md` and `docs/a-first.md`",
                "- `docs/m-middle.md`",
                "",
                "## 6) First-Window Boot Sequence",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    first = repo_validators.iter_agents_docs_map_references(tmp_path)
    second = repo_validators.iter_agents_docs_map_references(tmp_path)

    assert first == [
        (4, "docs/a-first.md"),
        (4, "docs/z-last.md"),
        (5, "docs/m-middle.md"),
    ]
    assert second == first


def test_meta_validator_has_no_docs_wording_assertions() -> None:
    """Guard against brittle tests that assert exact wording in repo docs.

    We intentionally avoid testing README.md or docs/**/*.md content in pytest
    unless it's directly tied to functionality (for example reviewer prompt
    contract validation).
    """

    assert True


def test_validate_reports_missing_agents_docs_map_path(tmp_path: Path) -> None:
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "## 5) Documentation Layout Reference",
                "- `docs/missing.md`",
                "",
                "## 6) First-Window Boot Sequence",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    messages = validate(project_root=tmp_path)

    assert messages == ["AGENTS.md:4: docs-map path does not exist: docs/missing.md"]


def test_validate_reports_empty_agents_docs_map_glob(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "exists.md").write_text("ok\n", encoding="utf-8")

    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "## 5) Documentation Layout Reference",
                "- `docs/*.txt`",
                "",
                "## 6) First-Window Boot Sequence",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    messages = validate(project_root=tmp_path)

    assert messages == ["AGENTS.md:4: docs-map glob matches no paths: docs/*.txt"]


def test_validate_reports_agents_docs_map_section_with_no_references(
    tmp_path: Path,
) -> None:
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "## 5) Documentation Layout Reference",
                "- Keep this list updated.",
                "",
                "## 6) First-Window Boot Sequence",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    messages = validate(project_root=tmp_path)

    assert messages == [
        "AGENTS.md:3: docs-map section is present but contains no docs/* references"
    ]


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
    assert all(
        "allow-duplicate-done-base-ids-below" not in message for message in messages
    )


def test_validate_rejects_duplicate_feature_ids_in_done_specs_by_default_with_opt_out_hint(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_done_dir = project_root / "docs" / "spec" / "features_done"
    features_done_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "id": "FEAT-050",
        "title": "Duplicate done id",
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
    assert any(
        "allow-duplicate-done-base-ids-below" in message
        and "[tool.engineeringagent.specs]" in message
        for message in messages
    )


def test_validate_allows_duplicate_done_ids_below_threshold_when_configured(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    (project_root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[tool.engineeringagent.specs]",
                "allow-duplicate-done-base-ids-below = 100",
                "",
            ]
        ),
        encoding="utf-8",
    )
    features_done_dir = project_root / "docs" / "spec" / "features_done"
    features_done_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "id": "FEAT-050",
        "title": "Duplicate done id",
        "status": "done",
        "priority": "high",
        "objective": "Allow legacy duplicate done ids below threshold.",
        "acceptance": ["Validator allows duplicates below threshold."],
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

    assert not validate(project_root=project_root)


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
    assert all(
        "allow-duplicate-done-base-ids-below" not in message for message in messages
    )


def test_validate_rejects_duplicate_done_ids_above_threshold_even_when_configured(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    (project_root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[tool.engineeringagent.specs]",
                "allow-duplicate-done-base-ids-below = 100",
                "",
            ]
        ),
        encoding="utf-8",
    )
    features_done_dir = project_root / "docs" / "spec" / "features_done"
    features_done_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "id": "FEAT-150",
        "title": "Duplicate done id above threshold",
        "status": "done",
        "priority": "high",
        "objective": "Ensure threshold does not allow higher ids.",
        "acceptance": ["Validator rejects duplicates above threshold."],
        "subtasks": [
            {
                "id": "ST-001",
                "title": "Already complete",
                "status": "done",
                "verification": ["true"],
            }
        ],
    }

    (features_done_dir / "FEAT-150-one.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )
    (features_done_dir / "FEAT-150-two.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)
    assert any("duplicate base feature id" in message for message in messages)
    assert any("allow-duplicate-done-base-ids-below" in message for message in messages)


def test_pytest_default_coverage_contract_is_declared(repo_root: Path) -> None:
    pyproject_payload = tomli.loads(
        (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    pytest_options = pyproject_payload["tool"]["pytest"]["ini_options"]
    addopts = pytest_options["addopts"]

    assert "--cov=engineeringagent" in addopts
    assert "--cov-fail-under=95" in addopts
    assert "not integration" not in addopts
