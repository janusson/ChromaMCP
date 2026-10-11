"""The result a panel metric returns (W3).

Every metric returns one of these.  ``M1-BRIEF.md`` §3 requires the value to
carry its **metric id**, its **unit**, the **formula id** whose row lives in
``SOURCES.md``, and the **tolerance** that applies to it.  A number without its
formula id is a bug, not an incomplete feature (``AGENTS.md`` §1.1).

``tolerance`` is ``None`` until W4 derives it from measured convergence error
(``AGENTS.md`` §1.3): a tolerance chosen by taste would encode the estimator's
bias as truth, so this field carries no number until there is a measured one.
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
