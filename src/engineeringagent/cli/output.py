from __future__ import annotations

from pathlib import Path


def resolve_optional_path(
    *,
    path: str | None,
    project_root: Path,
) -> Path | None:
    """Resolve optional path values relative to project root."""
    if path is None:
        return None
    resolved = Path(path)
    if resolved.is_absolute():
        return resolved
    return project_root / resolved


def emit_markdown_output(
    payload: str,
    *,
    project_root: Path,
    output: str | Path | None,
    output_prefix: str,
) -> int:
    """Print markdown payload or write it to a deterministic output path."""
    if isinstance(output, Path):
        output_path = output
    else:
        output_path = resolve_optional_path(path=output, project_root=project_root)
    if output_path is None:
        print(payload)
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload + "\n", encoding="utf-8")
    try:
        shown_path = output_path.relative_to(project_root)
    except ValueError:
        shown_path = output_path
    print(f"{output_prefix}: {shown_path}")
    return 0
