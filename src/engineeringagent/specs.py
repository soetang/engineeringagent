from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Annotated, Literal, cast

from typing_extensions import LiteralString

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic_core import InitErrorDetails, PydanticCustomError


PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
JSON_SCHEMA_DRAFT_URL = "https://json-schema.org/draft/2020-12/schema"
ERR_DUP_SUBTASK_ID: LiteralString = "duplicate subtask id: {subtask_id}"


FeatureId = Annotated[
    str, Field(strict=True, min_length=1, pattern=r"^FEAT-[0-9]{3,}$")
]
SubtaskId = Annotated[str, Field(strict=True, min_length=1, pattern=r"^ST-[0-9]{3,}$")]
NonEmptyStr = Annotated[str, Field(strict=True, min_length=1)]
StrictString = Annotated[str, Field(strict=True)]
CommitSubject = Annotated[
    str,
    Field(
        strict=True,
        pattern=r"^(feat|fix|spec|docs|chore|test): [^\n]+$",
    ),
]


class StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FeatureStatus(str, Enum):
    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class FeaturePriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FeatureType(str, Enum):
    FEATURE = "feature"
    BUG = "bug"
    SPEC = "spec"
    DOCS = "docs"
    CHORE = "chore"
    TEST = "test"


class PotentialFeatureStatus(str, Enum):
    IDEA = "idea"


PotentialFeatureId = Annotated[
    str, Field(strict=True, min_length=1, pattern=r"^POT-[0-9]{3,}$")
]


class PotentialFeatureSpec(StrictContractModel):
    id: PotentialFeatureId
    title: NonEmptyStr
    status: PotentialFeatureStatus
    context: StrictString | None = None
    value: list[StrictString] | None = None
    acceptance_hint: list[StrictString] | None = None


class PotentialFeaturesDocument(StrictContractModel):
    version: Annotated[int, Field(strict=True, ge=1)]
    description: StrictString | None = None
    potential_features: list[PotentialFeatureSpec] = Field(default_factory=list)


class GateRunnerDefinition(StrictContractModel):
    type: Literal["command"]
    command: NonEmptyStr


class GateDefinition(StrictContractModel):
    run: NonEmptyStr | None = None
    runner: GateRunnerDefinition | None = None
    on_change: Annotated[list[NonEmptyStr], Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def enforce_runner_form(self) -> "GateDefinition":
        has_run = self.run is not None
        has_runner = self.runner is not None
        if has_run == has_runner:
            raise ValueError("define exactly one of run or runner")
        return self


class GateConfigDocument(StrictContractModel):
    contract_version: Literal["1.0"] = "1.0"
    profiles: dict[NonEmptyStr, list[NonEmptyStr]]
    gates: dict[NonEmptyStr, GateDefinition]


class ReviewerTriggerPhase(str, Enum):
    ITERATION_END = "iteration_end"
    FEATURE_DONE = "feature_done"


class ReviewerApprovalMode(str, Enum):
    ADVISORY = "advisory"
    BLOCKING = "blocking"


class ReviewerSandboxMode(str, Enum):
    TEMP_WORKTREE_SNAPSHOT = "temp_worktree_snapshot"
    EMPTY_FOLDER = "empty_folder"


class ReviewerTriggerDefinition(StrictContractModel):
    phase: ReviewerTriggerPhase
    on_change: Annotated[list[NonEmptyStr], Field(min_length=1)] | None = None


class ReviewerApprovalDefinition(StrictContractModel):
    mode: ReviewerApprovalMode = ReviewerApprovalMode.ADVISORY
    first_feature_approval: bool = True
    max_retries: Annotated[int, Field(strict=True, ge=0)] = 2
    continue_on_exhausted: bool = True


class ReviewerSandboxDefinition(StrictContractModel):
    mode: ReviewerSandboxMode
    assets: Annotated[list[NonEmptyStr], Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def enforce_assets_support(self) -> "ReviewerSandboxDefinition":
        if self.assets is None:
            return self
        if self.mode != ReviewerSandboxMode.EMPTY_FOLDER:
            raise ValueError(
                "sandbox.assets is only supported for sandbox.mode=empty_folder"
            )
        return self


class ReviewerDefinition(StrictContractModel):
    prompt_file: NonEmptyStr
    feedback_context: StrictString | None = None
    trigger: ReviewerTriggerDefinition
    approval: ReviewerApprovalDefinition = Field(
        default_factory=ReviewerApprovalDefinition
    )
    sandbox: ReviewerSandboxDefinition | None = None

    @model_validator(mode="after")
    def enforce_prompt_file_location(self) -> "ReviewerDefinition":
        prompt_path = Path(self.prompt_file)
        normalized_parts = [part for part in prompt_path.parts if part not in {"", "."}]
        if prompt_path.is_absolute() or any(part == ".." for part in prompt_path.parts):
            raise ValueError(
                "prompt_file must be a repo-relative path under harness/reviewers/prompts/"
            )
        if normalized_parts[:3] != ["harness", "reviewers", "prompts"]:
            raise ValueError(
                "prompt_file must be a repo-relative path under harness/reviewers/prompts/"
            )
        if len(normalized_parts) <= 3:
            raise ValueError(
                "prompt_file must reference a file under harness/reviewers/prompts/"
            )
        return self


class ReviewerConfigDocument(StrictContractModel):
    contract_version: Literal["1.0"] = "1.0"
    profiles: dict[NonEmptyStr, list[NonEmptyStr]]
    reviewers: dict[NonEmptyStr, ReviewerDefinition]


class SubtaskSpec(StrictContractModel):
    id: SubtaskId
    title: NonEmptyStr
    status: FeatureStatus
    context: StrictString | None = None
    constraints: list[StrictString] | None = None
    verification: Annotated[list[StrictString], Field(min_length=1)]
    attempts: Annotated[int, Field(strict=True, ge=0)] | None = None
    last_error: StrictString | None = None
    notes: list[StrictString] | None = None


class FeatureSpec(StrictContractModel):
    model_config = ConfigDict(extra="forbid", title="Agent Harness Feature")

    id: FeatureId
    title: NonEmptyStr
    type: FeatureType
    expected_commit_subject: CommitSubject
    status: FeatureStatus
    priority: FeaturePriority
    objective: NonEmptyStr
    context: StrictString | None = None
    constraints: list[StrictString] | None = None
    implementation_notes: StrictString | None = None
    acceptance: Annotated[list[StrictString], Field(min_length=1)]
    subtasks: list[SubtaskSpec] = Field(default_factory=list)
    updated_at: StrictString | None = None

    @model_validator(mode="after")
    def enforce_invariants(self) -> FeatureSpec:
        """Apply repository feature invariants in the model layer."""
        errors, in_progress_count, done_count = _collect_subtask_state(self.subtasks)
        errors.extend(
            _feature_status_alignment_errors(
                self.status,
                len(self.subtasks),
                in_progress_count,
                done_count,
            )
        )

        if errors:
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)

        return self


def _collect_subtask_state(
    subtasks: list[SubtaskSpec],
) -> tuple[
    list[InitErrorDetails],
    int,
    int,
]:
    errors: list[InitErrorDetails] = []
    subtask_ids: set[str] = set()
    in_progress_count = 0
    done_count = 0

    for idx, subtask in enumerate(subtasks):
        if subtask.id in subtask_ids:
            errors.append(
                _init_error_detail(
                    error=PydanticCustomError(
                        "value_error",
                        ERR_DUP_SUBTASK_ID,
                        {"subtask_id": subtask.id},
                    ),
                    loc=("subtasks", idx, "id"),
                    input_value=subtask.id,
                )
            )
        subtask_ids.add(subtask.id)

        if subtask.status == FeatureStatus.IN_PROGRESS:
            in_progress_count += 1
        if subtask.status == FeatureStatus.DONE:
            done_count += 1

    return (
        errors,
        in_progress_count,
        done_count,
    )


def _feature_status_alignment_errors(
    feature_status: FeatureStatus,
    subtask_count: int,
    in_progress_count: int,
    done_count: int,
) -> list[InitErrorDetails]:
    errors: list[InitErrorDetails] = []
    all_done = subtask_count > 0 and done_count == subtask_count
    any_in_progress = in_progress_count > 0

    if feature_status == FeatureStatus.DONE and not all_done:
        errors.append(
            _init_error_detail(
                error=PydanticCustomError(
                    "value_error", "feature status done requires all subtasks done"
                ),
                loc=("status",),
                input_value=feature_status,
            )
        )

    if any_in_progress and feature_status != FeatureStatus.IN_PROGRESS:
        errors.append(
            _init_error_detail(
                error=PydanticCustomError(
                    "value_error",
                    "feature with in_progress subtask must be in_progress",
                ),
                loc=("status",),
                input_value=feature_status,
            )
        )

    if all_done and feature_status != FeatureStatus.DONE:
        errors.append(
            _init_error_detail(
                error=PydanticCustomError(
                    "value_error", "feature with all subtasks done must be done"
                ),
                loc=("status",),
                input_value=feature_status,
            )
        )

    return errors


class ValidationIssue(StrictContractModel):
    path: str
    message: str


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping from disk.

    Args:
        path: Path to a YAML file.

    Returns:
        Parsed YAML mapping.

    Raises:
        ValueError: If YAML top level is not a mapping.
    """
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping at top level")
    return data


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a YAML mapping to disk.

    Args:
        path: Destination YAML file path.
        data: Mapping content to serialize.
    """
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=False)


def iter_feature_files(features_dir: Path) -> list[Path]:
    """Return sorted feature spec files from a directory.

    Args:
        features_dir: Directory containing feature YAML files.

    Returns:
        Sorted list of matching feature file paths.
    """
    return sorted(features_dir.glob("*.yaml"))


def load_schema(schema_path: Path) -> dict[str, Any]:
    """Load the JSON schema used for feature validation.

    Args:
        schema_path: Path to the schema JSON file.

    Returns:
        Parsed schema mapping.
    """
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def feature_schema_from_model() -> dict[str, Any]:
    """Return feature schema generated from the Pydantic feature model."""
    schema = FeatureSpec.model_json_schema(mode="validation")
    schema["$schema"] = JSON_SCHEMA_DRAFT_URL
    return schema


def _path_from_pydantic_loc(loc: tuple[Any, ...]) -> str:
    parts: list[str] = []
    for segment in loc:
        if isinstance(segment, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{segment}]"
            else:
                parts.append(f"[{segment}]")
            continue
        parts.append(str(segment))
    if not parts:
        return "<root>"
    return ".".join(parts).replace(".[", "[")


def _init_error_detail(
    *,
    error: PydanticCustomError,
    loc: tuple[Any, ...],
    input_value: Any,
) -> InitErrorDetails:
    return cast(
        InitErrorDetails,
        {
            "type": error,
            "loc": loc,
            "input": input_value,
        },
    )


def feature_contract_issues(
    feature: dict[str, Any], file_path: Path
) -> list[ValidationIssue]:
    """Collect strict contract validation issues for one feature document.

    Args:
        feature: Feature mapping to validate.
        file_path: Source path used in issue reporting.

    Returns:
        Validation issues produced by strict Pydantic contract checks.
    """
    return _model_contract_issues(
        model_type=FeatureSpec,
        payload=feature,
        file_path=file_path,
    )


def potential_features_contract_issues(
    document: dict[str, Any], file_path: Path
) -> list[ValidationIssue]:
    """Collect strict contract issues for potential features backlog YAML."""
    return _model_contract_issues(
        model_type=PotentialFeaturesDocument,
        payload=document,
        file_path=file_path,
    )


def gate_contract_issues(
    document: dict[str, Any], file_path: Path
) -> list[ValidationIssue]:
    """Collect strict contract issues for gate configuration YAML."""
    return _model_contract_issues(
        model_type=GateConfigDocument,
        payload=document,
        file_path=file_path,
    )


def reviewer_contract_issues(
    document: dict[str, Any], file_path: Path
) -> list[ValidationIssue]:
    """Collect strict contract issues for reviewer configuration YAML."""
    return _model_contract_issues(
        model_type=ReviewerConfigDocument,
        payload=document,
        file_path=file_path,
    )


def _model_contract_issues(
    model_type: type[BaseModel],
    payload: dict[str, Any],
    file_path: Path,
) -> list[ValidationIssue]:
    """Collect deterministic issues produced by strict model validation."""
    try:
        model_type.model_validate(payload)
    except ValidationError as exc:
        issues: list[ValidationIssue] = []
        errors = sorted(
            exc.errors(include_url=False),
            key=lambda err: _path_from_pydantic_loc(tuple(err.get("loc", ()))),
        )
        for error in errors:
            path = _path_from_pydantic_loc(tuple(error.get("loc", ())))
            issues.append(
                ValidationIssue(
                    path=f"{file_path}:{path}",
                    message=str(error.get("msg", "invalid value")),
                )
            )
        return issues
    return []


def feature_sort_key(feature: dict[str, Any]) -> tuple[int, str]:
    """Build a deterministic sort key for feature priority.

    Args:
        feature: Feature mapping with priority and id fields.

    Returns:
        Tuple used for ascending priority and id ordering.
    """
    priority = feature.get("priority", "medium")
    return (PRIORITY_ORDER.get(priority, 1), str(feature.get("id", "")))


def find_subtask(feature: dict[str, Any], status: str) -> dict[str, Any] | None:
    """Return the first matching subtask with a target status.

    Args:
        feature: Feature mapping containing subtasks.
        status: Desired subtask status to match.

    Returns:
        First matching subtask by document order, or None when absent.
    """
    subtasks = feature.get("subtasks", [])
    matches = [s for s in subtasks if s.get("status") == status]
    if not matches:
        return None
    return matches[0]
