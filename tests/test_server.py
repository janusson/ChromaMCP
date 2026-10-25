"""W8 tests — the stdio MCP surface.

The gate is an **over-the-wire** session: the server is spawned as a subprocess
and driven with newline-delimited JSON-RPC on stdin/stdout, so the tests exercise
the wire and not the local functions (``M2-BRIEF.md`` §3 D1, §8).  Everything on
stdout must parse as a JSON-RPC frame; a tool error must arrive as ``isError``
with its text intact; and a 100k-point chromatogram must round-trip as a handle.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from chromamcp.errors import ReferenceError
from chromamcp.security import ENV_ALLOWED_ROOT
from chromamcp.server import ReferenceStore
from tests.test_io_mzml import _ACC_TIC, _chromatogram, _document, _write

_REF = "ptr:chrom:"
_TOOLS = [
    "assess_sequence",
    "compute_suitability",
    "integrate_peaks",
    "load_chromatogram",
    "release_reference",
    "summarise_chromatogram",
    "trend_qc",
]


def _trace(n_points: int, *, step: float = 0.001) -> tuple[list[float], list[float]]:
    time = np.arange(n_points, dtype=np.float64) * step
    centre = 0.5 * (float(time[0]) + float(time[-1]))
    intensity = np.exp(-0.5 * ((time - centre) / 0.05) ** 2)
    return time.tolist(), intensity.tolist()


def _mzml(tmp_path: Path, n_points: int = 400) -> Path:
    time, intensity = _trace(n_points)
    text = _document(
        [
            _chromatogram(
                "tic",
                kind_accession=_ACC_TIC,
                kind_name="total ion chromatogram",
                time=time,
                intensity=intensity,
            )
        ]
    )
    return _write(tmp_path, text)


def _two_peak_trace(
    n_points: int = 500, *, step: float = 0.001
) -> tuple[list[float], list[float]]:
    time = np.arange(n_points, dtype=np.float64) * step
    intensity = np.exp(-0.5 * ((time - 0.15) / 0.03) ** 2) + 0.8 * np.exp(
        -0.5 * ((time - 0.35) / 0.03) ** 2
    )
    return time.tolist(), intensity.tolist()


def _mzml_two_peaks(tmp_path: Path) -> Path:
    time, intensity = _two_peak_trace()
    text = _document(
        [
            _chromatogram(
                "tic",
                kind_accession=_ACC_TIC,
                kind_name="total ion chromatogram",
                time=time,
                intensity=intensity,
            )
        ]
    )
    return _write(tmp_path, text)


class _Wire:
    """A real stdio client: spawn the server and speak JSON-RPC to it."""

    def __init__(self, *, allowed_root: Path | None = None) -> None:
        env = dict(os.environ)
        if allowed_root is not None:
            env[ENV_ALLOWED_ROOT] = str(allowed_root)
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "chromamcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        self._id = 0
        self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        )
        self._send(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        )

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    def _send(self, message: dict[str, object]) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def _read(self) -> dict[str, object]:
        assert self.proc.stdout is not None
        line = self.proc.stdout.readline()
        assert line.strip(), "the server closed stdout"
        frame = json.loads(line)
        assert frame["jsonrpc"] == "2.0"
        return frame

    def _rpc(self, method: str, params: dict[str, object]) -> dict[str, object]:
        self._id += 1
        self._send(
            {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        )
        return self._read()

    def tools(self) -> list[str]:
        result = self._rpc("tools/list", {})["result"]
        assert isinstance(result, dict)
        return sorted(tool["name"] for tool in result["tools"])

    def call(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        frame = self._rpc("tools/call", {"name": name, "arguments": arguments})
        result = frame["result"]
        assert isinstance(result, dict)
        return result


@pytest.fixture
def wire(tmp_path: Path) -> Iterator[_Wire]:
    client = _Wire(allowed_root=tmp_path)
    try:
        yield client
    finally:
        client.close()


def _text(result: dict[str, object]) -> str:
    content = result["content"]
    assert isinstance(content, list)
    return str(content[0]["text"])


def _payload(result: dict[str, object]) -> Any:
    assert result["isError"] is False, _text(result)
    return json.loads(_text(result))


# --- the wire --------------------------------------------------------------
def test_the_seven_tools_are_registered(wire: _Wire) -> None:
    assert wire.tools() == _TOOLS


def test_the_error_text_survives_the_wire(wire: _Wire) -> None:
    result = wire.call(
        "assess_sequence",
        {"reference": f"{_REF}x:1", "criteria_path": "criteria.yaml"},
    )
    assert result["isError"] is True
    assert "not implemented in this unit" in _text(result)


def test_an_unknown_reference_is_refused_over_the_wire(wire: _Wire) -> None:
    result = wire.call("summarise_chromatogram", {"reference": f"{_REF}nope:9"})
    assert result["isError"] is True
    assert "unknown reference" in _text(result)


def test_a_path_outside_the_allowed_root_is_refused(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    path = _mzml(outside)
    client = _Wire(allowed_root=allowed)
    try:
        result = client.call("load_chromatogram", {"path": str(path)})
        assert result["isError"] is True
        assert "outside the allowed root" in _text(result)
        assert ENV_ALLOWED_ROOT in _text(result)
    finally:
        client.close()


def test_load_summarise_release_round_trip(wire: _Wire, tmp_path: Path) -> None:
    loaded = _payload(wire.call("load_chromatogram", {"path": str(_mzml(tmp_path))}))
    reference = str(loaded["reference"])
    assert reference.startswith(_REF)
    assert loaded["n_channels"] == 1
    assert str(loaded["channels"][0]["kind"]) == "tic"

    summary = _payload(wire.call("summarise_chromatogram", {"reference": reference}))
    assert summary["n_points_total"] == 400

    released = _payload(wire.call("release_reference", {"reference": reference}))
    assert released["released"] is True

    after = wire.call("summarise_chromatogram", {"reference": reference})
    assert after["isError"] is True


def test_a_100k_point_chromatogram_round_trips_as_a_handle(
    wire: _Wire, tmp_path: Path
) -> None:
    result = wire.call("load_chromatogram", {"path": str(_mzml(tmp_path, 100_000))})
    assert result["isError"] is False
    text = _text(result)
    assert _REF in text
    assert len(text) < 4000, (
        f"the trace crossed the context boundary ({len(text)} chars)"
    )


def test_every_response_carries_evidence_and_a_separate_event_block(
    wire: _Wire, tmp_path: Path
) -> None:
    loaded = _payload(wire.call("load_chromatogram", {"path": str(_mzml(tmp_path))}))
    provenance = loaded["provenance"]
    assert isinstance(provenance, dict)
    assert provenance["tolerance_basis"] == "relative"
    assert provenance["input_file"]["sha256"]
    assert provenance["operation"]["tool"] == "load_chromatogram"

    # The clock is metadata about the call, not evidence about the file, so it
    # lives in `event` and the evidence block stays reproducible.
    assert "timestamp_utc" not in provenance
    event = loaded["event"]
    assert event["timestamp_note"] == "run time, not acquisition time"
    assert str(event["timestamp_utc"]).endswith("Z")


# --- the panel over the wire ------------------------------------------------
def test_metric_values_carry_their_formula_and_tolerance(
    wire: _Wire, tmp_path: Path
) -> None:
    loaded = _payload(wire.call("load_chromatogram", {"path": str(_mzml(tmp_path))}))
    peaks = _payload(
        wire.call(
            "integrate_peaks",
            {
                "reference": str(loaded["reference"]),
                "channel": 0,
                "windows": [[0, 399]],
            },
        )
    )
    assert peaks["n_peaks"] == 1
    assert str(peaks["reference"]).startswith(_REF)

    panel = _payload(
        wire.call("compute_suitability", {"peaks": str(peaks["reference"])})
    )
    metrics = panel["metrics"]
    assert isinstance(metrics, list) and metrics
    for metric in metrics:
        assert metric["formula_id"]
        assert metric["tolerance"] is not None
        assert metric["verdict"] == "not-evaluated"
    missing = {item["metric_id"] for item in panel["not_evaluated"]}
    assert "peak_to_valley" in missing


# --- the store --------------------------------------------------------------
def test_the_store_is_bounded() -> None:
    store = ReferenceStore(max_entries=2)
    store.put("chromatograms", object())
    store.put("chromatograms", object())
    with pytest.raises(ReferenceError):
        store.put("chromatograms", object())


def test_a_released_handle_is_gone() -> None:
    store = ReferenceStore()
    reference = store.put("peaks", {"rows": []})
    store.release(reference)
    with pytest.raises(ReferenceError):
        store.get(reference)


def test_releasing_an_unknown_handle_is_refused() -> None:
    with pytest.raises(ReferenceError):
        ReferenceStore().release(f"{_REF}nope:1")


def test_get_validates_the_handle_kind() -> None:
    store = ReferenceStore()
    reference = store.put("peaks", {"rows": []})
    with pytest.raises(ReferenceError):
        store.get(reference, expect="chromatograms")
    assert store.get(reference, expect="peaks") == {"rows": []}


# --- the wrong-kind handle, and honest omissions ----------------------------
def test_a_wrong_kind_handle_is_refused_with_a_reason(
    wire: _Wire, tmp_path: Path
) -> None:
    """A peaks handle where a chromatogram is wanted must say so.

    A bare ``KeyError`` at the call site would have its text withheld by the SDK,
    so the store refuses the mismatch itself and the reason survives the wire.
    """
    loaded = _payload(wire.call("load_chromatogram", {"path": str(_mzml(tmp_path))}))
    peaks = _payload(
        wire.call(
            "integrate_peaks",
            {
                "reference": str(loaded["reference"]),
                "channel": 0,
                "windows": [[0, 399]],
            },
        )
    )
    result = wire.call("summarise_chromatogram", {"reference": str(peaks["reference"])})
    assert result["isError"] is True
    assert "wrong kind" in _text(result)


def test_selectivity_is_reported_not_evaluated(wire: _Wire, tmp_path: Path) -> None:
    loaded = _payload(
        wire.call("load_chromatogram", {"path": str(_mzml_two_peaks(tmp_path))})
    )
    peaks = _payload(
        wire.call(
            "integrate_peaks",
            {
                "reference": str(loaded["reference"]),
                "channel": 0,
                "windows": [[0, 249], [250, 499]],
            },
        )
    )
    assert peaks["n_peaks"] == 2
    reference = str(peaks["reference"])

    with_pairs = _payload(
        wire.call("compute_suitability", {"peaks": reference, "pairs": [[0, 1]]})
    )
    pairs_missing = {
        item["metric_id"]: item["reason"] for item in with_pairs["not_evaluated"]
    }
    assert "void_time" in pairs_missing["selectivity"]
    assert "resolution" not in pairs_missing

    without_pairs = _payload(wire.call("compute_suitability", {"peaks": reference}))
    names = {item["metric_id"] for item in without_pairs["not_evaluated"]}
    assert {"resolution", "selectivity"} <= names


# --- measurement lineage (F3) -----------------------------------------------
def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _two_peak_handles(wire: _Wire, tmp_path: Path) -> tuple[Any, Any]:
    loaded = _payload(
        wire.call("load_chromatogram", {"path": str(_mzml_two_peaks(tmp_path))})
    )
    peaks = _payload(
        wire.call(
            "integrate_peaks",
            {
                "reference": str(loaded["reference"]),
                "channel": 0,
                "windows": [[0, 249], [250, 499]],
            },
        )
    )
    return loaded, peaks


def test_a_peak_row_carries_its_window_apex_and_a_measurable_area(
    wire: _Wire, tmp_path: Path
) -> None:
    """Every number in the row is reconstructable from the row itself."""
    _loaded, peaks = _two_peak_handles(wire, tmp_path)
    row = peaks["peaks"][0]

    assert row["id"] == "peak:c0:w0-249"
    assert row["channel"] == 0
    assert row["window"] == {
        "left_index": 0,
        "right_index": 249,
        "t_left_min": 0.0,
        "t_right_min": row["window"]["t_right_min"],
    }
    assert 0.0 < row["window"]["t_right_min"] < 0.25
    assert row["baseline_rule"] == "linear"
    assert 0 <= row["apex"]["index"] <= 249
    assert row["apex"]["height"] == pytest.approx(
        row["apex"]["intensity"] - row["apex"]["baseline"]
    )
    assert row["widths"]["half_min"] > 0.0

    area = row["measurements"]["area"]
    assert area["measurement_id"] == "peak_area@peak:c0:w0-249"
    assert area["metric_id"] == "peak_area"
    assert area["formula_id"] == "peak_area"
    assert area["unit"] == "counts·min"
    assert area["tolerance"] is not None
    assert area["peaks"] == ["peak:c0:w0-249"]


def test_every_metric_row_names_its_subject(wire: _Wire, tmp_path: Path) -> None:
    """Two peaks produce rows whose subjects are explicit, not positional."""
    _loaded, peaks = _two_peak_handles(wire, tmp_path)
    panel = _payload(
        wire.call(
            "compute_suitability",
            {
                "peaks": str(peaks["reference"]),
                "pairs": [[0, 1]],
                "void_time": 0.05,
                "replicate_areas": [1.0, 2.0],
            },
        )
    )
    subjects = {str(row["subject"]) for row in panel["metrics"]}
    assert "peak:c0:w0-249" in subjects
    assert "peak:c0:w250-499" in subjects
    assert "peak:c0:w0-249|peak:c0:w250-499" in subjects
    assert "replicates:n=2" in subjects

    for row in panel["metrics"]:
        assert str(row["measurement_id"]).startswith(f"{row['metric_id']}@")
        assert str(row["subject"]) in str(row["measurement_id"])
        if row["metric_id"] == "rsd_replicates":
            assert row["peaks"] == []
        else:
            assert row["peaks"]

    pair_rows = [row for row in panel["metrics"] if "|" in str(row["subject"])]
    assert pair_rows
    for row in pair_rows:
        assert row["peaks"] == ["peak:c0:w0-249", "peak:c0:w250-499"]


def test_the_panel_accounts_for_every_metric_it_did_not_compute(
    wire: _Wire, tmp_path: Path
) -> None:
    """An absent value is stated as an omission with its reason, never dropped."""
    _loaded, peaks = _two_peak_handles(wire, tmp_path)
    panel = _payload(
        wire.call("compute_suitability", {"peaks": str(peaks["reference"])})
    )
    missing = {item["metric_id"]: item["reason"] for item in panel["not_evaluated"]}
    assert {
        "peak_to_valley",
        "signal_to_noise",
        "capacity_factor",
        "resolution",
        "selectivity",
        "rsd_replicates",
    } <= set(missing)
    # The S/N omission states the window the caller has to supply, in the
    # pharmacopoeial order: 20x primary, 5x the permitted fallback.
    assert "20" in missing["signal_to_noise"]
    assert "5" in missing["signal_to_noise"]


# --- canonical evidence (F6) -------------------------------------------------
def test_the_evidence_block_is_byte_identical_for_the_same_request(
    wire: _Wire, tmp_path: Path
) -> None:
    loaded = _payload(
        wire.call("load_chromatogram", {"path": str(_mzml_two_peaks(tmp_path))})
    )
    reference = str(loaded["reference"])
    first = _payload(wire.call("summarise_chromatogram", {"reference": reference}))
    second = _payload(wire.call("summarise_chromatogram", {"reference": reference}))

    assert _canonical(first["provenance"]) == _canonical(second["provenance"])
    without_clock_first = {k: v for k, v in first.items() if k != "event"}
    without_clock_second = {k: v for k, v in second.items() if k != "event"}
    assert _canonical(without_clock_first) == _canonical(without_clock_second)


def test_a_handle_is_a_digest_of_the_request_not_an_allocation(
    tmp_path: Path,
) -> None:
    """Two fresh processes loading one file agree, handle and evidence alike."""
    path = _mzml_two_peaks(tmp_path)
    first_client = _Wire(allowed_root=tmp_path)
    second_client = _Wire(allowed_root=tmp_path)
    try:
        first = _payload(first_client.call("load_chromatogram", {"path": str(path)}))
        second = _payload(second_client.call("load_chromatogram", {"path": str(path)}))
    finally:
        first_client.close()
        second_client.close()

    assert first["reference"] == second["reference"]
    assert _canonical(first["provenance"]) == _canonical(second["provenance"])


def test_the_operation_record_carries_the_arguments(
    wire: _Wire, tmp_path: Path
) -> None:
    _loaded, peaks = _two_peak_handles(wire, tmp_path)
    panel = _payload(
        wire.call(
            "compute_suitability",
            {"peaks": str(peaks["reference"]), "pairs": [[0, 1]], "void_time": 0.05},
        )
    )
    operation = panel["provenance"]["operation"]
    assert operation["tool"] == "compute_suitability"
    arguments = operation["arguments"]
    assert arguments["pairs"] == [[0, 1]]
    assert arguments["void_time"] == pytest.approx(0.05)
    assert arguments["baseline_rule"] == "linear"


def test_a_missing_sample_is_refused_rather_than_emitted(
    wire: _Wire, tmp_path: Path
) -> None:
    """A NaN in a trace is a missing measurement, and no geometry is defined on it.

    JSON has no number for a missing value, so the reader's convention
    (``AGENTS.md`` §1.6) reaches the wire as a refusal with its reason, never as a
    NaN token or a silently filled zero.
    """
    time, intensity = _two_peak_trace()
    intensity[100] = float("nan")
    text = _document(
        [
            _chromatogram(
                "tic",
                kind_accession=_ACC_TIC,
                kind_name="total ion chromatogram",
                time=time,
                intensity=intensity,
            )
        ]
    )
    loaded = _payload(
        wire.call("load_chromatogram", {"path": str(_write(tmp_path, text))})
    )
    result = wire.call(
        "integrate_peaks",
        {
            "reference": str(loaded["reference"]),
            "channel": 0,
            "windows": [[0, 249]],
        },
    )
    assert result["isError"] is True
    assert "non-finite" in _text(result)
