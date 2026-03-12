"""Filesystem-backed feature specification repository adapter."""

from __future__ import annotations

import errno
from pathlib import Path
import shutil

from engineeringagent.adapters.config import resolve_specifications_root
from engineeringagent.domain.specification import (
    FeatureArtifacts,
    FeaturePriority,
    FeatureSelectionCandidate,
    FeatureSpecification,
    FeatureStatus,
    FeatureType,
    PlanningTier,
)
from engineeringagent.ports import FeatureSpecificationRepository, ValidationFailure
from engineeringagent.specs import (
    dump_yaml,
    feature_contract_issues,
    iter_feature_files,
    load_markdown_frontmatter,
    load_yaml,
    resolve_feature_package_paths,
)

_PORT_NAME = "FeatureSpecificationRepository"
_PRIORITY_ORDER = {
    FeaturePriority.HIGH: 0,
    FeaturePriority.MEDIUM: 1,
    FeaturePriority.LOW: 2,
}


class FilesystemFeatureSpecificationRepository(FeatureSpecificationRepository):
    """Persist bundled `docs/spec/features/*/spec.yaml` feature packages."""

    def list_selection_candidates(
        self,
        project_root: Path,
    ) -> tuple[FeatureSelectionCandidate, ...]:
        """Return active feature candidates sorted by priority and id."""
        candidates = [
            _build_selection_candidate(
                spec_path=spec_path,
                payload=_load_valid_feature_payload(spec_path),
            )
            for spec_path in iter_feature_files(_active_features_root(project_root))
        ]
        return tuple(
            sorted(
                candidates,
                key=lambda candidate: (
                    _PRIORITY_ORDER[candidate.priority],
                    candidate.feature_id,
                ),
            )
        )

    def load(self, project_root: Path, feature_id: str) -> FeatureSpecification:
        """Load one specification by feature id from the active or archive roots."""
        spec_path = _find_feature_spec_path(project_root, feature_id)
        payload = _load_valid_feature_payload(spec_path)
        return _build_feature_specification(payload)

    def save(
        self,
        project_root: Path,
        feature_id: str,
        specification: FeatureSpecification,
    ) -> None:
        """Persist the specification YAML back to its resolved package entrypoint."""
        if specification.feature_id != feature_id:
            raise ValidationFailure(
                _PORT_NAME,
                "feature specification error: feature_id does not match save target",
            )
        spec_path = _find_feature_spec_path(project_root, feature_id)
        dump_yaml(spec_path, _serialize_feature_specification(specification))

    def archive(self, project_root: Path, feature_id: str) -> None:
        """Move one active feature package into docs/spec/features_done."""
        spec_path = _find_feature_spec_path(project_root, feature_id, active_only=True)
        package_paths = resolve_feature_package_paths(
            _active_features_root(project_root),
            _archived_features_root(project_root),
            spec_path,
        )
        if package_paths.archive_root.exists():
            raise ValidationFailure(
                _PORT_NAME,
                (
                    "feature specification error: archive destination already exists "
                    f"for {feature_id}"
                ),
            )
        package_paths.archive_root.parent.mkdir(parents=True, exist_ok=True)
        _move_path(package_paths.active_root, package_paths.archive_root)


def _active_features_root(project_root: Path) -> Path:
    return resolve_specifications_root(project_root).joinpath("features")


def _archived_features_root(project_root: Path) -> Path:
    return resolve_specifications_root(project_root).joinpath("features_done")


def _find_feature_spec_path(
    project_root: Path,
    feature_id: str,
    *,
    active_only: bool = False,
) -> Path:
    candidate_roots = [_active_features_root(project_root)]
    if not active_only:
        candidate_roots.append(_archived_features_root(project_root))
    for root in candidate_roots:
        for spec_path in iter_feature_files(root):
            payload = load_yaml(spec_path)
            if payload.get("id") == feature_id:
                return spec_path
    raise ValidationFailure(
        _PORT_NAME,
        f"feature specification error: missing bundled spec.yaml for {feature_id}",
    )


def _load_valid_feature_payload(spec_path: Path) -> dict[str, object]:
    payload = load_yaml(spec_path)
    issues = feature_contract_issues(payload, spec_path)
    if issues:
        messages = "; ".join(f"{issue.path}: {issue.message}" for issue in issues)
        raise ValidationFailure(
            _PORT_NAME,
            f"feature specification error: invalid feature package: {messages}",
        )
    return payload


def _build_feature_specification(payload: dict[str, object]) -> FeatureSpecification:
    artifacts_payload = payload.get("artifacts")
    supporting: tuple[str, ...] = ()
    if isinstance(artifacts_payload, dict):
        raw_supporting = artifacts_payload.get("supporting")
        if isinstance(raw_supporting, list):
            supporting = tuple(
                item.strip()
                for item in raw_supporting
                if isinstance(item, str) and item.strip()
            )
    return FeatureSpecification(
        feature_id=str(payload["id"]),
        title=str(payload["title"]),
        feature_type=FeatureType(str(payload["type"])),
        expected_commit_subject=str(payload["expected_commit_subject"]),
        planning_tier=PlanningTier(str(payload["planning_tier"])),
        status=FeatureStatus(str(payload["status"])),
        priority=FeaturePriority(str(payload["priority"])),
        objective=str(payload["objective"]),
        context=_optional_str(payload.get("context")),
        constraints=_string_tuple(payload.get("constraints")),
        implementation_notes=_optional_str(payload.get("implementation_notes")),
        acceptance=_string_tuple(payload.get("acceptance")),
        artifacts=FeatureArtifacts(
            plan=_artifact_ref(artifacts_payload, "plan"),
            research=_artifact_ref(artifacts_payload, "research"),
            supporting=supporting,
        ),
        updated_at=_optional_str(payload.get("updated_at")),
    )


def _build_selection_candidate(
    *,
    spec_path: Path,
    payload: dict[str, object],
) -> FeatureSelectionCandidate:
    specification = _build_feature_specification(payload)
    next_phase_id, dependencies_satisfied = _resolve_next_phase(spec_path, payload)
    return FeatureSelectionCandidate(
        feature_id=specification.feature_id,
        status=specification.status,
        priority=specification.priority,
        planning_tier=specification.planning_tier,
        next_phase_id=next_phase_id,
        phase_dependencies_satisfied=dependencies_satisfied,
        block_reason_code=_block_reason_code(specification.status),
    )


def _resolve_next_phase(
    spec_path: Path,
    payload: dict[str, object],
) -> tuple[str | None, bool]:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        return (None, True)
    plan_ref = artifacts.get("plan")
    if not isinstance(plan_ref, str) or not plan_ref.strip():
        return (None, True)
    plan_path = spec_path.parent / plan_ref.strip()
    if not plan_path.is_file():
        return (None, False)

    frontmatter = load_markdown_frontmatter(plan_path)
    raw_phases = frontmatter.get("phases")
    if not isinstance(raw_phases, list):
        return (None, True)

    all_previous_done = True
    for raw_phase in raw_phases:
        if not isinstance(raw_phase, dict):
            continue
        phase_id = _optional_str(raw_phase.get("id"))
        if phase_id is None:
            continue
        phase_status = _optional_str(raw_phase.get("status"))
        if phase_status == "done":
            continue
        return (phase_id, all_previous_done)
    return (None, True)


def _block_reason_code(status: FeatureStatus) -> str | None:
    if status == FeatureStatus.BLOCKED:
        return "feature_blocked"
    if status == FeatureStatus.DONE:
        return "feature_done"
    return None


def _serialize_feature_specification(
    specification: FeatureSpecification,
) -> dict[str, object]:
    artifacts: dict[str, object] = {}
    if specification.artifacts.plan is not None:
        artifacts["plan"] = specification.artifacts.plan
    if specification.artifacts.research is not None:
        artifacts["research"] = specification.artifacts.research
    if specification.artifacts.supporting:
        artifacts["supporting"] = list(specification.artifacts.supporting)

    payload: dict[str, object] = {
        "id": specification.feature_id,
        "title": specification.title,
        "type": specification.feature_type.value,
        "expected_commit_subject": specification.expected_commit_subject,
        "planning_tier": specification.planning_tier.value,
        "status": specification.status.value,
        "priority": specification.priority.value,
        "objective": specification.objective,
        "acceptance": list(specification.acceptance),
        "artifacts": artifacts,
    }
    if specification.context is not None:
        payload["context"] = specification.context
    if specification.constraints:
        payload["constraints"] = list(specification.constraints)
    if specification.implementation_notes is not None:
        payload["implementation_notes"] = specification.implementation_notes
    if specification.updated_at is not None:
        payload["updated_at"] = specification.updated_at
    return payload


def _artifact_ref(
    artifacts_payload: object,
    key: str,
) -> str | None:
    if not isinstance(artifacts_payload, dict):
        return None
    return _optional_str(artifacts_payload.get(key))


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _optional_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _move_path(source: Path, destination: Path) -> None:
    try:
        source.rename(destination)
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
        shutil.move(str(source), str(destination))
