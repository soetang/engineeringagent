# AGENTS.md


Below is a list of files describing relevant parts of the approach. You should only read the relevant ones for the task at hand. 

Devlopment in this repo follows the process used by the cli tool engineeringagent. It can be used by running `uvx engineeringagent --help`.

1. [Principles](docs/principles/harness-engineering-principles.md): High level description of the principles we follow. 
1. [README.md](README): Userfacing documentation
1. [Spec writing](docs/references/spec-writing.md): Guide for how to write specs in this repo.
1. [User workflow](docs/references/workflow.md): Description of workflow for users of engineering agent.
1. [Documentation practices](docs/references/documentation-practices.md): How to write documentation for this repo.
1. [Quality checks](docs/references/quality-check-playbook.md): How to run quality checks as a user.
1. [Reviewer Authoring](docs/references/reviewer-authoring-guide.md): How to create new reviewers

## Verification Quick Reference

- List all relevant schemas for specifications: `uvx engineeringagent schema list`  
- Get a specific schema: `uvx engineeringagent schema {schemaid}`
- Validate specs: `uvx engineeringagent validate --schema-only`
- Inspect init profile options: `uvx engineeringagent init --help`
- Run iteration-end checks: `uvx engineeringagent checks run --phase iteration_end`
- Run feature-done checks: `uvx engineeringagent checks run --phase feature_done`
