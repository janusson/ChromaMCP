"""The system-suitability panel (W3).

One pure function per metric — arrays and numbers in, a
:class:`~chromamcp.metrics.result.MetricResult` out.  No I/O, no module state.
Each carries the **formula id** whose row lives in ``SOURCES.md``; a formula id
with no row is a bug, and ``tests/test_sources_complete.py`` enforces it.

**Provenance of the formulas — read this before citing a number.**  The
designated source for the panel is USP 〈621〉 Chromatography (harmonised text),
read in its Stage 4 harmonisation document (official 1 December 2022), together
with JP XVIII *General Tests* 2.01.  The 〈621〉 rows in ``SOURCES.md`` are
transcribed from those two documents and say so in their ``Status`` column
(``AGENTS.md`` §1.2); later revisions of the system-sensitivity and peak-symmetry
subsections were not read, and the register names the revision it is anchored to.
Where this panel chooses between conventions the field also uses, the docstring
names the one it rejects.

Uniform conventions, named here once:

- Every width is measured **above an explicit baseline**, never against zero
  (W2, ``AGENTS.md`` §7.2).
- Every panel result carries **fixture reference evidence**, recorded in
  ``TOLERANCES.md`` and checked against
  :data:`~chromamcp.metrics.tolerances.TOLERANCE`. Applicability to a caller's
  measurement is not inferred. The historical %RSD floor is marked as not
  derived; the nine trace bounds retain their measured residuals and margins.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from chromamcp.errors import MetricInputError
from chromamcp.geometry import Baseline
from chromamcp.metrics.result import MetricResult
from chromamcp.metrics.tolerances import TOLERANCE

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
    ratio = _require_finite_result("plate_number ratio", apex_time / half_height_width)
    square = _require_finite_result("plate_number squared ratio", ratio * ratio)
    value = _require_finite_result("plate_number", 5.54 * square)
    return MetricResult(
        metric_id="plate_number",
        value=value,
        unit=_DIMENSIONLESS,
        formula_id=FORMULA_IDS["plate_number"],
        tolerance=TOLERANCE["plate_number"],
    )


def resolution(
    *,
    first_apex_time: float,
    first_half_height_width: float,
    second_apex_time: float,
    second_half_height_width: float,
) -> MetricResult:
    """Resolution ``Rs`` between two peaks, from half-height widths.

    ``Rs = 1.18 (tR2 − tR1) / (w½1 + w½2)``, with the peaks given in elution
    order (``tR1 < tR2``) — the harmonised half-height form as written in
    USP 〈621〉 Chromatography (Stage 4, 1 Dec 2022) and JP XVIII §2.01.

    Conventions.  Widths are at **half height**, and the coefficient belongs to
    that pair: ``1.18`` with half-height widths.  It rejects the base-width form
    ``Rs = 2 (tR2 − tR1) / (W1 + W2)``, whose ``W`` are widths at the baseline
    between the tangents — ``2`` is the right constant **only** for those widths.
    Pairing ``2`` with half-height widths, which this function did until W12,
    reported 1.695× the harmonised value from the same trace.
    """
    _require_positive("first_apex_time", first_apex_time)
    _require_positive("first_half_height_width", first_half_height_width)
    _require_positive("second_apex_time", second_apex_time)
    _require_positive("second_half_height_width", second_half_height_width)
    if second_apex_time <= first_apex_time:
        raise MetricInputError(
            "peaks must be given in elution order (second_apex_time > first_apex_time)."
        )
    width_sum = _require_finite_result(
        "resolution width sum", first_half_height_width + second_half_height_width
    )
    time_difference = _require_finite_result(
        "resolution time difference", second_apex_time - first_apex_time
    )
    value = _require_finite_result("resolution", 1.18 * time_difference / width_sum)
    return MetricResult(
        metric_id="resolution",
        value=value,
        unit=_DIMENSIONLESS,
        formula_id=FORMULA_IDS["resolution"],
        tolerance=TOLERANCE["resolution"],
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
    denominator = _require_finite_result(
        "symmetry_factor denominator", 2.0 * front_distance_at_5pct
    )
    value = _require_finite_result("symmetry_factor", width_at_5pct / denominator)
    return MetricResult(
        metric_id="symmetry_factor",
        value=value,
        unit=_DIMENSIONLESS,
        formula_id=FORMULA_IDS["symmetry_factor"],
        tolerance=TOLERANCE["symmetry_factor"],
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
    value = _require_finite_result(
        "capacity_factor", (apex_time - void_time) / void_time
    )
    return MetricResult(
        metric_id="capacity_factor",
        value=value,
        unit=_DIMENSIONLESS,
        formula_id=FORMULA_IDS["capacity_factor"],
        tolerance=TOLERANCE["capacity_factor"],
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
    numerator = _require_finite_result(
        "selectivity numerator", second_apex_time - void_time
    )
    denominator = _require_finite_result(
        "selectivity denominator", first_apex_time - void_time
    )
    value = _require_finite_result("selectivity", numerator / denominator)
    return MetricResult(
        metric_id="selectivity",
        value=value,
        unit=_DIMENSIONLESS,
        formula_id=FORMULA_IDS["selectivity"],
        tolerance=TOLERANCE["selectivity"],
    )


def signal_to_noise(
    *, signal_height: float, blank_intensity: NDArray[np.float64]
) -> MetricResult:
    """Signal-to-noise ``S/N``.

    ``S/N = 2 H / h``, with ``H`` the peak height above the baseline and ``h``
    the **peak-to-peak** noise of a blank region the caller supplies.

    Conventions — this is the panel's designated trap, and its noise range has a
    hierarchy the register states in the sources' own order (``DECISIONS.md`` §9,
    Q-B).  USP 〈621〉 takes ``h`` "observed over a distance equal to 20 times the
    width at half-height" and permits "at least 5 times the width at half-height"
    only where a 20× baseline "is not obtainable because of peaks due to the
    solvents"; JP XVIII §2.01 states the 20× range as well.  So **20× is the
    primary range and 5× the permitted fallback**, and the fallback is a property
    of the trace, not a licence to prefer the shorter window.

    The window is the **caller's**: this function takes the blank samples the
    caller has already sliced and fixes only the statistic (peak-to-peak) and the
    reading (``2H/h``).  It **rejects**, and does not mix with, the RMS (``6σ``)
    form and the plain ``H/h`` form, which give different numbers from the same
    blank — mixing them is the failure the convention must prevent.

    ``H`` must be **positive**: it is a peak height above the stated baseline, so
    a zero or negative height is refused rather than reported as a non-positive
    ``S/N``, which no chromatogram can support.
    """
    _require_positive("signal_height", signal_height)
    blank = np.asarray(blank_intensity, dtype=np.float64)
    if blank.size < 2:
        raise MetricInputError(
            "the blank region needs at least two samples to define a noise range."
        )
    if not bool(np.all(np.isfinite(blank))):
        raise MetricInputError("the blank region contains non-finite values.")
    with np.errstate(over="ignore", invalid="ignore"):
        noise = float(np.ptp(blank))
    _require_finite_result("signal_to_noise blank range", noise)
    if noise <= 0.0:
        raise MetricInputError(
            "the blank region has zero peak-to-peak noise; S/N is not defined "
            "against a noiseless blank."
        )
    numerator = _require_finite_result("signal_to_noise numerator", 2.0 * signal_height)
    value = _require_finite_result("signal_to_noise", numerator / noise)
    return MetricResult(
        metric_id="signal_to_noise",
        value=value,
        unit=_DIMENSIONLESS,
        formula_id=FORMULA_IDS["signal_to_noise"],
        tolerance=TOLERANCE["signal_to_noise"],
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
    first_height = _require_finite_result(
        "peak_to_valley first height", first_apex_intensity - baseline_intensity
    )
    second_height = _require_finite_result(
        "peak_to_valley second height", second_apex_intensity - baseline_intensity
    )
    valley_height = _require_finite_result(
        "peak_to_valley valley height", valley_intensity - baseline_intensity
    )
    if valley_height <= 0.0:
        raise MetricInputError(
            "the valley does not rise above the baseline; p/v is not defined."
        )
    smaller = min(first_height, second_height)
    if smaller <= 0.0:
        raise MetricInputError("a peak does not rise above the baseline.")
    value = _require_finite_result("peak_to_valley", smaller / valley_height)
    return MetricResult(
        metric_id="peak_to_valley",
        value=value,
        unit=_DIMENSIONLESS,
        formula_id=FORMULA_IDS["peak_to_valley"],
        tolerance=TOLERANCE["peak_to_valley"],
    )


def peak_height(
    *, apex_intensity: float, baseline_at_apex: float, intensity_unit: str = "unknown"
) -> MetricResult:
    """Peak height above the baseline.

    ``height = y_apex − baseline(t_apex)``.  This is a definition, not a cited
    equation: the height is only meaningful against the stated baseline
    (``SOURCES.md``). ``intensity_unit`` is an opaque caller-supplied axis
    label; when omitted the unit is unknown. Counts are never inferred.
    """
    _require_finite("apex_intensity", apex_intensity)
    _require_finite("baseline_at_apex", baseline_at_apex)
    value = _require_finite_result("peak_height", apex_intensity - baseline_at_apex)
    return MetricResult(
        metric_id="peak_height",
        value=value,
        unit=intensity_unit,
        formula_id=FORMULA_IDS["peak_height"],
        tolerance=TOLERANCE["peak_height"],
    )


def peak_area(
    time: NDArray[np.float64],
    intensity: NDArray[np.float64],
    *,
    baseline: Baseline,
    left_index: int,
    right_index: int,
    intensity_unit: str = "unknown",
) -> MetricResult:
    """Peak area above an explicit baseline, by the trapezoidal rule.

    The area of ``intensity − baseline`` over ``[left_index, right_index]``,
    integrated **trapezoidally** over the supplied grid.  The unit is the
    supplied intensity axis label times minutes. ``time`` must be in minutes;
    callers with other time units must convert first. The intensity unit is an
    opaque caller-supplied label, unknown when omitted; counts are never inferred.

    Window convention. The inclusive selected samples must have finite time
    and intensity values and strictly increasing times. Values outside the
    selected window do not enter the integral.

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
    window_time = grid[segment]
    window_intensity = values[segment]
    if not bool(np.all(np.isfinite(window_time))):
        raise MetricInputError(
            "time contains non-finite values in the selected window."
        )
    if not bool(np.all(np.isfinite(window_intensity))):
        raise MetricInputError(
            "intensity contains non-finite values in the selected window."
        )
    with np.errstate(over="ignore", invalid="ignore"):
        time_steps = np.diff(window_time)
    if not bool(np.all(np.isfinite(time_steps) & (time_steps > 0.0))):
        raise MetricInputError("time must increase strictly in the selected window.")
    with np.errstate(over="ignore", invalid="ignore"):
        baseline_values = baseline.values(window_time)
    if not bool(np.all(np.isfinite(baseline_values))):
        raise MetricInputError("the baseline is non-finite in the selected window.")
    with np.errstate(over="ignore", invalid="ignore"):
        above = window_intensity - baseline_values
        area = float(np.trapezoid(above, window_time))
    if not bool(np.all(np.isfinite(above))):
        raise MetricInputError("baseline subtraction produced non-finite values.")
    value = _require_finite_result("peak_area", area)
    return MetricResult(
        metric_id="peak_area",
        value=value,
        unit=f"{intensity_unit}·min",
        formula_id=FORMULA_IDS["peak_area"],
        tolerance=TOLERANCE["peak_area"],
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

    The mean must be **positive**, and a non-positive mean is refused.  ``%RSD``
    is a ratio to the mean response, so such a set has no meaningful relative
    precision; dividing by the absolute mean would report a positive number for
    a case the equation does not define.
    """
    values = np.asarray(replicates, dtype=np.float64)
    if values.ndim != 1:
        raise MetricInputError("replicates must be a 1-D sequence.")
    if values.size < 2:
        raise MetricInputError("the sample standard deviation needs n >= 2.")
    if not bool(np.all(np.isfinite(values))):
        raise MetricInputError("replicates contain non-finite values.")
    with np.errstate(over="ignore", invalid="ignore"):
        mean = float(np.mean(values))
    _require_finite_result("rsd_replicates mean", mean)
    if mean <= 0.0:
        raise MetricInputError(
            "%RSD is a ratio to the mean response, so the replicates' mean must "
            f"be positive; got a mean of {mean!r}."
        )
    with np.errstate(over="ignore", invalid="ignore"):
        standard_deviation = float(np.std(values, ddof=1))
    _require_finite_result("rsd_replicates standard deviation", standard_deviation)
    numerator = _require_finite_result(
        "rsd_replicates numerator", 100.0 * standard_deviation
    )
    value = _require_finite_result("rsd_replicates", numerator / mean)
    return MetricResult(
        metric_id="rsd_replicates",
        value=value,
        unit="%",
        formula_id=FORMULA_IDS["rsd_replicates"],
        tolerance=TOLERANCE["rsd_replicates"],
    )


# ---------------------------------------------------------------------------
# Input guards
# ---------------------------------------------------------------------------
def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise MetricInputError(f"{name} must be finite, got {value!r}.")


def _require_finite_result(name: str, value: float) -> float:
    if not math.isfinite(value):
        raise MetricInputError(f"{name} arithmetic produced a non-finite value.")
    return value


def _require_positive(name: str, value: float) -> None:
    if not (math.isfinite(value) and value > 0.0):
        raise MetricInputError(
            f"{name} must be a positive finite number, got {value!r}."
        )
