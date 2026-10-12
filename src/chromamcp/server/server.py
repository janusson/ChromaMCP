"""The stdio MCP server and its tools (W8).

The only module in the tree that imports the ``mcp`` SDK.  It exposes the seven
tools of ``PLAN.md`` §5 over **stdio and nothing else** — no HTTP, no REST, no
hosted service (``AGENTS.md`` §3, ``M2-BRIEF.md`` §0).

Two rules the code makes explicit:

- **Refuse, do not guess.**  A tool whose backing unit is not built returns an
  explicit "not implemented in this unit" error, and a bad handle or a bad window
  is a distinct, actionable error — never a plausible number.
- **The diagnosis reaches the model.**  Domain errors (``ChromamcpError``) are
  translated to the SDK's ``ToolError`` at the tool boundary, so the message
  survives the wire.  The translation lives *here*, not in ``errors.py``: the
  domain hierarchy must stay free of the SDK so the compute path keeps its
  boundary (``M2-BRIEF.md`` §7's "errors.py derives from ToolError" is read as
  "the surfaced error is a ToolError" for this reason).

``integrate_peaks`` is not a competing integrator (``AGENTS.md`` §3): it measures
the **caller-supplied** windows through the W2 geometry and detects nothing.
``assess_sequence`` and ``trend_qc`` are M3 and return "not implemented in this
unit".
"""

from __future__ import annotations

import logging
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from numpy.typing import NDArray

from chromamcp import __version__
from chromamcp.errors import ChromamcpError
from chromamcp.geometry import (
    Baseline,
    BaselineRule,
    find_apex,
    five_percent_width,
    half_height_width,
    resolve_baseline,
)
from chromamcp.io.mzml import Chromatogram, read_chromatograms
from chromamcp.metrics import (
    MetricResult,
    capacity_factor,
    peak_area,
    peak_height,
    plate_number,
    resolution,
    rsd_replicates,
    selectivity,
    symmetry_factor,
)
from chromamcp.provenance import TOLERANCE_BASIS, file_sha256, library_versions
from chromamcp.server.store import ReferenceStore

__all__ = ["build_server", "main"]

_INSTRUCTIONS = (
    "ChromaMCP measures chromatography — system-suitability metrics, each with "
    "its cited formula and derived tolerance, and (later) sequence review against "
    "a laboratory's own written criteria.  Every response carries a provenance "
    "block.  It reports measurements, never a verdict on a method."
)
_NOT_BUILT = (
    "{tool} is not implemented in this unit.  Sequence and trend logic is M3 "
    "(AGENTS.md section 3); it returns this explicit error rather than a result."
)


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _provenance(source: str | None, sha256: str | None) -> dict[str, object]:
    """The W5 provenance block, carried on every response (``M2-BRIEF.md`` §6)."""
    return {
        "input_file": None if source is None else {"path": source, "sha256": sha256},
        "reader": "chromamcp.io.mzml",
        "library_versions": asdict(library_versions()),
        "criteria": None,
        "tolerance_basis": TOLERANCE_BASIS,
        "timestamp_utc": _utc_now(),
        "timestamp_note": "run time, not acquisition time",
    }


def _metric(result: MetricResult) -> dict[str, object]:
    return {
        "metric_id": result.metric_id,
        "value": result.value,
        "unit": result.unit,
        "formula_id": result.formula_id,
        "tolerance": result.tolerance,
        "verdict": "not-evaluated",
    }


def _channel(index: int, chromatogram: Chromatogram) -> dict[str, object]:
    return {
        "index": index,
        "id": chromatogram.id,
        "kind": chromatogram.kind.value,
        "n_points": chromatogram.n_points,
    }


def _as_float(value: object) -> float:
    assert isinstance(value, (int, float))
    return float(value)


def _measure(
    time: NDArray[np.float64],
    intensity: NDArray[np.float64],
    left: int,
    right: int,
) -> dict[str, object]:
    """Measure one caller-supplied window, against a linear baseline."""
    if not 0 <= left < right < int(time.size):
        raise ToolError(
            f"window [{left}, {right}] must satisfy 0 <= left < right < n_points."
        )
    baseline: Baseline = resolve_baseline(
        BaselineRule.LINEAR, time, intensity, left_index=left, right_index=right
    )
    apex = find_apex(time, intensity, left_index=left, right_index=right)
    half = half_height_width(time, intensity, baseline=baseline, apex=apex)
    five = five_percent_width(time, intensity, baseline=baseline, apex=apex)
    area = peak_area(
        time, intensity, baseline=baseline, left_index=left, right_index=right
    )
    return {
        "apex_index": apex.index,
        "apex_time_min": apex.time,
        "apex_intensity": apex.intensity,
        "baseline_at_apex": baseline.value(apex.time),
        "width_half_min": half.width,
        "width_5pct_min": five.width,
        "front_5pct_min": five.front_distance,
        "area": area.value,
    }


def _per_peak(
    rows: list[dict[str, object]], void_time: float | None
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in rows:
        apex_time = _as_float(row["apex_time_min"])
        out.append(
            _metric(
                plate_number(
                    apex_time=apex_time,
                    half_height_width=_as_float(row["width_half_min"]),
                )
            )
        )
        out.append(
            _metric(
                symmetry_factor(
                    width_at_5pct=_as_float(row["width_5pct_min"]),
                    front_distance_at_5pct=_as_float(row["front_5pct_min"]),
                )
            )
        )
        out.append(
            _metric(
                peak_height(
                    apex_intensity=_as_float(row["apex_intensity"]),
                    baseline_at_apex=_as_float(row["baseline_at_apex"]),
                )
            )
        )
        if void_time is not None:
            out.append(
                _metric(capacity_factor(apex_time=apex_time, void_time=void_time))
            )
    return out


def _indices(pair: list[int], n_rows: int) -> tuple[int, int]:
    if len(pair) != 2:
        raise ToolError(f"a pair must be two peak indices, got {pair!r}.")
    first, second = pair
    if not 0 <= first < second < n_rows:
        raise ToolError(
            f"pair {pair!r} must satisfy 0 <= first < second < {n_rows} peaks."
        )
    return first, second


def _per_pair(
    rows: list[dict[str, object]],
    pairs: list[list[int]],
    void_time: float | None,
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for pair in pairs:
        first, second = _indices(pair, len(rows))
        low, high = rows[first], rows[second]
        out.append(
            _metric(
                resolution(
                    first_apex_time=_as_float(low["apex_time_min"]),
                    first_half_height_width=_as_float(low["width_half_min"]),
                    second_apex_time=_as_float(high["apex_time_min"]),
                    second_half_height_width=_as_float(high["width_half_min"]),
                )
            )
        )
        if void_time is not None:
            out.append(
                _metric(
                    selectivity(
                        first_apex_time=_as_float(low["apex_time_min"]),
                        second_apex_time=_as_float(high["apex_time_min"]),
                        void_time=void_time,
                    )
                )
            )
    return out


def build_server() -> MCPServer:
    """Build the server with its tool set and a fresh reference store."""
    server: MCPServer = MCPServer(
        name="chromamcp", version=__version__, instructions=_INSTRUCTIONS
    )
    store = ReferenceStore()

    @server.tool(
        name="load_chromatogram",
        description="Read an mzML file's TIC/XIC channels; returns a handle.",
    )
    def load_chromatogram(path: str) -> dict[str, object]:
        try:
            chromatograms = read_chromatograms(path)
            resolved = str(Path(path))
            digest = file_sha256(resolved)
        except ChromamcpError as exc:
            raise ToolError(str(exc)) from exc
        reference = store.put(
            "chromatograms",
            {"channels": chromatograms, "source": resolved, "sha256": digest},
        )
        return {
            "reference": reference,
            "n_channels": len(chromatograms),
            "channels": [
                _channel(index, item) for index, item in enumerate(chromatograms)
            ],
            "provenance": _provenance(resolved, digest),
        }

    @server.tool(
        name="summarise_chromatogram",
        description="A compact description of a loaded handle; never the raw trace.",
    )
    def summarise_chromatogram(reference: str) -> dict[str, object]:
        try:
            payload = store.get(reference, expect="chromatograms")
        except ChromamcpError as exc:
            raise ToolError(str(exc)) from exc
        chromatograms = payload["channels"]
        spans = [
            (float(item.time[0]), float(item.time[-1]))
            for item in chromatograms
            if item.n_points
        ]
        return {
            "reference": reference,
            "n_channels": len(chromatograms),
            "n_points_total": sum(item.n_points for item in chromatograms),
            "time_min": None
            if not spans
            else [min(low for low, _ in spans), max(high for _, high in spans)],
            "channels": [
                _channel(index, item) for index, item in enumerate(chromatograms)
            ],
            "provenance": _provenance(payload["source"], payload["sha256"]),
        }

    @server.tool(
        name="integrate_peaks",
        description=(
            "Measure the caller-supplied [left, right] windows through the W2 "
            "geometry; detects nothing."
        ),
    )
    def integrate_peaks(
        reference: str, channel: int, windows: list[list[int]]
    ) -> dict[str, object]:
        try:
            payload = store.get(reference, expect="chromatograms")
        except ChromamcpError as exc:
            raise ToolError(str(exc)) from exc
        chromatograms = payload["channels"]
        if not 0 <= channel < len(chromatograms):
            raise ToolError(
                f"channel {channel} is out of range; the handle has "
                f"{len(chromatograms)} channel(s)."
            )
        chromatogram = chromatograms[channel]
        time, intensity = chromatogram.time, chromatogram.intensity
        try:
            rows = [_measure(time, intensity, left, right) for left, right in windows]
        except ChromamcpError as exc:
            raise ToolError(str(exc)) from exc
        peaks_ref = store.put(
            "peaks",
            {
                "rows": rows,
                "baseline_rule": BaselineRule.LINEAR.value,
                "channel": channel,
                "source": payload["source"],
                "sha256": payload["sha256"],
            },
        )
        return {
            "reference": peaks_ref,
            "n_peaks": len(rows),
            "baseline_rule": BaselineRule.LINEAR.value,
            "peaks": rows,
            "provenance": _provenance(payload["source"], payload["sha256"]),
        }

    @server.tool(
        name="compute_suitability",
        description=(
            "The metric panel for a peak table, each value with its formula id "
            "and derived tolerance."
        ),
    )
    def compute_suitability(
        peaks: str,
        void_time: float | None = None,
        pairs: list[list[int]] | None = None,
        replicate_areas: list[float] | None = None,
    ) -> dict[str, object]:
        try:
            payload = store.get(peaks, expect="peaks")
        except ChromamcpError as exc:
            raise ToolError(str(exc)) from exc
        rows = payload["rows"]
        pairs = pairs or []
        try:
            metrics = _per_peak(rows, void_time)
            metrics.extend(_per_pair(rows, pairs, void_time))
            if replicate_areas:
                metrics.append(_metric(rsd_replicates(replicate_areas)))
        except ChromamcpError as exc:
            raise ToolError(str(exc)) from exc
        not_evaluated = [
            {
                "metric_id": "peak_to_valley",
                "reason": "p/v needs an unresolved pair's valley intensity, which "
                "the peak table does not carry in this unit.",
            }
        ]
        if void_time is None:
            not_evaluated.append(
                {"metric_id": "capacity_factor", "reason": "supply void_time."}
            )
        if not pairs:
            not_evaluated.append(
                {"metric_id": "resolution", "reason": "supply pairs of peak indices."}
            )
            not_evaluated.append(
                {"metric_id": "selectivity", "reason": "supply pairs of peak indices."}
            )
        elif void_time is None:
            not_evaluated.append(
                {"metric_id": "selectivity", "reason": "supply void_time."}
            )
        if not replicate_areas:
            not_evaluated.append(
                {"metric_id": "rsd_replicates", "reason": "supply replicate_areas."}
            )
        return {
            "peaks": peaks,
            "metrics": metrics,
            "not_evaluated": not_evaluated,
            "provenance": _provenance(payload["source"], payload["sha256"]),
        }

    @server.tool(
        name="assess_sequence",
        description="Not implemented in this unit: sequence evaluation is M3.",
    )
    def assess_sequence(reference: str, criteria_path: str) -> dict[str, object]:
        raise ToolError(_NOT_BUILT.format(tool="assess_sequence"))

    @server.tool(
        name="trend_qc",
        description="Not implemented in this unit: trend/drift statistics are M3.",
    )
    def trend_qc(reference: str) -> dict[str, object]:
        raise ToolError(_NOT_BUILT.format(tool="trend_qc"))

    @server.tool(
        name="release_reference",
        description="Free a handle; it is not decorative.",
    )
    def release_reference(reference: str) -> dict[str, object]:
        try:
            store.release(reference)
        except ChromamcpError as exc:
            raise ToolError(str(exc)) from exc
        return {"reference": reference, "released": True}

    return server


def main() -> None:
    """Run the server over stdio.  stdout carries protocol frames and nothing else."""
    logging.basicConfig(stream=sys.stderr)
    build_server().run("stdio")
