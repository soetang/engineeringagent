from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.checks.config_selection import (
    ChecksConfigSelectionError,
    load_selected_harness_checks_document,
)
from engineeringagent.checks.request_normalization import (
    build_run_checks_request,
)


def _commands_request(project_root: Path):
    _, request = build_run_checks_request(
        project_root,
        phase="iteration_end",
        checks=["commands"],
        kwargs={},
    )
    return request


def test_selection_returns_config_error_for_missing_configured_checks_path(
    tmp_path: Path,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        "[harness.checks]\npath = \"config/checks.yaml\"\n",
        encoding="utf-8",
    )

    doc, error = load_selected_harness_checks_document(
        tmp_path,
        request=_commands_request(tmp_path),
    )

    assert doc is None
    assert isinstance(error, ChecksConfigSelectionError)
    assert "checks config error: missing config/checks.yaml" in error.output


def test_build_request_requires_feature_path_for_trimmed_reviewers_group(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="feature_path is required when reviewers checks are selected",
    ):
        build_run_checks_request(
            tmp_path,
            phase="iteration_end",
            checks=["commands", " reviewers "],
            kwargs={},
        )
