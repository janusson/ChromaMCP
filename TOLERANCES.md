# TOLERANCES — how each metric's acceptance tolerance was derived

A tolerance is a claim. This file records the evidence for every one of them, because a tolerance
chosen by taste silently encodes the estimator's bias as truth: if the fixtures assert that a
Gaussian whose generating σ implies `N = 10 000` yields a reported `N = 10 000`, then a wrong
implementation passes its own test and the number is worthless.

**Status of this file:** the tolerance register was filled in during W4 (2026-10-11) from the
derivation in `tests/synthetic/`.  Every number below is **measured, not chosen** (`AGENTS.md` §1.3).

## The procedure (W4)

1. Generate a trace whose peak geometry is known by construction (Gaussian; exponentially modified
   Gaussian for controlled tailing; a controlled pair for `Rs`; a controlled valley for `p/v`; a
   noise region of known amplitude for `S/N`).
2. Compute the **expected value by an independent route at the estimator level** — extract the widths
   numerically at the exact heights the definition names, from a dense trace, and combine them with
   the definition's own equation. Never compare the estimator against the generating parameter.
3. Measure how the estimator converges as the sampling interval shrinks. The residual at the working
   sampling rate **is** the discretisation error.
4. Set the tolerance from that measured error plus a stated margin. Record both numbers here.
5. Repeat on a noisy fixture: the tolerance reported to a user must be honest about noise, so the
   noiseless number is not the one that ships.

## How the numbers below were obtained

`tests/synthetic/` builds each peak from a closed form and measures it two ways: the package's
working-rate estimator (W2/W3), and an **independent route** — a dense trace, crossings found by
bisection, an apex fitted by a different derivation — combined with the definition's own equation.
Two numbers are recorded per metric: the **discretisation error** (noiseless; the larger of the two
working rates) and the **noise residual** (the worst over 8 seeded noise realisations at both rates,
with Gaussian noise at 0.2 % of the peak height).  The shipped tolerance is the noise residual
`× 2` (the margin), rounded up — honest about a noisy single scan, which is what actually ships.

## Tolerance register

| Metric id | Metric | Independent expectation route | Discretisation error (noiseless) | Noise residual (8 seeds × 2 rates) | Margin | Tolerance shipped |
|---|---|---|---|---|---|---|
| `plate_number` | `N` | dense trace · bisection half-height widths · `5.54 (tR/w½)²` | 1.1e-4 | 9.4e-3 | ×2 | 2.0e-2 |
| `resolution` | `Rs` | dense trace · bisection widths · `2 (tR2−tR1) / (w½1 + w½2)` | 5.7e-5 | 2.4e-2 | ×2 | 5.0e-2 |
| `symmetry_factor` | `A` (symmetry factor) | dense trace · bisection 5 % widths · `w0.05 / (2 · d_front)` | 1.1e-4 | 2.4e-2 | ×2 | 5.0e-2 |
| `capacity_factor` | `k′` | dense apex · `(tR − t0) / t0` | 9.0e-12 | 3.3e-3 | ×2 | 1.0e-2 |
| `selectivity` | `α` | dense apexes · `(tR2 − t0) / (tR1 − t0)` | 1.4e-8 | 6.9e-3 | ×2 | 1.5e-2 |
| `signal_to_noise` | `S/N` | dense apex height vs a blank region of known amplitude | < 1e-12 | 3.3e-3 | ×2 | 1.0e-2 |
| `peak_to_valley` | `p/v` | dense apexes and valley · `h_smaller / h_valley` | 2.5e-4 | 9.2e-3 | ×2 | 2.0e-2 |
| `peak_area` | `area` | dense trapezoid over the window | 2.2e-16 | 1.0e-3 | ×2 | 2.5e-3 |
| `peak_height` | `height` | dense apex height above the baseline | < 1e-12 | 3.3e-3 | ×2 | 1.0e-2 |
| `rsd_replicates` | `%RSD` | exact arithmetic (sample sd, n − 1) | 0 (exact) | 0 (exact) | — | 1e-12 |

The **Metric id** column is the id the code emits, so it matches `SOURCES.md` and `FORMULA_IDS`. The
**Tolerance shipped** column is the value the panel attaches to every result
(`src/chromamcp/metrics/tolerances.py`); `tests/test_tolerances.py` asserts the column equals that
mapping, so the shipped number and the recorded derivation cannot drift apart. Every shipped
tolerance is on the **relative** basis — a fraction of the independently expected value — and the
provenance record states that basis (`tolerance_basis`), so a bare number cannot be read as an
absolute bound in the metric's own unit.

Notes.  These are the tolerances the W4 suite asserts against; they are relative.  `A` uses the EMG
fixture because a Gaussian cannot exercise tailing.  `k′` and `α` inherit any error in the supplied
`t0`, which is reported separately.  `S/N` carries the `P1` caveat — its convention is not settled —
so its tolerance may move with the convention.

## Sampling rates used

Coarse `Δt = 0.002 min` and fine `Δt = 0.001 min`; the independent route runs at `Δt = 1e-5 min`.
The tolerance holds at **both** working rates, as the gate requires; the residual is larger at the
coarser one.
