"""Tests for the rim geometry: rim linking, the rim fit, its checks, the formula and G4.

Spec §4 steps 4 to 6 (C300, C305 to C307). Every test that takes a tuning passes
START, so Task 17's tuning can't move its check 9 bounds, daylight cutoff, rim score or
step 3 values. Only the hubcap test's last check reads the live TUNING.
"""

import math
from dataclasses import replace

import cv2
import numpy as np
import pytest
from fakes import SIZE, around, instance, wheel_scene

from lusot_analysis.meta_client import SamInstance
from lusot_analysis.pipeline.geometry import (
    GEOMETRY_CAUSES,
    MIN_AXIS_RATIO,
    MIN_FIT_POINTS,
    GeometryReading,
    KeptReading,
    RimFit,
    check_fit,
    depth_inches,
    fit_rim,
    geometry_reading,
    keep_reading,
    link_rims,
    measure_rim,
    rim_points,
    rim_size_bounds,
    wheel_geometry,
)
from lusot_analysis.pipeline.waterline import Waterline, find_waterline
from lusot_analysis.rules import (
    WHEEL_ROWS,
    Reading,
    TireCode,
    level_for_inches,
    round_out,
    tire_codes,
)
from lusot_analysis.tuning import START, TUNING

WIDTH, HEIGHT = SIZE
SEDAN = tire_codes("sedan_hatch")
VAN = tire_codes("van")
T = START.touch_tolerance_px
WHEEL_BOX = (263, 183, 378, 257)  # wheel_scene(y_true=257)'s wheel, 115 px wide
ONE = replace(START, rim_size_low=1.0, rim_size_high=1.0)  # check 9's bare ratios


def filled_ellipse(axes: tuple[int, int], angle: float = 0.0) -> np.ndarray:
    """A uint8 mask of SIZE holding a filled ellipse centred on (320, 240).

    `axes` are the semi-axes along x and y before the turn by `angle` degrees. It is
    drawn with cv2.ellipse(..., thickness=-1), as the facts were measured (R135, M3).
    """
    mask = np.zeros((HEIGHT, WIDTH), np.uint8)
    cv2.ellipse(mask, (320, 240), axes, angle, 0, 360, 1, thickness=-1)
    return mask


def outer_points(mask: np.ndarray) -> np.ndarray:
    """Every outer boundary pixel of the mask, as (N, 2) int32 (x, y) points."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return np.concatenate(contours).reshape(-1, 2)


def mask_box(mask: np.ndarray) -> tuple[float, float, float, float]:
    """The mask's box, half-open as MS1's client keeps SAM's (R61)."""
    ys, xs = np.nonzero(mask)
    return float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)


def rim_of(mask: np.ndarray, score: float | None = 0.9) -> SamInstance:
    """SAM's rim match whose mask is `mask`, with the mask's own box."""
    return instance(0, mask_box(mask), mask=mask, score=score)


def scene_rim(**scene) -> SamInstance:
    """The rim match of wheel_scene(**scene), with score 0.9."""
    _, rim, _ = wheel_scene(**scene)
    return rim_of(rim)


def test_fit_ellipse_facts_on_this_opencv():
    # Step 1: the facts the brief read in OpenCV 4.13's docs, on the locked 4.14.0.
    # w lies along the angle and h across it, so the fit's horizontal extent is
    # sqrt((w cos θ)² + (h sin θ)²).
    def width_x(fit) -> float:
        _, (w, h), angle = fit
        theta = math.radians(angle)
        return math.hypot(w * math.cos(theta), h * math.sin(theta))

    (cx, cy), (w, h), _ = cv2.fitEllipse(outer_points(filled_ellipse((35, 35))))
    assert math.hypot(cx - 320, cy - 240) <= 0.5
    assert max(w, h) / 2 == pytest.approx(35, abs=1.0)

    fit = cv2.fitEllipse(outer_points(filled_ellipse((40, 20))))
    _, (w, h), _ = fit
    assert max(w, h) / 2 == pytest.approx(40, abs=1)
    assert min(w, h) / 2 / (max(w, h) / 2) == pytest.approx(0.5, abs=0.02)
    assert width_x(fit) == pytest.approx(80, abs=1)

    turned = cv2.fitEllipse(outer_points(filled_ellipse((40, 20), angle=30)))
    assert width_x(turned) == pytest.approx(72.1, abs=1)

    four = outer_points(filled_ellipse((35, 35)))[:4]
    with pytest.raises(cv2.error):
        cv2.fitEllipse(four)


def test_spec_values_and_causes():
    assert (MIN_FIT_POINTS, MIN_AXIS_RATIO) == (5, 0.5)
    assert GEOMETRY_CAUSES == (
        "waterline_not_visible",
        "no_tire_codes",
        "rim_missing",
        "rim_several",
        "waterline_dropped",
        "not_daylight",
        "rim_score_low",
        "rim_fit_points",
        "rim_fit_off_wheel",
        "rim_axis_ratio",
        "water_above_hub",
        "rim_size",
        "depth_not_positive",
    )


def test_link_rims_by_centre():
    # C300: a rim joins the one wheel whose box holds its box's centre, edges
    # included. Wheels A and B overlap from x 180 to 200.
    wheels = [instance(0, (100, 100, 200, 200)), instance(1, (180, 100, 280, 200))]
    centres = (140, 240, 190, 400, 120)  # A, B, both, neither, A again
    rims = [instance(i, around(cx, 150, 20, 20)) for i, cx in enumerate(centres)]
    linked = link_rims(wheels, rims)
    assert all(type(held) is tuple for held in linked)
    assert [tuple(rim.id for rim in held) for held in linked] == [(0, 4), (1,)]
    assert linked[0][0] is rims[0]
    assert link_rims(wheels, []) == [(), ()]
    assert link_rims([], rims) == []


def test_fit_needs_five_points():
    # Check 6: fitEllipse needs 5 points, and fit_rim counts them first.
    def on_circle(n: int) -> np.ndarray:
        angles = np.arange(n) * 2 * np.pi / n
        circle = np.stack([320 + 30 * np.cos(angles), 240 + 30 * np.sin(angles)], 1)
        return circle.astype(np.float32)  # rounded to int, r would be 30.38 (R135)

    assert fit_rim(on_circle(4)) is None
    fit = fit_rim(on_circle(5))
    assert fit.r == pytest.approx(30, abs=0.01)
    assert fit.axes == pytest.approx((60, 60), abs=0.02)
    assert fit.points == 5


def test_degenerate_fits_are_none():
    # Five copies of one point fit axes of 0, which isn't a fit.
    assert fit_rim(np.full((5, 2), 3, np.int32)) is None
    assert fit_rim(np.empty((0, 2), np.int32)) is None


def test_rim_points_skip_the_cut_edge():
    # Spec §4 step 5: the fit runs on the outer contour above y_w - T, so the
    # straight edge the cut leaves isn't fitted.
    _, rim, _ = wheel_scene(y_true=257)
    points = rim_points(rim, 257.0, T)
    assert points.dtype == np.int32
    assert points.ndim == 2 and points.shape[1] == 2
    assert len(points) >= MIN_FIT_POINTS
    assert (points[:, 1] < 252).all()
    fit = fit_rim(points)
    assert (fit.centre_x, fit.centre_y) == pytest.approx((320.0, 239.6), abs=0.5)
    assert fit.r == pytest.approx(34.5, abs=0.5)
    assert fit.points == len(points)
    assert rim[252:257].any()  # the rim reaches the cut, and rim_points leaves it


def test_formula_hand_computed():
    # Plan Table 7's sizes, exact to 1e-4.
    wigo = TireCode.parse("175/65R14")
    assert wigo.radius_in == pytest.approx(11.4783, abs=1e-4)
    depth = depth_inches(wigo, centre_y=200, r=35, y_w=220, k=1.0)  # s = 5.0
    assert depth == pytest.approx(7.4783, abs=1e-4)
    assert round(depth, 1) == 7.5
    assert level_for_inches(depth) == "gutter"

    # At the hub, the Hiace reads knee, where Table 8's hub row says half_tire (G4).
    hiace = TireCode.parse("215/70R16C")
    depth = depth_inches(hiace, centre_y=300, r=40, y_w=300, k=1.0)
    assert depth == pytest.approx(13.9252, abs=1e-4)
    assert round(depth, 1) == 13.9
    assert level_for_inches(depth) == "knee"
    assert WHEEL_ROWS["hub"].level == "half_tire"

    vios = TireCode.parse("195/55R16")
    depth = depth_inches(vios, centre_y=100, r=42, y_w=110, k=1.05)  # s = 5.0
    assert depth == pytest.approx(10.2224, abs=1e-4)
    assert round(depth, 1) == 10.2
    assert level_for_inches(depth) == "half_tire"


def test_envelope_over_the_sedan_codes():
    depths = [depth_inches(code, centre_y=200, r=35, y_w=215, k=1.0) for code in SEDAN]
    assert depths == pytest.approx([8.4783, 8.2916, 8.6558, 8.7939], abs=1e-4)
    reading = geometry_reading(depths)
    assert (reading.depth_in_min, reading.depth_in_max) == pytest.approx(
        (8.2916, 8.7939), abs=1e-4
    )
    assert (reading.level, reading.fit) == ("half_knee", None)
    assert round_out(reading.depth_in_min, reading.depth_in_max) == (8.2, 8.8)


def test_depth_not_positive_boundary():
    # C306: a depth of 0 or less on any code is a failed fit.
    assert geometry_reading([0.0, 3.0]) == "depth_not_positive"
    assert geometry_reading([3.0, -0.5]) == "depth_not_positive"
    assert geometry_reading([0.01, 3.0]) == GeometryReading(0.01, 3.0, "below_gutter")


def test_rim_size_bounds_from_the_codes():
    # R88, R91: rim × c ÷ (D × c + W × s), hand-computed. With both factors at 1,
    # one code's bounds are its own ratio.
    def ratio(code: str, axis_ratio: float) -> float:
        low, high = rim_size_bounds((TireCode.parse(code),), axis_ratio, ONE)
        assert low == high
        return low

    # Side-on (s = 0), the ratio is rim ÷ D.
    side_on = {
        "175/65R14": 0.6098,  # 14 ÷ 22.9567
        "185/55R15": 0.6518,  # 15 ÷ 23.0118
        "185/60R15": 0.6318,  # 15 ÷ 23.7402
        "195/55R16": 0.6545,  # 16 ÷ 24.4449
    }
    for code, expected in side_on.items():
        assert ratio(code, 1.0) == pytest.approx(expected, abs=1e-4)
    assert rim_size_bounds(SEDAN, 1.0, START) == pytest.approx(
        (0.5184, 0.7527), abs=1e-4
    )  # 0.85 × 0.6098 and 1.15 × 0.6545

    # At axis ratio 0.6 (s = 0.8), W is 6.8898, 7.2835, 7.2835 and 7.6772 in.
    angled = {
        "175/65R14": 0.4356,  # 8.4 ÷ (13.7740 + 5.5118)
        "185/55R15": 0.4584,  # 9.0 ÷ (13.8071 + 5.8268)
        "185/60R15": 0.4484,  # 9.0 ÷ (14.2441 + 5.8268)
        "195/55R16": 0.4613,  # 9.6 ÷ (14.6669 + 6.1417)
    }
    for code, expected in angled.items():
        assert ratio(code, 0.6) == pytest.approx(expected, abs=1e-4)
    assert rim_size_bounds(SEDAN, 0.6, START) == pytest.approx(
        (0.3702, 0.5306), abs=1e-4
    )  # 0.85 × 0.4356 and 1.15 × 0.4613

    others = {
        "suv_mpv": (0.5134, 0.7555),
        "van": (0.4883, 0.6814),
        "pickup": (0.4728, 0.6783),
        "unknown": (0.4728, 0.7555),
    }
    for vehicle_type, bounds in others.items():
        assert rim_size_bounds(tire_codes(vehicle_type), 1.0, START) == pytest.approx(
            bounds, abs=1e-4
        )


BASE_FIT = RimFit(
    centre_x=320.0,
    centre_y=240.0,
    r=35.0,
    axis_ratio=0.9,
    width_x=70.0,
    axes=(70.0, 63.0),
    angle_deg=0.0,
    points=50,
)


def check(fit: RimFit, *, wheel_box=WHEEL_BOX, y_w: float = 257.0, tuning=START):
    """check_fit on the sedan codes."""
    return check_fit(fit, wheel_box=wheel_box, y_w=y_w, codes=SEDAN, tuning=tuning)


def test_check_fit_boundaries():
    # The base's rim size, 70 ÷ 115 = 0.6087, lies inside the bounds at 0.9.
    assert rim_size_bounds(SEDAN, 0.9, START) == pytest.approx(
        (0.4526, 0.6533), abs=1e-4
    )
    assert check(BASE_FIT) is None

    # Check 7. At 0.5, 48 ÷ 115 = 0.4174 lies inside 0.3411 to 0.4875 (finding 3).
    assert rim_size_bounds(SEDAN, 0.5, START) == pytest.approx(
        (0.3411, 0.4875), abs=1e-4
    )
    assert check(replace(BASE_FIT, axis_ratio=0.5, width_x=48.0)) is None
    assert check(replace(BASE_FIT, axis_ratio=0.5)) == "rim_size"  # 70.0 fails there
    assert check(replace(BASE_FIT, axis_ratio=0.4999, width_x=48.0)) == (
        "rim_axis_ratio"
    )

    # Check 8: the water at or below the hub.
    assert check(BASE_FIT, y_w=240.0) is None
    assert check(BASE_FIT, y_w=239.99) == "water_above_hub"

    # Check 6: the centre inside the wheel's box, edges included.
    assert check(replace(BASE_FIT, centre_x=263.0)) is None
    assert check(replace(BASE_FIT, centre_x=262.99)) == "rim_fit_off_wheel"
    assert check(replace(BASE_FIT, centre_x=378.0)) is None
    assert check(replace(BASE_FIT, centre_x=378.01)) == "rim_fit_off_wheel"
    assert check(replace(BASE_FIT, centre_y=182.99)) == "rim_fit_off_wheel"

    # Check 9 at axis ratio 1.0 (bounds 0.51837 and 0.75271), in a box 100 px wide,
    # so the rim size is width_x ÷ 100.
    assert rim_size_bounds(SEDAN, 1.0, START) == pytest.approx(
        (0.51837, 0.75271), abs=1e-5
    )
    box = (300, 183, 400, 257)
    side_on = replace(BASE_FIT, axis_ratio=1.0)
    for width_x, cause in [
        (51.86, None),
        (51.82, "rim_size"),
        (75.26, None),
        (75.28, "rim_size"),
    ]:
        assert check(replace(side_on, width_x=width_x), wheel_box=box) == cause
    # A rim size exactly on a bound passes (R89, R91). In a box 128 px wide the
    # division is exact.
    box = (256, 183, 384, 257)
    for bound in rim_size_bounds(SEDAN, 1.0, START):
        assert check(replace(side_on, width_x=bound * 128), wheel_box=box) is None


def test_check_fit_order():
    # Each check speaks before the ones after it. With y_w = 250, a centre at row 255
    # sits in the box but below the water's edge.
    every_fault = replace(
        BASE_FIT, centre_x=262.0, centre_y=255.0, axis_ratio=0.4, width_x=10.0
    )
    assert check(every_fault, y_w=250.0) == "rim_fit_off_wheel"
    every_fault = replace(every_fault, centre_x=320.0)
    assert check(every_fault, y_w=250.0) == "rim_axis_ratio"
    every_fault = replace(every_fault, axis_ratio=0.9)
    assert check(every_fault, y_w=250.0) == "water_above_hub"
    every_fault = replace(every_fault, centre_y=240.0)
    assert check(every_fault, y_w=250.0) == "rim_size"  # 10 ÷ 115


def test_check_9_factors_come_from_the_tuning():
    # Finding 1: a rim size of 0.50 fails START's lower bound, 0.51837, and passes
    # 0.80 × 0.60984 = 0.48787.
    fit = replace(BASE_FIT, axis_ratio=1.0, width_x=50.0)
    box = (300, 183, 400, 257)
    assert check(fit, wheel_box=box) == "rim_size"
    lower = replace(START, rim_size_low=0.80)
    assert rim_size_bounds(SEDAN, 1.0, lower)[0] == pytest.approx(0.48787, abs=1e-5)
    assert check(fit, wheel_box=box, tuning=lower) is None


def test_an_angled_rim_passes_checks_7_and_9():
    # R89, R91: a 175/65R14 wheel at 5 px per inch, seen at axis ratio 0.6. Its box
    # takes in the tread: the face is D × cos φ = 114.78 × 0.6 = 68.87 px, plus
    # W × sin φ = 34.45 × 0.8 = 27.56 px of tread on one side.
    box = (258.01, 183, 354.44, 257)
    assert box[2] - box[0] == pytest.approx(68.87 + 27.56, abs=0.01)  # 96.43 px
    rim = scene_rim(y_true=257, squash=0.6)
    fit = fit_rim(rim_points(rim.mask, 257.0, T))
    assert fit.axes == pytest.approx((40.77, 68.15), abs=0.01)
    assert fit.angle_deg == pytest.approx(0, abs=0.5)
    assert fit.axis_ratio == pytest.approx(0.598, abs=5e-4)  # check 7 passes
    assert fit.width_x == pytest.approx(40.77, abs=0.01)
    size = fit.width_x / (box[2] - box[0])
    assert size == pytest.approx(0.4228, abs=1e-4)
    bounds = rim_size_bounds(SEDAN, fit.axis_ratio, START)
    assert bounds == pytest.approx((0.3697, 0.5298), abs=1e-4)
    assert check(fit, wheel_box=box) is None  # check 9 passes

    reading = measure_rim(
        rim, y_w=257.0, wheel_box=box, brightness=128.0, codes=SEDAN, tuning=START
    )
    assert reading.depth_in_min == pytest.approx(7.676, abs=0.02)
    assert reading.depth_in_max == pytest.approx(8.137, abs=0.02)
    assert reading.fit == fit

    # Against the side-on bounds, 0.5184 to 0.7527, the same rim would fail. That is
    # why the bounds follow the viewing angle.
    assert check(replace(fit, axis_ratio=1.0), wheel_box=box) == "rim_size"


def measure(rim, *, y_w: float = 257.0, brightness: float = 128.0):
    """measure_rim on wheel_scene(y_true=257)'s wheel box and the sedan codes."""
    return measure_rim(
        rim,
        y_w=y_w,
        wheel_box=WHEEL_BOX,
        brightness=brightness,
        codes=SEDAN,
        tuning=START,
    )


def test_measure_rim_checks():
    # C305, on wheel_scene(y_true=257)'s rim, score 0.9.
    _, mask, _ = wheel_scene(y_true=257)
    rim = rim_of(mask)
    reading = measure(rim)
    assert reading.depth_in_min == pytest.approx(7.720, abs=0.02)
    assert reading.depth_in_max == pytest.approx(8.184, abs=0.02)
    assert reading.level == "half_knee"
    assert reading.fit == fit_rim(rim_points(mask, 257.0, T))
    fit = reading.fit
    depths = [
        depth_inches(code, centre_y=fit.centre_y, r=fit.r, y_w=257.0, k=1.0)
        for code in SEDAN
    ]
    assert (reading.depth_in_min, reading.depth_in_max) == (min(depths), max(depths))

    # Check 4: daylight.
    assert measure(rim, brightness=79.99) == "not_daylight"
    assert isinstance(measure(rim, brightness=80.0), GeometryReading)

    # Check 5: the rim's SAM score; a missing score fails.
    assert measure(rim_of(mask, score=0.49)) == "rim_score_low"
    assert isinstance(measure(rim_of(mask, score=0.5)), GeometryReading)
    assert measure(rim_of(mask, score=None)) == "rim_score_low"

    # Check 6: no point lies above y_w - T.
    assert measure(rim, y_w=209.0) == "rim_fit_points"


def test_measure_rim_uses_k():
    # G3: k scales the rim's nominal size, so the depths follow it.
    _, mask, _ = wheel_scene(y_true=257)
    fit = fit_rim(rim_points(mask, 257.0, T))
    k = 1.05
    reading = measure_rim(
        rim_of(mask),
        y_w=257.0,
        wheel_box=WHEEL_BOX,
        brightness=128.0,
        codes=SEDAN,
        tuning=replace(START, rim_edge_k=k),
    )
    depths = [
        depth_inches(code, centre_y=fit.centre_y, r=fit.r, y_w=257.0, k=k)
        for code in SEDAN
    ]
    assert (reading.depth_in_min, reading.depth_in_max) == (min(depths), max(depths))
    assert reading.depth_in_max != measure(rim_of(mask)).depth_in_max


def geometry(
    *,
    answer_waterline: str = "hub",
    codes=SEDAN,
    rims=(),
    waterline: Waterline | None = None,
    wheel_box=WHEEL_BOX,
):
    """wheel_geometry with brightness 128 and START."""
    return wheel_geometry(
        answer_waterline=answer_waterline,
        codes=codes,
        rims=rims,
        waterline=waterline,
        wheel_box=wheel_box,
        brightness=128.0,
        tuning=START,
    )


def test_wheel_geometry_checks_in_order():
    wheel, mask, water = wheel_scene(y_true=257)
    rim = rim_of(mask)
    line = find_waterline(wheel, water, START)
    assert (line.y_w, line.cause) == (257.0, None)

    assert geometry(answer_waterline="not_visible", codes=()) == (
        "waterline_not_visible"
    )
    assert geometry(codes=(), rims=(rim,), waterline=line) == "no_tire_codes"
    assert geometry(rims=(), waterline=line) == "rim_missing"
    assert geometry(rims=(rim, rim), waterline=line) == "rim_several"
    assert geometry(rims=(rim,), waterline=None) == "waterline_dropped"
    no_contact = Waterline(None, 0.0, None, 74, None, "no_water_contact")
    assert geometry(rims=(rim,), waterline=no_contact) == "waterline_dropped"

    # With every check passed, it measures the rim at the waterline.
    assert geometry(rims=(rim,), waterline=line) == measure(rim, y_w=line.y_w)


def geo(level: str) -> GeometryReading:
    d = {"below_gutter": 4.0, "half_knee": 9.0, "half_tire": 12.0, "knee": 15.0}[level]
    return GeometryReading(d, d, level)


def kept_landmark(row: str) -> KeptReading:
    return KeptReading(WHEEL_ROWS[row], "landmark", None)


def kept_geometry(level: str) -> KeptReading:
    d = geo(level).depth_in_max
    return KeptReading(Reading(level, floor=False), "geometry", (d, d))


@pytest.mark.parametrize(
    ("landmark", "geometry_level", "expected"),
    [
        ("hub", None, kept_landmark("hub")),
        (None, "half_knee", kept_geometry("half_knee")),
        ("rim_quarter", "half_knee", kept_geometry("half_knee")),  # equal: geometry
        ("hub", "knee", kept_geometry("knee")),
        ("rim_quarter", "half_tire", kept_geometry("half_tire")),
        ("hub", "half_knee", kept_landmark("hub")),
        ("hub", "below_gutter", "wheel_methods_disagree"),
        ("wheel_covered", "knee", kept_landmark("wheel_covered")),  # the floor
        ("wheel_covered", "half_tire", "wheel_methods_disagree"),
        (None, None, None),
    ],
)
def test_keep_reading_follows_g4(landmark, geometry_level, expected):
    # G4, C307, C320: the deeper level is kept, an equal one counts as geometry, and
    # readings more than one level apart drop the wheel.
    reading = None if landmark is None else WHEEL_ROWS[landmark]
    measured = None if geometry_level is None else geo(geometry_level)
    assert keep_reading(reading, measured) == expected


HOLES = [(240, 290.0, 15.0, 114), (250, 309.0, 16.5, 134), (230, 271.0, 13.0, 94)]


def test_reflection_hole_gets_no_geometry_reading():
    # Review Focus 1 (R86). SAM's water has a hole where the reflection is, so step 3
    # drops the wheel as ragged, and no type gets a geometry reading.
    for y_true, y_w, iqr_px, box_height in HOLES:
        wheel, mask, water = wheel_scene(y_true=y_true, reflection="hole")
        line = find_waterline(wheel, water, START)
        assert line.cause == "ragged_waterline"
        assert (line.y_w, line.iqr_px, line.box_height) == (y_w, iqr_px, box_height)
        for codes in (SEDAN, VAN):
            result = geometry(
                codes=codes,
                rims=(rim_of(mask),),
                waterline=line,
                wheel_box=mask_box(wheel),
            )
            assert result == "waterline_dropped"

    # Without step 3, measure_rim at the hub with y_w = 290 would read below_gutter
    # and pass check 9. G4 would still drop a sedan's wheel.
    wheel, mask, _ = wheel_scene(y_true=240, reflection="hole")
    box = mask_box(wheel)
    shallow = measure_rim(
        rim_of(mask),
        y_w=290.0,
        wheel_box=box,
        brightness=128.0,
        codes=SEDAN,
        tuning=START,
    )
    assert shallow.level == "below_gutter"
    assert shallow.depth_in_min == pytest.approx(0.494, abs=0.001)
    assert shallow.depth_in_max == pytest.approx(1.216, abs=0.001)
    assert shallow.fit.width_x / (box[2] - box[0]) == pytest.approx(0.610, abs=0.001)
    assert keep_reading(WHEEL_ROWS["hub"], shallow) == "wheel_methods_disagree"


@pytest.mark.parametrize(
    ("rim_r", "axis_ratio", "width_x", "size", "bounds", "cause"),
    [
        pytest.param(
            17.5, 0.9988, 34.33, 0.2985, (0.5108, 0.7412), "rim_size", id="hubcap"
        ),
        pytest.param(
            57, 0.9895, 112.76, 0.9805, (0.4966, 0.7197), "rim_size", id="whole"
        ),
        pytest.param(35, 0.9894, 68.99, 0.5999, (0.4965, 0.7196), None, id="rim"),
    ],
)
def test_hubcap_and_whole_wheel_rims_fail_rim_size(
    rim_r, axis_ratio, width_x, size, bounds, cause
):
    # Review Focus 2 (R88): check 9 catches a hubcap or a whole-wheel mask, and the
    # wheel keeps its landmark reading.
    rim = scene_rim(y_true=257, rim_r=rim_r)
    fit = fit_rim(rim_points(rim.mask, 257.0, T))
    assert fit.axis_ratio == pytest.approx(axis_ratio, abs=0.002)
    assert fit.width_x == pytest.approx(width_x, abs=0.005)  # given to 0.01 px
    assert fit.width_x / 115 == pytest.approx(size, abs=0.002)
    assert rim_size_bounds(SEDAN, fit.axis_ratio, START) == pytest.approx(
        bounds, abs=0.002
    )
    assert check(fit) == cause
    result = measure(rim)
    if cause is None:
        assert isinstance(result, GeometryReading)
    else:
        assert result == cause
        # Under the live tuning too, so a tuned factor can't let them through (S3,
        # P4). They would pass only with rim_size_low at 0.4967 or below, or
        # rim_size_high at 1.5667 or above, hence the limits of 0.50 and 1.55.
        live = measure_rim(
            rim,
            y_w=257.0,
            wheel_box=WHEEL_BOX,
            brightness=128.0,
            codes=SEDAN,
            tuning=TUNING,
        )
        assert live == cause
    assert keep_reading(WHEEL_ROWS["rim_quarter"], None) == kept_landmark("rim_quarter")
