from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "check_shared_kernel_locality.py"
    )


def _run_checker(
    project_root: Path,
    *,
    checker_path: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(checker_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def _violations(payload: dict[str, object]) -> list[str]:
    return cast(list[str], payload["violations"])


def _write_file(project_root: Path, relative_path: str, content: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_shared_kernel_fixture(project_root: Path) -> None:
    _write_file(
        project_root,
        "src/engineeringagent/domain/shared/enums.py",
        "from enum import Enum\n"
        "class FeatureStatus(str, Enum):\n    BACKLOG = 'backlog'\n"
        "class PlanningTier(str, Enum):\n    DIRECT = 'direct'\n"
        "class CheckPhase(str, Enum):\n    MANUAL = 'manual'\n",
    )
    _write_file(
        project_root,
        "src/engineeringagent/domain/shared/ids.py",
        "from typing import Annotated\n"
        "from pydantic import Field\n"
        "FeatureId = Annotated[str, Field(strict=True, min_length=1)]\n"
        "PhaseId = Annotated[str, Field(strict=True, min_length=1)]\n"
        "CheckId = Annotated[str, Field(strict=True, min_length=1)]\n"
        "TopicId = Annotated[str, Field(strict=True, min_length=1)]\n",
    )
    _write_file(project_root, "src/engineeringagent/domain/shared/__init__.py", "")


def test_shared_kernel_locality_rule_emits_expected_rule_id(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Expose the stable architecture rule id for shared-kernel locality."""
    _write_shared_kernel_fixture(tmp_path)

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.shared-kernel-locality"


def test_shared_kernel_locality_rule_flags_raw_progress_event_feature_id(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject raw string feature ids restored in the audit-domain event model."""
    _write_shared_kernel_fixture(tmp_path)
    _write_file(
        tmp_path,
        "src/engineeringagent/domain/audit/progress_event.py",
        "from pydantic import BaseModel\n"
        "class ProgressEvent(BaseModel):\n"
        "    feature_id: str | None = None\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/domain/audit/progress_event.py:1 field feature_id must use shared-kernel type FeatureId; import shared identifiers from engineeringagent.domain.shared instead of raw strings."
    ]


def test_shared_kernel_locality_rule_flags_raw_guidance_topic_canonical_id(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Reject raw string topic ids restored in the guidance-domain model."""
    _write_shared_kernel_fixture(tmp_path)
    _write_file(
        tmp_path,
        "src/engineeringagent/domain/guidance/topic.py",
        "from pydantic import BaseModel\n"
        "class GuidanceTopic(BaseModel):\n"
        "    canonical_id: str\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/domain/guidance/topic.py:1 field canonical_id must use shared-kernel type TopicId; import shared identifiers from engineeringagent.domain.shared instead of raw strings."
    ]


def test_shared_kernel_locality_rule_allows_domain_models_using_shared_ids(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when guidance and audit domain models import the shared id aliases."""
    _write_shared_kernel_fixture(tmp_path)
    _write_file(
        tmp_path,
        "src/engineeringagent/domain/audit/progress_event.py",
        "from engineeringagent.domain.shared import FeatureId\n"
        "from pydantic import BaseModel\n"
        "class ProgressEvent(BaseModel):\n"
        "    feature_id: FeatureId | None = None\n",
    )
    _write_file(
        tmp_path,
        "src/engineeringagent/domain/guidance/topic.py",
        "from engineeringagent.domain.shared import TopicId\n"
        "from pydantic import BaseModel\n"
        "class GuidanceTopic(BaseModel):\n"
        "    canonical_id: TopicId\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []
