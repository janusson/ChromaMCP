"""The system-suitability panel (W3).

Pure metric functions, each returning a
:class:`~chromamcp.metrics.result.MetricResult` that carries its value, unit,
**formula id** and **derived tolerance**.  The formula ids are listed in
:data:`FORMULA_IDS` and checked against ``SOURCES.md`` by
``tests/test_sources_complete.py``; the tolerances are listed in :data:`TOLERANCE`
and checked against ``TOLERANCES.md`` by ``tests/test_tolerances.py``.

Every formula ships marked ``secondary source — primary text not consulted``
until the USP 〈621〉 text is transcribed (``AGENTS.md`` §1.2).
"""

from __future__ import annotations

from chromamcp.metrics.panel import (
    FORMULA_IDS,
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
from chromamcp.metrics.result import MetricResult
from chromamcp.metrics.tolerances import TOLERANCE

__all__ = [
    "FORMULA_IDS",
    "TOLERANCE",
    "MetricResult",
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
