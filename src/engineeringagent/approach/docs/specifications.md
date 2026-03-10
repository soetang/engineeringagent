---
approach_id: specifications
---

# Spec Writing Guide

## Purpose

- Define how contributors create new feature specs for this repository.
- Ensure every new spec starts with a short user interview before drafting YAML.

## Hard Rule

- Do not draft a new feature package under `docs/spec/features/FEAT-XXX-some-header/` until you complete a user interview and the user confirms scope.
- If the feature changes any API/contract behavior, explicit contract-delta documentation is mandatory and high priority in the spec (old behavior -> new behavior, compatibility policy, migration/rollout expectation).

## Mandatory Interview Flow

1. Ask targeted questions first (no spec draft yet).
2. Capture answers in a concise scope summary.
3. Ask for explicit confirmation on the summary.
4. Draft the feature spec only after confirmation.

## Minimum Interview Topics

- Problem statement: what pain this feature solves.
- Scope boundary: what is in scope vs out of scope.
- Success criteria: how the user will judge completion.
- Constraints: safety, compatibility, or workflow constraints.
- Verification expectations: required commands or checks.
- Contract impact: which interfaces/behaviors change, whether compatibility is required, and whether migration is one-time or phased.
- Fitness-rule risk: whether the proposed behavior may violate active rules in `docs/fitness-functions/rules.md`.

## Question Quality Bar

- Ask specific, decision-shaping questions; avoid generic filler.
- Prefer 3-7 focused questions over one broad question.
- If tradeoffs exist, present options and recommend a default.

## Drafting Rules After Interview

- Emit and follow the feature contract schema exactly:
  - `uv run engineeringagent schema feature.spec --format yaml`
  - Use `uv run engineeringagent schema list` to discover available schema ids.
- Create a bundled feature package rooted at `docs/spec/features/FEAT-XXX-some-header/spec.yaml`.
- Bundled `spec.yaml` packages are the only supported active feature layout.
- Treat `spec.yaml` as the canonical source for feature identity, status, and acceptance.
- Keep active bundled `spec.yaml` files outcome-oriented. Sequencing belongs in `plan.md` phases, not in spec `subtasks`.
- `plan.md` owns implementation sequencing and per-phase status.
- `plan.md` must not replace canonical feature status in `spec.yaml`.
- Choose the planning tier explicitly: `direct`, `planned`, and `researched`.
  - `direct`: `spec.yaml` only.
  - `planned`: `spec.yaml` plus `plan.md`.
  - `researched`: `spec.yaml`, `research.md`, and `plan.md`.
- Keep acceptance criteria outcome-based and testable.
- Keep verification commands concrete and executable.
- Write verification/check commands as plain argv-style command strings; shell operators (for example `&&`, `|`, redirects, or subshell syntax) are invalid as command separators, but shell-like text inside a token (such as `$VAR`, `${VAR}`, or backticks) is treated as data.
- Preserve repository language and conventions used in existing FEAT files.
- Require an explicit fitness-function impact assessment for every new spec.
  - Evaluate the planned behavior against active rules in `docs/fitness-functions/rules.md` and call out likely violations.
  - If violations are likely, evaluate whether the current rule is still the right rule (current architecture intent, safety value, and false-positive risk).
  - Choose and document one path explicitly: adjust implementation to satisfy the rule, or adjust the rule with clear rationale and expected guardrails.
  - If a rule change is needed, document why the rule should change and name affected rule IDs/scripts/docs plus expected verification updates.
  - If no fitness updates are needed, record the exact statement "no fitness-function changes required" with a brief justification.
- For contract/API changes, encode explicit deltas in spec text (typically `constraints`, `implementation_notes`, and `acceptance`) including:
  - changed surfaces (schema/model, CLI/runtime behavior, prompt contract, docs),
  - exact old vs new behavior,
  - compatibility/deprecation policy,
  - migration scope and rollback/fallback expectations.

## Spec Creation Checklist

- Include required top-level fields in every active bundled `spec.yaml`:
  - `type` (one of: `feature`, `bug`, `spec`, `docs`, `chore`, `test`)
  - `expected_commit_subject` in `type: summary` format
- Keep the expected subject deterministic for the spec intent (example: `spec: add FEAT-016 commit message policy and spec typing`).
- Verify the spec validates before commit.
- Commit the spec/doc changes with the exact `expected_commit_subject` value.

## Post-Draft Commit Workflow

After creating or updating a bundled feature package, commit it in the same loop so state is recoverable.

1. Validate specs before commit:
   - `uv run engineeringagent validate --schema-only`
2. Stage only the intended spec/doc files:
   - `git add docs/spec/features/FEAT-XXX-some-header/spec.yaml`
   - `git add docs/spec/features/FEAT-XXX-some-header/plan.md`
   - `git add docs/spec/features/FEAT-XXX-some-header/research.md`
   - Add related doc updates when applicable.
3. Use a clear commit message focused on intent:
   - Example: `spec: add FEAT-007 path-first run CLI`
4. Create the commit:
   - `git commit -m "spec: add FEAT-007 path-first run CLI"`
5. Verify clean result:
   - `git status --short`

Notes:

- Keep one logical spec change per commit.
- Do not include unrelated code refactors in the same spec commit.

## Suggested Interview Summary Template

- Goal:
- In scope:
- Out of scope:
- Constraints:
- Done looks like:
- Verification signals:
- Fitness-rule risk:

## Definition of Ready for Spec Drafting

- User interview completed.
- Scope summary confirmed by user.
- Fitness-rule risk assessed, rule validity considered, and a path chosen (implementation adjustment vs rule adjustment).
- Open questions resolved or explicitly deferred.

## Contract Change Declaration (Required When Applicable)

- Include a dedicated contract-change block in the spec narrative (`implementation_notes` recommended).
- Use concrete statements, not implied intent.
- Minimum declaration format:
  - Surface: what contract changes.
  - Old behavior: what happens today.
  - New behavior: what must happen after implementation.
  - Compatibility policy: immediate break, temporary dual-support, or deprecation path.
  - Migration plan: which files/data/configs change and whether migration is one-time.
  - Verification evidence: tests/commands that prove the contract transition.

## If User Asks to "Just Write the Spec"

- Still run a brief interview (minimum 3 focused questions).
- Keep it fast, then draft immediately after answers.
