"""Scaffold tests — the invariants that must hold before any science is written.

These are not busywork.  ``test_version_matches_package_metadata`` is what stops the
pyproject version and ``__version__`` drifting apart, and ``test_package_is_typed`` keeps
this a PEP 561 typed package, so a type checker sees real signatures instead of ``Any``.
"""

from __future__ import annotations

from importlib import metadata
from pathlib import Path

import chromamcp


def test_version_matches_package_metadata() -> None:
    assert chromamcp.__version__ == metadata.version("chromamcp")


def test_package_is_typed() -> None:
    package_dir = Path(chromamcp.__file__).parent
    assert (package_dir / "py.typed").is_file()


def test_no_runtime_dependencies_yet() -> None:
    """The scaffold ships no runtime dependency; W1 adds them one recorded at a time."""
    requires = metadata.requires("chromamcp") or []
    runtime = [r for r in requires if "extra ==" not in r]
    assert runtime == []
