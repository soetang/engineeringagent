"""Quality-domain checks catalog models."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)
from pydantic_core import InitErrorDetails, PydanticCustomError

from .checks import HarnessCheckPhase

NonEmptyStr = Annotated[str, Field(strict=True, min_length=1)]
StrictString = Annotated[str, Field(strict=True)]


class StrictContractModel(BaseModel):
    """Pydantic base model that forbids unknown fields."""

    model_config = ConfigDict(extra="forbid")


class ReviewerSandboxMode(str, Enum):
    """Sandbox strategy for running reviewer agents."""

    TEMP_WORKTREE_SNAPSHOT = "temp_worktree_snapshot"
    EMPTY_FOLDER = "empty_folder"


class ReviewerApprovalDefinition(StrictContractModel):
    """Approval policy for reviewer results."""

    first_feature_approval: bool = True


class ReviewerSandboxDefinition(StrictContractModel):
    """Configuration for reviewer sandbox behavior."""

    mode: ReviewerSandboxMode
    assets: Annotated[list[NonEmptyStr], Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def enforce_assets_support(self) -> "ReviewerSandboxDefinition":
        """Validate that sandbox.assets is only used with empty_folder."""
        if self.assets is None:
            return self
        if self.mode != ReviewerSandboxMode.EMPTY_FOLDER:
            raise ValueError(
                "sandbox.assets is only supported for sandbox.mode=empty_folder"
            )
        return self


def _validate_prompt_file_location(prompt_file: str) -> None:
    """Ensure prompt_file points under harness/reviewers/prompts/."""
    prompt_path = Path(prompt_file)
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


class HarnessCheckWhenDefinition(StrictContractModel):
    """Selection predicates that decide when a check runs."""

    phase: HarnessCheckPhase | None = None
    on_change: Annotated[list[NonEmptyStr], Field(min_length=1)] | None = None


class HarnessCheckDefaultsDefinition(StrictContractModel):
    """Defaults applied to checks that omit explicit fields."""

    when: HarnessCheckWhenDefinition | None = None


class HarnessCheckCommandDefinition(StrictContractModel):
    """A plain command-string check executed as argv by the harness."""

    type: Literal["command"]
    command: NonEmptyStr
    when: HarnessCheckWhenDefinition | None = None


class HarnessCheckFitnessDefinition(StrictContractModel):
    """A fitness-function check executed by the harness."""

    type: Literal["fitness"]
    when: HarnessCheckWhenDefinition | None = None
    scope: Literal["all"] | None = None
    rule_ids: Annotated[list[NonEmptyStr], Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def enforce_fitness_selection(self) -> "HarnessCheckFitnessDefinition":
        """Ensure exactly one of scope or rule_ids selects fitness rules."""
        has_scope = self.scope is not None
        has_rule_ids = self.rule_ids is not None
        if has_scope == has_rule_ids:
            error = PydanticCustomError(
                "value_error",
                "define exactly one of scope: all or rule_ids",
            )
            errors = [
                _init_error_detail(error=error, loc=("scope",), input_value=self.scope),
                _init_error_detail(
                    error=error, loc=("rule_ids",), input_value=self.rule_ids
                ),
            ]
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)
        return self


class HarnessCheckReviewerDefinition(StrictContractModel):
    """A reviewer (LLM) check executed by the harness."""

    type: Literal["reviewer"]
    prompt_file: NonEmptyStr
    feedback_context: StrictString | None = None
    when: HarnessCheckWhenDefinition | None = None
    sandbox: ReviewerSandboxDefinition | None = None
    approval: ReviewerApprovalDefinition = Field(
        default_factory=ReviewerApprovalDefinition
    )

    @model_validator(mode="after")
    def enforce_prompt_file_location(self) -> "HarnessCheckReviewerDefinition":
        """Ensure prompt_file points under harness/reviewers/prompts/."""
        _validate_prompt_file_location(self.prompt_file)
        return self


HarnessCheckDefinition = Annotated[
    HarnessCheckCommandDefinition
    | HarnessCheckFitnessDefinition
    | HarnessCheckReviewerDefinition,
    Field(discriminator="type"),
]


class HarnessCheckGroupDefinition(StrictContractModel):
    """A named checks group used by feature quality profiles."""

    group_id: NonEmptyStr
    description: NonEmptyStr
    checks: Annotated[list[NonEmptyStr], Field(min_length=1)]


class HarnessChecksDocument(StrictContractModel):
    """Top-level schema for harness/checks.yaml."""

    contract_version: Literal["1.0"]
    defaults: HarnessCheckDefaultsDefinition | None = None
    groups: list[HarnessCheckGroupDefinition] = Field(default_factory=list)
    checks: dict[NonEmptyStr, HarnessCheckDefinition]

    @model_validator(mode="after")
    def enforce_reviewer_phase_restrictions(self) -> "HarnessChecksDocument":
        """Reject reviewer checks scheduled for iteration_end."""
        errors: list[InitErrorDetails] = []
        for check_id, check in self.checks.items():
            if not isinstance(check, HarnessCheckReviewerDefinition):
                continue
            phase = effective_check_phase(doc=self, check_when=check.when)
            if phase == HarnessCheckPhase.ITERATION_END:
                errors.append(
                    _init_error_detail(
                        error=PydanticCustomError(
                            "value_error",
                            "reviewer checks must set when.phase to feature_done or manual",
                        ),
                        loc=("checks", check_id, "when", "phase"),
                        input_value=phase,
                    )
                )
        if errors:
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)
        return self

    @model_validator(mode="after")
    def enforce_group_integrity(self) -> "HarnessChecksDocument":
        """Require unique groups, valid references, and full check coverage."""
        if not self.groups:
            return self

        errors: list[InitErrorDetails] = []
        seen_group_ids: set[str] = set()
        referenced_checks: set[str] = set()

        for index, group in enumerate(self.groups):
            if group.group_id in seen_group_ids:
                errors.append(
                    _init_error_detail(
                        error=PydanticCustomError(
                            "value_error",
                            "group_id must be unique",
                        ),
                        loc=("groups", index, "group_id"),
                        input_value=group.group_id,
                    )
                )
            seen_group_ids.add(group.group_id)

            seen_group_checks: set[str] = set()
            for check_index, check_id in enumerate(group.checks):
                if check_id in seen_group_checks:
                    errors.append(
                        _init_error_detail(
                            error=PydanticCustomError(
                                "value_error",
                                "group checks must not contain duplicates",
                            ),
                            loc=("groups", index, "checks", check_index),
                            input_value=check_id,
                        )
                    )
                seen_group_checks.add(check_id)
                referenced_checks.add(check_id)
                if check_id not in self.checks:
                    errors.append(
                        _init_error_detail(
                            error=PydanticCustomError(
                                "value_error",
                                "group references unknown check_id",
                            ),
                            loc=("groups", index, "checks", check_index),
                            input_value=check_id,
                        )
                    )

        for check_id in self.checks:
            if check_id in referenced_checks:
                continue
            errors.append(
                _init_error_detail(
                    error=PydanticCustomError(
                        "value_error",
                        "check must belong to at least one group",
                    ),
                    loc=("checks", check_id),
                    input_value=check_id,
                )
            )

        if errors:
            raise ValidationError.from_exception_data(self.__class__.__name__, errors)
        return self


def effective_default_check_phase(doc: HarnessChecksDocument) -> HarnessCheckPhase:
    """Return the effective default phase for checks in a document."""
    defaults = doc.defaults
    if defaults is None or defaults.when is None or defaults.when.phase is None:
        return HarnessCheckPhase.ITERATION_END
    return defaults.when.phase


def effective_check_phase(
    *,
    doc: HarnessChecksDocument,
    check_when: HarnessCheckWhenDefinition | None,
) -> HarnessCheckPhase:
    """Return the effective phase for a single check-like object."""
    default_phase = effective_default_check_phase(doc)
    if check_when is None or check_when.phase is None:
        return default_phase
    return check_when.phase


def _init_error_detail(
    *,
    error: PydanticCustomError,
    loc: tuple[Any, ...],
    input_value: Any,
) -> InitErrorDetails:
    """Build an InitErrorDetails mapping for ValidationError construction."""
    return cast(
        InitErrorDetails,
        {
            "type": error,
            "loc": loc,
            "input": input_value,
        },
    )
