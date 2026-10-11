"""Error hierarchy for ChromaMCP.

Every expected failure is a named exception, so a caller can tell *why* a request
failed and act on it.  A refused format, a malformed file and an unresolvable
channel are distinct, actionable conditions — never a silently degraded number
(``AGENTS.md`` §4, ``M1-BRIEF.md`` §7.4).

The names describe what was observed, not a conclusion: a refused file is
*refused* — the reader states no verdict on it.
"""

from __future__ import annotations

__all__ = [
    "ChannelResolutionError",
    "ChromamcpError",
    "InaccessiblePathError",
    "MalformedFileError",
    "UnsupportedFormatError",
]


class ChromamcpError(Exception):
    """Base class for all expected ChromaMCP errors."""


class InaccessiblePathError(ChromamcpError):
    """Raised when a path cannot be read: missing, not a regular file, or no access."""


class UnsupportedFormatError(ChromamcpError):
    """Raised when a file's format is recognised but not supported (mzML only)."""


class MalformedFileError(ChromamcpError):
    """Raised when a file is opened but does not parse as valid mzML."""


class ChannelResolutionError(ChromamcpError):
    """Raised when a requested chromatogram channel cannot be resolved unambiguously."""
