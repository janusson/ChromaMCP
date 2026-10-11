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
from tests.synthetic import fixtures
from tests.synthetic.measure import independent_apex, independent_width

_RATES = [fixtures.RATE_COARSE, fixtures.RATE_FINE]
_BASELINE = fixtures.BASELINE
_SEED = fixtures.SEEDS[0]


def _relative(expected: float, actual: float) -> float:
    return abs(actual - expected) / abs(expected)


def _dense_single() -> tuple[float, float, float, float, float]:
    """Dense route on the single Gaussian: ``(apex_t, apex_y, w_half, w_5, front_5)``."""
    time, intensity = fixtures.single_gaussian(fixtures.DENSE)
    apex_t, apex_y = independent_apex(time, intensity)
    left_h, right_h, _ = independent_width(
        time, intensity, fraction=0.5, apex_time=apex_t, apex_intensity=apex_y
    )
    left_5, right_5, front_5 = independent_width(
        time, intensity, fraction=0.05, apex_time=apex_t, apex_intensity=apex_y
    )
    return apex_t, apex_y, right_h - left_h, right_5 - left_5, front_5


def _dense_pair(
    trace: tuple[NDArray[np.float64], NDArray[np.float64]], midpoint: float
) -> tuple[tuple[float, float], tuple[float, float], float, float]:
    """Dense route on a pair: apexes and half-height widths for both peaks."""
    time, intensity = trace
    middle = int(np.searchsorted(time, midpoint))
    first = independent_apex(time[:middle], intensity[:middle])
    second = independent_apex(time[middle:], intensity[middle:])
    left_1, right_1, _ = independent_width(
        time[:middle],
        intensity[:middle],
        fraction=0.5,
        apex_time=first[0],
        apex_intensity=first[1],
    )
    left_2, right_2, _ = independent_width(
        time[middle:],
        intensity[middle:],
        fraction=0.5,
        apex_time=second[0],
        apex_intensity=second[1],
    )
    return first, second, right_1 - left_1, right_2 - left_2


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


# --- metric recovery: noisy fixture, two rates ------------------------------
@pytest.mark.parametrize("step", _RATES)
def test_plate_number_recovers_its_expected_value(step: float) -> None:
    apex_t, _apex_y, width_half, _, _ = _dense_single()
    expected = plate_number(apex_time=apex_t, half_height_width=width_half).value
    time, intensity = fixtures.single_gaussian(step, noisy=True, seed=_SEED)
    apex = find_apex(time, intensity)
    width = half_height_width(time, intensity, baseline=_BASELINE, apex=apex)
    actual = plate_number(apex_time=apex.time, half_height_width=width.width).value
    assert _relative(expected, actual) <= fixtures.TOLERANCE["plate_number"]


@pytest.mark.parametrize("step", _RATES)
def test_resolution_recovers_its_expected_value(step: float) -> None:
    midpoint = fixtures.separated_midpoint()
    dense = fixtures.separated_pair(fixtures.DENSE)
    first, second, width_1, width_2 = _dense_pair(dense, midpoint)
    expected = resolution(
        first_apex_time=first[0],
        first_half_height_width=width_1,
        second_apex_time=second[0],
        second_half_height_width=width_2,
    ).value
    time, intensity = fixtures.separated_pair(step, noisy=True, seed=_SEED)
    middle = int(np.searchsorted(time, midpoint))
    apex_1 = find_apex(time, intensity, left_index=0, right_index=middle - 1)
    apex_2 = find_apex(time, intensity, left_index=middle, right_index=len(time) - 1)
    w_1 = half_height_width(time, intensity, baseline=_BASELINE, apex=apex_1)
    w_2 = half_height_width(time, intensity, baseline=_BASELINE, apex=apex_2)
    actual = resolution(
        first_apex_time=apex_1.time,
        first_half_height_width=w_1.width,
        second_apex_time=apex_2.time,
        second_half_height_width=w_2.width,
    ).value
    assert _relative(expected, actual) <= fixtures.TOLERANCE["resolution"]


@pytest.mark.parametrize("step", _RATES)
def test_symmetry_factor_recovers_its_expected_value(step: float) -> None:
    time_d, intensity_d = fixtures.tailing(fixtures.DENSE)
    apex_t, apex_y = independent_apex(time_d, intensity_d)
    left_5, right_5, front_5 = independent_width(
        time_d, intensity_d, fraction=0.05, apex_time=apex_t, apex_intensity=apex_y
    )
    expected = symmetry_factor(
        width_at_5pct=right_5 - left_5, front_distance_at_5pct=front_5
    ).value
    time, intensity = fixtures.tailing(step, noisy=True, seed=_SEED)
    apex = find_apex(time, intensity)
    width = five_percent_width(time, intensity, baseline=_BASELINE, apex=apex)
    actual = symmetry_factor(
        width_at_5pct=width.width, front_distance_at_5pct=width.front_distance
    ).value
    assert _relative(expected, actual) <= fixtures.TOLERANCE["symmetry_factor"]


@pytest.mark.parametrize("step", _RATES)
def test_capacity_factor_recovers_its_expected_value(step: float) -> None:
    apex_t, _, _, _, _ = _dense_single()
    expected = capacity_factor(apex_time=apex_t, void_time=fixtures.VOID_TIME).value
    time, intensity = fixtures.single_gaussian(step, noisy=True, seed=_SEED)
    apex = find_apex(time, intensity)
    actual = capacity_factor(apex_time=apex.time, void_time=fixtures.VOID_TIME).value
    assert _relative(expected, actual) <= fixtures.TOLERANCE["capacity_factor"]


@pytest.mark.parametrize("step", _RATES)
def test_selectivity_recovers_its_expected_value(step: float) -> None:
    midpoint = fixtures.separated_midpoint()
    first, second, _, _ = _dense_pair(fixtures.separated_pair(fixtures.DENSE), midpoint)
    expected = selectivity(
        first_apex_time=first[0],
        second_apex_time=second[0],
        void_time=fixtures.VOID_TIME,
    ).value
    time, intensity = fixtures.separated_pair(step, noisy=True, seed=_SEED)
    middle = int(np.searchsorted(time, midpoint))
    apex_1 = find_apex(time, intensity, left_index=0, right_index=middle - 1)
    apex_2 = find_apex(time, intensity, left_index=middle, right_index=len(time) - 1)
    actual = selectivity(
        first_apex_time=apex_1.time,
        second_apex_time=apex_2.time,
        void_time=fixtures.VOID_TIME,
    ).value
    assert _relative(expected, actual) <= fixtures.TOLERANCE["selectivity"]


@pytest.mark.parametrize("step", _RATES)
def test_peak_to_valley_recovers_its_expected_value(step: float) -> None:
    midpoint = fixtures.overlapped_midpoint()
    time_d, intensity_d = fixtures.overlapped_pair(fixtures.DENSE)
    middle_d = int(np.searchsorted(time_d, midpoint))
    first = independent_apex(time_d[:middle_d], intensity_d[:middle_d])
    second = independent_apex(time_d[middle_d:], intensity_d[middle_d:])
    valley_d = float(intensity_d[middle_d - 1 : middle_d + 2].min())
    expected = peak_to_valley(
        first_apex_intensity=first[1],
        second_apex_intensity=second[1],
        valley_intensity=valley_d,
        baseline_intensity=0.0,
    ).value
    time, intensity = fixtures.overlapped_pair(step, noisy=True, seed=_SEED)
    middle = int(np.searchsorted(time, midpoint))
    apex_1 = find_apex(time, intensity, left_index=0, right_index=middle - 1)
    apex_2 = find_apex(time, intensity, left_index=middle, right_index=len(time) - 1)
    valley = float(intensity[apex_1.index : apex_2.index + 1].min())
    actual = peak_to_valley(
        first_apex_intensity=apex_1.intensity,
        second_apex_intensity=apex_2.intensity,
        valley_intensity=valley,
        baseline_intensity=0.0,
    ).value
    assert _relative(expected, actual) <= fixtures.TOLERANCE["peak_to_valley"]


@pytest.mark.parametrize("step", _RATES)
def test_signal_to_noise_recovers_its_expected_value(step: float) -> None:
    _apex_t, apex_y, width_half, _, _ = _dense_single()
    blank = fixtures.noise_region(width_half, step)
    expected = signal_to_noise(signal_height=apex_y, blank_intensity=blank).value
    time, intensity = fixtures.single_gaussian(step, noisy=True, seed=_SEED)
    apex = find_apex(time, intensity)
    actual = signal_to_noise(signal_height=apex.intensity, blank_intensity=blank).value
    assert _relative(expected, actual) <= fixtures.TOLERANCE["signal_to_noise"]


@pytest.mark.parametrize("step", _RATES)
def test_peak_area_recovers_its_expected_value(step: float) -> None:
    time_d, intensity_d = fixtures.single_gaussian(fixtures.DENSE)
    expected = peak_area(
        time_d,
        intensity_d,
        baseline=_BASELINE,
        left_index=0,
        right_index=len(time_d) - 1,
    ).value
    time, intensity = fixtures.single_gaussian(step, noisy=True, seed=_SEED)
    actual = peak_area(
        time,
        intensity,
        baseline=_BASELINE,
        left_index=0,
        right_index=len(time) - 1,
    ).value
    assert _relative(expected, actual) <= fixtures.TOLERANCE["peak_area"]


@pytest.mark.parametrize("step", _RATES)
def test_peak_height_recovers_its_expected_value(step: float) -> None:
    _, apex_y, _, _, _ = _dense_single()
    expected = peak_height(apex_intensity=apex_y, baseline_at_apex=0.0).value
    time, intensity = fixtures.single_gaussian(step, noisy=True, seed=_SEED)
    apex = find_apex(time, intensity)
    actual = peak_height(apex_intensity=apex.intensity, baseline_at_apex=0.0).value
    assert _relative(expected, actual) <= fixtures.TOLERANCE["peak_height"]


def test_rsd_replicates_is_exact() -> None:
    replicates = [1.0, 2.0, 3.0, 4.0, 5.0]
    expected = 100.0 * float(np.std(replicates, ddof=1)) / float(np.mean(replicates))
    actual = rsd_replicates(replicates).value
    assert _relative(expected, actual) <= fixtures.TOLERANCE["rsd_replicates"]


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
