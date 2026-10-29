"""Tests for G3's truth: each wheel's scale, the drawn waterline and the true depth
(C212)."""

import numpy as np
import pytest
import synth
import tires
import truth


def test_truth_on_a_drawn_wheel():
    """V1: a wheel drawn in a 400 x 300 frame spans rows 150 to 250. With 175/65R14
    its scale is 101 / 22.9567 px/in, so a 6.0 in depth puts the line at 224.6025,
    drawn at row 225, and the truth is taken from that drawn row."""
    mask = synth.ellipse_mask((300, 400), (200, 200), 50, 45)
    geom = truth.wheel_geom(mask, tires.diameter_in(tires.parse_tire_code("175/65R14")))
    assert (geom.top_row, geom.ground_row) == (150, 251)
    assert (geom.x0, geom.y0, geom.x1, geom.y1, geom.cx) == (155, 150, 246, 251, 200)
    assert geom.px_per_in == pytest.approx(4.3996, abs=5e-5)
    assert geom.ground_row - 6.0 * geom.px_per_in == pytest.approx(224.6025, abs=5e-5)
    rows = truth.line_rows([geom], 6.0, 400)
    assert rows.shape == (400,) and (rows == 225).all()  # level for one wheel
    assert truth.wheel_truth(geom, rows) == (225, 225, 225, 5.9096)


def test_sloped_line_gives_both_wheels_one_depth():
    """Review Focus 5: two wheels that meet the ground on different rows, at different
    scales, get one straight line through both waterline points. Its rows at the two
    centres differ, and each wheel's truth lies within one pixel of the drawn depth,
    whichever wheel comes first."""
    near = truth.WheelGeom(60, 196, 141, 251, 196, 251, 4.4, 100)
    far = truth.WheelGeom(260, 203, 341, 263, 203, 263, 4.0, 300)
    for depth in (1.5, 6.0, 11.7):
        rows = truth.line_rows([near, far], depth, 400)
        assert np.array_equal(truth.line_rows([far, near], depth, 400), rows)
        assert rows[near.cx] != rows[far.cx]
        for geom in (near, far):
            left, right, row, depth_in = truth.wheel_truth(geom, rows)
            assert (left, right, row) == (
                rows[geom.x0],
                rows[geom.x1 - 1],
                rows[geom.cx],
            )
            assert left < right  # the line falls to the right
            assert abs(depth_in - depth) <= 1 / geom.px_per_in


def test_line_rows_round_half_up():
    """A line at exactly 246.5 is drawn at row 247: half up, never half to even."""
    geom = truth.WheelGeom(160, 150, 241, 251, 150, 251, 4.0, 200)
    assert 251 - 1.125 * 4.0 == 246.5
    assert (truth.line_rows([geom], 1.125, 400) == 247).all()


def test_line_rows_does_not_clip():
    """Rows above the frame or below it come back as computed; the crop code clips."""
    geom = truth.WheelGeom(160, 150, 241, 251, 150, 251, 4.0, 200)
    assert (truth.line_rows([geom], 70.0, 400) == -29).all()
    steep = truth.WheelGeom(205, 50, 216, 151, 50, 151, 4.0, 210)  # 100 rows higher
    rows = truth.line_rows([geom, steep], 1.0, 400)
    assert (rows[0], rows[-1]) == (2247, -1743)


def test_rim_edge_ratio():
    """A rim 70 px tall at 4.3996 px/in on a 14 in rim gives 1.1365; no rim, None."""
    rim = np.zeros((300, 400), bool)
    rim[165:235, 170:230] = True
    assert truth.rim_edge_ratio(rim, 4.3996, 14) == pytest.approx(1.1365, abs=5e-5)
    assert truth.rim_edge_ratio(None, 4.3996, 14) is None
