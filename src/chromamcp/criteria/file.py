"""The criteria-file contract (W6) — parse and validate only.

The user supplies their own acceptance limits; the tool never bakes in an
opinion (``M1-BRIEF.md`` §6).  This module reads the ``§6`` file, checks it
against the documented shape, and **stops there**: it does not evaluate a
sequence, a drift or a trend.  Evaluation is M3 (``AGENTS.md`` §3).

Examples of what is *refused*, each with an explicit, actionable message:

- a ``metric`` that is not a panel metric id;
- an ``operator`` outside ``>= > <= <``;
- a pairwise metric without its ``between`` peak names (or a non-pairwise metric
  that carries them);
- a replicate-based metric without ``n``;
- a file with **no ``source``** — required by design, because the tool's job is
  to apply the laboratory's *written* criteria, and a criteria file with no
  provenance is the failure mode this project exists to avoid.

One field needs care: ``on`` is a **YAML 1.1 boolean**, so an unquoted ``on:``
is read as ``True``.  The reader detects that and asks for the key to be quoted
(``"on": [...]``); see :func:`_reject_unknown`.

The file is **YAML** (the syntax ``M1-BRIEF.md`` §6 shows).  That is the one new
dependency W6 adds (``pyyaml``; ``AGENTS.md`` §5 records the reason), and it is
read through a local :class:`yaml.SafeLoader` subclass, which constructs no
arbitrary objects and refuses duplicate keys, including merged overrides.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from chromamcp.errors import CriteriaError, InaccessiblePathError
from chromamcp.metrics import FORMULA_IDS

__all__ = [
    "OPERATORS",
    "PAIRWISE_METRICS",
    "PANEL_METRICS",
    "REPLICATE_METRICS",
    "TECHNIQUES",
    "AppliesTo",
    "CriteriaFile",
    "Criterion",
    "load_criteria",
    "parse_criteria",
]

#: The comparison operators a limit may use (``M1-BRIEF.md`` §6).
OPERATORS = frozenset({">=", ">", "<=", "<"})
#: The techniques a criteria file may target.
TECHNIQUES = frozenset({"LC", "GC"})
#: Every metric id the panel can emit — the ids a ``metric`` field may name.
PANEL_METRICS = frozenset(FORMULA_IDS)
#: Metrics that describe a *pair* of peaks, and so require ``between``.
PAIRWISE_METRICS = frozenset({"resolution", "selectivity", "peak_to_valley"})
#: Metrics defined over replicate injections, and so requiring ``n``.
REPLICATE_METRICS = frozenset({"rsd_replicates"})

_TOP_LEVEL_KEYS = frozenset({"criteria", "source", "applies_to", "limits"})
_CRITERION_KEYS = frozenset({"metric", "between", "operator", "value", "n", "on"})


@dataclass(frozen=True, slots=True)
class Criterion:
    """One limit: distinct pair names; ``n`` only for replicate-based metrics."""

    metric: str
    operator: str
    value: float
    between: tuple[str, str] | None = None
    n: int | None = None
    on: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AppliesTo:
    """What the criteria file is written for."""

    technique: str
    detection: str


@dataclass(frozen=True, slots=True)
class CriteriaFile:
    """A criteria file that satisfies the §6 contract."""

    identifier: str
    source: str
    applies_to: AppliesTo
    limits: tuple[Criterion, ...]


def load_criteria(path: str | Path) -> CriteriaFile:
    """Read and validate the criteria file at *path* (YAML, ``M1-BRIEF.md`` §6)."""
    resolved = Path(path)
    if not resolved.exists():
        raise InaccessiblePathError(f"No such criteria file: '{resolved}'.")
    if not resolved.is_file():
        raise InaccessiblePathError(f"Not a regular file: '{resolved}'.")
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise InaccessiblePathError(f"Could not read '{resolved}': {exc}") from exc
    return parse_criteria(text)


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML construction with no silent mapping-key replacement."""

    def construct_mapping(
        self, node: yaml.nodes.MappingNode, deep: bool = False
    ) -> dict[Hashable, object]:
        self.flatten_mapping(node)
        keys: set[object] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in keys
                keys.add(key)
            except TypeError as exc:
                raise CriteriaError(
                    "criteria mapping keys must be scalar values."
                ) from exc
            if duplicate:
                raise CriteriaError(
                    f"duplicate mapping key {key!r} at line {key_node.start_mark.line + 1}; "
                    "state each key once, without merged overrides."
                )
        return super().construct_mapping(node, deep=deep)


def parse_criteria(text: str) -> CriteriaFile:
    """Parse and validate criteria *text*, refusing anything outside the §6 shape."""
    try:
        raw = yaml.load(text, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise CriteriaError(f"the criteria file is not valid YAML: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise CriteriaError(
            "the criteria file must be a YAML mapping at the top level."
        )
    _reject_unknown(raw, _TOP_LEVEL_KEYS, "the criteria file")
    return CriteriaFile(
        identifier=_text(raw, "criteria"),
        source=_text(raw, "source"),
        applies_to=_applies_to(raw.get("applies_to")),
        limits=_limits(raw.get("limits")),
    )


def _text(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CriteriaError(f"'{key}' must be a non-empty string.")
    return value


def _reject_unknown(
    mapping: Mapping[str, object], allowed: frozenset[str], where: str
) -> None:
    boolean_keys = sorted(str(key) for key in mapping if isinstance(key, bool))
    if boolean_keys:
        raise CriteriaError(
            f"{where} has a YAML boolean key ({boolean_keys}). In YAML 1.1 an "
            f"unquoted 'on' (or 'off', 'yes', 'no') is read as a boolean, so the "
            f'field must be quoted — e.g. "on": [...] — before it is retried.'
        )
    unknown = sorted(str(key) for key in set(mapping) - allowed)
    if unknown:
        raise CriteriaError(
            f"{where} has unknown key(s) {unknown}; allowed keys are {sorted(allowed)}."
        )


def _applies_to(value: object) -> AppliesTo:
    if not isinstance(value, Mapping):
        raise CriteriaError("'applies_to' must be a mapping.")
    _reject_unknown(value, frozenset({"technique", "detection"}), "'applies_to'")
    technique = value.get("technique")
    if technique not in TECHNIQUES:
        raise CriteriaError(
            f"'technique' must be one of {sorted(TECHNIQUES)}, got {technique!r}."
        )
    return AppliesTo(technique=str(technique), detection=_text(value, "detection"))


def _limits(value: object) -> tuple[Criterion, ...]:
    if not isinstance(value, list) or not value:
        raise CriteriaError("'limits' must be a non-empty list.")
    return tuple(_criterion(item, index) for index, item in enumerate(value))


def _criterion(value: object, index: int) -> Criterion:
    where = f"limits[{index}]"
    if not isinstance(value, Mapping):
        raise CriteriaError(f"{where} must be a mapping.")
    _reject_unknown(value, _CRITERION_KEYS, where)

    metric = value.get("metric")
    if not isinstance(metric, str) or metric not in PANEL_METRICS:
        raise CriteriaError(
            f"{where}: 'metric' must be a panel metric id "
            f"{sorted(PANEL_METRICS)}; got {metric!r}."
        )
    operator = value.get("operator")
    if operator not in OPERATORS:
        raise CriteriaError(
            f"{where}: 'operator' must be one of {sorted(OPERATORS)}; got {operator!r}."
        )
    number = value.get("value")
    if isinstance(number, bool) or not isinstance(number, (int, float)):
        raise CriteriaError(f"{where}: 'value' must be a number; got {number!r}.")

    try:
        finite_number = float(number)
    except OverflowError as exc:
        raise CriteriaError(f"{where}: 'value' must be finite in float64.") from exc
    if not math.isfinite(finite_number):
        raise CriteriaError(f"{where}: 'value' must be finite; got {number!r}.")

    if "n" in value and metric not in REPLICATE_METRICS:
        raise CriteriaError(
            f"{where}: '{metric}' is not replicate-based, so 'n' is not allowed."
        )
    return Criterion(
        metric=metric,
        operator=str(operator),
        value=finite_number,
        between=_between(value.get("between"), metric, where),
        n=_replicate_count(value.get("n"), metric, where),
        on=_roles(value.get("on"), where),
    )


def _between(value: object, metric: str, where: str) -> tuple[str, str] | None:
    if metric in PAIRWISE_METRICS:
        if (
            not isinstance(value, list)
            or len(value) != 2
            or not all(isinstance(item, str) and item.strip() for item in value)
        ):
            raise CriteriaError(
                f"{where}: '{metric}' is a pairwise metric and needs 'between' as "
                f"two non-empty peak names."
            )
        if value[0] == value[1]:
            raise CriteriaError(f"{where}: 'between' needs two distinct peak names.")
        return (value[0], value[1])
    if value is not None:
        raise CriteriaError(
            f"{where}: '{metric}' is not a pairwise metric, so 'between' is not "
            f"allowed."
        )
    return None


def _replicate_count(value: object, metric: str, where: str) -> int | None:
    if metric in REPLICATE_METRICS and value is None:
        raise CriteriaError(
            f"{where}: '{metric}' is replicate-based and needs 'n', an integer >= 2."
        )
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 2:
        raise CriteriaError(
            f"{where}: 'n', when given, must be an integer >= 2; got {value!r}."
        )
    return value


def _roles(value: object, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise CriteriaError(f"{where}: 'on' must be a list of non-empty labels.")
    return tuple(value)
