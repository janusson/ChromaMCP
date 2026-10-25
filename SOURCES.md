# SOURCES — the citation register

Every formula in `src/chromamcp/metrics/` gets a row here, and a metric whose formula id is
absent from this file fails the gate (`tests/test_sources_complete.py`). A number without its
formula's source is not an incomplete feature in this repository; it is a bug.

**Status of this file.** The register was filled in W3 (2026-10-11) and transcribed from the
primary texts in W12 (2026-10-25). The 〈621〉 rows are read from two free documents, both named
below; every row that survives the comparison says `transcribed`, and the two rows W12 corrected
say what was wrong. A row that this project computes itself, rather than transcribing, says `ours`.

**Revision anchor.** USP 〈621〉 Chromatography, **Stage 4 harmonisation, official 1 December 2022**.
Later revisions of its system-sensitivity and peak-symmetry subsections were **not** read, so no
claim is made about them. JP XVIII General Tests **2.01 Liquid Chromatography**, read from the
Ministry of Health, Labour and Welfare PDF (5 930 309 bytes, sha256
`0242677d3e714f19e84adb982528d5382e9f9fe1a0db2fab58c6a844fb269f26`).

| # | Source | Where |
|---|---|---|
| 1 | USP, 〈621〉 Chromatography — Stage 4 Harmonization (PDG), official 1 Dec 2022 | `https://www.usp.org/sites/default/files/usp/document/harmonization/gen-chapter/harmonization-november-2021-m99380.pdf` — the file answers HTTP 403 to a non-browser client and was read through a reader proxy; fetched copy sha256 `9c10d608…` |
| 2 | JP XVIII, General Tests 2.01 Liquid Chromatography | `https://www.mhlw.go.jp/content/11120000/000945683.pdf` |

## Rules

1. Transcribe the equation in the source's own wording. Do not paraphrase a formula into your own
   notation and then cite the source for it.
2. If the primary text is paywalled or unreadable, mark the row `S` — `secondary source, primary
   text not consulted` — rather than dressing a vendor summary up as authority.
3. Never invent a clause number, a paragraph reference or an edition year.
4. Where a convention is contested (noise definition, baseline model, width-at-height), record which
   convention this implementation follows **and** which one it rejects.

## Metric register

| Formula id | Metric | Equation as transcribed | Source | Status |
|---|---|---|---|---|
| `plate_number_half_height` | `N` | `N = 5.54 (tR / w½)²` | USP `N = 5.54 (tR/W)²`, `W` = peak width at half-height; JP `N = 5.54 × tR² / W0.5h²` | transcribed |
| `resolution_half_height` | `Rs` | `Rs = 1.18 (tR2 − tR1) / (w½1 + w½2)` | USP `Rs = 1.18 (tR2 − tR1) / (W0.5h1 + W0.5h2)`; JP `RS = 1.18 × (tR2 − tR1) / (W0.5h1 + W0.5h2)`, widths at half peak height | transcribed — W12 corrected the coefficient from `2`, which belongs to the base-width form |
| `symmetry_factor_5pct` | `A` (symmetry factor) | `A = w0.05 / (2 · d_front)` | USP `As = W0.05 / …`; JP `S = W0.05h / (2f)`, `W0.05h` at one-twentieth of the peak height, `f` the distance from the peak maximum perpendicular to the leading edge at that height | transcribed |
| `capacity_factor` | `k′` | `k′ = (tR − t0) / t0` | JP retention factor, same form | transcribed — `t0` is supplied, never inferred |
| `selectivity` | `α` | `α = (tR2 − t0) / (tR1 − t0)` | JP `a = (tR2 − t0) / (tR1 − t0)` | transcribed — the code's form is the pharmacopoeial one; `k′2 / k′1` is the algebraic equivalent |
| `signal_to_noise` | `S/N` | `S/N = 2H / h`, `h` = peak-to-peak noise over **20×** w½ (5× the permitted fallback) | USP: `h` "observed over a distance equal to 20 times the width at half-height"; "If a baseline of 20 times the width at half-height is not obtainable because of peaks due to the solvents …, a baseline of at least 5 times the width at half-height is permitted." JP: measured over a range 20 times the peak width at the centre point of peak height | transcribed — W12 corrected the hierarchy; 20× is primary, 5× the fallback |
| `peak_to_valley` | `p/v` | `p/v = Hp / Hv` | USP `p/v = Hp/Hv`; JP `Hp` = height from the baseline of the minor peak, `Hv` = height of the lowest point between the two | transcribed |
| `rsd_replicates` | `%RSD` | `100 / x̄ · √(Σ(xi − x̄)² / (n − 1))` | JP `RSD = 100/x̄ · √(Σ(xi − x̄)²/(n − 1))` | transcribed |
| `peak_area` | area | trapezoid of (intensity − baseline) over the window | *n/a — model-dependent; the baseline rule must cite whatever it follows* | `ours` — `geometry/baseline.py` (`LINEAR`, `VALLEY_DROP`; `TANGENT_SKIM` refused in M1) |
| `peak_height` | height | `y_apex − baseline(t_apex)` | *n/a — model-dependent* | `ours` — same baseline rule |
| — | retention time `tR` | apex time (W2 three-point parabolic interpolation) | *n/a — a measurement, not a formula* | `ours` — `geometry/peaks.py` |
| — | width at half height `w½` | width at ½ of peak height above the baseline (W2, first crossing, linear interpolation) | *n/a — a measurement; the interpolation rule is ours* | `ours` — `geometry/peaks.py` |

**Anchors for the surrounding vocabulary:** USP 〈1058〉 (analytical instrument qualification) and
ICH Q2(R2) are named as neighbours in `PLAN.md`; neither is a source for a metric in this panel.

## Conventions read from the primary text (2026-10-12)

| Convention | What the text says | Where |
|---|---|---|
| S/N noise range | `h` is taken over **20×** the width at half-height; "at least 5 times" is permitted only where a 20× baseline is unobtainable (solvent peaks, gradient) | USP 〈621〉 Stage 4; JP XVIII §2.01 |
| Widths at half height | Resolution and plate number use the peak width at **half height**; the resolved pair carries the `1.18` coefficient | USP 〈621〉 Stage 4; JP XVIII §2.01 |
| Symmetry factor height | measured at **5 %** (one-twentieth) of peak height; the quantity is named symmetry factor (`As`), and the calculation is unchanged from the older tailing factor | USP 〈621〉 Stage 4; JP XVIII §2.01 |
| Plate count → plate **number** | renamed | USP 〈621〉 Stage 4 |
| Legacy default limits | `k′ > 2`, `RSD ≤ 1 %` (n ≥ 5), `Rs > 2`, `T ≤ 2`, `N > 2000` are the **FDA-recommended** set quoted in vendor literature, not universal acceptance criteria | vendor technical note on automating system-suitability testing (secondary, read 2026-10-11) |

**Consequence for the design:** the default limits above may ship as a *template* in an example
criteria file, never as a baked-in opinion. The tool judges against the laboratory's own criteria
file (`M1-BRIEF.md` §6).
