# Scope questions raised by the third-party "handoff report" (2026-10-11)

**This is a finding, not a decision.** Per `AGENTS.md` §3, the scope table is changed only by a
decision the maintainer records in the private coordination record for this project — not by an
implementation choice made in a branch. That record is not distributed with this repository, and
each item names both readings and what a decision would have to settle. **All three are settled
now:** the answers are in `DECISIONS.md` §4 (Q1 and Q3 recorded as defaults on 2026-10-11, Q2
parked as W15), so this file is the finding those decisions were made against, not an open list.

**What prompted it.** An external report proposes a ChromaMCP MCP server — JSON-Schema tool
definitions plus a pytest suite — covering system suitability, USP 〈621〉 method scaling,
`S/N`, USP 〈1058〉 classification, and ICH Q2(R2) evaluation. Three of its surfaces raise questions
this repository's rules already speak to.

## Q1 — Timing: does this open M2, or does it ask M1 to be skipped?

- **Proposal:** build and deploy `src/chroma_mcp/server.py` with tool schemas, "for immediate
  deployment" over stdio/SSE.
- **Rule in tension:** `AGENTS.md` §3 — any MCP SDK, tool or server is **M2**; M1 is mzML (TIC/XIC)
  ingestion, cited pure metric functions, synthetic fixtures, and a criteria-file parse.
- **Both sides:** the surface described is M2 by the current plan, and it contains no M1 material —
  no mzML read, no criteria-file parse, no fixtures. Either M1 is declared far enough along to open
  M2, or the report is out of order with the plan.
- **Decision needed:** whether M2 is opened, and on what M1 exit evidence.

## Q2 — Is the column-scaling ("method transfer") family a metric surface?

- **Proposal:** a `modernize_usp621_method` function computing scaled flow `F2`, injection volume
  `V2`, gradient segment times `tG2`, and an `L/dp` check against a −25 %/+50 % window.
- **Record in tension:** the `SOURCES.md` metric register (lines 28–36) lists `tR, w½, N, Rs, A,
  k′, α, S/N, p/v, area, height, %RSD`. The scaling family is **absent**, so it has no formula id
  and no source row.
- **Both sides:** it is a plausible 〈621〉 surface, but each of its equations arrives uncited, and
  its window is a *chosen* number — which `TOLERANCES.md` forbids shipping without a measured
  derivation plus a stated margin.
- **Decision needed:** admit the family to the register (with source rows transcribed from the
  primary text), or keep it out.

## Q3 — USP 〈1058〉 AIQ and ICH Q2(R2): sources, or neighbours?

- **Proposal:** `evaluate_aiq_classification` (Group A/B/C with 4Q protocol strings) and a
  Q2(R2) evaluation returning `r²`, `%RSD` and recovery against pass/fail thresholds.
- **Record in tension:** `SOURCES.md` line 39 — USP 〈1058〉 and ICH Q2(R2) are "named as neighbours
  in `PLAN.md`; neither is a source for a metric in this panel."
- **Both sides:** they can remain reference vocabulary *around* the metrics, or be promoted to
  first-class surfaces — but promotion means locating primary sources and deriving tolerances for
  the numbers the report asserts (`r² ≥ 0.999`, recovery 98–102 %) yet does not cite.
- **Decision needed:** keep as neighbours, or promote them with sources.

## Also raised (consequences of §1, §2, §5, §7 — not scope questions)

- **Vocabulary:** the report's output field names and prose use terms `AGENTS.md` §2 bans —
  e.g. `validation_pass_status`, `ldp_compliant`, "confirm all … pass".
- **Tolerances as defaults:** `k′ > 2`, `N > 2000`, `%RSD ≤ 1`, `Rs > 2`, `T ≤ 2` are baked into the
  functions; `SOURCES.md` 54–58 records these as FDA-vendor guidance that may ship "as a template in
  an example criteria file, never as a baked-in opinion."
- **Provenance:** the report asserts it contains "all the exact" 〈621〉/〈1058〉/Q2(R2) equations; a
  report is not a primary source (`SOURCES.md` rules 1–3).
- **Gate:** it instructs bare `pytest test_chroma_mcp.py` after `pip install … numpy`; the gate is
  `make check` (`.github/workflows/ci.yml`). The report's instruction predates `numpy` being declared
  as a dependency here (W1).
- **The pasted suite would not run as given:** `concs =`, `responses =` and `rep_areas =` are empty
  (`SyntaxError`), and one assertion compares a list to a float (`TypeError`).
