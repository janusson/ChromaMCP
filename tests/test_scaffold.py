"""Scaffold tests — the invariants that must hold before any science is written.

These are not busywork.  ``test_version_matches_package_metadata`` is what stops the
pyproject version and ``__version__`` drifting apart, and ``test_package_is_typed`` keeps
this a PEP 561 typed package, so a type checker sees real signatures instead of ``Any``.
"""

from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path

import chromamcp


def test_version_matches_package_metadata() -> None:
    assert chromamcp.__version__ == metadata.version("chromamcp")


def test_package_is_typed() -> None:
    package_dir = Path(chromamcp.__file__).parent
    assert (package_dir / "py.typed").is_file()


def test_runtime_dependencies_are_bounded() -> None:
    """Only the W1 mzML reader stack (numpy) may be a runtime dependency.

    ``AGENTS.md`` §5: the scaffold ships zero runtime dependencies and every
    addition is recorded at the point of addition.  W1 records exactly one —
    ``numpy`` — because the mzML reader itself is standard-library only.
    """
    requires = metadata.requires("chromamcp") or []
    runtime = [r for r in requires if "extra ==" not in r]
    names = {re.split(r"[<>=!~;\[\s]", r, maxsplit=1)[0].lower() for r in runtime}
    assert names == {"numpy"}, f"unexpected runtime dependencies: {sorted(names)}"
