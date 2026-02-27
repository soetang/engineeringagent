from __future__ import annotations

import time
from time import monotonic_ns
from pathlib import Path
from typing import Any

import yaml

from engineeringagent.checks.commands.runtime import (
    CommandInvocationRecord,
    plan_command_checks,
)
from engineeringagent.checks.fitness.adapters import execute_rule_definition
from engineeringagent.checks.fitness.contracts import RuleStatus
from engineeringagent.checks.fitness.registry import build_rule_catalog
from engineeringagent.checks.fitness.runtime import plan_fitness_checks
from engineeringagent.checks.reviewers.runtime import (
    FALLBACK_REMEDIATION_GUIDANCE,
    RunPlannedReviewerChecksRequest,
    plan_reviewer_checks,
    run_planned_reviewer_checks_from_plan,
)
from engineeringagent.checks.validate.validator import validate
from engineeringagent.process import run_shell_command
from engineeringagent.specs import (
    HarnessCheckCommandDefinition,
    HarnessCheckFitnessDefinition,
    HarnessChecksDocument,
    load_yaml,
)
from engineeringagent.checks.planning_policy import ALWAYS_RUN_NO_ON_CHANGE_REASON

from .strategy_contracts import (
    CheckContext,
    CheckDecision,
    CheckExecutionRecord,
    CheckStrategy,
    make_check_decision,
    plan_doc_strategy_decisions,
    strategy_run_decisions,
)


def _checks_failure_header_lines(*, check_id: str, check_type: str) -> list[str]:
    """Build shared markdown mini-block header lines for checks failures."""

    return [
        "### Checks Failure",
        f"- check_id: `{check_id}`",
        f"- check_type: `{check_type}`",
    ]


class CommandCheckStrategy(CheckStrategy):
    """Plan and execute command checks with deterministic records."""

    check_type = "command"

    def __init__(self, *, doc: HarnessChecksDocument, verbose_output: bool) -> None:
        self._doc = doc
        self._verbose_output = verbose_output

    def plan(
        self,
        *,
        context: CheckContext,
    ) -> tuple[CheckDecision, ...]:
        return plan_doc_strategy_decisions(
            context=context,
            check_type=self.check_type,
            doc=self._doc,
            planner=plan_command_checks,
        )

    def execute(
        self,
        *,
        context: CheckContext,
        decisions: tuple[CheckDecision, ...],
    ) -> tuple[CheckExecutionRecord, ...]:
        records: list[CheckExecutionRecord] = []
        for decision in strategy_run_decisions(decisions):
            check_id = decision["check_id"]
            check = self._doc.checks.get(check_id)
            if not isinstance(check, HarnessCheckCommandDefinition):
                continue

            started_epoch_sec = int(time.time())
            started_monotonic_ns = monotonic_ns()
            proc = run_shell_command(context.project_root, check.command)
            finished_monotonic_ns = monotonic_ns()
            ended_epoch_sec = max(started_epoch_sec, int(time.time()))

            returncode_raw = getattr(proc, "returncode", None)
            returncode = returncode_raw if isinstance(returncode_raw, int) else None
            stdout = getattr(proc, "stdout", "") or ""
            stderr = getattr(proc, "stderr", "") or ""
            rendered_returncode = (
                returncode_raw if returncode_raw is not None else "unknown"
            )

            invocation = CommandInvocationRecord(
                check_id=check_id,
                command=check.command,
                returncode=returncode,
                started_epoch_sec=started_epoch_sec,
                ended_epoch_sec=ended_epoch_sec,
                started_monotonic_ns=started_monotonic_ns,
                finished_monotonic_ns=finished_monotonic_ns,
                duration_ms=(finished_monotonic_ns - started_monotonic_ns) / 1_000_000,
            )

            if self._verbose_output:
                if stdout:
                    print(stdout, end="")
                if stderr:
                    print(stderr, end="")

            check_output_parts = [
                f"[check:{check_id}] command={check.command}",
                f"[check:{check_id}] returncode={rendered_returncode}",
            ]
            output = f"{stdout}{stderr}".rstrip("\n")
            if output:
                check_output_parts.append(output)

            payload = None
            if returncode != 0:
                payload = {
                    "kind": "command_failure",
                    "check_id": check_id,
                    "command": check.command,
                }

            record = CheckExecutionRecord(
                check_id=check_id,
                check_type=self.check_type,
                ok=returncode == 0,
                output="\n".join(check_output_parts).strip(),
                payload=payload,
                timing={
                    "command_invocation": invocation.model_dump(mode="python"),
                },
            )
            records.append(record)
            if not record.ok:
                break

        return tuple(records)

    def render_prompt_feedback(
        self,
        *,
        failed_record: CheckExecutionRecord,
    ) -> str | None:
        payload = failed_record.payload or {}
        command = payload.get("command")
        if not isinstance(command, str) or not command.strip():
            return None
        lines = _checks_failure_header_lines(
            check_id=failed_record.check_id,
            check_type=self.check_type,
        )
        lines.append(f"- rerun: `{command}`")
        return "\n".join(lines)


class FitnessCheckStrategy(CheckStrategy):
    """Plan and execute fitness checks using the rule catalog."""

    check_type = "fitness"

    def __init__(self, *, doc: HarnessChecksDocument) -> None:
        self._doc = doc

    def plan(
        self,
        *,
        context: CheckContext,
    ) -> tuple[CheckDecision, ...]:
        return plan_doc_strategy_decisions(
            context=context,
            check_type=self.check_type,
            doc=self._doc,
            planner=plan_fitness_checks,
        )

    def execute(
        self,
        *,
        context: CheckContext,
        decisions: tuple[CheckDecision, ...],
    ) -> tuple[CheckExecutionRecord, ...]:
        records: list[CheckExecutionRecord] = []
        catalog = None

        for decision in strategy_run_decisions(
            decisions,
        ):
            record, catalog = self._execute_decision(
                context=context,
                decision=decision,
                catalog=catalog,
            )
            if record is None:
                continue
            records.append(record)
            if not record.ok:
                break

        return tuple(records)

    def _execute_decision(
        self,
        *,
        context: CheckContext,
        decision: CheckDecision,
        catalog: list[Any] | None,
    ) -> tuple[CheckExecutionRecord | None, list[Any] | None]:
        check_id = decision["check_id"]
        check = self._doc.checks.get(check_id)
        if not isinstance(check, HarnessCheckFitnessDefinition):
            return None, catalog

        active_catalog = catalog or build_rule_catalog(context.project_root)
        selection = "scope=all" if check.scope == "all" else "rule_ids"
        header = f"[check:{check_id}] type=fitness {selection}"
        requested_rule_ids = set(check.rule_ids or ())

        if check.scope != "all":
            selection_error = self._selection_error_record(
                check_id=check_id,
                header=header,
                requested_rule_ids=requested_rule_ids,
                catalog=active_catalog,
            )
            if selection_error is not None:
                return selection_error, active_catalog

        definitions = self._resolve_definitions(
            check=check,
            catalog=active_catalog,
            requested_rule_ids=requested_rule_ids,
        )
        output_lines, failed_rules = self._execute_rule_definitions(
            definitions=definitions,
            project_root=context.project_root,
            header=header,
        )
        payload = None
        if failed_rules:
            payload = {
                "kind": "fitness_failure",
                "check_id": check_id,
                "failed_rules": failed_rules,
            }
        return (
            CheckExecutionRecord(
                check_id=check_id,
                check_type=self.check_type,
                ok=not failed_rules,
                output="\n".join(output_lines).strip(),
                payload=payload,
            ),
            active_catalog,
        )

    def _selection_error_record(
        self,
        *,
        check_id: str,
        header: str,
        requested_rule_ids: set[str],
        catalog: list[Any],
    ) -> CheckExecutionRecord | None:
        present = {definition.metadata.rule_id for definition in catalog}
        missing = sorted(requested_rule_ids - present)
        if not missing:
            return None
        return CheckExecutionRecord(
            check_id=check_id,
            check_type=self.check_type,
            ok=False,
            output=(f"{header} missing_rule_ids={missing}").strip(),
            payload={
                "kind": "selection_error",
                "message": f"missing fitness rule_ids: {missing}",
                "check_id": check_id,
            },
        )

    def _resolve_definitions(
        self,
        *,
        check: HarnessCheckFitnessDefinition,
        catalog: list[Any],
        requested_rule_ids: set[str],
    ) -> list[Any]:
        if check.scope == "all":
            return catalog
        return [
            definition
            for definition in catalog
            if definition.metadata.rule_id in requested_rule_ids
        ]

    def _execute_rule_definitions(
        self,
        *,
        definitions: list[Any],
        project_root: Path,
        header: str,
    ) -> tuple[list[str], list[dict[str, object]]]:
        output_lines = [header]
        failed_rules: list[dict[str, object]] = []
        for definition in definitions:
            result = execute_rule_definition(definition, project_root)
            output_lines.append(
                (
                    f"[fitness:{result.rule_id}] status={result.status.value} "
                    f"summary={result.summary}"
                )
            )
            if result.status not in {RuleStatus.FAIL, RuleStatus.ERROR}:
                continue
            failed_rules.append(
                {
                    "rule_id": str(result.rule_id),
                    "remediation": str(definition.metadata.remediation),
                    "violations": list(result.violations or ()),
                    "details": result.details,
                }
            )
        return output_lines, failed_rules

    def render_prompt_feedback(
        self,
        *,
        failed_record: CheckExecutionRecord,
    ) -> str | None:
        payload = failed_record.payload or {}
        failed_rules_raw = payload.get("failed_rules")
        if not isinstance(failed_rules_raw, list) or not failed_rules_raw:
            return None

        lines = _checks_failure_header_lines(
            check_id=failed_record.check_id,
            check_type=self.check_type,
        )
        lines.append("- failed_rules:")
        for rule in failed_rules_raw:
            if not isinstance(rule, dict):
                continue
            rule_id = rule.get("rule_id")
            remediation = rule.get("remediation")
            if isinstance(rule_id, str) and isinstance(remediation, str):
                lines.append(f"  - `{rule_id}`: {remediation}")
        if len(lines) == 4:
            return None
        return "\n".join(lines)


class ValidateCheckStrategy(CheckStrategy):
    """Always-run schema/spec validation strategy."""

    check_type = "validate"

    def __init__(self, *, schema_only: bool) -> None:
        self._schema_only = schema_only

    def plan(
        self,
        *,
        context: CheckContext,
    ) -> tuple[CheckDecision, ...]:
        return (
            make_check_decision(
                check_id="validate",
                check_type=self.check_type,
                phase=context.phase,
                decision="run",
                reason=ALWAYS_RUN_NO_ON_CHANGE_REASON,
            ),
        )

    def execute(
        self,
        *,
        context: CheckContext,
        decisions: tuple[CheckDecision, ...],
    ) -> tuple[CheckExecutionRecord, ...]:
        if not strategy_run_decisions(decisions):
            return ()
        messages = validate(
            context.project_root,
            schema_only=self._schema_only,
        )
        if not messages:
            return (
                CheckExecutionRecord(
                    check_id="validate",
                    check_type=self.check_type,
                    ok=True,
                    output="",
                    payload=None,
                ),
            )
        return (
            CheckExecutionRecord(
                check_id="validate",
                check_type=self.check_type,
                ok=False,
                output="\n".join(messages).strip(),
                payload={
                    "kind": "validate_failure",
                    "messages": list(messages),
                },
            ),
        )

    def render_prompt_feedback(
        self,
        *,
        failed_record: CheckExecutionRecord,
    ) -> str | None:
        return None


class ReviewerCheckStrategy(CheckStrategy):
    """Plan and execute reviewer checks with checks-owned feedback rendering."""

    check_type = "reviewer"

    def __init__(self, *, doc: HarnessChecksDocument) -> None:
        self._doc = doc

    def plan(
        self,
        *,
        context: CheckContext,
    ) -> tuple[CheckDecision, ...]:
        return plan_doc_strategy_decisions(
            context=context,
            check_type=self.check_type,
            doc=self._doc,
            planner=plan_reviewer_checks,
        )

    def execute(
        self,
        *,
        context: CheckContext,
        decisions: tuple[CheckDecision, ...],
    ) -> tuple[CheckExecutionRecord, ...]:
        run_planned = strategy_run_decisions(decisions)
        if not run_planned:
            return ()

        feature_path = context.feature_path
        if feature_path is None:
            return (self._config_error_record("feature_path is required"),)
        if not feature_path.exists():
            return (
                self._config_error_record(
                    f"feature spec not found: {feature_path}",
                ),
            )

        feature_id, feature_error = self._load_feature_id(feature_path)
        if feature_error is not None:
            return (self._config_error_record(feature_error),)
        if feature_id is None:
            return (self._config_error_record("feature spec is missing required id"),)

        ok, failed_id, output, failed_payload = run_planned_reviewer_checks_from_plan(
            RunPlannedReviewerChecksRequest(
                project_root=context.project_root,
                doc=self._doc,
                phase=context.phase,
                changed_paths=context.changed_paths,
                feature_id=feature_id,
                feature_path=feature_path,
                run_agent_fn=context.run_agent_fn,
                feedback=context.feedback,
                verbose_output=context.verbose_output,
            ),
            run_planned,
        )
        return (
            CheckExecutionRecord(
                check_id=failed_id or run_planned[0]["check_id"],
                check_type=self.check_type,
                ok=ok,
                output=output,
                payload=failed_payload,
            ),
        )

    def render_prompt_feedback(
        self,
        *,
        failed_record: CheckExecutionRecord,
    ) -> str | None:
        payload = failed_record.payload or {}
        if payload.get("kind") != "reviewer_feedback":
            return None
        decision = payload.get("decision")
        if not isinstance(decision, dict):
            decision = {}
        summary = decision.get("summary")
        required_actions = decision.get("required_actions")
        lines = _checks_failure_header_lines(
            check_id=failed_record.check_id,
            check_type=self.check_type,
        )
        if isinstance(summary, str) and summary.strip():
            lines.append(f"- summary: {summary.strip()}")
        normalized_actions = (
            [
                action.strip()
                for action in required_actions
                if isinstance(action, str) and action.strip()
            ]
            if isinstance(required_actions, list)
            else []
        )
        if normalized_actions:
            lines.append("- required_actions:")
            for action in normalized_actions:
                lines.append(f"  - {action}")
        else:
            lines.append(f"- remediation: {FALLBACK_REMEDIATION_GUIDANCE}")
        return "\n".join(lines)

    def _config_error_record(self, message: str) -> CheckExecutionRecord:
        return CheckExecutionRecord(
            check_id="reviewer",
            check_type=self.check_type,
            ok=False,
            output=f"reviewers config error: {message}",
            payload={
                "kind": "reviewer_config_error",
                "message": message,
            },
        )

    def _load_feature_id(self, feature_path: Path) -> tuple[str | None, str | None]:
        try:
            feature_payload = load_yaml(feature_path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            return None, f"failed to load feature spec: {exc}"
        if not isinstance(feature_payload, dict):
            return None, "feature spec is missing required id"
        feature_id = str(feature_payload.get("id", "")).strip()
        return feature_id or None, None
