"""Set B's wheels: SAM's masks, loaded from set_b_masks' files, and the wheels each
photo's truth uses (C212).

set_b_masks saves each phrase's instances in one npz of ids, boxes, scores and masks
(N x height x width bool). An instance's box here comes from its mask's own extent,
half-open as SAM's boxes are: x0 and y0 are its first column and row, x1 and y1 one
past its last.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# C56's smallest reference, in pixels along a wheel box's longer side.
MIN_SIDE = 40
# How many wheels a photo's line runs through, at most.
MAX_WHEELS = 2


@dataclass(frozen=True)
class Instance:
    """One SAM instance: its half-open box (x0, y0, x1, y1), from its mask's own extent;
    its mask, a bool array of the image's height x width; and SAM's score, or None."""

    box: tuple[int, int, int, int]
    mask: np.ndarray
    score: float | None


def load_instances(npz: Path) -> list[Instance]:
    """The instances in one of set_b_masks' npz files, in its order. The file is opened
    by its name.

    np.load keeps its default allow_pickle=False, so an object array raises ValueError
    instead of running a pickle. An instance whose mask is empty has no extent, so it
    is skipped. A NaN score loads as None.
    """
    with np.load(npz) as data:
        masks, scores = data["masks"], data["scores"]
    found = []
    for mask, score in zip(masks, scores, strict=True):
        rows = np.flatnonzero(mask.any(axis=1))
        if rows.size == 0:
            continue
        columns = np.flatnonzero(mask.any(axis=0))
        box = (int(columns[0]), int(rows[0]), int(columns[-1]) + 1, int(rows[-1]) + 1)
        found.append(Instance(box, mask, None if np.isnan(score) else float(score)))
    return found


def pick_wheels(
    vehicles: Sequence[Instance], wheels: Sequence[Instance], shape: tuple[int, int]
) -> list[Instance] | str:
    """The wheels a photo's truth uses, left to right, or the cause there are none
    (C212): no_vehicle when SAM found no vehicle, and no_wheel when no wheel meets every
    rule below.

    The largest vehicle is the one with the largest box area. A wheel is kept when:
    - its box's centre, ((x0 + x1 - 1) // 2, (y0 + y1 - 1) // 2), lies inside that
      vehicle's box
    - its mask touches no edge of the image, whose (height, width) is shape: no true
      pixel in row 0, row height - 1, column 0 or column width - 1. The box is the
      mask's own extent, so its sides tell.
    - its box's longer side is at least MIN_SIDE pixels
    - its box's height over width is 0.9 to 2.0, both inclusive, compared exactly in
      integers

    Of the wheels kept, the MAX_WHEELS with the most mask pixels are used. Ties, for the
    largest vehicle and among the wheels, keep the input order.
    """
    if not vehicles:
        return "no_vehicle"
    vx0, vy0, vx1, vy1 = max(vehicles, key=_area).box  # max keeps the first of equals
    height, width = shape
    kept = []
    for wheel in wheels:
        x0, y0, x1, y1 = wheel.box
        cx, cy = (x0 + x1 - 1) // 2, (y0 + y1 - 1) // 2
        box_w, box_h = x1 - x0, y1 - y0
        if (
            vx0 <= cx < vx1
            and vy0 <= cy < vy1
            and x0 > 0
            and y0 > 0
            and x1 < width
            and y1 < height
            and max(box_w, box_h) >= MIN_SIDE
            and 9 * box_w <= 10 * box_h <= 20 * box_w
        ):
            kept.append(wheel)
    if not kept:
        return "no_wheel"
    # sorted is stable, with reverse too, so equal areas keep the input order.
    largest = sorted(kept, key=lambda wheel: np.count_nonzero(wheel.mask), reverse=True)
    return sorted(largest[:MAX_WHEELS], key=lambda wheel: wheel.box[0] + wheel.box[2])


def link_rim(wheel: Instance, rims: Sequence[Instance]) -> Instance | None:
    """The rim whose mask shares the most pixels with the wheel's mask, the first of
    equals, or None when no rim shares any."""
    overlaps = [np.count_nonzero(wheel.mask & rim.mask) for rim in rims]
    if not overlaps or max(overlaps) == 0:
        return None
    return rims[overlaps.index(max(overlaps))]


def _area(instance: Instance) -> int:
    """The area of an instance's box."""
    x0, y0, x1, y1 = instance.box
    return (x1 - x0) * (y1 - y0)
