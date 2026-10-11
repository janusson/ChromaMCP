"""Peak geometry: apex and width-at-height (W2).

The panel metrics are **estimators defined on measured widths at defined
heights**, so this module fixes the two measurements they rest on — where the
apex is, and how wide the peak is at a fraction of its height — and states the
convention each one follows.

**Apex.**  :func:`find_apex` reports the peak maximum with **three-point
parabolic interpolation** around the discrete maximum, giving a sub-sample apex
time.  It rejects the **discrete (sample-index) apex**, which snaps the earliest
retention time to the sampling grid; the interpolated apex is the value the
panel's half-height measurements are defined against.

**Width at height.**  :func:`width_at_height` measures, on each side of the
apex, the **first crossing** of a level that lies ``fraction`` of the way from
the baseline to the peak height, using **linear interpolation** between the two
samples that bracket that crossing.  It rejects two other readings: the
**nearest-sample width**, which reports a width quantised to the sampling grid
and overstates a narrow peak, and the **last crossing** (or an integrated
boundary), which a noisy tail or a following peak can push outward.  The width
is measured relative to an explicit :class:`~chromamcp.geometry.baseline.Baseline`
— never against zero by default.

Both functions are pure: they take arrays and return values, with no I/O and no
module state.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from chromamcp.errors import PeakGeometryError
from chromamcp.geometry.baseline import Baseline

__all__ = [
    "Apex",
    "PeakWidth",
    "find_apex",
    "five_percent_width",
    "half_height_width",
    "width_at_height",
]


@dataclass(frozen=True, slots=True)
class Apex:
    """A peak maximum.

    ``index`` is the discrete sample maximum; ``time`` and ``intensity`` are the
    reported apex, which are the interpolated values when ``interpolated`` is
    ``True`` and the sample values otherwise.
    """

    index: int
    time: float
    intensity: float
    interpolated: bool


@dataclass(frozen=True, slots=True)
class PeakWidth:
    """A peak's width at a fraction of its height above the baseline.

    ``height`` is the peak height above the baseline at the apex (so
    ``fraction`` of it is the measured level).  ``left_time`` and ``right_time``
    are the crossings, and ``front_distance`` / ``back_distance`` are the apex's
    distances to them — the two quantities the symmetry factor is built from.
    """

    fraction: float
    apex_time: float
    height: float
    left_time: float
    right_time: float

    @property
    def width(self) -> float:
        """The width: ``right_time - left_time``."""
        return self.right_time - self.left_time

    @property
    def front_distance(self) -> float:
        """Distance from the leading crossing to the apex."""
        return self.apex_time - self.left_time

    @property
    def back_distance(self) -> float:
        """Distance from the apex to the trailing crossing."""
        return self.right_time - self.apex_time


def _validate_trace(time: NDArray[np.float64], intensity: NDArray[np.float64]) -> None:
    """Refuse a trace that has no defined geometry, rather than guess one.

    A missing intensity is ``NaN`` by convention (``AGENTS.md`` §1.6), and a
    gap has no defined apex or width, so a non-finite trace is refused here
    rather than silently skipped.
    """
    if time.ndim != 1 or intensity.ndim != 1:
        raise PeakGeometryError("time and intensity must be 1-D arrays.")
    if time.size != intensity.size:
        raise PeakGeometryError("time and intensity must be the same length.")
    if time.size < 1:
        raise PeakGeometryError("the trace is empty.")
    if not bool(np.all(np.isfinite(time))):
        raise PeakGeometryError("time contains non-finite values.")
    if time.size > 1 and not bool(np.all(np.diff(time) > 0.0)):
        raise PeakGeometryError("time must be strictly increasing.")
    if not bool(np.all(np.isfinite(intensity))):
        raise PeakGeometryError(
            "intensity contains non-finite values; a trace with a gap has no "
            "defined geometry."
        )


def find_apex(
    time: NDArray[np.float64],
    intensity: NDArray[np.float64],
    *,
    left_index: int = 0,
    right_index: int | None = None,
) -> Apex:
    """Return the apex of the peak inside ``[left_index, right_index]``.

    The maximum is refined by three-point parabolic interpolation when it is an
    interior sample and the three points are concave; otherwise the discrete
    sample maximum is returned with ``interpolated=False``.
    """
    _validate_trace(time, intensity)
    n = int(time.size)
    right = n - 1 if right_index is None else right_index
    if not 0 <= left_index <= right < n:
        raise PeakGeometryError(
            "the apex window must satisfy 0 <= left_index <= right_index < n."
        )
    section = intensity[left_index : right + 1]
    index = left_index + int(np.argmax(section))

    if left_index < index < right:
        vertex = _parabolic_vertex(
            float(time[index - 1]),
            float(intensity[index - 1]),
            float(time[index]),
            float(intensity[index]),
            float(time[index + 1]),
            float(intensity[index + 1]),
        )
        if vertex is not None and float(time[index - 1]) < vertex[0] < float(
            time[index + 1]
        ):
            return Apex(
                index=index, time=vertex[0], intensity=vertex[1], interpolated=True
            )

    return Apex(
        index=index,
        time=float(time[index]),
        intensity=float(intensity[index]),
        interpolated=False,
    )


def width_at_height(
    time: NDArray[np.float64],
    intensity: NDArray[np.float64],
    *,
    fraction: float,
    baseline: Baseline,
    apex: Apex | None = None,
) -> PeakWidth:
    """Return the peak width at *fraction* of the height above *baseline*.

    *fraction* is a number in ``(0, 1)``: ``0.5`` is the half-height width, and
    ``0.05`` the 5 %-height width the symmetry factor is defined on.  The
    baseline is required — the width is never measured against zero by default.
    """
    _validate_trace(time, intensity)
    if not 0.0 < fraction < 1.0:
        raise PeakGeometryError("fraction must be strictly between 0 and 1.")
    if apex is None:
        apex = find_apex(time, intensity)

    above = intensity - baseline.values(time)
    height = apex.intensity - baseline.value(apex.time)
    if height <= 0.0:
        raise PeakGeometryError(
            "the apex is not above the baseline, so no height is defined."
        )
    level = fraction * height

    left_time = _left_crossing(time, above, apex.index, level)
    right_time = _right_crossing(time, above, apex.index, level)
    return PeakWidth(
        fraction=fraction,
        apex_time=apex.time,
        height=height,
        left_time=left_time,
        right_time=right_time,
    )


def half_height_width(
    time: NDArray[np.float64],
    intensity: NDArray[np.float64],
    *,
    baseline: Baseline,
    apex: Apex | None = None,
) -> PeakWidth:
    """The width at half height — ``width_at_height(fraction=0.5)``."""
    return width_at_height(time, intensity, fraction=0.5, baseline=baseline, apex=apex)


def five_percent_width(
    time: NDArray[np.float64],
    intensity: NDArray[np.float64],
    *,
    baseline: Baseline,
    apex: Apex | None = None,
) -> PeakWidth:
    """The width at 5 % of height — ``width_at_height(fraction=0.05)``.

    This is the height the harmonised symmetry factor is measured at, not the
    older 10 %-height convention; ``SOURCES.md`` records the convention.
    """
    return width_at_height(time, intensity, fraction=0.05, baseline=baseline, apex=apex)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _parabolic_vertex(
    t0: float, y0: float, t1: float, y1: float, t2: float, y2: float
) -> tuple[float, float] | None:
    """The vertex of the parabola through three points, or ``None``.

    ``None`` is returned when the triple is not concave (no maximum), so the
    caller falls back to the discrete apex rather than reporting a minimum.
    """
    d1 = (y1 - y0) / (t1 - t0)
    d2 = (y2 - y1) / (t2 - t1)
    a = (d2 - d1) / (t2 - t0)
    if a >= 0.0:
        return None
    vertex_time = 0.5 * (t0 + t1) - d1 / (2.0 * a)
    vertex_intensity = (
        y0 + d1 * (vertex_time - t0) + a * (vertex_time - t0) * (vertex_time - t1)
    )
    return vertex_time, vertex_intensity


def _left_crossing(
    time: NDArray[np.float64],
    above: NDArray[np.float64],
    apex_index: int,
    level: float,
) -> float:
    for i in range(apex_index, 0, -1):
        if above[i] >= level >= above[i - 1]:
            span = above[i] - above[i - 1]
            fraction = 0.0 if span == 0.0 else (above[i] - level) / span
            return float(time[i] + fraction * (time[i - 1] - time[i]))
    raise PeakGeometryError(
        "the peak's leading edge does not fall to the measured height within the trace."
    )


def _right_crossing(
    time: NDArray[np.float64],
    above: NDArray[np.float64],
    apex_index: int,
    level: float,
) -> float:
    for i in range(apex_index, int(time.size) - 1):
        if above[i] >= level >= above[i + 1]:
            span = above[i] - above[i + 1]
            fraction = 0.0 if span == 0.0 else (above[i] - level) / span
            return float(time[i] + fraction * (time[i + 1] - time[i]))
    raise PeakGeometryError(
        "the peak's trailing edge does not fall to the measured height within "
        "the trace."
    )
