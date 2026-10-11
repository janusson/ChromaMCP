# SOURCES — the citation register

Every formula in `src/chromamcp/metrics/` gets a row here, and a metric whose formula id is
absent from this file fails the gate (`tests/test_sources_complete.py`, added in W3). A number
without its formula's source is not an incomplete feature in this repository; it is a bug.

**Status of this file:** skeleton, created in W0.2. The convention rows at the bottom were
verified 2026-10-11 from the sources named there; the *equations themselves* are `TO TRANSCRIBE`
from the primary texts during W3.

## Rules

1. Transcribe the equation in the source's own wording. Do not paraphrase a formula into your own
   notation and then cite the source for it.
2. If the primary text is paywalled or unreadable, mark the row
   `secondary source — primary text not consulted` rather than dressing a vendor summary up as
   authority.
3. Never invent a clause number, a paragraph reference or an edition year.
4. Where a convention is contested (noise definition, baseline model, width-at-height), record which
   convention this implementation follows **and** which one it rejects.

## Metric register

| Formula id | Metric | Source to transcribe from | Status |
|---|---|---|---|
| — | retention time `tR` | *n/a — a measurement, not a formula* | — |
| — | width at half height `w½` | *n/a — a measurement; the interpolation rule is ours and must be documented* | — |
| `plate_number_half_height` | `N` | USP 〈621〉 Chromatography (harmonised text) | `TO TRANSCRIBE` |
| `resolution_half_height` | `Rs` | USP 〈621〉 | `TO TRANSCRIBE` |
| `symmetry_factor_5pct` | `A` (symmetry/tailing factor) | USP 〈621〉 | `TO TRANSCRIBE` |
| `capacity_factor` | `k′` | USP 〈621〉 | `TO TRANSCRIBE` |
| `selectivity` | `α` | USP 〈621〉 | `TO TRANSCRIBE` |
| `signal_to_noise` | `S/N` | USP 〈621〉 noise-range definition | `TO TRANSCRIBE` |
| `peak_to_valley` | `p/v` | USP 〈621〉 | `TO TRANSCRIBE` |
| `peak_area`, `peak_height` | area, height | *n/a — model-dependent; the baseline rule must cite whatever it follows* | — |
| `rsd_replicates` | `%RSD` | USP 〈621〉 / standard precision practice | `TO TRANSCRIBE` |

**Anchors for the surrounding vocabulary:** USP 〈1058〉 (analytical instrument qualification) and
ICH Q2(R2) are named as neighbours in `PLAN.md`; neither is a source for a metric in this panel.

## Conventions verified 2026-10-11 (secondary sources — primary text still to be consulted)

Recorded so the implementer does not rediscover them, **not** as citations for the equations. Each
was read on the date shown from documentation, not from the pharmacopoeial text itself.

| Convention | What it is | Where it was read |
|---|---|---|
| Widths at half height | Resolution and plate number use peak width at **half height**; "tangent width" no longer appears | USP 〈621〉 harmonisation material; vendor whitepaper on the 〈621〉 revisions |
| Plate count → plate **number** | renamed | vendor support note on Empower 3.8.0 system-suitability updates |
| Tailing factor → **symmetry factor** | renamed; the *calculation* is unchanged | same vendor support note |
| Symmetry factor height | measured at **5 %** of peak height (one-twentieth) | USP 〈621〉 text as published in a harmonisation draft; vendor guidance |
| S/N noise range | noise taken over a range tied to the peak's **half-height width** (five times that width, from a blank at the expected retention time) | vendor support note; vendor whitepaper on the 〈621〉 revisions |
| Half-height multiplier for S/N | changed from 5 to 20 in one vendor's implementation guidance | vendor support note (an implementation detail, not the pharmacopoeia) |
| Legacy default limits | `k′ > 2`, `RSD ≤ 1 %` (n ≥ 5), `Rs > 2`, `T ≤ 2`, `N > 2000` are the **FDA-recommended** set quoted in vendor literature, not universal acceptance criteria | vendor technical note on automating system-suitability testing |

**Consequence for the design:** the default limits above may ship as a *template* in an example
criteria file, never as a baked-in opinion. The tool judges against the laboratory's own criteria
file (`M1-BRIEF.md` §6).
