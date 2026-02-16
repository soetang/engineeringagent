# Python + uv + Ruff + Pyright Reference (LLM-Oriented)

## Purpose

- Keep Python contribution workflows deterministic with uv.
- Enforce linting and docstring quality with Ruff before commit.
- Enforce baseline static type validation with Pyright before commit.
- Keep precommit checks aligned with harness gate profiles.

## Canonical Workflow

From the repository root:

```bash
uv sync
uv run ruff check src/engineeringagent harness
uv run pyright src/engineeringagent tests harness
uv run pytest -q
uvx --from . engineeringagent gates run --profile precommit
```

## Gate and Tool Commands

- Install and sync environment: `uv sync`
- Run Ruff on package + harness code: `uv run ruff check src/engineeringagent harness`
- Run targeted docstring rules: `uv run ruff check src/engineeringagent --select D103,D417`
- Run Pyright on package, tests, and harness: `uv run pyright src/engineeringagent tests harness`
- Run tests: `uv run pytest -q`
- List configured gate profiles: `uvx --from . engineeringagent gates list`
- Run loop-fast gates: `uvx --from . engineeringagent gates run --profile loop_fast`
- Run precommit gates: `uvx --from . engineeringagent gates run --profile precommit`

## Docstring Policy

- Public functions in `src/engineeringagent` must include Google-style docstrings.
- Ruff enforces missing public-function docstrings (`D103`) and argument documentation (`D417`).
- Internal helpers (names prefixed with `_`) are not treated as exported public APIs.

## Ruff Rule ID Quick Reference

- Current repository Ruff selection in `pyproject.toml` enables `D103` and `D417`.
- If complexity guardrails are enabled for refactors, use inline comments so IDs are self-explanatory.
- Repository policy treats suppressions for non-ignorable IDs as gate failures across `src/`, `tests/`, and `harness/`.

### Common IDs used in this repository

- `D103`: undocumented public function (pydocstyle)
- `D417`: missing argument descriptions in docstring (pydocstyle)
- `C901`: complex-structure (McCabe complexity)
- `PLR0913`: too-many-arguments (pylint)
- `PLR0912`: too-many-branches (pylint)
- `PLR0915`: too-many-statements (pylint)

### Recommended commented Ruff config pattern

```toml
[tool.ruff.lint]
extend-select = [
  "D103",   # public function docstring required
  "D417",   # docstring args must be documented
  "C901",   # complex-structure (McCabe complexity)
  "PLR0912",# too-many-branches
  "PLR0915",# too-many-statements
]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pylint]
max-branches = 12
max-statements = 50
```

- Tune thresholds to this codebase; start from defaults and adjust only with clear signal/noise justification.

## PLR0913 Remediation + Naming Guidance

Use this section when a function signature grows beyond the argument budget (`PLR0913`).

### Core intent

- Keep orchestration functions focused on explicit control flow.
- Move non-control-flow details (I/O shaping, lifecycle bookkeeping, formatting, command wrappers) into intention-revealing helpers.
- Prefer self-documenting variable names that make lifecycle/state obvious.

### Preferred refactor order

1. Extract clearly named phase helpers so the main function reads as high-level steps.
2. Reduce argument fan-out with the smallest useful pattern:
   - phase extraction into helper functions
   - cohesive context object or dataclass for repeated parameter groups
   - keyword-only secondary controls for optional behavior
   - typed result object when multiple values move together
3. Rename variables for intent, not brevity, after flow and data shapes are clear.

### Variable naming examples

- Prefer names like `selected_feature_path`, `archived_feature_path`, `iteration_outcome`, `retry_feedback_by_path`.
- Avoid overloaded generic names (`path`, `result`, `data`) when lifecycle/state is knowable.

### Exception policy

- Do not add inline or file-level suppression directives for non-ignorable Ruff IDs.
- Non-ignorable seed IDs are `D103` and `PLR0913`, enforced by `architecture.no-non-ignorable-ruff-suppressions`.
- Disallowed examples include `# noqa: PLR0913`, `# noqa: D103`, `# noqa: F401,PLR0913`, and `# ruff: noqa: D103`.
- Preferred remediation for `PLR0913`: split orchestration phases and pass a structured object (`NamedTuple` or `pydantic` model) instead of many scalar arguments.

### Verification commands

```bash
uv run ruff check src/engineeringagent --select PLR0913
uv run pytest -q tests/test_loop_ralph_mode.py
uv run pytest -q tests/test_loop_opencode_integration.py
uvx --from . engineeringagent gates run --profile loop_fast
```

## Dependency and Lock Discipline

1. Update Python dependencies in `pyproject.toml`.
2. Refresh lock resolution with `uv lock`.
3. Sync local environment with `uv sync`.
4. Re-run Ruff, Pyright, and pytest checks before opening a PR.
