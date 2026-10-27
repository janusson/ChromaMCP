"""W4 tests — the ground-truth suite.

For each panel metric this compares the package's working-rate estimator (W2/W3)
against an **estimator-level expected value** computed by an independent route
(``tests.synthetic.measure``) on a dense trace, on a **noisy** fixture, at the
two working rates.  The tolerance is the derived, recorded one from
``TOLERANCES.md`` — never a value chosen to make the test pass.

It also runs the property tests ``M1-BRIEF.md`` §5.2.4 requires, which must hold
for any correct implementation.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from chromamcp.geometry import find_apex, five_percent_width, half_height_width
from chromamcp.metrics import (
    peak_area,
    peak_height,
    plate_number,
    resolution,
    symmetry_factor,
)
from tests.synthetic import fixtures
from tests.synthetic.derive_tolerances import Residual, experiment, report, residuals

_RATES = [fixtures.RATE_COARSE, fixtures.RATE_FINE]
_BASELINE = fixtures.BASELINE


def _relative(expected: float, actual: float) -> float:
    return abs(actual - expected) / abs(expected)


def _sharpness_metrics(
    trace: tuple[NDArray[np.float64], NDArray[np.float64]],
) -> dict[str, float]:
    """``N`` and the height, measured on *trace* with the package's own W2/W3."""
    time, intensity = trace
    apex = find_apex(time, intensity)
    width = half_height_width(time, intensity, baseline=_BASELINE, apex=apex)
    return {
        "N": plate_number(apex_time=apex.time, half_height_width=width.width).value,
        "height": peak_height(
            apex_intensity=apex.intensity, baseline_at_apex=0.0
        ).value,
    }


def _symmetry_at(time: NDArray[np.float64], intensity: NDArray[np.float64]) -> float:
    width = five_percent_width(time, intensity, baseline=_BASELINE)
    return symmetry_factor(
        width_at_5pct=width.width, front_distance_at_5pct=width.front_distance
    ).value


def _resolution_at(
    time: NDArray[np.float64], intensity: NDArray[np.float64], midpoint: float
) -> float:
    middle = int(np.searchsorted(time, midpoint))
    first = find_apex(time, intensity, left_index=0, right_index=middle - 1)
    second = find_apex(time, intensity, left_index=middle, right_index=len(time) - 1)
    width_1 = half_height_width(time, intensity, baseline=_BASELINE, apex=first)
    width_2 = half_height_width(time, intensity, baseline=_BASELINE, apex=second)
    return resolution(
        first_apex_time=first.time,
        first_half_height_width=width_1.width,
        second_apex_time=second.time,
        second_half_height_width=width_2.width,
    ).value


# --- full eight-seed, two-rate estimator disagreement experiment ------------
@pytest.mark.parametrize("step", _RATES)
@pytest.mark.parametrize("seed", fixtures.SEEDS)
def test_all_metrics_recover_independent_expectations(step: float, seed: int) -> None:
    """Expected equations do not call the production panel under test."""
    comparisons = residuals(step, seed)
    assert {row.metric_id for row in comparisons} == set(fixtures.TOLERANCE)
    for row in comparisons:
        assert row.relative <= fixtures.TOLERANCE[row.metric_id], row


def test_full_experiment_preserves_the_recorded_margin() -> None:
    rows = experiment()
    assert len(rows) == 2 * (8 + 1) * len(fixtures.TOLERANCE)
    for metric_id, reference in fixtures.TOLERANCE.items():
        noisy = [
            row for row in rows if row.metric_id == metric_id and row.seed is not None
        ]
        assert len(noisy) == 16
        if metric_id == "rsd_replicates":
            # Historical floor, not an output of the residual-times-margin recipe.
            assert max(row.relative for row in noisy) == 0.0
        else:
            assert 2 * max(row.relative for row in noisy) <= reference


def test_checked_evidence_is_the_full_experiment_replay() -> None:
    from pathlib import Path

    path = Path(__file__).parent / "synthetic" / "tolerance-evidence.md"
    assert path.is_file(), "the complete experiment needs its checked evidence artifact"
    assert path.read_text(encoding="utf-8") == report()


def test_relative_error_at_zero_expected_value_is_refused() -> None:
    with pytest.raises(ValueError, match="undefined at zero expected"):
        _ = Residual("peak_height", 0.002, 20261011, 0.0, 0.0).relative


# --- property tests (M1-BRIEF.md §5.2.4) ------------------------------------
def test_intensity_scaling_leaves_shape_metrics_unchanged() -> None:
    time, intensity = fixtures.single_gaussian(fixtures.RATE_FINE)
    scaled = _sharpness_metrics((time, intensity * 10.0))
    base = _sharpness_metrics((time, intensity))
    assert scaled["N"] == pytest.approx(base["N"], rel=1e-9)
    assert scaled["height"] == pytest.approx(10.0 * base["height"], rel=1e-9)

    time_d, intensity_d = fixtures.single_gaussian(fixtures.DENSE)
    base_area = peak_area(
        time_d,
        intensity_d,
        baseline=_BASELINE,
        left_index=0,
        right_index=len(time_d) - 1,
    ).value
    scaled_area = peak_area(
        time_d,
        intensity_d * 10.0,
        baseline=_BASELINE,
        left_index=0,
        right_index=len(time_d) - 1,
    ).value
    assert scaled_area == pytest.approx(10.0 * base_area, rel=1e-9)


def test_intensity_scaling_leaves_symmetry_factor_unchanged() -> None:
    time, intensity = fixtures.tailing(fixtures.RATE_FINE)
    assert _symmetry_at(time, intensity * 10.0) == pytest.approx(
        _symmetry_at(time, intensity), rel=1e-9
    )


def test_time_shift_moves_retention_time_but_not_shape_ratios() -> None:
    """A constant time offset moves tR but leaves the shape ratios unchanged.

    The plate number is **not** in this set: ``N = 5.54 (tR / w½)²`` contains the
    absolute retention time, so shifting the origin changes ``N``.  That
    diverges from ``M1-BRIEF.md`` §5.2.4, which lists ``N`` among the
    shift-invariant metrics.  Per ``AGENTS.md`` §10 it is raised as a finding,
    not silently resolved.  ``Rs`` and the symmetry factor are ratios of widths
    only, and are shift-invariant.
    """
    shift = 0.1
    time, intensity = fixtures.single_gaussian(fixtures.RATE_COARSE)
    apex = find_apex(time, intensity)
    assert find_apex(time + shift, intensity).time == pytest.approx(
        apex.time + shift, abs=1e-12
    )

    time_t, intensity_t = fixtures.tailing(fixtures.RATE_FINE)
    assert _symmetry_at(time_t + shift, intensity_t) == pytest.approx(
        _symmetry_at(time_t, intensity_t), rel=1e-9
    )

    midpoint = fixtures.separated_midpoint()
    time_p, intensity_p = fixtures.separated_pair(fixtures.RATE_FINE)
    assert _resolution_at(
        time_p + shift, intensity_p, midpoint + shift
    ) == pytest.approx(_resolution_at(time_p, intensity_p, midpoint), rel=1e-9)


def test_time_unit_scaling_leaves_plate_number_and_resolution_unchanged() -> None:
    time, intensity = fixtures.single_gaussian(fixtures.RATE_FINE)
    factor = 60.0
    base = _sharpness_metrics((time, intensity))
    rescaled = _sharpness_metrics((time * factor, intensity))
    assert rescaled["N"] == pytest.approx(base["N"], rel=1e-9)

    midpoint = fixtures.separated_midpoint()
    time_p, intensity_p = fixtures.separated_pair(fixtures.RATE_FINE)
    assert _resolution_at(
        time_p * factor, intensity_p, midpoint * factor
    ) == pytest.approx(_resolution_at(time_p, intensity_p, midpoint), rel=1e-9)


def test_plate_number_is_stable_across_the_two_sampling_rates() -> None:
    coarse = _sharpness_metrics(fixtures.single_gaussian(fixtures.RATE_COARSE))["N"]
    fine = _sharpness_metrics(fixtures.single_gaussian(fixtures.RATE_FINE))["N"]
    assert _relative(coarse, fine) <= fixtures.TOLERANCE["plate_number"]
