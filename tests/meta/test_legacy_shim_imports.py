from __future__ import annotations

import importlib.util


def test_legacy_checks_packages_are_removed() -> None:
    assert importlib.util.find_spec("engineeringagent.fitness") is None


def test_legacy_shims_are_importable() -> None:
    import engineeringagent.progress_logging as progress_logging

    assert callable(progress_logging.append_jsonl_record)
    assert callable(progress_logging.append_text_block)

    import engineeringagent.progress_paths as progress_paths

    assert isinstance(progress_paths.PROGRESS_DIRNAME, str)
    assert callable(progress_paths.progress_dir)
