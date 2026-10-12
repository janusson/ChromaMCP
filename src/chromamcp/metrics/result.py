"""The result a panel metric returns (W3).

Every metric returns one of these.  ``M1-BRIEF.md`` §3 requires the value to
```M1-BRIEF.md`` §3 requires the value to
carry its **metric id**, its **unit**, the **formula id** whose row lives in
``SOURCES.md``, and the **tolerance** that applies to it.  A number without its
formula id is a bug, not an incomplete feature (``AGENTS.md`` §1.1).

``tolerance`` is the **derived** per-metric tolerance (W4), attached by every
panel function from :data:`chromamcp.metrics.tolerances.TOLERANCE`.  It is a
relative tolerance, derived from measured convergence error plus a stated margin
and recorded in ``TOLERANCES.md`` — never a value chosen by taste, which would
encode the estimator's bias as truth (``AGENTS.md`` §1.3).  The ``None`` default
remains only so a caller constructing a result outside the panel is explicit
about carrying no tolerance; the panel never emits it.
"""

from __future__ import annotations

from dataclasses import dataclass

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
