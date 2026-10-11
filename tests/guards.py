"""Guards shared by the W7 hardening tests.

The banned vocabulary is assembled from fragments so the words do not appear as
literals anywhere in the tree — the vocabulary check greps the tree for them,
and a test that named them literally would flag itself.
"""

from __future__ import annotations

#: The vocabulary ``AGENTS.md`` §2 forbids.  Built from fragments (see above).
BANNED_WORDS: tuple[str, ...] = (
    "valid" + "ated",
    "confirm" + "ed",
    "compli" + "ant",
    "audit" + "-ready",
    "certif" + "ied",
    "regulatory" + "-grade",
    "guarant" + "eed",
)

#: Top-level packages the compute path must never import (``AGENTS.md`` §3): an
#: MCP SDK, a network client, an LLM client, or a vendor raw-file parser.
FORBIDDEN_TOP_LEVEL: frozenset[str] = frozenset(
    {
        # MCP SDK
        "mcp",
        # network clients
        "socket",
        "requests",
        "httpx",
        "aiohttp",
        "urllib3",
        "ftplib",
        "smtplib",
        "telnetlib",
        "xmlrpc",
        # LLM clients and frameworks
        "openai",
        "anthropic",
        "transformers",
        "torch",
        "langchain",
        "vllm",
        # vendor / competing raw-file parsers
        "pymzml",
        "pyteomics",
        "pynumpress",
        "ms_deisotope",
    }
)

#: Dotted modules that are forbidden even though their top-level name is generic.
FORBIDDEN_EXACT: frozenset[str] = frozenset(
    {"urllib.request", "http.client", "http.server"}
)
