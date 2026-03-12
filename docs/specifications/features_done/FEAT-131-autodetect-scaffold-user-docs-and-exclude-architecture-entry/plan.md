---
plan_id: FEAT-131
feature_id: FEAT-131
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add deterministic template discovery for scaffolded user docs
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_scaffold.py
- id: ST-002
  title: Rewire init manifest and scaffold-policy generation to discovery output
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py
- id: ST-003
  title: Exclude architecture doc from scaffold outputs and remove scaffold AGENTS
    link
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py tests/meta/test_spec_writing_reference_doc.py
- id: ST-004
  title: Lock regressions for policy-driven exact sync and AGENTS link consistency
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_scaffold_docs_exact_sync.py
    tests/fitness/test_fitness_rules_scaffold_template_agents_doc_links.py
- id: ST-005
  title: Run final validation sweep
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add deterministic template discovery for scaffolded user docs

Implement category-driven autodetection for scaffolded user docs from `src/engineeringagent/scaffold_templates` and remove hardcoded per-file pair dependence.

## ST-002 Rewire init manifest and scaffold-policy generation to discovery output

Use discovered docs/template mappings for user docs manifest and policy (`user_docs`, `scaffold_docs`, `exact_sync`) while keeping docs-mode-separate behavior unchanged.

## ST-003 Exclude architecture doc from scaffold outputs and remove scaffold AGENTS link

Ensure `docs/architecture/Architecture.md` is excluded from scaffolded user docs and remove its link from scaffold template AGENTS docs-map section.

## ST-004 Lock regressions for policy-driven exact sync and AGENTS link consistency

Confirm existing policy-driven fitness-related checks remain valid after autodetection change.

## ST-005 Run final validation sweep

Validate end-to-end spec and init scaffold behavior after all updates.
