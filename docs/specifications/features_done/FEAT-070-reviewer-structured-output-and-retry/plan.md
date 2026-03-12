---
plan_id: FEAT-070
feature_id: FEAT-070
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define reviewer decision envelope model and JSON Schema contract injection
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_parse.py tests/test_reviewers_runtime.py
- id: ST-002
  title: Add JSON event-stream extraction for OpenCode reviewer runs
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py
- id: ST-003
  title: Implement same-session reflection retries for parse/schema failures
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py tests/test_loop_reviewers.py
- id: ST-004
  title: Update docs to describe schema-validated reviewer outputs and retries
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-005
  title: Run readme_process reviewer and apply any required README fixes
  status: done
  verification:
  - uv run python -m engineeringagent.cli reviewers run --reviewer readme_process
    --feature-id FEAT-070 \ --feature-path docs/spec/features_done/FEAT-070-reviewer-structured-output-and-retry.yaml
- id: ST-006
  title: Expand readme_process trigger paths to cover onboarding docs and code changes
  status: done
  verification:
  - uv run pytest -q tests/test_repo_readme_process_reviewer_activation.py tests/test_loop_reviewers.py
- id: ST-007
  title: Tighten parse-failure guidance and de-duplicate stdio parsing
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_parse.py
  - uv run pytest -q tests/test_reviewers_runtime.py
- id: ST-008
  title: Move spec to features_done and restore readable YAML formatting
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define reviewer decision envelope model and JSON Schema contract injection

Add a Pydantic model for the reviewer decision envelope and replace the current prose-only
$responseformat injection with a contract that includes the model's JSON Schema and a
minimal example object.

## ST-002 Add JSON event-stream extraction for OpenCode reviewer runs

Teach the reviewer runner to call `opencode run --format json` and extract: (a) sessionID
and (b) the assistant's final text output from JSON events. Ignore non-text events.

## ST-003 Implement same-session reflection retries for parse/schema failures

When the extracted assistant text does not validate as a reviewer decision envelope, send
a corrective follow-up prompt in the same session using `opencode run --session <id> \
--format json`. Retry up to 2 times, then fall back to the existing deterministic
parser-failure decision.

## ST-004 Update docs to describe schema-validated reviewer outputs and retries

Update reviewer reference/authoring docs to describe that $responseformat expands to a JSON
schema-backed contract and that the harness performs bounded retries on schema violations.

## ST-005 Run readme_process reviewer and apply any required README fixes

Force-run the readme_process reviewer via the CLI to exercise the new structured-output
and retry behavior. If the reviewer requests changes to README.md (or linked docs), apply
those changes as part of this feature so the reviewer gets a realistic end-to-end pass.

## ST-006 Expand readme_process trigger paths to cover onboarding docs and code changes

Update `harness/reviewers.yaml` so readme_process triggers not only on README.md, but also
on onboarding-relevant docs (`docs/references/**/*.md`, `docs/principles/**/*.md`) and
onboarding surface code paths (CLI/init/validator/gates/loop runtime). Do not trigger on
AGENTS.md.

## ST-007 Tighten parse-failure guidance and de-duplicate stdio parsing

Address reviewer follow-up feedback:
- De-duplicate legacy stdout/stderr parsing fallback so the control flow in the reviewer
  runner is easier to scan.
- Ensure parse-failure required_actions points reviewers at the schema-based contract (JSON
  Schema) rather than a vague prose envelope.
- Rename the strictness regression test to match what it now asserts.

## ST-008 Move spec to features_done and restore readable YAML formatting

Move the completed spec to docs/spec/features_done/ with readable block scalars (avoid
collapsed single-line scalars) so the archived record remains reviewable.
