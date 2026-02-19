# Reviewer Authoring Guide

This guide is for contributors creating or updating repository reviewers.
Use it when adding a reviewer, changing reviewer scope, or migrating old prompt files.

## 1) Create a reviewer check entry

Define reviewers in `harness/checks.yaml` as checks with `type: reviewer`.

Required reviewer fields:

- `type`: `reviewer`
- `prompt_file`: repo-relative markdown path under `harness/reviewers/prompts/`

Common optional fields:

- `when.phase`: `feature_done` (or `manual`)
- `when.on_change`: path globs that scope when the reviewer runs
- `approval.first_feature_approval`: boolean (default `true`)
- `sandbox.mode`: `temp_worktree_snapshot` (snapshot) or `empty_folder` (explicit-asset sandbox)
- `sandbox.assets`: list of repo-relative paths copied into an `empty_folder` sandbox
- `feedback_context`: optional text forwarded with reviewer feedback into the next implement pass

Use `feedback_context` to record reviewer scope limits (for example, clean-room sandboxes that do not include `src/` or `tests/`) so implement treats failures as real and still picks fixes aligned with the feature spec.

## 2) Author prompt files without response-format boilerplate

Create prompt markdown files under `harness/reviewers/prompts/`.

Reviewer prompts should contain only review intent and scope guidance.
Do not include response-format placeholders or custom JSON envelope instructions.

Contract rules:

- Keep prompts focused on review intent, evidence expectations, and scope.
- Do not duplicate or customize the decision-envelope contract in prompt prose.
- Rely on backend-owned structured output via `run_agent(..., output_type=ReviewerDecisionEnvelope)`.

## 3) Keep reviewer instructions focused on review intent

Keep prompt text specific to what the reviewer should evaluate:

- scope boundaries (which files or concerns to focus on)
- quality criteria (readability, correctness, docs/process, and so on)
- required evidence or failure-reporting expectations

The decision envelope remains canonical (`decision`, `summary`, optional `required_actions`, `scope_notes`).

## 4) Migrate existing prompts

When migrating older reviewer prompts:

1. Remove bespoke output-format prose (for example, hand-written JSON field instructions).
2. Remove legacy response-format placeholder text.
3. Keep reviewer-specific evaluation guidance that is not format boilerplate.
4. Run validation and checks.

Recommended checks:

```bash
uv run engineeringagent validate
uv run engineeringagent checks run --phase feature_done
```

## 5) Troubleshooting

- If validation reports deprecated response-format placeholder usage, remove it from the prompt file.
- If reviewer output is malformed, runtime emits a deterministic `request_changes` envelope.
- For full contract details and policy examples, see `docs/references/reviewer-agents.md`.
