"""Canonical fixtures and derived tolerances for the ground-truth suite (W4).

Every fixture parameter is fixed here so the ground truth is reproducible.  The
noise is Gaussian, seeded, and set at 0.2 % of the peak height — a weak peak by
system-suitability standards — so the tolerances are honest about a *noisy*
trace rather than a noiseless idealisation (``M1-BRIEF.md`` §5.2 step 5).

The :data:`TOLERANCE` values are **derived**, not chosen: each is
``2 ×`` the largest relative residual measured over the two working rates and
eight noise seeds, after the derivation recorded in ``TOLERANCES.md``
(``AGENTS.md`` §1.3).  They are re-exported from the package
(:data:`chromamcp.metrics.tolerances.TOLERANCE`) rather than restated here, so the
value the ground-truth suite asserts against **is** the value the panel ships;
``tests/test_tolerances.py`` checks that mapping against ``TOLERANCES.md``.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from chromamcp.geometry import Baseline
from chromamcp.metrics.tolerances import TOLERANCE as TOLERANCE
from tests.synthetic.peaks import add_noise, emg, gaussian, sample, two_peaks

# --- fixture parameters -----------------------------------------------------
SIGMA = 0.05  # minutes
HEIGHT = 1.0
NOISE_SD = 0.002  # 0.2 % of the peak height
SEEDS: tuple[int, ...] = tuple(20261011 + i for i in range(8))
RATE_COARSE = 0.002  # minutes between samples (the coarser working rate)
RATE_FINE = 0.001
DENSE = 1e-5  # the independent-route grid
VOID_TIME = 0.3  # minutes, supplied explicitly (never defaulted)
BASELINE = Baseline.constant(0.0)

SINGLE_WINDOW = (0.6, 1.4)
TAILING_WINDOW = (0.6, 1.6)
TAILING_TAU = 0.08
SEPARATED_WINDOW = (0.6, 1.7)
SEPARATED_SECOND_CENTER = 1.25
OVERLAPPED_WINDOW = (0.6, 1.6)
OVERLAPPED_SECOND_CENTER = 1.15

_Trace = tuple[NDArray[np.float64], NDArray[np.float64]]
_Function = Callable[[NDArray[np.float64]], NDArray[np.float64]]


def _build(
    function: _Function,
    *,
    window: tuple[float, float],
    step: float,
    noisy: bool,
    seed: int,
) -> _Trace:
    time, intensity = sample(function, start=window[0], stop=window[1], step=step)
    if noisy:
        intensity = add_noise(intensity, sd=NOISE_SD, seed=seed)
    return time, intensity


def single_gaussian(step: float, *, noisy: bool = False, seed: int = 0) -> _Trace:
    """A single symmetric Gaussian — the fixture for ``N``, ``k′``, area, height."""
    return _build(
        lambda t: gaussian(t, center=1.0, sigma=SIGMA, height=HEIGHT),
        window=SINGLE_WINDOW,
        step=step,
        noisy=noisy,
        seed=seed,
    )


def tailing(step: float, *, noisy: bool = False, seed: int = 0) -> _Trace:
    """An EMG with controlled tailing — the fixture for the symmetry factor."""
    return _build(
        lambda t: emg(t, center=1.0, sigma=SIGMA, tau=TAILING_TAU, height=HEIGHT),
        window=TAILING_WINDOW,
        step=step,
        noisy=noisy,
        seed=seed,
    )


def separated_pair(step: float, *, noisy: bool = False, seed: int = 0) -> _Trace:
    """A resolved pair (valley below half height) — the fixture for ``Rs`` and ``α``."""
    return _build(
        lambda t: two_peaks(
            t,
            first_center=1.0,
            first_sigma=SIGMA,
            second_center=SEPARATED_SECOND_CENTER,
            second_sigma=SIGMA,
        ),
        window=SEPARATED_WINDOW,
        step=step,
        noisy=noisy,
        seed=seed,
    )


def overlapped_pair(step: float, *, noisy: bool = False, seed: int = 0) -> _Trace:
    """An overlapped pair (valley above half height) — the fixture for ``p/v``."""
    return _build(
        lambda t: two_peaks(
            t,
            first_center=1.0,
            first_sigma=SIGMA,
            second_center=OVERLAPPED_SECOND_CENTER,
            second_sigma=SIGMA,
        ),
        window=OVERLAPPED_WINDOW,
        step=step,
        noisy=noisy,
        seed=seed,
    )


def separated_midpoint() -> float:
    """The time midway between the separated pair's two centres."""
    return 0.5 * (1.0 + SEPARATED_SECOND_CENTER)


def overlapped_midpoint() -> float:
    """The time midway between the overlapped pair's two centres."""
    return 0.5 * (1.0 + OVERLAPPED_SECOND_CENTER)


def noise_region(
    half_height_width: float, step: float, *, seed: int = 990001
) -> NDArray[np.float64]:
    """A blank region five times a peak's half-height width, at the working rate.

    This is the noise window ``SOURCES.md`` records for ``S/N`` — tied to the
    peak's half-height width — realised as pure noise on the same grid.
    """
    count = max(2, round(5.0 * half_height_width / step))
    return add_noise(np.zeros(count), sd=NOISE_SD, seed=seed)
