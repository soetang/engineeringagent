from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Annotated, cast

from typing_extensions import LiteralString

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic_core import InitErrorDetails, PydanticCustomError


PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
JSON_SCHEMA_DRAFT_URL = "https://json-schema.org/draft/2020-12/schema"
ERR_DUP_SUBTASK_ID: LiteralString = "duplicate subtask id: {subtask_id}"
ERR_DUP_SUBTASK_ORDER: LiteralString = "duplicate order: {order}"
ERR_ORDER_SEQUENCE: LiteralString = (
    "subtask order values must be contiguous and start at 1 "
    "(expected {expected}, got {got})"
)
ERR_DONE_PREFIX: LiteralString = (
    "done subtasks must form a contiguous prefix by order; "
    "order {order} cannot be done when earlier subtasks are not done"
)


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


class GateDefinition(StrictContractModel):
    run: NonEmptyStr


class GateConfigDocument(StrictContractModel):
    profiles: dict[NonEmptyStr, list[NonEmptyStr]]
    gates: dict[NonEmptyStr, GateDefinition]


class SubtaskSpec(StrictContractModel):
    id: SubtaskId
    title: NonEmptyStr
    status: FeatureStatus
    order: Annotated[int, Field(strict=True, ge=1)]
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
        errors: list[InitErrorDetails] = []

        subtask_ids: set[str] = set()
        subtask_orders: set[int] = set()
        in_progress_count = 0
        done_count = 0
        ordered_subtasks: list[tuple[int, int, SubtaskSpec]] = []

        for idx, subtask in enumerate(self.subtasks):
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

            if subtask.order in subtask_orders:
                errors.append(
                    _init_error_detail(
                        error=PydanticCustomError(
                            "value_error",
                            ERR_DUP_SUBTASK_ORDER,
                            {"order": subtask.order},
                        ),
                        loc=("subtasks", idx, "order"),
                        input_value=subtask.order,
                    )
                )
            subtask_orders.add(subtask.order)

            ordered_subtasks.append((subtask.order, idx, subtask))

            if subtask.status == FeatureStatus.IN_PROGRESS:
                in_progress_count += 1
            if subtask.status == FeatureStatus.DONE:
                done_count += 1

        if in_progress_count > 1:
            errors.append(
                _init_error_detail(
                    error=PydanticCustomError(
                        "value_error",
                        "at most one subtask can be in_progress per feature",
                    ),
                    loc=("subtasks",),
                    input_value=[subtask.status for subtask in self.subtasks],
                )
            )

        if subtask_orders:
            expected = set(range(1, len(self.subtasks) + 1))
            if subtask_orders != expected:
                errors.append(
                    _init_error_detail(
                        error=PydanticCustomError(
                            "value_error",
                            ERR_ORDER_SEQUENCE,
                            {
                                "expected": sorted(expected),
                                "got": sorted(subtask_orders),
                            },
                        ),
                        loc=("subtasks",),
                        input_value=sorted(subtask_orders),
                    )
                )

        seen_non_done = False
        for order, idx, subtask in sorted(ordered_subtasks, key=lambda item: item[0]):
            if subtask.status != FeatureStatus.DONE:
                seen_non_done = True
            elif seen_non_done:
                errors.append(
                    _init_error_detail(
                        error=PydanticCustomError(
                            "value_error",
                            ERR_DONE_PREFIX,
                            {"order": order},
                        ),
                        loc=("subtasks", idx, "status"),
                        input_value=subtask.status,
                    )
                )

        subtask_count = len(self.subtasks)
        all_done = subtask_count > 0 and done_count == subtask_count
        any_in_progress = in_progress_count > 0

        if self.status == FeatureStatus.DONE and not all_done:
            errors.append(
                _init_error_detail(
                    error=PydanticCustomError(
                        "value_error", "feature status done requires all subtasks done"
                    ),
                    loc=("status",),
                    input_value=self.status,
                )
            )

        if any_in_progress and self.status != FeatureStatus.IN_PROGRESS:
            errors.append(
                _init_error_detail(
                    error=PydanticCustomError(
                        "value_error",
                        "feature with in_progress subtask must be in_progress",
                    ),
                    loc=("status",),
                    input_value=self.status,
                )
            )

        if all_done and self.status != FeatureStatus.DONE:
            errors.append(
                _init_error_detail(
                    error=PydanticCustomError(
                        "value_error", "feature with all subtasks done must be done"
                    ),
                    loc=("status",),
                    input_value=self.status,
                )
            )

        if errors:
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)

        return self


@dataclass
class ValidationIssue:
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
    """Return the earliest-ordered subtask with a target status.

    Args:
        feature: Feature mapping containing subtasks.
        status: Desired subtask status to match.

    Returns:
        First matching subtask by order, or None when absent.
    """
    subtasks = feature.get("subtasks", [])
    matches = [s for s in subtasks if s.get("status") == status]
    if not matches:
        return None
    return sorted(matches, key=lambda s: int(s.get("order", 1_000_000)))[0]
