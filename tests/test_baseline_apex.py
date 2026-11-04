"""A1: one explicit baseline for the apex and the resulting measurements."""

from typing import Any

import numpy as np
import pytest

from chromamcp.errors import PeakGeometryError
from chromamcp.geometry import Baseline, find_apex, half_height_width
from chromamcp.server.server import _measure, _per_peak


def test_sloped_baseline_window_uses_adjusted_apex() -> None:
    time = np.linspace(0.0, 10.0, 1001)
    intensity = 10 * time + 2 * np.exp(-0.5 * ((time - 5) / 0.4) ** 2)
    assert int(np.argmax(intensity[300:701])) + 300 == 700
    # Independent route: interpolate the two anchors, subtract, and locate
    # crossings by inverse interpolation of each monotonic half of the peak.
    t = time[300:701]
    anchors = intensity[[300, 700]]
    above = intensity[300:701] - np.interp(t, t[[0, -1]], anchors)
    index = int(np.argmax(above))
    assert index + 300 == 500
    height = float(above[index])
    half = float(np.interp(height / 2, above[: index + 1], t[: index + 1]))
    five = float(np.interp(height / 20, above[: index + 1], t[: index + 1]))
    half_right = float(np.interp(height / 2, above[index:][::-1], t[index:][::-1]))
    five_right = float(np.interp(height / 20, above[index:][::-1], t[index:][::-1]))
    # Sum trapezoids independently rather than call the production area route.
    area = float(np.sum(np.diff(t) * (above[:-1] + above[1:]) / 2))
    row: Any = _measure(time, intensity, 300, 700, channel=0)
    assert row["baseline_anchors"] == {
        "left": {"index": 300, "time_min": 3.0, "intensity": float(anchors[0])},
        "right": {"index": 700, "time_min": 7.0, "intensity": float(anchors[1])},
    }
    assert row["apex"]["index"] == 500
    assert row["apex"]["time_min"] == pytest.approx(float(t[index]))
    assert row["apex"]["height"] == pytest.approx(height)
    assert row["widths"]["half_min"] == pytest.approx(half_right - half)
    assert row["widths"]["at_5pct_min"] == pytest.approx(five_right - five)
    assert row["measurements"]["area"]["value"] == pytest.approx(area)
    metrics: Any = _per_peak([row], 1.0)
    assert metrics[0]["value"] == pytest.approx(
        5.54 * (t[index] / (half_right - half)) ** 2
    )
    assert metrics[1]["value"] == pytest.approx(
        (five_right - five) / (2 * (t[index] - five))
    )
    assert metrics[2]["value"] == pytest.approx(height)
    assert metrics[3]["value"] == pytest.approx((t[index] - 1) / 1)


def test_baseline_adjusted_subsample_apex_and_implicit_width() -> None:
    time = np.linspace(0.0, 2.0, 201)
    above = 2 - (time - 0.803) ** 2
    intensity = above + 10 * time
    baseline = Baseline(0.0, 10.0)
    apex = find_apex(time, intensity, baseline=baseline)
    assert apex.interpolated
    assert apex.time == pytest.approx(0.803)
    assert apex.intensity == pytest.approx(2 + 10 * 0.803)
    # A genuine missing crossing must still be refused on the corrected route.
    with pytest.raises(PeakGeometryError, match="leading edge"):
        half_height_width(time, intensity, baseline=baseline)
