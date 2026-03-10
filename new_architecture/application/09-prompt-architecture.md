# Prompt Architecture

## Purpose

Define how prompts are authored, how interpolations are declared, and how the harness keeps prompt context explicit and minimal.

## Design Goal

Prompt behavior must be inspectable.
An operator should be able to answer four questions from the template alone:

1. what values may be interpolated
2. where each value comes from
3. whether a file path or file content will be included
4. why that information is necessary

## Core Rule

A prompt is always the result of three explicit inputs:

1. a prompt definition
2. an interpolation contract
3. an application-provided context object

If a value is not declared in the interpolation contract, it cannot appear in the rendered prompt.

## Python-First Authoring Model

Take inspiration from BAML's idea that prompts behave like functions, but keep the implementation entirely in Python.

Recommended rule:

- author prompts as Python functions or callable definitions
- give each prompt a typed input model
- give structured prompts a typed output model
- keep interpolation metadata attached to the prompt definition

This avoids inventing a separate prompt DSL while still making prompts inspectable and testable.

## Prompt Families

### Implementation prompts

Used during feature iteration.
They describe the selected feature specification, active phase, constraints, acceptance criteria, and current quality expectations.

### Reviewer prompts

Used by reviewer checks.
They describe the review objective, approval criteria, changed artifacts, and required output shape.

## Structured Output Model

Structured prompt outputs should be declared as Python data models, preferably `pydantic.BaseModel` types.
Canonical v1 implementation and reviewer prompts both use typed structured output.

The prompt layer should expose three things together:

1. input model
2. rendered prompt body
3. output model

`AgentRunner` adapters then handle provider-specific JSON mode, schema transport, retries, and parsing.
Application services should receive already-validated Python objects.

## Prompt Definition Repository

Prompt definitions are loaded through `PromptDefinitionRepository`.
Default repository-backed prompt definitions live under:

```text
harness/prompts/
  implementation_default.py
  reviewer_architecture.py
```

The repository may load inline strings or helper files however it wants, but the application layer should consume prompt definitions as typed Python objects.

## Lookup Contract

- prompt id `implementation_default` resolves to `<paths.harness_root>/prompts/implementation_default.py`
- the resolved module must export `PROMPT_DEFINITION`
- `PROMPT_DEFINITION` is the authoritative Python `PromptDefinition` object
- duplicate prompt ids or missing exports fail validation

## Canonical Authority

V1 should use Python prompt definitions as the source of truth.
Markdown prompt bodies may exist as authoring helpers, but the authoritative object is the Python definition that binds prompt id, input model, output model, interpolation metadata, and rendering logic.

## Inspection Surface

The presentation layer should expose a dry-run inspection view for prompt definitions.
That view should show:

- prompt metadata
- every declared interpolation
- the source of each interpolation
- the render mode and content policy for each interpolation

This lets operators inspect possible interpolations before an iteration runs.

## Required Prompt Definition Metadata

Each prompt definition must declare:

- `prompt_id`
- `purpose`
- `target`
- `output_mode`
- `token_budget_hint`
- `input_model`
- `output_model`
- `interpolations`

Allowed `target` values:

- `implementation`
- `reviewer`

Allowed `output_mode` values:

- `structured`

## Interpolation Contract

Every interpolation must declare:

- `name`
- `source`
- `required`
- `render_as`
- `content_policy`
- `content_bound`
- `rationale`

`content_bound` must always be present.
Use `null` when no bounded content window is needed.

Allowed `render_as` values:

- `scalar`
- `bullet_list`
- `path_list`
- `markdown_block`
- `json_block`
- `excerpt`
- `full_document`

Allowed `content_policy` values:

- `path_only`
- `summary_only`
- `excerpt_only`
- `full_content`

## Minimal-Context Policy

### Default rule

Only interpolate what is necessary for the current decision or action.

### File rule

If the harness has file paths, it should pass those paths and not file contents unless the template explicitly asks for content.

Examples:

- changed files -> `path_list`
- relevant specification artifacts -> `path_list`
- a failing validator message -> `markdown_block`
- a source-file body -> excluded unless excerpt/full content is explicitly declared

### Escalation rule

File content may be included only when:

1. the template explicitly requires an excerpt or full document
2. metadata and file paths are not enough for the task
3. the content is bounded by an explicit rule

### Bounding rule

When content is allowed, the template must declare the bound:

- `content_bound` with at least `max_lines`, `selection_method`, and whether the content is an excerpt or full document

## Prompt Assembly Pipeline

1. choose the prompt family
2. load the prompt definition and interpolation contract
3. assemble the context object from specification, plan, quality state, and retry feedback
4. resolve only declared interpolations
5. apply minimal-context and bounding rules
6. drop empty optional sections
7. render sections in deterministic order
8. pass the final prompt to `AgentRunner`

## Canonical Implementation Prompt Inputs

Usually include:

- selected feature identifier
- path to `specification.yaml`
- path to `plan.md`, when present
- path to `research.md`, when present
- path to the persisted `handoff.md`, when continuing the same feature
- latest retry feedback
- any additional artifact paths explicitly required by the prompt definition

Usually exclude:

- full contents of every referenced file
- unrelated repository documents
- raw command history unless the retry step needs it

## Canonical Reviewer Prompt Inputs

Usually include:

- review purpose
- approval criteria
- diff summary against the integration branch
- changed artifact paths
- relevant acceptance criteria
- required output schema

Usually exclude:

- full repository history
- unrelated implementation notes
- file contents not directly needed for the review decision

## Conditional Sections

Templates should support simple conditional rendering:

- include a section only when its interpolation resolves to a value
- omit empty headings
- preserve deterministic section order

## Repository Guidance Boundary

Generic prompt definitions should stay portable across repositories.
Repository-specific operational instructions such as package-manager choice, environment activation, or local command conventions belong in repository guidance files such as `AGENTS.md`.
Prompt definitions may point the agent at those files by path, but should not hardcode repository-local workflow policy when referenced artifacts and repo guidance are enough.

## Validation Rules

The harness rejects a prompt definition when:

- required metadata is missing
- an interpolation is undeclared
- a placeholder appears without a matching interpolation
- a file-derived interpolation lacks explicit `content_policy`
- excerpt or full-content rendering lacks a bounding rule

## Concrete Example

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


PROMPT_DEFINITION = IMPLEMENTATION_DEFAULT
```

The canonical module exports `PROMPT_DEFINITION`, omits empty optional sections, and passes `handoff_path` as a file path rather than interpolating handoff contents.

## Design Outcome

This design makes prompt context intentional instead of accidental.
The harness can show possible interpolations up front, keep file content out by default, and still allow richer prompts when the template explicitly justifies them.
