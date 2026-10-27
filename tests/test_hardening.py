"""W7 tests — the mechanical checks the M1 exit gate names.

Three invariants ``M1-BRIEF.md`` §8 requires, checked rather than asserted in
prose: the tree carries no banned vocabulary; the compute path imports no MCP
SDK, network client, LLM or vendor parser; and the provenance record carries
every field §4 lists.
"""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

from chromamcp.metrics import plate_number
from chromamcp.provenance import MetricRecord, build_record, serialise
from tests.guards import BANNED_WORDS, FORBIDDEN_EXACT, FORBIDDEN_TOP_LEVEL

_ROOT = Path(__file__).resolve().parents[1]

#: Text the vocabulary check reads.  ``AGENTS.md`` is excluded because it is the
#: document that names the banned words, and ``notes/`` because it quotes examples
#: of their misuse; both are allowed to contain them.
_VOCABULARY_TARGETS = (
    _ROOT / "SOURCES.md",
    _ROOT / "TOLERANCES.md",
    *sorted((_ROOT / "src").rglob("*.py")),
    *sorted((_ROOT / "tests").rglob("*.py")),
)

_RECORD_FIELDS = (
    "input_file",
    "reader",
    "parameters",
    "library_versions",
    "criteria",
    "metrics",
    "timestamp_utc",
    "timestamp_note",
    "measurement_uncertainty",
)


def test_no_banned_vocabulary_in_the_tree() -> None:
    offenders: list[str] = []
    for path in _VOCABULARY_TARGETS:
        text = path.read_text(encoding="utf-8").lower()
        for word in BANNED_WORDS:
            if word in text:
                offenders.append(f"{path.relative_to(_ROOT)}: {word}")
    assert offenders == [], f"banned vocabulary found: {offenders}"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def _compute_path_files() -> list[Path]:
    """The compute path: everything under ``src/chromamcp`` except the server.

    The server (W8) is the one sanctioned ``mcp`` importer; the compute
    subpackages must stay free of the SDK, network clients, LLM clients and
    vendor parsers (``AGENTS.md`` §3).
    """
    package = _ROOT / "src" / "chromamcp"
    files = list(package.glob("*.py"))
    for name in ("io", "geometry", "metrics", "criteria", "provenance"):
        files.extend((package / name).rglob("*.py"))
    return sorted(files)


def test_compute_path_imports_nothing_forbidden() -> None:
    offenders: list[str] = []
    for path in _compute_path_files():
        for module in _imported_modules(path):
            top = module.split(".")[0]
            if top in FORBIDDEN_TOP_LEVEL or module in FORBIDDEN_EXACT:
                offenders.append(f"{path.relative_to(_ROOT)}: {module}")
    assert offenders == [], f"forbidden imports in the compute path: {offenders}"


def test_the_mcp_sdk_is_imported_only_by_the_server_package() -> None:
    importers = [
        path.relative_to(_ROOT).as_posix()
        for path in sorted((_ROOT / "src").rglob("*.py"))
        if any(module.split(".")[0] == "mcp" for module in _imported_modules(path))
    ]
    assert importers == ["src/chromamcp/server/server.py"], (
        f"only the server may import the mcp SDK, but found: {importers}"
    )


def test_provenance_record_covers_the_required_fields(tmp_path: Path) -> None:
    path = tmp_path / "chromatogram.mzML"
    path.write_bytes(b"synthetic fixture")
    record = build_record(
        input_path=path,
        parameters={"baseline_rule": "linear"},
        metrics=[
            MetricRecord.from_result(plate_number(apex_time=1.0, half_height_width=0.1))
        ],
        timestamp=datetime(2026, 10, 11, tzinfo=UTC),
    )
    data = json.loads(serialise(record))
    for field in _RECORD_FIELDS:
        assert field in data, f"provenance record is missing '{field}'"
    assert "sha256" in data["input_file"]
    assert {
        "metric_id",
        "value",
        "unit",
        "formula_id",
        "estimator_fixture_tolerance",
        "verdict",
    } <= set(data["metrics"][0])
