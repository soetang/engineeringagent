---
plan_id: FEAT-105
feature_id: FEAT-105
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-000
  title: Add `engineeringagent checks catalog` and checks API wrapper
  status: done
  verification:
  - uv run engineeringagent checks catalog --format markdown
  - uv run engineeringagent checks catalog --format json
  - uv run pytest -q
- id: ST-010
  title: Remove `engineeringagent fitness *` CLI group (no shims)
  status: done
  verification:
  - uv run engineeringagent --help
  - uv run engineeringagent checks --help
  - uv run pytest -q
- id: ST-011
  title: Migrate docs/tests/remediation strings to `engineeringagent checks catalog`
  status: done
  verification:
  - uv run pytest -q
- id: ST-001
  title: Define strict checks public surface and enforcement rules
  status: done
  verification:
  - uv run engineeringagent checks run --checks fitness
  - uv run pytest -q
- id: ST-002
  title: Add deterministic failed_payload objects to run_checks
  status: done
  verification:
  - uv run pytest -q
- id: ST-003
  title: Refactor loop runtime phases to depend only on run_checks outputs
  status: done
  verification:
  - uv run pytest -q
- id: ST-004
  title: Relocate retry-feedback envelope helpers to prompts package
  status: done
  verification:
  - uv run pytest -q
- id: ST-005
  title: Migrate CLI validate to run_checks validate group
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run pytest -q
- id: ST-006
  title: Move OpenCode permission probe under opencode submodule (no shims)
  status: done
  verification:
  - uv run pytest -q
- id: ST-007
  title: Move on-change matcher under checks package (no shims)
  status: done
  verification:
  - uv run pytest -q
- id: ST-008
  title: End-to-end verification and gate profile pass
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run engineeringagent checks run --phase iteration_end
  - uv run pytest -q
- id: ST-009
  title: Make start_agent_fn return structured OpenCode results
  status: done
  verification:
  - uv run pytest -q
- id: ST-012
  title: Address reviewer warnings (boundary-tightening refactors)
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run pytest -q
- id: ST-013
  title: Remove brittle markdown content assertions in catalog tests
  status: done
  verification:
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-000 Add `engineeringagent checks catalog` and checks API wrapper

Introduce `engineeringagent checks catalog` as the CLI interface for generating the
fitness-rule catalog.

Add a single supported orchestration function to the strict checks surface:
- `engineeringagent.checks.render_fitness_catalog(project_root, *, manifest_path=None, format="markdown") -> str`

CLI contract (normative):
- When `--output` is omitted: print rendered catalog to stdout.
- When `--output` is provided: write rendered catalog plus a trailing newline and print
  `checks catalog written: <path>` to stdout.
- Supported formats: `--format markdown|json`.

Determinism requirements (normative):
- Stable rule ordering (sorted by rule_id).
- JSON output uses sorted keys and stable formatting (indent=2, sort_keys=True).
- Markdown output is stable and does not embed absolute paths.

## ST-010 Remove `engineeringagent fitness *` CLI group (no shims)

Remove `engineeringagent fitness list|run|catalog` Typer routes and handlers.
Remove `src/engineeringagent/cli.py` imports of checks fitness internals.

## ST-011 Migrate docs/tests/remediation strings to `engineeringagent checks catalog`

Update all references to the removed `engineeringagent fitness catalog` command.
Required updates include: - `docs/fitness-functions/README.md`: replace the catalog regen command with `uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md`. - CLI tests that assert `fitness ... --help` routes: replace with `checks catalog --help` assertions. - Any tests/strings that embed `python -m engineeringagent.cli fitness run ...`: replace with `uv run engineeringagent checks run --checks fitness --phase iteration_end`.

## ST-001 Define strict checks public surface and enforcement rules

Slim `engineeringagent.checks` exports for non-checks production code to the supported surface and update `check_checks_import_surface.py` to enforce it. Ensure rule enforcement is based on explicit allowed names.

## ST-002 Add deterministic failed_payload objects to run_checks

Extend `ChecksRunResult.failed_payload` so each failing group returns a deterministic minimal object sufficient for loop retry-feedback construction. Add/adjust tests to cover payload stability and required fields.

## ST-003 Refactor loop runtime phases to depend only on run_checks outputs

Update `src/engineeringagent/loop_runtime/phases.py` to stop importing checks internals and to build retry feedback from `ChecksRunResult.failed_payload`. Preserve existing loop result/status fields.

## ST-004 Relocate retry-feedback envelope helpers to prompts package

Move retry-feedback parsing/serialization and normalization into `src/engineeringagent/prompts/retry_feedback.py` and update `prompts/renderer.py` and loop callers accordingly. Preserve FEAT-092 envelope contract.

## ST-005 Migrate CLI validate to run_checks validate group

Replace any direct validate runner import usage with `run_checks(..., checks=["validate"])` so CLI depends only on the strict checks surface.

## ST-006 Move OpenCode permission probe under opencode submodule (no shims)

Move `opencode_permissions` implementation into `src/engineeringagent/opencode/permissions.py` and update all callsites/tests/harness scripts to the new import path.

## ST-007 Move on-change matcher under checks package (no shims)

Move matcher into `src/engineeringagent/checks/on_change_matcher.py` and update checks submodules and tests accordingly.

## ST-008 End-to-end verification and gate profile pass

Run repository validation and checks to ensure no import-direction regressions, rule enforcement is active, and loop execution remains stable.

## ST-009 Make start_agent_fn return structured OpenCode results

Introduce an opencode-owned structured result type returned by `engineeringagent.opencode.client.start_agent` (and required for injected `start_agent_fn` callsites). The structured result must include stdout/stderr for logging plus explicit fields for `session_id` and the final text payload when OpenCode is invoked with `--format json`.
Update reviewer execution to rely on those structured fields instead of parsing stdout inside checks.

## ST-012 Address reviewer warnings (boundary-tightening refactors)

Apply small behavior-preserving refactors suggested by the code_simplifier reviewer to reduce repetition and keep the new checks failure payload plumbing easy to maintain.

## ST-013 Remove brittle markdown content assertions in catalog tests

Replace markdown-text assertions with JSON-contract assertions for fitness catalog generation.
Keep markdown tests limited to file writing and trailing newline.
