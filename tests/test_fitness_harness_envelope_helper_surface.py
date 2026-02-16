from __future__ import annotations

from pathlib import Path


def test_harness_fitness_functions_do_not_depend_on_local_result_envelope_helper() -> (
    None
):
    repo_root = Path(__file__).resolve().parents[1]
    fitness_functions_root = repo_root / "harness" / "fitness-functions"

    legacy_helper_path = fitness_functions_root / "result_envelope.py"
    assert not legacy_helper_path.exists(), (
        "harness fitness functions must use engineeringagent.fitness.envelope; "
        "legacy helper should be removed"
    )

    offenders: list[str] = []
    for script_path in sorted(fitness_functions_root.glob("*.py")):
        contents = script_path.read_text(encoding="utf-8")
        if "from result_envelope import emit_result_envelope" in contents:
            offenders.append(str(script_path.relative_to(repo_root)))
        if "import result_envelope" in contents:
            offenders.append(str(script_path.relative_to(repo_root)))

    assert not offenders, "\n".join(sorted(set(offenders)))
