"""Peak geometry: the measurements the suitability panel is built on (W2).

An apex with a stated interpolation rule, widths at half height and 5 % height,
and an explicit, named baseline.  Every function is pure — arrays in, values
out — and every convention it follows is named in the module docstring together
with the competing one it rejects.
"""

from __future__ import annotations

from chromamcp.geometry.baseline import (
    Baseline,
    BaselineRule,
    resolve_baseline,
)
from chromamcp.geometry.peaks import (
    Apex,
    PeakWidth,
    find_apex,
    five_percent_width,
    half_height_width,
    width_at_height,
)

__all__ = [
    "Apex",
    "Baseline",
    "BaselineRule",
    "PeakWidth",
    "find_apex",
    "five_percent_width",
    "half_height_width",
    "resolve_baseline",
    "width_at_height",
]
