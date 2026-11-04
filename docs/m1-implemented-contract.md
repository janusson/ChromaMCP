# M1 — the implemented contract

This is a map of what the M1 milestone implements, what it refuses, and what it does not yet
measure. It is deliberately short: the authoritative statements live in the registers below, and
nothing here restates them.

| Question | Authority |
|---|---|
| What the project must never claim, and the v0.1 scope table | `AGENTS.md` §1–§3 |
| The equation behind each metric, and its source | `SOURCES.md` |
| The measured basis for each fixture bound | `TOLERANCES.md` |
| The mzML subset, and the unit rules | `docs/axis-units.md` |
| The criteria-file shape | `docs/criteria-contract.md` |
| Client configuration | `docs/clients/` |

## What M1 is

A stdio MCP server that reads mzML chromatogram channels, measures peak geometry, and reports a
system-suitability panel in which every number carries the formula id it was computed from, the
source that formula was transcribed from, and the baseline it was measured against. The compute
path contains no LLM: `server/` is the only package that imports the MCP SDK.

## Scope

| In M1 | Not in M1 |
|---|---|
| mzML chromatogram ingestion (TIC, XIC, BPC) | Vendor raw formats — refused with a conversion instruction |
| Pure metric functions with cited formula ids | Peak detection or integration as a feature |
| Synthetic fixtures with analytic ground truth | Sequence evaluation, drift and trend logic (M3) |
| Criteria-file parse and validate only | Criteria evaluation (M3) |
| One provenance record per result | Network transport, web UI, instrument control |

## Ingestion: supported, refused, never done

Supported: inline `binaryDataArray` content for TIC (`MS:1000235`), XIC (`MS:1000627`) and BPC
(`MS:1000628`); 32- and 64-bit precision; zlib compression; an explicit time `unitAccession`
(second or minute); declared `count` attributes checked against the child elements.

Refused, each with a reason: the `indexedmzML` wrapper; `referenceableParamGroupRef` terms;
MS-Numpress arrays; an array with no precision term; a time unit given by name without an
accession, or none at all; any vendor binary format.

Never done: intensity conversion, a unit inferred from the chromatogram kind, full schema or
controlled-vocabulary checking, or reading spectra. Every response repeats the reader scope.

## Geometry

An apex is the three-point parabolic interpolation of the baseline-subtracted trace when the
maximum is an interior sample, the triple is concave, and the fitted vertex falls strictly between
its neighbours; otherwise the discrete sample maximum is reported with `interpolated=False`. A
discrete apex is never presented as an interpolated one.

A width at a fraction of height is the first crossing of that level, linearly interpolated between
the bracketing samples, measured above an explicit baseline that is never defaulted to zero. A
trace containing a non-finite sample is refused rather than measured around the gap. `TANGENT_SKIM`
is refused, not approximated.

## The panel

Ten metric ids, each with a formula id registered in `SOURCES.md`:

| Metric id | Unit |
|---|---|
| `plate_number`, `resolution`, `symmetry_factor`, `capacity_factor`, `selectivity`, `signal_to_noise`, `peak_to_valley` | dimensionless |
| `peak_height` | the caller's intensity label, else `unknown` |
| `peak_area` | the caller's intensity label plus `·min` |
| `rsd_replicates` | `%` |

Time is minutes throughout. The reader retains the decoded source time, the three source unit
attributes and the conversion factor. Intensity labels are opaque strings: retaining one does not
establish that it is dimensionally correct. `peak_area` requires a minutes grid; that is a stated
precondition, not a value the function is able to check.

## What the tolerances mean

`TOLERANCES.md` records, per metric, the measured disagreement between this implementation and an
independent estimator route on the fixture domain `synthetic-w4-w12-v1`. Each production result
carries that record as `estimator_fixture_tolerance` with `applicability: not-evaluated` and
`applied_bound: null`: no trace is asserted to belong to the studied domain. These bounds are not
measurement uncertainty and not laboratory acceptance limits.

Every result also carries a provenance record, serialised deterministically: two runs over the same
input produce byte-identical output.

## MCP surface

Seven tools. Five are implemented: `load_chromatogram`, `summarise_chromatogram`, `integrate_peaks`,
`compute_suitability`, `release_reference`. Two are refusal stubs for M3: `assess_sequence` and
`trend_qc` raise an explicit "not implemented in this unit" rather than returning a number.

`integrate_peaks` measures caller-supplied index windows through the geometry above. It detects no
peaks and chooses no windows; supplying the window is the caller's step.

## Filesystem boundary

Every file-reading tool is confined to `CHROMAMCP_ALLOWED_ROOT`, defaulting to the working
directory. The path is symlink-resolved before the check, so a link that escapes is refused like a
literal outside path. A source is read once and its `fstat` identity compared before and after, so
the reported hash and the returned bytes describe the same input.

## Verification evidence

`make check` runs `ruff format --check`, `ruff check`, `mypy`, `basedpyright` and `pytest`; CI runs
the same commands from `uv.lock`. The fixture suite is synthetic and analytic: each peak has a
closed-form generating geometry, and each metric is compared against an independent estimator route
rather than against the generating parameter.

## What is not established

- Numerical estimator behaviour is tested on synthetic fixtures. ChromaMCP has not been evaluated
  on a real laboratory method, a vendor trace, or a published dataset, and this repository makes no
  claim about that.
- The transcription in `SOURCES.md` was checked against two free documents. The USP text was read
  through a reader proxy because the publisher's site refuses non-browser clients, and the register
  says so. A person should check the transcribed rows against a directly obtained copy before any
  claim about method performance leaves this repository.
- Applicability of any recorded bound to an arbitrary trace is `not-evaluated`.
- Sequence and trend evaluation are M3 and absent.

Some docstrings cite milestone briefs that are private to the maintainer and are not distributed
with this repository. Those citations identify an internal decision; they are not documents a
reader here can open.
