# Reviewer agents reference

This document defines the v1 reviewer-agent contract and loop policy.
Reviewer agents complement deterministic repo-owned checks declared in
`harness/checks.yaml` and never replace them.

## Purpose and scope

- Reviewer checks are repository-local: `harness/checks.yaml` (`type: reviewer`).
- Reviewer prompts are repository-local markdown files under `harness/reviewers/prompts/`.
- Reviewer prompt setup is explicit via committed harness files.
- Reviewer execution uses shared OpenCode invocation with `agent=engineeringagent`.
- Reviewer output must be strict machine-parseable JSON.

## Contract (reviewer checks in `harness/checks.yaml`)

Reviewer checks live under the shared checks contract and follow the `type: reviewer`
shape.

Required reviewer fields:

- `prompt_file`: repo-relative path under `harness/reviewers/prompts/`.

Optional reviewer fields:

- `when.phase`: `feature_done` (or `manual`).
- `when.on_change`: list of glob patterns; if omitted, reviewer is considered for all changes at its phase.
- `approval.first_feature_approval`: boolean (default `true`).
- `sandbox.mode`: `temp_worktree_snapshot` or `empty_folder`.
- `sandbox.assets`: optional list of repo-relative paths (files or directories) to copy into an `empty_folder` sandbox.
- `feedback_context`: optional string forwarded verbatim into the next implement pass feedback when a follow-up implement pass is required.

Copy-pastable v1 example:

```yaml
contract_version: "1.0"
defaults:
  when:
    phase: iteration_end

checks:
  code_simplifier:
    type: reviewer
    prompt_file: "harness/reviewers/prompts/code_simplifier.md"
    when:
      phase: feature_done
      on_change:
        - "src/**/*.py"
        - "tests/**/*.py"
    approval:
      first_feature_approval: true
```

## Default `code_simplifier` reviewer

Use this reviewer when you want simplification guidance on code changes at `feature_done`.

Copy-pastable `code_simplifier` entry:

```yaml
code_simplifier:
  prompt_file: "harness/reviewers/prompts/code_simplifier.md"
  when:
    phase: feature_done
    on_change:
      - "src/**/*.py"
      - "tests/**/*.py"
  approval:
    first_feature_approval: true
```

Plain-English behavior:

- Runs at `feature_done` only when changed paths match configured code globs.
- Returns v1 decision JSON (`approve` or `request_changes`) from a harness-managed prompt file.
- At `feature_done`, any decision other than `approve` blocks completion and continues the same feature with forwarded feedback.
- Non-JSON or malformed output is treated as deterministic `request_changes` with a parser-failure summary.

## Decision envelope contract

- The `$responseformat` placeholder expands to a contract that includes the reviewer decision envelope JSON Schema.
- Reviewer execution prefers OpenCode JSON event output via `opencode run --format json`.
- If the decision payload fails JSON parsing or schema validation, the runner retries up to 2 times in the same OpenCode session.

Reviewer output must be JSON object with required fields:

- `decision`: one of `approve`, `request_changes`.
- `summary`: non-empty string.

Optional fields:

- `required_actions`: list of strings.
- `scope_notes`: string.

Any non-JSON or malformed output is treated as deterministic `request_changes` with a parser-failure summary.

Copy-pastable decision examples:

```json
{
  "decision": "approve",
  "summary": "No blocking issues found in scoped changes.",
  "required_actions": [],
  "scope_notes": "Reviewed src and tests changes only."
}
```

```json
{
  "decision": "request_changes",
  "summary": "Refactor duplicated parsing helper before completion.",
  "required_actions": [
    "Extract shared parser helper in src/engineeringagent/reviewers.py",
    "Add regression test for malformed decision payload"
  ],
  "scope_notes": "Focused on reviewer-runtime module changes."
}
```

## Trigger and planning semantics

- Runtime executes reviewers only at `feature_done`.
- `trigger.phase: iteration_end` is treated as a compatibility alias and normalized to `feature_done`.
- Planner accepts both configured phase values and emits deterministic run/skip entries against effective `feature_done` execution.
- If `trigger.on_change` is set, the reviewer runs only when changed paths match at least one pattern.
- If changed paths cannot be resolved deterministically, planner falls back to run-all with explicit reason.

## Approval caching semantics

- `approval.first_feature_approval=true` caches first approval per feature and reviewer and reuses it until relevant scoped paths change.

## Feedback forwarding and logging semantics

- Forwarded reviewer feedback is persisted in structured run telemetry as `reviewer_feedback_present` and `reviewer_feedback_summary`.
- Per-feature loop logs persist forwarded feedback between `reviewer_feedback_forwarded_begin` and `reviewer_feedback_forwarded_end` markers.
- Feedback text is deterministic and sanitized so humans can inspect exactly what the implement pass received.
- If `feedback_context` is configured for a reviewer, it is included verbatim in the forwarded feedback text so the implement pass can interpret scoped or sandboxed reviewer feedback correctly.

## Sandbox behavior

- `sandbox.mode: temp_worktree_snapshot` executes reviewer in an isolated temporary snapshot.
- Intended for process/document checks (for example README-process review) without mutating active worktree.

- `sandbox.mode: empty_folder` executes the reviewer in a new empty directory populated with:
  - the configured prompt file
  - any configured `sandbox.assets`
- `empty_folder` does not implicitly inject assets. If you want `README.md`, `docs/`, or `.opencode/agents`, list them in `sandbox.assets`.
- `sandbox.assets` is only supported for `empty_folder`.

## End-to-end policy examples

Feature completion path (`feature_done`):

1. Deterministic repo-owned checks pass.
1. Reviewer returns `approve` -> completion may proceed.
1. Reviewer returns `request_changes` -> completion is blocked and the loop continues the same feature with forwarded feedback.

## Execution surface

- Reviewer checks run via `engineeringagent run --all` based on `harness/checks.yaml`.

## Troubleshooting

- If validation fails, run `uv run engineeringagent validate` and fix `harness/checks.yaml` contract issues first.
- If a reviewer always returns `request_changes` with parser-failure summary, ensure prompt output is strict JSON only.
- If prompt file errors occur, confirm `prompt_file` path exists under `harness/reviewers/prompts/`.
- If planner unexpectedly skips a reviewer, confirm phase and `when.on_change` patterns against changed paths.
