from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import yaml

from ...schema_registry import (
    UnknownSchemaIdError,
    list_schema_ids,
    schema_from_registry,
)
from .output import emit_markdown_output, resolve_optional_path

_HandlerArgs = SimpleNamespace

_SCHEMA_FORMATS: tuple[str, ...] = ("json", "yaml")


def cmd_schema_list(args: _HandlerArgs) -> int:
    """Print supported schema ids in deterministic order."""
    _ = args
    for schema_id in list_schema_ids():
        print(schema_id)
    return 0


def cmd_schema(args: _HandlerArgs) -> int:
    """Emit one schema from the model-owned registry."""
    project_root = Path(args.project_root).resolve()
    output_path = resolve_optional_path(
        path=getattr(args, "output", None),
        project_root=project_root,
    )
    raw_schema_id = getattr(args, "schema_id", None)
    schema_id = "" if raw_schema_id is None else str(raw_schema_id).strip()
    if schema_id == "":
        print(
            "schema input error: provide a schema id or use "
            "`engineeringagent schema list`"
        )
        return 1

    raw_format = getattr(args, "output_format", "json")
    output_format = str(raw_format).strip().lower()
    if output_format not in _SCHEMA_FORMATS:
        print("schema input error: --format must be one of: json, yaml")
        return 1

    try:
        schema = schema_from_registry(schema_id)
    except UnknownSchemaIdError as exc:
        print(f"schema input error: {exc}")
        return 1

    if output_format == "json":
        rendered = json.dumps(schema, indent=2, sort_keys=True)
    else:
        rendered = yaml.safe_dump(
            schema,
            sort_keys=True,
            allow_unicode=False,
            default_flow_style=False,
        ).rstrip("\n")

    return emit_markdown_output(
        rendered,
        project_root=project_root,
        output=output_path,
        output_prefix="schema written",
    )
