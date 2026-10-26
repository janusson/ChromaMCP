"""The stdio MCP server and its tools (W8, evidence contract W13).

The only module in the tree that imports the ``mcp`` SDK.  It exposes the seven
tools of ``PLAN.md`` §5 over **stdio and nothing else** — no HTTP, no REST, no
hosted service (``AGENTS.md`` §3, ``M2-BRIEF.md`` §0).

Four rules the code makes explicit:

- **Refuse, do not guess.**  A tool whose backing unit is not built returns an
  explicit "not implemented in this unit" error, and a bad handle or a bad window
  is a distinct, actionable error — never a plausible number.
- **The diagnosis reaches the model.**  Domain errors (``ChromamcpError``) are
  translated to the SDK's ``ToolError`` at the tool boundary, so the message
  survives the wire.  The translation lives *here*, not in ``errors.py``: the
  domain hierarchy must stay free of the SDK so the compute path keeps its
  boundary (``M2-BRIEF.md`` §7's "errors.py derives from ToolError" is read as
  "the surfaced error is a ToolError" for this reason).
- **Every number carries its subject.**  A metric row names the peak or pair it
  was measured on (``measurement_id``, ``subject``, ``peaks``), and the peak row
  it refers to carries the integration window, the baseline rule and the apex it
  used — so a value can be reconstructed from the response without a transcript
  (``AGENTS.md`` §1, the 2026-10-23 review's F3).
- **The evidence block is deterministic; the clock is not in it.**  ``provenance``
  is built from the request and the input alone, and the handles it mentions are
  digests of those same inputs, so the same request against the same file yields
  byte-identical evidence in any process.  The wall-clock run time rides beside
  it in ``event``, outside the block the determinism rule constrains
  (``AGENTS.md`` §1.7).
- **A missing value is refused, not encoded.**  No non-finite number reaches a
  response: metric values are guarded, and the geometry layer refuses a trace
  with a non-finite sample (``PeakGeometryError``) instead of returning a
  geometry computed around a gap.  So the payload needs no NaN token — every
  float in it is a measured number (``AGENTS.md`` §1.6).

``integrate_peaks`` is not a competing integrator (``AGENTS.md`` §3): it measures
the **caller-supplied** windows through the W2 geometry and detects nothing.
``assess_sequence`` and ``trend_qc`` are M3 and return "not implemented in this
unit".

``load_chromatogram`` resolves its path through the **filesystem boundary**
(``chromamcp.security``) and reads the file **once**, so the hash it reports and
the chromatograms it returns describe the same bytes (W12).
"""

from __future__ import annotations

import hashlib
import logging
import sys
from dataclasses import asdict
from datetime import UTC, datetime

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
from chromamcp.io.mzml import Chromatogram, read_chromatograms_with_source
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
from chromamcp.provenance import TOLERANCE_BASIS, library_versions
from chromamcp.security import FilesystemPolicy, policy_from_env, resolve_path
from chromamcp.server.store import ReferenceStore

__all__ = ["build_server", "main"]

_INSTRUCTIONS = (
    "ChromaMCP measures chromatography — system-suitability metrics, each with "
    "its cited formula and derived tolerance, and (later) sequence review against "
    "a laboratory's own written criteria.  Every response carries a provenance "
    "block and every metric names the peak or pair it was measured on.  It "
    "reports measurements, never a verdict on a method."
)
_NOT_BUILT = (
    "{tool} is not implemented in this unit.  Sequence and trend logic is M3 "
    "(AGENTS.md section 3); it returns this explicit error rather than a result."
)
_TIMESTAMP_NOTE = "run time, not acquisition time"


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _content_key(*parts: object) -> str:
    """A short digest of the request and its input — a reproducible handle name."""
    joined = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


def _provenance(
    source: str | None,
    sha256: str | None,
    *,
    operation: dict[str, object],
) -> dict[str, object]:
    """The deterministic half of the response: no clock, no allocation order.

    Same input file + same parameters + same versions ⇒ byte-identical content
    here (``AGENTS.md`` §1.7).  The run time is in the sibling ``event`` block,
    which is metadata about the call rather than part of the evidence.
    """
    return {
        "input_file": None if source is None else {"path": source, "sha256": sha256},
        "reader": "chromamcp.io.mzml",
        "library_versions": asdict(library_versions()),
        "criteria": None,
        "tolerance_basis": TOLERANCE_BASIS,
        "operation": operation,
    }


def _event() -> dict[str, object]:
    """When the call ran.  Outside the evidence block by design."""
    return {"timestamp_utc": _utc_now(), "timestamp_note": _TIMESTAMP_NOTE}


def _metric(
    result: MetricResult, *, subject: str, peaks: list[str]
) -> dict[str, object]:
    """One metric row, naming the subject it was measured on.

    ``measurement_id`` is ``"<metric id>@<subject>"`` and is reproducible for the
    same request, so two rows for the same subject cannot be confused for each
    other by their position in the list.
    """
    return {
        "measurement_id": f"{result.metric_id}@{subject}",
        "metric_id": result.metric_id,
        "subject": subject,
        "peaks": peaks,
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


def _as_mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _as_str(value: object) -> str:
    assert isinstance(value, str)
    return value


def _peak_id(channel: int, left: int, right: int) -> str:
    """A peak's id encodes the channel and the window it was measured over."""
    return f"peak:c{channel}:w{left}-{right}"


def _measure(
    time: NDArray[np.float64],
    intensity: NDArray[np.float64],
    left: int,
    right: int,
    *,
    channel: int,
) -> dict[str, object]:
    """Measure one caller-supplied window, against a linear baseline.

    The row carries everything a reader needs to redo the measurement: the
    window in indices and in retention time, the baseline rule, the apex, the
    widths, and the area as a metric row with its formula id and tolerance.
    Apex selection and interpolation use intensity above the same anchored line
    as height, widths and area; the raw-intensity maximum is not used.
    """
    if not 0 <= left < right < int(time.size):
        raise ToolError(
            f"window [{left}, {right}] must satisfy 0 <= left < right < n_points."
        )
    peak = _peak_id(channel, left, right)
    baseline: Baseline = resolve_baseline(
        BaselineRule.LINEAR, time, intensity, left_index=left, right_index=right
    )
    apex = find_apex(
        time, intensity, baseline=baseline, left_index=left, right_index=right
    )
    half = half_height_width(time, intensity, baseline=baseline, apex=apex)
    five = five_percent_width(time, intensity, baseline=baseline, apex=apex)
    area = peak_area(
        time, intensity, baseline=baseline, left_index=left, right_index=right
    )
    height = peak_height(
        apex_intensity=apex.intensity, baseline_at_apex=baseline.value(apex.time)
    )
    return {
        "id": peak,
        "channel": channel,
        "window": {
            "left_index": left,
            "right_index": right,
            "t_left_min": float(time[left]),
            "t_right_min": float(time[right]),
        },
        "baseline_rule": BaselineRule.LINEAR.value,
        "baseline_anchors": {
            "left": {
                "index": left,
                "time_min": float(time[left]),
                "intensity": float(intensity[left]),
            },
            "right": {
                "index": right,
                "time_min": float(time[right]),
                "intensity": float(intensity[right]),
            },
        },
        "apex": {
            "index": apex.index,
            "time_min": apex.time,
            "intensity": apex.intensity,
            "baseline": baseline.value(apex.time),
            "height": height.value,
        },
        "widths": {
            "half_min": half.width,
            "at_5pct_min": five.width,
            "front_5pct_min": five.front_distance,
        },
        "measurements": {
            "area": _metric(area, subject=peak, peaks=[peak]),
            "height": _metric(height, subject=peak, peaks=[peak]),
        },
    }


def _per_peak(
    rows: list[dict[str, object]], void_time: float | None
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in rows:
        peak = _as_str(row["id"])
        apex = _as_mapping(row["apex"])
        widths = _as_mapping(row["widths"])
        apex_time = _as_float(apex["time_min"])
        out.append(
            _metric(
                plate_number(
                    apex_time=apex_time,
                    half_height_width=_as_float(widths["half_min"]),
                ),
                subject=peak,
                peaks=[peak],
            )
        )
        out.append(
            _metric(
                symmetry_factor(
                    width_at_5pct=_as_float(widths["at_5pct_min"]),
                    front_distance_at_5pct=_as_float(widths["front_5pct_min"]),
                ),
                subject=peak,
                peaks=[peak],
            )
        )
        out.append(
            _metric(
                peak_height(
                    apex_intensity=_as_float(apex["intensity"]),
                    baseline_at_apex=_as_float(apex["baseline"]),
                ),
                subject=peak,
                peaks=[peak],
            )
        )
        if void_time is not None:
            out.append(
                _metric(
                    capacity_factor(apex_time=apex_time, void_time=void_time),
                    subject=peak,
                    peaks=[peak],
                )
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
        low_id = _as_str(low["id"])
        high_id = _as_str(high["id"])
        subject = f"{low_id}|{high_id}"
        low_apex, high_apex = _as_mapping(low["apex"]), _as_mapping(high["apex"])
        low_widths = _as_mapping(low["widths"])
        high_widths = _as_mapping(high["widths"])
        out.append(
            _metric(
                resolution(
                    first_apex_time=_as_float(low_apex["time_min"]),
                    first_half_height_width=_as_float(low_widths["half_min"]),
                    second_apex_time=_as_float(high_apex["time_min"]),
                    second_half_height_width=_as_float(high_widths["half_min"]),
                ),
                subject=subject,
                peaks=[low_id, high_id],
            )
        )
        if void_time is not None:
            out.append(
                _metric(
                    selectivity(
                        first_apex_time=_as_float(low_apex["time_min"]),
                        second_apex_time=_as_float(high_apex["time_min"]),
                        void_time=void_time,
                    ),
                    subject=subject,
                    peaks=[low_id, high_id],
                )
            )
    return out


def build_server(*, policy: FilesystemPolicy | None = None) -> MCPServer:
    """Build the server: its tool set, a reference store and a path policy.

    *policy* defaults to :func:`~chromamcp.security.policy_from_env`, i.e. the
    root named by ``CHROMAMCP_ALLOWED_ROOT`` or the working directory.
    """
    server: MCPServer = MCPServer(
        name="chromamcp", version=__version__, instructions=_INSTRUCTIONS
    )
    store = ReferenceStore()
    policy = policy_from_env() if policy is None else policy

    @server.tool(
        name="load_chromatogram",
        description="Read an mzML file's TIC/XIC channels; returns a handle.",
    )
    def load_chromatogram(path: str) -> dict[str, object]:
        try:
            allowed = resolve_path(path, policy=policy)
            snapshot, chromatograms = read_chromatograms_with_source(allowed)
        except ChromamcpError as exc:
            raise ToolError(str(exc)) from exc
        resolved = snapshot.path
        reference = store.put(
            "chromatograms",
            {
                "channels": chromatograms,
                "source": resolved,
                "sha256": snapshot.sha256,
                "n_bytes": snapshot.n_bytes,
            },
            key=_content_key("chromatograms", snapshot.sha256, resolved, __version__),
        )
        return {
            "reference": reference,
            "n_channels": len(chromatograms),
            "n_bytes": snapshot.n_bytes,
            "channels": [
                _channel(index, item) for index, item in enumerate(chromatograms)
            ],
            "provenance": _provenance(
                resolved,
                snapshot.sha256,
                operation={
                    "tool": "load_chromatogram",
                    "arguments": {"path": resolved},
                },
            ),
            "event": _event(),
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
            "n_bytes": payload["n_bytes"],
            "time_min": None
            if not spans
            else [min(low for low, _ in spans), max(high for _, high in spans)],
            "channels": [
                _channel(index, item) for index, item in enumerate(chromatograms)
            ],
            "provenance": _provenance(
                payload["source"],
                payload["sha256"],
                operation={
                    "tool": "summarise_chromatogram",
                    "arguments": {"reference": reference},
                },
            ),
            "event": _event(),
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
            rows = [
                _measure(time, intensity, left, right, channel=channel)
                for left, right in windows
            ]
        except ChromamcpError as exc:
            raise ToolError(str(exc)) from exc
        peaks_ref = store.put(
            "peaks",
            {
                "rows": rows,
                "baseline_rule": BaselineRule.LINEAR.value,
                "channel": channel,
                "windows": windows,
                "source": payload["source"],
                "sha256": payload["sha256"],
            },
            key=_content_key(
                "peaks",
                reference,
                channel,
                windows,
                BaselineRule.LINEAR.value,
            ),
        )
        return {
            "reference": peaks_ref,
            "n_peaks": len(rows),
            "channel": channel,
            "baseline_rule": BaselineRule.LINEAR.value,
            "windows": windows,
            "peaks": rows,
            "provenance": _provenance(
                payload["source"],
                payload["sha256"],
                operation={
                    "tool": "integrate_peaks",
                    "arguments": {
                        "channel": channel,
                        "windows": windows,
                        "baseline_rule": BaselineRule.LINEAR.value,
                        "source_reference": reference,
                    },
                },
            ),
            "event": _event(),
        }

    @server.tool(
        name="compute_suitability",
        description=(
            "The metric panel for a peak table, each value with its formula id, "
            "derived tolerance and the peak or pair it was measured on."
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
                subject = f"replicates:n={len(replicate_areas)}"
                metrics.append(
                    _metric(
                        rsd_replicates(replicate_areas),
                        subject=subject,
                        peaks=[],
                    )
                )
        except ChromamcpError as exc:
            raise ToolError(str(exc)) from exc
        not_evaluated: list[dict[str, object]] = [
            {
                "metric_id": "peak_to_valley",
                "reason": "p/v needs an unresolved pair's valley intensity, which "
                "the peak table does not carry in this unit.",
            },
            {
                "metric_id": "signal_to_noise",
                "reason": "S/N needs a blank region, which the peak table does not "
                "carry. Supply one: h is peak-to-peak noise over 20× the peak's "
                "half-height width, with 5× the permitted fallback where a 20× "
                "baseline is unobtainable.",
            },
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
            "n_peaks": len(rows),
            "metrics": metrics,
            "not_evaluated": not_evaluated,
            "provenance": _provenance(
                payload["source"],
                payload["sha256"],
                operation={
                    "tool": "compute_suitability",
                    "arguments": {
                        "peaks": peaks,
                        "void_time": void_time,
                        "pairs": pairs,
                        "replicate_areas": replicate_areas,
                        "baseline_rule": payload["baseline_rule"],
                    },
                },
            ),
            "event": _event(),
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
        return {"reference": reference, "released": True, "event": _event()}

    return server


def main() -> None:
    """Run the server over stdio.  stdout carries protocol frames and nothing else."""
    logging.basicConfig(stream=sys.stderr)
    build_server().run("stdio")
