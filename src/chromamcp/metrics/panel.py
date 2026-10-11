"""The system-suitability panel (W3).

One pure function per metric — arrays and numbers in, a
:class:`~chromamcp.metrics.result.MetricResult` out.  No I/O, no module state.
Each carries the **formula id** whose row lives in ``SOURCES.md``; a formula id
with no row is a bug, and ``tests/test_sources_complete.py`` enforces it.

**Provenance of the formulas — read this before citing a number.**  The
designated source for the panel is USP 〈621〉 Chromatography (harmonised text).
That primary text was **not consulted** when these functions were written (it is
paywalled), so every row ships marked ``secondary source — primary text not
consulted`` and the equations below are the standard published forms, not
transcriptions from 〈621〉 itself (``AGENTS.md`` §1.2).  They must be checked
against the primary text before any of them is presented as "the published
formula".

Uniform conventions, named here once:

- Every width is measured **above an explicit baseline**, never against zero
  (W2, ``AGENTS.md`` §7.2).
- Tolerances are ``None`` until W4 derives them from measured convergence; no
  function returns a tolerance chosen by taste (``AGENTS.md`` §1.3).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from chromamcp.errors import MetricInputError
from chromamcp.geometry import Baseline
from chromamcp.metrics.result import MetricResult

__all__ = [
    "FORMULA_IDS",
    "capacity_factor",
    "peak_area",
    "peak_height",
    "peak_to_valley",
    "plate_number",
    "resolution",
    "rsd_replicates",
    "selectivity",
    "signal_to_noise",
    "symmetry_factor",
]

#: metric id -> formula id.  The single source of the formula ids the code
#: emits, so ``tests/test_sources_complete.py`` can check every one against
#: ``SOURCES.md``.  A function must take its id from here, not hardcode it.
FORMULA_IDS: dict[str, str] = {
    "plate_number": "plate_number_half_height",
    "resolution": "resolution_half_height",
    "symmetry_factor": "symmetry_factor_5pct",
    "capacity_factor": "capacity_factor",
    "selectivity": "selectivity",
    "signal_to_noise": "signal_to_noise",
    "peak_to_valley": "peak_to_valley",
    "peak_area": "peak_area",
    "peak_height": "peak_height",
    "rsd_replicates": "rsd_replicates",
}

_DIMENSIONLESS = "dimensionless"


def plate_number(*, apex_time: float, half_height_width: float) -> MetricResult:
    """Plate number ``N`` from the half-height form.

    ``N = 5.54 (tR / w½)²``, with ``tR`` the interpolated apex time and ``w½``
    the **half-height** width (both W2).

    Conventions.  This is the harmonised half-height form.  It rejects the legacy
    "tangent width" reading ``N = 16 (tR / w)²``, whose ``w`` is the base width
    between the two tangent lines; that gives a different number from the same
    trace and is not the current definition.
    """
    _require_positive("apex_time", apex_time)
    _require_positive("half_height_width", half_height_width)
    return MetricResult(
        metric_id="plate_number",
        value=5.54 * (apex_time / half_height_width) ** 2,
        unit=_DIMENSIONLESS,
        formula_id=FORMULA_IDS["plate_number"],
    )


def resolution(
    *,
    first_apex_time: float,
    first_half_height_width: float,
    second_apex_time: float,
    second_half_height_width: float,
) -> MetricResult:
    """Resolution ``Rs`` between two peaks, from half-height widths.

    ``Rs = 2 (tR2 − tR1) / (w½1 + w½2)``, with the peaks given in elution order
    (``tR1 < tR2``).

    Conventions.  Widths are at **half height**, the form on which US, EP and JP
    agree.  It rejects the base-width form ``Rs = 2 (tR2 − tR1) / (W1 + W2)``,
    whose ``W`` are widths at the baseline between the tangents and which gives a
    larger number from the same trace.
    """
    _require_positive("first_apex_time", first_apex_time)
    _require_positive("first_half_height_width", first_half_height_width)
    _require_positive("second_apex_time", second_apex_time)
    _require_positive("second_half_height_width", second_half_height_width)
    if second_apex_time <= first_apex_time:
        raise MetricInputError(
            "peaks must be given in elution order (second_apex_time > first_apex_time)."
        )
    value = (
        2.0
        * (second_apex_time - first_apex_time)
        / (first_half_height_width + second_half_height_width)
    )
    return MetricResult(
        metric_id="resolution",
        value=value,
        unit=_DIMENSIONLESS,
        formula_id=FORMULA_IDS["resolution"],
    )


def symmetry_factor(
    *, width_at_5pct: float, front_distance_at_5pct: float
) -> MetricResult:
    """Symmetry factor ``A`` from the peak's 5 %-height width.

    ``A = w0.05 / (2 · d_front)``, where ``w0.05`` is the width at 5 % of peak
    height and ``d_front`` the distance from the leading edge at that height to
    the apex (both from the W2 width at ``fraction=0.05``).  ``A = 1`` for a
    symmetric peak.

    Conventions.  The height is **5 %** of the peak height (one-twentieth).
    This is a 5 %-height measurement, and it rejects the older 10 %-height form.
    The quantity was renamed from "tailing factor" (``T``) to "symmetry factor"
    (``As``) in the harmonised text; the calculation is unchanged (``SOURCES.md``).
    """
    _require_positive("width_at_5pct", width_at_5pct)
    _require_positive("front_distance_at_5pct", front_distance_at_5pct)
    if front_distance_at_5pct > width_at_5pct:
        raise MetricInputError(
            "front_distance_at_5pct cannot exceed the 5 %-height width."
        )
    return MetricResult(
        metric_id="symmetry_factor",
        value=width_at_5pct / (2.0 * front_distance_at_5pct),
        unit=_DIMENSIONLESS,
        formula_id=FORMULA_IDS["symmetry_factor"],
    )


def capacity_factor(*, apex_time: float, void_time: float) -> MetricResult:
    """Capacity (retention) factor ``k′``.

    ``k′ = (tR − t0) / t0``.

    Conventions.  ``t0`` (the void time) must be **supplied**; the tool never
    defaults it.  If ``t0`` is an estimate rather than a measurement, that must
    be reported separately, because the estimate's error propagates straight into
    ``k′`` (``M1-BRIEF.md`` §3).
    """
    _require_positive("apex_time", apex_time)
    _require_positive("void_time", void_time)
    if apex_time <= void_time:
        raise MetricInputError(
            "apex_time must be greater than void_time; a peak cannot elute "
            "before the void time."
        )
    return MetricResult(
        metric_id="capacity_factor",
        value=(apex_time - void_time) / void_time,
        unit=_DIMENSIONLESS,
        formula_id=FORMULA_IDS["capacity_factor"],
    )


def selectivity(
    *, first_apex_time: float, second_apex_time: float, void_time: float
) -> MetricResult:
    """Selectivity ``α`` between two peaks.

    ``α = k′2 / k′1 = (tR2 − t0) / (tR1 − t0)``, with ``tR1 < tR2``.

    Conventions.  It inherits the ``t0`` requirement of :func:`capacity_factor`:
    ``t0`` is supplied, never defaulted, and an estimated ``t0`` must be reported
    separately.
    """
    _require_positive("first_apex_time", first_apex_time)
    _require_positive("second_apex_time", second_apex_time)
    _require_positive("void_time", void_time)
    if second_apex_time <= first_apex_time:
        raise MetricInputError(
            "peaks must be given in elution order (second_apex_time > first_apex_time)."
        )
    if first_apex_time <= void_time:
        raise MetricInputError("first_apex_time must be greater than void_time.")
    value = (second_apex_time - void_time) / (first_apex_time - void_time)
    return MetricResult(
        metric_id="selectivity",
        value=value,
        unit=_DIMENSIONLESS,
        formula_id=FORMULA_IDS["selectivity"],
    )


def signal_to_noise(
    *, signal_height: float, blank_intensity: NDArray[np.float64]
) -> MetricResult:
    """Signal-to-noise ``S/N``.

    ``S/N = 2 H / h``, with ``H`` the peak height above the baseline and ``h``
    the **peak-to-peak** noise of a blank region the caller supplies.

    Conventions — this is the panel's designated trap, and the one convention
    still open (ping point **P1**).  ``SOURCES.md`` records the harmonised noise
    range as tied to the peak's half-height width (a window of five times that
    width, from a blank at the expected retention time); the caller selects that
    window and passes the blank samples here.  This function fixes the statistic
    as peak-to-peak and the reading as ``2H/h``.  It **rejects**, and does not
    mix with, the RMS (``6σ``) form and the plain ``H/h`` form, which give
    different numbers from the same blank — mixing them is the failure the
    convention must prevent.  A vendor 20×-window variant is also recorded in
    ``SOURCES.md`` and is not used here.  Pending Eric's house convention (P1),
    this reading is a stated default, not a settled one.
    """
    _require_finite("signal_height", signal_height)
    blank = np.asarray(blank_intensity, dtype=np.float64)
    if blank.size < 2:
        raise MetricInputError(
            "the blank region needs at least two samples to define a noise range."
        )
    if not bool(np.all(np.isfinite(blank))):
        raise MetricInputError("the blank region contains non-finite values.")
    noise = float(np.ptp(blank))
    if noise <= 0.0:
        raise MetricInputError(
            "the blank region has zero peak-to-peak noise; S/N is not defined "
            "against a noiseless blank."
        )
    return MetricResult(
        metric_id="signal_to_noise",
        value=2.0 * signal_height / noise,
        unit=_DIMENSIONLESS,
        formula_id=FORMULA_IDS["signal_to_noise"],
    )


def peak_to_valley(
    *,
    first_apex_intensity: float,
    second_apex_intensity: float,
    valley_intensity: float,
    baseline_intensity: float,
) -> MetricResult:
    """Peak-to-valley ratio ``p/v`` for an unresolved pair.

    ``p/v = h_smaller / h_valley``, where each ``h`` is the intensity **above the
    stated baseline**: ``h_smaller`` is the smaller of the two apex heights and
    ``h_valley`` the valley height between them.

    Conventions.  It applies only to an unresolved pair and must not be emitted
    in place of :func:`resolution` (``M1-BRIEF.md`` §3).  The baseline is stated
    by the caller; a sloped baseline under the pair must be reduced to the level
    the caller is prepared to defend, not left implicit.
    """
    for name, value in (
        ("first_apex_intensity", first_apex_intensity),
        ("second_apex_intensity", second_apex_intensity),
        ("valley_intensity", valley_intensity),
        ("baseline_intensity", baseline_intensity),
    ):
        _require_finite(name, value)
    first_height = first_apex_intensity - baseline_intensity
    second_height = second_apex_intensity - baseline_intensity
    valley_height = valley_intensity - baseline_intensity
    if valley_height <= 0.0:
        raise MetricInputError(
            "the valley does not rise above the baseline; p/v is not defined."
        )
    smaller = min(first_height, second_height)
    if smaller <= 0.0:
        raise MetricInputError("a peak does not rise above the baseline.")
    return MetricResult(
        metric_id="peak_to_valley",
        value=smaller / valley_height,
        unit=_DIMENSIONLESS,
        formula_id=FORMULA_IDS["peak_to_valley"],
    )


def peak_height(*, apex_intensity: float, baseline_at_apex: float) -> MetricResult:
    """Peak height above the baseline.

    ``height = y_apex − baseline(t_apex)``.  This is a definition, not a cited
    equation: the height is only meaningful against the stated baseline
    (``SOURCES.md``).
    """
    _require_finite("apex_intensity", apex_intensity)
    _require_finite("baseline_at_apex", baseline_at_apex)
    return MetricResult(
        metric_id="peak_height",
        value=apex_intensity - baseline_at_apex,
        unit="counts",
        formula_id=FORMULA_IDS["peak_height"],
    )


def peak_area(
    time: NDArray[np.float64],
    intensity: NDArray[np.float64],
    *,
    baseline: Baseline,
    left_index: int,
    right_index: int,
) -> MetricResult:
    """Peak area above an explicit baseline, by the trapezoidal rule.

    The area of ``intensity − baseline`` over ``[left_index, right_index]``,
    integrated **trapezoidally** over the supplied grid.  The unit is the
    intensity axis times time (``counts·min`` when intensity is detector counts
    and time is minutes).

    Conventions.  The baseline is required and explicit; an area is never
    presented as model-free (``M1-BRIEF.md`` §3).  It rejects the rectangular
    (mid-point) and Simpson rules, which give a different number from the same
    trace; the trapezoidal rule is used because it is what a caller reproducing
    the number by hand would write.
    """
    grid = np.asarray(time, dtype=np.float64)
    values = np.asarray(intensity, dtype=np.float64)
    if grid.ndim != 1 or values.ndim != 1 or grid.size != values.size:
        raise MetricInputError("time and intensity must be 1-D and the same length.")
    if not 0 <= left_index < right_index < grid.size:
        raise MetricInputError(
            "the window must satisfy 0 <= left_index < right_index < len(time)."
        )
    segment = slice(left_index, right_index + 1)
    above = values[segment] - baseline.values(grid[segment])
    return MetricResult(
        metric_id="peak_area",
        value=float(np.trapezoid(above, grid[segment])),
        unit="counts·min",
        formula_id=FORMULA_IDS["peak_area"],
    )


def rsd_replicates(replicates: Sequence[float] | NDArray[np.float64]) -> MetricResult:
    """Injection-to-injection precision ``%RSD`` over explicit replicates.

    ``%RSD = 100 · s / mean``, where ``s`` is the **sample** standard deviation
    (``n − 1`` denominator) and ``mean`` is the arithmetic mean of the replicates.

    Conventions.  The replicate set is supplied explicitly — this metric belongs
    to the sequence layer and is computed only when a replicate list is handed to
    it (``M1-BRIEF.md`` §3).  It uses the sample (``n − 1``) denominator and
    rejects the population (``n``) denominator, which understates the spread at
    the small ``n`` system suitability uses.
    """
    values = np.asarray(replicates, dtype=np.float64)
    if values.ndim != 1:
        raise MetricInputError("replicates must be a 1-D sequence.")
    if values.size < 2:
        raise MetricInputError("the sample standard deviation needs n >= 2.")
    if not bool(np.all(np.isfinite(values))):
        raise MetricInputError("replicates contain non-finite values.")
    mean = float(np.mean(values))
    if mean == 0.0:
        raise MetricInputError("the mean is zero; %RSD is not defined.")
    value = 100.0 * float(np.std(values, ddof=1)) / abs(mean)
    return MetricResult(
        metric_id="rsd_replicates",
        value=value,
        unit="%",
        formula_id=FORMULA_IDS["rsd_replicates"],
    )


# ---------------------------------------------------------------------------
# Input guards
# ---------------------------------------------------------------------------
def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise MetricInputError(f"{name} must be finite, got {value!r}.")


def _require_positive(name: str, value: float) -> None:
    if not (math.isfinite(value) and value > 0.0):
        raise MetricInputError(
            f"{name} must be a positive finite number, got {value!r}."
        )
