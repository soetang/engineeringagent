# Configuration Model

## Purpose

Define where runtime configuration lives and what belongs in configuration rather than in feature specifications or harness catalogs.

## Canonical Location

Repository-wide configuration lives in `engineeringagent.toml` at the repository root.

For Python-first repositories, a secondary fallback may read `[tool.engineeringagent]` from `pyproject.toml` only when dedicated EngineeringAgent config files are absent.
The dedicated file remains the canonical source of truth because it also works in repositories that do not otherwise use `pyproject.toml`.

## Why TOML

- it fits Python tooling expectations
- backend, model, path, and mode settings are simple scalar configuration
- it keeps repository configuration close to `ruff`, `pyright`, and other Python-first toolchains

Recommended precedence:

1. CLI flags
2. local override file such as `engineeringagent.local.toml`
3. repository default `engineeringagent.toml`
4. optional `[tool.engineeringagent]` from `pyproject.toml` when no dedicated EngineeringAgent config file exists
5. built-in defaults

Configured roots are real overrides, not documentation aliases.
Prompt-definition and specification lookup must resolve from the effective `paths.harness_root` and `paths.specifications_root` values.

Secrets do not live in these files.
API keys and credentials should come from environment variables or an external credential store.

## What Belongs in Configuration

- implementation backend id
- implementation model id
- reviewer backend id
- reviewer model id
- integration branch name
- worktree root path
- progress root path
- harness root path
- optional remote-execution settings

## What Does Not Belong in Configuration

- feature-specific scope or acceptance
- research or plan content
- quality-profile decisions for one feature
- prompt interpolation values for one run

Those belong in specifications, plans, or runtime context objects.

## Canonical `engineeringagent.toml`

```toml
version = 1

[agents.implementation]
backend = "opencode"
model = "gpt-5.4"
prompt_definition = "implementation_default"

[agents.reviewer]
backend = "opencode"
model = "gpt-5.4-mini"

[paths]
specifications_root = "docs/specifications"
harness_root = "harness"
progress_root = ".engineeringagent/progress"
worktree_root = ".engineeringagent/worktrees"

[vcs]
integration_branch = "main"

[execution]
mode = "local_worktree"
```

## Local Override Example

```toml
[agents.implementation]
model = "gpt-5.4-large"
```

This is useful for operator-specific preferences without changing repository defaults.

## Configuration Boundaries

- configuration selects which backend, model, and implementation prompt definition to use
- prompt definitions decide how those models are prompted
- specifications decide what the agent should accomplish
- harness catalogs decide how quality is enforced

That separation keeps backend/model choices from leaking into feature specifications.

## Validation Rules

The configuration validator should reject:

- unknown backend ids
- missing model ids
- unknown prompt definition ids
- invalid repository paths
- incompatible remote-execution options

## Design Goal

Operators should be able to answer the question "what is the repository default backend and model?" by opening `engineeringagent.toml`.
If overrides are active, the CLI should surface the effective merged configuration explicitly.
