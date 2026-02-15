# Engineering Agent

Engineering agent - is agent that helps you implement code changes directly from specs. The intention is to allow the agent to run independently for long time. To achieve this a harness is needed though. This happens through validators: linters, tests, codecoverage requirements, fitness functions, and other agents that review the changes. The repos - comes with a structure for how to do this.

You will need to implement the harnesses specific to your repo yourself. You can use the same flow to create harnesses - if you are just starting our i recommend the first few specs and implementations you write should be

The primary flow is rather simple: `application spec -> run loop`. You can of cause craft feature specs by hand - but we suggest that you use the agent for this.

## Command styles

- Package usage (PyPI, no clone): `uvx engineeringagent <command>`
- Package usage (version pinned): `uvx engineeringagent@<version> <command>`

## Quickstart from PyPI (no clone)

1. If you are starting in a fresh repository, scaffold the baseline harness first.

   ```bash
   uvx engineeringagent init 
   ```

   Warning: `init` is experimental scaffolding. Inspect generated files,
   run `uvx engineeringagent validate`, and review the git diff before committing.

   We recommend u do this in a seperat branch or toy project the first time you try out the process.

1. Create or pick one feature spec in `docs/spec/features/`.

1. Validate the setup and run gates.

   ```bash
   uvx engineeringagent validate
   uvx engineeringagent gates run --profile loop_fast
   ```

1. Do a safe dry run first.

   ```bash
   uvx engineeringagent run docs/spec/features/FEAT-001-example.yaml --dry-run
   ```

Run for real by removing `--dry-run`.

## Bootstrapping a new repository with `init`

If you are starting in a fresh repository, you can scaffold a baseline harness with:

```bash
uvx engineeringagent init
```

`init` defaults to the language-agnostic `core` scaffold profile.
Use `python_uv` only when you intentionally want Python/uv-oriented bootstrap defaults:

```bash
uvx engineeringagent init --scaffold-profile python_uv
```

`init` creates a starter structure for docs/specs/gates and handles existing `docs/` or
`AGENTS.md` through explicit conflict choices.

Warning: treat `init` as experimental scaffolding.
Always inspect generated files, run `uvx engineeringagent validate`, and review
the git diff before committing anything produced by `init`.

## What this gives you

- Deterministic progress: one spec file at a time.
- Human control: you set priorities and scope; agents execute loops.
- Built-in quality checks: validation, gates, and commit hooks.

## Run output tips

- Default output is concise; full implement/gate output stays in `progress/run-feature-<FEATURE_ID>.txt`.
- Use `--verbose-output` if you want full implement/gate output in the terminal.

## OpenCode default agent contract

- Default loop execution uses the `engineeringagent` OpenCode agent; this contract does not fall back to `build`.
- Keep `opencode.json` configured with `default_agent: "engineeringagent"` and an `agent.engineeringagent` entry using `model: "openai/gpt-5.3-codex"` plus `variant: "high"`.
- Keep permission policy remediation anchored to `.opencode/agents/engineeringagent.md` with equivalent allow-all posture for this repository.
- Existing `.opencode/agents/build.md` and `agent.build` entries can remain for other workflows and should not be overwritten by this loop contract.

## Human docs vs agent docs

- `README.md`: first-run, for you the developer.
- [Harness Engineering Principles](docs/principles/harness-engineering-principles.md): deeper for you the developer.
- `AGENTS.md` and `docs/references/*-llms.md`: agent execution rules and deterministic procedures.

## Reviewer agents (optional)

- Reviewer agents are a harness-managed complement to deterministic gates, configured in `harness/reviewers.yaml`.
- `engineeringagent init` does not scaffold reviewer config or prompts; keep reviewer policy repository-owned through committed harness files.
- Use `uvx engineeringagent reviewers init` to scaffold a baseline config and prompt files under `harness/reviewers/prompts/`.
- Use `uvx engineeringagent reviewers list|plan|run` to inspect and test reviewer behavior.
- For setup and migration guidance, see [Reviewer authoring guide](docs/principles/reviewer-authoring-guide.md).
- For full contract, policy semantics, decision-envelope examples, and troubleshooting, see [Reviewer agents reference](docs/references/reviewer-agents-llms.md).

## Core files to know

- `docs/spec/features/`: active feature specs (`backlog`, `in_progress`, `blocked`)
- `docs/spec/features_done/`: archived completed specs (`done`)
- `harness/gates.yaml`: gate and profile definitions
- `progress/runs.jsonl`: append-only loop execution history

## Contributing

- Pull requests are not accepted for this repository.
- Code changes are implemented through the project agent workflow.
- If you want a new capability, open a GitHub issue with the problem, desired outcome, and constraints.
- Feature requests from issues may be promoted into a formal spec under `docs/spec/features/`.

## Go deeper

- [CLI workflow details](docs/references/uv-llms.md)
- [Agent execution map](AGENTS.md)
- [Docs architecture for agents](docs/references/docs-architecture-llms.md)

## Curated external context

- [Harness engineering overview (OpenAI)](https://openai.com/index/harness-engineering/)
- [Ralph Loop background](https://ghuntley.com/loop/)
- [Agent loop patterns (Anthropic)](https://www.anthropic.com/engineering/building-effective-agents)
