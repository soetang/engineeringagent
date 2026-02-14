from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from engineeringagent.cli import build_parser
from engineeringagent.init_scaffold import build_baseline_scaffold_manifest


def test_build_baseline_scaffold_manifest_excludes_reviewers_by_default() -> None:
    manifest = build_baseline_scaffold_manifest()

    assert "harness/reviewers.yaml" not in manifest
    assert "harness/reviewers/prompts/code_simplifier.md" not in manifest
    assert "harness/reviewers/prompts/readme_process.md" not in manifest


def test_build_baseline_scaffold_manifest_can_include_reviewers() -> None:
    manifest = build_baseline_scaffold_manifest(include_reviewers=True)

    assert "harness/reviewers.yaml" in manifest
    assert "harness/reviewers/prompts/code_simplifier.md" in manifest
    assert "harness/reviewers/prompts/readme_process.md" in manifest

    reviewers_config = yaml.safe_load(manifest["harness/reviewers.yaml"])
    assert reviewers_config["contract_version"] == "1.0"
    assert reviewers_config["profiles"]["loop_fast"] == [
        "code_simplifier",
        "readme_process",
    ]

    readme_process = reviewers_config["reviewers"]["readme_process"]
    assert readme_process == {
        "prompt_file": "harness/reviewers/prompts/readme_process.md",
        "trigger": {
            "phase": "feature_done",
            "on_change": ["README.md"],
        },
        "sandbox": {
            "mode": "temp_worktree_snapshot",
        },
        "approval": {
            "mode": "blocking",
            "first_feature_approval": True,
            "max_retries": 2,
            "continue_on_exhausted": True,
        },
    }

    readme_prompt = manifest["harness/reviewers/prompts/readme_process.md"]
    assert "Read README.md" in readme_prompt
    assert "Create a new temporary directory" in readme_prompt
    assert "decision=request_changes" in readme_prompt
    assert (
        "README instructions, init/scaffold command behavior, or both" in readme_prompt
    )
    assert "Return strict JSON only" in readme_prompt


def test_init_include_reviewers_writes_scaffold_files(
    tmp_path: Path,
    capsys: Any,
) -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "--include-reviewers",
        ]
    )

    code = args.func(args)
    _ = capsys.readouterr().out

    assert code == 0
    assert (tmp_path / "harness" / "reviewers.yaml").exists()
    assert (
        tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    ).exists()
    assert (
        tmp_path / "harness" / "reviewers" / "prompts" / "readme_process.md"
    ).exists()
