"""Synthetic closed-form peaks (W4).

Every fixture in the ground-truth suite is built here, in code, from a
closed-form function.  There is no vendor file, no client data and no published
dataset in the fixtures (``AGENTS.md`` §8), and the noise is a seeded numpy
generator, so a fixture is reproducible byte-for-byte.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

__all__ = ["add_noise", "emg", "gaussian", "sample", "two_peaks"]

_Function = Callable[[NDArray[np.float64]], NDArray[np.float64]]
_erfc = np.vectorize(math.erfc, otypes=[np.float64])


def sample(
    function: _Function, *, start: float, stop: float, step: float
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Sample *function* on ``[start, stop)`` at *step*, returning ``(t, y)``."""
    time = np.arange(start, stop, step, dtype=np.float64)
    return time, np.asarray(function(time), dtype=np.float64)


def gaussian(
    time: NDArray[np.float64], *, center: float, sigma: float, height: float = 1.0
) -> NDArray[np.float64]:
    """A symmetric Gaussian of amplitude *height*, centred at *center*."""
    return height * np.exp(-((time - center) ** 2) / (2.0 * sigma**2))


def emg(
    time: NDArray[np.float64],
    *,
    center: float,
    sigma: float,
    tau: float,
    height: float = 1.0,
) -> NDArray[np.float64]:
    """An exponentially modified Gaussian — a Gaussian with controlled tailing.

    *tau* is the exponential time constant; as ``tau -> 0`` the shape tends to
    the Gaussian.  The result is scaled so its maximum is *height*, so the apex
    height is controlled rather than the area.
    """
    lam = 1.0 / tau
    exponent = lam * (center + lam * sigma**2 / 2.0 - time)
    argument = (center + lam * sigma**2 - time) / (math.sqrt(2.0) * sigma)
    shape = (lam / 2.0) * np.exp(exponent) * _erfc(argument)
    peak = float(np.max(shape))
    if peak <= 0.0:
        raise ValueError("emg: the shape has no positive maximum.")
    return height * shape / peak


def two_peaks(
    time: NDArray[np.float64],
    *,
    first_center: float,
    first_sigma: float,
    second_center: float,
    second_sigma: float,
    first_height: float = 1.0,
    second_height: float = 1.0,
) -> NDArray[np.float64]:
    """Two Gaussians on a common baseline — a controlled pair for ``Rs`` and ``p/v``."""
    return gaussian(
        time, center=first_center, sigma=first_sigma, height=first_height
    ) + gaussian(time, center=second_center, sigma=second_sigma, height=second_height)


def add_noise(
    intensity: NDArray[np.float64], *, sd: float, seed: int
) -> NDArray[np.float64]:
    """Add Gaussian noise of standard deviation *sd*, from a seeded generator.

    The seed makes the fixture reproducible: the same *seed* and *sd* give the
    same trace on every run, so the ground-truth residuals are stable.
    """
    rng = np.random.default_rng(seed)
    return intensity + rng.normal(0.0, sd, size=intensity.shape)
