"""Numbered boxes for Muse Spark (plan §7 step 4).

Each vehicle, wheel and person SAM found gets a thin outline and a label with its id,
so Muse Spark's answer names them and code ties each answer back to its mask. A box is
never filled, so it hides no rim and no waterline; only its small label tag is.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Literal

import cv2

from lusot_analysis.face_blur import BlurredImage, FaceBox, detect_faces
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
_LINE_THICKNESS = 2  # OpenCV draws it 3 px wide, centred on the box's edge
_FONT = cv2.FONT_HERSHEY_SIMPLEX
_FACE_MARGIN = 0.25  # blur_faces' default margin, which derive blurs with


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


def draw_numbered_boxes(img: BlurredImage, boxes: list[NumberedBox]) -> BlurredImage:
    """Draw each box as a thin outline, and its id on a small tag in the same colour.

    The outline is cv2.rectangle at thickness 2, which OpenCV draws 3 px wide, centred
    on the box's edge. Its second corner is inclusive, so a half-open box is drawn to
    (x1 - 1, y1 - 1).

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
    faces = [_blur_area(face) for face in detect_faces(bgr)]
    scale = max(0.5, max(width, height) / 1600)  # digits about 11 px tall, or more
    thickness = 1 if scale < 1 else 2
    pad = thickness + 2
    for box in boxes:
        x0, y0, x1, y1 = box.box
        colour = _COLOURS[box.kind]
        cv2.rectangle(bgr, (x0, y0), (x1 - 1, y1 - 1), colour, _LINE_THICKNESS)
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


def _blur_area(face: FaceBox) -> tuple[int, int, int, int]:
    """Where derive blurs `face`: its box grown by the margin, half-open like a box."""
    dx, dy = math.ceil(face.w * _FACE_MARGIN), math.ceil(face.h * _FACE_MARGIN)
    return face.x - dx, face.y - dy, face.x + face.w + dx, face.y + face.h + dy


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
