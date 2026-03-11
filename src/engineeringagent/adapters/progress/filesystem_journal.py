"""Filesystem-backed progress journal adapter."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Sequence

from engineeringagent.domain.audit import ProgressEvent
from engineeringagent.ports import ProgressJournal

from . import paths as progress_paths


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
        if Path(getattr(handler, "baseFilename", "")).resolve() != resolved:
            continue
        if _file_handler_targets_live_path(handler=handler, log_path=log_path):
            return logger
        logger.removeHandler(handler)
        handler.close()

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


def _file_handler_targets_live_path(
    *,
    handler: logging.FileHandler,
    log_path: Path,
) -> bool:
    """Return whether a cached file handler still points at the live filesystem path."""

    stream = handler.stream
    if stream is None:
        return False
    if not log_path.exists():
        return False
    try:
        handler_stat = os.fstat(stream.fileno())
        path_stat = log_path.stat()
    except OSError:
        return False
    return (
        handler_stat.st_dev == path_stat.st_dev
        and handler_stat.st_ino == path_stat.st_ino
    )


class FilesystemProgressJournal(ProgressJournal):
    """Persist loop progress artifacts under the configured progress root."""

    def append(
        self,
        *,
        project_root: Path,
        event: ProgressEvent,
    ) -> None:
        log_path = progress_paths.runs_jsonl_path(project_root)
        logger = _get_or_create_file_logger(
            namespace="engineeringagent.progress.runs",
            log_path=log_path,
        )
        logger.info(json.dumps(event.to_log_record(), ensure_ascii=True))

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

    def write_iteration_report(
        self,
        *,
        project_root: Path,
        feature_id: str,
        payload: dict[str, Any],
    ) -> None:
        report_path = progress_paths.iteration_report_path(project_root, feature_id)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as report_file:
            report_file.write(json.dumps(payload, ensure_ascii=True, indent=2) + "\n")

    def write_handoff(
        self,
        *,
        project_root: Path,
        feature_id: str,
        lines: Sequence[str],
    ) -> None:
        log_path = progress_paths.handoff_markdown_path(project_root, feature_id)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        rendered = "\n".join(lines)
        if rendered and not rendered.endswith("\n"):
            rendered += "\n"
        with open(log_path, "w", encoding="utf-8") as handoff_file:
            handoff_file.write(rendered)

    def latest_handoff_path(self, *, project_root: Path, feature_id: str) -> Path | None:
        handoff_path = progress_paths.handoff_markdown_path(project_root, feature_id)
        if handoff_path.is_file():
            return handoff_path
        return None
