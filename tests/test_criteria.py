"""W6 tests — the criteria-file contract.

One test per refusal case ``M1-BRIEF.md`` §6 names (unknown metric id, bad
operator, missing pairwise names, replicate metric without ``n``, missing
``source``), plus a valid file that parses, and a check that no evaluation
leaks into this package.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chromamcp.criteria import CriteriaFile, load_criteria, parse_criteria
from chromamcp.errors import CriteriaError, InaccessiblePathError

_VALID = """\
criteria: SUIT-01
source: "SOP-42, internal system-suitability specification"
applies_to:
  technique: LC
  detection: UV
limits:
  - metric: resolution
    between: ["main", "impurity"]
    operator: ">="
    value: 2.0
    "on": [system_suitability_injection]
  - metric: rsd_replicates
    operator: "<="
    value: 1.0
    n: 5
"""


def test_a_valid_file_parses() -> None:
    parsed = parse_criteria(_VALID)
    assert isinstance(parsed, CriteriaFile)
    assert parsed.identifier == "SUIT-01"
    assert parsed.source.startswith("SOP-42")
    assert parsed.applies_to.technique == "LC"
    assert parsed.applies_to.detection == "UV"
    assert len(parsed.limits) == 2

    first = parsed.limits[0]
    assert first.metric == "resolution"
    assert first.between == ("main", "impurity")
    assert first.operator == ">="
    assert first.value == 2.0
    assert first.n is None
    assert first.on == ("system_suitability_injection",)

    second = parsed.limits[1]
    assert second.metric == "rsd_replicates"
    assert second.n == 5
    assert second.between is None


def test_load_criteria_reads_a_file(tmp_path: Path) -> None:
    path = tmp_path / "criteria.yaml"
    path.write_text(_VALID, encoding="utf-8")
    assert load_criteria(path).identifier == "SUIT-01"


def test_missing_file_is_inaccessible(tmp_path: Path) -> None:
    with pytest.raises(InaccessiblePathError):
        load_criteria(tmp_path / "absent.yaml")


# --- refusals ---------------------------------------------------------------
def test_unknown_metric_id_is_refused() -> None:
    text = _VALID.replace("metric: resolution", "metric: frobnicate")
    with pytest.raises(CriteriaError) as excinfo:
        parse_criteria(text)
    assert "panel metric id" in str(excinfo.value)


def test_unparseable_operator_is_refused() -> None:
    text = _VALID.replace('operator: ">="', 'operator: "~="')
    with pytest.raises(CriteriaError) as excinfo:
        parse_criteria(text)
    assert "operator" in str(excinfo.value)


def test_pairwise_metric_without_between_is_refused() -> None:
    text = _VALID.replace('    between: ["main", "impurity"]\n', "")
    with pytest.raises(CriteriaError) as excinfo:
        parse_criteria(text)
    assert "pairwise" in str(excinfo.value)


def test_between_with_the_wrong_arity_is_refused() -> None:
    text = _VALID.replace('["main", "impurity"]', '["main"]')
    with pytest.raises(CriteriaError):
        parse_criteria(text)


def test_between_on_a_non_pairwise_metric_is_refused() -> None:
    text = _VALID.replace(
        "  - metric: rsd_replicates\n",
        '  - metric: rsd_replicates\n    between: ["a", "b"]\n',
    )
    with pytest.raises(CriteriaError) as excinfo:
        parse_criteria(text)
    assert "not a pairwise metric" in str(excinfo.value)


def test_replicate_metric_without_n_is_refused() -> None:
    text = _VALID.replace(
        '  - metric: rsd_replicates\n    operator: "<="\n    value: 1.0\n    n: 5\n',
        '  - metric: rsd_replicates\n    operator: "<="\n    value: 1.0\n',
    )
    with pytest.raises(CriteriaError) as excinfo:
        parse_criteria(text)
    assert "replicate-based" in str(excinfo.value)


def test_n_below_two_is_refused() -> None:
    text = _VALID.replace("    n: 5", "    n: 1")
    with pytest.raises(CriteriaError):
        parse_criteria(text)


def test_missing_source_is_refused() -> None:
    text = _VALID.replace(
        'source: "SOP-42, internal system-suitability specification"\n', ""
    )
    with pytest.raises(CriteriaError) as excinfo:
        parse_criteria(text)
    assert "source" in str(excinfo.value)


def test_missing_identifier_is_refused() -> None:
    text = _VALID.replace("criteria: SUIT-01\n", "")
    with pytest.raises(CriteriaError) as excinfo:
        parse_criteria(text)
    assert "criteria" in str(excinfo.value)


def test_a_non_mapping_document_is_refused() -> None:
    with pytest.raises(CriteriaError):
        parse_criteria("- one\n- two\n")


def test_invalid_yaml_is_refused() -> None:
    with pytest.raises(CriteriaError) as excinfo:
        parse_criteria("criteria: [unclosed\n")
    assert "YAML" in str(excinfo.value)


def test_an_unknown_top_level_key_is_refused() -> None:
    with pytest.raises(CriteriaError) as excinfo:
        parse_criteria(_VALID + "extra: 1\n")
    assert "unknown key" in str(excinfo.value)


def test_an_unknown_criterion_key_is_refused() -> None:
    text = _VALID.replace('    operator: ">="\n', '    operator: ">="\n    foo: 1\n')
    with pytest.raises(CriteriaError):
        parse_criteria(text)


def test_an_unknown_technique_is_refused() -> None:
    text = _VALID.replace("technique: LC", "technique: LCMS")
    with pytest.raises(CriteriaError) as excinfo:
        parse_criteria(text)
    assert "technique" in str(excinfo.value)


def test_empty_limits_is_refused() -> None:
    text = (
        'criteria: SUIT-01\nsource: "SOP-42"\n'
        "applies_to: { technique: LC, detection: UV }\nlimits: []\n"
    )
    with pytest.raises(CriteriaError):
        parse_criteria(text)


def test_an_unquoted_boolean_key_is_refused() -> None:
    # An unquoted ``on:`` is YAML 1.1 boolean ``True``; the reader asks for it to
    # be quoted rather than silently mis-reading the field.
    text = _VALID.replace('"on":', "on:")
    with pytest.raises(CriteriaError) as excinfo:
        parse_criteria(text)
    assert "boolean" in str(excinfo.value)


def test_the_package_exposes_no_evaluation() -> None:
    import chromamcp.criteria as criteria

    assert not any("eval" in name or "verdict" in name for name in criteria.__all__), (
        "W6 is parse-and-validate only; evaluation belongs to M3."
    )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("criteria: SUIT-01", "criteria: SUIT-01\ncriteria: OTHER"),
        ("  technique: LC", "  technique: LC\n  technique: GC"),
        ("    value: 2.0", "    value: 2000\n    value: 200"),
        (
            '    between: ["main", "impurity"]',
            '    between: ["a", "b"]\n    between: ["c", "d"]',
        ),
    ],
)
def test_duplicate_mapping_keys_are_refused(old: str, new: str) -> None:
    with pytest.raises(CriteriaError, match="duplicate"):
        parse_criteria(_VALID.replace(old, new))


@pytest.mark.parametrize("limit", [".nan", ".inf", "-.inf", "1.0e+400", "9" * 400])
def test_non_finite_limits_are_refused(limit: str) -> None:
    with pytest.raises(CriteriaError, match="finite"):
        parse_criteria(_VALID.replace("value: 2.0", f"value: {limit}"))


def test_pairwise_names_must_be_distinct() -> None:
    with pytest.raises(CriteriaError, match="distinct"):
        parse_criteria(_VALID.replace('["main", "impurity"]', '["main", "main"]'))


@pytest.mark.parametrize("count", ["5", "null"])
def test_n_on_non_replicate_metric_is_refused(count: str) -> None:
    with pytest.raises(CriteriaError, match="not replicate-based"):
        parse_criteria(_VALID.replace("value: 2.0", f"value: 2.0\n    n: {count}"))


def test_yaml_merge_cannot_override_a_limit() -> None:
    text = _VALID.replace("    value: 2.0", "    <<: {value: 2000}\n    value: 200")
    with pytest.raises(CriteriaError, match="duplicate"):
        parse_criteria(text)
