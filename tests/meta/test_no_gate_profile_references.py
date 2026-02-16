from __future__ import annotations

import re
from pathlib import Path


def _iter_candidate_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in {".py", ".md", ".yaml", ".yml", ".toml", ".txt"}:
            continue
        candidates.append(path)
    return candidates


def test_no_gate_profile_references_outside_specs() -> None:
    project_root = Path(__file__).resolve().parents[2]

    scan_roots = [
        project_root / "src" / "engineeringagent",
        project_root / "harness",
        project_root / "docs" / "references",
        project_root / "docs" / "principles",
        project_root / "docs" / "fitness-functions",
        project_root / "README.md",
    ]

    patterns = {
        "gate_profile": re.compile(r"\bgate_profile\b"),
        "loop_fast": re.compile(r"\bloop_fast\b"),
        "legacy_gates_yaml": re.compile(r"harness/gates\.yaml"),
        "legacy_gates_command": re.compile(r"\bengineeringagent\s+gates\b"),
        "legacy_gates_run": re.compile(r"\bgates\s+run\b"),
        "legacy_gates_plan": re.compile(r"\bgates\s+plan\b"),
        "legacy_gates_list": re.compile(r"\bgates\s+list\b"),
        "legacy_profile_flag": re.compile(r"--profile\s+"),
    }

    violations: list[str] = []
    for scan_root in scan_roots:
        files: list[Path]
        if scan_root.is_file():
            files = [scan_root]
        else:
            files = _iter_candidate_files(scan_root)

        for path in files:
            # Feature specs are allowed to mention legacy surfaces for migration context.
            if "docs/spec/" in path.as_posix():
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            for name, pattern in patterns.items():
                if pattern.search(content):
                    violations.append(f"{path.as_posix()}: contains {name}")

    assert not violations, "Gate profile references remain:\n" + "\n".join(violations)
