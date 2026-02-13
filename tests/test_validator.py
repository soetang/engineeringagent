from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from engineeringagent.fitness import DEPENDENCY_DIRECTIONALITY_RULE_ID
from engineeringagent.specs import feature_schema_from_model
from engineeringagent.validator import _iter_agents_docs_map_references, validate


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SOURCE = REPO_ROOT / "docs" / "spec" / "schemas" / "feature.schema.json"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "specs" / "invalid"


def _make_invalid_project(tmp_path: Path, fixture_name: str) -> Path:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    schema_target = project_root / "docs" / "spec" / "schemas" / "feature.schema.json"

    features_dir.mkdir(parents=True, exist_ok=True)
    schema_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCHEMA_SOURCE, schema_target)
    shutil.copy2(FIXTURES_DIR / fixture_name, features_dir / f"{fixture_name}")

    return project_root


@pytest.mark.parametrize(
    ("fixture_name", "expected"),
    [
        ("missing-objective.yaml", "Field required"),
        ("bad-status.yaml", "Input should be 'backlog'"),
        ("illegal-transition.yaml", "feature status done requires all subtasks done"),
    ],
)
def test_invalid_spec_fixtures_report_clear_errors(
    tmp_path: Path,
    fixture_name: str,
    expected: str,
) -> None:
    project_root = _make_invalid_project(tmp_path, fixture_name)

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
        "subtasks[0].order" in message and "valid integer" in message
        for message in messages
    )
    assert any(
        "unknown_field" in message and "Extra inputs are not permitted" in message
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
                        "order": 1,
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


def test_feature_schema_artifact_generated_from_pydantic_model() -> None:
    schema_payload = json.loads(SCHEMA_SOURCE.read_text(encoding="utf-8"))
    assert schema_payload == feature_schema_from_model()


def test_validate_reports_done_feature_left_in_active_directory(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    schema_target = project_root / "docs" / "spec" / "schemas" / "feature.schema.json"

    features_dir.mkdir(parents=True, exist_ok=True)
    schema_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCHEMA_SOURCE, schema_target)

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
                        "order": 1,
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


def test_validate_transitional_policy_for_preexisting_done_features(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    schema_target = project_root / "docs" / "spec" / "schemas" / "feature.schema.json"

    features_dir.mkdir(parents=True, exist_ok=True)
    schema_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCHEMA_SOURCE, schema_target)

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
                        "order": 1,
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

    assert messages == []


def test_validate_allows_legacy_done_specs_missing_new_metadata(tmp_path: Path) -> None:
    project_root = tmp_path
    features_done_dir = project_root / "docs" / "spec" / "features_done"
    schema_target = project_root / "docs" / "spec" / "schemas" / "feature.schema.json"

    features_done_dir.mkdir(parents=True, exist_ok=True)
    schema_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCHEMA_SOURCE, schema_target)

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
                        "order": 1,
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages == []


def test_validate_preserves_subtask_order_and_done_prefix_rules(tmp_path: Path) -> None:
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
                        "order": 1,
                        "verification": ["true"],
                    },
                    {
                        "id": "ST-002",
                        "title": "Second",
                        "status": "backlog",
                        "order": 3,
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
                        "order": 1,
                        "verification": ["true"],
                    },
                    {
                        "id": "ST-002",
                        "title": "Second",
                        "status": "done",
                        "order": 2,
                        "verification": ["true"],
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert any(
        "subtask order values must be contiguous and start at 1" in message
        for message in messages
    )
    assert any(
        "done subtasks must form a contiguous prefix by order" in message
        for message in messages
    )


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
                        "order": 1,
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
                        "order": 1,
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    (features_dir / "FEAT-909-all-done-not-done-feature.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-909",
                "title": "All done but feature not done",
                "type": "feature",
                "expected_commit_subject": "feat: preserve all done status invariant",
                "status": "in_progress",
                "priority": "high",
                "objective": "Preserve all-done status invariant.",
                "acceptance": ["Validator reports all-done mismatch."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Complete",
                        "status": "done",
                        "order": 1,
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
    assert any(
        "feature with all subtasks done must be done" in message for message in messages
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

    references = _iter_agents_docs_map_references(tmp_path)

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

    references = _iter_agents_docs_map_references(tmp_path)

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

    first = _iter_agents_docs_map_references(tmp_path)
    second = _iter_agents_docs_map_references(tmp_path)

    assert first == [
        (4, "docs/a-first.md"),
        (4, "docs/z-last.md"),
        (5, "docs/m-middle.md"),
    ]
    assert second == first


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


def test_validate_reports_unknown_builtin_fitness_reference(tmp_path: Path) -> None:
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

    assert messages == [
        (
            "unknown builtin fitness rule reference 'unknown.rule' at "
            f"{manifest_path}:rules[0]"
        )
    ]


def test_validate_accepts_known_builtin_fitness_reference(tmp_path: Path) -> None:
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "contract_version": "1.0",
                "rules": [{"builtin": DEPENDENCY_DIRECTIONALITY_RULE_ID}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=tmp_path)

    assert messages == []
