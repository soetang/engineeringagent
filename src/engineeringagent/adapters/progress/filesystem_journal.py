"""Filesystem-backed progress journal adapter."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Sequence

from engineeringagent.progress import paths as progress_paths
from engineeringagent.ports import ProgressJournal


_FORMATTER = logging.Formatter("%(message)s")


def _logger_name_for_path(*, namespace: str, log_path: Path) -> str:
    digest = hashlib.sha256(str(log_path).encode("utf-8")).hexdigest()[:16]
    return f"{namespace}.{digest}"


def _get_or_create_file_logger(*, namespace: str, log_path: Path) -> logging.Logger:
    """Return a dedicated logger that appends raw messages to `log_path`."""

    logger = logging.getLogger(
        _logger_name_for_path(namespace=namespace, log_path=log_path)
    )
    logger.setLevel(logging.INFO)
    logger.propagate = False

    resolved = log_path.resolve()
    for handler in logger.handlers:
        if not isinstance(handler, logging.FileHandler):
            continue
        if Path(getattr(handler, "baseFilename", "")).resolve() == resolved:
            return logger

    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(
        str(log_path),
        mode="a",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(_FORMATTER)
    logger.addHandler(file_handler)
    return logger


class FilesystemProgressJournal(ProgressJournal):
    """Persist loop progress artifacts under the configured progress root."""

    def append_run_record(
        self,
        *,
        project_root: Path,
        payload: dict[str, Any],
    ) -> None:
        log_path = progress_paths.runs_jsonl_path(project_root)
        logger = _get_or_create_file_logger(
            namespace="engineeringagent.progress.runs",
            log_path=log_path,
        )
        logger.info(json.dumps(payload, ensure_ascii=True))

    def append_feature_log(
        self,
        *,
        project_root: Path,
        feature_id: str,
        lines: Sequence[str],
    ) -> None:
        log_path = progress_paths.run_feature_log_path(project_root, feature_id)
        logger = _get_or_create_file_logger(
            namespace="engineeringagent.progress.feature",
            log_path=log_path,
        )
        logger.info("\n".join(lines))

    def append_handoff_entry(
        self,
        *,
        project_root: Path,
        feature_id: str,
        entry_lines: Sequence[str],
    ) -> None:
        log_path = progress_paths.handoff_markdown_path(project_root, feature_id)
        logger = _get_or_create_file_logger(
            namespace="engineeringagent.progress.feature",
            log_path=log_path,
        )
        logger.info("\n".join(entry_lines))

    def latest_handoff_path(self, *, project_root: Path, feature_id: str) -> Path | None:
        handoff_path = progress_paths.handoff_markdown_path(project_root, feature_id)
        if handoff_path.is_file():
            return handoff_path
        return None
