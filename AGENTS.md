# AGENTS.md — working rules for this repository

**Scope.** These rules bind any agent or contributor writing code in `janusson/ChromaMCP`. They
exist because this project's value is its *evidence*, not its features: every number it emits has to
be traceable to a named source and a stated tolerance, and nothing it emits may overstate what a
measurement can support.

**Authority when rules conflict:** this file → `SOURCES.md` → `TOLERANCES.md` → `PLAN.md` §3 in the
coordination hub → an individual task brief. A conflict is a finding to raise, not a choice to make
silently.

---

## 1. Scientific and data integrity

1. **No uncited formula ships.** Every metric in `src/chromamcp/metrics/` carries a formula id whose
   row exists in `SOURCES.md`. `SOURCES.md` already states the standard: a number without its
   formula's source is a **bug** in this repository, not an incomplete feature. Reason: the product
   claim is "this is the published formula", and that claim dies the first time a formula is
   transcribed from memory.
2. **Never invent a citation.** Transcribe the equation in the source's own wording. Never fabricate
   a clause number, a paragraph reference or an edition year. If the primary text is paywalled or
   unreadable, mark the row `secondary source — primary text not consulted`. Reason: a
   plausible-looking citation is worse than a missing one, because it survives review.
3. **A tolerance is a claim, and it is derived — not chosen.** Tolerances come from the measured
   convergence error of the estimator plus a stated margin, recorded in `TOLERANCES.md`. Reason: a
   tolerance picked by taste encodes the estimator's systematic bias as truth, so a wrong
   implementation passes its own test.
4. **Compare estimator against estimator, never against the generating parameter.** The independent
   expectation route is defined in `TOLERANCES.md`. Reason: a Gaussian whose generating σ implies
   `N = 10 000` does not yield a *measured* `N` of 10 000, and asserting that it does is precisely
   the defect this project exists to expose.
5. **State every convention in the docstring.** Where two conventions exist in the field — noise
   window, baseline model, width-at-height — the docstring names both, says which one this function
   implements, and which one it rejects. Reason: a silent convention choice is invisible to a
   reviewer and is the most common way two labs compute different numbers from the same peak.
6. **Numerics.** `float64` for intensity and time. Missing values are `NaN`, never `0`. Reason: a
   zero-filled gap is indistinguishable from a measured zero.
7. **Determinism is a gate, not a preference.** Same input file + same parameters + same versions →
   **byte-identical** serialised output. Pin float formatting in the serializer and test it. Reason:
   the evidence record *is* the deliverable, and one that changes between runs is not evidence.

## 2. Vocabulary this project must not use

The output is evidence a qualified person can review. It asserts nothing more.

- **Banned in code, docstrings, output field names, logs, and any document added here:**
  "validated", "confirmed", "compliant", "audit-ready", "certified", "regulatory-grade",
  "guaranteed".
- **Use instead:** *measured*, *observed*, *inferred*, *flagged*, *not-evaluated*.
- Reason: the tool measures method performance. It cannot validate a method, confirm an identity, or
  assert compliance — and a stray adjective in a field name becomes a claim in someone's SOP.

## 3. Scope boundaries

| In v0.1 / M1 | Out — do not start without a recorded decision |
|---|---|
| mzML chromatogram ingestion (TIC, XIC) | Any MCP SDK, tool or server (that is M2) |
| Pure metric functions, each cited and tolerance-stated | Sequence evaluation, drift or trend logic (M3) |
| Synthetic fixtures with analytic ground truth | Vendor raw-file parsers |
| Criteria-file parse + validate only | Network transport, hosted service, web UI |
| A provenance record per result | Instrument control or actuation of any kind |
| | Re-implementing peak detection/integration as a competing feature |
| | Any LLM in the compute path |

Changing that table is a decision for the maintainer, recorded in the coordination hub — not an
implementation choice made in a branch.

## 4. Formats

`mzML` only. Any other input, including every vendor binary format, is **refused with an explicit
conversion instruction** — never silently degraded. Reason: a refusal is honest and actionable; a
best-effort read of an unparsed format produces numbers that look real.

## 5. Dependencies

The scaffold ships **zero** runtime dependencies, and a test asserts it. Add one only with a recorded
reason at the point of addition. W1's expected set is the mzML reader stack, `numpy` and a
serialiser — nothing else. No peak-detection framework, no plotting library, no CLI framework unless
the gate needs it. Reason: an unused dependency is not free, and §6 makes every addition a licensing
question as well as a technical one.

## 6. Licence boundary

This repository is MIT. **Chromascope is GPL-3.0.** Read it for ideas; never copy code from it, or
from any other copyleft source, into this tree. If a design is borrowed the borrow is a *concept*,
and the implementation is written here. Reason: one copied function changes the licence of the whole
distribution.

## 7. Verification

- The gate is `make check` (`ruff format --check`, `ruff check`, `mypy`, `basedpyright`, `pytest`) —
  the same commands CI runs, so a green local run means what it means on a developer's machine.
- **Report the exact command and its observed output** when claiming the gate passed. Do not report
  confidence, and do not summarise a result you did not see.
- Every new rule of behaviour needs a test that fails without it. The property tests required by
  `TOLERANCES.md` are part of the gate, not optional extras.
- Bound any heavy job: thread caps plus bounded parallelism; never `-n auto`.

## 8. Data

- **M1 fixtures are synthetic only.** No vendor file, no client or former-employer data, and no
  published dataset inside the fixture suite.
- Public datasets are used only as recorded in the coordination hub
  (`~/Agent/Projects/ChromaMCP/DATASETS.md`), with the licence noted there.
- Never commit data files. Fetch scripts live with the project notes; the data stays outside the tree.

## 9. Publication and handoff

- **Nothing is published without the maintainer's approval of the exact text.** That covers the
  README, the repository description, release notes, and any post or write-up. Absent that approval,
  this repository has **no README by design** — its absence is not an oversight to be fixed.
- Work lands on a branch, **never `main`**. Do not push. Deliver a patch or bundle plus the exact
  commands to apply it, and state plainly that nothing was pushed.
- Collapse to one commit before handoff, leave `git status --porcelain` empty in the handoff tree,
  and verify the patch applies to a fresh clone of the intended remote.

## 10. When uncertain

- Two rules conflict: raise it, name both, and do not resolve it silently.
- A convention has no citable source: stop and say so. The correct output is a recorded gap, not a
  plausible default.
- An instruction would require inventing a citation, a tolerance or a default: refuse and report.
  Refusing is the correct behaviour here — it is what this repository is for.
