"""Tests for step 5: each kept vehicle and adult gives at most one deciding reading.

Spec §3.3, and MS3b's C317 and G4. measure takes Kept after the drops, so every
vehicle stands still and is a sedan_hatch or suv_mpv, or with geometry on a van or
unknown (C318), and every person is an adult. Box ids follow number_boxes: vehicles
first, then wheels, then people.
"""

from collections import Counter
from collections.abc import Mapping

import pytest

from lusot_analysis.pipeline.geometry import GeometryReading
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
    *vehicles: KeptVehicle,
    people: tuple[KeptPerson, ...] = (),
    step3_drops: Mapping[int, str] | None = None,
    geometry: Mapping[int, GeometryReading] | None = None,
) -> tuple[list[Reference], dict[str, int]]:
    """measure's references and drops for these kept items.

    The drops come back as a plain dict, so a cause logged at 0 fails a test:
    Counter's own == treats a missing cause as 0. Only the options a test gives are
    passed, so MS3a's tests still call measure(kept) alone.
    """
    options = {"step3_drops": step3_drops, "geometry": geometry}
    references, drops = measure(
        Kept(vehicles=vehicles, people=people),
        **{name: value for name, value in options.items() if value is not None},
    )
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


KNEE = Reading("knee", floor=False)
KNEE_GEOMETRY = GeometryReading(13.47, 13.47, "knee")  # 13.47 in is knee (§1)


@pytest.mark.parametrize("type_", ["van", "unknown"])
def test_geometry_only_types_read_from_geometry(type_):
    # C318: Table 8's wheel rows don't cover these types, so their wheels read from
    # geometry alone. The landmark is still Muse Spark's category (C320).
    van = KeptVehicle(
        1, "not_visible", ((5, "hub"),), wheels_hidden=False, vehicle_type=type_
    )
    assert measured(van, geometry={5: KNEE_GEOMETRY}) == (
        [
            Reference(
                "wheel", 5, "hub", KNEE, level_from="geometry", depth_in=(13.47, 13.47)
            )
        ],
        {},
    )
    assert measured(van) == ([], {"vehicle_no_reading": 1})
    # With no landmark reading, a wheel step 3 dropped leaves nothing to keep (C317).
    assert measured(van, step3_drops={5: "no_water_contact"}) == (
        [],
        {"no_water_contact": 1, "vehicle_no_reading": 1},
    )
    # C53's body rule is for sedans and SUVs only.
    hidden = KeptVehicle(
        1, "window", ((5, "not_visible"),), wheels_hidden=True, vehicle_type=type_
    )
    assert measured(hidden) == ([], {"vehicle_no_reading": 1})


def test_g4_through_measure():
    # G4: a sedan wheel's landmark and geometry readings give one, the deeper. A
    # geometry level keeps the wheel's landmark, Muse Spark's category (C320).
    sedan = KeptVehicle(1, "not_visible", ((2, "hub"),), wheels_hidden=False)
    assert measured(sedan, geometry={2: KNEE_GEOMETRY}) == (
        [
            Reference(
                "wheel", 2, "hub", KNEE, level_from="geometry", depth_in=(13.47, 13.47)
            )
        ],
        {},
    )
    # More than one level apart, the wheel is dropped, and the vehicle has nothing
    # left to read.
    shallow = GeometryReading(3.2, 4.1, "below_gutter")
    assert measured(sedan, geometry={2: shallow}) == (
        [],
        {"wheel_methods_disagree": 1, "vehicle_no_reading": 1},
    )
    # A deeper landmark is kept, and carries no inches (C307).
    rim_top = KeptVehicle(1, "not_visible", ((2, "rim_top"),), wheels_hidden=False)
    assert measured(rim_top, geometry={2: KNEE_GEOMETRY}) == (
        [Reference("wheel", 2, "rim_top", Reading("tire", floor=False))],
        {},
    )


def test_step3_drops_keep_the_reading_for_c317():
    # C317: step 3's drop takes away only the reading's say. The reading never
    # decides, but combine still sees it, so it can refuse the photo. Each counts
    # under its cause.
    sedan = KeptVehicle(1, "not_visible", ((4, "rim_top"),), wheels_hidden=False)
    assert measured(sedan, step3_drops={4: "no_water_contact"}) == (
        [Reference("wheel", 4, "rim_top", Reading("tire", floor=False), decides=False)],
        {"no_water_contact": 1, "vehicle_no_reading": 1},
    )
    adult = KeptPerson(5, "waist")
    assert measured(people=(adult,), step3_drops={5: "ragged_waterline"}) == (
        [Reference("person", 5, "waist", Reading("waist", floor=False), decides=False)],
        {"ragged_waterline": 1},
    )
    hidden = KeptVehicle(1, "window", ((2, "not_visible"),), wheels_hidden=True)
    assert measured(hidden, step3_drops={1: "ragged_waterline"}) == (
        [Reference("body", 1, "window", TIRE_FLOOR, decides=False)],
        {"ragged_waterline": 1, "vehicle_no_reading": 1},
    )


def test_a_dropped_wheel_still_counts_as_visible():
    # C317, C53: step 3 dropping the hub's reading doesn't hide the wheel, so the
    # window-deep body gives no reading.
    sedan = KeptVehicle(1, "window", ((2, "hub"),), wheels_hidden=False)
    assert measured(sedan, step3_drops={2: "no_water_contact"}) == (
        [
            Reference(
                "wheel", 2, "hub", Reading("half_tire", floor=False), decides=False
            )
        ],
        {"no_water_contact": 1, "vehicle_no_reading": 1},
    )


def test_a_kept_vehicle_keeps_its_dropped_readings_too():
    # C317: wheel 2's rim_top, which step 3 dropped, goes beside the hub that speaks
    # for the vehicle, so combine refuses the photo rather than let the shallower
    # hub win. C43 runs over the deciding wheels only, so the vehicle isn't dropped.
    # The vehicle's own reference comes first, then the ones that can't decide.
    sedan = KeptVehicle(
        1, "not_visible", ((2, "rim_top"), (3, "hub")), wheels_hidden=False
    )
    assert measured(sedan, step3_drops={2: "no_water_contact"}) == (
        [
            Reference("wheel", 3, "hub", Reading("half_tire", floor=False)),
            Reference(
                "wheel", 2, "rim_top", Reading("tire", floor=False), decides=False
            ),
        ],
        {"no_water_contact": 1},
    )


def test_a_dropped_vehicle_gives_nothing():
    # C317: readings of a vehicle that C53 drops play no part, not even as ones that
    # can't decide. Its wheel counts once, with its vehicle.
    sedan = KeptVehicle(1, "door_sill", ((2, "wheel_covered"),), wheels_hidden=True)
    assert measured(sedan, step3_drops={2: "no_water_contact"}) == (
        [],
        {"vehicle_body_below_covered_wheel": 1, "wheel_vehicle_dropped": 1},
    )


def test_a_c43_dropped_vehicle_gives_nothing():
    # Finding 8: hub and tire_only sit three levels apart, so C43 drops the vehicle.
    # Wheel 6's rim_top, which step 3 dropped, plays no part either (C317).
    sedan = KeptVehicle(
        1,
        "not_visible",
        ((4, "hub"), (5, "tire_only"), (6, "rim_top")),
        wheels_hidden=False,
    )
    assert measured(sedan, step3_drops={6: "no_water_contact"}) == (
        [],
        {"vehicle_wheels_disagree": 1, "wheel_vehicle_dropped": 3},
    )


def test_a_dropped_vehicle_counts_a_g4_drop_once():
    # Each wheel counts once, after its vehicle's fate is known. G4 drops wheel 6
    # (half_knee against chest), then C43 drops the vehicle, so wheel 6 counts only
    # as wheel_vehicle_dropped.
    sedan = KeptVehicle(
        1,
        "not_visible",
        ((4, "hub"), (5, "tire_only"), (6, "rim_quarter")),
        wheels_hidden=False,
    )
    chest = GeometryReading(40.2, 41.0, "chest")
    assert measured(sedan, geometry={6: chest}) == (
        [],
        {"vehicle_wheels_disagree": 1, "wheel_vehicle_dropped": 3},
    )
