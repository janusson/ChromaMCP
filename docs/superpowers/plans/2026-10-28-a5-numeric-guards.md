# A5 Numeric Guards Implementation Plan

> **For agentic workers:** Implement this plan inline with test-first steps. Track each step with a checkbox.

**Goal:** Make each pure metric refuse non-finite inputs and arithmetic results, and make peak-area integration require finite, strictly increasing values in its selected window.

**Architecture:** Keep the existing pure functions and error type. Add shared finite-result checks at the arithmetic boundary and a `MetricResult` invariant so a non-finite value cannot escape through direct construction.

**Tech Stack:** Python 3.13, NumPy, pytest, ruff, mypy, basedpyright.

**Spec:** `../Hermes/Projects/ChromaMCP/SCIENTIFIC-AUDIT-2026-10-25.md`, A5 acceptance; repository `AGENTS.md` §§1 and 7.

## Global Constraints

- Every metric carries its registered formula id from `FORMULA_IDS`.
- Use `float64` for intensity and time; missing values are `NaN`, never `0`.
- Keep outputs evidence-bounded and deterministic.
- Use only synthetic inputs; add no dependency; do not push.

## Review Focus

- Non-finite time or intensity inside the area window must raise `MetricInputError`.
- Equal or decreasing selected times must raise `MetricInputError`.
- Overflow in a ratio, difference, or integral must not return a number.
- A direct `MetricResult` construction must reject a non-finite value.
- Finite values outside the selected integration window do not affect the area.

---

### Task 1: Reproduce invalid peak-area and result behavior

**Files:** `tests/test_metrics.py`.

- [x] Add direct tests for non-finite selected time and intensity, equal/decreasing selected times, overflowing area, and direct `MetricResult` construction with `NaN`.
- [x] Run each new test and confirm it fails for the stated missing refusal.

### Task 2: Guard arithmetic across pure metrics

**Files:** `src/chromamcp/metrics/panel.py`, `src/chromamcp/metrics/result.py`, `tests/test_metrics.py`.

- [x] Add direct overflow cases for representative ratio and spread calculations.
- [x] Run the cases to confirm they expose a returned non-finite result or an exception outside `MetricInputError`.
- [x] Add finite-result checks for all metric arithmetic; require finite, strictly increasing time and finite arrays in the selected area window; reject non-finite `MetricResult.value`.
- [x] Run the focused metric tests, then the exact repository gate with one-thread numeric libraries.

### Task 3: Prepare a clean local handoff

**Files:** metric source/tests, this plan, A5 handoff artifacts outside the repository.

- [x] Commit one repair commit on `codex/a5-numeric-guards`.
- [x] Produce a patch and bundle, apply the patch to a fresh clone restored to `0d1d9bd`, and run the same gate.
- [x] Confirm the repair worktree is clean and provide the exact command outputs; do not push or merge.
