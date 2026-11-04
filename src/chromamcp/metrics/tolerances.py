"""Reference bounds for disagreement on the named synthetic fixture domain.

These historical bounds are not measurement uncertainty or laboratory criteria.
No production trace is assigned an applied bound: domain applicability is
``not-evaluated``. The %RSD floor is retained as historical, not derived.
See ``TOLERANCES.md`` for residuals, margins and the zero-expected-value policy.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["FIXTURE_DOMAIN_ID", "TOLERANCE", "EstimatorFixtureTolerance"]

FIXTURE_DOMAIN_ID = "synthetic-w4-w12-v1"


@dataclass(frozen=True, slots=True)
class EstimatorFixtureTolerance:
    """A reference fixture bound; never an applied bound on a caller trace.

    Relative error uses the independent expected value, not the measured value.
    At zero expected value it is undefined. Nonzero expected values use the
    relative definition without a near-zero cutoff or an absolute floor.
    No inference of domain membership is made from a result value alone.
    """

    reference_bound: float
    derivation_status: str
    basis: str = "relative"
    domain_id: str = FIXTURE_DOMAIN_ID
    applicability: str = "not-evaluated"
    applied_bound: None = None
    zero_expected_policy: str = "relative-error-undefined-at-zero-no-absolute-floor"


#: metric id -> historical relative fixture reference bound.  Mirrors the register in
#: ``TOLERANCES.md``; the two are checked equal by ``tests/test_tolerances.py``.
TOLERANCE: dict[str, float] = {
    "plate_number": 2.0e-2,
    "resolution": 5.0e-2,
    "symmetry_factor": 5.0e-2,
    "capacity_factor": 1.0e-2,
    "selectivity": 1.5e-2,
    "signal_to_noise": 1.0e-2,
    "peak_to_valley": 2.0e-2,
    "peak_area": 2.0e-3,
    "peak_height": 1.0e-2,
    "rsd_replicates": 1e-12,
}
