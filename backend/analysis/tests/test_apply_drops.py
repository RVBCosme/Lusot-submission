"""Tests for step 4.6: the drops that need Muse Spark's answer (spec §3.3).

apply_drops takes the answer after check_ids_per_item, so each entry names a numbered
box of its own kind, once. A numbered box with no entry is unanswered (C76).
"""

from collections import Counter
from collections.abc import Iterable, Mapping

import pytest
from fakes import answer, person, vehicle, wheel

from lusot_analysis.annotate import NumberedBox
from lusot_analysis.pipeline.references import (
    Kept,
    KeptPerson,
    KeptVehicle,
    Layout,
    apply_drops,
)


def numbered(
    *,
    vehicles: Iterable[int] = (),
    wheels: Mapping[int, int] | None = None,
    people: Iterable[int] = (),
    small: Iterable[int] = (),
) -> Layout:
    """A Layout with these box ids, its boxes in id order as number_boxes gives them.

    `wheels` maps each wheel's id to its vehicle's, in the order given. `small` names
    the vehicles that lost a linked wheel to the 40 px rule. apply_drops never reads a
    box's pixels, so every box has the same outline.
    """
    wheels = wheels or {}
    kinds = (
        dict.fromkeys(vehicles, "vehicle")
        | dict.fromkeys(wheels, "wheel")
        | dict.fromkeys(people, "person")
    )
    return Layout(
        boxes=tuple(NumberedBox(i, kinds[i], (0, 0, 10, 10)) for i in sorted(kinds)),
        wheel_vehicle=dict(wheels),
        small_wheel_vehicles=frozenset(small),
    )


@pytest.mark.parametrize(
    ("moving", "type_"),
    [
        pytest.param("yes", "sedan_hatch", id="moving"),
        pytest.param("unsure", "sedan_hatch", id="unsure"),
        # A drop counts once, under its first cause: moving comes before the type.
        pytest.param("yes", "bus_truck", id="a-moving-bus"),
    ],
)
def test_moving_vehicles_are_dropped_with_their_wheels(moving, type_):
    # W1: unsure counts as moving. Vehicle 2 stands still, so it keeps its wheel.
    given = answer(
        vehicles=[vehicle(1, type=type_, moving=moving), vehicle(2)],
        wheels=[wheel(3, "hub"), wheel(4, "rim_top"), wheel(5, "rim_quarter")],
    )
    boxes = numbered(vehicles=[1, 2], wheels={3: 1, 4: 1, 5: 2})
    kept, drops = apply_drops(given, boxes)
    assert kept == Kept(
        vehicles=(
            KeptVehicle(2, "not_visible", ((5, "rim_quarter"),), wheels_hidden=False),
        ),
        people=(),
    )
    assert drops == Counter(vehicle_moving=1, wheel_vehicle_dropped=2)


@pytest.mark.parametrize(
    "type_",
    ["pickup", "van", "jeepney", "tricycle", "motorcycle", "bus_truck", "unknown"],
)
def test_only_sedans_and_suvs_are_read(type_):
    # C45: Table 8's wheel rows are for these two body types. Vehicle 1's wheel goes
    # with it.
    given = answer(
        vehicles=[
            vehicle(1, type=type_),
            vehicle(2, type="sedan_hatch"),
            vehicle(3, type="suv_mpv"),
        ],
        wheels=[wheel(4, "hub"), wheel(5, "hub")],
    )
    kept, drops = apply_drops(given, numbered(vehicles=[1, 2, 3], wheels={4: 1, 5: 2}))
    assert kept == Kept(
        vehicles=(
            KeptVehicle(2, "not_visible", ((5, "hub"),), wheels_hidden=False),
            KeptVehicle(3, "not_visible", (), wheels_hidden=True),
        ),
        people=(),
    )
    assert drops == Counter(vehicle_type=1, wheel_vehicle_dropped=1)


@pytest.mark.parametrize("adult", ["no", "unsure"])
def test_children_and_unsure_adults_are_dropped(adult):
    # Person 1 stands and person 2 wades. Each is dropped as not an adult, never as
    # wading beside adult 3, who stands still: a drop counts under its first cause.
    given = answer(
        people=[
            person(1, "knee", adult=adult),
            person(2, "waist", adult=adult, standing_still="no"),
            person(3, "mid_shin"),
        ]
    )
    kept, drops = apply_drops(given, numbered(people=[1, 2, 3]))
    assert kept == Kept(vehicles=(), people=(KeptPerson(3, "mid_shin"),))
    assert drops == Counter(person_not_adult=2)


def test_wading_adults_yield_to_a_standing_adult():
    # D13, C57: unsure counts as wading. The standing adult has the last id, so it
    # also blocks the adults numbered before it.
    given = answer(
        people=[
            person(1, "waist", standing_still="no"),
            person(2, "chest", standing_still="unsure"),
            person(3, "knee"),
        ]
    )
    kept, drops = apply_drops(given, numbered(people=[1, 2, 3]))
    assert kept == Kept(vehicles=(), people=(KeptPerson(3, "knee"),))
    assert drops == Counter(person_wading=2)


def test_a_hidden_standing_adult_still_blocks_wading():
    # Rene's Q3: a standing adult whose legs are hidden, behind a car say, gives no
    # reading but still blocks. Step 5 then finds no reading in the kept person.
    given = answer(
        people=[person(1, "not_visible"), person(2, "waist", standing_still="no")]
    )
    kept, drops = apply_drops(given, numbered(people=[1, 2]))
    assert kept == Kept(vehicles=(), people=(KeptPerson(1, "not_visible"),))
    assert drops == Counter(person_wading=1)


def test_wading_adults_count_when_nobody_stands():
    given = answer(
        people=[
            person(1, "waist", standing_still="no"),
            person(2, "mid_thigh", standing_still="unsure"),
        ]
    )
    kept, drops = apply_drops(given, numbered(people=[1, 2]))
    assert kept == Kept(
        vehicles=(), people=(KeptPerson(1, "waist"), KeptPerson(2, "mid_thigh"))
    )
    assert not drops  # nothing was dropped, so no cause is logged, even at 0


@pytest.mark.parametrize("adult", ["no", "unsure"])
def test_a_standing_child_does_not_block_wading_adults(adult):
    # C76: only a person answered as an adult standing still blocks.
    given = answer(
        people=[person(1, "knee", adult=adult), person(2, "waist", standing_still="no")]
    )
    kept, drops = apply_drops(given, numbered(people=[1, 2]))
    assert kept == Kept(vehicles=(), people=(KeptPerson(2, "waist"),))
    assert drops == Counter(person_not_adult=1)


@pytest.mark.parametrize(
    ("waterlines", "small", "hidden"),
    [
        pytest.param(("wheel_covered", "not_visible"), False, True, id="all-hidden"),
        pytest.param(("rim_top",), False, False, id="one-wheel-at-rim-top"),
        pytest.param(
            ("wheel_covered", "rim_top"), False, False, id="rim-top-beside-covered"
        ),
        pytest.param((), False, True, id="no-linked-wheel"),
        # C69: a linked wheel cut by the 40 px rule shows water isn't hiding them.
        pytest.param(
            ("not_visible", "not_visible"), True, False, id="lost-a-small-wheel"
        ),
        # The commonest C69 case: a far car whose only linked wheel was cut, so none
        # is numbered. Its window-deep body would otherwise give a tire floor.
        pytest.param((), True, False, id="lost-its-only-wheel"),
    ],
)
def test_wheels_hidden(waterlines, small, hidden):
    # C53: the body reads only when the wheels are hidden. apply_drops passes the
    # body waterline through unread.
    ids = range(2, 2 + len(waterlines))
    given = answer(
        vehicles=[vehicle(1, body="window")],
        wheels=[wheel(i, line) for i, line in zip(ids, waterlines, strict=True)],
    )
    boxes = numbered(
        vehicles=[1], wheels=dict.fromkeys(ids, 1), small=[1] if small else []
    )
    kept, drops = apply_drops(given, boxes)
    wheels = tuple(zip(ids, waterlines, strict=True))
    assert kept == Kept(
        vehicles=(KeptVehicle(1, "window", wheels, wheels_hidden=hidden),), people=()
    )
    assert not drops


@pytest.mark.parametrize("wake", [True, False])
def test_wake_visible_changes_nothing(wake):
    # C63: Table 5 uses a wake to lower confidence, and 3a has no confidence output.
    # So both values give this one result.
    given = answer(
        vehicles=[vehicle(1, wake=wake), vehicle(2, moving="unsure", wake=wake)],
        wheels=[wheel(3, "rim_top"), wheel(4, "hub")],
    )
    kept, drops = apply_drops(given, numbered(vehicles=[1, 2], wheels={3: 1, 4: 2}))
    assert kept == Kept(
        vehicles=(
            KeptVehicle(1, "not_visible", ((3, "rim_top"),), wheels_hidden=False),
        ),
        people=(),
    )
    assert drops == Counter(vehicle_moving=1, wheel_vehicle_dropped=1)


def test_unanswered_boxes_give_no_reading():
    # Review Focus 1 (C76). Muse Spark left out vehicle 1 and its wheel 3, wheel 4 of
    # vehicle 2, and person 6.
    boxes = numbered(vehicles=[1, 2], wheels={3: 1, 4: 2, 5: 2}, people=[6, 7])
    given = answer(
        vehicles=[vehicle(2)],
        wheels=[wheel(5, "not_visible")],
        people=[person(7, "waist", standing_still="no")],
    )
    kept, drops = apply_drops(given, boxes)
    assert kept == Kept(
        # Unanswered wheel 4 counts as visible, so vehicle 2 gets no body reading.
        vehicles=(
            KeptVehicle(2, "not_visible", ((5, "not_visible"),), wheels_hidden=False),
        ),
        # Person 6 neither counts nor blocks wading adult 7.
        people=(KeptPerson(7, "waist"),),
    )
    assert drops == Counter(
        vehicle_unanswered=1,
        wheel_vehicle_dropped=1,
        wheel_unanswered=1,
        person_unanswered=1,
    )


def test_kept_items_come_in_id_order():
    # The answer's lists and the wheel links come in other orders than the ids. In
    # SAM's order, one vehicle's wheels can be numbered apart.
    boxes = numbered(vehicles=[1, 2], wheels={5: 1, 3: 2, 4: 1}, people=[6, 7])
    given = answer(
        vehicles=[vehicle(2), vehicle(1)],
        wheels=[wheel(5, "hub"), wheel(3, "rim_top"), wheel(4, "rim_quarter")],
        people=[person(7, "knee"), person(6, "mid_shin")],
    )
    kept, drops = apply_drops(given, boxes)
    assert kept == Kept(
        vehicles=(
            KeptVehicle(
                1, "not_visible", ((4, "rim_quarter"), (5, "hub")), wheels_hidden=False
            ),
            KeptVehicle(2, "not_visible", ((3, "rim_top"),), wheels_hidden=False),
        ),
        people=(KeptPerson(6, "mid_shin"), KeptPerson(7, "knee")),
    )
    assert not drops
