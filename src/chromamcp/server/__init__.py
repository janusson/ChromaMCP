"""The MCP surface (W8) — a local stdio server over the M1 library.

This is the only package in the tree that imports the ``mcp`` SDK.  The compute
path (``io``, ``geometry``, ``metrics``, ``criteria``, ``provenance``) stays free
of it, so ``AGENTS.md`` §3's boundary is a property the import graph can be
checked for (``tests/test_hardening.py``).

``assess_sequence`` and ``trend_qc`` are **M3** (``AGENTS.md`` §3): in this unit
they return an explicit "not implemented in this unit" error and never a
fabricated result.
"""

from __future__ import annotations

from chromamcp.server.server import build_server, main
from chromamcp.server.store import MAX_REFERENCES, PREFIX, ReferenceStore

__all__ = [
    "MAX_REFERENCES",
    "PREFIX",
    "ReferenceStore",
    "build_server",
    "main",
]
