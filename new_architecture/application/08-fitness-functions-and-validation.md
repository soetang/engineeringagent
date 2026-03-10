# Fitness Functions and Validation

## Purpose

Define the structural rules that keep the architecture intact and the validations that keep the harness trustworthy.

## Three Enforcement Mechanisms

### Static validation

Runs without side effects.
Used for schema conformance, repository integrity, boundary rules, and harness configuration.

### Runtime checks

Run during harness execution.
Used for command checks, executable fitness functions, and reviewer workflows.

### Fitness functions

Executable rules that continuously protect architectural and process intent.
Some fitness functions are static validators; others run as command-backed checks.

## Harness Layout

```text
harness/
  checks.yaml
  prompts/
    *.py
  fitness_functions/
    rules.yaml
    rules/
      *.py
  reviewers/
    *.yaml
  validators/
    *.py
```

## Canonical Harness Contracts

### `harness/checks.yaml`

The check catalog should define two things: named groups and concrete checks.

Required group fields:

- `group_id`
- `description`
- `checks`

Required check fields:

- `check_id`
- `check_type` (`command`, `fitness`, or `reviewer`)
- `phases` (`startup`, `iteration_end`, and/or `feature_done`)
- `trigger.mode` (`always`, `on_change`, or `manual`)
- `failure_policy` (`stop` or `continue`)
- `config`

The `quality_profile` inside a feature specification binds to these groups through `iteration_end_groups` and `feature_done_groups`.
Default Python groups should map to `ruff` for style, `pyright` for type checking, and `pytest` for tests.
See `12-harness-contract-examples.md` for a canonical `checks.yaml` example.

### Reviewer definition contract

Each reviewer definition should declare:

- `reviewer_id`
- `title`
- `purpose`
- `prompt_definition`
- `output_model`
- `approval_policy`

Reviewer definitions live under `harness/reviewers/` and are resolved as part of `ChecksCatalogRepository.load()`.

### Fitness manifest contract

`harness/fitness_functions/rules.yaml` should declare:

- `rule_id`
- `name`
- `kind` (`static` or `runtime`)
- `entrypoint`
- `description`
- `failure_message`

Each manifest entry maps to one executable rule implementation under `harness/fitness_functions/rules/` and is resolved as part of `ChecksCatalogRepository.load()`.

### Prompt definition contract

Each prompt definition should declare:

- `prompt_id`
- `purpose`
- `target`
- `output_mode`
- `token_budget_hint`
- `input_model`
- `output_model`
- `interpolations`

Each interpolation declaration should declare:

- `name`
- `source`
- `required`
- `render_as`
- `content_policy`
- `content_bound`
- `rationale`

`content_policy` must default to `path_only` for file-derived values unless the prompt definition explicitly requests excerpts or full content, and `content_bound` must be present whenever bounded content is allowed.

## Validation Families

### 1. Specification validation

Protects the specification domain.

Validates:

- `specification.yaml` required fields and enums
- `plan.md` presence and phase metadata for planned and researched work
- `research.md` presence for researched work
- status alignment between specification and phases
- required quality-profile fields

### 2. Harness validation

Protects quality configuration.

Validates:

- `harness/checks.yaml` structure
- uniqueness of check identifiers and rule identifiers
- reviewer definition references
- check-group references used by quality profiles
- phase names and trigger policies
- Python command checks and generated verification commands use `uv run` unless the repository explicitly declares a non-`uv` Python toolchain

### 3. Architecture validation

Protects ports-and-adapters structure.

Validates:

- domain isolation
- ports are declared as Python `Protocol` contracts
- application-to-port dependency discipline
- adapter containment of vendor-specific execution
- presentation isolation from business rules
- single agent-runner boundary

### 4. Guidance and documentation validation

Protects operator-facing discoverability.

Validates:

- topic identifiers
- alias uniqueness
- required headings and metadata
- broken references inside guidance bundles

### 5. Configuration validation

Protects bootstrap correctness.

Validates:

- selected backend identifier
- selected model identifier
- repository path configuration
- required harness paths
- prompt definition identifiers referenced by configuration
- incompatible option combinations

### 6. Prompt validation

Protects prompt assembly discipline.

Validates:

- template metadata fields
- interpolation names and source references
- prompt input and output model declarations
- prompt-definition callables resolve and render deterministically
- explicit content policy for file-derived values
- token budget hints and bounded-content metadata

### 7. Version-control validation

Protects isolated execution policy.

Validates:

- configured integration branch
- worktree root path
- branch naming pattern
- no execution-in-place mode when isolated workspaces are required

### 8. Execution-target validation

Protects local versus remote execution discipline.
This family is optional and post-v1 only.

Validates:

- selected execution target identifier
- required publish and reconciliation settings
- remote target credentials or endpoints when configured
- authoritative-workspace policy when remote execution is enabled

## Core Fitness Functions

| ID | Name | Protects | Enforcement |
| --- | --- | --- | --- |
| `FF-001` | Domain isolation | The domain does not depend on application, ports, adapters, presentation, or bootstrap | static import-graph validator |
| `FF-002` | Application port discipline | Application services depend on ports defined as Python `Protocol` contracts, not concrete adapters | static import-graph validator |
| `FF-003` | Adapter containment | Vendor CLIs and backend-specific protocols appear only inside adapters | static boundary validator |
| `FF-004` | Presentation separation | Printing, ANSI formatting, and CLI-specific output stay inside presentation | static AST or text validator |
| `FF-005` | Single agent-runner boundary | Agent execution always flows through one `AgentRunner` port | static boundary validator |
| `FF-006` | Specification package integrity | Every feature specification package contains the required artifacts for its planning mode | repository validator |
| `FF-007` | Status and plan alignment | Specification status and phase status cannot contradict each other | repository validator |
| `FF-008` | Deterministic check planning | The same inputs yield the same run or skip decisions | runtime dry-run test |
| `FF-009` | Quality ordering | Reviewer checks do not run before deterministic validation and runtime checks succeed | runtime integration check |
| `FF-010` | Append-only audit trail | Progress journals record new events without silently rewriting history | repository validator plus runtime check |
| `FF-011` | Prompt interpolation declaration | Every interpolated value is declared in the prompt definition contract | prompt validator |
| `FF-012` | Minimal file-context policy | File-derived values default to path-only rendering unless a template explicitly overrides it | prompt validator |
| `FF-013` | Stable prompt rendering | The same inputs produce the same interpolation order and prompt text | prompt snapshot test |
| `FF-014` | Isolated workspace policy | Implementation and review run in the feature workspace rather than the integration checkout | repository validator plus runtime check |
| `FF-015` | Base-branch diff discipline | Reviewers and completion checks evaluate the diff against the configured integration branch | runtime integration check |
| `FF-016` | Execution-target declaration | Optional remote mode declares a valid target and publish strategy | configuration validator |
| `FF-017` | Authoritative workspace discipline | Optional remote mode never makes the integration checkout the active mutation surface | runtime integration check |
| `FF-018` | Reconciliation integrity | Optional remote mode reconciles changes deterministically into the authoritative feature workspace | runtime integration check |

## Recommended Additional Fitness Functions

- `FF-019` no hidden mutable runtime state outside explicit services and journals
- `FF-020` contract-change evidence required whenever a specification declares a changed surface
- `FF-021` every iteration outcome emits a machine-readable iteration report
- `FF-022` when continuing the same feature, the prompt builder injects the latest persisted `handoff.md` path as `handoff_path` instead of inlining its contents
- `FF-023` Python command checks and generated verification commands run through `uv`
- `FF-024` behavior-changing phases include focused unit or integration test evidence, or declare an explicit docs/config-only exception

## Validation Command Contract

The `validate` command should be side-effect free and deterministic.
It returns structured issues with at least:

- validator id
- scope
- logical path
- stable rule code
- message

The command should fail fast on malformed documents but still aggregate independent issues when possible.

`run` should always invoke blocking startup validation before any implementation agent call or runtime check execution.
That startup validation may be scoped to the selected specifications plus global harness and architecture rules, while `validate` remains the full repository pass.

For Python repositories, canonical command execution flows through `uv`.
Validators should reject check definitions or phase `verification_commands` that invoke Python tools directly without `uv run`, unless the specification explicitly opts into a different toolchain.

## Runtime Check Contract

The `checks run` command should:

1. build a shared check context
2. plan all eligible checks deterministically
3. execute only `run` decisions
4. stop on the first failure when policy requires it
5. return prompt-ready failure feedback plus structured execution records

Verification-command normalization is canonical:

- convert each phase `verification_commands` entry into a generated command check with id `verify::<feature-id>::<phase-id>::<index>`
- generated checks use `check_type=command`, `phases=[iteration_end]`, and `failure_policy=stop`
- require argv vectors in the specification model, dedupe by exact argv tuple, and keep the catalog check on collision
- execute catalog checks first in catalog order, then remaining generated checks in plan order, only for phases that transitioned to `done` in the current iteration

## Harness Phases

Recommended phases:

- `startup`: validate architecture, configuration, and harness structure
- `iteration_end`: run checks relevant after one implementation iteration
- `feature_done`: run completion checks and reviewer requirements

Not every check runs in every phase, but every phase must be explicit in the check catalog.

## Failure Semantics

- validation failure blocks execution before side effects
- runtime check failure stops the current iteration
- reviewer rejection returns actionable feedback and keeps deterministic failures visible
- fitness-function failure is treated as a normal quality failure with a stable rule id

## What Makes the Harness Trustworthy

The harness is trustworthy when:

- structure is validated before execution
- runtime quality policy is declarative and deterministic to plan
- architectural boundaries are enforced continuously
- the audit trail explains what happened without relying on chat history

That is the role of validation and fitness functions in this design.
