"""W3 tests — the suitability panel.

Each metric is checked against a hand-computed value, and the identifiers a
reviewer needs (unit, formula id, and the derived tolerance from W4) are asserted
alongside.  The refusals are tested too: a bad input is an explicit error, never
a silently degraded number.
"""

from __future__ import annotations

import numpy as np
import pytest

from chromamcp.errors import MetricInputError
from chromamcp.geometry import Baseline
from chromamcp.metrics import (
    FORMULA_IDS,
    TOLERANCE,
    capacity_factor,
    peak_area,
    peak_height,
    peak_to_valley,
    plate_number,
    resolution,
    rsd_replicates,
    selectivity,
    signal_to_noise,
    symmetry_factor,
)


# --- values -----------------------------------------------------------------
def test_plate_number_value_and_identifiers() -> None:
    result = plate_number(apex_time=1.0, half_height_width=0.1)
    assert result.value == pytest.approx(554.0)  # 5.54 * (1.0 / 0.1) ** 2
    assert result.metric_id == "plate_number"
    assert result.unit == "dimensionless"
    assert result.formula_id == FORMULA_IDS["plate_number"]
    assert result.tolerance == TOLERANCE["plate_number"]


def test_resolution_value() -> None:
    result = resolution(
        first_apex_time=1.0,
        first_half_height_width=0.1,
        second_apex_time=1.5,
        second_half_height_width=0.1,
    )
    assert result.value == pytest.approx(2.95)  # 1.18 * 0.5 / 0.2


def test_resolution_uses_the_harmonised_coefficient() -> None:
    """``Rs = 1.18 (tR2 − tR1) / (w½1 + w½2)``, worked by hand from the citation.

    The expected value is arithmetic on the cited equation — not a call to this
    package — so it cannot inherit the implementation's constant.  A pair the
    harmonised definition puts at ``Rs = 1.18`` is the region where labs set
    ``Rs > 1.5``; reporting ``2.0`` there (the base-width constant applied to
    half-height widths) is 1.695× high and not comparable with vendor software.
    """
    result = resolution(
        first_apex_time=1.0,
        first_half_height_width=0.5,
        second_apex_time=2.0,
        second_half_height_width=0.5,
    )
    assert result.value == pytest.approx(1.18)


def test_symmetry_factor_is_one_for_a_symmetric_peak() -> None:
    result = symmetry_factor(width_at_5pct=0.2, front_distance_at_5pct=0.1)
    assert result.value == pytest.approx(1.0)


def test_symmetry_factor_exceeds_one_for_a_tailing_peak() -> None:
    result = symmetry_factor(width_at_5pct=0.2, front_distance_at_5pct=0.08)
    assert result.value == pytest.approx(1.25)


def test_capacity_factor_value() -> None:
    result = capacity_factor(apex_time=5.0, void_time=1.0)
    assert result.value == pytest.approx(4.0)


def test_selectivity_value() -> None:
    result = selectivity(first_apex_time=5.0, second_apex_time=7.0, void_time=1.0)
    assert result.value == pytest.approx(1.5)  # 6 / 4


def test_signal_to_noise_value() -> None:
    blank = np.array([5.0, 6.0, 5.0, 7.0, 5.0])  # peak-to-peak = 2
    result = signal_to_noise(signal_height=10.0, blank_intensity=blank)
    assert result.value == pytest.approx(10.0)  # 2 * 10 / 2


def test_peak_to_valley_value() -> None:
    result = peak_to_valley(
        first_apex_intensity=100.0,
        second_apex_intensity=80.0,
        valley_intensity=20.0,
        baseline_intensity=0.0,
    )
    assert result.value == pytest.approx(4.0)  # smaller height 80 / valley 20


def test_peak_height_value_and_unit() -> None:
    result = peak_height(apex_intensity=100.0, baseline_at_apex=10.0)
    assert result.value == pytest.approx(90.0)
    assert result.unit == "counts"


def test_peak_area_trapezoid_over_baseline() -> None:
    time = np.array([0.0, 1.0, 2.0])
    intensity = np.array([1.0, 3.0, 1.0])
    result = peak_area(
        time,
        intensity,
        baseline=Baseline.constant(1.0),
        left_index=0,
        right_index=2,
    )
    assert result.value == pytest.approx(2.0)  # two triangles of area 1
    assert result.unit == "counts·min"


def test_rsd_replicates_sample_standard_deviation() -> None:
    result = rsd_replicates([1.0, 2.0, 3.0, 4.0, 5.0])
    # sample sd 1.5811, mean 3 -> 52.7046 %
    assert result.value == pytest.approx(52.7046, rel=1e-4)
    assert result.unit == "%"


def test_rsd_replicates_of_identical_values_is_zero() -> None:
    assert rsd_replicates([10.0, 10.0, 10.0]).value == pytest.approx(0.0)


def test_every_metric_carries_a_registered_formula_id() -> None:
    results = [
        plate_number(apex_time=1.0, half_height_width=0.1),
        resolution(
            first_apex_time=1.0,
            first_half_height_width=0.1,
            second_apex_time=1.5,
            second_half_height_width=0.1,
        ),
        symmetry_factor(width_at_5pct=0.2, front_distance_at_5pct=0.1),
        capacity_factor(apex_time=5.0, void_time=1.0),
        selectivity(first_apex_time=5.0, second_apex_time=7.0, void_time=1.0),
        signal_to_noise(signal_height=10.0, blank_intensity=np.array([1.0, 2.0])),
        peak_to_valley(
            first_apex_intensity=100.0,
            second_apex_intensity=80.0,
            valley_intensity=20.0,
            baseline_intensity=0.0,
        ),
        peak_height(apex_intensity=100.0, baseline_at_apex=10.0),
        peak_area(
            np.array([0.0, 1.0]),
            np.array([0.0, 1.0]),
            baseline=Baseline.constant(0.0),
            left_index=0,
            right_index=1,
        ),
        rsd_replicates([1.0, 2.0]),
    ]
    for result in results:
        assert result.formula_id in set(FORMULA_IDS.values())
        assert result.tolerance == TOLERANCE[result.metric_id]


# --- refusals ---------------------------------------------------------------
def test_plate_number_rejects_a_nonpositive_width() -> None:
    with pytest.raises(MetricInputError):
        plate_number(apex_time=1.0, half_height_width=0.0)


def test_resolution_rejects_reversed_order() -> None:
    with pytest.raises(MetricInputError):
        resolution(
            first_apex_time=1.5,
            first_half_height_width=0.1,
            second_apex_time=1.0,
            second_half_height_width=0.1,
        )


def test_symmetry_factor_rejects_front_longer_than_width() -> None:
    with pytest.raises(MetricInputError):
        symmetry_factor(width_at_5pct=0.1, front_distance_at_5pct=0.2)


def test_capacity_factor_rejects_apex_before_void() -> None:
    with pytest.raises(MetricInputError):
        capacity_factor(apex_time=1.0, void_time=1.0)


def test_selectivity_rejects_first_peak_before_void() -> None:
    with pytest.raises(MetricInputError):
        selectivity(first_apex_time=1.0, second_apex_time=2.0, void_time=1.0)


def test_signal_to_noise_rejects_a_noiseless_blank() -> None:
    with pytest.raises(MetricInputError):
        signal_to_noise(signal_height=10.0, blank_intensity=np.array([3.0, 3.0]))


def test_peak_to_valley_rejects_a_valley_at_the_baseline() -> None:
    with pytest.raises(MetricInputError):
        peak_to_valley(
            first_apex_intensity=100.0,
            second_apex_intensity=80.0,
            valley_intensity=0.0,
            baseline_intensity=0.0,
        )


def test_peak_area_rejects_an_inverted_window() -> None:
    with pytest.raises(MetricInputError):
        peak_area(
            np.array([0.0, 1.0, 2.0]),
            np.array([0.0, 1.0, 0.0]),
            baseline=Baseline.constant(0.0),
            left_index=2,
            right_index=0,
        )


def test_rsd_replicates_needs_at_least_two_values() -> None:
    with pytest.raises(MetricInputError):
        rsd_replicates([5.0])


def test_rsd_replicates_rejects_a_nan() -> None:
    with pytest.raises(MetricInputError):
        rsd_replicates([1.0, float("nan")])
