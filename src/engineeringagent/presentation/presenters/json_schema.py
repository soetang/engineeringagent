from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from importlib import import_module
from typing import Any

from engineeringagent.domain.shared import JSON_SCHEMA_DRAFT_URL as _JSON_SCHEMA_DRAFT_URL
from engineeringagent.domain.specification import (
    checks_schema_from_model,
    feature_schema_from_model,
)

SchemaProducer = Callable[[], dict[str, Any]]
JSON_SCHEMA_DRAFT_URL = _JSON_SCHEMA_DRAFT_URL


def custom_rule_manifest_schema_from_model() -> dict[str, Any]:
    """Load the fitness manifest schema producer from its owning adapter module."""
    contracts = import_module("engineeringagent.adapters.quality.fitness.contracts")
    return contracts.custom_rule_manifest_schema_from_model()


def reviewer_decision_schema_from_model() -> dict[str, Any]:
    """Load the reviewer schema producer from its owning adapter module."""
    engine = import_module("engineeringagent.adapters.quality.reviewers.engine")
    return engine.reviewer_decision_schema_from_model()


SCHEMA_REGISTRY: dict[str, SchemaProducer] = {
    "checks.harness": checks_schema_from_model,
    "feature.spec": feature_schema_from_model,
    "fitness.manifest": custom_rule_manifest_schema_from_model,
    "reviewer.decision": reviewer_decision_schema_from_model,
}


class UnknownSchemaIdError(ValueError):
    """Raised when schema lookup receives an unsupported schema id."""


def list_schema_ids() -> tuple[str, ...]:
    """Return all supported schema ids in deterministic order."""
    return tuple(sorted(SCHEMA_REGISTRY))


def schema_from_registry(schema_id: str) -> dict[str, Any]:
    """Return one schema by id using model-owned schema producers."""
    producer = SCHEMA_REGISTRY.get(schema_id)
    if producer is None:
        supported = ", ".join(list_schema_ids())
        raise UnknownSchemaIdError(
            f"unknown schema id: {schema_id}; supported ids: {supported}"
        )
    return deepcopy(producer())
