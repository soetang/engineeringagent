from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
import zipfile

from pytest import Config
import pytest

from engineeringagent.adapters.documents import guidance_topic_catalog
from tests.presentation.cli.approach_fixture_data import (
    APPROACH_ALIAS_MAP,
    APPROACH_TOPIC_IDS,
)


_APPROACH_TOPIC_ID_PREFIX = re.compile(r"^\s*(?P<topic_id>[A-Za-z0-9-]+):")


def _parse_approach_topic_ids(payload: str) -> tuple[str, ...]:
    topic_ids: list[str] = []
    for line in payload.splitlines():
        match = _APPROACH_TOPIC_ID_PREFIX.match(line)
        if match is None:
            continue
        topic_ids.append(match.group("topic_id"))
    return tuple(topic_ids)


def _expected_frontmatter(document: str) -> dict[str, object]:
    frontmatter_text = document.split("---\n", 2)[1]
    import yaml

    payload = yaml.safe_load(frontmatter_text)
    assert isinstance(payload, dict)
    return payload


def test_guidance_topics_are_discoverable_and_sorted() -> None:
    """Discover packaged guidance topics in the canonical order."""
    topics = guidance_topic_catalog.list_packaged_guidance_topics()
    actual_ids = tuple(topic.canonical_id for topic in topics)
    actual_aliases = {topic.canonical_id: topic.aliases for topic in topics}
    assert actual_ids == APPROACH_TOPIC_IDS
    assert actual_aliases == APPROACH_ALIAS_MAP


def test_guidance_topics_include_frontmatter_and_title() -> None:
    """Expose topic ids from frontmatter and titles from the markdown body."""
    for topic in guidance_topic_catalog.list_packaged_guidance_topics():
        content = guidance_topic_catalog.load_guidance_topic_content(topic.canonical_id)
        frontmatter = _expected_frontmatter(content)
        assert frontmatter["approach_id"] == topic.canonical_id
        assert topic.title


def test_guidance_task_specific_topics_expose_frontmatter_descriptions() -> None:
    """Preserve task-specific topic descriptions from frontmatter."""
    descriptions = {
        topic.canonical_id: topic.description
        for topic in guidance_topic_catalog.list_packaged_guidance_topics()
    }

    assert descriptions["research-session"] == "Task-specific: only when creating research.md."
    assert descriptions["plan-session"] == "Task-specific: only when creating plan.md."


def test_load_guidance_topic_body_hides_frontmatter() -> None:
    """Return topic bodies without YAML frontmatter content."""
    rendered = guidance_topic_catalog.load_guidance_topic_body("plan-session")

    assert rendered.startswith("# Plan Session Approach")
    assert not rendered.startswith("---\n")


def _project_root(pytestconfig: Config) -> Path:
    """Return repository root path for this test file."""
    return Path(pytestconfig.rootpath)


def _build_package_artifacts(
    pytestconfig: Config, output_dir: Path
) -> tuple[Path, Path]:
    """Build wheel and sdist artifacts and return output paths."""
    pytest.importorskip(
        "build", reason="build dependency is required for packaging resource checks"
    )
    if not os.access(output_dir, os.W_OK):
        pytest.skip("build output directory is not writable")

    build_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--sdist",
            "--outdir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        cwd=_project_root(pytestconfig),
        check=False,
    )
    if build_result.returncode != 0:
        message = (build_result.stderr or "").strip() + (build_result.stdout or "").strip()
        normalized = message.lower()
        if (
            "backend 'hatchling.build' is not available" in normalized
            or "could not find a version that satisfies the requirement" in normalized
            or "no module named build" in normalized
            or "permission denied" in normalized
        ):
            pytest.skip(
                "build backend dependencies are unavailable or build output path "
                "cannot be written in this environment."
            )
        msg = build_result.stderr.strip() or build_result.stdout.strip()
        assert False, f"python -m build failed:\n{msg}"
    wheel_paths = sorted(output_dir.glob("*.whl"))
    sdist_paths = sorted(output_dir.glob("*.tar.gz"))
    assert wheel_paths
    assert sdist_paths
    return wheel_paths[0], sdist_paths[0]


@pytest.mark.integration
def test_guidance_docs_are_packaged_resources(pytestconfig: Config) -> None:
    """Ship packaged guidance markdown assets in wheel and sdist builds."""
    source_docs_root = (
        _project_root(pytestconfig) / "src" / "engineeringagent" / "approach" / "docs"
    )
    expected_docs = tuple(sorted(item.name for item in source_docs_root.glob("*.md")))
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)
        wheel_path, sdist_path = _build_package_artifacts(pytestconfig, artifact_dir)

        with zipfile.ZipFile(wheel_path) as wheel:
            wheel_members = set(wheel.namelist())
        for expected_doc in expected_docs:
            assert f"engineeringagent/approach/docs/{expected_doc}" in wheel_members

        with tarfile.open(sdist_path, "r:gz") as sdist:
            sdist_members = set(sdist.getnames())
        for expected_doc in expected_docs:
            expected_suffix = f"src/engineeringagent/approach/docs/{expected_doc}"
            assert any(
                member.endswith(expected_suffix) for member in sdist_members
            ), f"missing {expected_doc} in sdist artifact"

        env = os.environ.copy()
        env["PYTHONPATH"] = str(wheel_path)
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json; "
                "from importlib.resources import files; "
                "from engineeringagent.adapters.documents.guidance_topic_catalog import "
                "load_guidance_topic_content; "
                "payload = {\n"
                '    "topic_payload": load_guidance_topic_content("workflow"),\n'
                '    "docs": sorted(\n'
                "        path.name\n"
                "        for path in files(\"engineeringagent\").joinpath(\"approach\").joinpath(\"docs\").iterdir()\n"
                "        if path.suffix == \".md\"\n"
                "    ),\n"
                "}\n"
                "print(json.dumps(payload))",
            ],
            capture_output=True,
            env=env,
            check=True,
            text=True,
            cwd=artifact_dir,
        )

    installed_data = json.loads(proc.stdout.strip())
    source_payload = (source_docs_root / "workflow.md").read_text(encoding="utf-8")
    assert installed_data["topic_payload"] == source_payload
    assert tuple(sorted(item for item in installed_data["docs"])) == expected_docs


def test_guidance_topic_lookup_accepts_aliases() -> None:
    """Resolve stable aliases to their canonical topic ids."""
    assert guidance_topic_catalog.resolve_guidance_topic_id("principles") == "principles"
    assert (
        guidance_topic_catalog.resolve_guidance_topic_id("harness-engineering-principles")
        == "principles"
    )
    assert guidance_topic_catalog.resolve_guidance_topic_id("spec-writing") == "specifications"
    assert (
        guidance_topic_catalog.resolve_guidance_topic_id("reviewer-authoring-guide")
        == "reviewer-authoring"
    )


def test_guidance_topic_lookup_raises_for_unknown() -> None:
    """Reject unknown guidance topic ids with a stable error type."""
    with pytest.raises(guidance_topic_catalog.UnknownGuidanceTopicIdError):
        guidance_topic_catalog.resolve_guidance_topic_id("does-not-exist")


@pytest.mark.parametrize("topic_id", ["quality-checks", "workflow"])
def test_guidance_topics_resolve_stable_resource_contract(topic_id: str) -> None:
    """Expose stable filename and source-path hints for packaged topics."""
    topic = next(
        item
        for item in guidance_topic_catalog.list_packaged_guidance_topics()
        if item.canonical_id == topic_id
    )
    content = guidance_topic_catalog.load_guidance_topic_content(topic_id)
    frontmatter = _expected_frontmatter(content)

    assert topic.filename.endswith(".md")
    assert Path(topic.path).name == topic.filename
    assert frontmatter["approach_id"] == topic_id
