"""Tests for metro_manila.py: the Metro Manila test in Python, on the API's own boundary
file and S2's points (MS4 spec §4.3, §7 S2; plan Task 2).

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" --with pyyaml pytest -q
        backend/scripts/test_metro_manila.py
"""

import json
from pathlib import Path

import pytest
from metro_manila import NCR, geohash6, in_boundary, in_metro_manila, load_boundary

S2 = (
    Path(__file__).resolve().parents[1] / "api" / "test" / "fixtures" / "s2-points.json"
)
MS1_POINT = (14.6095, 120.9894)
SQUARE = [
    [120.98, 14.6],
    [121.0, 14.6],
    [121.0, 14.62],
    [120.98, 14.62],
    [120.98, 14.6],
]


def test_s2_points_agree_with_the_api():
    points = json.loads(S2.read_text(encoding="utf-8"))
    assert len(points) == 15
    assert load_boundary(NCR) is not None
    for point in points:
        inside = in_metro_manila(point["lat"], point["lng"])
        assert inside is point["inside"], point["name"]


@pytest.mark.parametrize(
    "text",
    [
        "{}",
        "not json",
        json.dumps({"type": "Polygon", "coordinates": [SQUARE]}),
        json.dumps({"type": "MultiPolygon", "coordinates": [[SQUARE[:3]]]}),
        # Python's json reads NaN, which JSON.parse refuses, so the check must too.
        '{"type": "MultiPolygon", "coordinates": [[[[120.98, 14.6], [121.0, 14.6], [121.0, NaN], [120.98, 14.6]]]]}',
        json.dumps(
            {
                "type": "MultiPolygon",
                "coordinates": [
                    [[[120.98, 14.6], [121.0, True], [121.0, 14.62], [120.98, 14.6]]]
                ],
            }
        ),
    ],
)
def test_a_missing_or_malformed_boundary_reads_as_outside(tmp_path, text):
    assert load_boundary(tmp_path / "missing.json") is None
    bad = tmp_path / "ncr.json"
    bad.write_text(text, encoding="utf-8")
    assert load_boundary(bad) is None
    assert in_boundary(load_boundary(bad), *MS1_POINT) is False
    assert in_boundary(None, *MS1_POINT) is False

    # The same square, well formed, holds the point, so the refusals above aren't vacuous.
    good = tmp_path / "square.json"
    good.write_text(
        json.dumps({"type": "MultiPolygon", "coordinates": [[SQUARE]]}),
        encoding="utf-8",
    )
    assert in_boundary(load_boundary(good), *MS1_POINT) is True


def test_geohash6_matches_ngeohash():
    # MS1's cell, as ngeohash.encode(14.6095, 120.9894, 6) gives it for the report's pk.
    assert geohash6(14.6095, 120.9894) == "wdw515"
