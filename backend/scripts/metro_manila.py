"""The Metro Manila test for the scripts, on the API's own boundary file (C502).

`backend/api/src/data/ncr.json` is OpenStreetMap's Metro Manila clipped to the
coastline (its NCR_SOURCE.md says how). The API reads the same file, and both
apply the same rule: even-odd ray casting over every ring, so a hole counts as
outside. A file that is missing or malformed contains no point, so a script that
asks gets "outside", never "inside" (spec §4.3).
"""

import json
import math
from pathlib import Path

NCR = Path(__file__).parents[1] / "api" / "src" / "data" / "ncr.json"

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def load_boundary(path: Path = NCR) -> list | None:
    """The MultiPolygon's coordinates, or None unless every ring has at least 4 finite points."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("type") != "MultiPolygon":
        return None
    polygons = data.get("coordinates")
    if not _non_empty_list(polygons):
        return None
    for polygon in polygons:
        if not _non_empty_list(polygon):
            return None
        for ring in polygon:
            if (
                not isinstance(ring, list)
                or len(ring) < 4
                or not all(map(_point, ring))
            ):
                return None
    return polygons


def in_boundary(boundary: list | None, lat: float, lng: float) -> bool:
    if boundary is None:
        return False
    inside = False
    for polygon in boundary:
        for ring in polygon:
            # Each point with the one before it, the first with the last.
            for (xi, yi, *_), (xj, yj, *_) in zip(ring, ring[-1:] + ring[:-1]):
                spans = (yi > lat) != (yj > lat)
                if spans and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                    inside = not inside
    return inside


def in_metro_manila(lat: float, lng: float) -> bool:
    return in_boundary(load_boundary(), lat, lng)


def geohash6(lat: float, lng: float) -> str:
    """The standard base-32 geohash to 6 characters, as the API's ngeohash makes MS1's pk."""
    lat_lo, lat_hi, lng_lo, lng_hi = -90.0, 90.0, -180.0, 180.0
    cell, bits, value, even = [], 0, 0, True
    while len(cell) < 6:
        if even:
            mid = (lng_lo + lng_hi) / 2
            bit = lng > mid
            lng_lo, lng_hi = (mid, lng_hi) if bit else (lng_lo, mid)
        else:
            mid = (lat_lo + lat_hi) / 2
            bit = lat > mid
            lat_lo, lat_hi = (mid, lat_hi) if bit else (lat_lo, mid)
        value = value * 2 + bit
        bits += 1
        even = not even
        if bits == 5:
            cell.append(_BASE32[value])
            bits, value = 0, 0
    return "".join(cell)


def _non_empty_list(value: object) -> bool:
    return isinstance(value, list) and len(value) > 0


def _point(value: object) -> bool:
    # JSON booleans are ints in Python, and Python's json reads NaN, so both are refused here.
    return (
        isinstance(value, list)
        and len(value) >= 2
        and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
            for v in value
        )
    )
