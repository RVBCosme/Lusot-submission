"""Tests for steps 6 and 7: one photo's references give one level (spec §3.3, C54)."""

import pytest

from lusot_analysis.pipeline.combine import combine
from lusot_analysis.pipeline.types import Outcome, Reference
from lusot_analysis.rules import BODY_ROWS, PEOPLE_ROWS, WHEEL_ROWS

# Each reference stands for one vehicle or one adult, read from Table 8's own rows. A
# vehicle's reference is its deciding wheel, or its body under the vehicle's box id.


def wheel(box_id: int, waterline: str) -> Reference:
    return Reference("wheel", box_id, waterline, WHEEL_ROWS[waterline])


def body(vehicle_id: int, waterline: str) -> Reference:
    return Reference("body", vehicle_id, waterline, BODY_ROWS[waterline])


def person(box_id: int, waterline: str) -> Reference:
    return Reference("person", box_id, waterline, PEOPLE_ROWS[waterline])


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
        pytest.param([person(8, "ankle"), person(9, "mid_shin")], id="people"),
    ],
)
def test_gutter_gap_refuses(references):
    # Landmarks never read gutter, so each pair sits two levels apart (Rene Q2).
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
