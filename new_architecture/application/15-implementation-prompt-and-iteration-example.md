# Implementation Prompt and Iteration Example

## Purpose

Provide a copyable implementation prompt definition and one canonical accepted-iteration flow.

## Canonical Implementation Prompt Models

```python
from pydantic import BaseModel, Field


class ImplementationPromptInput(BaseModel):
    feature_id: str
    specification_path: str
    plan_path: str | None = None
    research_path: str | None = None
    handoff_path: str | None = None
    retry_feedback: str | None = None


class ImplementationPromptOutputV1(BaseModel):
    summary: str
    changed_paths: list[str] = Field(default_factory=list)
    follow_up_notes: list[str] = Field(default_factory=list)
```

`FeatureIterationService` uses `ImplementationPromptOutputV1` for iteration reporting and telemetry only.
Specification truth still comes from reloading repository artifacts after the agent run.

## Canonical Implementation PromptDefinition Object

```python
IMPLEMENTATION_DEFAULT = PromptDefinition(
    prompt_id="implementation_default",
    purpose="Execute the active work unit from a feature specification.",
    target="implementation",
    output_mode="structured",
    token_budget_hint=6000,
    input_model=ImplementationPromptInput,
    output_model=ImplementationPromptOutputV1,
    interpolations=[
        PromptInterpolation(
            name="feature_id",
            source="feature_specification.id",
            required=True,
            render_as="scalar",
            content_policy="summary_only",
            content_bound=None,
            rationale="The agent should know which feature it is executing.",
        ),
        PromptInterpolation(
            name="specification_path",
            source="runtime.specification_path",
            required=True,
            render_as="path_list",
            content_policy="path_only",
            content_bound=None,
            rationale="The agent should read the selected specification file itself.",
        ),
        PromptInterpolation(
            name="plan_path",
            source="runtime.plan_path",
            required=False,
            render_as="path_list",
            content_policy="path_only",
            content_bound=None,
            rationale="The agent should read the selected plan file when one exists.",
        ),
        PromptInterpolation(
            name="research_path",
            source="runtime.research_path",
            required=False,
            render_as="path_list",
            content_policy="path_only",
            content_bound=None,
            rationale="The agent should read the research file when one exists.",
        ),
        PromptInterpolation(
            name="handoff_path",
            source="runtime.handoff_path",
            required=False,
            render_as="path_list",
            content_policy="path_only",
            content_bound=None,
            rationale="The agent should read the persisted handoff file when continuing the same feature.",
        ),
        PromptInterpolation(
            name="retry_feedback",
            source="runtime.retry_feedback",
            required=False,
            render_as="markdown_block",
            content_policy="summary_only",
            content_bound=None,
            rationale="The latest correction loop should be available when retrying.",
        ),
    ],
)
```

## Canonical `harness/prompts/implementation_default.py`

```python
def implementation_default(data: ImplementationPromptInput) -> str:
    sections = [
        f"Feature: {data.feature_id}",
        "Read and follow these files:",
        f"- specification: {data.specification_path}",
    ]
    if data.plan_path:
        sections.append(f"- plan: {data.plan_path}")
    if data.research_path:
        sections.append(f"- research: {data.research_path}")
    if data.handoff_path:
        sections.append(f"- handoff: {data.handoff_path}")
    if data.retry_feedback:
        sections.extend(["", "Retry feedback:", data.retry_feedback])
    return "\n".join(sections)


PROMPT_DEFINITION = IMPLEMENTATION_DEFAULT
```

The canonical implementation prompt stays artifact-oriented.
Repository-specific workflow rules such as whether Python uses `uv` belong in `AGENTS.md` or equivalent repo guidance, not in the generic prompt definition itself.
Testing expectations should usually come from the specification, plan, and checks configuration rather than ad hoc prompt-only instructions.

## Specification to Implementation Flow

1. write `specification.yaml` in `draft`
2. for `direct` work, no `plan.md` is required
3. for `researched` work, complete `research.md` before authoring `plan.md`
4. for `planned` and `researched` work, add `plan.md`
5. validate artifacts and move the specification to `ready`
6. let the harness move `ready -> active` when it selects the work
7. run the accepted-iteration loop, creating one accepted-iteration commit on the feature branch for each successful iteration, until the final accepted iteration also marks the specification `done` and archives it

## Accepted Iteration Decision Table

| Step | Condition | Action | Result |
| --- | --- | --- | --- |
| workspace gate | isolated feature workspace is clean | continue | iteration may start |
| selection | executable `active` or `ready` specification exists | choose deterministic candidate | one feature and optional phase selected |
| startup validation | selected specification and global harness rules validate | continue | agent execution may begin |
| activate | selected specification is `ready` | write provisional `active` status in the workspace | selected work becomes the active attempt |
| prompt render | prompt definition validates | build implementation prompt | one typed `AgentRunRequest` |
| implementation | agent returns structured output | reload repository artifacts | repository state becomes the source of truth |
| validation | repository and harness rules pass | continue | deterministic validation pass |
| quality | `iteration_end` catalog checks and generated verification checks pass | continue | deterministic quality pass |
| completion gates | feature is a completion candidate | run `feature_done` check groups, including reviewer checks when configured | completion checks pass |
| persistence | all required gates passed | prepare provisional `done` and archive updates when completion is confirmed, then create the accepted-iteration commit | `commit_created=True` makes provisional state authoritative |
| no-op commit | staged diff is empty | do not persist completion state; finalize the iteration as not accepted | no authoritative `done` or `archived` transition |
| finalization | iteration result has been determined | append progress event, emit `IterationReport`, and emit handoff when the feature remains unarchived | iteration outcome is durable and explainable |

## Accepted Iteration Pseudocode

```text
assert workspace is clean or block for reset
select candidate
run blocking startup validation
if selected spec is ready, write provisional active status
render implementation prompt
run agent
reload specification artifacts
expand generated verification checks from to-be-persisted phase completions
run validation
run catalog checks
run generated verification checks
run feature_done checks if completion candidate
prepare provisional done/archive updates if completion confirmed
create accepted-iteration commit
if commit_created is false:
    append progress event
    emit iteration report
    emit handoff
    stop without authoritative state change
append progress event
emit iteration report
if feature remains unarchived:
    emit handoff
```

If validation, checks, or review fail, the workspace remains dirty until explicit reset.
Failures follow the same finalization rule: append progress events, write an `IterationReport`, and emit handoff whenever the feature remains unarchived.
Any `active` or phase-status writes remain provisional and do not become authoritative until the accepted-iteration commit succeeds.

## Minimal Planned-Mode Fixture Tree

```text
docs/specifications/features/FEAT-001/
  specification.yaml
  plan.md
harness/
  checks.yaml
  prompts/
    implementation_default.py
    reviewer_architecture.py
  reviewers/
    architecture-review.yaml
```

This is the smallest repository shape that should support one successful local iteration.
