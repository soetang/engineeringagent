from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


CONTRACT_VERSION = "1.0"

NonEmptyStr = Annotated[str, Field(strict=True, min_length=1)]
RuleId = Annotated[
    str,
    Field(
        strict=True,
        min_length=3,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    ),
]


class FitnessModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RuleSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class RuleStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


class RuleAdapter(str, Enum):
    PYTHON = "python"
    COMMAND = "command"


class RuleSource(str, Enum):
    BUILTIN = "builtin"
    CUSTOM = "custom"


class FitnessRuleMetadata(FitnessModel):
    rule_id: RuleId
    name: NonEmptyStr
    summary: NonEmptyStr
    rationale: NonEmptyStr
    remediation: NonEmptyStr
    scope: NonEmptyStr
    severity: RuleSeverity
    adapter: RuleAdapter
    source: RuleSource
    side_effect_free: Literal[True]


class FitnessRuleResult(FitnessModel):
    contract_version: Annotated[str, Field(strict=True, pattern=r"^1\.0$")]
    rule_id: RuleId
    status: RuleStatus
    severity: RuleSeverity
    summary: NonEmptyStr
    violations: list[NonEmptyStr] = Field(default_factory=list)
    details: dict[str, Any] | None = None


class CustomRuleManifestEntry(FitnessModel):
    rule_id: RuleId
    name: NonEmptyStr
    summary: NonEmptyStr
    rationale: NonEmptyStr
    remediation: NonEmptyStr
    scope: NonEmptyStr
    severity: RuleSeverity
    side_effect_free: Literal[True]
    adapter: Literal[RuleAdapter.COMMAND]
    command: Annotated[list[NonEmptyStr], Field(min_length=1)]
    timeout_seconds: Annotated[int, Field(strict=True, ge=1)] | None = None
    env: dict[NonEmptyStr, str] | None = None


class CustomRuleManifest(FitnessModel):
    contract_version: Annotated[str, Field(strict=True, pattern=r"^1\.0$")]
    rules: list[CustomRuleManifestEntry] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _reject_builtin_references(cls, payload: object) -> object:
        if not isinstance(payload, dict):
            return payload

        rules = payload.get("rules")
        if not isinstance(rules, list):
            return payload

        for index, rule in enumerate(rules):
            if isinstance(rule, dict) and "builtin" in rule:
                raise ValueError(
                    "builtin manifest references are no longer supported; "
                    f"replace rules[{index}].builtin with a command adapter entry"
                )
        return payload


def load_custom_rule_manifest(path: Path) -> CustomRuleManifest:
    """Load and validate the custom fitness-rule manifest from YAML."""
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping at top level")

    return CustomRuleManifest.model_validate(payload)
