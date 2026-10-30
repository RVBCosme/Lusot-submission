"""Tests for step 5: each kept vehicle and adult gives at most one deciding reading.

Spec §3.3, and MS3b's C317 and G4. measure takes Kept after the drops, so every
vehicle stands still and is a sedan_hatch or suv_mpv, or with geometry on a type kept
for geometry (C318), and every person is an adult. Box ids follow number_boxes: vehicles
first, then wheels, then people.
"""

from collections import Counter
from collections.abc import Mapping

import pytest
from fakes import answer, vehicle, wheel

from lusot_analysis.annotate import NumberedBox
from lusot_analysis.pipeline.combine import combine
from lusot_analysis.pipeline.geometry import GeometryReading, KeptReading
from lusot_analysis.pipeline.measure import measure, measure_boxes
from lusot_analysis.pipeline.references import (
    Kept,
    KeptPerson,
    KeptVehicle,
    Layout,
    apply_drops,
)
from lusot_analysis.pipeline.types import Outcome, Reference
from lusot_analysis.rules import (
    GEOMETRY_ONLY_TYPES,
    HIDDEN_WHEEL,
    PEOPLE_ROWS,
    READING_TYPES,
    WHEEL_ROWS,
    Reading,
)

TIRE_FLOOR = Reading("tire", floor=True)  # tire or deeper (C54)
HUB_FLOOR = Reading("half_tire", floor=True)  # a hub's sedan row, as a floor (M5)

# The types kept for geometry: van and unknown, and pickup since M11's tire codes
# (C318). Jeepney has none yet (R170).
GEOMETRY_TYPES = sorted(GEOMETRY_ONLY_TYPES)

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


@pytest.mark.parametrize("type_", GEOMETRY_TYPES)
def test_geometry_only_types_read_from_geometry(type_):
    # C318: Table 8's wheel rows don't cover these types, so their wheels read from
    # geometry alone. The landmark is still Muse Spark's category (C320). The hub's
    # sedan row is held as a floor that can't decide (M5).
    van = KeptVehicle(
        1, "not_visible", ((5, "hub"),), wheels_hidden=False, vehicle_type=type_
    )
    hub_floor = Reference("wheel", 5, "hub", HUB_FLOOR, decides=False)
    assert measured(van, geometry={5: KNEE_GEOMETRY}) == (
        [
            Reference(
                "wheel", 5, "hub", KNEE, level_from="geometry", depth_in=(13.47, 13.47)
            ),
            hub_floor,
        ],
        {},
    )
    assert measured(van) == ([hub_floor], {"vehicle_no_reading": 1})
    # A wheel step 3 dropped still holds its floor (M5, C317).
    assert measured(van, step3_drops={5: "no_water_contact"}) == (
        [hub_floor],
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


# Wheel 3 at hub, read by geometry at knee, and the floors that a geometry-only type
# holds without letting them decide: covered wheel 2's tire (R143) and wheel 3's hub
# row (M5).
KNEE_AT_3 = Reference(
    "wheel", 3, "hub", KNEE, level_from="geometry", depth_in=(13.47, 13.47)
)
COVERED_FLOOR_AT_2 = Reference("wheel", 2, "wheel_covered", TIRE_FLOOR, decides=False)
HUB_FLOOR_AT_3 = Reference("wheel", 3, "hub", HUB_FLOOR, decides=False)


@pytest.mark.parametrize(
    ("type_", "expected", "outcome"),
    [
        *(
            pytest.param(
                type_,
                ([KNEE_AT_3, COVERED_FLOOR_AT_2, HUB_FLOOR_AT_3], {}),
                Outcome.refused("references_disagree"),
                id=type_,
            )
            for type_ in GEOMETRY_TYPES
        ),
        *(
            pytest.param(
                type_,
                (
                    [],
                    {"vehicle_body_below_covered_wheel": 1, "wheel_vehicle_dropped": 2},
                ),
                Outcome.refused("no_usable_reference"),
                id=type_,
            )
            for type_ in ("sedan_hatch", "suv_mpv")
        ),
    ],
)
def test_c53_drops_only_sedans_and_suvs(type_, expected, outcome):
    # R142: C53's drop rests on a sedan's or SUV's door sill sitting below the top of
    # its wheels, so like the body reading it is for READING_TYPES only. Vehicle 1's
    # body is at door_sill, below its covered wheel 2, and wheel 3 has a geometry
    # reading. With geometry on, apply_drops keeps every one of these types. A van's
    # covered wheel holds its floor (R143), which refuses the shallower knee.
    given = answer(
        vehicles=[vehicle(1, type=type_, body="door_sill")],
        wheels=[wheel(2, "wheel_covered"), wheel(3, "hub")],
    )
    boxes = Layout(
        boxes=tuple(
            NumberedBox(i, kind, (0, 0, 10, 10))
            for i, kind in ((1, "vehicle"), (2, "wheel"), (3, "wheel"))
        ),
        wheel_vehicle={2: 1, 3: 1},
        small_wheel_vehicles=frozenset(),
    )
    kept, drops = apply_drops(given, boxes, geometry_types=GEOMETRY_ONLY_TYPES)
    assert not drops
    references, causes = measured(*kept.vehicles, geometry={3: KNEE_GEOMETRY})
    assert (references, causes) == expected
    assert combine(references)[0] == outcome


HALF_TIRE_GEOMETRY = GeometryReading(11.2, 12.6, "half_tire")  # 12.6 in is half_tire
WAIST_GEOMETRY = GeometryReading(30.2, 31.6, "waist")  # 31.6 in is waist


@pytest.mark.parametrize("type_", GEOMETRY_TYPES)
def test_a_covered_geometry_only_wheel_gives_a_floor_that_cannot_decide(type_):
    # R143: Table 8's covered row is a sedan's, and a larger wheel that is covered is
    # at least as deep, so a geometry-only type's covered wheel holds tire as a
    # floor. It never decides and joins no C43 test, but combine can refuse with it
    # (C317).
    def van(*wheels: tuple[int, str]) -> KeptVehicle:
        hidden = all(line in HIDDEN_WHEEL for _, line in wheels)
        return KeptVehicle(1, "not_visible", wheels, hidden, vehicle_type=type_)

    covered = (2, "wheel_covered")
    assert measured(van(covered, (3, "hub")), geometry={3: KNEE_GEOMETRY}) == (
        [KNEE_AT_3, COVERED_FLOOR_AT_2, HUB_FLOOR_AT_3],
        {},
    )
    assert measured(van(covered)) == ([COVERED_FLOOR_AT_2], {"vehicle_no_reading": 1})
    # half_tire sits two levels below the floor, so the floor would fail C43's test
    # if it took part.
    half_tire = Reference(
        "wheel",
        3,
        "hub",
        Reading("half_tire", floor=False),
        level_from="geometry",
        depth_in=(11.2, 12.6),
    )
    assert measured(van(covered, (3, "hub")), geometry={3: HALF_TIRE_GEOMETRY}) == (
        [half_tire, COVERED_FLOOR_AT_2, HUB_FLOOR_AT_3],
        {},
    )
    # A C43 drop of its vehicle takes the floor with it.
    shallow = GeometryReading(3.2, 4.1, "below_gutter")
    assert measured(
        van(covered, (3, "hub"), (4, "tire_only")),
        geometry={3: KNEE_GEOMETRY, 4: shallow},
    ) == ([], {"vehicle_wheels_disagree": 1, "wheel_vehicle_dropped": 3})
    # A covered wheel that step 3 dropped still holds its floor, as a sedan's holds its
    # landmark (C317).
    assert measured(van(covered), step3_drops={2: "no_water_contact"}) == (
        [COVERED_FLOOR_AT_2],
        {"no_water_contact": 1, "vehicle_no_reading": 1},
    )


@pytest.mark.parametrize("type_", GEOMETRY_TYPES)
def test_a_covered_geometry_only_wheel_refuses_a_shallower_reading(type_):
    # R143 through combine: the same answers on a sedan give tire or deeper, so the
    # van can't publish an exact shallower level beside its covered wheel.
    van = KeptVehicle(
        1,
        "not_visible",
        ((2, "wheel_covered"), (3, "hub")),
        wheels_hidden=False,
        vehicle_type=type_,
    )

    def combined(
        depth: GeometryReading, step3_drops: dict[int, str] | None = None
    ) -> tuple[Outcome, Reference | None]:
        references, _ = measure(
            Kept(vehicles=(van,), people=()),
            step3_drops=step3_drops,
            geometry={3: depth},
        )
        return combine(references)

    # The exact knee sits below the floor, so the photo is refused (C317).
    assert combined(KNEE_GEOMETRY) == (Outcome.refused("references_disagree"), None)
    # The floor holds when step 3 drops the covered wheel too, so SAM missing the water
    # doesn't let the shallower reading win (R143, C317).
    dropped = {2: "no_water_contact"}
    assert combined(KNEE_GEOMETRY, dropped) == (
        Outcome.refused("references_disagree"),
        None,
    )
    # Waist isn't below the floor, so geometry's result stands, with its inches
    # (C307). Check 8 keeps a real wheel's depth within its tire's radius, under
    # 14 in for these codes, so this depth is synthetic.
    waist = Reference(
        "wheel",
        3,
        "hub",
        Reading("waist", floor=False),
        level_from="geometry",
        depth_in=(30.2, 31.6),
    )
    result = Outcome.level_result(
        "waist",
        "hub",
        False,
        {"vehicles": 1, "people": 0},
        level_from="geometry",
        depth_in=(30.2, 31.6),
    )
    assert combined(WAIST_GEOMETRY) == (result, waist)


REFUSED = (Outcome.refused("references_disagree"), None)
BELOW_GUTTER_GEOMETRY = GeometryReading(3.2, 4.1, "below_gutter")  # 4.1 in
TIRE_GEOMETRY = GeometryReading(20.4, 21.3, "tire")  # 21.3 in is tire


def geometry_result(level: str, landmark: str, depth: GeometryReading) -> Outcome:
    """combine's result when one geometry reading on a vehicle decides (C307)."""
    return Outcome.level_result(
        level,
        landmark,
        False,
        {"vehicles": 1, "people": 0},
        level_from="geometry",
        depth_in=(depth.depth_in_min, depth.depth_in_max),
    )


@pytest.mark.parametrize("type_", GEOMETRY_TYPES)
def test_m5_another_wheels_floor_refuses_a_shallower_reading(type_):
    # M5 (Rene, Oct 30): a sedan's Table 8 row bounds any larger wheel from below, so
    # each answered wheel of a geometry-only type holds its row as a floor that never
    # decides. Wheel 2's hub has no geometry, yet its half_tire floor refuses wheel
    # 3's exact below_gutter through combine (C317). tire_only's own floor is
    # below_gutter, so the refusal is wheel 2's.
    van = KeptVehicle(
        1,
        "not_visible",
        ((2, "hub"), (3, "tire_only")),
        wheels_hidden=False,
        vehicle_type=type_,
    )
    hub_floor = Reference("wheel", 2, "hub", HUB_FLOOR, decides=False)
    tire_only_floor = Reference(
        "wheel", 3, "tire_only", Reading("below_gutter", floor=True), decides=False
    )

    def at_3(depth: GeometryReading) -> Reference:
        return Reference(
            "wheel",
            3,
            "tire_only",
            Reading(depth.level, floor=False),
            level_from="geometry",
            depth_in=(depth.depth_in_min, depth.depth_in_max),
        )

    references, drops = measured(van, geometry={3: BELOW_GUTTER_GEOMETRY})
    assert (references, drops) == (
        [at_3(BELOW_GUTTER_GEOMETRY), hub_floor, tire_only_floor],
        {},
    )
    assert combine(references) == REFUSED
    # Knee is at or above every held floor, so geometry's result stands, with its
    # inches.
    references, drops = measured(van, geometry={3: KNEE_GEOMETRY})
    assert (references, drops) == (
        [at_3(KNEE_GEOMETRY), hub_floor, tire_only_floor],
        {},
    )
    assert combine(references) == (
        geometry_result("knee", "tire_only", KNEE_GEOMETRY),
        at_3(KNEE_GEOMETRY),
    )
    # The evidence record gives the floor, or the geometry reading over it (R147).
    m = measure_boxes(Kept(vehicles=(van,), people=()), geometry={3: KNEE_GEOMETRY})
    assert m.readings == {
        2: KeptReading(HUB_FLOOR, "landmark", None),
        3: KeptReading(KNEE, "geometry", (13.47, 13.47)),
    }


@pytest.mark.parametrize("type_", GEOMETRY_TYPES)
def test_m5_a_wheels_floor_refuses_its_own_shallower_reading(type_):
    # M5: rim_top's sedan row is tire, so the van wheel holds tire as a floor, and its
    # own geometry must read tire or deeper to stand. combine refuses any exact level
    # below a held floor, knee too, as R143's covered wheel does (C317).
    van = KeptVehicle(
        1, "not_visible", ((2, "rim_top"),), wheels_hidden=False, vehicle_type=type_
    )
    floor = Reference("wheel", 2, "rim_top", TIRE_FLOOR, decides=False)

    def combined(depth: GeometryReading) -> tuple[Outcome, Reference | None]:
        references, drops = measured(van, geometry={2: depth})
        assert drops == {}
        assert references[1:] == [floor]
        return combine(references)

    assert combined(HALF_TIRE_GEOMETRY) == REFUSED
    assert combined(KNEE_GEOMETRY) == REFUSED
    # Check 8 keeps a real wheel's depth within its tire's radius, so a tire-deep
    # reading is synthetic.
    deciding = Reference(
        "wheel",
        2,
        "rim_top",
        Reading("tire", floor=False),
        level_from="geometry",
        depth_in=(20.4, 21.3),
    )
    assert combined(TIRE_GEOMETRY) == (
        geometry_result("tire", "rim_top", TIRE_GEOMETRY),
        deciding,
    )


@pytest.mark.parametrize("type_", GEOMETRY_TYPES)
def test_m5_a_step3_dropped_wheel_still_holds_its_floor(type_):
    # M5, C317: step 3's drop takes away the wheel's geometry, not its floor, and its
    # cause still counts.
    van = KeptVehicle(
        1, "not_visible", ((2, "rim_quarter"),), wheels_hidden=False, vehicle_type=type_
    )
    half_knee_floor = Reading("half_knee", floor=True)
    kept = Kept(vehicles=(van,), people=())
    m = measure_boxes(
        kept, step3_drops={2: "no_water_contact"}, geometry={2: KNEE_GEOMETRY}
    )
    assert m.references == [
        Reference("wheel", 2, "rim_quarter", half_knee_floor, decides=False)
    ]
    assert dict(m.drops) == {"no_water_contact": 1, "vehicle_no_reading": 1}
    assert m.causes == {2: "no_water_contact", 1: "vehicle_no_reading"}
    assert m.readings == {2: KeptReading(half_knee_floor, "landmark", None)}


@pytest.mark.parametrize("type_", GEOMETRY_TYPES)
def test_m5_an_unseen_wheel_holds_nothing(type_):
    # not_visible has no Table 8 row, so it gives no floor (M5).
    van = KeptVehicle(
        1, "not_visible", ((2, "not_visible"),), wheels_hidden=True, vehicle_type=type_
    )
    assert measured(van) == ([], {"vehicle_no_reading": 1})
    assert measure_boxes(Kept(vehicles=(van,), people=())).readings == {}


@pytest.mark.parametrize("type_", sorted(READING_TYPES))
@pytest.mark.parametrize("mark", WHEEL_MARKS)
def test_m5_leaves_sedans_and_suvs_as_they_were(type_, mark):
    # M5 is for types kept for geometry. A sedan's or SUV's landmark row still decides
    # (C45), and step 3's drop leaves it as it was, not as a floor (C317).
    car = KeptVehicle(
        1,
        "not_visible",
        ((2, mark),),
        wheels_hidden=mark in HIDDEN_WHEEL,
        vehicle_type=type_,
    )
    row = WHEEL_ROWS[mark]
    assert measured(car) == ([Reference("wheel", 2, mark, row)], {})
    assert measured(car, step3_drops={2: "no_water_contact"}) == (
        [Reference("wheel", 2, mark, row, decides=False)],
        {"no_water_contact": 1, "vehicle_no_reading": 1},
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
    # The same holds for C53: G4 drops wheel 3, and the body sits below covered
    # wheel 2.
    low_body = KeptVehicle(
        1, "door_sill", ((2, "wheel_covered"), (3, "rim_quarter")), wheels_hidden=False
    )
    assert measured(low_body, geometry={3: chest}) == (
        [],
        {"vehicle_body_below_covered_wheel": 1, "wheel_vehicle_dropped": 2},
    )


def test_measure_boxes_keeps_each_box():
    # C328: measure_boxes also names each box's cause, counted as measure counts it,
    # and the reading each box gives, so the evidence record measures nothing itself.
    sedan = KeptVehicle(
        1, "not_visible", ((2, "hub"), (3, "tire_only")), wheels_hidden=False
    )
    kept = Kept(vehicles=(sedan,), people=())
    m = measure_boxes(kept)
    assert m.causes == {
        1: "vehicle_wheels_disagree",
        2: "wheel_vehicle_dropped",
        3: "wheel_vehicle_dropped",
    }
    assert m.readings == {}  # a vehicle C43 drops gives nothing (C317)
    assert (m.references, m.drops) == measure(kept)
    assert dict(m.drops) == {"vehicle_wheels_disagree": 1, "wheel_vehicle_dropped": 2}
    lone = Kept(
        vehicles=(KeptVehicle(1, "not_visible", ((2, "hub"),), wheels_hidden=False),),
        people=(),
    )
    m = measure_boxes(lone)
    assert m.readings[2].reading.level == "half_tire"
    assert m.readings == {2: KeptReading(WHEEL_ROWS["hub"], "landmark", None)}
    assert m.causes == {}
    assert (m.references, m.drops) == measure(lone)
    # G4's reading is the one kept, and G4's drop gives none.
    m = measure_boxes(lone, geometry={2: KNEE_GEOMETRY})
    assert m.readings == {2: KeptReading(KNEE, "geometry", (13.47, 13.47))}
    shallow = GeometryReading(3.2, 4.1, "below_gutter")
    m = measure_boxes(lone, geometry={2: shallow})
    assert m.readings == {}
    assert m.causes == {2: "wheel_methods_disagree", 1: "vehicle_no_reading"}
    # A reading step 3 dropped stays beside its cause (C317). A body that step 3
    # dropped leaves its vehicle with no reading too: both count, and the box keeps
    # its first cause.
    hidden = KeptVehicle(1, "window", ((2, "not_visible"),), wheels_hidden=True)
    m = measure_boxes(
        Kept(vehicles=(hidden,), people=(KeptPerson(3, "knee"),)),
        step3_drops={1: "ragged_waterline", 3: "no_water_contact"},
    )
    assert m.causes == {1: "ragged_waterline", 3: "no_water_contact"}
    assert dict(m.drops) == {
        "ragged_waterline": 1,
        "vehicle_no_reading": 1,
        "no_water_contact": 1,
    }
    assert m.readings == {
        1: KeptReading(TIRE_FLOOR, "landmark", None),
        3: KeptReading(KNEE, "landmark", None),
    }
    # R147: a geometry-only type's covered wheel holds a floor that can't decide, and
    # its geometry reading, which can, is the one kept.
    van = KeptVehicle(
        1,
        "not_visible",
        ((2, "wheel_covered"),),
        wheels_hidden=True,
        vehicle_type="van",
    )
    m = measure_boxes(Kept(vehicles=(van,), people=()))
    assert m.readings == {2: KeptReading(TIRE_FLOOR, "landmark", None)}
    m = measure_boxes(Kept(vehicles=(van,), people=()), geometry={2: KNEE_GEOMETRY})
    assert m.readings == {2: KeptReading(KNEE, "geometry", (13.47, 13.47))}
