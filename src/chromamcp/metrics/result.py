"""A panel measurement and separately named synthetic-fixture evidence.

``tolerance`` is retained as an internal constructor compatibility field for the
panel's historical mapping. Consumers use ``estimator_fixture_tolerance``:
its bound describes a reference experiment, not the caller's measurement.
No applicability, measurement uncertainty or laboratory criteria is inferred.
The raw dataclass representation is not the wire schema; the supported record
and server serializers emit the named fixture metadata, omitting the legacy
constructor field.
"""

from __future__ import annotations

from dataclasses import dataclass

from chromamcp.metrics.tolerances import TOLERANCE, EstimatorFixtureTolerance

__all__ = ["MetricResult"]


@dataclass(frozen=True, slots=True)
class MetricResult:
    """A single panel measurement, with the identifiers a reviewer needs."""

    metric_id: str
    value: float
    unit: str
    formula_id: str
    tolerance: float | None = None

    def __post_init__(self) -> None:
        if self.tolerance is not None and self.tolerance <= 0.0:
            raise ValueError(
                "tolerance must be a positive relative number or None, got "
                f"{self.tolerance!r}."
            )

    @property
    def estimator_fixture_tolerance(self) -> EstimatorFixtureTolerance | None:
        """Reference evidence with applicability explicitly not evaluated."""
        if (
            self.tolerance is None
            or self.metric_id not in TOLERANCE
            or self.tolerance != TOLERANCE[self.metric_id]
        ):
            return None
        return EstimatorFixtureTolerance(
            reference_bound=self.tolerance,
            derivation_status=(
                "historical-floor-not-derived"
                if self.metric_id == "rsd_replicates"
                else "residual-times-margin"
            ),
        )
