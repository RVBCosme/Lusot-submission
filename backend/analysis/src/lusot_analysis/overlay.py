"""The overlay: the evidence drawn on the stored photo, its layers and its readings.

For a level result the analysis Lambda draws MS3b's evidence record (C328) on the
stored photo, the one `publish_jpeg` makes with SAM's faces and plates blurred (C48,
C61), and keeps the same marks as vectors beside it (C505, C524). The record has the
water's outline and, for each numbered box, its outline, its linked rim's outline, its
fitted rim, its waterline and its reading. It holds no face or plate, so none is drawn.
`readings` is built from the record alone (C507).

Nothing here shows inches. A label says the landmark and the level in words (C81's
wording, without "at this spot"), and Rene reviews the words (M20). Models never output
inches, and code does all the measuring (CLAUDE.md).

The colours are fixed, since a JPEG has no app theme. Every line is drawn twice, a wide
black halo and then its colour, so it shows on a bright photo through the halo and on a
dark one through the colour. The hues are told apart by more than colour too: the water
is dashed, the fitted rim is an ellipse, the box is rectangular, the waterline carries
end ticks, and a re-checked wheel's box has a second border inside it.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from itertools import pairwise

import cv2
import numpy as np

from lusot_analysis import rules
from lusot_analysis.face_blur import decode_image
from lusot_analysis.pipeline.evidence import Evidence, EvidenceEntry

OVERLAY_JPEG_QUALITY = 90
LAYERS_VERSION = 1
_KINDS = frozenset({"wheel", "body", "person"})

# The 9 levels, in C81's words without "at this spot".
LEVEL_WORDS: Mapping[str, str] = {
    "below_gutter": "Below gutter deep",
    "gutter": "Gutter deep",
    "half_knee": "Half-knee deep",
    "half_tire": "Half-tire deep",
    "knee": "Knee deep",
    "tire": "Tire deep",
    "waist": "Waist deep",
    "chest": "Chest deep",
    "above_chest": "Above chest deep",
}

# A floor reading (C54) is "this level or deeper", so its label says so, in Rene's
# wording (Oct 30, M20) as the app's result card has it: `{level}` takes the level's
# words from LEVEL_WORDS, lowercased. The app's Taglish is "Hindi bababa sa {level}".
FLOOR_WORDS = "At least {level}"

# Muse Spark's categories, as they read after a box number: where the water is on the
# wheel, the person or the vehicle's body. One table, since "not_visible" is in three.
LANDMARK_WORDS: Mapping[str, str] = {
    # wheels (rules.WHEEL_ROWS)
    "tire_only": "tire only",
    "rim_quarter": "rim quarter",
    "hub": "hub",
    "rim_three_quarters": "rim three-quarters",
    "rim_top": "rim top",
    "wheel_covered": "wheel covered",
    # people (rules.PEOPLE_ROWS)
    "ankle": "ankle",
    "mid_shin": "mid-shin",
    "knee": "knee",
    "mid_thigh": "mid-thigh",
    "waist": "waist",
    "chest": "chest",
    "above_chest": "above chest",
    # a vehicle's body (rules.BODY_ROWS)
    "mid_door": "mid-door",
    "window": "window",
    "below_bumper": "below bumper",
    "bumper": "bumper",
    "door_sill": "door sill",
    # all three
    "not_visible": "not visible",
}


def _bgr(rgb: str) -> tuple[int, int, int]:
    """OpenCV's blue, green, red for a hex colour written as red, green, blue."""
    red, green, blue = (int(rgb[i : i + 2], 16) for i in (1, 3, 5))
    return blue, green, red


_HALO = (0, 0, 0)  # pure black: the 10 and 245 test photos both differ from it
_CHIP = _bgr("#0C1014")  # a label's ground
# Each mark's colour and its halo, in BGR. Every colour is at least 4.5:1 against its
# halo and against a photo as dark as 10; every halo is at least 4.5:1 against a photo
# as bright as 245 (tests/test_overlay.py). The hues follow Okabe and Ito's
# palette for readers with colour-vision deficiency, raised to carry on a photo.
MARKS: Mapping[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "water": (_bgr("#2EB8FF"), _HALO),  # sky blue, dashed
    "outline": (_bgr("#FFD60A"), _HALO),  # yellow: a reference's mask
    "rim_outline": (_bgr("#FF8A1F"), _HALO),  # orange: the linked rim's mask
    "box": (_bgr("#FFFFFF"), _HALO),  # white: the numbered box
    "fitted_rim": (_bgr("#5BFF8A"), _HALO),  # green: geometry's ellipse
    "waterline": (_bgr("#FF3D9A"), _HALO),  # magenta: where the water meets it
    "label": (_bgr("#FFFFFF"), _CHIP),  # white text on a dark chip
}
# How much of a dropped reference's marks shows (§4.2: dropped references are dimmed),
# and how much of its label, which has to stay readable.
_DIM = 0.4
_DIM_LABEL = 0.7


# The layers and readings


def _entries(evidence: Evidence) -> list[EvidenceEntry]:
    """The record's entries in id order, once each, and only of the three kinds.

    MS3b's record holds one entry per box (R147), so a repeated id is a fault to stop
    on, not one to merge. A kind other than a wheel, a body or a person, such as a face
    or a plate, can never be drawn or stored.
    """
    entries = sorted(evidence.references, key=lambda entry: entry.id)
    if len({entry.id for entry in entries}) != len(entries):
        raise ValueError("the evidence record holds an id twice")
    for entry in entries:
        if entry.kind not in _KINDS:
            raise ValueError(f"not a numbered kind: {entry.kind!r}")
    return entries


def _pixel(point: tuple[float, float]) -> list[int]:
    """A point rounded to whole pixels."""
    return [round(point[0]), round(point[1])]


def _polygons(polygons) -> list[list[list[int]]]:
    return [[_pixel(point) for point in polygon] for polygon in polygons]


def _tenths(values) -> list[float]:
    return [round(float(value), 1) for value in values]


def layers(evidence: Evidence, size: tuple[int, int]) -> dict:
    """The marks as vectors, for `overlay/{id}.json` (C524). `size` is (width, height).

    The coordinates are the stored photo's pixels, whole ones except the fitted rim's,
    which are rounded to 0.1. Each reference is as the record holds it, in id order. A
    dropped reference carries no level (§4.2), so its `level`, `level_from` and
    `level_is_floor` are null, and `dropped` is the dimmed state. `level_is_floor` is the
    record's own flag (C54): "this level or deeper", null with no level. No inches and no
    face or plate are in it.
    """
    width, height = size
    refs = []
    for entry in _entries(evidence):
        dropped = entry.dropped is not None
        has_level = not dropped and entry.level is not None
        refs.append(
            {
                "id": entry.id,
                "kind": entry.kind,
                "box": [int(value) for value in entry.box],
                "outline": _polygons(entry.outline),
                "rim_outline": (
                    _polygons(entry.rim_outline) if entry.rim_outline else None
                ),
                "landmark": entry.landmark,
                "level": None if dropped else entry.level,
                "level_from": None if dropped else entry.level_from,
                "level_is_floor": entry.level_is_floor if has_level else None,
                "used": entry.used,
                "dropped": entry.dropped,
                "rechecked": entry.rechecked,
                "rim": (
                    None
                    if entry.rim is None
                    else {
                        "center": _tenths(entry.rim.centre),
                        "axes": _tenths(entry.rim.axes),
                        "angle": round(float(entry.rim.angle_deg), 1),
                    }
                ),
                "waterline": (
                    None
                    if entry.waterline is None
                    else [_pixel(point) for point in entry.waterline]
                ),
            }
        )
    return {
        "version": LAYERS_VERSION,
        "width": int(width),
        "height": int(height),
        "water": _polygons(evidence.water_outline),
        "refs": refs,
    }


def readings(evidence: Evidence) -> list[dict]:
    """One reading per entry (C507): `id`, `kind`, `landmark`, `level`, `levelIsFloor`,
    `inches`, `used` and `dropped`.

    It reads the record alone. `levelIsFloor` is the record's flag (C54), None where
    `level` is None. `inches` is the rounded pair (rules.round_out) only on a deciding
    entry whose level came from geometry: the record sets inches on every wheel
    geometry measured, so any other wheel can hold inches the result doesn't rest on.
    A dropped entry's level, levelIsFloor and inches are None, and `dropped` keeps its
    cause; the record keeps the raw level. An inch value that isn't finite raises
    ValueError, on whichever entry holds it.
    """
    found = []
    for entry in _entries(evidence):
        if entry.inches is not None and not all(map(math.isfinite, entry.inches)):
            raise ValueError("the evidence record holds inches that aren't finite")
        dropped = entry.dropped is not None
        has_level = not dropped and entry.level is not None
        from_geometry = (
            entry.deciding
            and entry.level_from == "geometry"
            and not dropped
            and entry.inches is not None
        )
        found.append(
            {
                "id": entry.id,
                "kind": entry.kind,
                "landmark": entry.landmark,
                "level": None if dropped else entry.level,
                "levelIsFloor": entry.level_is_floor if has_level else None,
                "inches": list(rules.round_out(*entry.inches))
                if from_geometry
                else None,
                "used": entry.used,
                "dropped": entry.dropped,
            }
        )
    return found


def label(entry: EvidenceEntry) -> str:
    """The words on a box: its number, then what was read, never inches (C81).

    - a landmark reading: `2 rim three-quarters: Knee deep`
    - a geometry reading: `2 Half-knee deep`
    - a floor reading (the entry's `level_is_floor`, C54): its level's words take
      FLOOR_WORDS, as `1 window: At least tire deep`
    - dropped or unread: `3 knee`, or just `3` without a landmark. A dropped
      reference carries no level, even one the record kept.
    """
    words = None if entry.landmark is None else LANDMARK_WORDS[entry.landmark]
    if entry.dropped is None and entry.level is not None:
        level = LEVEL_WORDS[entry.level]
        if entry.level_is_floor:
            level = FLOOR_WORDS.format(level=level.lower())
        if entry.level_from == "geometry" or words is None:
            return f"{entry.id} {level}"
        return f"{entry.id} {words}: {level}"
    return f"{entry.id}" if words is None else f"{entry.id} {words}"


# The drawing


def draw_overlay(publish_jpeg: bytes, evidence: Evidence) -> tuple[bytes, dict]:
    """The overlay's JPEG and its layers, for the stored photo and its record (C505).

    `publish_jpeg` is the stored photo, with SAM's faces and plates blurred. The
    overlay is drawn on it and never on the image sent to Meta, whose plates aren't
    blurred. The JPEG is at OVERLAY_JPEG_QUALITY.
    """
    bgr = decode_image(publish_jpeg)
    height, width = bgr.shape[:2]
    found = layers(evidence, (width, height))
    words = {entry.id: label(entry) for entry in evidence.references}
    ok, buf = cv2.imencode(
        ".jpg",
        render(bgr, found, words),
        [cv2.IMWRITE_JPEG_QUALITY, OVERLAY_JPEG_QUALITY],
    )
    if not ok:
        raise ValueError("JPEG encoding failed")
    return buf.tobytes(), found


def render(bgr: np.ndarray, layers: dict, labels: Mapping[int, str]) -> np.ndarray:
    """A copy of `bgr` with the layers drawn on it, in C524's order.

    First `water`. Then, for each reference in order, its outline, its rim outline,
    its box, its fitted rim, its waterline and its label, where `labels` has one. A
    dropped reference is drawn dimmed. Nothing is drawn where a layer holds none, and
    nothing but the marks changes a pixel.
    """
    height, width = bgr.shape[:2]
    short = min(height, width)
    thickness = max(2, round(short / 240))
    out = bgr.copy()
    _water(out, layers["water"], thickness)
    for ref in layers["refs"]:
        dimmed = ref["dropped"] is not None
        out = _blended(out, _DIM if dimmed else 1.0, _marks, ref, thickness)
        words = labels.get(ref["id"])
        if words:
            out = _blended(
                out, _DIM_LABEL if dimmed else 1.0, _label, words, ref["box"], short
            )
    return out


def _blended(out: np.ndarray, alpha: float, draw, *args) -> np.ndarray:
    """`out` with `draw(canvas, *args)` applied: on it, or blended in at `alpha`."""
    if alpha >= 1.0:
        draw(out, *args)
        return out
    canvas = out.copy()
    draw(canvas, *args)
    return cv2.addWeighted(canvas, alpha, out, 1.0 - alpha, 0)


def _stroke(draw, marks: str, thickness: int) -> None:
    """Run `draw(colour, thickness)` twice: the wide halo, then the colour on top."""
    colour, halo = MARKS[marks]
    draw(halo, thickness + 2 * max(1, thickness // 2))
    draw(colour, thickness)


def _water(canvas: np.ndarray, polygons: list, thickness: int) -> None:
    """The water's outline, dashed, so it isn't taken for a reference's mask."""
    dashes = [
        (a, b)
        for polygon in polygons
        for a, b in _dashes(polygon, 6 * thickness, 4 * thickness)
    ]

    def draw(colour, width):
        for a, b in dashes:
            cv2.line(canvas, a, b, colour, width, cv2.LINE_AA)

    _stroke(draw, "water", thickness)


def _dashes(polygon: list, dash: float, gap: float):
    """The (start, end) pixels of each dash along a closed polygon."""
    points = np.array([*polygon, polygon[0]], float)
    drawing, left = True, dash
    for a, b in pairwise(points):
        length = float(np.hypot(*(b - a)))
        if length == 0:
            continue
        direction, at = (b - a) / length, 0.0
        while at < length:
            step = min(left, length - at)
            if drawing:
                yield _pixel(a + direction * at), _pixel(a + direction * (at + step))
            at, left = at + step, left - step
            if left <= 0:
                drawing = not drawing
                left = dash if drawing else gap


def _marks(canvas: np.ndarray, ref: dict, thickness: int) -> None:
    """One reference's lines, in order: outline, rim outline, box, fitted rim, waterline."""
    for polygons, marks in (
        (ref["outline"], "outline"),
        (ref["rim_outline"], "rim_outline"),
    ):
        if polygons:
            shapes = [np.array(polygon, np.int32) for polygon in polygons]

            def draw(colour, width, shapes=shapes):
                cv2.polylines(canvas, shapes, True, colour, width, cv2.LINE_AA)

            _stroke(draw, marks, thickness)
    _box(canvas, ref["box"], ref["rechecked"], thickness)
    if ref["rim"] is not None:
        rim = ref["rim"]
        ellipse = (tuple(rim["center"]), tuple(rim["axes"]), rim["angle"])

        def draw_rim(colour, width):
            cv2.ellipse(canvas, ellipse, colour, width, cv2.LINE_AA)

        _stroke(draw_rim, "fitted_rim", thickness)
    if ref["waterline"] is not None:
        (x0, y0), (x1, y1) = ref["waterline"]
        tick = 3 * thickness

        def draw_line(colour, width):
            cv2.line(canvas, (x0, y0), (x1, y1), colour, width, cv2.LINE_AA)
            for x, y in ((x0, y0), (x1, y1)):  # ticks mark where it starts and ends
                cv2.line(
                    canvas, (x, y - tick), (x, y + tick), colour, width, cv2.LINE_AA
                )

        _stroke(draw_line, "waterline", thickness + 1)


def _box(canvas: np.ndarray, box: list, rechecked: bool, thickness: int) -> None:
    """The numbered box. A wheel the self-check re-checked has a second border inside."""
    x0, y0, x1, y1 = box
    corners = [(x0, y0, x1 - 1, y1 - 1)]
    inset = min(2 * thickness + 2, (x1 - x0) // 4, (y1 - y0) // 4)
    if rechecked and inset >= 1:
        corners.append((x0 + inset, y0 + inset, x1 - 1 - inset, y1 - 1 - inset))

    def draw(colour, width):
        for left, top, right, bottom in corners:
            cv2.rectangle(canvas, (left, top), (right, bottom), colour, width)

    _stroke(draw, "box", thickness)


def _label(canvas: np.ndarray, words: str, box: list, short: int) -> None:
    """A dark chip with white words, sitting on the box's top edge or just inside it."""
    height, width = canvas.shape[:2]
    ink, ground = MARKS["label"]
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = max(0.5, short / 800)
    while True:  # shrink a long label until it fits the photo's width
        weight = 1 if scale < 1 else 2
        pad = max(3, round(scale * 5))
        (text_w, text_h), baseline = cv2.getTextSize(words, font, scale, weight)
        if text_w + 2 * pad <= width or scale <= 0.3:
            break
        scale *= 0.9
    chip_w, chip_h = text_w + 2 * pad, text_h + baseline + 2 * pad
    left = min(max(box[0], 0), max(width - chip_w, 0))
    top = box[1] - chip_h if box[1] >= chip_h else box[1]
    top = min(max(top, 0), max(height - chip_h, 0))
    cv2.rectangle(
        canvas, (left, top), (left + chip_w - 1, top + chip_h - 1), ground, cv2.FILLED
    )
    cv2.putText(
        canvas,
        words,
        (left + pad, top + pad + text_h),
        font,
        scale,
        ink,
        weight,
        cv2.LINE_AA,
    )
