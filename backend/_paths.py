"""
Centralized sys.path setup for importing `mission_planner` from src/.

Import this module once at the top of any backend entry-point that needs
the mission_planner library:

    import backend._paths  # noqa: F401  — registers src/ on sys.path

When the package is installed in editable mode (`pip install -e .` with
Python ≥3.11), this module becomes a no-op because `mission_planner`
is already importable.
"""

import importlib.util
import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src_dir = os.path.join(_project_root, "src")


def _ensure_importable() -> None:
    """Add project root and src/ to sys.path only if mission_planner isn't already importable."""
    if importlib.util.find_spec("mission_planner") is not None:
        return  # Already importable (e.g. editable install)

    for path in (_project_root, _src_dir):
        if path not in sys.path:
            sys.path.insert(0, path)


_ensure_importable()
