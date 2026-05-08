from __future__ import annotations

import pandas as pd
import pytest

from app.services.panel_pipeline.diff.feed_diff import FeedDiff, feed_diff


def _stops(rows):
    return pd.DataFrame(rows, columns=["stop_id", "stop_name", "stop_lat", "stop_lon"])


def _routes(rows):
    return pd.DataFrame(rows, columns=["route_id", "route_short_name", "route_type"])


def test_feed_diff_added_removed():
    a = {"stops": _stops([("S1", "A", 0.0, 0.0), ("S2", "B", 1.0, 1.0)]),
         "routes": _routes([("R1", "1", 3)])}
    b = {"stops": _stops([("S2", "B", 1.0, 1.0), ("S3", "C", 2.0, 2.0)]),
         "routes": _routes([("R1", "1", 3), ("R2", "2", 3)])}
    d = feed_diff(a, b)
    assert d.stops_added == ["S3"]
    assert d.stops_removed == ["S1"]
    assert d.stops_modified == {}
    assert d.routes_added == ["R2"]
    assert d.routes_removed == []
    assert pytest.approx(d.stop_jaccard, abs=1e-6) == 1 / 3
    assert pytest.approx(d.route_jaccard, abs=1e-6) == 1 / 2


def test_feed_diff_modified_field():
    a = {"stops": _stops([("S1", "Old", 0.0, 0.0)]), "routes": _routes([])}
    b = {"stops": _stops([("S1", "New", 0.001, 0.0)]), "routes": _routes([])}
    d = feed_diff(a, b)
    assert d.stops_modified == {"S1": {"stop_name": ["Old", "New"], "stop_lat": [0.0, 0.001]}}
    assert d.stops_added == []
    assert d.stops_removed == []


def test_feed_diff_identical_full_jaccard():
    a = {"stops": _stops([("S1", "A", 0.0, 0.0)]), "routes": _routes([("R1", "1", 3)])}
    d = feed_diff(a, a)
    assert d.stop_jaccard == 1.0
    assert d.route_jaccard == 1.0
    assert d.stops_added == [] and d.stops_removed == [] and d.stops_modified == {}


def test_feed_diff_duplicate_stop_id_raises():
    """C1 regression: duplicate stop_id in input raises a clear ValueError."""
    dup = _stops([("S1", "A", 0.0, 0.0), ("S1", "A2", 0.5, 0.0)])
    clean = _stops([("S1", "A", 0.0, 0.0)])
    a = {"stops": dup, "routes": _routes([])}
    b = {"stops": clean, "routes": _routes([])}
    with pytest.raises(ValueError, match="duplicate stop_id"):
        feed_diff(a, b)


def test_feed_diff_duplicate_route_id_raises():
    """C1 regression: duplicate route_id raises ValueError."""
    a = {"stops": _stops([]), "routes": _routes([("R1", "1", 3), ("R1", "1bis", 3)])}
    b = {"stops": _stops([]), "routes": _routes([("R1", "1", 3)])}
    with pytest.raises(ValueError, match="duplicate route_id"):
        feed_diff(a, b)


def test_feed_diff_nan_both_sides_not_modified():
    """C2 regression: NaN on both sides is not a modification."""
    import math
    a = {"stops": _stops([("S1", "A", 0.0, math.nan)]), "routes": _routes([])}
    b = {"stops": _stops([("S1", "A", 0.0, math.nan)]), "routes": _routes([])}
    d = feed_diff(a, b)
    assert d.stops_modified == {}


def test_feed_diff_nan_to_value_is_modified():
    """C2 regression: NaN -> value (or value -> NaN) IS a modification."""
    import math
    a = {"stops": _stops([("S1", "A", 0.0, math.nan)]), "routes": _routes([])}
    b = {"stops": _stops([("S1", "A", 0.0, 1.5)]), "routes": _routes([])}
    d = feed_diff(a, b)
    assert "S1" in d.stops_modified
    assert d.stops_modified["S1"]["stop_lon"][0] != d.stops_modified["S1"]["stop_lon"][1]
