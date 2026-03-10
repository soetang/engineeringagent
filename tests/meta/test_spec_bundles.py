from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from pydantic import BaseModel

from engineeringagent import spec_bundles


def _write_flat_feature(path: Path) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "FEAT-900",
        "title": "Flat feature",
        "type": "spec",
        "expected_commit_subject": "spec: flat feature",
        "status": "backlog",
        "priority": "high",
        "objective": "Exercise legacy subtask progress.",
        "acceptance": ["Flat features keep subtask progress."],
        "subtasks": [
            {
                "id": "ST-001",
                "title": "Legacy unit",
                "status": "backlog",
                "context": "Legacy progress surface.",
                "verification": ["uv run pytest -q"],
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return payload


def _write_bundled_feature(feature_root: Path) -> tuple[Path, dict[str, object]]:
    spec_path = feature_root / "spec.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "id": "FEAT-181",
        "title": "Bundled feature",
        "type": "spec",
        "expected_commit_subject": "spec: bundled feature contract",
        "planning_tier": "planned",
        "status": "backlog",
        "priority": "high",
        "objective": "Validate bundled feature packages.",
        "acceptance": ["Validator enforces bundled feature contracts."],
        "artifacts": {"plan": "plan.md"},
    }
    spec_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    (feature_root / "plan.md").write_text(
        "---\n"
        "plan_id: FEAT-181\n"
        "feature_id: FEAT-181\n"
        "status: backlog\n"
        "source_spec: spec.yaml\n"
        "planning_tier: planned\n"
        "phases:\n"
        "  - id: P1\n"
        "    title: First phase\n"
        "    status: pending\n"
        "    verification:\n"
        "      - uv run pytest -q\n"
        "---\n"
        "# Plan\n",
        encoding="utf-8",
    )
    return spec_path, payload


def test_feature_progress_kind_tracks_bundled_plan_artifacts(tmp_path: Path) -> None:
    flat_feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-900-flat.yaml"
    flat_feature_payload = _write_flat_feature(flat_feature_path)
    bundled_spec_path, bundled_feature_payload = _write_bundled_feature(
        tmp_path / "docs" / "spec" / "features" / "FEAT-181-bundled-feature-contract"
    )

    assert (
        spec_bundles.feature_progress_kind(flat_feature_path, flat_feature_payload)
        == "subtask"
    )
    assert (
        spec_bundles.feature_progress_kind(bundled_spec_path, bundled_feature_payload)
        == "phase"
    )


def test_feature_progress_kind_uses_feature_surface_for_direct_bundles(
    tmp_path: Path,
) -> None:
    feature_root = tmp_path / "docs" / "spec" / "features" / "FEAT-182-direct-bundle"
    spec_path = feature_root / "spec.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "id": "FEAT-182",
        "title": "Direct bundled feature",
        "type": "spec",
        "expected_commit_subject": "spec: direct bundled feature contract",
        "planning_tier": "direct",
        "status": "backlog",
        "priority": "high",
        "objective": "Validate bundled direct feature progress wording.",
        "acceptance": ["Bundled direct features do not fall back to subtasks."],
        "artifacts": {},
    }
    spec_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    assert spec_bundles.feature_progress_kind(spec_path, payload) == "feature"


def test_plan_artifact_issues_validate_plan_linkage_via_shared_module_import(
    tmp_path: Path,
) -> None:
    spec_path, feature_payload = _write_bundled_feature(
        tmp_path / "docs" / "spec" / "features" / "FEAT-181-bundled-feature-contract"
    )

    issues = spec_bundles.plan_artifact_issues(spec_path, feature_payload, "plan.md")

    assert issues == []


def test_plan_artifact_issues_bootstraps_spec_contracts_when_registry_is_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, feature_payload = _write_bundled_feature(
        tmp_path / "docs" / "spec" / "features" / "FEAT-181-bundled-feature-contract"
    )

    spec_bundles.reset_spec_contracts_for_testing()

    issues = spec_bundles.plan_artifact_issues(spec_path, feature_payload, "plan.md")

    assert issues == []


def test_bootstrap_spec_contracts_accepts_public_model_contract_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    class DummyModel(BaseModel):
        pass

    def build_issue(path: str, message: str) -> object:
        return SimpleNamespace(path=path, message=message)

    def model_contract_issues(
        model_type: object,
        payload: dict[str, object],
        file_path: Path,
    ) -> list[object]:
        captured["call"] = {
            "model_type": model_type,
            "payload": payload,
            "file_path": file_path,
        }
        return []

    stub_specs_module = SimpleNamespace(
        PlanningTier=object(),
        ValidationIssue=object(),
        FeaturePlanArtifact=object(),
        build_validation_issue=build_issue,
        model_contract_issues=model_contract_issues,
    )

    def import_specs_module(_name: str) -> SimpleNamespace:
        return stub_specs_module

    spec_bundles.reset_spec_contracts_for_testing()
    monkeypatch.setattr(spec_bundles, "import_module", import_specs_module)

    try:
        spec_bundles.bootstrap_spec_contracts()
        issues = spec_bundles.model_contract_issues_for_bundle(
            model_type=DummyModel,
            payload={"id": "FEAT-181"},
            file_path=Path("docs/spec/features/FEAT-181-example/spec.yaml"),
        )

        assert issues == []
        assert captured["call"] == {
            "model_type": DummyModel,
            "payload": {"id": "FEAT-181"},
            "file_path": Path("docs/spec/features/FEAT-181-example/spec.yaml"),
        }
    finally:
        monkeypatch.undo()
        spec_bundles.reset_spec_contracts_for_testing()
        spec_bundles.bootstrap_spec_contracts()


def test_resolve_compatibility_wrapper_canonical_spec_path_points_to_bundle(
    tmp_path: Path,
) -> None:
    wrapper_path = tmp_path / "docs" / "spec" / "features" / "FEAT-181-example.yaml"
    canonical_root = tmp_path / "docs" / "spec" / "features" / "FEAT-181-example"
    _write_flat_feature(wrapper_path)
    _write_bundled_feature(canonical_root)

    resolved = spec_bundles.resolve_compatibility_wrapper_canonical_spec_path(
        wrapper_path
    )

    assert resolved == canonical_root / "spec.yaml"


def test_resolve_compatibility_wrapper_canonical_spec_path_ignores_bundled_entrypoint(
    tmp_path: Path,
) -> None:
    spec_path, _payload = _write_bundled_feature(
        tmp_path / "docs" / "spec" / "features" / "FEAT-181-example"
    )

    resolved = spec_bundles.resolve_compatibility_wrapper_canonical_spec_path(
        spec_path
    )

    assert resolved is None


def test_compatibility_wrapper_plan_mirror_issues_report_title_and_verification_drift(
    tmp_path: Path,
) -> None:
    wrapper_path = tmp_path / "docs" / "spec" / "features" / "FEAT-181-example.yaml"
    canonical_root = tmp_path / "docs" / "spec" / "features" / "FEAT-181-example"
    wrapper_payload = _write_flat_feature(wrapper_path)
    _write_bundled_feature(canonical_root)

    wrapper_payload["subtasks"] = [
        {
            "id": "ST-001",
            "title": "Legacy unit",
            "status": "backlog",
            "context": "Legacy progress surface.",
            "verification": ["uv run pytest -q tests/unit/test_legacy.py"],
        }
    ]
    wrapper_path.write_text(
        yaml.safe_dump(wrapper_payload, sort_keys=False), encoding="utf-8"
    )

    issues = spec_bundles.compatibility_wrapper_plan_mirror_issues(
        wrapper_path,
        wrapper_payload,
    )

    assert issues == [
        (
            "docs/spec/features/FEAT-181-example.yaml subtask ST-001 title "
            "must mirror bundled phase P1 title"
        ),
        (
            "docs/spec/features/FEAT-181-example.yaml subtask ST-001 status "
            "must mirror bundled phase P1 status"
        ),
        (
            "docs/spec/features/FEAT-181-example.yaml subtask ST-001 verification "
            "must mirror bundled phase P1 verification"
        ),
    ]


def test_compatibility_wrapper_plan_mirror_issues_report_status_drift(
    tmp_path: Path,
) -> None:
    wrapper_path = tmp_path / "docs" / "spec" / "features" / "FEAT-181-example.yaml"
    canonical_root = tmp_path / "docs" / "spec" / "features" / "FEAT-181-example"
    wrapper_payload = _write_flat_feature(wrapper_path)
    _write_bundled_feature(canonical_root)

    wrapper_payload["subtasks"] = [
        {
            "id": "ST-001",
            "title": "First phase",
            "status": "in_progress",
            "context": "Legacy progress surface.",
            "verification": ["uv run pytest -q"],
        }
    ]
    wrapper_path.write_text(
        yaml.safe_dump(wrapper_payload, sort_keys=False), encoding="utf-8"
    )

    issues = spec_bundles.compatibility_wrapper_plan_mirror_issues(
        wrapper_path,
        wrapper_payload,
    )

    assert issues == [
        (
            "docs/spec/features/FEAT-181-example.yaml subtask ST-001 status "
            "must mirror bundled phase P1 status"
        )
    ]


@pytest.mark.parametrize(
    ("progress_kind", "expected"),
    [
        pytest.param(None, "subtask", id="missing"),
        pytest.param("feature", "implementation step", id="feature"),
        pytest.param("phase", "phase", id="phase"),
        pytest.param("subtask", "subtask", id="subtask"),
        pytest.param("unexpected", "subtask", id="fallback"),
    ],
)
def test_progress_kind_label_normalizes_unknown_values(
    progress_kind: str | None,
    expected: str,
) -> None:
    assert spec_bundles.progress_kind_label(progress_kind) == expected
