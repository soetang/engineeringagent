# Coding Agent Harness Tools

## Commands

### Dependency Management
- Add dependencies: `uv add <package>`
- Add development dependencies: `uv add --group dev <package>`
- Do not manually edit `pyproject.toml`

### Running Commands
- Run commands from installed packages: `uv run <command>`

### Linting and Formatting
- Lint: `ruff check`
- Format: `ruff format`

### Type Checking
- Type check: `pyrefly check`

### Testing
- Run tests: `pytest`