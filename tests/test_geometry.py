"""W2 tests — peak geometry against closed-form peaks.

Each fixture is a Gaussian (or a two-piece Gaussian) whose apex and widths are
known analytically, so the estimator can be checked against arithmetic rather
than against another run of itself.  The tolerances below are set by the grid
spacing, not chosen for comfort; the *derived* metric tolerances are W4's
evidence and are recorded in `TOLERANCES.md`, not here.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from chromamcp.errors import PeakGeometryError
from chromamcp.geometry import (
    Baseline,
    BaselineRule,
    find_apex,
    five_percent_width,
    half_height_width,
    resolve_baseline,
    width_at_height,
)

# A dense grid: dt = 0.0005 min.  At this spacing the linear-interpolation error
# on a crossing is ~1e-7 min, i.e. a relative error ~4e-7 on a 0.24 min width,
# so the relative tolerance below is comfortably above the discretisation error.
_STEP = 0.0005
_TIME: NDArray[np.float64] = np.arange(0.0, 2.0, _STEP)
_SIGMA = 0.1
_CENTER = 1.0
_HEIGHT = 1.0
_RTOL = 1e-5
_FWHM_FACTOR = 2.0 * np.sqrt(2.0 * np.log(2.0))  # 2.3548
_FIVE_PCT_FACTOR = 2.0 * np.sqrt(2.0 * np.log(20.0))  # 4.8955


def _gaussian(
    time: NDArray[np.float64],
    *,
    center: float = _CENTER,
    sigma: float = _SIGMA,
    height: float = _HEIGHT,
) -> NDArray[np.float64]:
    return height * np.exp(-((time - center) ** 2) / (2.0 * sigma**2))


def _two_piece(
    time: NDArray[np.float64],
    *,
    center: float,
    sigma_left: float,
    sigma_right: float,
    height: float,
) -> NDArray[np.float64]:
    sigma = np.where(time < center, sigma_left, sigma_right)
    return height * np.exp(-((time - center) ** 2) / (2.0 * sigma**2))


# --- apex -------------------------------------------------------------------
def test_find_apex_recovers_the_gaussian_center() -> None:
    apex = find_apex(_TIME, _gaussian(_TIME))
    assert apex.time == pytest.approx(_CENTER, abs=1e-6)
    assert apex.intensity == pytest.approx(_HEIGHT, abs=1e-6)


def test_apex_is_interpolated_between_samples() -> None:
    center = _CENTER + 0.5 * _STEP  # exactly halfway between two grid points
    apex = find_apex(_TIME, _gaussian(_TIME, center=center))
    assert apex.interpolated is True
    # closer to the true centre than either adjacent sample
    assert abs(apex.time - center) < 0.5 * _STEP


def test_apex_falls_back_to_the_sample_when_not_interpolable() -> None:
    short_time = np.array([0.0, 1.0])
    short_intensity = np.array([1.0, 2.0])
    apex = find_apex(short_time, short_intensity)
    assert apex.interpolated is False
    assert apex.index == 1
    assert apex.time == 1.0


def test_find_apex_within_a_window() -> None:
    time = _TIME
    intensity = _gaussian(time, center=0.5, sigma=0.05) + _gaussian(
        time, center=1.5, sigma=0.05
    )
    first = find_apex(time, intensity, left_index=0, right_index=1800)
    second = find_apex(time, intensity, left_index=2200, right_index=3999)
    assert first.time == pytest.approx(0.5, abs=1e-3)
    assert second.time == pytest.approx(1.5, abs=1e-3)


# --- widths against closed form ---------------------------------------------
def test_half_height_width_matches_the_gaussian() -> None:
    width = half_height_width(_TIME, _gaussian(_TIME), baseline=Baseline.constant(0.0))
    assert width.width == pytest.approx(_FWHM_FACTOR * _SIGMA, rel=_RTOL)
    assert width.fraction == 0.5


def test_five_percent_width_matches_the_gaussian() -> None:
    width = five_percent_width(_TIME, _gaussian(_TIME), baseline=Baseline.constant(0.0))
    assert width.width == pytest.approx(_FIVE_PCT_FACTOR * _SIGMA, rel=_RTOL)
    assert width.fraction == 0.05


def test_gaussian_width_is_symmetric() -> None:
    width = half_height_width(_TIME, _gaussian(_TIME), baseline=Baseline.constant(0.0))
    assert width.front_distance == pytest.approx(width.back_distance, rel=_RTOL)


def test_two_piece_gaussian_gives_asymmetric_widths() -> None:
    intensity = _two_piece(
        _TIME, center=_CENTER, sigma_left=0.08, sigma_right=0.15, height=1.0
    )
    width = half_height_width(_TIME, intensity, baseline=Baseline.constant(0.0))
    # The crossings are exact closed form; the apex-based distances are asserted
    # only for the sign of the asymmetry, because parabolic interpolation is
    # biased on a kinked (piecewise) peak.
    assert width.left_time == pytest.approx(
        _CENTER - 0.08 * _FWHM_FACTOR / 2.0, rel=1e-5
    )
    assert width.right_time == pytest.approx(
        _CENTER + 0.15 * _FWHM_FACTOR / 2.0, rel=1e-5
    )
    assert width.front_distance < width.back_distance


def test_width_is_invariant_to_intensity_scaling() -> None:
    base = half_height_width(_TIME, _gaussian(_TIME), baseline=Baseline.constant(0.0))
    scaled = half_height_width(
        _TIME, 10.0 * _gaussian(_TIME), baseline=Baseline.constant(0.0)
    )
    assert scaled.width == pytest.approx(base.width, rel=1e-9)


def test_flat_nonzero_baseline_does_not_change_the_width() -> None:
    trace = 5.0 + _gaussian(_TIME)
    zero = half_height_width(_TIME, _gaussian(_TIME), baseline=Baseline.constant(0.0))
    raised = half_height_width(_TIME, trace, baseline=Baseline.constant(5.0))
    assert raised.width == pytest.approx(zero.width, rel=_RTOL)


def test_width_at_an_arbitrary_fraction() -> None:
    # width at 25 % height for a Gaussian: 2*sigma*sqrt(2 ln 4)
    expected = 2.0 * _SIGMA * np.sqrt(2.0 * np.log(4.0))
    width = width_at_height(
        _TIME, _gaussian(_TIME), fraction=0.25, baseline=Baseline.constant(0.0)
    )
    assert width.width == pytest.approx(expected, rel=_RTOL)


# --- baseline ---------------------------------------------------------------
def test_baseline_through_evaluates_a_line() -> None:
    baseline = Baseline.through(0.0, 2.0, 4.0, 6.0)
    assert baseline.value(0.0) == pytest.approx(2.0)
    assert baseline.value(4.0) == pytest.approx(6.0)
    assert baseline.value(2.0) == pytest.approx(4.0)


def test_resolve_baseline_linear_from_anchors() -> None:
    time = np.array([0.0, 1.0, 2.0])
    intensity = np.array([1.0, 5.0, 3.0])
    baseline = resolve_baseline(
        BaselineRule.LINEAR, time, intensity, left_index=0, right_index=2
    )
    assert baseline.value(0.0) == pytest.approx(1.0)
    assert baseline.value(2.0) == pytest.approx(3.0)


def test_resolve_baseline_valley_drop_is_flat_at_the_valley() -> None:
    time = np.array([0.0, 1.0, 2.0])
    intensity = np.array([1.0, 0.4, 1.0])
    baseline = resolve_baseline(
        BaselineRule.VALLEY_DROP,
        time,
        intensity,
        left_index=0,
        right_index=2,
        valley_index=1,
    )
    assert baseline.value(0.0) == pytest.approx(0.4)
    assert baseline.value(2.0) == pytest.approx(0.4)


def test_resolve_baseline_tangent_skim_is_refused() -> None:
    time = np.array([0.0, 1.0])
    intensity = np.array([1.0, 1.0])
    with pytest.raises(PeakGeometryError) as excinfo:
        resolve_baseline(
            BaselineRule.TANGENT_SKIM, time, intensity, left_index=0, right_index=1
        )
    assert "TANGENT_SKIM" in str(excinfo.value)


def test_valley_drop_without_a_valley_is_refused() -> None:
    time = np.array([0.0, 1.0])
    intensity = np.array([1.0, 1.0])
    with pytest.raises(PeakGeometryError):
        resolve_baseline(
            BaselineRule.VALLEY_DROP, time, intensity, left_index=0, right_index=1
        )


# --- refusals ---------------------------------------------------------------
def test_empty_trace_is_refused() -> None:
    with pytest.raises(PeakGeometryError):
        find_apex(np.array([]), np.array([]))


def test_non_increasing_time_is_refused() -> None:
    with pytest.raises(PeakGeometryError):
        find_apex(np.array([0.0, 1.0, 1.0]), np.array([1.0, 2.0, 3.0]))


def test_nan_intensity_is_refused() -> None:
    with pytest.raises(PeakGeometryError):
        find_apex(np.array([0.0, 1.0, 2.0]), np.array([1.0, np.nan, 3.0]))


def test_fraction_outside_open_unit_interval_is_refused() -> None:
    with pytest.raises(PeakGeometryError):
        width_at_height(
            _TIME, _gaussian(_TIME), fraction=1.0, baseline=Baseline.constant(0.0)
        )


def test_apex_not_above_baseline_is_refused() -> None:
    flat = np.array([3.0, 3.0, 3.0])
    with pytest.raises(PeakGeometryError):
        width_at_height(
            np.array([0.0, 1.0, 2.0]),
            flat,
            fraction=0.5,
            baseline=Baseline.constant(3.0),
        )


def test_width_not_bracketed_is_refused() -> None:
    # A monotonic ramp: the level at 5 % of "height" is never reached on the
    # leading side.
    time = np.arange(0.0, 1.0, 0.01)
    ramp = time.copy()
    with pytest.raises(PeakGeometryError):
        width_at_height(time, ramp, fraction=0.05, baseline=Baseline.constant(0.0))
