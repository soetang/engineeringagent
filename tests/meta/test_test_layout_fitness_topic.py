from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("old_relpath", "new_relpath"),
    [
        ("tests/test_fitness_adapters.py", "tests/fitness/test_fitness_adapters.py"),
        (
            "tests/test_fitness_catalog_generation.py",
            "tests/fitness/test_fitness_catalog_generation.py",
        ),
        ("tests/test_fitness_contract.py", "tests/fitness/test_fitness_contract.py"),
        (
            "tests/test_fitness_harness_envelope_helper_surface.py",
            "tests/fitness/test_fitness_harness_envelope_helper_surface.py",
        ),
        (
            "tests/test_fitness_harness_supported_surface_docs.py",
            "tests/fitness/test_fitness_harness_supported_surface_docs.py",
        ),
        ("tests/test_fitness_manifest.py", "tests/fitness/test_fitness_manifest.py"),
        (
            "tests/test_fitness_manifest_contract.py",
            "tests/fitness/test_fitness_manifest_contract.py",
        ),
        (
            "tests/test_fitness_no_facade_varargs_shims.py",
            "tests/fitness/test_fitness_no_facade_varargs_shims.py",
        ),
        (
            "tests/test_fitness_parallel_runner.py",
            "tests/fitness/test_fitness_parallel_runner.py",
        ),
        (
            "tests/test_fitness_registry.py",
            "tests/fitness/test_fitness_registry.py",
        ),
        (
            "tests/test_fitness_rule_id_collisions.py",
            "tests/fitness/test_fitness_rule_id_collisions.py",
        ),
        (
            "tests/test_fitness_rules_directionality.py",
            "tests/fitness/test_fitness_rules_directionality.py",
        ),
        (
            "tests/test_fitness_rules_docs_allowlist_policy.py",
            "tests/fitness/test_fitness_rules_docs_allowlist_policy.py",
        ),
        (
            "tests/test_fitness_rules_harness_root_yaml_only.py",
            "tests/fitness/test_fitness_rules_harness_root_yaml_only.py",
        ),
        (
            "tests/test_fitness_rules_harness_src_import_allowlist.py",
            "tests/fitness/test_fitness_rules_harness_src_import_allowlist.py",
        ),
        (
            "tests/test_fitness_rules_logging_path_locality.py",
            "tests/fitness/test_fitness_rules_logging_path_locality.py",
        ),
        (
            "tests/test_fitness_rules_loop_subprocess_boundary.py",
            "tests/fitness/test_fitness_rules_loop_subprocess_boundary.py",
        ),
        (
            "tests/test_fitness_rules_markdown_locality.py",
            "tests/fitness/test_fitness_rules_markdown_locality.py",
        ),
        (
            "tests/test_fitness_rules_markdown_references.py",
            "tests/fitness/test_fitness_rules_markdown_references.py",
        ),
        (
            "tests/test_fitness_rules_prompt_locality.py",
            "tests/fitness/test_fitness_rules_prompt_locality.py",
        ),
        (
            "tests/test_fitness_rules_scaffold_docs_exact_sync.py",
            "tests/fitness/test_fitness_rules_scaffold_docs_exact_sync.py",
        ),
        (
            "tests/test_fitness_rules_scaffold_template_agents_doc_links.py",
            "tests/fitness/test_fitness_rules_scaffold_template_agents_doc_links.py",
        ),
        (
            "tests/test_fitness_rules_scaffold_template_locality.py",
            "tests/fitness/test_fitness_rules_scaffold_template_locality.py",
        ),
        (
            "tests/test_fitness_rules_source_first_loop_commands.py",
            "tests/fitness/test_fitness_rules_source_first_loop_commands.py",
        ),
        (
            "tests/test_fitness_side_effect_contract.py",
            "tests/fitness/test_fitness_side_effect_contract.py",
        ),
    ],
)
def test_fitness_tests_are_grouped_under_topic_folder(
    pytestconfig: pytest.Config,
    old_relpath: str,
    new_relpath: str,
) -> None:
    """Enforce a stable, topic-oriented layout for fitness-related tests."""

    repo_root = Path(pytestconfig.rootpath)

    assert (repo_root / new_relpath).is_file(), f"missing moved test: {new_relpath}"
    assert not (repo_root / old_relpath).exists(), (
        f"unexpected root test: {old_relpath}"
    )
