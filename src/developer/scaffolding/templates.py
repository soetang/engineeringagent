"""Canonical starter template content for onboarding."""

from pathlib import Path

from developer.scaffolding.models import ScaffoldFile

IMPLEMENTATION_PROMPT_TEMPLATE = """You are a code agent running in a loop. You pick one small implementation step at a time from the plan and implement that.

Study the plan: {{ task_path }} and complete the most important task.

Use this markdown task plan as the source of truth for what to implement and when the task is complete.
Use the checkmarks in the plan, to mark when a task is complete.
Mark phases as complete when all tasks for a phase is complete and relevant refactoring / clean-up is finished.
When the full plan is implemented mark the plan as complete.

You can validate that status update are correct with `uv run --active developer validate-plan {{ task_path }}`

{% if feedback %}
Address feedback from previous iterations first.
Feedback:
{{ feedback }}
{% endif %}

Return concrete, production-ready implementation output.
"""

COMMIT_MESSAGE_PROMPT_TEMPLATE = """Write a concise conventional-commit-style message for the staged changes.

Requirements:
- Use one short subject line.
- Keep the tone factual.
- Reflect the actual code changes.
"""

PULL_REQUEST_PROMPT_TEMPLATE = """Write a pull request description for the current branch.

Include:
- a short summary of the change;
- the main implementation details;
- validation performed; and
- any follow-up work or risks.
"""

CHECKS_YAML_TEMPLATE = """checks:
  - name: "Local quality commands"
    filepath: "quality/commands.yaml"
"""

QUALITY_COMMANDS_TEMPLATE = """name: "commands"
filepath: ""
checks:
  - check_type: "command"
    command: ["uv", "run", "--active", "ruff", "check"]
  - check_type: "command"
    command: ["uv", "run", "--active", "pyrefly", "check"]
  - check_type: "command"
    command: ["uv", "run", "--active", "pytest"]
"""

EXAMPLE_PLAN_TEMPLATE = """---
schema_version: 1
task_id: example-onboarding-task
title: Example onboarding task
status: ready
branch: feat/example-onboarding-task
base_branch: master
phases:
  - id: bootstrap
    title: Bootstrap the example change
    status: todo
---

# Example Plan

## Goal

Describe the user-visible outcome here.

## Tasks

- [ ] Replace this placeholder task with real implementation work.
"""

AGENTS_MD_SNIPPET = """<!-- developer:init:start -->
## Developer CLI

- Run package commands with `uv run --active developer ...`.
- Initialize a repository scaffold with `uv run --active developer init`.
- Export machine-readable contracts with `uv run --active developer schema plan` and `uv run --active developer schema quality`.
- Validate plans before implementation with `uv run --active developer validate-plan <plan.md>`.
- Run checks with `uv run --active developer check validate` and `uv run --active developer check run`.
- Start an implementation loop with `uv run --active developer implement <plan.md>`.
- Scaffolded harness files live under `<harness-dir>/`, and the sample plan lives under `docs/plans/`.
- Reuse the generated schemas and templates instead of inventing new plan or quality formats.
<!-- developer:init:end -->
"""


def build_scaffold_files(harness_dir: str) -> list[ScaffoldFile]:
    """Return the canonical scaffold file set for a harness directory."""
    harness_path = Path(harness_dir)
    return [
        ScaffoldFile(
            path=harness_path / "checks.yaml",
            content=CHECKS_YAML_TEMPLATE,
        ),
        ScaffoldFile(
            path=harness_path / "quality" / "commands.yaml",
            content=QUALITY_COMMANDS_TEMPLATE,
        ),
        ScaffoldFile(
            path=harness_path / "prompts" / "implementation_prompt.md",
            content=IMPLEMENTATION_PROMPT_TEMPLATE,
        ),
        ScaffoldFile(
            path=harness_path / "prompts" / "commit_message_prompt.md",
            content=COMMIT_MESSAGE_PROMPT_TEMPLATE,
        ),
        ScaffoldFile(
            path=harness_path / "prompts" / "pull_request_prompt.md",
            content=PULL_REQUEST_PROMPT_TEMPLATE,
        ),
        ScaffoldFile(
            path=Path("docs") / "plans" / "example-plan.md",
            content=EXAMPLE_PLAN_TEMPLATE,
        ),
    ]
