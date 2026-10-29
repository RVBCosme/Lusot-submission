"""Steps 2, 4, 5 and 6's geometry: rim linking, the rim fit, its checks and G4.

Spec §4 (C300, C304 to C307). A rim joins the one wheel whose box holds its centre.
An ellipse fitted to the rim's outline above the water gives the scale, and the tire
codes of the vehicle's type turn it into depths in inches: an envelope over the codes,
whose deepest end sets the level. Code does all the measuring, and Muse Spark never
outputs inches (C307, C308). A wheel's landmark and geometry readings then give one
kept reading (G4).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

import cv2
import numpy as np

from lusot_analysis.meta_client import SamInstance
from lusot_analysis.pipeline.segment import link_wheels
from lusot_analysis.pipeline.waterline import Waterline, cut_at_waterline
from lusot_analysis.rules import (
    Reading,
    TireCode,
    disagree,
    level_for_inches,
    level_index,
)
from lusot_analysis.tuning import Tuning

# Spec values, not tuned (C305; plan §8). Check 9's factors are Tuning.rim_size_low
# and rim_size_high (finding 1).
MIN_FIT_POINTS = 5  # cv2.fitEllipse needs 5
MIN_AXIS_RATIO = 0.5  # minor over major

# Why a wheel gets no geometry reading, in the order the checks run (C305, C306).
GEOMETRY_CAUSES: tuple[str, ...] = (
    "waterline_not_visible",  # 1: Muse Spark answered not_visible (C318)
    "no_tire_codes",  # 2: the type has none (C304)
    "rim_missing",  # 3: no linked rim (C300)
    "rim_several",  # 3: two or more
    "waterline_dropped",  # step 3 dropped the wheel's waterline (C317)
    "not_daylight",  # 4
    "rim_score_low",  # 5
    "rim_fit_points",  # 6: under 5 points above the water, or no fit
    "rim_fit_off_wheel",  # 6: the fit's centre outside the wheel's box
    "rim_axis_ratio",  # 7
    "water_above_hub",  # 8
    "rim_size",  # 9
    "depth_not_positive",  # C306
)


def rim_size_bounds(
    codes: Sequence[TireCode], axis_ratio: float, tuning: Tuning
) -> tuple[float, float]:
    """Check 9's bounds on a rim's size, its width over the wheel box's (R88, R91).

    Each code gives rim × c ÷ (D × c + W × s), where c is the fit's axis ratio,
    s = √(1 − c²), D the tire's diameter and W its section width, all in inches.
    Seen at an angle, the box also takes in the tread, W × s. The bounds are
    `rim_size_low` × the smallest ratio and `rim_size_high` × the largest.
    """
    c = axis_ratio
    s = math.sqrt(1 - c * c)
    ratios = [
        code.rim_in * c / (2 * code.radius_in * c + code.width_mm / 25.4 * s)
        for code in codes
    ]
    return tuning.rim_size_low * min(ratios), tuning.rim_size_high * max(ratios)


def link_rims(
    wheels: Sequence[SamInstance], rims: Sequence[SamInstance]
) -> list[tuple[SamInstance, ...]]:
    """For each wheel, the rims whose box's centre its box holds, in SAM's order.

    C55's rule, as link_wheels applies it to wheels and vehicles: a box holds a point
    on its edge, and a rim held by no wheel box, or by several, joins none (C300). A
    wheel with two rims gets no geometry; wheel_geometry gives it `rim_several`.
    """
    links = link_wheels(wheels, rims)
    return [
        tuple(rim for rim, link in zip(rims, links, strict=True) if link == index)
        for index in range(len(wheels))
    ]


@dataclass(frozen=True)
class RimFit:
    """The ellipse fitted to a rim's outline above the water (spec §4 step 5).

    - `centre_x`, `centre_y`: the fit's centre, in pixels.
    - `r`: half the longer axis.
    - `axis_ratio`: the shorter axis over the longer.
    - `width_x`: the fit's full extent along x (R89).
    - `axes`, `angle_deg`: cv2.fitEllipse's own full axes, in its order, and its
      angle in degrees, kept so the evidence record can draw the fit (C328).
    - `points`: how many contour points it was fitted to.
    """

    centre_x: float
    centre_y: float
    r: float
    axis_ratio: float
    width_x: float
    axes: tuple[float, float]
    angle_deg: float
    points: int


def rim_points(rim_mask: np.ndarray, y_w: float, tolerance_px: float) -> np.ndarray:
    """The rim's outer contour points above the water, as (N, 2) int32 (x, y).

    The mask is cut at the waterline first (rows ≥ y_w), and the points of every outer
    contour are kept where y < y_w − `tolerance_px`, so the straight edge the cut
    leaves isn't fitted (spec §4 step 5).
    """
    cut = cut_at_waterline(rim_mask, y_w).astype(np.uint8)
    contours, _ = cv2.findContours(cut, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return np.empty((0, 2), np.int32)
    points = np.concatenate(contours).reshape(-1, 2)
    return points[points[:, 1] < y_w - tolerance_px]


def fit_rim(points: np.ndarray) -> RimFit | None:
    """The ellipse cv2.fitEllipse fits to `points`, or None.

    It is None with fewer than 5 points, which fitEllipse refuses, or when the centre
    or an axis isn't finite or an axis isn't positive. fitEllipse gives its full axes
    (w, h), with w along its angle θ and h across it, so the extent along x is
    √((w cos θ)² + (h sin θ)²).
    """
    if len(points) < MIN_FIT_POINTS:
        return None
    (cx, cy), (w, h), angle = cv2.fitEllipse(points)
    if not all(math.isfinite(v) for v in (cx, cy, w, h)) or min(w, h) <= 0:
        return None
    theta = math.radians(angle)
    return RimFit(
        centre_x=float(cx),
        centre_y=float(cy),
        r=max(w, h) / 2,
        axis_ratio=min(w, h) / max(w, h),
        width_x=math.hypot(w * math.cos(theta), h * math.sin(theta)),
        axes=(float(w), float(h)),
        angle_deg=float(angle),
        points=len(points),
    )


def check_fit(
    fit: RimFit,
    *,
    wheel_box: tuple[float, float, float, float],
    y_w: float,
    codes: Sequence[TireCode],
    tuning: Tuning,
) -> str | None:
    """The first of checks 6 to 9 the fit fails, or None (C305).

    In order: `rim_fit_off_wheel` when its centre lies outside the wheel's box (edges
    included); `rim_axis_ratio` under 0.5; `water_above_hub` when y_w lies above its
    centre row; `rim_size` when its width over the box's lies outside
    rim_size_bounds, bounds included (R89, R91).
    """
    x0, y0, x1, y1 = wheel_box
    if not (x0 <= fit.centre_x <= x1 and y0 <= fit.centre_y <= y1):
        return "rim_fit_off_wheel"
    if fit.axis_ratio < MIN_AXIS_RATIO:
        return "rim_axis_ratio"
    if y_w < fit.centre_y:  # rows count down, so the water is above the hub
        return "water_above_hub"
    low, high = rim_size_bounds(codes, fit.axis_ratio, tuning)
    if not low <= fit.width_x / (x1 - x0) <= high:
        return "rim_size"
    return None


def depth_inches(
    code: TireCode, *, centre_y: float, r: float, y_w: float, k: float
) -> float:
    """The water's depth at the wheel in inches, for one tire code (spec §4 step 5).

    s = r ÷ (k × rim ÷ 2) is the scale in pixels per inch, R the tire's radius in
    inches, and the depth (c + R × s − y_w) ÷ s, with c the fit's centre row.
    """
    s = r / (k * code.rim_in / 2)
    return (centre_y + code.radius_in * s - y_w) / s


@dataclass(frozen=True)
class GeometryReading:
    """A wheel's geometry reading: the envelope of depths over its type's codes.

    The level is the level rule applied to the deepest, so it rounds deeper. It is
    exact, never a floor. measure_rim sets `fit`, so Set B takes its point estimate
    from the same fit.
    """

    depth_in_min: float
    depth_in_max: float
    level: str
    fit: RimFit | None = None


def geometry_reading(depths: Sequence[float]) -> GeometryReading | str:
    """The envelope over `depths`, or `depth_not_positive` when any is 0 or less.

    Such a depth can only come from a bad fit (C306).
    """
    if any(depth <= 0 for depth in depths):
        return "depth_not_positive"
    return GeometryReading(min(depths), max(depths), level_for_inches(max(depths)))


def measure_rim(
    rim: SamInstance,
    *,
    y_w: float,
    wheel_box: tuple[float, float, float, float],
    brightness: float,
    codes: Sequence[TireCode],
    tuning: Tuning,
) -> GeometryReading | str:
    """The rim's geometry reading, or the first of checks 4 to 9 and C306 it fails.

    Check 4 is the photo's brightness against the daylight cutoff, and check 5 the
    rim's SAM score, where a missing score fails. The fit runs on the rim's points
    above y_w − T, and no fit is `rim_fit_points` (check 6). Then check_fit, and the
    depths with k = `tuning.rim_edge_k` (G3).
    """
    if brightness < tuning.daylight_brightness_min:
        return "not_daylight"
    if rim.score is None or rim.score < tuning.rim_score_min:
        return "rim_score_low"
    fit = fit_rim(rim_points(rim.mask, y_w, tuning.touch_tolerance_px))
    if fit is None:
        return "rim_fit_points"
    cause = check_fit(fit, wheel_box=wheel_box, y_w=y_w, codes=codes, tuning=tuning)
    if cause is not None:
        return cause
    depths = [
        depth_inches(code, centre_y=fit.centre_y, r=fit.r, y_w=y_w, k=tuning.rim_edge_k)
        for code in codes
    ]
    reading = geometry_reading(depths)
    if isinstance(reading, str):
        return reading
    return replace(reading, fit=fit)


def wheel_geometry(
    *,
    answer_waterline: str,
    codes: Sequence[TireCode],
    rims: Sequence[SamInstance],
    waterline: Waterline | None,
    wheel_box: tuple[float, float, float, float],
    brightness: float,
    tuning: Tuning,
) -> GeometryReading | str:
    """One wheel's geometry reading, or the first check it fails (spec §4 step 4).

    Checks 1 to 3 come first: Muse Spark's answer for the wheel (C318), the type's
    tire codes (C304) and exactly one linked rim (C300). A waterline step 3 dropped,
    or none, is `waterline_dropped` (C317). Then measure_rim at the waterline.
    """
    if answer_waterline == "not_visible":
        return "waterline_not_visible"
    if not codes:
        return "no_tire_codes"
    if not rims:
        return "rim_missing"
    if len(rims) > 1:
        return "rim_several"
    if waterline is None or waterline.cause is not None:
        return "waterline_dropped"
    return measure_rim(
        rims[0],
        y_w=waterline.y_w,
        wheel_box=wheel_box,
        brightness=brightness,
        codes=codes,
        tuning=tuning,
    )


@dataclass(frozen=True)
class KeptReading:
    """A wheel's one reading after G4, and where its level came from (C307, C320).

    `depth_in` is geometry's (min, max) when the level came from geometry, else None.
    """

    reading: Reading
    level_from: Literal["landmark", "geometry"]
    depth_in: tuple[float, float] | None


def keep_reading(
    landmark: Reading | None, geometry: GeometryReading | None
) -> KeptReading | Literal["wheel_methods_disagree"] | None:
    """G4's choice between a wheel's landmark and geometry readings (C307).

    Geometry's reading is exact. With one reading, it is kept; with none, None. With
    both, readings that fail C54's test drop the wheel as `wheel_methods_disagree`;
    otherwise the deeper is kept, and an equal level counts as geometry.
    """
    measured = None
    if geometry is not None:
        measured = KeptReading(
            Reading(geometry.level, floor=False),
            "geometry",
            (geometry.depth_in_min, geometry.depth_in_max),
        )
    if landmark is None:
        return measured
    kept = KeptReading(landmark, "landmark", None)
    if measured is None:
        return kept
    if disagree([landmark, measured.reading]):
        return "wheel_methods_disagree"
    if level_index(measured.reading.level) >= level_index(landmark.level):
        return measured
    return kept
