# Markdown Task Adapter Plan

## Goal

Add a real task adapter layer so `developer implement path-to-plan.md` resolves a markdown-backed task definition instead of using a raw string.

The first adapter should read a plan markdown file with YAML frontmatter, validate it, and expose a stable task object for:

- task identity;
- branch naming;
- completion checks; and
- future publication reuse.

Phases should stay intentionally simple in v1 and exist mainly to track structured status.

This work should also add a dedicated `developer validate-plan path-to-plan.md` command so plan authors can validate task files before execution.

## Scope

Initial scope:

- keep the task subsystem adapter-based so future task formats can be added without changing CLI or orchestrator code;
- support one task adapter family in v1: markdown plan files with YAML frontmatter;
- treat the markdown plan file as the source of truth for task identity and completion state;
- require both top-level task status and all phase statuses to report completion;
- allow `implement path-to-plan.md` to accept a plan path and resolve it into a task object before orchestration;
- make iteration limits configurable through TOML and overridable from the `implement` CLI;
- inject the resolved plan path into the implementation prompt context so the agent knows which plan file to follow; and
- add a CLI validation command for a single plan path.

Out of scope for this slice:

- background execution;
- automatic phase mutation or workflow state transitions;
- editing plan files from the runtime;
- multiple plan storage backends beyond the first markdown adapter; and
- task discovery commands such as listing all plans in a repository.

This task-format work should not be treated as a hard prerequisite for later async execution work.

It is still a good standalone improvement, but the async/background design should not assume it must wait on this adapter slice.

## Current State

- `src/developer/application/services/implementation_run_service.py` constructs `SimpleImplementationTask(task_name)` directly.
- `src/developer/tasks/implementation_task.py` contains only a stub task object whose completion always returns `COMPLETE`.
- `src/developer/tasks/protocol.py` defines a very small task interface but there is no resolver or adapter selection boundary.
- `src/developer/application/workspace_bridges.py` rebuilds the same stub task inside workspace runs from raw request context.
- `docs/plans/version-control-implementation-plan.md` already expects implementation task input to resolve into the task module before orchestration.
- `src/developer/orchestrators/implementation_agent.py` currently passes both `task_name` and `task_path` into the prompt-builder context.
- `harness/implementation_prompt.md` does not currently use `task_path`, so the resolved plan path is not surfaced to the agent in the rendered prompt.
- there is not yet a guardrail that blocks plan-backed execution when the caller checkout has uncommitted changes.

## Recommended Design

Keep the task subsystem shaped like the version-control and forge subsystems:

- a task protocol layer for the runtime-facing contract;
- task models for parsed and validated plan data;
- a task adapter protocol for resolving user input into task objects;
- an adapter selector service that returns the configured adapter or infers one from input; and
- a markdown-plan adapter as the first concrete implementation.

This preserves flexibility for future formats such as JSON, database-backed tasks, or external issue tracker adapters.

### Runtime Contract

The implementation loop should still depend only on `ImplementationTask`.

Recommended contract behavior:

- `task_name` should return a stable human-readable task title or display name;
- `task_path` should return the canonical plan path for markdown-backed tasks;
- `get_branch_name()` should return the explicit branch from frontmatter or a deterministic default derived from `task_id`; and
- `is_complete()` should re-read the plan file from disk each time and return `COMPLETE` only when the task is marked `done` and all phases are marked `done`.

Why re-read on completion checks:

- the plan file is expected to be edited by the agent during execution;
- completion must reflect the latest on-disk frontmatter state rather than a stale in-memory snapshot; and
- this keeps the task object aligned with the real plan source of truth.

### CLI Path Syntax

Support plan inputs with or without a leading `@`.

Recommended behavior:

- `developer implement @docs/plans/my-plan.md`
- `developer implement docs/plans/my-plan.md`
- `developer validate-plan @docs/plans/my-plan.md`
- `developer validate-plan docs/plans/my-plan.md`
- accept either `path/to/plan.md` or `@path/to/plan.md`;
- treat leading-`@` normalization as presentation-layer input handling;
- strip the leading `@` when present before filesystem resolution; and
- fail clearly only when the normalized value does not point to a markdown file.

Why this fits:

- `@` already reads as a special agent-facing reference marker;
- it makes plan-file execution visually distinct from freeform task text; and
- it leaves room for other task input forms later without overloading bare strings.

### Iteration Limits

While changing `implement`, also make iteration limits configurable.

Recommended behavior:

- add a TOML-backed `max_iterations` setting for implementation runs;
- default to `40` rather than the current low hardcoded limit;
- allow CLI override via `developer implement <plan-path> --max-iterations ...`; and
- support explicit infinite mode in both config and CLI.

Recommended accepted values:

- finite positive integers such as `10` or `40`
- the string `infinite`

Recommended precedence:

- CLI `--max-iterations`
- TOML setting
- default `40`

Recommended config shape after this change:

```toml
[implementation]
max_iterations = 40

[prompts]
implementation_prompt_path = "harness/implementation_prompt.md"
commit_prompt_path = "harness/prompts/commit_message_prompt.md"
pull_request_prompt_path = "harness/prompts/pull_request_prompt.md"
```

Do not add a new `[implementation_agent]` section.

Also update the repository root `engineeringagent.toml` as part of this change so the checked-in example config reflects the new section layout.

Recommended internal representation:

- normalize `infinite` to `None` at the application boundary;
- keep finite values as validated positive integers; and
- reject `0` and negative numbers.

### Prompt Context

The implementation prompt should explicitly include the resolved plan path.

Why this matters:

- the implementation prompt should be driven by the plan path rather than a duplicated task name;
- the markdown plan file is the actual task definition the agent should follow; and
- prompt visibility makes it much less likely the agent ignores the plan structure.

Recommended changes:

- change the prompt context to include `feedback` and `task_path` only;
- update `harness/implementation_prompt.md` to instruct the agent to use the plan at `{{ task_path }}` as the source of truth for work sequencing and completion; and
- keep `task_name` available on the task object and execution context for CLI output, metadata, and publication flows, but remove it from prompt rendering inputs.

### Markdown Plan Format

The first adapter should support markdown files that begin with YAML frontmatter.

Recommended frontmatter schema:

```yaml
---
schema_version: 1
task_id: add-background-workspace-runs
title: Add background workspace runs
status: ready
branch: feat/add-background-workspace-runs
base_branch: main
phases:
  - id: runtime
    title: Runtime foundation
    status: todo
  - id: cli
    title: CLI and status UX
    status: todo
---
```

Recommended required fields:

- `schema_version`
- `task_id`
- `title`
- `status`
- `phases`

Recommended optional fields:

- `branch`
- `base_branch`

Recommended task status enum:

- `draft`
- `ready`
- `in_progress`
- `blocked`
- `done`

Recommended phase status enum:

- `todo`
- `in_progress`
- `blocked`
- `done`

Recommended phase shape:

- `id`
- `title`
- `status`

Do not add dependency fields in v1.

Reasoning:

- the background agent will own sequencing decisions;
- phases are primarily for structured progress tracking and completion checks; and
- keeping phase metadata small makes the format easier to author and validate.

Recommended markdown body convention:

- the file body remains normal markdown for human-readable implementation notes; and
- v1 validation should ignore markdown body structure completely and validate frontmatter only.

Example:

```md
---
schema_version: 1
task_id: add-background-workspace-runs
title: Add background workspace runs
status: ready
branch: feat/add-background-workspace-runs
base_branch: main
phases:
  - id: runtime
    title: Runtime foundation
    status: todo
  - id: cli
    title: CLI and status UX
    status: todo
---

# Goal

Describe the feature goal here.

## Notes

Implementation notes for the task live here.
```

### Completion Semantics

Completion should use both top-level task state and phase state.

Recommended rule:

- report complete only when task `status == "done"` and every phase `status == "done"`.

Recommended implications:

- if task status is `done` while any phase is not `done`, validation should fail;
- if all phases are `done` but task status is not `done`, `is_complete()` should still report incomplete; and
- `todo`, `in_progress`, and `blocked` phase statuses all block completion.

Implementation note:

- the concrete markdown-backed task should keep stable identity fields in memory, but it should re-parse current frontmatter from `task_path` when evaluating completion.

### Adapter Selection

The initial adapter selector can be simple.

Recommended behavior:

- if the user passes a `...md` or `@...md` input, normalize it to a filesystem path and resolve it through the markdown-plan adapter;
- fail clearly for unsupported inputs instead of silently falling back to the stub task; and
- keep the selector in a dedicated service so a future config-driven or multi-format resolver can be added without changing call sites.

## Proposed Package Shape

Recommended additions under `src/developer/tasks/`:

- `protocol.py` - keep the runtime `ImplementationTask` protocol
- `models.py` - add parsed task and phase models
- `adapter_protocol.py` - add task adapter interface
- `select_service.py` - add task adapter selection/resolution service
- `services/markdown_plan_parser.py` - parse frontmatter and markdown body
- `services/plan_validator.py` - validate parsed plans and return structured errors
- `adapters/markdown_plan_adapter.py` - resolve a markdown path into a concrete task object
- `implementation_task.py` - replace or extend stub task usage with a real plan-backed implementation task

Recommended test additions:

- `tests/tasks/test_markdown_plan_parser.py`
- `tests/tasks/test_plan_validator.py`
- `tests/tasks/test_markdown_plan_adapter.py`
- `tests/presentation/test_validate_plan_cli.py`
- `tests/prompts/test_builder.py`

## Concrete Code Changes

### 1. Task Models

Update `src/developer/tasks/models.py`.

Add models for:

- `TaskPhaseDefinition`
  - `id: str`
  - `title: str`
  - `status: str`
- `TaskPlanDefinition`
  - `schema_version: int`
  - `task_id: str`
  - `title: str`
  - `status: str`
  - `branch: str | None`
  - `base_branch: str | None`
  - `phases: list[TaskPhaseDefinition]`
  - `path: str`
- `PlanValidationError`
  - `location: str`
  - `message: str`
- `PlanValidationResult`
  - `valid: bool`
  - `errors: list[PlanValidationError]`

Keep `TaskPublicationState` in this file unless it becomes clearer to split persistence models later.

### 2. Task Adapter Protocol

Add `src/developer/tasks/adapter_protocol.py`.

Recommended interface:

```python
class TaskAdapter(Protocol):
    def can_resolve(self, task_input: str) -> bool:
        ...

    def resolve(self, task_input: str) -> ImplementationTask:
        ...

    def validate(self, task_input: str) -> PlanValidationResult:
        ...
```

The runtime will only need `resolve()`, but including `validate()` keeps `developer validate-plan` and execution-time validation on the same underlying implementation.

### 3. Markdown Parsing Service

Add `src/developer/tasks/services/markdown_plan_parser.py`.

Recommended responsibilities:

- read a markdown file from a provided path;
- split YAML frontmatter from markdown body;
- parse frontmatter into Python data;
- normalize the path to a canonical string; and
- build a `TaskPlanDefinition` candidate object from frontmatter or raise a parse error that the validator can surface cleanly.

Implementation notes:

- prefer a small YAML dependency only if the project already uses or accepts one; otherwise use a lightweight parser strategy intentionally;
- parsing errors should include the path and a clear reason; and
- keep parsing separate from semantic validation so error reporting stays precise.

### 4. Plan Validation Service

Add `src/developer/tasks/services/plan_validator.py`.

Recommended validation rules:

- frontmatter exists;
- required fields exist and have the correct types;
- `schema_version == 1` for v1;
- `task_id` is slug-like and stable;
- `branch`, when present, is non-empty;
- `base_branch`, when present, is non-empty;
- there is at least one phase;
- phase ids are unique;
- task status `done` requires every phase status to be `done`; and
- no markdown body validation is required in v1.

Recommended output:

- return a structured `PlanValidationResult` for CLI usage; and
- raise only for true read/parse failures that prevent any meaningful validation result.

### 5. Markdown Plan Adapter

Add `src/developer/tasks/adapters/markdown_plan_adapter.py`.

Recommended behavior:

- accept markdown task inputs with or without a leading `@` and resolve them to filesystem paths;
- parse and validate the file;
- if invalid, raise a clear error suitable for surfacing in the CLI;
- construct a concrete `ImplementationTask` implementation backed by the parsed plan; and
- derive `get_branch_name()` from frontmatter `branch` or from `task_id` when omitted.

The adapter-backed task should also re-read frontmatter from disk inside `is_complete()` rather than relying only on the state captured at resolve time.

The concrete task object should expose:

- `task_name` -> `title`
- `task_path` -> canonical markdown path
- stable access to `task_id`, `status`, and `phases` for future workspace metadata expansion

### 6. Task Selection Service

Add `src/developer/tasks/select_service.py`.

Recommended behavior:

- hold the available adapters;
- resolve a task input to the first matching adapter;
- provide a `validate_plan(path)`-style entrypoint for the CLI command; and
- fail with an actionable error when no adapter can handle the input.

This file is the key abstraction that preserves the adapter style for later formats.

### 7. Replace Stub Resolution In The Application Service

Update `src/developer/application/services/implementation_run_service.py`.

Recommended edits:

- stop constructing `SimpleImplementationTask(task_name)` directly;
- resolve the provided `task_name` input through the task selection service;
- fail fast when the current checkout has uncommitted changes before creating a workspace or starting direct execution;
- resolve `max_iterations` from CLI input or config and pass the normalized value into the orchestrator build path;
- use the resolved task object for branch naming, publication lookup, and orchestration;
- use the resolved task path for publication reuse in workspace mode; and
- fail before workspace creation if the task input cannot be parsed or validated.

This is the main runtime behavior change.

Why the clean-checkout guardrail matters:

- workspaces are created from committed branch state, not from the caller's uncommitted working tree;
- a plan file with local edits may be missing or stale inside the workspace if those edits are not committed; and
- running against a dirty checkout makes it too easy for the agent to act on a plan or repository state that the workspace will not actually contain.

Recommended behavior:

- check for uncommitted tracked or untracked changes before `implement` starts;
- ignore files excluded by normal git ignore rules when enforcing this preflight;
- fail with a clear message instructing the user to commit or stash changes first; and
- do this before workspace creation and before any task resolution that depends on the current repository state.

Add a small configuration seam for iteration limits here rather than hardcoding them in the orchestrator constructor call sites.

### 8. Preserve Task Identity Across Workspace Runs

Update `src/developer/application/workspace_bridges.py`.

Recommended edits:

- stop rebuilding `SimpleImplementationTask` from just `task_name` and `task_path`;
- pass enough request context to re-resolve the same markdown task from path inside the workspace run;
- ensure the workspace-run task object is equivalent to the caller-side task object; and
- keep the workspace bridge depending on the task selection service rather than on markdown-specific details.

Minimum run context additions:

- `task_input`
- optionally `task_id` once available for easier diagnostics

The raw `task_input` may preserve the original user input for diagnostics, while resolution should use the normalized filesystem path.

### 9. Inject The Plan Path Into The Rendered Prompt

Update `src/developer/orchestrators/implementation_agent.py` and `harness/implementation_prompt.md`.

Recommended edits:

- change the prompt-builder context dict to pass only `feedback` and `task_path`;
- include the resolved task plan path explicitly in the instructions;
- tell the agent the markdown plan is the source of truth for the implementation task; and
- treat `task_path` as required for this command shape because `implement` now runs plan-backed tasks only.

Recommended prompt addition:

```md
Task plan path: {{ task_path }}

Use this markdown task plan as the source of truth for what to implement and when the task is complete.
```

This should be a small orchestrator change rather than a broader contract redesign.

### 10. CLI Command For Plan Validation

Add a new presentation command module or extend the root CLI wiring.

Recommended CLI surface:

- `developer validate-plan path/to/plan.md`

Recommended implementation shape:

- add `src/developer/presentation/commands/plan.py` with a single command;
- register it in `src/developer/presentation/cli.py`; and
- delegate to the shared task selection/validation service.

Recommended command behavior:

- print a clear success line when valid;
- print one error per validation problem when invalid;
- exit `0` on success and `1` on invalid input.

Example success output:

- `✓ Plan validation successful: docs/plans/example.md`

Example failure output:

- `✗ Plan validation failed: docs/plans/example.md`
- `- status: task cannot be 'done' until all phases are 'done'`

### 11. Simplify The Implement Command Surface

Update:

- `src/developer/presentation/commands/implement.py`
- `src/developer/presentation/cli.py`

Recommended edits:

- remove the `run` keyword entirely and make `developer implement <plan-path>` the only execution shape;
- make the plan path a positional argument instead of a `--task` option;
- add `--max-iterations` as an optional override;
- keep help text explicit that the positional argument accepts a markdown plan path with or without a leading `@`; and
- remove `implementation run --task ...` rather than keeping a compatibility alias.

Recommended `--max-iterations` behavior:

- accept a positive integer or the literal `infinite`;
- normalize and validate at the CLI or application boundary;
- pass the normalized value through to the implementation service; and
- describe the config precedence in the command help text.

Recommendation:

- switch fully to `developer implement <plan-path>` in this change, because it matches the mental model better while still allowing optional `@` syntax.

## Validation And Error Handling Strategy

Use two error layers:

1. parse/load errors
   - file missing
   - unreadable file
   - malformed frontmatter

2. preflight execution errors
   - uncommitted changes in the current checkout

3. semantic validation errors
     - invalid status
     - duplicate phase ids
     - inconsistent top-level and phase statuses

4. iteration configuration errors
   - invalid `max_iterations` value in config
   - invalid `--max-iterations` CLI override

Recommended behavior:

- execution should fail fast on either category;
- execution should fail fast on dirty-checkout preflight errors before workspace creation;
- execution should fail fast on invalid iteration-limit configuration before orchestration starts;
- `validate-plan` should show all semantic errors when possible instead of stopping at the first one; and
- user-facing messages should always include the offending path.

## Testing Plan

Most new tests should live around the task adapter and validation layer.

Reasoning:

- most of the new behavior belongs to parsing, validation, adapter selection, and task resolution;
- most of the orchestrator can stay unchanged, but prompt context should be narrowed so only `task_path` is passed into prompt rendering; and
- orchestrator tests should stay narrow and cover only that prompt-context change.

Test fixtures for plans should be created in temporary directories at test time rather than committed as static fixture files.

Recommended approach:

- use pytest tmp-path fixtures to write plan markdown files on demand;
- keep each test focused on only the frontmatter fields relevant to that case;
- validate the temporary file path exactly as the real CLI and adapter code will receive it; and
- avoid a large checked-in matrix of plan fixture files unless a later scenario truly needs shared reusable samples.

### Unit Tests

- frontmatter parsing succeeds for a valid markdown plan
- missing frontmatter fails clearly
- malformed YAML fails clearly
- duplicate phase ids are rejected
- `done` task with incomplete phases is rejected
- branch defaults from `task_id` when omitted
- `is_complete()` returns complete only when task and all phases are `done`
- task adapter resolves valid markdown paths into concrete task objects
- task adapter rejects unsupported file extensions and missing files clearly
- re-writing a temporary plan file from incomplete to complete causes a subsequent `is_complete()` call on the same task object to return complete
- `implement` preflight fails when the checkout has uncommitted changes

Add focused tests for iteration normalization:

- config default falls back to `40` when unset
- config value is used when CLI override is absent
- CLI `--max-iterations` overrides config
- `infinite` normalizes to the internal unbounded representation
- `0` and negative values are rejected

Each of these tests should create its own temporary plan file inside `tmp_path`.

Include one explicit mutation test shape:

- write a temporary plan with `status: in_progress` or an incomplete phase;
- resolve it into a task object and assert `is_complete()` is incomplete;
- rewrite the same file on disk with `status: done` and all phase statuses `done`; and
- assert a second `is_complete()` call on the same task object now reports complete.

### Service / Composition Tests

- `implement <plan-path>` resolves through the task selection service
- workspace execution receives enough context to re-resolve the same task in the workspace
- publication lookup still uses resolved task identity and path
- unsupported task input fails before orchestration starts
- dirty checkout fails before workspace creation starts
- rendered implementation prompt includes the resolved plan path
- rendered implementation prompt does not depend on `task_name`
- resolved iteration limits are passed into the orchestrator build path

These tests should also prefer temporary on-disk plan files over repository fixture files so path resolution behavior is exercised realistically.

### CLI Tests

- `developer validate-plan path/to/plan.md` succeeds for a valid plan
- `developer validate-plan @path/to/plan.md` also succeeds for a valid plan
- `developer validate-plan path/to/plan.md` prints actionable errors for an invalid plan
- `developer implement path/to/plan.md` shows task-derived output for a valid plan
- `developer implement @path/to/plan.md` also shows task-derived output for a valid plan
- `developer implement path/to/plan.md --max-iterations 20` overrides config
- `developer implement path/to/plan.md --max-iterations infinite` enables unbounded mode
- root CLI help lists `validate-plan`

CLI tests should write temporary plan files in the isolated filesystem or pytest temp directory and pass those paths directly to the command.

### Orchestrator Tests

Add one focused orchestrator test for the prompt-context change.

Expected minimal case:

- assert `src/developer/orchestrators/implementation_agent.py` passes `feedback` and `task_path` to the prompt builder; and
- assert it no longer passes `task_name` into prompt rendering.

Add one small orchestrator-level test for unbounded iteration mode only if the implementation changes loop control behavior inside the orchestrator.

## Implementation Order

### Phase 1: Task schema and validation

- extend `src/developer/tasks/models.py`
- add markdown parser service
- add plan validator service
- add unit tests for parsing and validation

### Phase 2: Adapter boundary

- add task adapter protocol
- add markdown plan adapter
- add selection service
- add unit tests for adapter resolution and errors

### Phase 3: Application integration

- update `implementation_run_service.py` to resolve tasks through the selector
- update workspace bridge task reconstruction
- update related application tests
- add configurable `max_iterations` resolution from config and CLI override
- narrow implementation prompt context to `feedback` plus `task_path`
- update the implementation prompt template to surface the plan path
- update config loading so implementation behavior comes from `[implementation]`

### Phase 4: CLI validation command and command-shape cleanup

- add `validate-plan` presentation command
- register the command in the root CLI
- add the simplified `implement <plan-path>` command shape
- add `--max-iterations` CLI override support
- update the repository root `engineeringagent.toml` to use `[implementation]` and `[prompts]`
- add CLI tests

## Open Implementation Choices

Resolve these during implementation, but do not let them block the overall structure.

### YAML Dependency

Decide whether to add a YAML parsing dependency or use an existing transitive dependency if one is already acceptable for the project.

Recommendation:

- use a standard YAML parser if dependency policy allows it, because frontmatter parsing is a core format concern and hand-rolled YAML parsing will be brittle.

### Canonical Task Name

Decide whether `ImplementationTask.task_name` should expose `task_id` or `title`.

Recommendation:

- use `title` for `task_name` because it is better for prompts and terminal output;
- keep `task_id` as separate stable identity inside the concrete task model and workspace metadata.

### Iteration Setting Location

Decide where the TOML-backed implementation iteration setting should live.

Recommendation:

- use a dedicated `[implementation]` TOML section;
- keep the settings model close to the implementation/orchestrator code rather than creating a brand new top-level module just for this setting;
- resolve and inject the setting from the application layer so the orchestrator still receives an already-resolved `max_iterations` value; and
- use `None` internally for unbounded mode.

Concrete placement recommendation:

- add an `ImplementationSettings` model under `src/developer/application/` rather than creating a new standalone package;
- load it through `ConfigService.get_config("implementation", ImplementationSettings)` in the same style as other subsystems; and
- keep the application service responsible for combining config defaults with CLI overrides before constructing the orchestrator.

Config migration note:

- move prompt-path ownership out of legacy `[orchestrator]` usage and keep it under `[prompts]`;
- add `[implementation]` for iteration settings;
- update the checked-in root `engineeringagent.toml` accordingly; and
- remove legacy `[orchestrator]` fallback as part of this change rather than carrying compatibility behavior forward.

## Expected Outcome

After this change:

- the task subsystem remains adapter-based and extensible;
- markdown plans become the first real task format;
- completion checks become meaningful instead of stubbed;
- `implement <plan-path>` operates on a resolved task object, not a freeform string; and
- `implement` supports TOML-configured and CLI-overridden iteration limits, including `infinite`; and
- users can validate a plan explicitly before execution with `developer validate-plan <plan-path>`.
