from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ..approach import (
    UnknownApproachIdError,
    format_approach_topic_index,
    load_topic_content,
    render_approach_overview,
)
from .output import emit_markdown_output, resolve_optional_path

_HandlerArgs = SimpleNamespace


def cmd_approach_overview(args: _HandlerArgs) -> int:
    """Render CLI-native overview text and topic index."""
    project_root = Path(args.project_root).resolve()
    output_path = resolve_optional_path(
        path=getattr(args, "output", None),
        project_root=project_root,
    )
    try:
        overview = load_topic_content("overview")
    except UnknownApproachIdError as exc:
        print(f"approach input error: {exc}")
        return 1
    except ValueError as exc:
        print(f"approach content error: {exc}")
        return 1

    rendered = render_approach_overview(overview)
    return emit_markdown_output(
        rendered,
        project_root=project_root,
        output=output_path,
        output_prefix="approach overview written",
    )


def cmd_approach_list(args: _HandlerArgs) -> int:
    """Render a deterministic list of approach topic ids with short titles."""
    project_root = Path(args.project_root).resolve()
    output_path = resolve_optional_path(
        path=getattr(args, "output", None),
        project_root=project_root,
    )
    rendered = format_approach_topic_index()
    if rendered == "":
        rendered = "No approach topics are available."

    return emit_markdown_output(
        rendered,
        project_root=project_root,
        output=output_path,
        output_prefix="approach list written",
    )


def cmd_approach_show(args: _HandlerArgs) -> int:
    """Render one approach topic by canonical id or alias."""
    project_root = Path(args.project_root).resolve()
    output_path = resolve_optional_path(
        path=getattr(args, "output", None),
        project_root=project_root,
    )
    topic_id = str(getattr(args, "topic_id", "")).strip()
    if topic_id == "":
        print(
            "approach input error: provide a topic id or use "
            "`engineeringagent approach list`"
        )
        return 1

    try:
        rendered = load_topic_content(topic_id)
    except UnknownApproachIdError as exc:
        print(f"approach input error: {exc}; use `engineeringagent approach list`")
        return 1
    except ValueError as exc:
        print(f"approach content error: {exc}")
        return 1

    return emit_markdown_output(
        rendered,
        project_root=project_root,
        output=output_path,
        output_prefix="approach topic written",
    )
