---
plan_id: FEAT-091
feature_id: FEAT-091
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Draft the temp-repo hello-world feature spec template (tight interface +
    verification)
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-002
  title: Implement harness fitness script (temp repo + init slim + run loop + assertions)
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-003
  title: Register the new rule in the fitness manifest with a 15-minute timeout budget
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run python -m engineeringagent.cli fitness catalog --format markdown --output
    docs/fitness-functions/rules.md
- id: ST-004
  title: Document how to run the opt-in smoke rule and interpret results
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Draft the temp-repo hello-world feature spec template (tight interface + verification)

Create the exact YAML payload the harness script will write into the temp repo at
`docs/spec/features/FEAT-001-hello-world-smoke.yaml`.

Requirements:
- type: feature (in temp repo)
- expected_commit_subject set deterministically (for the temp repo)
- acceptance criteria list the exact interface contract
- one subtask with verification commands (stdlib-only)
- context/constraints instruct the agent to:
  - only create `hello_world/__init__.py` and `hello_world/__main__.py`
  - mark subtask and feature status to done after verification passes
  - not modify harness/runtime timeout plumbing

## ST-002 Implement harness fitness script (temp repo + init slim + run loop + assertions)

Add `harness/fitness-functions/check_real_opencode_hello_world_smoke.py` that:
- gates execution on `ENGINEERINGAGENT_REAL_OPENCODE_SMOKE=1`
- skips (PASS) when `opencode` is missing
- creates temp repo and runs init slim
- writes the feature spec template
- commits baseline
- runs `engineeringagent run` against the feature spec
- asserts archived spec + done status + verification commands pass
- emits results via `engineeringagent.fitness.envelope.emit_result_envelope`

Keep imports within the harness allowlist (`engineeringagent.fitness.*` only).

## ST-003 Register the new rule in the fitness manifest with a 15-minute timeout budget

Add a new rule entry to `harness/fitness-functions/rules.yaml`:

- rule_id: `smoke.opencode-real-hello-world`
- adapter: command
- side_effect_free: true
- command: `uv run python harness/fitness-functions/check_real_opencode_hello_world_smoke.py`
- timeout_seconds: 900

Ensure `engineeringagent.cli fitness catalog` and `fitness run` remain deterministic.

## ST-004 Document how to run the opt-in smoke rule and interpret results

Update `docs/fitness-functions/README.md` to document:
- the rule is skipped unless enabled with `ENGINEERINGAGENT_REAL_OPENCODE_SMOKE=1`
- it uses `engineeringagent init slim` in a temp repo (no reviewers init)
- it validates the real agent loop end-to-end using a tight hello-world spec
- common failure modes (missing opencode, permission rejection, loop errors)
