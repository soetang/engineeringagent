from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.adapters.quality.runtime import RuntimeChecksRunner
from engineeringagent.domain.quality import ChecksRunResult, HarnessCheckPhase
from engineeringagent.ports import ChecksRunRequest


def test_runtime_checks_runner_delegates_to_concrete_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter should forward the typed request to the checks runtime."""
    captured: dict[str, object] = {}
    expected = ChecksRunResult(ok=True, dry_run=False)

    def _fake_run_checks(
        project_root: Path,
        **kwargs: object,
    ) -> ChecksRunResult:
        captured.update(
            project_root=project_root,
            **kwargs,
        )
        return expected

    monkeypatch.setattr(
        "engineeringagent.adapters.quality.runtime.run_checks",
        _fake_run_checks,
    )

    result = RuntimeChecksRunner().run(
        ChecksRunRequest(
            project_root=Path("/tmp/project"),
            selected_checks=["commands"],
            check_id="smoke",
            feature_path="docs/specifications/features/FEAT-001/spec.yaml",
            phase=HarnessCheckPhase.FEATURE_DONE,
            base="main",
            head="HEAD",
            verbose_output=True,
            dry_run=True,
        )
    )

    assert result is expected
    assert captured == {
        "project_root": Path("/tmp/project"),
        "phase": HarnessCheckPhase.FEATURE_DONE,
        "checks": ["commands"],
        "check_id": "smoke",
        "feature_path": "docs/specifications/features/FEAT-001/spec.yaml",
        "verbose_output": True,
        "base": "main",
        "head": "HEAD",
        "dry_run": True,
    }


def test_runtime_checks_runner_uses_quality_domain_group_helper() -> None:
    """Reviewer-group detection should reuse the shared quality-domain helper."""
    runner = RuntimeChecksRunner()

    assert runner.reviewers_group_selected(["reviewers"]) is True
    assert runner.reviewers_group_selected(["commands"]) is False
