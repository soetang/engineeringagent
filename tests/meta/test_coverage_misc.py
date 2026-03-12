from __future__ import annotations

# Tests intentionally validate internal helpers.
# pylint: disable=protected-access

import logging
import subprocess
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from engineeringagent.adapters.progress.filesystem_journal import (
    _get_or_create_file_logger,
    _logger_name_for_path,
)
from engineeringagent.adapters.agents.opencode import client as opencode_client


def _load_harness_commit_messages(repo_root: Path) -> ModuleType:
    policy_path = repo_root / "harness" / "fitness_functions" / "commit_messages.py"
    spec = importlib.util.spec_from_file_location(
        "harness_commit_messages", policy_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load commit message policy from {policy_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_opencode_start_agent_includes_optional_session_and_format(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """OpenCode startup should forward optional session and format arguments."""
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
    """File logger setup should replace non-file handlers when needed."""
    log_path = tmp_path / "progress" / "runs.jsonl"
    namespace = "engineeringagent.progress.runs"
    logger_name = _logger_name_for_path(
        namespace=namespace, log_path=log_path
    )
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    logger.addHandler(logging.StreamHandler())

    resolved = _get_or_create_file_logger(
        namespace=namespace,
        log_path=log_path,
    )
    assert any(
        isinstance(handler, logging.FileHandler) for handler in resolved.handlers
    )


def test_validate_commit_subject_rejects_multiline_subject(repo_root: Path) -> None:
    """Commit policy helper should reject multiline subjects."""
    commit_messages = _load_harness_commit_messages(repo_root)
    assert commit_messages.validate_commit_subject("feat: ok\nmore") == (
        "subject must be a single line"
    )


def test_subject_from_commit_message_file_errors_when_missing_subject(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Commit message parsing should fail when no subject line exists."""
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text("# comment\n\n# another\n", encoding="utf-8")

    commit_messages = _load_harness_commit_messages(repo_root)

    with pytest.raises(ValueError, match="does not contain a subject line"):
        commit_messages.subject_from_commit_message_file(message_file)
