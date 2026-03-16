# Coding Agent Harness Tools

## Commands
- To run the `developer` cli user `uv run developer ... `

### Dependency Management
- Add dependencies: `uv add <package>`
- Add development dependencies: `uv add --group dev <package>`
- Do not manually edit `pyproject.toml`

### Running Commands
- Run commands from installed packages: `uv run <command>`

### Linting and Formatting
- Lint: `ruff check`
- Format: `ruff format`
- **Always run both after code changes**

### Type Checking
- Type check: `pyrefly check`

### Testing
- Run tests: `pytest`

# Guidelines 
1. [Testing](docs/contributor/TESTING.md) - Read this before writing tests, running test or debugging tests.