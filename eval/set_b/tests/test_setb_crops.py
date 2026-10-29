"""Tests for Set B's crops (C211): the depth bands, the seeded plans, the shrunk crops'
wheel heights and their own rows, and crops that come out the same, byte for byte, for
the same photo name.

crops loads cv2 itself, so cv2 is imported here at the top, unlike synth's helpers.
"""

import hashlib
import random

import crops
import cv2
import numpy as np
import pytest
import synth
import table
import tires
import truth

SHAPE = (360, 640)  # (height, width), numpy's order
# 175/65R14, whose diameter Task 14 pins at 22.9567 in.
DIAMETER = tires.diameter_in(tires.parse_tire_code("175/65R14"))
BAND_NAMES = [name for name, _, _ in crops.BANDS]


def photo(seed: int, shape: tuple[int, int] = SHAPE) -> np.ndarray:
    """A decoded synthetic JPEG, as the generator decodes blurred.jpg."""
    data = np.frombuffer(synth.jpeg(seed, shape), np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def wheel_masks(
    half_h: int = 50, shape: tuple[int, int] = SHAPE, ground: int = 300
) -> list[np.ndarray]:
    """Two wheels whose lowest rows are ground and ground - 6: the near one on the left,
    2 * half_h + 1 rows tall, and a far one on the right, 12 rows shorter."""
    near = synth.ellipse_mask(shape, (ground - half_h, 150), half_h, half_h - 5)
    far_h = half_h - 6
    far = synth.ellipse_mask(shape, (ground - 6 - far_h, 470), far_h, far_h - 4)
    return [near, far]


def shrunk_size(scale: float, shape: tuple[int, int]) -> tuple[int, int]:
    """Addition 5's dsize, (width, height), for a scale."""
    return (max(1, round(shape[1] * scale)), max(1, round(shape[0] * scale)))


def smaller_height(
    image: np.ndarray,
    masks: list[np.ndarray],
    plan: crops.CropPlan,
    rng: np.random.Generator,
) -> int | None:
    """The smaller wheel's height on the crop's own WheelGeom, or None when make_crop
    refuses the crop with ShrinkOutOfRange."""
    try:
        crop = crops.make_crop(image, masks, DIAMETER, plan, rng)
    except crops.ShrinkOutOfRange:
        return None
    return min(geom.ground_row - geom.top_row for geom, _ in crop.wheels)


def test_photo_rngs_are_seeded_from_the_name():
    """Addition 1: both generators take the SHA-256 of "<GENERATOR_SEED>:<file>" as a
    big-endian integer."""
    assert crops.GENERATOR_SEED == 20261029
    seed = int.from_bytes(hashlib.sha256(b"20261029:B01-1.jpg").digest(), "big")
    rng, np_rng = crops.photo_rngs("B01-1.jpg")
    assert isinstance(rng, random.Random)
    assert isinstance(np_rng, np.random.Generator)
    assert rng.random() == random.Random(seed).random()
    assert np_rng.random() == np.random.default_rng(seed).random()


def test_band_limits():
    """Addition 8: 175/65R14 gives half_tire a top of 10.9783 (22.9567 / 2 - 0.5), and
    diameter 20.0 none, since 9.5 isn't above 10; nor is 10.0, at 21.0. The other bands
    keep their limits."""
    assert crops.BANDS == (
        ("below_gutter", 1.0, 5.0),
        ("gutter", 5.0, 8.0),
        ("half_knee", 8.0, 10.0),
        ("half_tire", 10.0, 13.0),
    )
    assert round(DIAMETER, 4) == 22.9567
    assert crops.band_limits("half_tire", DIAMETER) == (10.0, DIAMETER / 2 - 0.5)
    assert round(DIAMETER / 2 - 0.5, 4) == 10.9783
    assert crops.band_limits("half_tire", 30.0) == (10.0, 13.0)  # min(13, 14.5)
    assert crops.band_limits("half_tire", 21.0) is None
    assert crops.band_limits("half_tire", 20.0) is None
    for name, low, high in crops.BANDS[:3]:
        assert crops.band_limits(name, 20.0) == (low, high)


def test_plan_crops():
    """Four plans, B01-1-1 to B01-1-4, one per band in a seeded order. Each depth lies
    within its band, exactly two shrink, to targets of 52.5 to 79.5 px (S-R27), and the
    same seed gives the same plans."""
    plans = crops.plan_crops("B01", 1, DIAMETER, random.Random(7))
    assert [plan.crop_id for plan in plans] == [f"B01-1-{n}" for n in range(1, 5)]
    assert all(table.is_id(plan.crop_id) for plan in plans)
    assert sorted(plan.band for plan in plans) == sorted(BAND_NAMES)
    for plan in plans:
        low, high = crops.band_limits(plan.band, DIAMETER)
        assert low <= plan.depth_in <= high
        if plan.shrink:
            assert 52.5 <= plan.target_px <= 79.5
        else:
            assert plan.target_px is None
    assert sum(plan.shrink for plan in plans) == 2
    assert crops.plan_crops("B01", 1, DIAMETER, random.Random(7)) == plans
    orders = {
        tuple(plan.band for plan in crops.plan_crops("B01", 1, DIAMETER, rng))
        for rng in map(random.Random, range(20))
    }
    assert len(orders) > 1  # the order is drawn, not fixed


@pytest.mark.parametrize(("diameter", "count"), [(DIAMETER, 4), (20.0, 3)])
def test_plan_crops_draw_order(diameter, count):
    """Addition 2: the draws come in a fixed order: the kept bands shuffled, the depths
    in crop order, the shrunk crops sampled, then their targets in crop order. At
    diameter 20.0 half_tire is left out, so 3 crops are numbered 1 to 3, and two still
    shrink."""
    plans = crops.plan_crops("B01", 2, diameter, random.Random(11))
    check = random.Random(11)
    kept = [
        name for name in BAND_NAMES if crops.band_limits(name, diameter) is not None
    ]
    check.shuffle(kept)
    depths = [check.uniform(*crops.band_limits(name, diameter)) for name in kept]
    shrunk = check.sample(range(len(kept)), min(2, len(kept)))
    targets = [
        check.uniform(52.5, 79.5) if n in shrunk else None for n in range(len(kept))
    ]
    assert len(plans) == count
    assert plans == [
        crops.CropPlan(f"B01-2-{n + 1}", name, depth, target is not None, target)
        for n, (name, depth, target) in enumerate(
            zip(kept, depths, targets, strict=True)
        )
    ]
    assert sum(plan.shrink for plan in plans) == 2


def test_small_crop_wheel_height():
    """Addition 5: over 200 photo names and 50 wheel sizes, every shrunk crop's smaller
    wheel, measured on the crop's own WheelGeom, is 50 to 80 px tall, so C56's 40 px
    holds, and make_crop refuses none of them."""
    image = photo(1, (480, 800))
    outside, checked = [], 0
    for k in range(200):
        car_id, photo_no = f"B{2 * (k // 4) + 1:02d}", k % 4 + 1
        name = f"{car_id}-{photo_no}.jpg"
        masks = wheel_masks(50 + k % 50, (480, 800), ground=420)
        rng, np_rng = crops.photo_rngs(name)
        for plan in crops.plan_crops(car_id, photo_no, DIAMETER, rng):
            if not plan.shrink:
                continue
            height = smaller_height(image, masks, plan, np_rng)
            checked += 1
            if height is None or not 50 <= height <= 80:
                outside.append((name, plan.crop_id, round(plan.target_px, 4), height))
    assert checked == 400
    assert outside == []


def test_shrink_margin_holds_at_both_ends():
    """S-R27: on the test's round wheels, of 50 sizes, every target within a pixel of
    either end of the drawn range, 52.5 to 53.5 and 78.5 to 79.5 px in steps of 0.05,
    gives a smaller wheel 50 to 80 px tall, and make_crop refuses none. A target of 50.5
    could give 49 px: INTER_NEAREST samples columns too, and can miss a round wheel's
    one-pixel top and bottom rows."""
    image = photo(1, (480, 800))
    hundredths = [*range(5250, 5351, 5), *range(7850, 7951, 5)]
    targets = [n / 100 for n in hundredths]  # 21 at each end
    outside = []
    for half_h in range(50, 100):
        masks = wheel_masks(half_h, (480, 800), ground=420)
        for target in targets:
            plan = crops.CropPlan("B01-1-1", "gutter", 6.0, True, target)
            height = smaller_height(image, masks, plan, np.random.default_rng(0))
            if height is None or not 50 <= height <= 80:
                outside.append((half_h, target, height))
    assert outside == []


def test_make_crop_refuses_an_out_of_range_shrink():
    """S-R27: a shrunk crop whose smaller wheel lands outside 50 to 80 px raises
    ShrinkOutOfRange, a ValueError whose fixed text names no id or path. On the test's
    wheel_masks(54), whose far wheel is 97 px tall, a target of 50.5 gives 49 px, since
    the column sampling misses its one-pixel top and bottom rows, and one of 85.0 gives
    about 85. A wheel already under its target isn't shrunk (scale 1), so it never
    raises, even under 50 px."""
    image = photo(1, (480, 800))
    masks = wheel_masks(54, (480, 800), ground=420)
    for target in (50.5, 85.0):
        plan = crops.CropPlan("B01-1-1", "gutter", 6.0, True, target)
        with pytest.raises(crops.ShrinkOutOfRange) as refused:
            crops.make_crop(image, masks, DIAMETER, plan, np.random.default_rng(0))
        assert isinstance(refused.value, ValueError)
        assert str(refused.value) == "a shrunk wheel is outside 50 to 80 px"
    small = wheel_masks(28, (480, 800), ground=420)  # the far wheel is 45 px tall
    plan = crops.CropPlan("B01-1-2", "gutter", 6.0, True, 60.0)
    crop = crops.make_crop(image, small, DIAMETER, plan, np.random.default_rng(0))
    assert crop.scale == 1.0
    assert min(geom.ground_row - geom.top_row for geom, _ in crop.wheels) == 45


def test_rows_are_the_crops_own():
    """A shrunk crop's wheels, scale and waterline rows are the shrunk image's. Water
    starts at waterline_row in column cx, with the shrunk photo's pixel above it."""
    image, masks = photo(1), wheel_masks()
    unshrunk = [truth.wheel_geom(mask, DIAMETER) for mask in masks]
    smaller = min(geom.ground_row - geom.top_row for geom in unshrunk)
    assert smaller == 89
    plan = crops.CropPlan("B01-1-2", "gutter", 6.0, True, 60.0)
    crop = crops.make_crop(image, masks, DIAMETER, plan, np.random.default_rng(3))
    scale = 60.0 / smaller
    dsize = shrunk_size(scale, SHAPE)
    shrunk = cv2.resize(image, dsize, interpolation=cv2.INTER_AREA)
    geoms = [
        truth.wheel_geom(
            cv2.resize(
                mask.astype(np.uint8), dsize, interpolation=cv2.INTER_NEAREST
            ).astype(bool),
            DIAMETER,
        )
        for mask in masks
    ]
    assert crop.plan == plan and crop.scale == scale
    assert crop.image.shape == shrunk.shape and crop.water.shape == shrunk.shape[:2]
    assert [geom for geom, _ in crop.wheels] == geoms
    for geom, full in zip(geoms, unshrunk, strict=True):
        assert geom.ground_row < full.ground_row
        assert geom.px_per_in == pytest.approx(full.px_per_in * scale, abs=2 / DIAMETER)
    rows = truth.line_rows(geoms, 6.0, dsize[0])
    assert np.array_equal(crop.water, np.arange(dsize[1])[:, None] >= rows)
    assert np.array_equal(crop.image[~crop.water], shrunk[~crop.water])
    for geom, found in crop.wheels:
        assert found == truth.wheel_truth(geom, rows)
        row, depth_in = found[2], found[3]
        assert crop.water[row, geom.cx] and not crop.water[row - 1, geom.cx]
        assert np.array_equal(crop.image[:row, geom.cx], shrunk[:row, geom.cx])
        assert abs(depth_in - 6.0) <= 1 / geom.px_per_in


def test_crops_at_full_size_keep_the_photos_pixels():
    """A crop that doesn't shrink keeps the photo's size and wheels, and so does a
    shrunk one whose target is over the smaller wheel's height: the scale is at most
    1."""
    image, masks = photo(1), wheel_masks()
    unshrunk = [truth.wheel_geom(mask, DIAMETER) for mask in masks]
    for plan in (
        crops.CropPlan("B01-1-1", "half_knee", 9.0, False, None),
        crops.CropPlan("B01-1-3", "half_knee", 9.0, True, 95.0),  # over 89 px
    ):
        crop = crops.make_crop(image, masks, DIAMETER, plan, np.random.default_rng(3))
        assert crop.scale == 1.0
        assert crop.image.shape == image.shape
        assert [geom for geom, _ in crop.wheels] == unshrunk
        assert np.array_equal(crop.image[~crop.water], image[~crop.water])


def generated(name: str, image: np.ndarray, masks: list[np.ndarray]) -> list:
    """One photo's crops as the generator makes them: its plans, each crop made in
    plan order with the photo's one numpy generator, then JPEG-encoded at quality 95
    (addition 6). Each crop gives its plan, its JPEG's bytes, its water mask's shape and
    bytes, and its wheels."""
    car_id, photo_no = name.removesuffix(".jpg").split("-")
    rng, np_rng = crops.photo_rngs(name)
    found = []
    for plan in crops.plan_crops(car_id, int(photo_no), DIAMETER, rng):
        crop = crops.make_crop(image, masks, DIAMETER, plan, np_rng)
        ok, data = cv2.imencode(".jpg", crop.image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        assert ok
        water = crop.water
        found.append((plan, data.tobytes(), water.shape, water.tobytes(), crop.wheels))
    return found


def test_generator_is_reproducible():
    """The same photo name gives the same crops, byte for byte after JPEG encoding,
    and the same water masks, whatever the global random states hold. Another name
    gives other crops."""
    image, masks = photo(1), wheel_masks()
    random.seed(1)
    np.random.seed(1)
    first = generated("B01-1.jpg", image, masks)
    random.seed(2)
    np.random.seed(2)
    again = generated("B01-1.jpg", image, masks)
    assert len(first) == 4 and sum(crop[0].shrink for crop in first) == 2
    assert again == first
    other = generated("B03-1.jpg", image, masks)
    assert [crop[1] for crop in other] != [crop[1] for crop in first]
