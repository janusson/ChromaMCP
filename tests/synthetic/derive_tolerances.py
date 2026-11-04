"""Bounded replay of the historical fixture experiment, using independent equations.

Run serially with thread caps from the repository root::

    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
        uv run python -m tests.synthetic.derive_tolerances

No input or output data file is needed. The printed Markdown is evidence of
estimator disagreement, not measurement uncertainty or laboratory criteria.
Expectations use dense-route geometry and literal equations from SOURCES.md;
no production metric is called to compute an expected value. The observed
route uses production geometry and metrics. No rounding policy is inferred
from the historical register's nonuniform upward rounding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cache

import numpy as np
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
from chromamcp.metrics.tolerances import FIXTURE_DOMAIN_ID, TOLERANCE
from tests.synthetic import fixtures
from tests.synthetic.measure import independent_apex, independent_width

RATES = (fixtures.RATE_COARSE, fixtures.RATE_FINE)
RSD_RESPONSES = (1.0, 2.0, 3.0, 4.0, 5.0)


@dataclass(frozen=True, slots=True)
class Residual:
    """One comparison on the named fixture domain."""

    metric_id: str
    step: float
    seed: int | None
    expected: float
    observed: float

    @property
    def relative(self) -> float:
        """Relative error is undefined at zero; no denominator floor is used."""
        if self.expected == 0.0:
            raise ValueError("relative error is undefined at zero expected value")
        return abs(self.observed - self.expected) / abs(self.expected)


def _dense_peak(
    time: NDArray[np.float64], intensity: NDArray[np.float64]
) -> tuple[float, float, float]:
    apex_t, apex_y = independent_apex(time, intensity)
    left, right, _ = independent_width(
        time, intensity, fraction=0.5, apex_time=apex_t, apex_intensity=apex_y
    )
    return apex_t, apex_y, right - left


@cache
def dense_expectations() -> dict[str, float]:
    """Apply the registered equations directly to independent dense geometry."""
    time, intensity = fixtures.single_gaussian(fixtures.DENSE)
    apex_t, apex_y, width = _dense_peak(time, intensity)
    # Independent trapezoid reduction, not production peak_area or np.trapezoid.
    area = math.fsum(
        0.5 * float(intensity[i] + intensity[i + 1]) * float(time[i + 1] - time[i])
        for i in range(len(time) - 1)
    )
    time_t, intensity_t = fixtures.tailing(fixtures.DENSE)
    tail_t, tail_y = independent_apex(time_t, intensity_t)
    left, right, front = independent_width(
        time_t, intensity_t, fraction=0.05, apex_time=tail_t, apex_intensity=tail_y
    )
    time_p, intensity_p = fixtures.separated_pair(fixtures.DENSE)
    middle = int(np.searchsorted(time_p, fixtures.separated_midpoint()))
    first = _dense_peak(time_p[:middle], intensity_p[:middle])
    second = _dense_peak(time_p[middle:], intensity_p[middle:])
    time_o, intensity_o = fixtures.overlapped_pair(fixtures.DENSE)
    middle_o = int(np.searchsorted(time_o, fixtures.overlapped_midpoint()))
    first_o = independent_apex(time_o[:middle_o], intensity_o[:middle_o])
    second_o = independent_apex(time_o[middle_o:], intensity_o[middle_o:])
    # The symmetric pair's midpoint brackets the valley on the dense grid.
    valley = min(float(item) for item in intensity_o[middle_o - 1 : middle_o + 2])
    mean = math.fsum(RSD_RESPONSES) / len(RSD_RESPONSES)
    sample_variance = math.fsum((x - mean) ** 2 for x in RSD_RESPONSES) / (
        len(RSD_RESPONSES) - 1
    )
    return {
        "plate_number": 5.54 * (apex_t / width) ** 2,
        "resolution": 1.18 * (second[0] - first[0]) / (first[2] + second[2]),
        "symmetry_factor": (right - left) / (2.0 * front),
        "capacity_factor": (apex_t - fixtures.VOID_TIME) / fixtures.VOID_TIME,
        "selectivity": (second[0] - fixtures.VOID_TIME)
        / (first[0] - fixtures.VOID_TIME),
        "peak_to_valley": min(first_o[1], second_o[1]) / valley,
        "peak_area": area,
        "peak_height": apex_y,
        "rsd_replicates": 100.0 * math.sqrt(sample_variance) / mean,
        # Used only to construct the independent, caller-supplied S/N blank.
        "half_height_width": width,
    }


def residuals(step: float, seed: int | None) -> tuple[Residual, ...]:
    """Measure all metrics at one rate; seed=None is the noiseless replay."""
    dense = dense_expectations()
    noisy = seed is not None
    noise_seed = 0 if seed is None else seed
    time, intensity = fixtures.single_gaussian(step, noisy=noisy, seed=noise_seed)
    apex = find_apex(time, intensity)
    width = half_height_width(time, intensity, baseline=fixtures.BASELINE, apex=apex)
    blank = fixtures.noise_region(dense["half_height_width"], step)
    noise_span = max(float(x) for x in blank) - min(float(x) for x in blank)
    expected = {key: value for key, value in dense.items() if key in TOLERANCE}
    expected["signal_to_noise"] = 2.0 * dense["peak_height"] / noise_span
    observed = {
        "plate_number": plate_number(
            apex_time=apex.time, half_height_width=width.width
        ).value,
        "capacity_factor": capacity_factor(
            apex_time=apex.time, void_time=fixtures.VOID_TIME
        ).value,
        "peak_area": peak_area(
            time,
            intensity,
            baseline=fixtures.BASELINE,
            left_index=0,
            right_index=len(time) - 1,
        ).value,
        "peak_height": peak_height(
            apex_intensity=apex.intensity, baseline_at_apex=0.0
        ).value,
        "signal_to_noise": signal_to_noise(
            signal_height=apex.intensity, blank_intensity=blank
        ).value,
        "rsd_replicates": rsd_replicates(RSD_RESPONSES).value,
    }
    time_t, intensity_t = fixtures.tailing(step, noisy=noisy, seed=noise_seed)
    tail_apex = find_apex(time_t, intensity_t)
    tail_width = five_percent_width(
        time_t, intensity_t, baseline=fixtures.BASELINE, apex=tail_apex
    )
    observed["symmetry_factor"] = symmetry_factor(
        width_at_5pct=tail_width.width,
        front_distance_at_5pct=tail_width.front_distance,
    ).value
    time_p, intensity_p = fixtures.separated_pair(step, noisy=noisy, seed=noise_seed)
    middle = int(np.searchsorted(time_p, fixtures.separated_midpoint()))
    first = find_apex(time_p, intensity_p, left_index=0, right_index=middle - 1)
    second = find_apex(
        time_p, intensity_p, left_index=middle, right_index=len(time_p) - 1
    )
    first_width = half_height_width(
        time_p, intensity_p, baseline=fixtures.BASELINE, apex=first
    )
    second_width = half_height_width(
        time_p, intensity_p, baseline=fixtures.BASELINE, apex=second
    )
    observed["resolution"] = resolution(
        first_apex_time=first.time,
        first_half_height_width=first_width.width,
        second_apex_time=second.time,
        second_half_height_width=second_width.width,
    ).value
    observed["selectivity"] = selectivity(
        first_apex_time=first.time,
        second_apex_time=second.time,
        void_time=fixtures.VOID_TIME,
    ).value
    time_o, intensity_o = fixtures.overlapped_pair(step, noisy=noisy, seed=noise_seed)
    middle_o = int(np.searchsorted(time_o, fixtures.overlapped_midpoint()))
    first_o = find_apex(time_o, intensity_o, left_index=0, right_index=middle_o - 1)
    second_o = find_apex(
        time_o, intensity_o, left_index=middle_o, right_index=len(time_o) - 1
    )
    valley = float(intensity_o[first_o.index : second_o.index + 1].min())
    observed["peak_to_valley"] = peak_to_valley(
        first_apex_intensity=first_o.intensity,
        second_apex_intensity=second_o.intensity,
        valley_intensity=valley,
        baseline_intensity=0.0,
    ).value
    return tuple(
        Residual(metric_id, step, seed, expected[metric_id], observed[metric_id])
        for metric_id in sorted(TOLERANCE)
    )


@cache
def experiment() -> tuple[Residual, ...]:
    """All 8 seeds at both rates plus each noiseless rate, serially."""
    return tuple(
        row
        for step in RATES
        for seed in (None, *fixtures.SEEDS)
        for row in residuals(step, seed)
    )


def report() -> str:
    """Deterministic measured maxima; the historical register remains separate."""
    rows = experiment()
    lines = [
        "# Fixture estimator disagreement replay",
        "",
        f"Domain: `{FIXTURE_DOMAIN_ID}`. Independent dense grid: 1e-5 min.",
        "Working grids: 0.002 and 0.001 min; Gaussian noise SD: 0.002 of height.",
        "Seeds: " + ", ".join(str(seed) for seed in fixtures.SEEDS) + ".",
        "All comparisons are serial; no domain inference is made for caller traces.",
        "The %RSD route is the same fixed positive-response vector in every case.",
        "The S/N blank is shared by the two routes (seed 990001, 20x width).",
        "",
        "| Metric | Noiseless maximum | Noisy maximum | 2x noisy maximum | Worst rate | Worst seed | Historical reference bound |",
        "|---|---|---|---|---|---|---|",
    ]
    for metric_id in sorted(TOLERANCE):
        metric_rows = [row for row in rows if row.metric_id == metric_id]
        noiseless = max(row.relative for row in metric_rows if row.seed is None)
        worst = max(
            (row for row in metric_rows if row.seed is not None),
            key=lambda row: row.relative,
        )
        margin = (
            "not-derived"
            if metric_id == "rsd_replicates"
            else f"{2 * worst.relative:.6e}"
        )
        lines.append(
            f"| {metric_id} | {noiseless:.6e} | {worst.relative:.6e} | "
            f"{margin} | {worst.step} | {worst.seed} | {TOLERANCE[metric_id]:.6e} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(report(), end="")
