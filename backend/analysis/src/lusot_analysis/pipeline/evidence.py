"""The evidence record: what the steps found for each numbered box (C328).

MS4 draws its overlay, its layers and its `readings` from it (MS4's C505, C507 and
C518). It is assembled from what steps 2 to 6 already hold, so it measures nothing and
nothing in the result depends on it. It outlines the numbered boxes and the water
only, never a face or a plate, and it never holds Muse Spark's reason (C62). It never
reaches a log line, and nothing in MS3b stores it. Its coordinates are the sent
image's pixels, which are the stored photo's (C48, C61).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

from lusot_analysis.annotate import NumberedBox
from lusot_analysis.meta_client import SamInstance
from lusot_analysis.pipeline.geometry import GeometryReading, KeptReading
from lusot_analysis.pipeline.waterline import Waterline

# A closed outline, as (x, y) pixel points.
Polygon = tuple[tuple[int, int], ...]

# Where Muse Spark's answer gives each kind's category: its list and its field.
_LANDMARKS = {
    "vehicle": ("vehicles", "body_waterline"),
    "wheel": ("wheels", "waterline"),
    "person": ("people", "waterline"),
}


def outline(mask: np.ndarray) -> tuple[Polygon, ...]:
    """The mask's outer contours, each simplified to within 1 px (C328).

    The contours are cv2.findContours' with RETR_EXTERNAL and CHAIN_APPROX_SIMPLE,
    each simplified with cv2.approxPolyDP(contour, 1.0, True). A contour left with
    under 3 points is left out, and an empty mask gives ().
    """
    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    polygons = []
    for contour in contours:
        points = cv2.approxPolyDP(contour, 1.0, True).reshape(-1, 2)
        if len(points) >= 3:
            polygons.append(tuple((int(x), int(y)) for x, y in points))
    return tuple(polygons)


@dataclass(frozen=True)
class RimDrawing:
    """The rim fit as cv2.fitEllipse returned it, which cv2.ellipse draws.

    `axes` are its full axes, in its order, and `angle_deg` its angle in degrees.
    """

    centre: tuple[float, float]
    axes: tuple[float, float]
    angle_deg: float


@dataclass(frozen=True, kw_only=True)
class EvidenceEntry:
    """One numbered box, and what the steps found for it (C328).

    - `kind`: a vehicle's box is `body`, since its reading is its body's. `box` is the
      numbered box, half-open, and `outline` its SAM mask's.
    - `landmark`: Muse Spark's category for the box (a wheel's or a person's
      `waterline`, a vehicle's `body_waterline`), or None when it is unanswered.
    - `level`, `level_from`: the box's own reading, or None when it gives none. A box
      with two readings shows the one that can decide (R147). A reading step 3
      dropped keeps its level here (C317).
    - `inches`: geometry's unrounded min and max whenever geometry measured the
      wheel, G4's drop included. `rim`: the fit, with a geometry reading only.
    - `rim_outline`: on a wheel, the outline of the one `wheel rim` mask step 2
      linked to it, with or without a geometry reading; () with none or several.
    - `waterline`: step 3's y_w from its first to its last touching column, wherever
      step 3 found one.
    - `used`: its reading entered the combine as one that can decide, so on a level
      result it counts in `basis`. `deciding`: it set the level.
    - `dropped`: its first cause, or None. `rechecked`: only the self-check sets it
      (C311).
    """

    id: int
    kind: Literal["wheel", "body", "person"]
    box: tuple[int, int, int, int]
    outline: tuple[Polygon, ...]
    landmark: str | None
    level: str | None
    level_from: Literal["landmark", "geometry"] | None
    inches: tuple[float, float] | None
    rim: RimDrawing | None
    rim_outline: tuple[Polygon, ...] = ()
    waterline: tuple[tuple[float, float], tuple[float, float]] | None
    used: bool
    deciding: bool
    dropped: str | None
    rechecked: bool = False


@dataclass(frozen=True)
class Evidence:
    """Every numbered box's entry, in box-id order, and the water mask's outline."""

    references: tuple[EvidenceEntry, ...]
    water_outline: tuple[Polygon, ...]


def build_evidence(
    boxes: Sequence[NumberedBox],
    instances: Mapping[int, SamInstance],
    answer: dict,
    water: np.ndarray,
    *,
    rims: Mapping[int, SamInstance],
    causes: Mapping[int, str],
    readings: Mapping[int, KeptReading],
    waterlines: Mapping[int, Waterline],
    geometry: Mapping[int, GeometryReading],
    used: frozenset[int],
    deciding: int | None,
) -> Evidence:
    """The record of what steps 2 to 6 found, for each numbered box.

    `instances` holds each numbered box's SAM instance and `rims` each wheel's one
    linked rim (R127), both by box id. `answer` has passed the schema and the id
    check; only its lists are read, never its reason (C62). The rest are the steps'
    own, by box id: `causes` each dropped box's first cause, `readings` the reading
    each box gives, `waterlines` step 3's, `geometry` each measured wheel's, `used`
    the boxes whose reading entered the combine as one that can decide, and
    `deciding` the box that set the level, or None.
    """
    landmarks = {
        kind: {item["id"]: item[key] for item in answer[name]}
        for kind, (name, key) in _LANDMARKS.items()
    }
    entries = []
    for box in sorted(boxes, key=lambda b: b.id):
        reading = readings.get(box.id)
        inches = drawing = None
        measured = geometry.get(box.id)
        if measured is not None:
            inches = (measured.depth_in_min, measured.depth_in_max)
            fit = measured.fit
            if fit is not None:
                centre = (fit.centre_x, fit.centre_y)
                drawing = RimDrawing(centre, fit.axes, fit.angle_deg)
        rim = rims.get(box.id) if box.kind == "wheel" else None
        entries.append(
            EvidenceEntry(
                id=box.id,
                kind="body" if box.kind == "vehicle" else box.kind,
                box=box.box,
                outline=outline(instances[box.id].mask),
                landmark=landmarks[box.kind].get(box.id),
                level=None if reading is None else reading.reading.level,
                level_from=None if reading is None else reading.level_from,
                inches=inches,
                rim=drawing,
                rim_outline=() if rim is None else outline(rim.mask),
                waterline=_waterline(waterlines.get(box.id)),
                used=box.id in used,
                deciding=box.id == deciding,
                dropped=causes.get(box.id),
            )
        )
    return Evidence(tuple(entries), outline(water))


def _waterline(
    found: Waterline | None,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Step 3's waterline as two points, (x_first, y_w) and (x_last, y_w), or None."""
    if found is None or found.y_w is None or found.x_span is None:
        return None
    x_first, x_last = found.x_span
    return (float(x_first), found.y_w), (float(x_last), found.y_w)
