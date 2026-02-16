from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

import pytest

from engineeringagent import commit_messages
from engineeringagent import on_change_matcher
from engineeringagent import progress_logging
from engineeringagent.opencode import client as opencode_client


def test_path_matches_any_glob_normalizes_dot_slash_prefix() -> None:
    assert on_change_matcher.path_matches_any_glob("./README.md", ["README.md"]) is True


def test_path_matches_any_glob_empty_patterns_returns_false() -> None:
    assert on_change_matcher.path_matches_any_glob("README.md", []) is False


def test_opencode_start_agent_includes_optional_session_and_format(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)

    opencode_client.start_agent(
        tmp_path,
        "hello",
        session="sess-123",
        format="json",
    )

    command = captured["args"][0]
    assert "--session" in command
    assert "sess-123" in command
    assert "--format" in command
    assert "json" in command
    assert captured["kwargs"]["cwd"] == tmp_path


def test_progress_logging_skips_non_file_handlers(tmp_path: Path) -> None:
    log_path = tmp_path / "progress" / "runs.jsonl"
    namespace = "engineeringagent.progress.runs"
    logger_name = progress_logging._logger_name_for_path(
        namespace=namespace, log_path=log_path
    )
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    logger.addHandler(logging.StreamHandler())

    resolved = progress_logging._get_or_create_file_logger(
        namespace=namespace,
        log_path=log_path,
    )
    assert any(
        isinstance(handler, logging.FileHandler) for handler in resolved.handlers
    )


def test_validate_commit_subject_rejects_multiline_subject() -> None:
    assert commit_messages.validate_commit_subject("feat: ok\nmore") == (
        "subject must be a single line"
    )


def test_subject_from_commit_message_file_errors_when_missing_subject(
    tmp_path: Path,
) -> None:
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text("# comment\n\n# another\n", encoding="utf-8")

    with pytest.raises(ValueError, match="does not contain a subject line"):
        commit_messages.subject_from_commit_message_file(message_file)
