---
plan_id: FEAT-080
feature_id: FEAT-080
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Move tests into topic folders under tests/
  status: done
  verification:
  - uv run pytest -q
- id: ST-002
  title: Fix tests that compute repo root via Path(__file__).parents
  status: done
  verification:
  - uv run pytest -q
- id: ST-003
  title: Update ruff_validate gate to lint harness/
  status: done
  verification:
  - uv run pytest -q tests/harness/test_gates.py
  - uv run python -m engineeringagent.cli gates run --profile precommit
- id: ST-004
  title: Configure Ruff so harness fitness-function scripts pass lint
  status: done
  verification:
  - uv run ruff check harness
- id: ST-005
  title: Update docs referencing Ruff command and run full regression
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run ruff check src/engineeringagent harness
  - uv run pyright src/engineeringagent tests harness
  - uv run pytest -q
  - uv run python -m engineeringagent.cli gates run --profile precommit
- id: ST-006
  title: Update README troubleshooting for init hooks and OpenCode retries
  status: done
  verification:
  - uv run pytest -q tests/reviewers/test_repo_readme_process_reviewer_activation.py
- id: ST-007
  title: Ensure quality-check playbook uses source-first CLI invocations
  status: done
  verification:
  - uv run pytest -q tests/meta/test_quality_check_playbook_source_first_cli.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Move tests into topic folders under tests/

Create topic folders and move each test module according to the move map
in this spec. Do not move `tests/conftest.py` or `tests/fixtures/`.
Progress (2026-02-16): moved CLI-related tests into `tests/cli/`, moved loop-related tests into `tests/loop/`, added layout assertion tests under `tests/meta/`, moved VCS-related tests into `tests/vcs/`, and moved harness script relocation tests into `tests/harness/`.
Progress (2026-02-16): moved opencode-related tests into `tests/opencode/` and added a layout assertion test under `tests/meta/`.
Progress (2026-02-16): moved reviewer-related tests into `tests/reviewers/` and added a layout assertion test under `tests/meta/`.
Progress (2026-02-16): moved remaining root tests into `tests/fitness/`, `tests/meta/`, and `tests/harness/`; added layout assertion tests for `fitness` and `meta` topics; `tests/` root now only contains `conftest.py`, `fixtures/`, and topic folders.
Progress (2026-02-16): removed a stale duplicate `tests/test_loop_opencode_integration.py` left behind after the move; `tests/` root now contains only `conftest.py`, `fixtures/`, and topic folders.

## ST-002 Fix tests that compute repo root via Path(__file__).parents

Update tests that use `Path(__file__).resolve().parents[1]` so they still
resolve the repository root after being moved one directory deeper.
Prefer a robust approach that remains correct if additional nesting is
introduced later (e.g. pytest rootpath fixture or a centralized helper).
Progress (2026-02-16): updated `tests/loop/test_loop_contracts.py` to resolve `harness/fitness-functions/*` scripts via `pytestconfig.rootpath` instead of `Path(__file__).resolve().parents[1]`.
Progress (2026-02-16): updated `tests/vcs/test_commit_message_validation.py` to resolve the repo root via `pytestconfig.rootpath` instead of `Path(__file__).resolve().parents[1]`.
Progress (2026-02-16): added a shared `repo_root` fixture in `tests/conftest.py`, updated remaining tests to use `repo_root`/`pytestconfig.rootpath` (including harness fitness-function script path resolution), and added a meta test to prevent reintroducing brittle `parents[1]` repo-root computation.

## ST-003 Update ruff_validate gate to lint harness/

Align gate behavior with `on_change` by updating both this repo's
`harness/gates.yaml` and `src/engineeringagent/gates.py` default config so
`ruff_validate` runs Ruff on `src/engineeringagent` and `harness/`.
Update any tests that assert the exact gate runner string.

## ST-004 Configure Ruff so harness fitness-function scripts pass lint

`uv run ruff check harness` currently fails due to docstring and
complexity rules applied to harness scripts. Update `pyproject.toml`
Ruff settings to ignore these rules for `harness/fitness-functions/*.py`
(and only for that path), while keeping baseline linting enabled.
Progress (2026-02-16): restored `tool.ruff.lint.extend-select` so the docstring/complexity rules are actually enabled globally, making the `per-file-ignores` exemption for `harness/fitness-functions/*.py` meaningful.

## ST-005 Update docs referencing Ruff command and run full regression

Update references in docs that currently state `uv run ruff check
src/engineeringagent` to match the new canonical lint command.
Run the full precommit profile gates and the full pytest suite.
Progress (2026-02-16): updated canonical Ruff command references to include `harness` and added a meta test to prevent regressions.

## ST-006 Update README troubleshooting for init hooks and OpenCode retries

Reviewer feedback: document that `engineeringagent init` skips pre-commit
hook installation when `.git/` does not exist (and that `git init` should be run
before `engineeringagent init` when hooks are expected).
Also document that `engineeringagent run` retries up to `--max-iterations`
(default 50), and that `--max-iterations 1` helps fail fast when debugging
OpenCode timeouts.
Progress (2026-02-16): updated README so the first non-dry `engineeringagent run` example uses a longer OpenCode timeout by default (to avoid clean-room `opencode_timeout` failures), documented that `init` can also skip hook installation when `pre-commit` is not available on PATH, and aligned the readme_process reviewer prompt outline with the README's validate/gates steps.
Progress (2026-02-16): tightened the README Quickstart indentation rules (Quickstart content indented <= 3 spaces; no 4-space indentation outside code fences) so notes render as list paragraphs (not indented code blocks) in common Markdown renderers. Updated `README.md` to match and strengthened the meta test to prevent regressions.
Progress (2026-02-16): enabled the `readme_process` reviewer in `harness/reviewers.yaml` and updated `README.md` to document init hook-installation skip cases and OpenCode retry/max-iterations guidance.
Progress (2026-02-16): updated `README.md` to include a source-run callout using `.engineeringagent/bin/engineeringagent`, clarified first non-dry-run cleanliness expectations (untracked `init` output can be swept into the first loop commit), clarified that the loop may auto-archive `status: done` specs into `docs/spec/features_done/`, and clarified that `harness/reviewers.yaml` is created by `engineeringagent reviewers init`. Added a committed `.engineeringagent/bin/engineeringagent` helper script for contributors.

## ST-007 Ensure quality-check playbook uses source-first CLI invocations

Update `docs/principles/quality-check-playbook.md` to use source-first
`uv run python -m engineeringagent.cli ...` commands (instead of relying on the
console-script entrypoint).
