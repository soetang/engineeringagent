from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.vcs import git_cli

_EXCLUDED_PREFIXES = (
    "docs/spec/features_done/",
    ".engineeringagent/progress/",
)


def append_purge_invariant_issues(messages: list[str], *, project_root: Path) -> None:
    """Fail validation when removed identifiers reappear in active tracked files."""

    if not (project_root / ".git").exists():
        return

    needles = tuple(_purge_forbidden_needles())
    if not needles:
        return

    paths = _tracked_project_files(project_root=project_root, messages=messages)
    if paths is None:
        return

    needle_blobs = tuple(needle.encode("utf-8") for needle in needles)
    for rel in paths:
        _append_first_token_hit(
            messages=messages,
            project_root=project_root,
            rel=rel,
            needles=needles,
            needle_blobs=needle_blobs,
        )


def _tracked_project_files(*, project_root: Path, messages: list[str]) -> tuple[str, ...] | None:
    proc = git_cli.ls_files(project_root)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        detail = f": {stderr}" if stderr else ""
        messages.append(f"validate: git ls-files failed{detail}")
        return None

    return tuple(
        rel
        for line in (proc.stdout or "").splitlines()
        for rel in (line.strip(),)
        if rel and not rel.endswith("/") and not rel.startswith(_EXCLUDED_PREFIXES)
    )


def _append_first_token_hit(
    *,
    messages: list[str],
    project_root: Path,
    rel: str,
    needles: tuple[str, ...],
    needle_blobs: tuple[bytes, ...],
) -> None:
    payload = _read_bytes(project_root / rel)
    if payload is None:
        return

    for needle, needle_blob in zip(needles, needle_blobs, strict=True):
        if needle_blob in payload:
            messages.append(f"{rel}: forbidden token present (purge invariant): {needle}")
            return


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _purge_forbidden_needles() -> list[str]:
    """Return forbidden identifiers without embedding them verbatim in source."""

    removed_reviewer_id = "_".join(["readme", "process"])
    removed_sandbox_mode = "_".join(["clean", "room", "readme", "cli"])
    return [removed_reviewer_id, removed_sandbox_mode]
