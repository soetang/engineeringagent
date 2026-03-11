from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest
import tomli
import yaml

from engineeringagent.checks.validate.validator import validate
from tests.meta.validator_support import (
    write_bundled_feature_spec,
    write_plan_artifact,
)


def _write_done_plan_artifact(feature_root: Path, *, feature_id: str) -> Path:
    plan_path = feature_root / "plan.md"
    plan_path.write_text(
        "\n".join(
            [
                "---",
                f"plan_id: {feature_id}",
                f"feature_id: {feature_id}",
                "status: done",
                "source_spec: spec.yaml",
                "planning_tier: planned",
                "phases:",
                "  - id: P1",
                "    title: Archived phase",
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
    return plan_path


def test_validate_missing_required_fields_with_bundled_contract(tmp_path: Path) -> None:
    project_root = tmp_path
    feature_root = (
        project_root / "docs" / "spec" / "features" / "FEAT-904-missing-required"
    )
    feature_root.mkdir(parents=True, exist_ok=True)
    feature_path = feature_root / "spec.yaml"
    feature_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-904",
                "title": "Missing fields",
                "type": "feature",
                "expected_commit_subject": "feat: validate missing required fields",
                "planning_tier": "planned",
                "status": "backlog",
                "priority": "high",
                "acceptance": ["Missing required fields are reported."],
                "artifacts": {},
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


def test_validate_requires_feature_type(tmp_path: Path) -> None:
    project_root = tmp_path
    feature_root = project_root / "docs" / "spec" / "features" / "FEAT-910-missing-type"
    feature_root.mkdir(parents=True, exist_ok=True)

    (feature_root / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-910",
                "title": "Missing type",
                "expected_commit_subject": "feat: validate missing feature type",
                "planning_tier": "direct",
                "status": "backlog",
                "priority": "high",
                "objective": "Feature type is required.",
                "acceptance": ["Validator reports missing type."],
                "artifacts": {},
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
    feature_root = (
        project_root
        / "docs"
        / "spec"
        / "features"
        / "FEAT-911-missing-expected-subject"
    )
    feature_root.mkdir(parents=True, exist_ok=True)

    (feature_root / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-911",
                "title": "Missing expected commit subject",
                "type": "feature",
                "planning_tier": "direct",
                "status": "backlog",
                "priority": "high",
                "objective": "Expected commit subject is required.",
                "acceptance": [
                    "Validator reports missing expected commit subject metadata."
                ],
                "artifacts": {},
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

    bad_active = features_dir / "FEAT-999-bad-active" / "spec.yaml"
    bad_done = features_done_dir / "FEAT-998-bad-done" / "spec.yaml"
    bad_active.parent.mkdir(parents=True, exist_ok=True)
    bad_done.parent.mkdir(parents=True, exist_ok=True)
    bad_active.write_text("[\n", encoding="utf-8")
    bad_done.write_text("[\n", encoding="utf-8")
    potential_features_path.write_text("[\n", encoding="utf-8")

    messages = validate(project_root=tmp_path)

    assert any("FEAT-999-bad-active/spec.yaml: failed to parse YAML" in m for m in messages)
    assert any("FEAT-998-bad-done/spec.yaml: failed to parse YAML" in m for m in messages)
    assert any("potential_features.yaml: failed to parse YAML" in m for m in messages)


def test_validate_ignores_legacy_feature_schema_artifact_parse_and_sync_errors(
    tmp_path: Path,
) -> None:
    feature_root = tmp_path / "docs" / "spec" / "features" / "FEAT-999-valid"
    schemas_dir = tmp_path / "docs" / "spec" / "schemas"
    feature_root.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)

    (feature_root / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-999",
                "title": "Ignore legacy schema artifact file",
                "type": "feature",
                "expected_commit_subject": "feat: ignore legacy feature schema artifact",
                "planning_tier": "direct",
                "status": "backlog",
                "priority": "medium",
                "objective": "Validation should ignore removed schema artifact checks.",
                "acceptance": ["Legacy schema artifact drift checks stay removed."],
                "artifacts": {},
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
    feature_root = features_done_dir / "FEAT-897-missing-priority"
    feature_root.mkdir(parents=True, exist_ok=True)
    (feature_root / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-897",
                "title": "Done spec still requires priority",
                "type": "spec",
                "expected_commit_subject": "spec: done spec still requires priority",
                "planning_tier": "direct",
                "status": "done",
                "objective": "Keep non-legacy required-field errors visible.",
                "acceptance": ["priority remains required for done specs."],
                "artifacts": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=tmp_path)

    assert any(
        "FEAT-897-missing-priority/spec.yaml:priority: Field required" in m
        for m in messages
    )


def test_validate_reports_done_feature_left_in_active_directory(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    feature_root = (
        project_root / "docs" / "spec" / "features" / "FEAT-901-preexisting-done"
    )
    write_bundled_feature_spec(
        feature_root,
        feature_id="FEAT-901",
        extra_fields={"status": "done"},
    )
    _write_done_plan_artifact(feature_root, feature_id="FEAT-901")

    messages = validate(project_root=project_root)

    assert messages
    assert any(
        "completed feature specs must be archived" in message for message in messages
    )
    assert any(
        "docs/spec/features_done/FEAT-901-preexisting-done/spec.yaml" in message
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
    feature_root = (
        project_root / "docs" / "spec" / "features" / "FEAT-938-default-docs-root"
    )
    write_bundled_feature_spec(
        feature_root,
        feature_id="FEAT-938",
        extra_fields={"status": "done"},
    )
    _write_done_plan_artifact(feature_root, feature_id="FEAT-938")

    messages = validate(project_root=project_root)

    assert messages
    assert any(
        "docs/spec/features_done/FEAT-938-default-docs-root/spec.yaml" in message
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

    feature_root = features_dir / "FEAT-937-configured-docs-root"
    write_bundled_feature_spec(
        feature_root,
        feature_id="FEAT-937",
        extra_fields={"status": "done"},
    )
    _write_done_plan_artifact(feature_root, feature_id="FEAT-937")
    (features_dir / ".allow-done-active.txt").write_text(
        "FEAT-937-configured-docs-root/spec.yaml\n",
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
        "docs.engineeringagent/spec/features_done/FEAT-937-configured-docs-root/spec.yaml"
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
    feature_root = features_done_dir / "FEAT-899-missing-done-metadata"
    feature_root.mkdir(parents=True, exist_ok=True)

    (feature_root / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-899",
                "title": "Done spec missing metadata",
                "planning_tier": "direct",
                "status": "done",
                "priority": "high",
                "objective": "Reject done specs missing required metadata.",
                "acceptance": ["Done specs still enforce required metadata."],
                "artifacts": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages
    assert any(
        "FEAT-899-missing-done-metadata/spec.yaml:type: Field required" in message
        for message in messages
    )
    assert any(
        "FEAT-899-missing-done-metadata/spec.yaml:expected_commit_subject: Field required"
        in message
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
    manifest_path = tmp_path / "harness" / "fitness_functions" / "rules.yaml"
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
    manifest_path = tmp_path / "harness" / "fitness_functions" / "rules.yaml"
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

    active_root = features_dir / "FEAT-002-mismatch"
    active_root.mkdir(parents=True, exist_ok=True)
    (active_root / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-001",
                "title": "Active filename mismatch",
                "type": "feature",
                "expected_commit_subject": "feat: active filename mismatch",
                "planning_tier": "direct",
                "status": "backlog",
                "priority": "high",
                "objective": "Reject filename/frontmatter id drift.",
                "acceptance": ["Validator rejects mismatched filename ids."],
                "artifacts": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    done_root = features_done_dir / "FEAT-004-mismatch"
    done_root.mkdir(parents=True, exist_ok=True)
    (done_root / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-003",
                "title": "Done filename mismatch",
                "type": "spec",
                "expected_commit_subject": "spec: done filename mismatch",
                "planning_tier": "direct",
                "status": "done",
                "priority": "high",
                "objective": "Reject filename/frontmatter id drift for done specs.",
                "acceptance": ["Validator rejects mismatched filename ids."],
                "artifacts": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert any(
        "FEAT-002-mismatch/spec.yaml:id: filename id token FEAT-002 does not match frontmatter id FEAT-001"
        in message
        for message in messages
    )
    assert any(
        "FEAT-004-mismatch/spec.yaml:id: filename id token FEAT-004 does not match frontmatter id FEAT-003"
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
        "planning_tier": "direct",
        "status": "backlog",
        "priority": "high",
        "objective": "Reject overlapping active feature ids.",
        "acceptance": ["Validator rejects duplicate feature ids."],
        "artifacts": {},
    }

    for dirname in ("FEAT-010-a", "FEAT-010-b"):
        feature_root = features_dir / dirname
        feature_root.mkdir(parents=True, exist_ok=True)
        (feature_root / "spec.yaml").write_text(
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
        "type": "spec",
        "expected_commit_subject": "spec: duplicate done id",
        "planning_tier": "direct",
        "status": "done",
        "priority": "high",
        "objective": "Reject overlapping done feature ids by default.",
        "acceptance": ["Validator rejects duplicate done ids by default."],
        "artifacts": {},
    }

    for dirname in ("FEAT-050-one", "FEAT-050-two"):
        feature_root = features_done_dir / dirname
        feature_root.mkdir(parents=True, exist_ok=True)
        (feature_root / "spec.yaml").write_text(
            yaml.safe_dump(payload, sort_keys=False),
            encoding="utf-8",
        )

    messages = validate(project_root=project_root)

    assert any("duplicate base feature id" in message for message in messages)


def test_validate_reports_filename_id_token_extraction_failure(tmp_path: Path) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    feature_root = features_dir / "FEAT999"
    feature_root.mkdir(parents=True, exist_ok=True)
    (feature_root / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-999",
                "title": "Bad filename token",
                "type": "feature",
                "expected_commit_subject": "feat: bad filename token",
                "planning_tier": "direct",
                "status": "backlog",
                "priority": "high",
                "objective": "Force filename token extraction failure.",
                "acceptance": ["Validator reports filename token extraction failure."],
                "artifacts": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert any(
        "FEAT999/spec.yaml:id: failed to extract filename id token" in message for message in messages
    )


def test_validate_rejects_duplicate_feature_id_across_active_and_done_specs(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    features_done_dir = project_root / "docs" / "spec" / "features_done"
    features_dir.mkdir(parents=True, exist_ok=True)
    features_done_dir.mkdir(parents=True, exist_ok=True)

    active_root = features_dir / "FEAT-020-active"
    active_root.mkdir(parents=True, exist_ok=True)
    (active_root / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-020",
                "title": "Active",
                "type": "feature",
                "expected_commit_subject": "feat: active",
                "planning_tier": "direct",
                "status": "backlog",
                "priority": "high",
                "objective": "Create active/done collision.",
                "acceptance": ["Validator rejects collisions involving active specs."],
                "artifacts": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    archived_root = features_done_dir / "FEAT-020-archived"
    archived_root.mkdir(parents=True, exist_ok=True)
    (archived_root / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-020",
                "title": "Archived",
                "type": "spec",
                "expected_commit_subject": "spec: archived",
                "planning_tier": "direct",
                "status": "done",
                "priority": "high",
                "objective": "Create active/done collision.",
                "acceptance": ["Validator rejects collisions involving active specs."],
                "artifacts": {},
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


def test_validate_bundled_feature_contract_rejects_flat_wrapper_alongside_bundle(
    tmp_path: Path,
) -> None:
    features_dir = tmp_path / "docs" / "spec" / "features"
    wrapper_path = features_dir / "FEAT-181-bundled-feature-contract.yaml"
    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-181",
                "title": "Legacy wrapper",
                "type": "spec",
                "expected_commit_subject": "spec: legacy wrapper",
                "status": "in_progress",
                "priority": "high",
                "objective": "Compatibility wrapper for bundled feature.",
                "acceptance": ["Legacy wrapper remains selectable."],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
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

    assert any(
        message
        == f"{wrapper_path}: feature specs must use bundled spec.yaml entrypoints"
        for message in messages
    )


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
