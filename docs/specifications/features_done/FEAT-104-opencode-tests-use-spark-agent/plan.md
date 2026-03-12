---
plan_id: FEAT-104
feature_id: FEAT-104
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add init flag to select agent model
  status: done
  verification:
  - uv run engineeringagent init --help
- id: ST-002
  title: Wire spark agent into real opencode smoke harness
  status: done
  verification:
  - uv run pytest -q tests/harness/test_real_opencode_smoke.py
- id: ST-003
  title: Wire spark agent into pytest opencode integration fixture
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_opencode_integration.py
- id: ST-004
  title: Remove spark template and update tests
  status: done
  verification:
  - uv run pytest -q tests/harness/test_real_opencode_smoke.py
- id: ST-005
  title: Document init option in README
  status: done
  verification:
  - uv run pytest -q
- id: ST-006
  title: De-brittle FEAT-104 tests and add harness seam
  status: done
  verification:
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add init flag to select agent model

Add `--model` to `engineeringagent init` and thread the value into the scaffold template rendering for `.opencode/agents/engineeringagent.md`.

## ST-002 Wire spark agent into real opencode smoke harness

Update `harness/fitness_functions/check_real_opencode_hello_world_smoke.py` to call `engineeringagent init` with `--model openai/gpt-5.3-codex-spark` and remove any spark-template override logic.

## ST-003 Wire spark agent into pytest opencode integration fixture

Update `tests/loop/test_loop_opencode_integration.py` to avoid creating the legacy repo-root OpenCode config file and to ensure `.opencode/agents/engineeringagent.md` is spark-pinned for the temp repo.

## ST-004 Remove spark template and update tests

Delete `harness/fitness_functions/opencode.agent.engineeringagent.spark.md.tmpl` and update/remove any unit tests that referenced helper code for copying that template.

## ST-005 Document init option in README

Update `README.md` to document `--model`, clarify that the repo does not use the legacy repo-root OpenCode config file, and show how to scaffold spark for fast test/CI loops.

## ST-006 De-brittle FEAT-104 tests and add harness seam

Address reviewer feedback by making assertions behavior-focused (avoid source inspection and full-file equality checks) while still verifying `init --model` scaffolding and spark pinning.
