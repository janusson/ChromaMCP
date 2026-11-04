"""Estimator-level expectations by an independent route (W4).

``M1-BRIEF.md`` §5.2.2 requires the expected value to be computed **at the
estimator level, by a different route from the one under test**: measure the
apex and the widths at the defined heights on a *dense* trace, and combine them
with the definition's own equation.  Comparing the package's working-rate
estimator against a value taken from the generating parameters instead is the
defect §5.1 describes, so nothing here reads a generating parameter — every
number is measured from a sampled trace.

How this route differs from the package's (W2):

- **Resolution.**  These helpers run on a trace ~100× denser than the working
  rate, so their residual is orders of magnitude below the package's.
- **Apex.**  A parabola is fitted to the three dense samples around the maximum
  by a least-squares ``polyfit``/``polyval``, where W2 solves the same vertex in
  divided-difference form — a different derivation.
- **Crossings.**  The height crossings are found by bisection on the dense
  piecewise-linear interpolant, where W2 takes the first bracketing pair and
  interpolates directly once — a different algorithm.

The route still applies the *same definitions* (parabolic apex, half-height and
5 %-height widths above a baseline); only the numerics differ, which is the
point: a definition is shared, a numerical route is not.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

__all__ = ["independent_apex", "independent_width"]

_BISECTION_STEPS = 100


def independent_apex(
    time: NDArray[np.float64], intensity: NDArray[np.float64]
) -> tuple[float, float]:
    """Return ``(apex_time, apex_intensity)`` measured on a dense trace."""
    index = int(np.argmax(intensity))
    n = int(time.size)
    if 0 < index < n - 1:
        x = time[index - 1 : index + 2]
        y = intensity[index - 1 : index + 2]
        a, b, c = np.polyfit(x, y, 2)
        if a < 0.0:
            vertex = -b / (2.0 * a)
            if float(x[0]) < vertex < float(x[2]):
                return float(vertex), float(np.polyval((a, b, c), vertex))
    return float(time[index]), float(intensity[index])


def independent_width(
    time: NDArray[np.float64],
    intensity: NDArray[np.float64],
    *,
    fraction: float,
    apex_time: float,
    apex_intensity: float,
    baseline_level: float = 0.0,
) -> tuple[float, float, float]:
    """Return ``(left_time, right_time, front_distance)`` at *fraction* of height.

    The height is ``apex_intensity - baseline_level`` and the level is that
    fraction of the way from the baseline to the apex; both crossings are found
    by bisection on the dense interpolant.
    """
    level = baseline_level + fraction * (apex_intensity - baseline_level)
    apex_index = int(np.argmin(np.abs(time - apex_time)))
    left = _root(time, intensity, float(time[0]), float(time[apex_index]), level)
    right = _root(time, intensity, float(time[apex_index]), float(time[-1]), level)
    return left, right, apex_time - left


def _root(
    time: NDArray[np.float64],
    intensity: NDArray[np.float64],
    low: float,
    high: float,
    level: float,
) -> float:
    """Bisect the dense piecewise-linear interpolant for a crossing of *level*."""
    low_value = float(np.interp(low, time, intensity)) - level
    high_value = float(np.interp(high, time, intensity)) - level
    if low_value == 0.0:
        return low
    if high_value == 0.0:
        return high
    if low_value * high_value > 0.0:
        raise ValueError("independent_width: the level is not bracketed.")
    for _ in range(_BISECTION_STEPS):
        middle = 0.5 * (low + high)
        middle_value = float(np.interp(middle, time, intensity)) - level
        if middle_value == 0.0:
            return middle
        if low_value * middle_value < 0.0:
            high = middle
        else:
            low = middle
            low_value = middle_value
    return 0.5 * (low + high)
