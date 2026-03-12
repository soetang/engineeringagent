---
plan_id: FEAT-073
feature_id: FEAT-073
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add pack arg and TTY-only prompt with deterministic default
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py
- id: ST-002
  title: Wire standard pack demo-fail into precommit gate plan
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py
- id: ST-003
  title: Stop --skip-implement from looping when gates pass
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py -k skip_implement_exits_after_one_passing_iteration
- id: ST-004
  title: README quickstart coherence for init + run (dirty worktree, mutations)
  status: done
  verification:
  - uv run pytest -q tests/test_repo_readme_process_reviewer_activation.py
- id: ST-005
  title: Align uv-llms docs with --skip-implement behavior
  status: done
  verification:
  - uv run pytest -q tests/test_reviewer_reference_docs.py
- id: ST-006
  title: Improve run diagnostics when default OpenCode implement cannot proceed
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py
- id: ST-007
  title: Fix progress log path locality violation in OpenCode precheck hint
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-008
  title: Deduplicate spec validation gate scaffold
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py
- id: ST-009
  title: Format README for mdformat gate
  status: done
  verification:
  - uv run mdformat --check README.md AGENTS.md docs/references/docs-architecture.md
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add pack arg and TTY-only prompt with deterministic default

Extend the Typer `init` command to accept `slim|standard` as an optional positional.
Implement TTY detection and prompt only when pack is omitted and TTY is true.
Add unit tests covering TTY vs non-TTY behavior and "no prompt when pack provided".

## ST-002 Wire standard pack demo-fail into precommit gate plan

Add standard-pack scaffold differences that cause pre-commit to run a demo
fitness rule that always fails (without making the default `fitness run` unusable).
Add tests verifying slim vs standard outputs differ as intended.

## ST-003 Stop --skip-implement from looping when gates pass

`engineeringagent run --skip-implement` is documented as gates-only mode, but it can loop/retry the same passing iteration until hitting --max-iterations.

Ensure gates-only runs execute a single iteration and exit (0 on pass, 1 on fail).

## ST-004 README quickstart coherence for init + run (dirty worktree, mutations)

Update README.md to cover: clean-worktree requirement (commit or --allow-dirty) after init/spec edits, that non-dry run mutates feature YAML + writes progress logs, and document `engineeringagent init [slim|standard]` pack behavior (including TTY prompt + how to avoid it).

## ST-005 Align uv-llms docs with --skip-implement behavior

Update docs/references/uv-workflow.md examples and guidance to match gates-only runtime behavior (no silent looping/retries when gates pass).

## ST-006 Improve run diagnostics when default OpenCode implement cannot proceed

Non-dry `engineeringagent run` can appear to hang when default OpenCode implement mode cannot run. Add clear terminal output pointing to --implement-command/--skip-implement and where logs are written.

## ST-007 Fix progress log path locality violation in OpenCode precheck hint

Remove progress artifact path literals from loop runtime diagnostics by constructing progress references via engineeringagent.progress_paths.

## ST-008 Deduplicate spec validation gate scaffold

Refactor init scaffold gate construction so the spec_validate gate shape comes from a single helper, reducing drift risk between slim and standard packs.

## ST-009 Format README for mdformat gate

The precommit gate profile includes mdformat validation for README.md.
Ensure README.md is mdformat-compliant so `engineeringagent-precommit` can pass.

Notes:
- Fixes reported failure: "Error: File README.md is not formatted."
