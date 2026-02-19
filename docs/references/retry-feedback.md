# Retry Feedback Injection (Contracts)

This reference describes what `engineeringagent` injects into the next implement prompt
when an iteration fails and the loop retries.

## Policy

- The retry-feedback block is a single strict JSON object (a v1 envelope).
- The envelope is deterministic: validated and re-serialized (sorted keys, compact, ASCII-only).
- The envelope is bounded by construction (explicit caps in the contract); prompt injection does not truncate by slicing.
- The envelope is the only supported retry context for the implement agent; do not rely on full raw logs.

## Envelope kinds

All envelopes include:

```json
{"kind":"...","phase":"...","message":"..."}
```

### Command failures (`kind=command_failure`)

Used for gate, verification, and completion-commit command failures.

Contract highlights:

- `command`: exact failing command (single line)
- `rerun`: deterministic rerun instructions (always from repo root)
- `gate`: gate/check id when available
- `precommit`: `true` when the failure occurred under the pre-commit context

Example:

```json
{"command":"uv run ruff check src/engineeringagent harness","gate":"ruff","kind":"command_failure","message":"Command check failed. Rerun the command to see full diagnostics.","phase":"gates","precommit":true,"rerun":{"cwd":"repo_root","instructions":"Run the command exactly as shown from the repository root."}}
```

### Fitness failures (`kind=fitness_failure`)

Used when the fitness runner fails.

Contract highlights:

- `failed_rules`: failures-only list (no passing rules; no full results payload)
- Each failed rule includes `rule_id`, `remediation`, and bounded `violations`

Example:

```json
{"command":"uv run engineeringagent checks run --checks fitness --phase iteration_end","failed_rules":[{"details":null,"remediation":"...","rule_id":"architecture.docs-allowlist-policy","status":"fail","violations":["docs/references/new-doc.md:1 missing from both human_docs and agent_docs ..."]}],"gate":"fitness_validate","kind":"fitness_failure","message":"Fitness rule(s) failed. Apply remediation and rerun the command.","phase":"gates"}
```

### Reviewer feedback (`kind=reviewer_feedback`)

Used to forward structured reviewer decisions into the next implement pass.

Contract highlights:

- `decision`: parsed/validated reviewer decision payload
- Keep outputs minimal and deterministic; do not add extra fields beyond the contract.

Example:

```json
{"decision":{"decision":"request_changes","required_actions":["Extract helper ..."],"scope_notes":"Reviewed src and tests changes only.","summary":"Refactor duplicated helper."},"kind":"reviewer_feedback","message":"Reviewer requested changes. Apply required actions before completing.","phase":"reviewers","reviewer_id":"code_simplifier","reviewer_phase":"feature_done"}
```

## Notes for operators

- Full raw command output is still available in progress logs for humans, but retry feedback injection does not include pointers to those artifacts.
- When in doubt, rerun the `command` exactly as provided; the envelope is designed to provide the minimum reliable repro path.
