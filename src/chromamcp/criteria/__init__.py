"""The criteria-file contract (W6).

Parse and validate the criteria file ``M1-BRIEF.md`` §6 describes.  No
evaluation: this package answers "is this file well formed and complete?", not
"does the method pass?".
"""

from __future__ import annotations

from chromamcp.criteria.file import (
    OPERATORS,
    PAIRWISE_METRICS,
    PANEL_METRICS,
    REPLICATE_METRICS,
    TECHNIQUES,
    AppliesTo,
    CriteriaFile,
    Criterion,
    load_criteria,
    parse_criteria,
)

__all__ = [
    "OPERATORS",
    "PAIRWISE_METRICS",
    "PANEL_METRICS",
    "REPLICATE_METRICS",
    "TECHNIQUES",
    "AppliesTo",
    "CriteriaFile",
    "Criterion",
    "load_criteria",
    "parse_criteria",
]
