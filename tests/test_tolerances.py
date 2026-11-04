"""Historical fixture reference bounds and explicitly unevaluated applicability.

The mapping must match TOLERANCES.md. Production results carry the reference
bound as separate fixture evidence, with no applied bound on a caller trace.
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


def test_fixture_bound_is_reference_metadata_not_an_applied_bound() -> None:
    result = plate_number(apex_time=1.0, half_height_width=0.1)
    metadata = result.estimator_fixture_tolerance
    assert metadata is not None
    assert metadata.reference_bound == TOLERANCE["plate_number"]
    assert metadata.basis == "relative"
    assert metadata.domain_id == "synthetic-w4-w12-v1"
    assert metadata.applicability == "not-evaluated"
    assert metadata.applied_bound is None


@pytest.mark.parametrize("value", [0.0, 1e-300])
def test_zero_and_small_results_do_not_acquire_an_applied_relative_bound(
    value: float,
) -> None:
    from chromamcp.metrics import peak_height

    result = peak_height(apex_intensity=value, baseline_at_apex=0.0)
    metadata = result.estimator_fixture_tolerance
    assert metadata is not None
    assert metadata.zero_expected_policy == (
        "relative-error-undefined-at-zero-no-absolute-floor"
    )
    assert metadata.applicability == "not-evaluated"
    assert metadata.applied_bound is None


def test_the_rsd_floor_is_not_described_as_derived() -> None:
    from chromamcp.metrics import rsd_replicates

    result = rsd_replicates([1.0, 1.0, 1.0])
    metadata = result.estimator_fixture_tolerance
    assert metadata is not None
    assert metadata.reference_bound == 1e-12
    assert metadata.derivation_status == "historical-floor-not-derived"
    assert metadata.applied_bound is None


@pytest.mark.parametrize(
    ("metric_id", "bound"), [("plate_number", 0.5), ("caller_metric", 0.02)]
)
def test_custom_constructor_bounds_do_not_inherit_the_fixture_domain(
    metric_id: str, bound: float
) -> None:
    result = MetricResult(
        metric_id=metric_id,
        value=1.0,
        unit="dimensionless",
        formula_id="caller_formula",
        tolerance=bound,
    )
    assert result.estimator_fixture_tolerance is None
