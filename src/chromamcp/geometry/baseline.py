"""Baseline models for peak geometry (W2).

A peak's height, width and area are all measured **relative to a baseline**, so
the baseline is not a detail — it is a stated choice.  This module makes that
choice explicit: the caller selects a :class:`BaselineRule`, and the baseline is
a straight line that every downstream measurement subtracts.

**Conventions this module implements, and the ones it rejects.**  For a pair of
overlapping peaks the field uses more than one convention to place that line,
and they give different widths and areas from the same trace:

- :attr:`BaselineRule.LINEAR` — a straight line through two anchor points (a
  peak's baseline start and end).  This is the reading used for a resolved peak
  or a flat baseline; it assumes the baseline is linear between the anchors.
- :attr:`BaselineRule.VALLEY_DROP` — the perpendicular drop: a horizontal line
  at the valley intensity between two unresolved peaks.
- :attr:`BaselineRule.TANGENT_SKIM` — the tangent drawn under a valley.  It is
  **named but not implemented in M1**: requesting it raises rather than
  returning a plausible number, because the tangent construction belongs with
  the integration metric M1 does not ship.

The reading the whole module rejects is the *implicit* one — any measurement
returned without naming the baseline it was measured against.  A number whose
baseline is unstated is not reproducible, and reproducibility is the point of
the record this project emits.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from chromamcp.errors import PeakGeometryError

__all__ = [
    "Baseline",
    "BaselineRule",
    "resolve_baseline",
]


class BaselineRule(Enum):
    """The named ways of placing the baseline under a peak."""

    LINEAR = "linear"
    VALLEY_DROP = "valley_drop"
    TANGENT_SKIM = "tangent_skim"


@dataclass(frozen=True, slots=True)
class Baseline:
    """A straight-line baseline, ``intercept + slope * time``.

    The line is defined by two numbers rather than by its anchor span, so a flat
    baseline (``slope == 0``) is representable without a degenerate interval.
    Which samples the line was drawn through is the caller's to record; this
    object only evaluates the line.
    """

    intercept: float
    slope: float = 0.0

    @classmethod
    def constant(cls, level: float) -> Baseline:
        """A horizontal baseline at *level*."""
        return cls(level, 0.0)

    @classmethod
    def through(
        cls,
        left_time: float,
        left_intensity: float,
        right_time: float,
        right_intensity: float,
    ) -> Baseline:
        """The straight line through two anchor points.

        Raises :class:`~chromamcp.errors.PeakGeometryError` if the two anchor
        times coincide, so a slope cannot be defined.
        """
        if right_time == left_time:
            raise PeakGeometryError(
                "baseline anchors must have distinct times to define a slope."
            )
        slope = (right_intensity - left_intensity) / (right_time - left_time)
        return cls(left_intensity - slope * left_time, slope)

    def value(self, time: float) -> float:
        """The baseline intensity at a single *time*."""
        return self.intercept + self.slope * time

    def values(self, time: NDArray[np.float64]) -> NDArray[np.float64]:
        """The baseline intensity at each point of a *time* array."""
        values = self.intercept + self.slope * time
        return np.asarray(values, dtype=np.float64)


def resolve_baseline(
    rule: BaselineRule,
    time: NDArray[np.float64],
    intensity: NDArray[np.float64],
    *,
    left_index: int,
    right_index: int,
    valley_index: int | None = None,
) -> Baseline:
    """Build the :class:`Baseline` named by *rule* from a trace.

    *left_index* and *right_index* are the samples the ``LINEAR`` line spans (a
    peak's baseline start and end).  ``VALLEY_DROP`` needs *valley_index* — the
    sample at the valley between two unresolved peaks.  ``TANGENT_SKIM`` is
    refused, not approximated.
    """
    if rule is BaselineRule.LINEAR:
        return Baseline.through(
            float(time[left_index]),
            float(intensity[left_index]),
            float(time[right_index]),
            float(intensity[right_index]),
        )
    if rule is BaselineRule.VALLEY_DROP:
        if valley_index is None:
            raise PeakGeometryError(
                "VALLEY_DROP needs the valley sample (valley_index)."
            )
        return Baseline.constant(float(intensity[valley_index]))
    raise PeakGeometryError(
        "TANGENT_SKIM is not implemented in M1 and is refused rather than "
        "approximated. The tangent-skim baseline belongs with the integration "
        "metric, which M1 does not ship."
    )
