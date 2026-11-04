"""The filesystem boundary (W8.2).

Every file-reading tool is confined to a single root directory, so a mistyped or
hostile path cannot reach the rest of the filesystem.  The root is
``CHROMAMCP_ALLOWED_ROOT`` when it is set, and the process working directory
otherwise; the path is **symlink-resolved before the check**, so a link that
points outside the root is refused the same as a literal outside path.

A refusal names the resolved path, the root, and the variable to set — an escape
is an actionable condition, not a generic failure (``AGENTS.md`` §10).

The *concept* follows the sibling project MSMCP (``msmcp/security.py``, MIT); the
implementation is written here (``AGENTS.md`` §6).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from chromamcp.errors import PathEscapeError

__all__ = [
    "ENV_ALLOWED_ROOT",
    "FilesystemPolicy",
    "policy_from_env",
    "resolve_path",
]

#: The environment variable a client sets to widen (or narrow) the boundary.
ENV_ALLOWED_ROOT = "CHROMAMCP_ALLOWED_ROOT"


@dataclass(frozen=True, slots=True)
class FilesystemPolicy:
    """The one root every file-reading tool is confined to."""

    allowed_root: Path = field(default_factory=Path.cwd)

    def __post_init__(self) -> None:
        # Store an absolute, symlink-resolved root so the containment test is
        # comparing like with like.
        object.__setattr__(
            self,
            "allowed_root",
            Path(self.allowed_root).expanduser().resolve(strict=False),
        )


def policy_from_env() -> FilesystemPolicy:
    """The policy named by ``CHROMAMCP_ALLOWED_ROOT``, or the working directory."""
    raw = os.environ.get(ENV_ALLOWED_ROOT)
    if raw is None or not raw.strip():
        return FilesystemPolicy()
    return FilesystemPolicy(Path(raw))


def resolve_path(path: str | Path, *, policy: FilesystemPolicy) -> Path:
    """Resolve *path* and refuse it if it escapes ``policy.allowed_root``."""
    candidate = Path(path).expanduser().resolve(strict=False)
    root = policy.allowed_root
    if candidate != root and root not in candidate.parents:
        raise PathEscapeError(
            f"'{candidate}' is outside the allowed root '{root}'. Set "
            f"{ENV_ALLOWED_ROOT} to a directory that contains it, or move the "
            f"file under the root."
        )
    return candidate
