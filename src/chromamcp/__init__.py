"""ChromaMCP — an MCP server for the chromatography half of LC-MS and GC-MS methods.

The package holds the mzML reader (``io``), the peak geometry (``geometry``), the
system-suitability panel (``metrics``), the criteria-file contract (``criteria``), the
provenance record (``provenance``), the filesystem boundary (``security``) and the
stdio MCP surface (``server``).  The compute path is all of those except ``server``,
which is the one module that imports the ``mcp`` SDK.

The rules that bind this repository live in ``AGENTS.md`` at the repository root, and
behind it ``SOURCES.md`` and ``TOLERANCES.md`` and the project documents in the
coordination hub (``~/Agent/Projects/ChromaMCP/`` — the milestone briefs for the
implementer rules, and ``PLAN.md`` §3 for the claims this project must never make). An
uncited metric does not ship.
"""

__version__ = "0.0.1"
