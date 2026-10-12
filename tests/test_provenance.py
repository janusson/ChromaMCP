"""W5 tests — the provenance record.

The determinism test is the gate ``M1-BRIEF.md`` §5.2.5 names: two runs over the
same fixture produce byte-identical serialised output.  The rest check the
schema, the pinned float formatting, the permitted vocabulary, and that the
record carries the criteria id and hash.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from chromamcp.metrics import TOLERANCE, plate_number
from chromamcp.provenance import (
    TOLERANCE_BASIS,
    Criteria,
    MetricRecord,
    ProvenanceRecord,
    build_record,
    file_sha256,
    serialise,
)
from tests.guards import BANNED_WORDS

_FIXED_TIME = datetime(2026, 10, 11, 12, 0, 0, tzinfo=UTC)


def _input_file(tmp_path: Path) -> Path:
    path = tmp_path / "chromatogram.mzML"
    path.write_bytes(b"synthetic fixture")
    return path


def _sample_record(
    path: Path, *, timestamp: datetime = _FIXED_TIME
) -> ProvenanceRecord:
    return build_record(
        input_path=path,
        parameters={
            "apex_interpolation": "parabolic_3point",
            "baseline_rule": "linear",
            "noise_window_factor": 5.0,
        },
        metrics=[
            MetricRecord.from_result(plate_number(apex_time=1.0, half_height_width=0.1))
        ],
        timestamp=timestamp,
    )


def test_serialisation_is_byte_identical_across_runs(tmp_path: Path) -> None:
    path = _input_file(tmp_path)
    record = _sample_record(path)
    assert serialise(record) == serialise(record)
    assert serialise(record) == serialise(_sample_record(path))


def test_record_schema(tmp_path: Path) -> None:
    data = json.loads(serialise(_sample_record(_input_file(tmp_path))))
    assert set(data) == {
        "input_file",
        "library_versions",
        "parameters",
        "criteria",
        "metrics",
        "reader",
        "timestamp_utc",
        "timestamp_note",
        "tolerance_basis",
    }
    assert set(data["input_file"]) == {"path", "sha256"}
    assert set(data["reader"]) == {"name", "version"}
    assert set(data["library_versions"]) == {
        "chromamcp",
        "numpy",
        "mzml_reader",
        "python",
    }
    assert data["criteria"] is None
    assert data["timestamp_note"] == "run time, not acquisition time"
    assert str(data["timestamp_utc"]).endswith("Z")
    metric = data["metrics"][0]
    assert set(metric) == {
        "metric_id",
        "value",
        "unit",
        "formula_id",
        "tolerance",
        "verdict",
    }
    assert metric["verdict"] == "not-evaluated"


def test_the_tolerance_basis_is_stated(tmp_path: Path) -> None:
    """A bare tolerance number is ambiguous; the record states its basis.

    Every panel tolerance is **relative** (a fraction of the independently
    expected value), so the record says so and ties the number to the shipped
    mapping — a reviewer reading ``0.02`` can tell it means 2 %.
    """
    data = json.loads(serialise(_sample_record(_input_file(tmp_path))))
    assert data["tolerance_basis"] == TOLERANCE_BASIS
    assert data["metrics"][0]["tolerance"] == TOLERANCE["plate_number"]


def test_float_formatting_is_pinned(tmp_path: Path) -> None:
    text = serialise(_sample_record(_input_file(tmp_path)))
    assert '"value": 554.0' in text
    assert '"noise_window_factor": 5.0' in text


def test_non_finite_floats_stay_valid_json(tmp_path: Path) -> None:
    record = build_record(
        input_path=_input_file(tmp_path),
        parameters={"inf": float("inf"), "missing": float("nan")},
        metrics=[],
        timestamp=_FIXED_TIME,
    )
    data = json.loads(serialise(record))
    assert data["parameters"]["missing"] == "NaN"
    assert data["parameters"]["inf"] == "Infinity"


def test_record_uses_only_the_permitted_vocabulary(tmp_path: Path) -> None:
    text = serialise(_sample_record(_input_file(tmp_path))).lower()
    for word in BANNED_WORDS:
        assert word not in text


def test_criteria_is_recorded_by_id_and_hash(tmp_path: Path) -> None:
    record = build_record(
        input_path=_input_file(tmp_path),
        parameters={},
        metrics=[],
        timestamp=_FIXED_TIME,
        criteria=Criteria(id="SOP-42", sha256="0" * 64),
    )
    data = json.loads(serialise(record))
    assert data["criteria"] == {"id": "SOP-42", "sha256": "0" * 64}


def test_file_sha256_matches_a_known_digest(tmp_path: Path) -> None:
    path = tmp_path / "abc.bin"
    path.write_bytes(b"abc")
    assert (
        file_sha256(path)
        == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_a_verdict_outside_the_permitted_set_is_refused() -> None:
    with pytest.raises(ValueError):
        MetricRecord(
            metric_id="plate_number",
            value=1.0,
            unit="dimensionless",
            formula_id="plate_number_half_height",
            tolerance=None,
            verdict="unknown",
        )
