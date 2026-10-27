# TOLERANCES — synthetic-fixture estimator disagreement evidence

A tolerance is a claim. This file records the evidence for every one of them, because a tolerance
chosen by taste silently encodes the estimator's bias as truth: if the fixtures assert that a
Gaussian whose generating σ implies `N = 10 000` yields a reported `N = 10 000`, then a wrong
implementation passes its own test and the number is worthless.

**Status of this file:** the tolerance register was filled in during W4 (2026-10-11) and two rows were
re-derived in W12 (2026-10-25). The historical residuals and margins below are retained. Nine reference bounds
come from measured residuals with a stated margin; the `%RSD` `1e-12` is a
historical numerical floor, not a derived bound (`AGENTS.md` §1.3). It remains
visible as historical evidence and is never applied to a caller's measurement.

**What these numbers are, and are not.** Each tolerance bounds **estimator disagreement** between the
package's working-rate route and an independent route on the fixture domain below — two sampling
intervals, 0.2 %-of-height Gaussian noise, eight seeds. It is not a measurement uncertainty, not an
acceptance limit for a laboratory method, and not transferable to an arbitrary trace: an unfamiliar
detector's noise, drift, saturation, overlap or coarse sampling is outside the domain that was
studied, and a result outside it is `not-evaluated` rather than inside a bound nobody measured.

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
5. Repeat on a noisy fixture: a reference bound must state the noise studied, so the
   noiseless residual alone does not set the reference bound.

## How the numbers below were obtained

`tests/synthetic/` builds each peak from a closed form and measures it two ways: the package's
working-rate estimator (W2/W3), and an **independent route** — a dense trace, crossings found by
bisection, an apex fitted by a different derivation — combined with the definition's own equation.
Two numbers are recorded per metric: the **discretisation error** (noiseless; the larger of the two
working rates) and the **noise residual** (the worst over 8 seeded noise realisations at both rates,
with Gaussian noise at 0.2 % of the peak height). For the nine trace metrics the fixture reference bound is the noise residual
`× 2` (the margin), rounded up. The `%RSD` historical floor is an exception,
explicitly recorded below. These reference bounds describe the experiment;
applicability to a production measurement remains `not-evaluated`.

## Tolerance register

| Metric id | Metric | Independent expectation route | Discretisation error (noiseless) | Noise residual (8 seeds × 2 rates) | Margin | Fixture reference bound |
|---|---|---|---|---|---|---|
| `plate_number` | `N` | dense trace · bisection half-height widths · `5.54 (tR/w½)²` | 1.1e-4 | 9.4e-3 | ×2 | 2.0e-2 |
| `resolution` | `Rs` | dense trace · bisection widths · `1.18 (tR2−tR1) / (w½1 + w½2)` | 5.7e-5 | 2.4e-2 | ×2 | 5.0e-2 |
| `symmetry_factor` | `A` (symmetry factor) | dense trace · bisection 5 % widths · `w0.05 / (2 · d_front)` | 1.1e-4 | 2.4e-2 | ×2 | 5.0e-2 |
| `capacity_factor` | `k′` | dense apex · `(tR − t0) / t0` | 9.0e-12 | 3.3e-3 | ×2 | 1.0e-2 |
| `selectivity` | `α` | dense apexes · `(tR2 − t0) / (tR1 − t0)` | 1.4e-8 | 6.9e-3 | ×2 | 1.5e-2 |
| `signal_to_noise` | `S/N` | dense apex height vs a blank region of known amplitude, **20× w½** window | < 1e-12 | 3.3e-3 | ×2 | 1.0e-2 |
| `peak_to_valley` | `p/v` | dense apexes and valley · `h_smaller / h_valley` | 2.5e-4 | 9.2e-3 | ×2 | 2.0e-2 |
| `peak_area` | `area` | dense trapezoid over the window | 2.2e-16 | 1.0e-3 | ×2 | 2.0e-3 |
| `peak_height` | `height` | dense apex height above the baseline | < 1e-12 | 3.3e-3 | ×2 | 1.0e-2 |
| `rsd_replicates` | `%RSD` | exact arithmetic (sample sd, n − 1) | 0 (exact) | 0 (exact) | — | 1e-12 |

The **Metric id** column is the id the code emits, so it matches `SOURCES.md`
and `FORMULA_IDS`. The **Fixture reference bound** column equals the historical
`TOLERANCE` mapping (`src/chromamcp/metrics/tolerances.py`), checked by
`tests/test_tolerances.py`. Production responses expose it only inside
`estimator_fixture_tolerance`, with `reference_bound`, `basis: relative`,
`domain_id: synthetic-w4-w12-v1`, `applicability: not-evaluated` and
`applied_bound: null`. The pure result exposes the same metadata property;
`tolerance` remains an internal compatibility field for panel construction.
Custom constructor bounds or unregistered metric ids receive no fixture metadata;
they cannot inherit the domain or derivation claim from a supplied number.
The criteria `verdict` is a separate field and measurement uncertainty is
separately `not-evaluated`. None of these reference numbers is a laboratory
acceptance limit or a measurement uncertainty.

## A4 applicability and zero policy (implementer decision, 2026-10-26)

The conservative implementation makes no automatic inference that a caller's
trace belongs to the fixture domain. Sampling interval or metric value alone
cannot establish its peak model, noise or detector behaviour. Every production
result therefore carries applicability `not-evaluated` and no applied bound,
including a result numerically equal to zero or one from a synthetic caller.
The fixture tests compare only fixtures they construct explicitly.

Relative disagreement is `abs(observed - expected) / abs(expected)` for nonzero
independent expected values. It is undefined at expected zero, even when the
observed value is also zero. No near-zero threshold or absolute floor is
introduced: there is no measured evidence here from which to derive one.
A small nonzero expected value still uses that relative expression only within
the recorded fixture experiment; the code makes no applicability inference from
it. The output's `zero_expected_policy` records this distinction.

The `%RSD` residual is zero on the fixed positive-response vector, with no margin
in the historical register. Multiplication of zero by a margin cannot derive
`1e-12`. Its metadata says `historical-floor-not-derived`; that value is
retained for historical traceability and is not an applied relative bound on
equal replicates (zero `%RSD`) or on any other production measurement.

## Complete bounded replay (A4)

`tests/synthetic/derive_tolerances.py` now replays **all eight seeds at both
working rates**, plus both noiseless rates, serially. It measures the dense
geometry independently and applies the registered equations directly; expected
values do not call production panel functions. Area uses an independent
`math.fsum` trapezoid reduction and `%RSD` uses explicit sample variance arithmetic.
S/N shares the supplied blank between routes; it measures apex-estimator
agreement, not blank adequacy. The blank uses fixed seed 990001 at 20× width.

Reproduce the checked Markdown evidence (numbers only, no trace files):

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  uv run python -m tests.synthetic.derive_tolerances
```

`tests/synthetic/tolerance-evidence.md` records actual maxima, twice each noisy
maximum, and the worst rate and seed, beside the retained historical reference
bound. The gate replays and compares the evidence artifact and checks each of
the 16 noisy cases per metric against its reference; for the nine trace metrics
it also checks the stated ×2 margin fits that reference. The `%RSD` vector has
no rate/noise-dependent estimator and is repeated only for a uniform replay
record. Its historical floor is marked rather than re-derived. The replay
reproduces the historical rounded residuals; it does not extend the studied
domain or establish production uncertainty.

Notes.  `A` uses the EMG fixture because a Gaussian cannot exercise tailing.  `k′` and `α` inherit any
error in the supplied `t0`, which is reported separately.  `Rs`'s residual is unchanged by the W12
coefficient correction: both routes combine the same widths with the same constant, so a relative
residual is scale-invariant.

## W12 re-derivations (2026-10-25)

Both numbers below come from `w12-2026-10-25/derive.py`, run against the tree at the reviewed commit;
its output is reproduced in the handover.

**`S/N`, at the 20× window.** Worst relative residual over 8 seeds × 2 rates: **3.302e-3** at
`Δt = 0.002` (seed 20261011) — identical to the 5× value, 3.302e-3. The tolerance therefore does not
move, and the reason is structural rather than lucky: `h` is exact arithmetic (peak-to-peak) over the
*blank the caller supplies*, and the same blank is used by both routes, so the window cancels out of
the ratio and the only estimator left is the apex height (3.302e-3 is the `peak_height` residual). The
window does change the **reported value** — 162.18 against 166.97 from the same seed, a 2.9 % lower
`S/N` at 20× — which is why the convention had to be corrected even though the tolerance did not.

That also states the limit honestly: the shipped `1.0e-2` bounds the *estimator* at the working
sampling rate on this fixture domain. It does not bound how well a 20× or 5× window estimates the
noise of a real trace, because no independent route for that exists — the window is a convention, and
its adequacy is a property of the chromatogram, not of the code.

**`peak_area`, reconciled.** The register recorded a residual of `1.0e-3` and shipped `2.5e-3`, which
is not what the recorded recipe produces (`1.0e-3 × 2 = 2.0e-3`). Re-measured: worst residual
**9.969e-4** over 8 seeds × 2 rates, so the recorded residual was right and the shipped number was
not derived. The shipped value is now **2.0e-3**, the recipe's own output, and the ground-truth
residual sits at half of it.

**Rounding, stated.** The margin is `× 2` with the result rounded up to a short number, but the rows
were not rounded by one uniform rule (`selectivity` 1.38e-2 → 1.5e-2, `peak_height` 6.6e-3 → 1.0e-2).
The values are as measured and as shipped; the rule is not uniform, and that is recorded here rather
than restated as a system.

## Sampling rates used

Coarse `Δt = 0.002 min` and fine `Δt = 0.001 min`; the independent route runs at `Δt = 1e-5 min`.
The fixture reference bounds hold at **both** working rates, as the gate
requires. The worst seed and rate vary by metric; the checked evidence records
them (symmetry factor and peak-to-valley have their worst noisy residual at the
finer rate).
