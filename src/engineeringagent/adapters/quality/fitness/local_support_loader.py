from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def load_local_support_module(
    module_name: str,
    *,
    caller_file: Path,
) -> Any:
    """Load a sibling helper module from the caller's directory by file path."""
    module_path = caller_file.resolve().parent / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"failed to load support module: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
