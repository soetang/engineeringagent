---
plan_id: FEAT-164
feature_id: FEAT-164
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define minimal README section structure and content budget
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
- id: ST-002
  title: Rewrite onboarding around spec-to-implement without approach routing
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_markdown_references.py
  - uv run pytest -q tests/fitness/test_fitness_rules_markdown_locality.py
- id: ST-003
  title: Add AGENTS fallback snippet and spec-authoring guidance
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_markdown_references.py
- id: ST-005
  title: Final README polish and invariant checks
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
  - uv run pytest -q tests/fitness/test_fitness_rules_markdown_references.py
  - uv run pytest -q tests/fitness/test_fitness_rules_markdown_locality.py
- id: ST-006
  title: Add concise agent allowlist recommendation
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_markdown_references.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define minimal README section structure and content budget

Propose final section order and strict brevity targets so README remains intentionally
minimal while still complete for first-run onboarding.

## ST-002 Rewrite onboarding around spec-to-implement without approach routing

Replace long-form startup instructions with concise flow guidance while avoiding
user-facing redirects to `engineeringagent approach`.

## ST-003 Add AGENTS fallback snippet and spec-authoring guidance

Keep only the required contributor policy statements (no PRs, agent-written code,
issue-driven specs) and remove operational command details.

## ST-005 Final README polish and invariant checks

Ensure readability, stable links/path references, and compatibility with existing
markdown locality/reference fitness rules.

## ST-006 Add concise agent allowlist recommendation

Add a short README note recommending allowlisting `engineeringagent approach` and
`engineeringagent schema *` for agents in restrictive command-permission setups.
