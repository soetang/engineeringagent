---
plan_id: FEAT-016
feature_id: FEAT-016
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add schema fields for spec type and expected commit subject metadata
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_validate_requires_feature_type
  - uv run pytest -q tests/test_validator.py::test_validate_requires_expected_commit_subject
  - uvx --from . engineeringagent validate --schema-only
- id: ST-002
  title: Backfill active feature specs with required metadata
  status: done
  verification:
  - uvx --from . engineeringagent validate
  - python3 -c "from pathlib import Path; import yaml; files=sorted(Path('docs/spec/features').glob('*.yaml'));
    assert files; [(_ for _ in ()).throw(AssertionError(str(p))) for p in files if
    'type' not in yaml.safe_load(p.read_text(encoding='utf-8'))]; print('ok')"
- id: ST-003
  title: Implement shared commit message policy validator
  status: done
  verification:
  - uv run pytest -q tests/test_commit_message_validation.py
  - uv run python harness/fitness-functions/validate_commit_messages.py --help
- id: ST-004
  title: Enforce commit message policy in local commit-msg hook
  status: done
  verification:
  - uvx --from . engineeringagent gates run --profile precommit
  - uv run pytest -q tests/test_gates.py::test_commit_msg_hook_configuration
- id: ST-005
  title: Enforce commit message policy in CI commit range checks
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py::test_commit_message_ci_gate_registered
  - python3 -c "from pathlib import Path; t=Path('.github/workflows/ci.yaml').read_text(encoding='utf-8');
    assert 'commit' in t.lower() and 'validate' in t.lower(); print('ok')"
- id: ST-006
  title: Use spec metadata for loop completion commit subject generation
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_loop_uses_expected_commit_subject
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_loop_commit_subject_fallback_uses_type_mapping
- id: ST-007
  title: Update AGENTS and spec-writing guide with mandatory checklist
  status: done
  verification:
  - python3 -c "from pathlib import Path; t=Path('AGENTS.md').read_text(encoding='utf-8').lower();
    assert 'docs/references/spec-writing.md' in t and 'must follow' in t; print('ok')"
  - 'python3 -c "from pathlib import Path; t=Path(''docs/references/spec-writing.md'').read_text(encoding=''utf-8'').lower();
    assert ''checklist'' in t and ''commit'' in t and ''type: summary'' in t; print(''ok'')"'
- id: ST-008
  title: Run targeted regression checks for validator loop and gate wiring
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_gates.py
  - uvx --from . engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add schema fields for spec type and expected commit subject metadata

Update feature schema to require top-level `type` and expected commit subject metadata fields with strict validation and no unknown values.

## ST-002 Backfill active feature specs with required metadata

Add valid `type` and expected commit subject metadata to all existing files in `docs/spec/features/*.yaml` so required-now schema enforcement passes.

## ST-003 Implement shared commit message policy validator

Add reusable validation for single commit-message files and commit ranges, using one policy source for local hook and CI enforcement.

## ST-004 Enforce commit message policy in local commit-msg hook

Wire commit subject validation into local commit-msg stage so invalid commit subjects fail before commit creation.

## ST-005 Enforce commit message policy in CI commit range checks

Add CI validation step/profile that evaluates commit subjects in push/PR scope and fails on policy violations.

## ST-006 Use spec metadata for loop completion commit subject generation

Update loop completion commit generation to use selected feature expected commit subject metadata and retain deterministic fallback mapping by feature `type`.

## ST-007 Update AGENTS and spec-writing guide with mandatory checklist

Add explicit AGENTS linkage and must-follow wording for spec-writing guide, and add a checklist section to spec-writing guide including the required commit step.

## ST-008 Run targeted regression checks for validator loop and gate wiring

Execute focused tests for validator behavior, loop commit subject generation, and gate/hook wiring to confirm full policy coverage.
