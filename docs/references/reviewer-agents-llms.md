# Reviewer agents reference

This document defines the v1 reviewer-agent contract and loop policy.
Reviewer agents complement deterministic checks (`engineeringagent validate`, gates)
and never replace them.

## Purpose and scope

- Reviewer config is repository-local: `harness/reviewers.yaml`.
- Reviewer prompts are repository-local markdown files under `harness/reviewers/prompts/`.
- `engineeringagent init` does not seed reviewer files; reviewer setup is explicit via committed harness files or `engineeringagent reviewers init`.
- Reviewer execution uses shared OpenCode invocation with `agent=build`.
- Reviewer output must be strict machine-parseable JSON.

## Contract (`harness/reviewers.yaml`)

Top-level keys:

- `contract_version`: exact string `"1.0"`.
- `profiles`: map of profile name -> ordered reviewer id list.
- `reviewers`: map of reviewer id -> reviewer definition.

Required reviewer fields:

- `prompt_file`: repo-relative path under `harness/reviewers/prompts/`.
- `trigger.phase`: `iteration_end` or `feature_done` in config.
- `approval.mode`: `advisory` or `blocking` (defaults to `advisory` if omitted).

Optional reviewer fields:

- `trigger.on_change`: list of glob patterns; if omitted, reviewer is considered for all changes at its phase.
- `approval.first_feature_approval`: boolean (default `true`).
- `approval.max_retries`: integer >= 0 (default `2`).
- `approval.continue_on_exhausted`: boolean (default `true`).
- `sandbox.mode`: currently `temp_worktree_snapshot` or `clean_room_readme_cli`.
- `sandbox.assets`: optional list of repo-relative paths (files or directories) to copy into a clean-room sandbox.

Copy-pastable v1 example:

```yaml
contract_version: "1.0"
profiles:
  loop_fast:
    - code_simplifier
    - readme_process
reviewers:
code_simplifier:
    prompt_file: "harness/reviewers/prompts/code_simplifier.md"
    trigger:
      phase: "feature_done"
      on_change:
        - "src/**/*.py"
        - "tests/**/*.py"
    approval:
      mode: "advisory"
      first_feature_approval: true
      max_retries: 2
      continue_on_exhausted: true
  readme_process:
    prompt_file: "harness/reviewers/prompts/readme_process.md"
    trigger:
      phase: "feature_done"
      on_change: ["README.md"]
    sandbox:
      mode: "temp_worktree_snapshot"
    approval:
      mode: "blocking"
      first_feature_approval: true
      max_retries: 2
      continue_on_exhausted: true
```

## Default `readme_process` reviewer

Use this built-in reviewer when you want README getting-started instructions to block
feature completion until the documented process works in a clean-room run.

Copy-pastable `readme_process` entry:

```yaml
readme_process:
  prompt_file: "harness/reviewers/prompts/readme_process.md"
  trigger:
    phase: "feature_done"
    on_change: ["README.md"]
  sandbox:
    mode: "clean_room_readme_cli"
    assets:
      - "docs"
      - "opencode.json"
      - ".opencode/agents"
  approval:
    mode: "blocking"
    first_feature_approval: true
    max_retries: 2
    continue_on_exhausted: true
```

Plain-English behavior:

- Runs only for `feature_done`, and only when `README.md` changed.
- Runs inside a sandbox so the active checkout is not mutated.
- `clean_room_readme_cli` is recommended for README onboarding checks because it limits sandbox contents to the README flow and the minimal linked docs/assets.
- Reviewer instructions require reading `README.md` and attempting documented bootstrap/setup in a fresh temporary directory.
- Returns strict v1 decision JSON; non-JSON output is treated as deterministic `request_changes`.
- Uses blocking policy with retry (`max_retries: 2`) and continues with warning on exhaustion when `continue_on_exhausted` is true.
- When bootstrap fails, required actions must classify the fix surface as README instructions, init/scaffold behavior, or both.

## Default `code_simplifier` reviewer

Use this built-in reviewer when you want simplification guidance on code changes
without default hard-blocking completion behavior.

Copy-pastable `code_simplifier` entry:

```yaml
  code_simplifier:
  prompt_file: "harness/reviewers/prompts/code_simplifier.md"
  trigger:
    phase: "feature_done"
    on_change:
      - "src/**/*.py"
      - "tests/**/*.py"
  approval:
    mode: "advisory"
    first_feature_approval: true
    max_retries: 2
    continue_on_exhausted: true
```

Plain-English behavior:

- Runs at `feature_done` only when changed paths match configured code globs.
- Returns v1 decision JSON (`approve`, `warning`, or `request_changes`) from a harness-managed prompt file.
- Any returned feedback requires one follow-up implement pass before completion commit eligibility.
- Does not hard-block completion by default when advice is returned.
- Non-JSON or malformed output is treated as deterministic advisory guidance that still requires one follow-up implement pass.

## Decision envelope contract

Reviewer output must be JSON object with required fields:

- `decision`: one of `approve`, `request_changes`, `warning`.
- `summary`: non-empty string.

Optional fields:

- `required_actions`: list of strings.
- `confidence`: number in `[0, 1]`.
- `scope_notes`: string.

Any non-JSON or malformed output is treated as deterministic `request_changes` with a parser-failure summary.

Copy-pastable decision examples:

```json
{
  "decision": "approve",
  "summary": "No blocking issues found in scoped changes.",
  "required_actions": [],
  "confidence": 0.94,
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
  "confidence": 0.88,
  "scope_notes": "Focused on reviewer-runtime module changes."
}
```

```json
{
  "decision": "warning",
  "summary": "Readability can improve, but no hard blocker.",
  "required_actions": [
    "Consider simplifying nested conditional in reviewer planner"
  ],
  "confidence": 0.73,
  "scope_notes": "Advisory readability guidance only."
}
```

## Trigger and planning semantics

- Runtime executes reviewers only at `feature_done`.
- `trigger.phase: iteration_end` is treated as a compatibility alias and normalized to `feature_done`.
- Planner accepts both configured phase values and emits deterministic run/skip entries against effective `feature_done` execution.
- If `trigger.on_change` is set, the reviewer runs only when changed paths match at least one pattern.
- If changed paths cannot be resolved deterministically, planner falls back to run-all with explicit reason.

## Approval policy semantics

- `advisory`:
  - Never permanently blocks completion.
  - All reviewer decisions (`approve`, `warning`, `request_changes`) produce forwarded feedback for the next implement pass.
  - Any forwarded reviewer feedback requires exactly one follow-up implement pass before completion commit eligibility.
- `blocking`:
  - `request_changes` triggers retry behavior.
  - Retry attempts continue until approval or exhaustion (`max_retries`).
  - On exhaustion:
    - `continue_on_exhausted=true`: continue with warning and recorded non-approval state.
    - `continue_on_exhausted=false`: fail iteration.
- `first_feature_approval=true` caches first approval per feature and reviewer and reuses it until relevant scoped paths change.

## Feedback forwarding and logging semantics

- Forwarded reviewer feedback is persisted in structured run telemetry as `reviewer_feedback_present` and `reviewer_feedback_summary`.
- Per-feature loop logs persist forwarded feedback between `reviewer_feedback_forwarded_begin` and `reviewer_feedback_forwarded_end` markers.
- Feedback text is deterministic and sanitized so humans can inspect exactly what the implement pass received.

## Sandbox behavior

- `sandbox.mode: temp_worktree_snapshot` executes reviewer in an isolated temporary snapshot.
- Intended for process/document checks (for example README-process review) without mutating active worktree.

- `sandbox.mode: clean_room_readme_cli` executes the reviewer in a new empty directory populated with:
  - `README.md`
  - the configured prompt file
  - the harness-provided local CLI helper (`.engineeringagent/bin/engineeringagent`)
  - any configured `sandbox.assets`
- Intended for clean-room README onboarding checks where README links into `docs/` or other minimal artifacts.
- Clean-room sandboxes exclude `.git/`, `src/`, and `tests/` by design. They also do not copy `.opencode/node_modules`.

## End-to-end policy examples

Advisory path (`feature_done`):

1. Deterministic gates pass.
1. Advisory reviewer returns `warning`.
1. Loop records feedback and requires one follow-up implement pass.
1. Next iteration runs implement once, then reviewer phase can pass without blocking completion.

Blocking path (`feature_done`):

1. Deterministic gates pass.
1. Blocking reviewer returns `request_changes`.
1. Loop retries implement and reruns reviewer (bounded by `max_retries`).
1. If reviewer still requests changes after exhaustion:
   - continue with warning when `continue_on_exhausted=true`, or
   - fail iteration when `continue_on_exhausted=false`.

## CLI surfaces

- `engineeringagent reviewers init`: scaffold baseline reviewer config and prompts.
- `engineeringagent reviewers list`: list configured reviewer profiles.
- `engineeringagent reviewers plan --profile <name> --phase <phase>`: print deterministic plan.
- `engineeringagent reviewers run --reviewer <id> --feature-id <id> --feature-path <path>`: execute one reviewer and print decision JSON.

## Troubleshooting

- If validation fails, run `uv run python -m engineeringagent.cli validate` and fix `harness/reviewers.yaml` contract issues first.
- If a reviewer always returns `request_changes` with parser-failure summary, ensure prompt output is strict JSON only.
- If prompt file errors occur, confirm `prompt_file` path exists under `harness/reviewers/prompts/`.
- If planner unexpectedly skips a reviewer, confirm phase and `trigger.on_change` patterns against changed paths.
