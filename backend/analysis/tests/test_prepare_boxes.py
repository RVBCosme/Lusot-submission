"""Tests for step 4.1: SAM's boxes before Muse Spark numbers them (C69, C70).

Every rule here reads SAM's boxes alone: linking (C55), the 40 px rule (C56) and the
caps of 6 vehicles and 6 people.
"""

from collections import Counter

import pytest
from fakes import around, sam_results

from lusot_analysis.meta_client import SAM_PHRASES
from lusot_analysis.pipeline.references import Prepared, prepare_boxes
from lusot_analysis.tuning import START


def ids(prepared: Prepared, phrase: str) -> list[int]:
    """The SAM ids of a phrase's kept instances, in their order."""
    return [inst.id for inst in prepared.sam[phrase].instances]


def test_limits_are_the_spec_values():
    assert (START.min_wheel_side_px, START.max_vehicles, START.max_people) == (40, 6, 6)


def test_small_and_unlinked_wheels_are_dropped_before_numbering():
    sam = sam_results(
        {
            "vehicle": [(100, 100, 600, 400)],
            "wheel": [
                around(150, 300, 39.9, 30),  # a longer side of 39.9 px
                around(220, 300, 30, 39.9),  # upright, a longer side of 39.9 px
                around(290, 300, 40.0, 30),  # a longer side of 40 px
                around(360, 300, 30, 40.0),
                around(450, 300, 45, 20),  # only 20 px tall, but 45 px wide (C56)
                around(620, 440),  # inside no vehicle
            ],
            "person": [(10, 10, 20, 20)],  # people get no size floor (spec §3.3)
        }
    )
    prepared = prepare_boxes(sam)
    assert ids(prepared, "wheel") == [2, 3, 4]
    assert ids(prepared, "person") == [0]
    assert prepared.drops == Counter(wheel_small=2, wheel_unlinked=1)


def test_small_linked_wheel_marks_its_vehicle():
    # C69: vehicle 0's small wheel is cut, but it shows water isn't hiding the
    # vehicle's wheels, so the mark later stops a body reading. Vehicle 1 lost no
    # wheel, so it isn't marked.
    sam = sam_results(
        {
            "vehicle": [(0, 100, 300, 300), (320, 100, 620, 300)],
            "wheel": [
                around(60, 250, 30, 30),  # vehicle 0, small
                around(200, 250, 60, 60),  # vehicle 0, large
                around(450, 250, 60, 60),  # vehicle 1, large
            ],
        }
    )
    prepared = prepare_boxes(sam)
    assert prepared.small_wheel_vehicles == frozenset({0})
    assert ids(prepared, "wheel") == [1, 2]
    assert prepared.wheel_vehicle == (0, 1)
    assert prepared.drops == Counter(wheel_small=1)


def test_the_fixed_order_decides_each_cause():
    # Vehicle 6 is the smallest of 7, so the cap cuts it. It overlaps vehicle 0.
    vehicles = [
        (0, 0, 100, 100),
        (110, 0, 210, 100),
        (220, 0, 320, 100),
        (330, 0, 430, 100),
        (440, 0, 540, 100),
        (0, 200, 100, 300),
        (80, 80, 120, 120),
    ]
    wheels = [
        # Inside vehicles 0 and 6: a wheel links among all of SAM's vehicles, before
        # the cap, so it stays unlinked.
        around(90, 90),
        # Small, and inside vehicle 6 alone: the 40 px rule runs before the cap.
        around(110, 110, 20, 20),
        # Small, and inside no vehicle: linking runs before the 40 px rule.
        around(600, 400, 20, 20),
    ]
    prepared = prepare_boxes(sam_results({"vehicle": vehicles, "wheel": wheels}))
    assert prepared.drops == Counter(wheel_unlinked=2, wheel_small=1, vehicle_cap=1)
    assert ids(prepared, "vehicle") == [0, 1, 2, 3, 4, 5]
    assert prepared.small_wheel_vehicles == frozenset()  # vehicle 6 was cut


def test_caps_keep_the_six_largest():
    # Vehicle boxes 1 px tall and 1 to 8 px wide, so their areas are 1 to 8, out of
    # SAM's order. A 40 px wheel's centre sits in the smallest: linking reads only
    # the centre (C55).
    areas = [3, 8, 1, 6, 2, 7, 5, 4]
    vehicles = [(60 * n + 20, 200, 60 * n + 20 + a, 201) for n, a in enumerate(areas)]
    heights = [40, 10, 70, 30, 60, 20, 50]
    people = [(40 * n + 20, 300, 40 * n + 30, 300 + h) for n, h in enumerate(heights)]
    sam = sam_results(
        {"vehicle": vehicles, "wheel": [around(140.5, 200.5)], "person": people}
    )
    prepared = prepare_boxes(sam)
    assert ids(prepared, "vehicle") == [0, 1, 3, 5, 6, 7]  # areas 3, 8, 6, 7, 5, 4
    assert ids(prepared, "wheel") == []
    assert prepared.wheel_vehicle == ()
    assert ids(prepared, "person") == [0, 2, 3, 4, 5, 6]  # the 10 px tall one is cut
    assert prepared.drops == Counter(vehicle_cap=2, wheel_cap=1, person_cap=1)
    assert len(sam["vehicle"].instances) == 8  # SAM's own results are never changed


@pytest.mark.parametrize(
    ("phrase", "cause"), [("vehicle", "vehicle_cap"), ("person", "person_cap")]
)
def test_cap_ties_keep_sam_order(phrase, cause):
    equal = [(80 * n, 100, 80 * n + 50, 200) for n in range(7)]
    prepared = prepare_boxes(sam_results({phrase: equal}))
    assert ids(prepared, phrase) == [0, 1, 2, 3, 4, 5]
    assert prepared.drops == Counter({cause: 1})


def test_kept_wheels_point_at_their_kept_vehicle():
    # Vehicle 1 is the smallest of 7, so the cap cuts it, and every later vehicle
    # moves up one position. The wheels come in another order than their vehicles,
    # and the last one is small.
    vehicles = [(90 * n, 100, 90 * n + 80, 200) for n in range(7)]
    vehicles[1] = (90, 100, 130, 140)
    own = [6, 0, 3, 1, 5, 6]  # each wheel's vehicle
    wheels = [
        around(580, 180),
        around(40, 180),
        around(310, 180),
        around(110, 120),
        around(490, 180),
        around(560, 130, 20, 20),
    ]
    prepared = prepare_boxes(sam_results({"vehicle": vehicles, "wheel": wheels}))
    assert ids(prepared, "vehicle") == [0, 2, 3, 4, 5, 6]
    assert ids(prepared, "wheel") == [0, 1, 2, 4]  # wheel 3 went with vehicle 1
    assert prepared.wheel_vehicle == (5, 0, 2, 4)
    kept = prepared.sam["vehicle"].instances
    assert [kept[k].id for k in prepared.wheel_vehicle] == [
        own[wheel] for wheel in ids(prepared, "wheel")
    ]
    assert prepared.small_wheel_vehicles == frozenset({5})  # vehicle 6's position
    assert prepared.drops == Counter(vehicle_cap=1, wheel_cap=1, wheel_small=1)


def test_a_crowded_street_stays_within_the_caps():
    # 40 vehicles in an 8 x 5 grid, each wider than the one before. Each has a wheel
    # at its centre: 30 px on the first 10, 40 px on the rest. The last 10 have a
    # second 40 px wheel. 10 more wheels sit between rows 0 and 1, inside no
    # vehicle. The 30 people are each taller than the one before.
    vehicles, wheels = [], []
    for n in range(40):
        x0, y0 = 80 * (n % 8) + 2, 96 * (n // 8) + 2
        vehicles.append((x0, y0, x0 + 36 + n, y0 + 80))
        side = 30 if n < 10 else 40
        wheels.append(around(x0 + 18 + n / 2, y0 + 40, side, side))
    wheels += [around(x0 + 20, y0 + 40) for x0, y0, _, _ in vehicles[30:]]
    wheels += [around(40 + 60 * k, 89) for k in range(10)]
    people = [(20 * n, 400, 20 * n + 15, 420 + n) for n in range(30)]
    sam = sam_results({"vehicle": vehicles, "wheel": wheels, "person": people})
    prepared = prepare_boxes(sam)
    assert ids(prepared, "vehicle") == list(range(34, 40))
    assert ids(prepared, "person") == list(range(24, 30))
    # The kept vehicles' first wheels, then their second ones
    assert ids(prepared, "wheel") == list(range(34, 40)) + list(range(44, 50))
    assert prepared.wheel_vehicle == (0, 1, 2, 3, 4, 5) * 2
    assert prepared.drops == Counter(
        vehicle_cap=34, person_cap=24, wheel_small=10, wheel_cap=28, wheel_unlinked=10
    )
    kept = sum(len(prepared.sam[p].instances) for p in ("vehicle", "wheel", "person"))
    assert kept + prepared.drops.total() == 40 + 60 + 30  # every cut is counted


def test_other_phrases_pass_through():
    sam = sam_results(
        {
            "floodwater": [(0, 300, 640, 480)],
            "wheel": [around(150, 260)],
            "wheel rim": [(135, 245, 165, 275)],
            "person": [(400, 40, 440, 200)],
            "vehicle": [(100, 100, 300, 280)],
            "face": [(410, 50, 430, 70)],
            "license plate": [(200, 250, 240, 262)],
        }
    )
    prepared = prepare_boxes(sam)
    for phrase in ("floodwater", "wheel rim", "face", "license plate"):
        assert prepared.sam[phrase] is sam[phrase]
    assert prepared.sam.keys() == set(SAM_PHRASES)
    # The cut results keep SAM's phrase, timing and raw text.
    for phrase in ("vehicle", "wheel", "person"):
        cut, given = prepared.sam[phrase], sam[phrase]
        assert (cut.phrase, cut.elapsed_s, cut.raw) == (
            given.phrase,
            given.elapsed_s,
            given.raw,
        )
        assert ids(prepared, phrase) == [0]
    assert not prepared.drops  # nothing was cut, so no cause is logged, even at 0


def test_missing_phrases_count_as_no_instances():
    assert prepare_boxes({}) == Prepared({}, (), frozenset(), Counter())
    # Wheels with no vehicle phrase link to nothing.
    sam = sam_results({"wheel": [around(100, 100)]})
    del sam["vehicle"]
    prepared = prepare_boxes(sam)
    assert "vehicle" not in prepared.sam
    assert ids(prepared, "wheel") == []
    assert prepared.drops == Counter(wheel_unlinked=1)
