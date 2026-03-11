from __future__ import annotations

from pathlib import Path

from engineeringagent.application import (
    FeatureIterationRequest,
    FeatureIterationResult,
    FeatureIterationService,
)
from engineeringagent.ports import (
    FeatureIterationExecutionRequest,
    FeatureIterationExecutionResult,
)


def _build_request(**overrides: object) -> FeatureIterationRequest:
    fields: dict[str, object] = {
        "project_root": Path("/tmp/project"),
        "feature_path": Path("docs/specifications/features/FEAT-001/specification.yaml"),
        "run_all": False,
        "attempt": 3,
        "feedback": "fix the failing check",
        "verbose_output": True,
    }
    fields.update(overrides)
    return FeatureIterationRequest.model_validate(fields)


class _FakeFeatureIterationExecutor:
    def __init__(self, result: FeatureIterationExecutionResult) -> None:
        self.requests: list[FeatureIterationExecutionRequest] = []
        self._result = result

    def run(
        self,
        request: FeatureIterationExecutionRequest,
    ) -> FeatureIterationExecutionResult:
        self.requests.append(request)
        return self._result


def test_feature_iteration_service_delegates_to_feature_iteration_executor() -> None:
    """The service should forward the typed request to the executor port."""
    executor = _FakeFeatureIterationExecutor(
        FeatureIterationExecutionResult(
            completed=False,
            result="failed",
            failed_gate="tests",
            next_action="retry_same_feature",
            feedback="rerun focused tests",
            log_path=".engineeringagent/progress/FEAT-001/iteration-report.json",
            verification_status="failed:tests",
            verification_failed_command="uv run pytest tests/application",
            reviewer_status="not_run",
            reviewer_decision=None,
            failed_reviewer_id=None,
        )
    )

    result = FeatureIterationService(executor=executor).run(_build_request())

    assert executor.requests == [
        FeatureIterationExecutionRequest(
            project_root=Path("/tmp/project"),
            feature_path=Path(
                "docs/specifications/features/FEAT-001/specification.yaml"
            ),
            run_all=False,
            attempt=3,
            feedback="fix the failing check",
            verbose_output=True,
        )
    ]
    assert result == FeatureIterationResult(
        completed=False,
        result="failed",
        failed_gate="tests",
        next_action="retry_same_feature",
        feedback="rerun focused tests",
        log_path=".engineeringagent/progress/FEAT-001/iteration-report.json",
        verification_status="failed:tests",
        verification_failed_command="uv run pytest tests/application",
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
    )
