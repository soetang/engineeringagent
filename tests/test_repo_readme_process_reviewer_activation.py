from __future__ import annotations

from pathlib import Path

import yaml

from engineeringagent.specs import reviewer_contract_issues


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEWERS_PATH = REPO_ROOT / "harness" / "reviewers.yaml"
README_PROCESS_PROMPT_PATH = (
    REPO_ROOT / "harness" / "reviewers" / "prompts" / "readme_process.md"
)


def test_repo_enables_readme_process_reviewer_in_loop_fast() -> None:
    document = yaml.safe_load(REVIEWERS_PATH.read_text(encoding="utf-8"))

    assert "loop_fast" in document["profiles"]
    assert "readme_process" in document["profiles"]["loop_fast"]

    assert "readme_process" in document["reviewers"]
    reviewer = document["reviewers"]["readme_process"]

    assert reviewer["prompt_file"] == "harness/reviewers/prompts/readme_process.md"
    assert reviewer["trigger"] == {
        "phase": "feature_done",
        "on_change": [
            "README.md",
            "docs/references/**/*.md",
            "docs/principles/**/*.md",
            "src/engineeringagent/cli.py",
            "src/engineeringagent/init_scaffold.py",
            "src/engineeringagent/scaffold_templates/**",
            "src/engineeringagent/validator.py",
            "src/engineeringagent/gates.py",
            "src/engineeringagent/loop.py",
            "src/engineeringagent/loop_runtime/**/*.py",
        ],
    }
    assert "AGENTS.md" not in reviewer["trigger"]["on_change"]
    assert reviewer["approval"] == {
        "mode": "blocking",
        "first_feature_approval": True,
        "max_retries": 2,
        "continue_on_exhausted": True,
    }
    assert reviewer["sandbox"]["mode"] == "clean_room_readme_cli"
    assert reviewer["sandbox"]["assets"] == [
        "docs",
        ".opencode/agents",
    ]

    issues = reviewer_contract_issues(document, Path("harness/reviewers.yaml"))
    assert issues == []

    prompt_body = README_PROCESS_PROMPT_PATH.read_text(encoding="utf-8")
    assert "$responseformat" in prompt_body
    assert "opencode.json" not in prompt_body
    assert "Do not leave the sandbox" in prompt_body
    assert "Create a fresh, empty directory under the sandbox root" in prompt_body
    assert "../.engineeringagent/bin/engineeringagent init" in prompt_body
    assert "../.engineeringagent/bin/engineeringagent validate" in prompt_body
    assert (
        "../.engineeringagent/bin/engineeringagent gates run --profile loop_fast"
        in prompt_body
    )
    assert "--dry-run" in prompt_body
