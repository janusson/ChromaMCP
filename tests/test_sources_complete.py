"""The citation gate (W3).

``AGENTS.md`` §1.1: every metric carries a formula id whose row exists in
``SOURCES.md``.  A formula id in code with no row is a bug, not an incomplete
feature, so this test fails when one appears.
"""

from __future__ import annotations

import re
from pathlib import Path

from chromamcp.metrics import FORMULA_IDS

_ROOT = Path(__file__).resolve().parents[1]
_SOURCES = _ROOT / "SOURCES.md"
_METRICS_SRC = _ROOT / "src" / "chromamcp" / "metrics"


def _sources_formula_ids() -> set[str]:
    """The ids in the first (backticked) column of the ``SOURCES.md`` tables."""
    ids: set[str] = set()
    for line in _SOURCES.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        match = re.fullmatch(r"`([^`]+)`", cells[0])
        if match:
            ids.add(match.group(1))
    return ids


def _code_formula_ids() -> set[str]:
    """Every formula id the code can emit: the registry plus any literal."""
    ids: set[str] = set(FORMULA_IDS.values())
    for path in sorted(_METRICS_SRC.glob("*.py")):
        ids.update(
            re.findall(r'formula_id="([^"]+)"', path.read_text(encoding="utf-8"))
        )
    return ids


def test_every_code_formula_id_has_a_sources_row() -> None:
    missing = sorted(_code_formula_ids() - _sources_formula_ids())
    assert missing == [], f"formula ids with no SOURCES.md row: {missing}"


def test_registry_covers_the_whole_panel() -> None:
    assert set(FORMULA_IDS) == {
        "plate_number",
        "resolution",
        "symmetry_factor",
        "capacity_factor",
        "selectivity",
        "signal_to_noise",
        "peak_to_valley",
        "peak_area",
        "peak_height",
        "rsd_replicates",
    }
