---
plan_id: FEAT-069
feature_id: FEAT-069
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add scaffold template files for .opencode agent policy and gitignore
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py::test_init_renders_scaffold_from_template_files
- id: ST-002
  title: Extend init scaffold manifest to write .opencode policy outputs
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py
- id: ST-003
  title: Remove opencode.json requirement from hints, docs, and readme_process sandbox
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_sandbox.py tests/test_repo_readme_process_reviewer_activation.py
  - uv run python -m engineeringagent.cli validate
- id: ST-004
  title: Tighten docs examples and simplify permission-probe helpers
  status: done
  verification:
  - uv run pytest -q tests/test_opencode_permissions.py tests/test_docs_reviewer_agents_reference.py
  - uv run python -m engineeringagent.cli validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add scaffold template files for .opencode agent policy and gitignore

Add file-based templates under `src/engineeringagent/scaffold_templates/` for: `.opencode/agents/engineeringagent.md` and `.opencode/.gitignore`.

## ST-002 Extend init scaffold manifest to write .opencode policy outputs

Update `build_baseline_scaffold_manifest` so init writes the new `.opencode/*` files for all scaffold profiles, respecting existing `--force` behavior.

## ST-003 Remove opencode.json requirement from hints, docs, and readme_process sandbox

Update remediation messaging, docs references, and readme_process reviewer prompt/config to stop requiring `opencode.json`, and adjust tests asserting sandbox asset presence accordingly.

## ST-004 Tighten docs examples and simplify permission-probe helpers

Follow-up polish from reviewer feedback: make the copy-pastable YAML examples
    in docs valid and simplify OpenCode permission probe parsing logic without changing
    behavior.
