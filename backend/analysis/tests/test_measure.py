"""Tests for step 5: each kept vehicle and adult gives at most one reading (spec §3.3).

measure takes Kept after the drops, so every vehicle is a sedan_hatch or suv_mpv
standing still, and every person an adult. Box ids follow number_boxes: vehicles
first, then wheels, then people.
"""

from collections import Counter

import pytest

from lusot_analysis.pipeline.measure import measure
from lusot_analysis.pipeline.references import Kept, KeptPerson, KeptVehicle
from lusot_analysis.pipeline.types import Reference
from lusot_analysis.rules import HIDDEN_WHEEL, PEOPLE_ROWS, WHEEL_ROWS, Reading

TIRE_FLOOR = Reading("tire", floor=True)  # tire or deeper (C54)

# The marks that give a reading, shallowest first. not_visible gives none.
WHEEL_MARKS = (
    "tire_only",
    "rim_quarter",
    "hub",
    "rim_three_quarters",
    "rim_top",
    "wheel_covered",
)
PEOPLE_MARKS = (
    "ankle",
    "mid_shin",
    "knee",
    "mid_thigh",
    "waist",
    "chest",
    "above_chest",
)


def measured(
    *vehicles: KeptVehicle, people: tuple[KeptPerson, ...] = ()
) -> tuple[list[Reference], dict[str, int]]:
    """measure's references and drops for these kept items.

    The drops come back as a plain dict, so a cause logged at 0 fails a test:
    Counter's own == treats a missing cause as 0.
    """
    references, drops = measure(Kept(vehicles=vehicles, people=people))
    assert isinstance(drops, Counter)
    return references, dict(drops)


@pytest.mark.parametrize(
    ("mark", "expected"),
    [
        *(
            pytest.param(
                mark, ([Reference("wheel", 2, mark, WHEEL_ROWS[mark])], {}), id=mark
            )
            for mark in WHEEL_MARKS
        ),
        pytest.param("not_visible", ([], {"vehicle_no_reading": 1}), id="not_visible"),
    ],
)
def test_each_wheel_row_reads_through(mark, expected):
    # A sedan with one wheel. Its body is not_visible, so only the wheel can speak.
    sedan = KeptVehicle(
        1, "not_visible", ((2, mark),), wheels_hidden=mark in HIDDEN_WHEEL
    )
    assert measured(sedan) == expected


@pytest.mark.parametrize(("hub", "rim"), [(2, 3), (3, 2)])
def test_deepest_wheel_speaks(hub, rim):
    # C43: one tire size serves all of a vehicle's wheels, so the deepest reading
    # speaks for it, whichever wheel has the lower id.
    wheels = tuple(sorted([(hub, "hub"), (rim, "rim_three_quarters")]))
    sedan = KeptVehicle(1, "not_visible", wheels, wheels_hidden=False)
    knee = Reading("knee", floor=False)
    assert measured(sedan) == (
        [Reference("wheel", rim, "rim_three_quarters", knee)],
        {},
    )


WHEELS_DISAGREE = ([], {"vehicle_wheels_disagree": 1, "wheel_vehicle_dropped": 2})


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        # Landmarks never read gutter, so these sit two levels apart (Rene Q2).
        pytest.param("tire_only", "rim_quarter", WHEELS_DISAGREE, id="the-gutter-gap"),
        pytest.param(
            "rim_quarter", "rim_top", WHEELS_DISAGREE, id="half-knee-and-tire"
        ),
        # The exact half_tire sits two levels below the tire floor.
        pytest.param("wheel_covered", "hub", WHEELS_DISAGREE, id="floor-and-2-below"),
        # The floor means tire or deeper, and the exact knee sits one level below it.
        pytest.param(
            "wheel_covered",
            "rim_three_quarters",
            ([Reference("wheel", 2, "wheel_covered", TIRE_FLOOR)], {}),
            id="floor-and-1-below",
        ),
    ],
)
def test_wheels_too_far_apart_drop_the_vehicle(first, second, expected):
    # C43, with C54's test: an exact wheel more than one level below the vehicle's
    # deepest wheel drops the vehicle, and its wheels go with it.
    sedan = KeptVehicle(
        1, "not_visible", ((2, first), (3, second)), wheels_hidden=False
    )
    assert measured(sedan) == expected


@pytest.mark.parametrize(("covered", "rim_top"), [(3, 2), (2, 3)])
def test_rim_top_and_wheel_covered_read_as_a_floor(covered, rim_top):
    # C78: both read tire. The floor speaks, whichever wheel has the lower id.
    wheels = tuple(sorted([(covered, "wheel_covered"), (rim_top, "rim_top")]))
    sedan = KeptVehicle(1, "not_visible", wheels, wheels_hidden=False)
    assert measured(sedan) == (
        [Reference("wheel", covered, "wheel_covered", TIRE_FLOOR)],
        {},
    )


@pytest.mark.parametrize(
    ("vehicle", "expected"),
    [
        pytest.param(
            KeptVehicle(1, "window", ((2, "not_visible"),), wheels_hidden=True),
            ([Reference("body", 1, "window", TIRE_FLOOR)], {}),
            id="window",
        ),
        pytest.param(
            KeptVehicle(1, "mid_door", ((2, "not_visible"),), wheels_hidden=True),
            ([Reference("body", 1, "mid_door", TIRE_FLOOR)], {}),
            id="mid_door",
        ),
        # A body floor would tie with the wheel's exact tire and win, so only an
        # unread body leaves the wheel to speak.
        pytest.param(
            KeptVehicle(1, "window", ((2, "rim_top"),), wheels_hidden=False),
            ([Reference("wheel", 2, "rim_top", Reading("tire", floor=False))], {}),
            id="a-visible-wheel",
        ),
        # C69: the vehicle lost a linked wheel to the 40 px rule. That wheel still
        # counts as visible, so the body gives no reading.
        pytest.param(
            KeptVehicle(
                1,
                "window",
                ((2, "not_visible"), (3, "not_visible")),
                wheels_hidden=False,
            ),
            ([], {"vehicle_no_reading": 1}),
            id="lost-a-small-wheel",
        ),
    ],
)
def test_body_reads_only_when_wheels_are_hidden(vehicle, expected):
    # C53: the body reads tire, as a floor, only when the wheels are hidden.
    assert measured(vehicle) == expected


COVERED = ((2, "wheel_covered"),)


@pytest.mark.parametrize(
    ("vehicle", "expected"),
    [
        *(
            pytest.param(
                KeptVehicle(1, body, COVERED, wheels_hidden=True),
                (
                    [],
                    {"vehicle_body_below_covered_wheel": 1, "wheel_vehicle_dropped": 1},
                ),
                id=body,
            )
            for body in ("below_bumper", "bumper", "door_sill")
        ),
        pytest.param(
            KeptVehicle(1, "not_visible", COVERED, wheels_hidden=True),
            ([Reference("wheel", 2, "wheel_covered", TIRE_FLOOR)], {}),
            id="not_visible",
        ),
        # Both read tire, as a floor. A wheel comes before the body, though the body
        # has the lower box id (C78).
        pytest.param(
            KeptVehicle(1, "mid_door", COVERED, wheels_hidden=True),
            ([Reference("wheel", 2, "wheel_covered", TIRE_FLOOR)], {}),
            id="mid_door",
        ),
        # Visible wheels don't save it, and every wheel goes with it, an unseen one
        # too.
        pytest.param(
            KeptVehicle(
                1,
                "door_sill",
                ((2, "wheel_covered"), (3, "not_visible"), (4, "rim_top")),
                wheels_hidden=False,
            ),
            ([], {"vehicle_body_below_covered_wheel": 1, "wheel_vehicle_dropped": 3}),
            id="beside-other-wheels",
        ),
        # A covered wheel beside a hub also fails C43's test, which comes second.
        pytest.param(
            KeptVehicle(
                1, "bumper", ((2, "wheel_covered"), (3, "hub")), wheels_hidden=False
            ),
            ([], {"vehicle_body_below_covered_wheel": 1, "wheel_vehicle_dropped": 2}),
            id="before-the-wheels-test",
        ),
        # Only a covered wheel drops it. A wheel nobody can see gives no reading.
        pytest.param(
            KeptVehicle(1, "door_sill", ((2, "not_visible"),), wheels_hidden=True),
            ([], {"vehicle_no_reading": 1}),
            id="an-unseen-wheel",
        ),
    ],
)
def test_covered_wheel_with_low_body_drops_the_vehicle(vehicle, expected):
    # C53: on these cars the door sill sits below the top of the wheel, so water at
    # the sill or lower can't cover a wheel.
    assert measured(vehicle) == expected


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        pytest.param(
            "window", ([Reference("body", 1, "window", TIRE_FLOOR)], {}), id="window"
        ),
        # With no covered wheel, a low body drops nothing. It just gives no reading.
        pytest.param("bumper", ([], {"vehicle_no_reading": 1}), id="bumper"),
    ],
)
def test_no_linked_wheel_reads_from_the_body(body, expected):
    # C53: with no wheel linked, the wheels count as hidden.
    sedan = KeptVehicle(1, body, (), wheels_hidden=True)
    assert measured(sedan) == expected


@pytest.mark.parametrize(
    ("mark", "expected"),
    [
        *(
            pytest.param(
                mark, ([Reference("person", 1, mark, PEOPLE_ROWS[mark])], {}), id=mark
            )
            for mark in PEOPLE_MARKS
        ),
        pytest.param("not_visible", ([], {"person_no_reading": 1}), id="not_visible"),
    ],
)
def test_each_people_row_reads_through(mark, expected):
    # D13: people count fully, so each kept adult gives its own reference.
    assert measured(people=(KeptPerson(1, mark),)) == expected


def test_unanswered_wheel_blocks_the_body_reading():
    # Review Focus 1 (C76). Muse Spark skipped vehicle 2's wheel 4, so apply_drops
    # counted it as visible and passed on only wheel 5. Hidden wheels and a
    # window-deep body would read tire as a floor, but here nothing reads, and the
    # unseen wheel isn't counted as dropped.
    vehicle = KeptVehicle(2, "window", ((5, "not_visible"),), wheels_hidden=False)
    assert measured(vehicle) == ([], {"vehicle_no_reading": 1})


def test_one_reference_per_vehicle_then_per_adult():
    # Each kind comes in id order, vehicles first. Vehicle 3's body speaks for it
    # under box id 3, yet comes after vehicle 1's wheel 5. The drops add up.
    vehicles = (
        KeptVehicle(
            1,
            "not_visible",
            ((4, "hub"), (5, "rim_three_quarters")),
            wheels_hidden=False,
        ),
        KeptVehicle(
            2,
            "not_visible",
            ((6, "tire_only"), (7, "rim_quarter")),
            wheels_hidden=False,
        ),
        KeptVehicle(3, "window", (), wheels_hidden=True),
    )
    people = (
        KeptPerson(8, "knee"),
        KeptPerson(9, "not_visible"),
        KeptPerson(10, "mid_thigh"),
    )
    assert measured(*vehicles, people=people) == (
        [
            Reference("wheel", 5, "rim_three_quarters", Reading("knee", floor=False)),
            Reference("body", 3, "window", TIRE_FLOOR),
            Reference("person", 8, "knee", Reading("knee", floor=False)),
            Reference("person", 10, "mid_thigh", Reading("tire", floor=False)),
        ],
        {
            "vehicle_wheels_disagree": 1,
            "wheel_vehicle_dropped": 2,
            "person_no_reading": 1,
        },
    )
