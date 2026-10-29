"""Step 3: the water edge under each reference, the touch check and the cut.

Spec §4 step 3 (C301 to C303). It runs on SAM's masks after Muse Spark's answer and
the gate, for every kept reference that gives a reading (C317). In each column of the
object's lower outline, the edge is the top row of the water run that touches the
object's lowest pixel there. Flood water often wraps around a person or a car and
shows above them, so the water's top row elsewhere in the column is no edge. The
median edge is the waterline, and the object's pixels at or below it are cut, so a
reflection can't make a wheel look whole (W4).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from lusot_analysis.meta_client import SamResult
from lusot_analysis.tuning import Tuning


@dataclass(frozen=True)
class Waterline:
    """Where the water meets one object, and whether the reference is dropped.

    - `y_w`: the median edge row of the touching columns, or None when none touches.
    - `touch_share`: the touching columns' share of the lower-outline columns, or 0.0
      when there are none.
    - `iqr_px`: the interquartile range of the edge rows, or None when none touches.
    - `box_height`: the object mask's height in rows, 0 for an empty mask.
    - `x_span`: the first and last touching columns, which the evidence record draws
      the waterline between (C328), or None when none touches.
    - `cause`: None, "no_water_contact" (C302) or "ragged_waterline" (C303).
    """

    y_w: float | None
    touch_share: float
    iqr_px: float | None
    box_height: int
    x_span: tuple[int, int] | None
    cause: str | None


def water_mask(result: SamResult, shape: tuple[int, int]) -> np.ndarray:
    """The union of the instances' masks, as a new (height, width) bool array.

    It is all False when SAM found no water.
    """
    water = np.zeros(shape, bool)
    for inst in result.instances:
        water |= inst.mask
    return water


def find_waterline(obj: np.ndarray, water: np.ndarray, tuning: Tuning) -> Waterline:
    """The waterline under the object mask `obj`, from the water mask `water`.

    The lower-outline columns are those whose lowest object pixel, y_low, lies in the
    bottom third of the object's box: y_low - top >= 2 x height / 3 (C302). In each,
    the edge is the top row of the first water run, top down, that comes within T px
    of y_low: it reaches into rows y_low - T to y_low + T (C301). The reference is
    dropped as no_water_contact when fewer than `touch_share_min` of the lower-outline
    columns touch, or when there are none, as in a mask 1 or 2 px tall (finding 7).
    It is dropped as ragged_waterline when the edges' interquartile range exceeds
    `ragged_iqr_share` of the box's height (C303, R86).
    """
    ys, xs = np.nonzero(obj)
    if ys.size == 0:
        return Waterline(None, 0.0, None, 0, None, "no_water_contact")
    top = int(ys.min())
    height = int(ys.max()) - top + 1
    tolerance = tuning.touch_tolerance_px  # T
    columns = np.unique(xs)
    # Each column's lowest object pixel: the first True row counted from the bottom.
    lowest = obj.shape[0] - 1 - np.argmax(obj[::-1, columns], axis=0)
    lower, edges, touching = 0, [], []
    for x, y_low in zip(columns.tolist(), lowest.tolist(), strict=True):
        if y_low - top < 2 * height / 3:  # not a lower-outline column
            continue
        lower += 1
        for start, end in _runs(water[:, x]):
            if start <= y_low + tolerance and end >= y_low - tolerance:
                edges.append(start)  # this run touches: its top is the edge
                touching.append(x)
                break
    if lower == 0:  # a mask 1 or 2 px tall (finding 7)
        return Waterline(None, 0.0, None, height, None, "no_water_contact")
    share = len(edges) / lower
    if not edges:
        return Waterline(None, share, None, height, None, "no_water_contact")
    y_w = float(np.median(edges))
    iqr = float(np.percentile(edges, 75) - np.percentile(edges, 25))
    if share < tuning.touch_share_min:
        cause = "no_water_contact"
    elif iqr > tuning.ragged_iqr_share * height:
        cause = "ragged_waterline"
    else:
        cause = None
    return Waterline(y_w, share, iqr, height, (min(touching), max(touching)), cause)


def cut_at_waterline(mask: np.ndarray, y_w: float) -> np.ndarray:
    """A copy of `mask` with every row at or below the edge (rows >= y_w) cleared."""
    cut = mask.copy()
    cut[math.ceil(y_w) :] = False
    return cut


def _runs(column: np.ndarray) -> list[tuple[int, int]]:
    """The maximal runs of True in `column`, top down, as (first, last) rows.

    Both rows are inclusive. A column with no True gives no run.
    """
    padded = np.concatenate(([False], column, [False]))
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    return list(zip(changes[0::2].tolist(), (changes[1::2] - 1).tolist(), strict=True))
