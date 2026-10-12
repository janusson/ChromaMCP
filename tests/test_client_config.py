"""W9 tests — the client configuration blocks.

The blocks are documentation, so this is what keeps them honest: every fenced
JSON block in ``docs/clients/`` must parse, carry the wrapper key that client
uses, and launch ``python -m chromamcp.server`` with ``CHROMAMCP_ALLOWED_ROOT``
set.  It also asserts the one thing ``AGENTS.md`` §9 requires of the tree — that
there is **no README**.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_DOCS = _ROOT / "docs" / "clients"

#: doc -> the wrapper key that client's own schema uses.
_CASES = {
    "claude-desktop.md": "mcpServers",
    "claude-code.md": "mcpServers",
    "cursor.md": "mcpServers",
    "vscode.md": "servers",
    "zed.md": "context_servers",
}
_WRAPPERS = frozenset(_CASES.values())


def _blocks(name: str) -> list[dict[str, object]]:
    text = (_DOCS / name).read_text(encoding="utf-8")
    raw = re.findall(r"```json\n(.*?)```", text, re.DOTALL)
    assert raw, f"{name} carries no json block"
    return [json.loads(block) for block in raw]


@pytest.mark.parametrize("name,key", sorted(_CASES.items()))
def test_the_client_reference_block_uses_that_clients_wrapper_key(
    name: str, key: str
) -> None:
    blocks = _blocks(name)
    assert list(blocks[0]) == [key], (name, list(blocks[0]))


@pytest.mark.parametrize("name", sorted(_CASES))
def test_every_block_launches_the_server_inside_the_allowed_root(name: str) -> None:
    for block in _blocks(name):
        (wrapper,) = list(block)
        assert wrapper in _WRAPPERS, (name, wrapper)
        entry = block[wrapper]["chromamcp"]  # type: ignore[index]
        assert entry["args"] == ["-m", "chromamcp.server"]
        assert entry["command"].endswith("python")
        assert entry["env"]["CHROMAMCP_ALLOWED_ROOT"].startswith("/")


@pytest.mark.parametrize("name", sorted(_CASES))
def test_each_doc_names_its_config_file_and_the_variable(name: str) -> None:
    text = (_DOCS / name).read_text(encoding="utf-8")
    assert "Config file" in text
    assert "CHROMAMCP_ALLOWED_ROOT" in text
    assert "Exercised" in text


def test_cursor_records_that_its_schema_is_unverified() -> None:
    """Cursor's docs could not be read here, so the doc must say so, not imply it."""
    text = (_DOCS / "cursor.md").read_text(encoding="utf-8")
    assert "not checked in this unit" in text


def test_the_repository_has_no_readme_by_design() -> None:
    """``AGENTS.md`` §9: no README until M4; its absence is not an oversight."""
    found = sorted(
        path.relative_to(_ROOT).as_posix()
        for tree in (
            _ROOT,
            _ROOT / "src",
            _ROOT / "tests",
            _ROOT / "docs",
            _ROOT / "notes",
        )
        for path in tree.glob("README*")
    )
    assert found == [], f"a README appeared: {found}"
