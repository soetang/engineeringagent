# Development practices

1. Tests the package with: `uv run pytest -q`
1. Run ruff checks `uv run ruff check`
1. Fomat code `uv run ruff format`
1. Run full harness `uv run engineeringagent checks run`
1. Validate specs `uv run engineeringagent validate --schema-only`
1. pyright `uv run pyright src/engineeringagent tests harness`
1. when running python code: `uv run python xxx`


## Docstring Policy
- Public functions in `src/engineeringagent` must include Google-style docstrings.
- Ruff enforces missing public-function docstrings (`D103`) and argument documentation (`D417`).
- Internal helpers (names prefixed with `_`) are not treated as exported public APIs.

### Any extra rules added or disabled - should be commented with what the rule is for 

Dont change settings unless explicitly asked to.

```toml
[tool.ruff.lint]
extend-select = [
  "D103",   # public function docstring required
  "D417",   # docstring args must be documented
  "C901",   # complex-structure (McCabe complexity)
  "PLR0912",# too-many-branches
  "PLR0915",# too-many-statements
]
```
