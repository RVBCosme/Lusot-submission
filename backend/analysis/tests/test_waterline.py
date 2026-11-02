"""Tests for step 3: the water edge, the touch check, the cut and raggedness.

Spec §4 step 3 (C301 to C303). Every test passes START, never the live TUNING, so
tuning T, the touch share or the IQR share in Task 17 can't break it. Row and column
ranges are inclusive, as the spec writes them.
"""

import numpy as np
import pytest
from fakes import SIZE, instance, wheel_scene

from lusot_analysis.meta_client import SamResult
from lusot_analysis.pipeline.waterline import (
    Waterline,
    cut_at_waterline,
    find_waterline,
    lower_half_share,
    water_mask,
)
from lusot_analysis.tuning import START

WIDTH, HEIGHT = SIZE


def block(rows: tuple[int, int], cols: tuple[int, int]) -> np.ndarray:
    """A mask of SIZE, True on `rows` and `cols`, both inclusive."""
    mask = np.zeros((HEIGHT, WIDTH), bool)
    mask[rows[0] : rows[1] + 1, cols[0] : cols[1] + 1] = True
    return mask


def below(row: int) -> np.ndarray:
    """Water on every row from `row` down, across the whole image."""
    return block((row, HEIGHT - 1), (0, WIDTH - 1))


BODY = block((200, 239), (300, 359))  # 40 rows by 60 columns
LEGS = block((200, 299), (300, 319))


def test_seam_within_tolerance_touches():
    # C301, D3's seam. The wheel's lowest row is 249, so a seam of 4 leaves the
    # water 5 px below it: T itself.
    for seam in (0, 3, 4):
        wheel, _, water = wheel_scene(y_true=250, seam=seam)
        line = find_waterline(wheel, water, START)
        assert (line.y_w, line.cause) == (250.0 + seam, None)
    wheel, _, water = wheel_scene(y_true=250, seam=5)
    line = find_waterline(wheel, water, START)
    assert (line.cause, line.touch_share, line.y_w) == ("no_water_contact", 0.0, None)


def test_reflection_in_the_wheel_mask_is_cut():
    # W4, D3: SAM's wheel holds its reflection, and the water holds it too.
    wheel, _, water = wheel_scene(y_true=250, reflection="overlap")
    line = find_waterline(wheel, water, START)
    assert line.cause is None
    assert abs(line.y_w - 250) <= 2  # D3's bound
    assert line.y_w == 250.0
    assert line.box_height == 134  # the wheel and its reflection
    plain, _, _ = wheel_scene(y_true=250)
    assert np.array_equal(cut_at_waterline(wheel, line.y_w), plain)
    assert wheel[250:].any()  # the cut is a copy


@pytest.mark.parametrize(
    ("y_true", "y_w", "iqr_px", "box_height"),
    [
        pytest.param(240, 290.0, 15.0, 114, id="hub"),  # 13.2%
        pytest.param(250, 309.0, 16.5, 134, id="250"),  # 12.3%
        pytest.param(230, 271.0, 13.0, 94, id="230"),  # 13.8%
    ],
)
def test_reflection_hole_edge_is_ragged(y_true, y_w, iqr_px, box_height):
    # Review Focus 1 (R86): SAM's water has a hole where the reflection is, so the
    # edge follows the reflection's round bottom, and 10% of the box drops it.
    wheel, _, water = wheel_scene(y_true=y_true, reflection="hole")
    line = find_waterline(wheel, water, START)
    assert line.cause == "ragged_waterline"
    assert line.touch_share == 1.0
    assert (line.y_w, line.iqr_px, line.box_height) == (y_w, iqr_px, box_height)


def test_flat_waterlines_pass():
    # Review Focus 1 (R86): flat waterlines sit well under 10% of the box.
    wheel, _, water = wheel_scene(y_true=250)
    line = find_waterline(wheel, water, START)
    assert (line.iqr_px, line.cause) == (0.0, None)
    wheel, _, water = wheel_scene(y_true=250, reflection="overlap", ripple=1)
    line = find_waterline(wheel, water, START)
    assert (line.iqr_px, line.box_height) == (2.0, 134)  # 1.5%
    assert (line.cause, line.y_w) == (None, 250.0)


@pytest.mark.parametrize(
    ("n", "share", "cause"),
    [(15, 0.25, None), (14, 14 / 60, "no_water_contact")],
)
def test_touch_share_boundary(n, share, cause):
    # C302: the water touches the body's first n columns of 60; the rest of it
    # starts 20 rows lower.
    water = below(260)
    water[240:, 300 : 300 + n] = True
    line = find_waterline(BODY, water, START)
    assert (line.touch_share, line.cause) == (share, cause)


def test_umbrella_columns_are_not_lower_outline():
    # C302: a person under an umbrella. Only the legs' columns reach the bottom third
    # of the box; counting every column would give 20 of 100, 0.2, and drop them.
    person = LEGS | block((200, 214), (260, 359))
    water = below(296) & ~person
    line = find_waterline(person, water, START)
    assert (line.cause, line.touch_share, line.y_w) == (None, 1.0, 300.0)


def test_ragged_boundary():
    # C303, R86: water tops alternate 236 and 236 + step by column, over the body's
    # bottom rows. 10% of the 40-row box is 4.0, and only above it is ragged.
    def alternating(step: int) -> np.ndarray:
        rows = np.arange(HEIGHT)[:, None]
        return rows >= 236 + step * (np.arange(WIDTH) % 2)

    line = find_waterline(BODY, alternating(4), START)
    assert (line.iqr_px, line.cause, line.y_w) == (4.0, None, 238.0)
    assert find_waterline(BODY, alternating(5), START).cause == "ragged_waterline"


def test_far_water_above_the_object_is_ignored():
    # Plan §7 step 3: the edge is the top of the water run at the legs' feet, not
    # the water's top row anywhere in the column.
    water = below(300) | block((100, 180), (300, 319))
    line = find_waterline(LEGS, water, START)
    assert line.y_w == 300.0


def test_no_water_and_empty_masks():
    nothing = np.zeros((HEIGHT, WIDTH), bool)
    assert find_waterline(BODY, nothing, START) == Waterline(
        None, 0.0, None, 40, None, "no_water_contact"
    )
    assert find_waterline(nothing, below(240), START) == Waterline(
        None, 0.0, None, 0, None, "no_water_contact"
    )


@pytest.mark.parametrize("tall", [1, 2])
def test_thin_masks_have_no_water_contact(tall):
    # Finding 7: a mask 1 or 2 px tall has no lower-outline column.
    thin = block((200, 200 + tall - 1), (300, 359))
    line = find_waterline(thin, below(200 + tall), START)
    assert line == Waterline(None, 0.0, None, tall, None, "no_water_contact")


def test_waterline_span():
    # C328: the evidence record draws the waterline between the first and last
    # touching columns.
    water = block((240, HEIGHT - 1), (310, 349))
    line = find_waterline(BODY, water, START)
    assert (line.cause, line.touch_share, line.y_w) == (None, 40 / 60, 240.0)
    assert line.x_span == (310, 349)
    assert all(type(v) is int for v in (line.box_height, *line.x_span))


def test_water_mask_is_the_union():
    puddle = block((350, HEIGHT - 1), (200, WIDTH - 1))
    puddle[400:420, 500:520] = False  # a post standing in it
    road = instance(0, (0, 300, 320, 480))
    pool = instance(1, (200, 350, 640, 480), mask=puddle)
    assert pool.mask is puddle
    result = SamResult("floodwater", [road, pool], elapsed_s=0.5, raw="")
    water = water_mask(result, (HEIGHT, WIDTH))
    assert np.array_equal(water, road.mask | puddle)
    assert not road.mask[:, 320:].any()  # the instances' masks are untouched
    empty = water_mask(SamResult("floodwater", [], elapsed_s=0.5, raw=""), (334, 320))
    assert (empty.shape, empty.dtype) == ((334, 320), np.dtype(bool))
    assert not empty.any()


def test_lower_half_share_reads_the_rows_from_the_middle_down():
    # C93: the share of the image's lower half that SAM's water covers. With an odd
    # height, the middle row counts as lower.
    water = np.zeros((10, 4), dtype=bool)
    water[:5] = True  # the upper half never counts
    water[5:, :2] = True
    assert lower_half_share(water) == 0.5
    odd = np.zeros((11, 2), dtype=bool)
    odd[5:, 0] = True
    assert lower_half_share(odd) == 0.5
    assert lower_half_share(np.zeros((4, 4), dtype=bool)) == 0.0
