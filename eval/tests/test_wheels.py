"""Set B's and Set D's wheels, and latency (rules §7; C407, C416; MS6E-Q1, item 4)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

from builders import run_json, set_b_row, write_run
from scoring.metrics import (
    LatencyScores,
    Rate,
    WheelScores,
    measured_errors,
    score_latency,
    score_wheels,
    wheel_groups,
)
from scoring.rows import SET_B_VARIANTS, WheelRow, load_run


def measured(point: str, low: str, high: str) -> dict:
    """A measured estimate: its depthInPoint, depthInMin and depthInMax."""
    return {
        "measured": True,
        "depthInPoint": Decimal(point),
        "depthInMin": Decimal(low),
        "depthInMax": Decimal(high),
        "fail": None,
    }


def unmeasured(fail: str) -> dict:
    """An unmeasured estimate, with the check that failed."""
    return {
        "measured": False,
        "depthInPoint": None,
        "depthInMin": None,
        "depthInMax": None,
        "fail": fail,
    }


def wheel_row(crop_id: str, depth: str, geometry: dict, **fields: object) -> dict:
    """A wheel `depth` in deep, with only its geometry estimate."""
    return set_b_row(
        crop_id,
        true_depth_in=Decimal(depth),
        estimates={"geometry": geometry},
        **fields,
    )


def load_set_b(
    folder: Path, rows: Sequence[dict], **run: object
) -> tuple[WheelRow, ...]:
    """Write Set B rows with the builders, then load them as the harness does."""
    return load_run(write_run(folder, run=run_json(**run), set_b=rows)).set_b


# The hand-computed wheels (plan Task 5), each with its error and whether its true
# depth lies inside its envelope.
HAND_WHEELS = (
    wheel_row("C1", "10", measured("11", "9", "12")),  # 1, inside
    wheel_row("C2", "12", measured("11.5", "12.5", "15")),  # 0.5, outside
    wheel_row("C3", "14", measured("14", "13", "15")),  # 0, inside
    wheel_row("C4", "18", measured("20", "17", "19.5")),  # 2, inside
    wheel_row("C5", "16", unmeasured("axis_ratio")),
)

# Three wheels, 10, 12 and 16 in deep, as each variant estimates them.
VARIANT_ESTIMATES = {
    # Errors 1, 0.5 and 3; the third true depth lies below its envelope.
    "geometry": (
        measured("11", "9", "12"),
        measured("12.5", "11", "13"),
        measured("19", "17", "20"),
    ),
    # One wheel measured, 3 in off and outside its envelope.
    "geometry_uncalibrated": (
        measured("13", "12", "14"),
        unmeasured("axis_ratio"),
        unmeasured("axis_ratio"),
    ),
    # Every wheel exact.
    "known_waterline": (
        measured("10", "9", "11"),
        measured("12", "11", "13"),
        measured("16", "15", "17"),
    ),
    # Errors 2 (outside) and 1 (inside).
    "known_waterline_uncalibrated": (
        measured("8", "7", "9"),
        unmeasured("axis_ratio"),
        measured("17", "15", "18"),
    ),
    "geometry_no_self_check": (unmeasured("axis_ratio"),) * 3,
}


def test_hand_computed_wheels(tmp_path):
    rows = load_set_b(tmp_path / "set_b", HAND_WHEELS)
    assert score_wheels(rows, "geometry") == WheelScores(
        variant="geometry",
        wheels=5,
        measured=Rate(4, 5),
        median_error=Decimal("0.75"),  # the mean of 0.5 and 1
        worst_error=Decimal(2),
        envelope=Rate(3, 4),
        sam_water_found=Rate(5, 5),
    )
    assert measured_errors(rows, "geometry") == tuple(
        Decimal(error) for error in ("0", "0.5", "1", "2")
    )
    # Set D's wheels load as Set B's do, and score the same way.
    run = load_run(write_run(tmp_path / "set_d", run=run_json(), set_d=HAND_WHEELS))
    assert score_wheels(run.set_d, "geometry") == score_wheels(rows, "geometry")


def test_envelope_bounds_are_inclusive(tmp_path):
    envelope = measured("11", "10", "12")
    rows = load_set_b(
        tmp_path,
        [
            wheel_row("C1", "10", envelope),  # on depthInMin: inside
            wheel_row("C2", "12", envelope),  # on depthInMax: inside
            wheel_row("C3", "9.9999", envelope),  # just below: outside
            wheel_row("C4", "12.0001", envelope),  # just above: outside
        ],
    )
    assert score_wheels(rows, "geometry").envelope == Rate(2, 4)


def test_variants_are_scored_apart(tmp_path):
    wheels = (("B1", 1, "10"), ("B1", 2, "12"), ("B2", 1, "16"))
    rows = load_set_b(
        tmp_path,
        [
            set_b_row(
                crop_id,
                wheel,
                true_depth_in=Decimal(depth),
                estimates={
                    variant: estimates[index]
                    for variant, estimates in VARIANT_ESTIMATES.items()
                },
            )
            for index, (crop_id, wheel, depth) in enumerate(wheels)
        ],
        self_check="on",
    )
    water = Rate(3, 3)  # SAM's water is the wheel's, the same in every variant
    scores = [score_wheels(rows, variant) for variant in SET_B_VARIANTS]
    assert scores == [
        WheelScores(
            "geometry", 3, Rate(3, 3), Decimal(1), Decimal(3), Rate(2, 3), water
        ),
        WheelScores(
            "geometry_uncalibrated",
            3,
            Rate(1, 3),
            Decimal(3),
            Decimal(3),
            Rate(0, 1),
            water,
        ),
        WheelScores(
            "known_waterline", 3, Rate(3, 3), Decimal(0), Decimal(0), Rate(3, 3), water
        ),
        WheelScores(
            "known_waterline_uncalibrated",
            3,
            Rate(2, 3),
            Decimal("1.5"),
            Decimal(2),
            Rate(1, 2),
            water,
        ),
        WheelScores(
            "geometry_no_self_check", 3, Rate(0, 3), None, None, Rate(0, 0), water
        ),
    ]
    # Their figures differ, not just their names.
    figures = {
        (score.measured, score.median_error, score.worst_error, score.envelope)
        for score in scores
    }
    assert len(figures) == 5
    assert measured_errors(rows, "known_waterline_uncalibrated") == (
        Decimal(1),
        Decimal(2),
    )


def test_groups_by_type_and_bins(tmp_path):
    rows = load_set_b(
        tmp_path,
        [
            set_b_row("B1", vehicle_type="suv_mpv", bins={"view": "side"}),
            set_b_row("B2"),  # a sedan_hatch, without bins
            set_b_row("B3", bins={"view": "side"}),
        ],
    )
    b1, b2, b3 = rows
    # Sorted by value, each group in the rows' order.
    assert wheel_groups(rows, "vehicle_type") == (
        ("sedan_hatch", (b2, b3)),
        ("suv_mpv", (b1,)),
    )
    # A row without the bin is left out.
    assert wheel_groups(rows, "view") == (("side", (b1, b3)),)
    assert wheel_groups(rows, "size_bin") == ()


def test_nothing_measured(tmp_path):
    rows = load_set_b(
        tmp_path,
        [
            wheel_row("C1", "10", unmeasured("axis_ratio")),
            wheel_row("C2", "12", unmeasured("no_waterline"), sam_water_found=False),
        ],
    )
    scores = score_wheels(rows, "geometry")
    assert scores.measured == Rate(0, 2)
    assert scores.median_error is None
    assert scores.worst_error is None
    assert scores.envelope.value is None
    # SAM's water counts over every wheel, measured or not.
    assert scores.sam_water_found == Rate(1, 2)
    assert measured_errors(rows, "geometry") == ()
    # No wheels at all leave every figure undefined.
    assert score_wheels((), "geometry") == WheelScores(
        "geometry", 0, Rate(0, 0), None, None, Rate(0, 0), Rate(0, 0)
    )


def test_latency_nearest_rank(tmp_path):
    # 1 to 20 seconds, the two slowest first, loaded as Run.latency gives them.
    order = (20, 19, *range(1, 19))
    samples = [{"test_id": f"L{seconds}", "seconds": seconds} for seconds in order]
    latency = load_run(write_run(tmp_path, run=run_json(), latency=samples)).latency
    # The mean of the 10th and 11th smallest, and the ceil(0.95 * 20) = 19th.
    assert score_latency(latency) == LatencyScores(20, Decimal("10.5"), Decimal(19))
    # ceil(0.95 * 11) = ceil(10.45) is the 11th smallest, where rounding gives the
    # 10th.
    eleven = [(f"L{seconds}", Decimal(seconds)) for seconds in range(1, 12)]
    assert score_latency(eleven) == LatencyScores(11, Decimal(6), Decimal(11))
    assert score_latency([("L1", Decimal("4.25"))]) == LatencyScores(
        1, Decimal("4.25"), Decimal("4.25")
    )
    assert score_latency([]) == LatencyScores(0, None, None)
    # Every sample counts, a repeated id too; ceil(0.95 * 2) is the 2nd smallest.
    assert score_latency([("L1", Decimal(4)), ("L1", Decimal(2))]) == (
        LatencyScores(2, Decimal(3), Decimal(4))
    )
