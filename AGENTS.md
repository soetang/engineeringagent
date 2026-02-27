# AGENTS.md

You can assume that this repository currently have no users. So changes are allowed to be breaking, and we prefer to improve the design and structure over maintaining exact compatbility with current functionality.

Below is a list of files describing relevant parts of the approach. You should only read the relevant ones. 

1. [Principles](docs/principles/harness-engineering-principles.md) - High level description of the principles we follow. 
1. [README.md](README) - Userfacing documentation
1. [Spec writing](docs/references/spec-writing.md) - Guide for how to write specs in this repo.
1. [Contributor commands](docs/references/contributor-commands.md) - The key commands to know when contributing to the repo.
1. [User workflow](docs/references/workflow.md) - Description of workflow for users of engineering agent.
1. [Dokumentation practices](docs/references/documentation-practices.md) - How to write documentation for this repo.
1. [Quality checks](docs/references/quality-check-playbook.md) - How to run quality checks as a user.
1. [Architecture map](docs/architecture/Architecture.md) - Entry point for target-state architecture documents.

## Verification Quick Reference

- Validate specs: `uv run engineeringagent validate --schema-only`
- Inspect init profile options: `uv run engineeringagent init --help`
- Run iteration-end checks: `uv run engineeringagent checks run --phase iteration_end`
- Run feature-done checks: `uv run engineeringagent checks run --phase feature_done`
