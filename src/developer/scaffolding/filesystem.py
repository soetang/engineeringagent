"""Filesystem helpers for scaffold generation."""

from pathlib import Path

from developer.scaffolding.models import FileWriteResult


def write_file_if_missing(path: Path, content: str) -> FileWriteResult:
    """Create a file unless it already exists."""
    if path.exists():
        return FileWriteResult(path=path, status="skipped", reason="already exists")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return FileWriteResult(path=path, status="created")


def upsert_text_file(path: Path, content: str) -> FileWriteResult:
    """Create or replace a text file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    status = "updated" if path.exists() else "created"
    path.write_text(content)
    return FileWriteResult(path=path, status=status)
