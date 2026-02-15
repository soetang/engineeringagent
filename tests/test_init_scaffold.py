from __future__ import annotations

from typing import Any

import pytest

from engineeringagent.cli import build_parser
from engineeringagent.init_scaffold import build_baseline_scaffold_manifest


def test_build_baseline_scaffold_manifest_excludes_reviewers_by_default() -> None:
    manifest = build_baseline_scaffold_manifest()

    assert "harness/reviewers.yaml" not in manifest
    assert "harness/reviewers/prompts/code_simplifier.md" not in manifest
    assert "harness/reviewers/prompts/readme_process.md" not in manifest


def test_build_baseline_scaffold_manifest_ignores_include_reviewers_flag() -> None:
    manifest = build_baseline_scaffold_manifest(include_reviewers=True)

    assert "harness/reviewers.yaml" not in manifest
    assert "harness/reviewers/prompts/code_simplifier.md" not in manifest
    assert "harness/reviewers/prompts/readme_process.md" not in manifest


def test_init_rejects_include_reviewers_flag(capsys: Any) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["init", "--include-reviewers"])

    output = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "unrecognized arguments: --include-reviewers" in output.err
