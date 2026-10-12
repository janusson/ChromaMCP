"""The tolerance gate (closes the W4 plumbing).

``AGENTS.md`` §1.3: a tolerance is derived, not chosen, and it is recorded in
``TOLERANCES.md``.  ``M1-BRIEF.md`` §3 requires every value the panel returns to
carry the tolerance that applies to it, and §4 requires the provenance record's
per-metric block to carry it too.  This test ties the three together:

- the shipped mapping must equal the register recorded in ``TOLERANCES.md``;
- it must cover the whole panel (every id in ``FORMULA_IDS``);
- the panel must actually attach it, so a result never ships without its stated
  tolerance again.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from chromamcp.metrics import FORMULA_IDS, TOLERANCE, MetricResult, plate_number

_ROOT = Path(__file__).resolve().parents[1]
_TOLERANCES = _ROOT / "TOLERANCES.md"


def _recorded_tolerances() -> dict[str, float]:
    """metric id -> shipped tolerance, read from the ``TOLERANCES.md`` register.

    The register leads with the metric id in backticks (mirroring ``SOURCES.md``),
    so the first cell of each data row is the id and the last is the shipped value.
    """
    recorded: dict[str, float] = {}
    for line in _TOLERANCES.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        match = re.fullmatch(r"`([^`]+)`", cells[0])
        if match:
            recorded[match.group(1)] = float(cells[-1])
    return recorded


def test_the_recorded_register_is_parseable_and_non_empty() -> None:
    assert _recorded_tolerances(), "the TOLERANCES.md register could not be read"


def test_shipped_tolerances_match_the_recorded_register() -> None:
    recorded = _recorded_tolerances()
    assert recorded == TOLERANCE


def test_every_panel_metric_has_a_tolerance() -> None:
    assert set(TOLERANCE) == set(FORMULA_IDS)


def test_the_panel_attaches_the_shipped_tolerance() -> None:
    result = plate_number(apex_time=1.0, half_height_width=0.1)
    assert result.tolerance == TOLERANCE["plate_number"]


def test_a_nonpositive_tolerance_is_refused() -> None:
    with pytest.raises(ValueError):
        MetricResult(
            metric_id="plate_number",
            value=1.0,
            unit="dimensionless",
            formula_id="plate_number_half_height",
            tolerance=-1.0,
        )
