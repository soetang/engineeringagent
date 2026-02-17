from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from .adapters import execute_rule_definition
from .contracts import FitnessRuleResult, RuleStatus
from .registry import build_rule_catalog


class FitnessRunSummary(BaseModel):
    """Deterministic aggregate output for one fitness run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    results: tuple[FitnessRuleResult, ...]

    @property
    def has_failures(self) -> bool:
        """Return whether the run contains any failing or errored rules."""
        return any(
            result.status in {RuleStatus.FAIL, RuleStatus.ERROR}
            for result in self.results
        )


def run_rule_catalog(
    project_root: Path,
    *,
    jobs: int = 1,
    manifest_path: Path | None = None,
) -> FitnessRunSummary:
    """Execute active fitness rules with deterministic result ordering."""
    if jobs < 1:
        raise ValueError("jobs must be >= 1")

    definitions = build_rule_catalog(
        project_root,
        manifest_path=manifest_path,
    )
    if not definitions:
        return FitnessRunSummary(results=())

    if jobs == 1:
        return FitnessRunSummary(
            results=tuple(
                execute_rule_definition(definition, project_root)
                for definition in definitions
            )
        )

    max_workers = min(jobs, len(definitions))
    ordered_results: list[FitnessRuleResult | None] = [None] * len(definitions)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(execute_rule_definition, definition, project_root): index
            for index, definition in enumerate(definitions)
        }
        for future in as_completed(futures):
            ordered_results[futures[future]] = future.result()

    return FitnessRunSummary(
        results=tuple(_coerce_result(result) for result in ordered_results)
    )


def _coerce_result(result: FitnessRuleResult | None) -> FitnessRuleResult:
    if result is None:
        raise ValueError("internal error: missing fitness result")
    return result
