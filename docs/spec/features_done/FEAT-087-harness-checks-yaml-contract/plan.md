---
plan_id: FEAT-087
feature_id: FEAT-087
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add strict Pydantic models and validators for checks.yaml
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
- id: ST-002
  title: Implement checks.yaml planner/executor in loop runtime
  status: done
  verification:
  - uv run python -m engineeringagent.cli run --all --dry-run
  - uv run pytest -q
- id: ST-003
  title: Update init scaffolding and migrate this repo harness
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
  - uv run python -c "from pathlib import Path; import sys; present=[str(p) for p
    in (Path('harness/gates.yaml'), Path('harness/reviewers.yaml')) if p.exists()];
    sys.exit(f'legacy harness files still present={present}') if present else None;
    print('ok')"
- id: ST-004
  title: Document single-file harness contract and remove legacy docs
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
- id: ST-005
  title: Remove gate profile references from active code and docs
  status: done
  verification:
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add strict Pydantic models and validators for checks.yaml

Add contract models and semantic validation for `harness/checks.yaml`.
Enforce:
- allowed enums (`when.phase`)
- required fields per check type
- forbidden extra fields
- reviewer prompt file path constraints (repo-relative under harness/reviewers/prompts/)
- fitness selection exclusivity (scope vs rule_ids)
- reject `blocking` fields (not part of the contract)

## ST-002 Implement checks.yaml planner/executor in loop runtime

Implement:
- load + validate checks.yaml
- determine changed paths once per iteration (for on_change)
- select checks by phase
- execute command/fitness/reviewer checks
- forward failures deterministically as hook_feedback
Ensure reviewer execution aligns with FEAT-086 (approve/request_changes; no advisory followup).

Notes:
- Wire `harness/checks.yaml` command checks into loop gate phase when `run --all`.
- Run `iteration_end` checks every iteration; run `feature_done` checks only when the feature is archived for completion.
- Execute `type: reviewer` checks from `harness/checks.yaml` during `run --all` feature_done.
- Plan run/skip deterministically with `when.on_change` using one changed-path snapshot per iteration.
- Migrate runtime planning models to Pydantic (no stdlib dataclasses in src).
- Execute `type: fitness` checks from `harness/checks.yaml` during `run --all` (iteration_end + feature_done).

## ST-003 Update init scaffolding and migrate this repo harness

Update `engineeringagent init` scaffolding to write `harness/checks.yaml` by default.
Migrate this repository's harness config to checks.yaml.
Remove or disable legacy harness paths in `run`.

Notes:
- Init scaffolding now writes harness/checks.yaml (minimal empty contract).
- This repo uses harness/checks.yaml; legacy harness contract files removed.
- Tests no longer scaffold harness/gates.yaml into the repo root.

## ST-004 Document single-file harness contract and remove legacy docs

Update README/docs references to describe `harness/checks.yaml` as the sole
repo-owned verification surface. Remove references that instruct users to
edit legacy harness files.

Notes:
- Updated README and docs references to use `harness/checks.yaml` and removed `gates`/`reviewers` CLI guidance.
- Updated fitness docs and regenerated `docs/fitness-functions/rules.md`.

## ST-005 Remove gate profile references from active code and docs

Remove or update any remaining references to gate profiles / gate-profile
plumbing outside `docs/spec/**` (code + docs).

Notes:
- Removed legacy `engineeringagent gates` and `engineeringagent reviewers` CLI surfaces and deleted legacy harness contract files.
- Removed `gate_profile` plumbing from runtime models and execution paths.
- Added meta test to enforce no gate-profile references outside `docs/spec/**`.
- Replaced ripgrep (`rg`) verification with pytest-only meta checks.

Attempts: 1
