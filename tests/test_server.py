"""W8 tests — the stdio MCP surface.

The gate is an **over-the-wire** session: the server is spawned as a subprocess
and driven with newline-delimited JSON-RPC on stdin/stdout, so the tests exercise
the wire and not the local functions (``M2-BRIEF.md`` §3 D1, §8).  Everything on
stdout must parse as a JSON-RPC frame; a tool error must arrive as ``isError``
with its text intact; and a 100k-point chromatogram must round-trip as a handle.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from chromamcp.errors import ReferenceError
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

    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "chromamcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
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
def wire() -> Iterator[_Wire]:
    client = _Wire()
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


def test_every_response_carries_provenance(wire: _Wire, tmp_path: Path) -> None:
    loaded = _payload(wire.call("load_chromatogram", {"path": str(_mzml(tmp_path))}))
    provenance = loaded["provenance"]
    assert isinstance(provenance, dict)
    assert provenance["tolerance_basis"] == "relative"
    assert provenance["timestamp_note"] == "run time, not acquisition time"
    assert provenance["input_file"]["sha256"]


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
