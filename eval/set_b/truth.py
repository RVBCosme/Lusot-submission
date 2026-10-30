"""G3's truth for Set B: each wheel's scale from its dry mask and its tire code, the
waterline drawn for a depth, and the true depth read back from the row drawn (C212).

The scale is the whole wheel mask's height over the code's overall diameter, never the
rim's (G3). Depth is measured up from the ground row, one past the wheel mask's last
row, as SAM's half-open boxes have it. The truth comes from the row actually drawn, so
a line rounded to whole rows still has an exact truth.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class WheelGeom:
    """One wheel in one image's pixels: its half-open box (x0, y0, x1, y1); top_row, the
    mask's first row, and ground_row, one past its last; px_per_in, (ground_row -
    top_row) over the tire's diameter; and cx, the box's centre column,
    (x0 + x1 - 1) // 2."""

    x0: int
    y0: int
    x1: int
    y1: int
    top_row: int
    ground_row: int
    px_per_in: float
    cx: int


def wheel_geom(mask: np.ndarray, diameter: float) -> WheelGeom:
    """The geometry of a wheel's dry mask, whose tire is diameter inches across."""
    rows = np.flatnonzero(mask.any(axis=1))
    columns = np.flatnonzero(mask.any(axis=0))
    x0, x1 = int(columns[0]), int(columns[-1]) + 1
    top_row, ground_row = int(rows[0]), int(rows[-1]) + 1
    px_per_in = (ground_row - top_row) / diameter
    return WheelGeom(
        x0, top_row, x1, ground_row, top_row, ground_row, px_per_in, (x0 + x1 - 1) // 2
    )


def rim_edge_ratio(
    rim_mask: np.ndarray | None, px_per_in: float, rim_in: int
) -> float | None:
    """The linked rim mask's row extent, from its first row to one past its last, in
    inches at the wheel's scale, over the code's rim size. None without a rim: the
    generator writes it as a blank rim_edge_ratio and counts it in
    wheels_without_rim."""
    if rim_mask is None:
        return None
    rows = np.flatnonzero(rim_mask.any(axis=1))
    return (int(rows[-1]) + 1 - int(rows[0])) / px_per_in / rim_in


def line_rows(wheels: Sequence[WheelGeom], depth_in: float, width: int) -> np.ndarray:
    """The waterline's row in each of the image's width columns, as int64.

    Each wheel gives a point, (cx, ground_row - depth_in × px_per_in). One wheel gives a
    level line. Two give the straight line through both points, taken left to right so
    the order they come in doesn't matter; they need two centre columns. Each column's
    row is rounded half up, as floor(row + 0.5), never half to even, and water fills
    the column from that row down.

    The rows aren't clipped: a row above the image comes back negative, and one below
    it past the last row. The crop code clips them.
    """
    points = sorted(
        (wheel.cx, wheel.ground_row - depth_in * wheel.px_per_in) for wheel in wheels
    )
    if len(points) == 1:
        line = np.full(width, points[0][1])
    else:
        (xa, ya), (xb, yb) = points
        slope = (yb - ya) / (xb - xa)  # ZeroDivisionError for two in one column
        line = ya + slope * (np.arange(width) - xa)
    return np.floor(line + 0.5).astype(np.int64)


def wheel_truth(geom: WheelGeom, rows: np.ndarray) -> tuple[int, int, int, float]:
    """One wheel's truth from the rows drawn: waterline_left_row (rows[x0]),
    waterline_right_row (rows[x1 - 1]), waterline_row (rows[cx]) and true_depth_in,
    (ground_row - waterline_row) / px_per_in rounded to 4 decimals."""
    waterline_row = int(rows[geom.cx])
    true_depth_in = round((geom.ground_row - waterline_row) / geom.px_per_in, 4)
    return int(rows[geom.x0]), int(rows[geom.x1 - 1]), waterline_row, true_depth_in
