# Checks Orchestration Architecture (To-Be)

## Purpose

Define a checks architecture where the loop does not know concrete check types, check timing rules, or prompt-feedback shaping details.

## Non-goals

- Specify migration sequencing.
- Document current-state limitations.
- Change check policy semantics defined by shared planning policy constants.

## Core Outcome

Checks owns selection, timing, execution orchestration, and prompt-feedback rendering. The loop consumes one stable result contract.

## Public API

`run_checks(project_root, *, phase, dry_run=False, ...) -> ChecksRunResult`

Behavior:

- Always computes a full decision trace for eligible checks.
- `dry_run=True`: no command/agent execution; returns decisions only.
- `dry_run=False`: executes only planned `run` decisions.
- Returns prompt-ready failure feedback as a plain string (`prompt_feedback`) for direct prompt injection.

## Contracts

### CheckContext

Execution context passed to orchestration and strategies.

Required fields:

- `project_root`
- `phase`
- `changed_paths`

Optional fields:

- `feature_path`
- `feature_id`
- `prior_feedback`
- `run_agent_fn`
- `verbose_output`

### CheckDecision

One deterministic plan entry:

- `check_id`
- `check_type`
- `phase`
- `decision` (`run` or `skip`)
- `reason`

Reason labels must reuse shared planning policy values (for example `always_run_no_on_change`, `matched_on_change`, `no_on_change_match`, `manual`).

### CheckExecutionRecord

One side-effecting check execution result:

- `check_id`
- `check_type`
- `ok`
- `output`
- `payload` (optional structured diagnostics)
- `timing` / command invocation metadata when applicable

### ChecksRunResult

Stable loop-facing contract:

- `ok`
- `dry_run`
- `failed_check_id` (or `None`)
- `failed_payload` (or `None`)
- `decisions` (all run/skip decisions)
- `executions` (empty in dry-run)
- `output` (combined human-readable output)
- `prompt_feedback` (plain string for prompt injection, optional)

## Orchestration Model

Use a registry of check strategies keyed by check type.

Each strategy is responsible for:

- Enumerating check definitions it owns.
- Producing deterministic decisions from `CheckContext`.
- Executing its `run` decisions.
- Rendering prompt feedback from failures as plain text.

The orchestrator is responsible for:

- Building one shared `CheckContext`.
- Collecting all decisions across strategies in deterministic order.
- Executing in deterministic order when not dry-run.
- Stopping on first failure and returning that failure's `prompt_feedback`.

## Loop Boundary

The loop does not branch on check type.

Loop behavior is limited to:

- Calling `run_checks(...)`.
- Reading `ok`, `output`, and `prompt_feedback`.
- Forwarding `prompt_feedback` directly into prompt rendering.

No loop logic should map check-type payloads into prompt text.

## Extensibility Rules

Adding a new check type requires:

1. New strategy implementation.
2. Strategy registration.
3. Strategy tests for decision and execution behavior.

No loop changes are required.

## Determinism and Observability Invariants

- Decision order is stable.
- Decision reasons are stable.
- Dry-run output is side-effect free and explainable.
- Failure reporting identifies the exact failing check.
- Prompt feedback is plain text and token-efficient for retry prompts.
