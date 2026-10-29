"""Set B's crops (C211): four per car photo, one per depth band, each with its own
drawn water and its wheels' truth.

Two of a photo's four crops are shrunk so the smaller wheel is 50 to 80 px tall, well
over C56's 40 px. Each crop's wheels and waterline are measured again in the crop's own
pixels, so its truth is its own. Every draw comes from the photo's two generators,
seeded from its file name, so the same photo gives the same crops, byte for byte.
"""

import hashlib
import random
from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np
import truth
import water

# Fixed before any Set B photo exists, so no seed is chosen for how its crops come out.
GENERATOR_SEED = 20261029
# The depth bands, as (band, lowest, highest) in inches. half_tire's top is lowered on
# a small tire (band_limits).
BANDS = (
    ("below_gutter", 1.0, 5.0),
    ("gutter", 5.0, 8.0),
    ("half_knee", 8.0, 10.0),
    ("half_tire", 10.0, 13.0),
)
_LIMITS = {band: (low, high) for band, low, high in BANDS}


def band_limits(band: str, diameter: float) -> tuple[float, float] | None:
    """The band's (lowest, highest) depth on a tire diameter inches across, as BANDS
    gives it, except that half_tire's top is the lower of 13 and half the diameter less
    0.5 in, so the water stays below the hub. None when that top isn't above 10."""
    low, high = _LIMITS[band]
    if band == "half_tire":
        high = min(high, diameter / 2 - 0.5)
    return (low, high) if high > low else None


def photo_rngs(photo_file: str) -> tuple[random.Random, np.random.Generator]:
    """The photo's two generators, both seeded from the SHA-256 of
    "<GENERATOR_SEED>:<photo_file>", read as a big-endian integer: one for the plans,
    one for the water."""
    text = f"{GENERATOR_SEED}:{photo_file}".encode()  # UTF-8
    seed = int.from_bytes(hashlib.sha256(text).digest(), "big")
    return random.Random(seed), np.random.default_rng(seed)


@dataclass(frozen=True)
class CropPlan:
    """One crop's plan: its id (<car>-<photo>-<n>), its band, the depth drawn in
    inches, and whether it shrinks, to a target height for the smaller wheel in pixels,
    or None."""

    crop_id: str
    band: str
    depth_in: float
    shrink: bool
    target_px: float | None


def plan_crops(
    car_id: str, photo_no: int, diameter: float, rng: random.Random
) -> list[CropPlan]:
    """The photo's crop plans, one per band that has limits on this tire.

    The draws come in a fixed order, so a rerun gives the same plans: the bands kept,
    in BANDS order, are shuffled, and crop numbers 1 to n follow that order; then each
    crop's depth, evenly within its band, in crop order; then which two crops shrink;
    then each shrunk crop's target, evenly from 50.5 to 79.5 px, in crop order.
    """
    kept = [
        (band, limits)
        for band, _, _ in BANDS
        if (limits := band_limits(band, diameter)) is not None
    ]
    rng.shuffle(kept)
    depths = [rng.uniform(*limits) for _, limits in kept]
    shrunk = rng.sample(range(len(kept)), min(2, len(kept)))
    # Half a pixel inside C211's 50 to 80 (S-R26): INTER_NEAREST can move a shrunk
    # wheel's height a pixel from its target, so this margin keeps it in 50 to 80.
    targets = [
        rng.uniform(50.5, 79.5) if n in shrunk else None for n in range(len(kept))
    ]
    return [
        CropPlan(
            f"{car_id}-{photo_no}-{n + 1}", band, depth, target is not None, target
        )
        for n, ((band, _), depth, target) in enumerate(
            zip(kept, depths, targets, strict=True)
        )
    ]


@dataclass
class Crop:
    """One crop: its plan, its BGR image with the water drawn, the water mask, the
    scale from the photo (1.0 when it doesn't shrink), and each wheel's geometry in the
    crop's pixels with its truth, as truth.wheel_truth gives it."""

    plan: CropPlan
    image: np.ndarray
    water: np.ndarray
    scale: float
    wheels: list[tuple[truth.WheelGeom, tuple[int, int, int, float]]]


def make_crop(
    blurred: np.ndarray,
    wheel_masks: Sequence[np.ndarray],
    diameter: float,
    plan: CropPlan,
    rng: np.random.Generator,
) -> Crop:
    """The crop a plan gives from the blurred photo and its chosen wheels' dry masks.

    A shrunk crop shrinks first, by the target over the smaller wheel's height
    (ground_row - top_row in the photo), at most 1. The image shrinks with INTER_AREA
    and each mask with INTER_NEAREST. Each wheel's geometry is then measured in the
    crop's own pixels, and the line drawn through them at the plan's depth, so the
    truth comes from the rows the crop's water actually starts at.
    """
    image, scale = blurred, 1.0
    geoms = [truth.wheel_geom(mask, diameter) for mask in wheel_masks]
    if plan.shrink:
        smaller = min(geom.ground_row - geom.top_row for geom in geoms)
        scale = min(1.0, plan.target_px / smaller)
        height, width = blurred.shape[:2]
        dsize = (max(1, round(width * scale)), max(1, round(height * scale)))
        image = cv2.resize(blurred, dsize, interpolation=cv2.INTER_AREA)
        geoms = [
            truth.wheel_geom(
                cv2.resize(
                    mask.astype(np.uint8), dsize, interpolation=cv2.INTER_NEAREST
                ).astype(bool),
                diameter,
            )
            for mask in wheel_masks
        ]
    rows = truth.line_rows(geoms, plan.depth_in, image.shape[1])
    composited, water_mask = water.composite(image, rows, rng)
    wheels = [(geom, truth.wheel_truth(geom, rows)) for geom in geoms]
    return Crop(plan, composited, water_mask, scale, wheels)
