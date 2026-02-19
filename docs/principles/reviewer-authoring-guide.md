# Reviewer Authoring Guide

This guide is for humans creating or updating reviewer agents in a repository.
Use it when adding a new reviewer, changing reviewer scope, or migrating old prompt files.

## 1) Create a reviewer entry

Define the reviewer in `harness/reviewers.yaml`.

Minimum fields:

- `prompt_file`: repo-relative markdown path under `harness/reviewers/prompts/`
- `trigger.phase`: `iteration_end` or `feature_done`

Common optional fields:

- `trigger.on_change`: path globs that scope when the reviewer runs
- `approval.first_feature_approval`: boolean (default `true`)
- `sandbox.mode`: `temp_worktree_snapshot` (snapshot) or `empty_folder` (explicit-asset sandbox)
- `sandbox.assets`: list of repo-relative paths to include in an `empty_folder` sandbox (files or directories)
- `feedback_context`: optional string forwarded verbatim alongside reviewer feedback into the next implement pass.

Use `feedback_context` to describe reviewer scope limitations (for example, clean-room sandboxes that do not include `src/` or `tests/`) so implement treats failures as real but chooses fixes that align with the full repository and feature specs.

You can scaffold a baseline config and prompt set with:

```bash
uvx engineeringagent reviewers init
```

## 2) Author the prompt without response-format boilerplate

Create prompt markdown files under `harness/reviewers/prompts/`.

Reviewer prompts should contain only review intent and scope guidance.
Do not include response-format placeholders or custom JSON envelope instructions.

Important contract rules:

- Do keep prompts focused on review intent, evidence expectations, and scope.
- Do not duplicate or customize the decision envelope contract in prompt prose.
- Do rely on backend-owned structured output via `run_agent(..., output_type=ReviewerDecisionEnvelope)`.

## 3) Keep reviewer instructions focused on review intent

Keep prompt text specific to what the reviewer should evaluate:

- scope boundaries (which files or concerns to focus on)
- quality criteria (readability, correctness, docs/process, etc.)
- required evidence or failure reporting expectations

The decision envelope stays canonical (`decision`, `summary`, optional `required_actions`, `scope_notes`).

## 4) Migrate existing prompts

When migrating older reviewer prompts:

1. Remove bespoke output-format prose (for example, hand-written JSON field instructions).
2. Remove any legacy response-format placeholder text.
3. Keep reviewer-specific evaluation guidance that is not format boilerplate.
4. Run validation to catch contract issues.

Recommended checks:

```bash
uv run engineeringagent validate
uvx engineeringagent reviewers list
```

## 5) Troubleshooting

- If validation reports deprecated response-format placeholder usage, remove it from the prompt file.
- If reviewer output is malformed, the runtime parser emits a deterministic `request_changes` envelope.
- For full contract details and policy examples, see `docs/references/reviewer-agents-llms.md`.
