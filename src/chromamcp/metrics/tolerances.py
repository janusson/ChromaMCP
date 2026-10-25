"""The derived, recorded per-metric tolerances (W4).

A tolerance is a **claim**, and this project derives it rather than choosing it
(``AGENTS.md`` §1.3).  Each value below is ``2 ×`` the largest relative residual
the ground-truth suite measured across the two working sampling rates and eight
noise seeds, after the derivation recorded in ``TOLERANCES.md`` — the noise
residual scaled by a stated margin and rounded up, so it is honest about a noisy
single scan.

The numbers are **relative** (a fraction of the expected value), and this mapping
is the single source of truth for them: the panel attaches the value to every
:class:`~chromamcp.metrics.result.MetricResult` it returns, and
``tests/test_tolerances.py`` checks it against the register in ``TOLERANCES.md``
so the shipped number and the recorded derivation cannot drift apart.

``signal_to_noise``'s reading is ``S/N = 2H/h`` with peak-to-peak noise, and its
window is settled by ``DECISIONS.md`` §9 Q-B: 20× the half-height width, with 5×
the permitted fallback.  Its tolerance was re-measured at the 20× window for W12
and did not move: ``h`` is exact arithmetic over the caller's blank, so the only
estimator in the ratio is the apex height and the S/N residual **is** the height
residual (``TOLERANCES.md``).
"""

from __future__ import annotations

__all__ = ["TOLERANCE"]

#: metric id -> derived relative tolerance.  Mirrors the register in
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
