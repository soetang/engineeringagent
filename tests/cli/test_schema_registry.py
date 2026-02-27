from __future__ import annotations

import pytest

from engineeringagent.schema_registry import (
    UnknownSchemaIdError,
    list_schema_ids,
    schema_from_registry,
)


def test_schema_registry_lists_expected_ids_in_deterministic_order() -> None:
    assert list_schema_ids() == (
        "checks.harness",
        "feature.spec",
        "fitness.manifest",
        "reviewer.decision",
    )


@pytest.mark.parametrize("schema_id", list_schema_ids())
def test_schema_registry_returns_model_owned_json_schema(schema_id: str) -> None:
    schema = schema_from_registry(schema_id)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert schema.get("properties")


def test_schema_registry_rejects_unknown_schema_id_with_supported_ids() -> None:
    with pytest.raises(UnknownSchemaIdError) as exc_info:
        schema_from_registry("not-real")

    message = str(exc_info.value)
    assert message.startswith("unknown schema id: not-real; supported ids:")
    assert "feature.spec" in message
