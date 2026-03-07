from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

from ..progress import handoff as progress_handoff
from ..progress import paths as progress_paths

_HandlerArgs = SimpleNamespace

__all__ = [
    "cmd_progress_feature_prune",
    "cmd_progress_handoff_append",
]


def cmd_progress_handoff_append(args: _HandlerArgs) -> int:
    """Append one feature handoff markdown entry from JSON stdin payload."""
    project_root = Path(args.project_root).resolve()
    feature_id = _require_feature_id(args)
    if feature_id is None:
        return 1

    payload = _read_json_stdin_payload()

    envelope, used_fallback = progress_handoff.parse_implement_progress_envelope(
        payload
    )
    entry_lines = progress_handoff.render_handoff_markdown_entry(
        attempt=int(args.attempt),
        envelope=envelope,
        timestamp=getattr(args, "timestamp", None),
        used_fallback=used_fallback,
    )
    handoff_path = progress_paths.handoff_markdown_path(project_root, feature_id)
    progress_handoff.append_handoff_markdown_entry(
        handoff_path=handoff_path,
        entry_lines=entry_lines,
    )
    print(
        "progress handoff append: "
        f"path={progress_paths.handoff_markdown_reference(project_root, feature_id)} "
        f"fallback={str(used_fallback).lower()}"
    )
    return 0


def cmd_progress_feature_prune(args: _HandlerArgs) -> int:
    """Delete the feature-scoped progress directory for manual cleanup."""
    project_root = Path(args.project_root).resolve()
    feature_id = _require_feature_id(args)
    if feature_id is None:
        return 1

    target_dir = progress_paths.feature_dir_path(project_root, feature_id)
    target_ref = target_dir.relative_to(project_root)
    if not target_dir.exists():
        print(f"progress feature prune: no-op path={target_ref}")
        return 0

    shutil.rmtree(target_dir)
    print(f"progress feature prune: removed path={target_ref}")
    return 0


def _read_json_stdin_payload() -> object:
    """Return parsed JSON payload from stdin or empty object on failure."""
    raw_stdin = sys.stdin.read().strip()
    if not raw_stdin:
        return {}
    try:
        return json.loads(raw_stdin)
    except json.JSONDecodeError:
        return {}


def _require_feature_id(args: _HandlerArgs) -> str | None:
    """Return normalized feature id or emit deterministic CLI input error."""
    feature_id = str(args.feature_id).strip()
    if feature_id != "":
        return feature_id
    print("progress input error: --feature-id must be non-empty")
    return None
