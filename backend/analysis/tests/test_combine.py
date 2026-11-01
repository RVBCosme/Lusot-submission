"""Tests for steps 6 and 7: one photo's references give one level (spec §3.3, C54)."""

from dataclasses import replace

import pytest

from lusot_analysis.pipeline.combine import combine
from lusot_analysis.pipeline.types import Outcome, Reference
from lusot_analysis.rules import BODY_ROWS, PEOPLE_ROWS, WHEEL_ROWS, Reading

# Each reference stands for one vehicle or one adult, read from Table 8's own rows. A
# vehicle's reference is its deciding wheel, or its body under the vehicle's box id.


def wheel(box_id: int, waterline: str) -> Reference:
    return Reference("wheel", box_id, waterline, WHEEL_ROWS[waterline])


def body(vehicle_id: int, waterline: str) -> Reference:
    return Reference("body", vehicle_id, waterline, BODY_ROWS[waterline])


def person(box_id: int, waterline: str) -> Reference:
    return Reference("person", box_id, waterline, PEOPLE_ROWS[waterline])


def geometry_wheel(
    box_id: int, waterline: str, level: str, depth_in: tuple[float, float]
) -> Reference:
    """A wheel whose level geometry set. Its landmark stays Muse Spark's (C320)."""
    return Reference(
        "wheel",
        box_id,
        waterline,
        Reading(level, floor=False),  # geometry readings are exact
        level_from="geometry",
        depth_in=depth_in,
    )


def dropped(reference: Reference) -> Reference:
    """The reference as step 3 leaves it: it can refuse, never decide (C317)."""
    return replace(reference, decides=False)


DISAGREE = (Outcome.refused("references_disagree"), None)


def test_floor_beside_exact_chest_gives_chest():
    # A floor means "this level or deeper", so it agrees with any deeper reading.
    outcome, deciding = combine([wheel(4, "wheel_covered"), person(9, "chest")])
    assert outcome == Outcome(
        "done",
        level="chest",
        landmark="chest",
        passability="NPATV",
        level_is_floor=False,
        basis={"vehicles": 1, "people": 1},
    )
    assert deciding == person(9, "chest")


def test_floor_beside_exact_knee_gives_tire_as_a_floor():
    outcome, deciding = combine(
        [wheel(4, "wheel_covered"), wheel(6, "rim_three_quarters")]
    )
    assert outcome == Outcome(
        "done",
        level="tire",
        landmark="wheel_covered",
        passability="NPATV",
        level_is_floor=True,
        basis={"vehicles": 2, "people": 0},
    )
    assert deciding == wheel(4, "wheel_covered")


def test_floor_beside_exact_half_tire_refuses():
    # The exact half_tire sits two levels below the tire floor.
    assert combine([wheel(4, "wheel_covered"), wheel(6, "hub")]) == DISAGREE


def test_exact_knee_beside_exact_chest_refuses():
    assert combine([person(8, "knee"), person(9, "chest")]) == DISAGREE


@pytest.mark.parametrize(
    "references",
    [
        pytest.param([wheel(3, "tire_only"), wheel(5, "rim_quarter")], id="wheels"),
    ],
)
def test_gutter_gap_refuses(references):
    # Landmarks never read gutter, so each pair sits two levels apart (Rene Q2). An
    # adult's ankle gives no reading since C91, so only the wheels' pair is left.
    assert combine(references) == DISAGREE


def test_one_level_apart_takes_the_deeper():
    outcome, deciding = combine([wheel(3, "hub"), person(8, "knee")])
    assert outcome == Outcome(
        "done",
        level="knee",
        landmark="knee",
        passability="NPLV",
        level_is_floor=False,
        basis={"vehicles": 1, "people": 1},
    )
    assert deciding == person(8, "knee")


def test_a_standing_adult_alone_sets_the_level():
    # D13: people count fully, so one adult gives a level with no vehicle in sight.
    outcome, deciding = combine([person(8, "knee")])
    assert outcome == Outcome(
        "done",
        level="knee",
        landmark="knee",
        passability="NPLV",
        level_is_floor=False,
        basis={"vehicles": 0, "people": 1},
    )
    assert deciding == person(8, "knee")


def test_no_reference_refuses():
    assert combine([]) == (Outcome.refused("no_usable_reference"), None)


@pytest.mark.parametrize(
    ("references", "deciding", "level_is_floor"),
    [
        pytest.param(
            [wheel(6, "rim_top"), person(9, "mid_thigh")],
            wheel(6, "rim_top"),
            False,
            id="a-wheel-before-a-person",
        ),
        pytest.param(
            [wheel(6, "rim_top"), body(2, "window")],
            body(2, "window"),
            True,
            id="a-floor-before-an-exact-reading",
        ),
        pytest.param(
            [wheel(7, "wheel_covered"), body(1, "mid_door")],
            wheel(7, "wheel_covered"),
            True,
            id="a-wheel-before-a-body",
        ),
        pytest.param(
            [wheel(8, "rim_top"), wheel(5, "rim_top")],
            wheel(5, "rim_top"),
            False,
            id="the-lowest-wheel-id",
        ),
        pytest.param(
            [person(10, "chest"), person(9, "chest")],
            person(9, "chest"),
            False,
            id="the-lowest-person-id",
        ),
    ],
)
def test_ties(references, deciding, level_is_floor):
    # Both input orders, so only C54's tie order can pass.
    for order in (references, references[::-1]):
        outcome, chosen = combine(order)
        assert chosen == deciding
        assert outcome.landmark == deciding.landmark
        assert outcome.level_is_floor is level_is_floor


def test_level_is_floor_only_at_the_result_level():
    # The tire floor sits below the waist result, so the result is exact.
    outcome, deciding = combine([wheel(4, "wheel_covered"), person(9, "waist")])
    assert outcome == Outcome(
        "done",
        level="waist",
        landmark="waist",
        passability="NPATV",
        level_is_floor=False,
        basis={"vehicles": 1, "people": 1},
    )
    assert deciding == person(9, "waist")


def test_result_ignores_input_order():
    # B3: a replay gives the same result, whatever order the references come in.
    references = [
        person(10, "mid_thigh"),
        wheel(8, "rim_top"),
        body(2, "window"),
        wheel(5, "rim_three_quarters"),
        person(9, "mid_thigh"),
        wheel(7, "wheel_covered"),
    ]
    outcome, deciding = combine(references)
    assert (outcome, deciding) == combine(list(reversed(references)))
    # Five tie at tire. Of the two floors, the covered wheel decides before the body,
    # and the body counts as a vehicle.
    assert outcome == Outcome(
        "done",
        level="tire",
        landmark="wheel_covered",
        passability="NPATV",
        level_is_floor=True,
        basis={"vehicles": 4, "people": 2},
    )
    assert deciding == wheel(7, "wheel_covered")
    # Non-deciding references change none of it, in either order (C317): a covered
    # wheel that would win the tie, a person deeper than the floor, and a wheel that
    # C54 would refuse if it were kept.
    mixed = [
        dropped(wheel(3, "wheel_covered")),
        *references[:3],
        dropped(person(11, "waist")),
        *references[3:],
        dropped(wheel(6, "hub")),
    ]
    assert combine(mixed) == combine(list(reversed(mixed))) == (outcome, deciding)


def test_geometry_deciding_reference_brings_its_inches():
    # C307: the deciding reference's level came from geometry, so its inches go too.
    reference = geometry_wheel(2, "rim_quarter", "half_knee", (8.29, 8.79))
    outcome, deciding = combine([reference])
    assert deciding == reference
    assert outcome.level == "half_knee"
    assert outcome.landmark == "rim_quarter"
    assert outcome.level_from == "geometry"
    assert (outcome.depth_in_min, outcome.depth_in_max) == (8.29, 8.79)


def test_a_person_reading_deeper_decides_without_inches():
    # Review Focus 4. Two levels apart refuses, as C54 does for any two readings.
    geometry = geometry_wheel(3, "rim_quarter", "half_knee", (8.29, 8.79))
    assert combine([geometry, person(9, "knee")]) == DISAGREE
    # One level deeper: the person decides, and a person's level carries no inches.
    geometry = geometry_wheel(3, "hub", "half_tire", (11.08, 11.77))
    outcome, deciding = combine([geometry, person(9, "knee")])
    assert deciding == person(9, "knee")
    assert outcome.level == "knee"
    assert outcome.landmark == "knee"
    assert outcome.level_from == "landmark"
    assert (outcome.depth_in_min, outcome.depth_in_max) == (None, None)
    # A tie goes to the wheel (C54), with its inches. Its landmark stays hub (C320).
    geometry = geometry_wheel(3, "hub", "knee", (13.47, 13.47))
    outcome, deciding = combine([person(9, "knee"), geometry])
    assert deciding == geometry
    assert outcome == Outcome.level_result(
        "knee",
        "hub",
        False,
        {"vehicles": 1, "people": 1},
        level_from="geometry",
        depth_in=(13.47, 13.47),
    )


def test_geometry_ties_follow_c54():
    # C307 leaves C54's tie order as it is: the lowest wheel id decides.
    geometry = geometry_wheel(3, "rim_quarter", "half_tire", (11.08, 11.77))
    for order in ([geometry, wheel(5, "hub")], [wheel(5, "hub"), geometry]):
        outcome, deciding = combine(order)
        assert deciding == geometry
        assert outcome.landmark == "rim_quarter"
        assert outcome.level_from == "geometry"
        assert (outcome.depth_in_min, outcome.depth_in_max) == (11.08, 11.77)
    # Swap the boxes, and the landmark wheel decides, without inches.
    geometry = geometry_wheel(5, "rim_quarter", "half_tire", (11.08, 11.77))
    for order in ([geometry, wheel(3, "hub")], [wheel(3, "hub"), geometry]):
        outcome, deciding = combine(order)
        assert deciding == wheel(3, "hub")
        assert outcome.landmark == "hub"
        assert outcome.level_from == "landmark"
        assert (outcome.depth_in_min, outcome.depth_in_max) == (None, None)


@pytest.mark.parametrize(
    ("kept", "drops", "expected"),
    [
        # Deeper than an exact result: the photo is refused, even one level deeper,
        # which two kept readings may be (R87).
        pytest.param(
            [wheel(4, "hub")],
            [person(9, "knee")],
            DISAGREE,
            id="a-deeper-person-refuses-an-exact-wheel",
        ),
        pytest.param(
            [person(8, "knee")],
            [person(9, "waist")],
            DISAGREE,
            id="a-deeper-person-refuses-an-exact-person",
        ),
        # A floor already means "this level or deeper" (R90).
        pytest.param(
            [wheel(4, "wheel_covered")],
            [person(9, "waist")],
            (
                Outcome.level_result(
                    "tire", "wheel_covered", True, {"vehicles": 1, "people": 0}
                ),
                wheel(4, "wheel_covered"),
            ),
            id="a-floor-stands",
        ),
        # At the result's level or below, a dropped reading changes nothing, and the
        # basis counts the deciding references only.
        pytest.param(
            [person(8, "knee")],
            [wheel(4, "rim_three_quarters")],
            (
                Outcome.level_result(
                    "knee", "knee", False, {"vehicles": 0, "people": 1}
                ),
                person(8, "knee"),
            ),
            id="the-same-level",
        ),
        pytest.param(
            [person(8, "chest")],
            [body(2, "window")],
            (
                Outcome.level_result(
                    "chest", "chest", False, {"vehicles": 0, "people": 1}
                ),
                person(8, "chest"),
            ),
            id="a-floor-below",
        ),
        # Three levels below: C54 would refuse it if it were kept, but a dropped
        # reading never refuses from below.
        pytest.param(
            [wheel(4, "hub")],
            [wheel(5, "tire_only")],
            (
                Outcome.level_result(
                    "half_tire", "hub", False, {"vehicles": 1, "people": 0}
                ),
                wheel(4, "hub"),
            ),
            id="three-levels-below",
        ),
        # Nothing that may decide, whatever was dropped.
        pytest.param(
            [],
            [wheel(4, "hub"), person(9, "knee")],
            (Outcome.refused("no_usable_reference"), None),
            id="only-dropped-readings",
        ),
    ],
)
def test_dropped_readings_refuse_only_when_deeper(kept, drops, expected):
    # C317 as amended (R87, R90): a reading step 3 drops never decides.
    references = [*kept, *map(dropped, drops)]
    for order in (references, references[::-1]):
        assert combine(order) == expected
