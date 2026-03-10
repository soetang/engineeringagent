---
plan_id: FEAT-096
feature_id: FEAT-096
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define TOML config keys, precedence, and typed accessors
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
- id: ST-002
  title: Migrate real OpenCode smoke rule enablement from env var to TOML
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run python -m engineeringagent.cli fitness catalog --format markdown --output
    docs/fitness-functions/rules.md
  - uv run pytest -q
- id: ST-003
  title: Migrate opencode integration-test gating from env var to TOML
  status: done
  verification:
  - uv run pytest -q
- id: ST-004
  title: Remove env-key reads from run-loop ANSI/TTY presentation
  status: done
  verification:
  - uv run pytest -q
- id: ST-005
  title: Add a fitness function enforcing "no env-key reads" policy
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run python -m engineeringagent.cli fitness catalog --format markdown --output
    docs/fitness-functions/rules.md
  - uv run pytest -q
- id: ST-006
  title: Add engineeringagent.toml enabling opt-in smoke + integration in this repo
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run pytest -q
- id: ST-007
  title: Apply reviewer feedback fixes
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define TOML config keys, precedence, and typed accessors

Extend configuration loading beyond docs-root to include harness/runtime toggles. Keep deterministic precedence: engineeringagent.toml then pyproject.toml[tool.engineeringagent], then defaults. Provide a small accessor surface that both harness fitness scripts and tests can use without duplicating TOML parsing logic.

## ST-002 Migrate real OpenCode smoke rule enablement from env var to TOML

Update harness/fitness-functions/check_real_opencode_hello_world_smoke.py to read the TOML key [harness.fitness].opencode-real-smoke (with pyproject fallback) instead of ENGINEERINGAGENT_REAL_OPENCODE_SMOKE.
Contract: - Disabled: PASS with deterministic "skipped (disabled in engineeringagent.toml)" summary. - Enabled + opencode missing: FAIL with remediation to install/configure opencode or disable the key. - Enabled + opencode present: run end-to-end as before.
Update associated docs/metadata to remove env-var instructions: - harness/fitness-functions/rules.yaml remediation text - docs/fitness-functions/README.md - docs/fitness-functions/rules.md (regen catalog)

## ST-003 Migrate opencode integration-test gating from env var to TOML

Update tests/loop/test_loop_opencode_integration.py to consult the TOML key [harness.pytest].opencode-integration (with pyproject fallback) instead of ENGINEERINGAGENT_OPENCODE_INTEGRATION. Keep deterministic skip messaging that points to engineeringagent.toml (not env vars).

## ST-004 Remove env-key reads from run-loop ANSI/TTY presentation

Update src/engineeringagent/loop_runtime/presentation.py so tty_supports_ansi() uses only stdout TTY detection. Remove env parameter usage and remove reads of NO_COLOR and TERM=dumb (and any other env-key reads).

## ST-005 Add a fitness function enforcing "no env-key reads" policy

Add a new harness fitness rule that fails if any Python code under src/, harness/, or tests/ performs env-key reads/branching.
Enforcement should: - FAIL on direct env reads: os.getenv(...), os.environ.get(...), os.environ['X'],
  'X' in os.environ, and common aliases (from os import environ; environ.get(...), etc.).
- Allow os.environ.copy() usage (and downstream subprocess env pass-through). - Be explicit about scope roots (src/, harness/, tests/) and exclude docs/spec/features_done/
  from any doc-text enforcement to avoid rewriting historical done-specs.

Register the rule in harness/fitness-functions/rules.yaml and regenerate the catalog.

## ST-006 Add engineeringagent.toml enabling opt-in smoke + integration in this repo

Add engineeringagent.toml at repo root with: - [harness.fitness] opencode-real-smoke = true - [harness.pytest] opencode-integration = true
This makes the opt-in behaviors active for this repository by default, while other repos remain opt-in via TOML.

## ST-007 Apply reviewer feedback fixes

Fix repo root resolution in the real OpenCode smoke fitness rule and rename a misleading test name after the shift to TTY-only ANSI decisions.
