from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ...application import GuidanceInputError, GuidanceQuery
from ...bootstrap import AppFactory
from ...domain.guidance import UnknownGuidanceTopicIdError
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
        result = AppFactory(project_root).build_guidance_service().render(
            GuidanceQuery(kind="overview")
        )
    except UnknownGuidanceTopicIdError as exc:
        print(f"approach input error: {exc}")
        return 1
    except ValueError as exc:
        print(f"approach content error: {exc}")
        return 1

    return emit_markdown_output(
        result.payload,
        project_root=project_root,
        output=output_path,
        output_prefix=result.output_prefix,
    )


def cmd_approach_list(args: _HandlerArgs) -> int:
    """Render a deterministic list of approach topic ids with short titles."""
    project_root = Path(args.project_root).resolve()
    output_path = resolve_optional_path(
        path=getattr(args, "output", None),
        project_root=project_root,
    )
    result = AppFactory(project_root).build_guidance_service().render(
        GuidanceQuery(kind="list")
    )

    return emit_markdown_output(
        result.payload,
        project_root=project_root,
        output=output_path,
        output_prefix=result.output_prefix,
    )


def cmd_approach_show(args: _HandlerArgs) -> int:
    """Render one approach topic by canonical id or alias."""
    project_root = Path(args.project_root).resolve()
    output_path = resolve_optional_path(
        path=getattr(args, "output", None),
        project_root=project_root,
    )
    try:
        result = AppFactory(project_root).build_guidance_service().render(
            GuidanceQuery(kind="topic", topic_id=str(getattr(args, "topic_id", "")))
        )
    except GuidanceInputError as exc:
        print(f"approach input error: {exc}")
        return 1
    except UnknownGuidanceTopicIdError as exc:
        print(f"approach input error: {exc}; use `engineeringagent approach list`")
        return 1
    except ValueError as exc:
        print(f"approach content error: {exc}")
        return 1

    return emit_markdown_output(
        result.payload,
        project_root=project_root,
        output=output_path,
        output_prefix=result.output_prefix,
    )
