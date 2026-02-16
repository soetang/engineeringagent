from __future__ import annotations

from pathlib import Path

import pytest


def _read(repo_root: Path, relpath: str) -> str:
    return (repo_root / relpath).read_text(encoding="utf-8")


def test_reviewer_reference_docs_do_not_describe_legacy_decisions(
    pytestconfig: pytest.Config,
) -> None:
    repo_root = Path(pytestconfig.rootpath)
    doc = _read(repo_root, "docs/references/reviewer-agents-llms.md")

    # Only approve/request_changes should be presented as supported decisions.
    assert "`approve`" in doc
    assert "`request_changes`" in doc
    assert "`warning`" not in doc


def test_reviewer_authoring_guide_does_not_mention_removed_approval_mode(
    pytestconfig: pytest.Config,
) -> None:
    repo_root = Path(pytestconfig.rootpath)
    doc = _read(repo_root, "docs/principles/reviewer-authoring-guide.md")

    assert "approval.mode" not in doc
    assert "approval`: `mode`" not in doc
    assert "approval: `mode`" not in doc
    assert "first_feature_approval" in doc


def test_workflow_reference_documents_next_action_taxonomy(
    pytestconfig: pytest.Config,
) -> None:
    repo_root = Path(pytestconfig.rootpath)
    doc = _read(repo_root, "docs/references/workflow-llms.md")

    # Loop control-flow values should be discoverable by agents.
    assert "continue_same_feature" in doc
    assert "retry_same_feature" in doc
    assert "select_next_feature" in doc
