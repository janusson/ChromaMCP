# Criteria parse contract — A2, 2026-10-26

This is a project schema decision, not a laboratory limit or an evaluation rule.
The M1 brief §6 example places `n` on `resolution`, while its inline comment
reserves it for a replicate-based metric. The earlier parser accepted it on any
metric. The A2 repair follows the explicit comment and refuses the ambiguous use.

- `n` is required for `rsd_replicates` and must be an integer at least two.
  Every other metric refuses the key, including `n: null`. No replicate set or
  aggregation is inferred. A future sequence layer needs explicit replicate identity.
- Pairwise metrics require `between` as two distinct non-empty peak names in
  caller order. Names are preserved exactly; the parser does not decide adjacency
  or retention order. Repetition of the same exact name is refused. Non-pairwise
  metrics keep the existing refusal of a non-null `between`.
- Mapping keys must occur once at every level. YAML merges may supply unique
  keys, but a merge followed by replacement of a key is refused, just like two
  explicit occurrences. The local SafeLoader subclass retains safe construction.
- Every numeric limit must have a finite float64 representation. Booleans,
  non-finite values and integer overflow are refused with `CriteriaError`.
- The laboratory's written `source` remains required. Parsing does not apply
  the criterion, set a limit, or compute a criteria verdict.

These choices resolve the parse ambiguity for this repair. They do not open M3.
