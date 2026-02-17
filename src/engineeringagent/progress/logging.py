"""Logging-backed writers for loop progress artifacts.

This module centralizes *writes* to progress sinks that are intended to be
repository-local artifacts (e.g. JSONL telemetry and per-feature progress logs).

Path construction remains the responsibility of `engineeringagent.progress.paths`.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Sequence


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


def append_jsonl_record(*, log_path: Path, payload: dict[str, Any]) -> None:
    """Append one JSONL record to `log_path` using a logging handler."""

    logger = _get_or_create_file_logger(
        namespace="engineeringagent.progress.runs", log_path=log_path
    )
    logger.info(json.dumps(payload, ensure_ascii=True))


def append_text_block(*, log_path: Path, lines: Sequence[str]) -> None:
    """Append a newline-terminated block to `log_path` using a logging handler."""

    logger = _get_or_create_file_logger(
        namespace="engineeringagent.progress.feature", log_path=log_path
    )
    logger.info("\n".join(lines))
