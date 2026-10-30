"""Numbered boxes for Muse Spark (plan §7 step 4).

Each vehicle, wheel and person SAM found gets a thin outline and a label with its id,
so Muse Spark's answer names them and code ties each answer back to its mask. A box is
never filled; only its small label tag is. In MS3a's drawing, boxes-v1, its outline is
3 px wide and centred on the box's edge, so it covers the box's two outermost rows and
columns and the one just outside them. On a wheel's box, the bottom edge covers rows
y1 - 2 to y1: the wheel's lowest two rows and the row below, where the wheel meets the
water. The candidate, boxes-v2, draws the same outline outside the box, 2 px off it,
so those rows stay clear (C325).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import cv2

from lusot_analysis.face_blur import BlurredImage, blur_area, detect_faces
from lusot_analysis.meta_client import SamResult

Kind = Literal["vehicle", "wheel", "person"]

# Each kind is also its SAM phrase, and names the answer list it goes in. The order is
# the numbering order.
_LISTS: dict[Kind, str] = {"vehicle": "vehicles", "wheel": "wheels", "person": "people"}
# Outline and tag colours (BGR): cyan, yellow and magenta, as the prompt names them.
_COLOURS: dict[Kind, tuple[int, int, int]] = {
    "vehicle": (255, 255, 0),
    "wheel": (0, 255, 255),
    "person": (255, 0, 255),
}
_LINE_THICKNESS = 2  # OpenCV draws it 3 px wide, centred on the line it is given
# The drawings of the boxes' outlines (C325, §D6). outline_corners says where each goes.
DRAWINGS = ("boxes-v1", "boxes-v2")
_FONT = cv2.FONT_HERSHEY_SIMPLEX


@dataclass(frozen=True)
class NumberedBox:
    """One numbered SAM match.

    `box` is (x0, y0, x1, y1) in whole pixels of the image SAM saw. It is half-open,
    like SamInstance.box: x1 and y1 are one past the last column and row, so
    `mask[y0:y1, x0:x1]` holds the match. SAM's box is rounded outward (floor the
    start, ceil the end), so it still holds the whole match (R74).
    """

    id: int
    kind: Kind
    box: tuple[int, int, int, int]


def number_boxes(sam: dict[str, SamResult]) -> list[NumberedBox]:
    """Number the vehicles, then the wheels, then the people, from 1 (R66).

    Each kind keeps SAM's order. A phrase missing from `sam` has no matches.
    """
    boxes = []
    for kind in _LISTS:
        result = sam.get(kind)
        for instance in result.instances if result else ():
            x0, y0, x1, y1 = instance.box
            box = (math.floor(x0), math.floor(y0), math.ceil(x1), math.ceil(y1))
            boxes.append(NumberedBox(len(boxes) + 1, kind, box))
    return boxes


def outline_corners(
    box: tuple[int, int, int, int], drawing: str
) -> tuple[tuple[int, int], tuple[int, int]]:
    """The two corners draw_numbered_boxes gives cv2.rectangle for `box` (C325, §D6).

    `box` is half-open, and cv2.rectangle's corners are inclusive. At thickness 2 the
    outline is 3 px wide, centred on the line between the corners.
    - boxes-v1, MS3a's: (x0, y0) and (x1 - 1, y1 - 1), so the outline is centred on
      the box's edge. On a wheel's box it covers rows y1 - 2 to y1.
    - boxes-v2: (x0 - 4, y0 - 4) and (x1 + 3, y1 + 3), so the outline lies outside the
      box, with a 2 px gap. Its bottom covers rows y1 + 2 to y1 + 4.

    Any other drawing raises ValueError.
    """
    x0, y0, x1, y1 = box
    if drawing == "boxes-v1":
        return (x0, y0), (x1 - 1, y1 - 1)
    if drawing == "boxes-v2":
        return (x0 - 4, y0 - 4), (x1 + 3, y1 + 3)
    raise ValueError(f"drawing {drawing!r} isn't one of {DRAWINGS}")


def draw_numbered_boxes(
    img: BlurredImage, boxes: list[NumberedBox], *, drawing: str = "boxes-v1"
) -> BlurredImage:
    """Draw each box as a thin outline, and its id on a small tag in the same colour.

    The outline is cv2.rectangle at thickness 2, which OpenCV draws 3 px wide, at the
    corners outline_corners gives for `drawing`: boxes-v1, MS3a's, by default.

    The result comes from BlurredImage.derive, which keeps the blur record and blurs
    every face it finds once more (R18), so a label must miss every head. Each label
    goes above the box's top-left corner, else above its top-right, below its
    bottom-left or below its bottom-right, each moved inside the image if needed. It
    takes the first place that misses both every face found in `img`, grown by the blur
    margin, and every label drawn before it, so no label hides another's id. If none
    does, it takes the first that misses every face, and if all four meet a face, the
    first.
    """
    bgr = img.bgr()
    height, width = bgr.shape[:2]
    faces = [blur_area(face) for face in detect_faces(bgr)]  # where derive blurs
    scale = max(0.5, max(width, height) / 1600)  # digits about 11 px tall, or more
    thickness = 1 if scale < 1 else 2
    pad = thickness + 2
    for box in boxes:
        corners = outline_corners(box.box, drawing)
        cv2.rectangle(bgr, *corners, _COLOURS[box.kind], _LINE_THICKNESS)
    labels: list[tuple[int, int, int, int]] = []
    for box in boxes:  # labels go over every outline
        text = str(box.id)
        (text_w, text_h), _ = cv2.getTextSize(text, _FONT, scale, thickness)
        size = (text_w + 2 * pad, text_h + 2 * pad)
        place = _label_area(box.box, size, faces, labels, width, height)
        labels.append(place)
        lx0, ly0, lx1, ly1 = place
        cv2.rectangle(bgr, (lx0, ly0), (lx1 - 1, ly1 - 1), _COLOURS[box.kind], -1)
        cv2.putText(
            bgr, text, (lx0 + pad, ly1 - pad), _FONT, scale, (0, 0, 0), thickness
        )
    return BlurredImage.derive(bgr, img)


def check_ids(answer: dict, boxes: list[NumberedBox]) -> list[str]:
    """The problems with a schema-valid answer's ids; [] means none (R73).

    Each answered id must be a box's, sit in the list for that box's kind, and be
    answered once across vehicles, wheels and people. A box left out isn't a problem.
    """
    kinds = {box.id: box.kind for box in boxes}
    problems = []
    counts: Counter[int] = Counter()
    for kind, name in _LISTS.items():
        for item in answer[name]:
            box_id = item["id"]
            counts[box_id] += 1
            if box_id not in kinds:
                problems.append(f"unknown id {box_id} in {name}")
            elif kinds[box_id] != kind:
                problems.append(f"{kinds[box_id]} id {box_id} in {name}")
    problems += [f"id {i} answered {n} times" for i, n in counts.items() if n > 1]
    return problems


def check_ids_per_item(
    answer: dict, boxes: Sequence[NumberedBox]
) -> tuple[dict, Counter[str]]:
    """A schema-valid answer without its entries whose ids are bad, and the drops (C47).

    Each bad entry counts under the first cause that applies:
    1. `unknown_id`: its id isn't a box's.
    2. `duplicate_id`: its id is a box's, but entries across vehicles, wheels and
       people name it more than once, so every one of them goes (C77).
    3. `wrong_list`: it sits in another list than its box's kind.

    The answer comes back as a copy, with its other keys unchanged; `answer` itself
    is never changed. The probe keeps check_ids, which only lists the problems.
    """
    kinds = {box.id: box.kind for box in boxes}
    counts: Counter[int] = Counter(
        item["id"] for name in _LISTS.values() for item in answer[name]
    )
    checked = dict(answer)
    drops: Counter[str] = Counter()
    for kind, name in _LISTS.items():
        kept = []
        for item in answer[name]:
            box_id = item["id"]
            if box_id not in kinds:
                drops["unknown_id"] += 1
            elif counts[box_id] > 1:
                drops["duplicate_id"] += 1
            elif kinds[box_id] != kind:
                drops["wrong_list"] += 1
            else:
                kept.append(item)
        checked[name] = kept
    return checked, drops


def _label_area(
    box: tuple[int, int, int, int],
    size: tuple[int, int],
    faces: list[tuple[int, int, int, int]],
    labels: list[tuple[int, int, int, int]],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    """Where a label of `size` goes, by the order draw_numbered_boxes describes."""
    x0, y0, x1, y1 = box
    w, h = size
    places = []
    for x, y in ((x0, y0 - h), (x1 - w, y0 - h), (x0, y1), (x1 - w, y1)):
        x, y = min(max(x, 0), width - w), min(max(y, 0), height - h)
        places.append((x, y, x + w, y + h))
    for avoid in (faces + labels, faces):
        for place in places:
            if not any(_overlaps(place, other) for other in avoid):
                return place
    return places[0]


def _overlaps(a: tuple[int, ...], b: tuple[int, ...]) -> bool:
    """Whether two half-open (x0, y0, x1, y1) boxes share a pixel."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
