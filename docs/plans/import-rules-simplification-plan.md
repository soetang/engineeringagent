---
schema_version: 1
task_id: simplify-import-rules-config
title: Simplify import rules config around module selectors and explicit modes
status: ready
branch: feat/simplify-import-rules-config
base_branch: main
phases:
  - id: schema
    title: Replace path-based selectors with dotted module and package selectors
    status: todo
  - id: semantics
    title: Make allow and deny behavior explicit through rule modes
    status: todo
  - id: policy
    title: Migrate the live import policy to the simplified schema
    status: todo
  - id: tests
    title: Lock the new behavior with targeted coverage and validation
    status: todo
---

# Import Rules Simplification Plan

## Goal

Replace path-based rule targeting with dotted module and package selectors and make rule behavior explicit so the config reads as package boundaries, not filesystem globs.

This plan assumes a breaking change: remove `paths` from the schema instead of carrying a compatibility layer.

This plan should use the post-merge `harness/policy/import_rules.yaml` from `feat/move-implementation-run-orchestration-boundary` as its baseline, then simplify and clean up from there.

## Problems In The Current Design

- Rule selection uses filesystem `paths`, but import matching uses Python module prefixes. That mixes two mental models in one rule.
- The policy leaks implementation details such as `src/.../**/*.py`, even though the checker only works on Python modules under `src/`.
- `allow` is not enough by itself today. A rule only fails when an import matches `deny` and does not match `allow`, so broad `deny: developer` entries are needed just to express an allowlist.
- Relative imports are configured separately with `allow.relative_import_roots`, even though the checker already resolves them to real module names.
- Some live rules overlap or are stale, so the policy currently enforces the same boundary in more than one place.
- The current YAML is harder to read than the actual architectural intent.

## Existing Rule Simplifications To Include

- Remove `application-must-not-import-presentation`, because it duplicates the `developer.application` slice of `no-non-entrypoint-imports-from-presentation` today.
- Remove `deny: developer` scaffolding from allowlist-style rules once `allow_only` exists.
- Remove `allow.relative_import_roots` once resolved-module matching becomes the only boundary mechanism.
- Replace the dead `src/developer/agents/**/*.py` selector with the real package name `developer.agent_backends` if that package should stay covered by the presentation boundary.
- Shrink the broad presentation deny rule so it covers only packages that are not already protected by stricter `allow_only` rules.
- Decide whether `developer.workspaces` should remain a narrow `deny_only` rule or become a full `allow_only` boundary; if it becomes `allow_only`, its explicit denies become redundant too.
- Clean up the branch-only orchestrator split rules so they do not rely on unsupported negated path entries like `!src/developer/orchestrators/loop/**/*.py`.
- Preserve the narrow `implementation-run-service-import-boundary`, but express it with a dotted module selector instead of a single-file path.

## Current Behavior To Preserve Or Change

### Preserve

- Only first-party `developer.*` imports are checked.
- Prefix matching stays package-oriented, so `developer.presentation` still means that package and all submodules.
- Rules continue to operate on package trees, not on one file at a time.
- Negative rules such as "must not import presentation" remain possible.

### Change

- Replace `paths` with dotted selectors as the rule target mechanism.
- Remove the need to mention `*.py` in config.
- Remove `relative_import_roots` from the schema.
- Make rule mode explicit so `allow` can mean "only these imports are allowed" without a companion deny-all entry.

## Proposed Rule Model

Each rule should answer two separate questions:

1. which module or package tree does this rule apply to?
2. what import policy applies inside that package tree?

### Target Selection

Use dotted selectors:

```yaml
targets:
  - developer.presentation
  - developer.application.services.implementation_run_service
```

Meaning:

- if the target resolves to a package directory, match every Python module in that package tree;
- if the target resolves to a concrete module file, match only that module;
- include nested subpackages recursively;
- include `__init__.py` files in that tree; and
- stop exposing raw filesystem globs in the user-facing config.

Implementation detail: the script can still map dotted selectors to `src/<module path>` internally, but that becomes invisible to the policy author.

### Target Overlap

The post-merge orchestration-boundary branch introduces a parent orchestrator rule plus more specific `developer.orchestrators.loop` and `developer.orchestrators.runs` rules.

The simplified design should define overlap explicitly instead of relying on path negation.

Recommended behavior:

- resolve every rule target to concrete Python files first;
- if multiple rules match the same file, use the most specific target; and
- fail validation when two rules have the same specificity for the same file and neither clearly wins.

This allows targeted child-package or single-module rules without carrying fragile path exclusions.

### Enforcement Modes

Use an explicit mode field.

#### `allow_only`

Any local import that does not match an allowed prefix is a violation.

```yaml
rules:
  - name: presentation-boundary
    description: Presentation is the CLI-facing layer and may depend on application but not on unrelated concrete subsystems.
    targets:
      - developer.presentation
    mode: allow_only
    allow:
      - developer.presentation
      - developer.application
```

This replaces the current pattern of:

- `allow` specific packages; and
- `deny: developer` just to make the allowlist enforceable.

#### `deny_only`

Any local import that matches a denied prefix is a violation.

```yaml
rules:
  - name: application-must-not-import-presentation
    targets:
      - developer.application
    mode: deny_only
    deny:
      - developer.presentation
```

This keeps simple negative rules simple.

#### `deny_except`

Any local import that matches `deny` is a violation unless it also matches `allow`.

```yaml
rules:
  - name: narrow-exception-rule
    targets:
      - developer.some_package
    mode: deny_except
    deny:
      - developer
    allow:
      - developer.some_package
      - developer.shared_protocols
```

This supports the rare "deny these except" case explicitly, instead of making every rule look like that.

## Relative Import Simplification

Drop `relative_import_roots` from the config.

Reasoning:

- the checker already resolves relative imports to normalized module names;
- `from .models import GatePhase` can be judged by its resolved module, not by the fact that it used `.` syntax; and
- once rules become selector-based, resolved-module matching is enough for most boundary policies.

Result:

- absolute and relative imports are evaluated the same way;
- policy authors think in terms of dotted local modules and packages; and
- config no longer duplicates the same intent in both `allow.local_prefixes` and `allow.relative_import_roots`.

One behavior change is worth making explicit: a relative import that resolves to an allowed package should pass, even if it uses `..`. If later you want a separate style rule like "only `.` relative imports are allowed", that should be a different checker or a separate optional syntax-level setting, not part of this simplification.

## Proposed YAML Shape

Recommended v2 shape:

```yaml
rules:
  - name: presentation-boundary
    targets:
      - developer.presentation
    mode: allow_only
    allow:
      - developer.presentation
      - developer.application

  - name: application-must-not-import-presentation
    description: Application composes use cases and should not depend on CLI presentation code.
    targets:
      - developer.application
    mode: deny_only
    deny:
      - developer.presentation
```

Schema rules:

- `name`: non-empty string.
- `description`: optional short architectural explanation for why the rule exists.
- `targets`: non-empty list of dotted module or package selectors.
- `mode`: one of `allow_only`, `deny_only`, `deny_except`.
- `allow`: required for `allow_only`; optional for `deny_except`; invalid for `deny_only`.
- `deny`: required for `deny_only` and `deny_except`; invalid for `allow_only`.

This keeps the schema strict and avoids ambiguous combinations.

## Implementation Plan

## Phase 1: Replace path-based selectors with dotted module and package selectors

### Checklist

- [ ] Replace `paths` with `targets` in `RuleSpec` and YAML parsing.
- [ ] Add optional `description` support for short architectural intent on each rule.
- [ ] Add strict validation that `targets` is a non-empty list of dotted module or package selectors.
- [ ] Remove `allowed_relative_import_roots` from the rule model.
- [ ] Resolve each configured target to either a `src/...` module file or package directory internally.
- [ ] Fail clearly when a configured target does not map to a real source module or package.
- [ ] Define and implement deterministic overlap handling for parent and child targets.

### Implementation Details

Update `harness/fitness/scripts/import_rules.py` so `RuleSpec` stores:

- `description`;
- `targets` instead of `paths`;
- `mode`;
- `allowed_local_prefixes`; and
- `denied_local_prefixes`.

Remove `allowed_relative_import_roots`.

Validation should be stricter than today. The current checker does not already protect against unsupported path features like `!`; it only checks that `paths` is a list of strings, so negated entries are accepted syntactically but ignored semantically. The new schema should fail fast for anything that is not a valid dotted selector or does not resolve to a real module or package.

The optional `description` should stay short and architectural. Violation output should include it when present so the rule explains both the boundary and the reason for it.

Add dotted-target-to-file resolution in place of path-glob matching.

Recommended behavior:

- convert `developer.presentation` into `src/developer/presentation`;
- convert `developer.application.services.implementation_run_service` into `src/developer/application/services/implementation_run_service.py`;
- fail clearly if a configured package does not map to an existing directory or package tree;
- gather all `.py` files recursively under that directory; and
- include `__init__.py` files.

This makes Python-ness implicit and removes the need for `*.py` in policy.

## Phase 2: Make allow and deny behavior explicit through rule modes

### Checklist

- [ ] Add `mode` with supported values `allow_only`, `deny_only`, and `deny_except`.
- [ ] Reject ambiguous config combinations such as `allow_only` plus `deny`.
- [ ] Rework violation evaluation to follow the configured mode directly.
- [ ] Remove rule-time dependence on relative-import syntax.
- [ ] Keep local-import detection scoped to `developer.*` for this change.

### Implementation Details

Update `is_violation()` to follow the mode directly:

- `allow_only`: local import is a violation when it does not match any allowed prefix.
- `deny_only`: local import is a violation when it matches any denied prefix.
- `deny_except`: local import is a violation when it matches a denied prefix and does not match any allowed prefix.

This is the core behavior fix the user asked for.

Remove relative-root handling from configuration and rule evaluation.

- Keep `collect_imports()` resolving relative imports to normalized modules.
- Stop carrying `relative_root` into rule evaluation.
- Remove config parsing and validation for `relative_import_roots`.

If `relative_root` becomes unused entirely, remove it from `ImportStatement` as part of the cleanup.

## Phase 3: Migrate the live import policy to the simplified schema

### Checklist

- [ ] Rewrite `harness/policy/import_rules.yaml` to use `targets` and `mode`.
- [ ] Add short architectural descriptions to each retained rule.
- [ ] Convert package boundary rules like presentation and orchestrators to `allow_only`.
- [ ] Convert negative rules like application-vs-presentation to `deny_only`.
- [ ] Use `deny_except` only where a real deny-with-exceptions rule is needed.
- [ ] Remove duplicate rules that are already enforced by a broader or stricter rule.
- [ ] Remove stale selectors that do not map to real packages.
- [ ] Reduce broad deny rules when stricter `allow_only` rules already imply the same boundary.
- [ ] Replace branch-only negated path exclusions with explicit parent/child target rules.
- [ ] Preserve necessary single-module boundaries using dotted module targets instead of file paths.
- [ ] Rename rules where useful so the new policy reads like architecture, not implementation detail.

### Implementation Details

Convert the post-merge `harness/policy/import_rules.yaml` to the new schema.

Expected conversions:

- `presentation`, `orchestrators`, `workspaces`, `version_control`, `forge`, and `config` rules become `allow_only` rules.
- `no-non-entrypoint-imports-from-presentation` and `application-must-not-import-presentation` become `deny_only` rules.
- the orchestrator split from `feat/move-implementation-run-orchestration-boundary` should be expressed with explicit `developer.orchestrators`, `developer.orchestrators.loop`, and `developer.orchestrators.runs` targets rather than unsupported negated paths.
- `implementation-run-service-import-boundary` should target `developer.application.services.implementation_run_service` directly.

Example conversion for presentation:

```yaml
- name: presentation-boundary
  targets:
    - developer.presentation
  mode: allow_only
  allow:
    - developer.presentation
    - developer.application
```

Recommended policy simplification during this phase:

- drop the standalone `application-must-not-import-presentation` rule;
- keep one presentation-facing `deny_only` rule for packages that still need an explicit "must not import presentation" constraint;
- remove packages from that broad deny rule when their own `allow_only` rule already excludes `developer.presentation`; and
- replace stale coverage for `developer.agents` with `developer.agent_backends` if the architectural intent is to keep backend code isolated from CLI presentation code.
- replace unsupported orchestrator path negation with explicit, precedence-aware dotted targets.

## Phase 4: Lock the new behavior with targeted coverage and validation

### Checklist

- [ ] Rewrite `harness/fitness/tests/test_import_rules.py` helpers for the new YAML schema.
- [ ] Add coverage for `allow_only`, `deny_only`, and `deny_except`.
- [ ] Verify relative imports pass or fail based on resolved package names alone.
- [ ] Verify package selector recursion covers nested modules and `__init__.py`.
- [ ] Verify config errors are clear for invalid `mode`, missing `targets`, incompatible allow/deny combinations, and nonexistent targets.
- [ ] Verify validation errors and violation output include useful rule descriptions when present.
- [ ] Run `uv run developer validate-plan docs/plans/import-rules-simplification-plan.md`.
- [ ] Run `pytest`, `ruff check`, `ruff format`, and `pyrefly check` once implementation lands.

### Implementation Details

Rewrite `harness/fitness/tests/test_import_rules.py` around the new schema and add missing coverage for:

- `allow_only` failing when a local import is not in the allowlist;
- `deny_only` failing when a denied import appears;
- `deny_except` allowing a specific exception to a broad deny;
- relative imports being accepted based on resolved module names without `relative_import_roots`;
- target resolution for both packages and exact modules;
- overlap resolution between parent and child targets;
- package selector recursion including nested modules and `__init__.py`; and
- clear failure when a configured target does not map to a real source module or package.

## Suggested Validation Rules

Add clear config validation errors for:

- missing or empty `targets`;
- invalid `mode`;
- `allow_only` without `allow`;
- `deny_only` without `deny`;
- `deny_except` without `deny`;
- unexpected `allow` on `deny_only`; and
- unexpected `deny` on `allow_only`;
- ambiguous overlapping targets with equal specificity; and
- unsupported or unresolvable dotted selectors.

These errors should point to the offending rule name.

## Risks And Decisions

### Breaking Config Change

This plan intentionally replaces `paths` now, because you chose not to keep a compatibility phase.

That means implementation should update all of the following together in one change:

- rule parsing;
- rule evaluation;
- the live YAML policy; and
- the test helpers and fixtures.

### Package Root Assumption

The checker currently treats only `developer.*` as first-party local imports.

Keep that assumption in this change. Generalizing to multiple local package roots is a separate design problem and would widen the scope unnecessarily.

### Syntax Versus Boundary Policy

This proposal treats relative and absolute imports the same once resolved.

That simplifies boundary rules, but it does mean syntax-level preferences are out of scope. If those matter later, add them as a separate concern.

## Recommended Execution Order

1. Rebase the plan mentally on the post-merge policy from `feat/move-implementation-run-orchestration-boundary`.
2. Define the new YAML schema and validation rules.
3. Update rule-file selection from `paths` to dotted `targets`.
4. Define and implement target-overlap precedence.
5. Rework `is_violation()` around `mode` semantics.
6. Remove `relative_import_roots` handling.
7. Rewrite `harness/policy/import_rules.yaml`.
8. Rewrite and expand `harness/fitness/tests/test_import_rules.py`.
9. Run `pytest`, `ruff check`, `ruff format`, and `pyrefly check`.

## Expected Outcome

After this change, a rule should read like architecture instead of path matching.

For example, the presentation rule becomes:

- apply to `developer.presentation`; and
- allow imports only from `developer.presentation` and `developer.application`.

That is the behavior you described, without requiring `src/.../**/*.py`, `relative_import_roots`, or a fake deny-all entry just to activate the allowlist.
