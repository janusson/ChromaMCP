# TOLERANCES — how each metric's acceptance tolerance was derived

A tolerance is a claim. This file records the evidence for every one of them, because a tolerance
chosen by taste silently encodes the estimator's bias as truth: if the fixtures assert that a
Gaussian whose generating σ implies `N = 10 000` yields a reported `N = 10 000`, then a wrong
implementation passes its own test and the number is worthless.

**Status of this file:** skeleton, created in W0.2. The procedure below is the requirement; the
numbers are filled in during W4, from measurement.

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

## Tolerance register

| Metric | Independent expectation route | Measured convergence error | Margin | Tolerance shipped | Notes |
|---|---|---|---|---|---|
| `N` | numeric widths at half height on a dense synthetic trace | `TBD (W4)` | `TBD` | `TBD` | |
| `Rs` | numeric widths at half height for a controlled pair | `TBD (W4)` | `TBD` | `TBD` | |
| `A` (symmetry factor) | numeric widths at 5 % height plus the front distance at that height | `TBD (W4)` | `TBD` | `TBD` | EMG fixtures only; a Gaussian cannot exercise tailing |
| `k′` | from the supplied `t0` and the apex | `TBD (W4)` | `TBD` | `TBD` | inherits any `t0` estimation error, which must be reported separately |
| `S/N` | known noise amplitude in the fixture vs the chosen noise-window definition | `TBD (W4)` | `TBD` | `TBD` | depends on the noise convention chosen in `SOURCES.md` |
| `p/v` | numeric valley height between a controlled pair | `TBD (W4)` | `TBD` | `TBD` | |
| `%RSD` | analytic: replicate values supplied with a known spread | `TBD (W4)` | `TBD` | `TBD` | pure arithmetic; the tolerance should be tight |

## Sampling rates used

`TBD (W4)` — at least two rates, so that stability of the estimator across sampling is demonstrated
rather than assumed.
