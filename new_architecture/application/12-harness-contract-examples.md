# Harness Contract Examples

## Purpose

Provide canonical harness examples that are concrete enough to guide implementation.

## Canonical `harness/checks.yaml`

```yaml
groups:
  - group_id: style
    description: Style and linting checks.
    checks: [ruff]
  - group_id: typecheck
    description: Static type checks.
    checks: [pyright]
  - group_id: tests
    description: Automated tests that prove changed behavior.
    checks: [pytest]
  - group_id: reviewer
    description: Reviewer checks used for completion.
    checks: [architecture-review]
  - group_id: fitness
    description: Architecture fitness functions.
    checks: [domain-isolation]

checks:
  - check_id: ruff
    check_type: command
    phases: [iteration_end, feature_done]
    trigger:
      mode: always
    failure_policy: stop
    config:
      command: [uv, run, ruff, check, .]

  - check_id: pyright
    check_type: command
    phases: [iteration_end, feature_done]
    trigger:
      mode: always
    failure_policy: stop
    config:
      command: [uv, run, pyright]

  - check_id: pytest
    check_type: command
    phases: [iteration_end, feature_done]
    trigger:
      mode: always
    failure_policy: stop
    config:
      command: [uv, run, pytest]

  - check_id: architecture-review
    check_type: reviewer
    phases: [feature_done]
    trigger:
      mode: always
    failure_policy: stop
    config:
      reviewer_id: architecture-review

  - check_id: domain-isolation
    check_type: fitness
    phases: [startup, feature_done]
    trigger:
      mode: always
    failure_policy: stop
    config:
      rule_id: FF-001
```

For Python repositories, `uv` is the canonical environment and dependency manager.
Command-backed checks should invoke Python tools through `uv run` rather than relying on ambient virtualenv activation.

## Canonical `harness/fitness_functions/rules.yaml`

```yaml
rules:
  - rule_id: FF-001
    name: Domain isolation
    kind: static
    entrypoint: harness.fitness_functions.rules.domain_isolation:run
    description: Prevent domain code from importing outer layers.
    failure_message: Domain layer imports application or adapter code.
```

## Canonical Reviewer Definition

```yaml
reviewer_id: architecture-review
title: Architecture Review
purpose: Confirm that the completed change respects the declared architecture rules.
prompt_definition: reviewer_architecture
output_model: harness.reviewers.schemas.ReviewerDecisionV1
approval_policy: required
```

## Canonical Serialized Registry View

```python
REVIEWER_ARCHITECTURE_METADATA = {
    "prompt_id": "reviewer_architecture",
    "purpose": "Review the diff for architectural compliance.",
    "target": "reviewer",
    "output_mode": "structured",
    "token_budget_hint": 5000,
    "input_model": "harness.prompts.reviewer_architecture.ReviewerPromptInput",
    "output_model": "harness.reviewers.schemas.ReviewerDecisionV1",
    "interpolations": [
        {
            "name": "approval_criteria",
            "source": "runtime.approval_criteria",
            "required": True,
            "render_as": "bullet_list",
            "content_policy": "summary_only",
            "content_bound": None,
            "rationale": "The reviewer needs explicit approval criteria.",
        },
        {
            "name": "diff_summary",
            "source": "runtime.diff_summary",
            "required": True,
            "render_as": "markdown_block",
            "content_policy": "summary_only",
            "content_bound": None,
            "rationale": "The reviewer needs the relevant architectural change summary.",
        },
        {
            "name": "changed_paths",
            "source": "runtime.changed_paths",
            "required": True,
            "render_as": "path_list",
            "content_policy": "path_only",
            "content_bound": None,
            "rationale": "File paths are enough unless excerpts are explicitly requested.",
        },
    ],
}
```

This is a serialized registry view for inspection and loading.
The authoritative v1 shape is the Python `PromptDefinition` object shown below.

## Canonical Python Prompt Function

```python
from pydantic import BaseModel, Field


class ReviewerPromptInput(BaseModel):
    approval_criteria: list[str]
    changed_paths: list[str]
    diff_summary: str


class ReviewerDecisionV1(BaseModel):
    approved: bool
    reasons: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)


def reviewer_architecture(data: ReviewerPromptInput) -> str:
    criteria = "\n".join(f"- {item}" for item in data.approval_criteria)
    changed = "\n".join(f"- {path}" for path in data.changed_paths)
    return f"""
Review the change against the architecture rules.

Approval criteria:
{criteria}

Changed paths:
{changed}

Diff summary:
{data.diff_summary}
""".strip()
```

This is the canonical v1 implementation shape.
The harness should treat the callable plus its input/output models as the real prompt definition.

## Canonical Reviewer Output Model

```python
from pydantic import BaseModel, Field


class ReviewerDecisionV1(BaseModel):
    approved: bool
    reasons: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
```

The reviewer definition binds directly to this Python model.
Adapters must validate structured output against the bound model before returning to application services.

## Canonical PromptDefinition Object

```python
REVIEWER_ARCHITECTURE = PromptDefinition(
    prompt_id="reviewer_architecture",
    purpose="Review the diff for architectural compliance.",
    target="reviewer",
    output_mode="structured",
    token_budget_hint=5000,
    input_model=ReviewerPromptInput,
    output_model=ReviewerDecisionV1,
    interpolations=[...],
)
```

## Canonical Quality Profile Binding

```yaml
quality_profile:
  validation: required
  iteration_end_groups: [style, typecheck, tests]
  feature_done_groups: [style, typecheck, tests, fitness, reviewer]
  reviewer_policy: required_on_completion
```

The `tests` group is expected to contain focused unit or integration coverage for the behavior introduced or changed by the current slice, not only broad repository smoke checks.

## Canonical Execution-Target Configuration

```toml
[execution]
mode = "local_worktree"

[vcs]
integration_branch = "main"

[paths]
worktree_root = ".engineeringagent/worktrees"
```

Future remote mode may extend this shape:

```toml
[execution]
mode = "remote_container"
publish_strategy = "branch_push"
reconcile_strategy = "returned_commit"

[vcs]
integration_branch = "main"

[paths]
worktree_root = ".engineeringagent/worktrees"

[execution.remote]
endpoint = "https://example.invalid/containers/run"
environment = "engineeringagent-python"
```
