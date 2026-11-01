"""Tests for step 4 after numbering: box ids, and the gate on Muse Spark's answer.

The gate reads only the answer's top level, its waterlines and SAM's water mask, in
spec §3.2 step 4.5's order (C51, C52).
"""

from collections import Counter

import pytest
from fakes import answer, around, instance, person, sam_results, vehicle, wheel

from lusot_analysis.annotate import number_boxes
from lusot_analysis.meta_client import SamResult
from lusot_analysis.pipeline.references import (
    Layout,
    gate,
    instances_by_id,
    layout,
    prepare_boxes,
    water_found,
)
from lusot_analysis.pipeline.types import Outcome

PHOTO_UNUSABLE = Outcome.refused("photo_unusable")
WATER_UNSURE = Outcome.refused("water_unsure")
NO_WATER_FOUND = Outcome.refused("no_water_found")


def test_layout_maps_positions_to_ids():
    # Vehicle A (position 0) and B (position 1). In SAM's order, the wheels are on B,
    # on B but small, on A and on B, so the small one is cut and marks B.
    sam = sam_results(
        {
            "vehicle": [(20, 100, 300, 300), (320, 100, 620, 300)],
            "wheel": [
                around(400, 260, 60, 60),
                around(480, 270, 30, 30),
                around(100, 260, 60, 60),
                around(560, 260, 60, 60),
            ],
            "person": [(300, 20, 320, 90)],
        }
    )
    prepared = prepare_boxes(sam)
    assert prepared.wheel_vehicle == (1, 0, 1)
    assert prepared.small_wheel_vehicles == {1}
    assert prepared.drops == Counter(wheel_small=1)
    boxes = number_boxes(prepared.sam)
    assert [box.kind for box in boxes] == ["vehicle"] * 2 + ["wheel"] * 3 + ["person"]
    assert layout(prepared, boxes) == Layout(
        boxes=tuple(boxes),
        wheel_vehicle={3: 2, 4: 1, 5: 2},
        small_wheel_vehicles=frozenset({2}),
    )


def test_instances_by_id_follows_the_numbering():
    # Each box id names its own SAM instance. SAM's second wheel is small, so it is
    # cut before numbering and has no id; its third becomes box 3 (C69).
    sam = sam_results(
        {
            "vehicle": [(20, 100, 300, 300)],
            "wheel": [
                around(100, 260, 60, 60),
                around(160, 270, 30, 30),
                around(220, 260, 60, 60),
            ],
            "person": [(300, 20, 320, 90)],
        }
    )
    prepared = prepare_boxes(sam)
    instances = instances_by_id(prepared, layout(prepared, number_boxes(prepared.sam)))
    wheels = sam["wheel"].instances
    expected = [
        *sam["vehicle"].instances,
        wheels[0],
        wheels[2],
        *sam["person"].instances,
    ]
    assert list(instances) == [1, 2, 3, 4]
    assert all(instances[i] is inst for i, inst in enumerate(expected, start=1))


def no_water(*, vehicles=(), wheels=(), people=()) -> dict:
    """A no on standing water, with every kind at its lowest mark or not_visible.

    The items given are added to those.
    """
    return answer(
        standing_water="no",
        vehicles=[vehicle(1, body="below_bumper"), vehicle(2), *vehicles],
        wheels=[wheel(3, "tire_only"), wheel(4, "not_visible"), *wheels],
        people=[person(5, "ankle"), person(6, "not_visible"), *people],
    )


@pytest.mark.parametrize(
    ("given", "has_water", "expected"),
    [
        pytest.param(
            answer(photo_usable="no", standing_water="yes"),
            True,
            PHOTO_UNUSABLE,
            id="unusable-water-yes",
        ),
        pytest.param(
            answer(photo_usable="no", standing_water="no"),
            False,
            PHOTO_UNUSABLE,
            id="unusable-water-no",
        ),
        pytest.param(
            answer(photo_usable="no", standing_water="unsure"),
            False,
            PHOTO_UNUSABLE,
            id="unusable-water-unsure",
        ),
        pytest.param(
            answer(standing_water="unsure"), False, WATER_UNSURE, id="water-unsure"
        ),
        pytest.param(no_water(), False, Outcome.no_flood(), id="no-at-lowest-marks"),
        pytest.param(
            answer(standing_water="no"), False, Outcome.no_flood(), id="no-and-no-items"
        ),
        pytest.param(
            no_water(wheels=[wheel(7, "rim_quarter")]),
            False,
            WATER_UNSURE,
            id="no-but-a-wheel-at-rim-quarter",
        ),
        pytest.param(
            no_water(wheels=[wheel(7, "wheel_covered")]),
            False,
            WATER_UNSURE,
            id="no-but-a-wheel-covered",
        ),
        pytest.param(
            no_water(people=[person(7, "mid_shin")]),
            False,
            WATER_UNSURE,
            id="no-but-a-person-at-mid-shin",
        ),
        pytest.param(
            no_water(vehicles=[vehicle(7, body="bumper")]),
            False,
            WATER_UNSURE,
            id="no-but-a-body-at-bumper",
        ),
        pytest.param(
            answer(
                standing_water="no",
                vehicles=[vehicle(1)],
                wheels=[wheel(2, "not_visible")],
                people=[person(3, "not_visible")],
            ),
            True,
            Outcome.no_flood(),
            id="the-mask-never-overrides-a-clear-no",
        ),
        pytest.param(answer(), False, NO_WATER_FOUND, id="yes-without-water"),
        pytest.param(answer(), True, None, id="yes-with-water-goes-on"),
    ],
)
def test_gate_order(given, has_water, expected):
    assert gate(given, has_water=has_water) == expected


@pytest.mark.parametrize(
    "items",
    [
        pytest.param(
            {"vehicles": [vehicle(1, type="bus_truck", moving="yes", body="window")]},
            id="a-moving-bus-at-the-window",
        ),
        pytest.param(
            {
                "vehicles": [vehicle(1, type="bus_truck", moving="yes")],
                "wheels": [wheel(2, "hub")],
            },
            id="a-wheel-of-a-moving-bus",
        ),
        pytest.param(
            {"people": [person(3, "knee", adult="no", standing_still="no")]},
            id="a-wading-child",
        ),
    ],
)
def test_contradiction_counts_every_answered_item(items):
    # C52: an item the later drops would remove still contradicts the no.
    assert gate(answer(standing_water="no", **items), has_water=False) == WATER_UNSURE


def floodwater(*instances) -> SamResult:
    return SamResult("floodwater", list(instances), elapsed_s=0.5, raw="")


def test_water_found_ignores_empty_masks():
    # Review Focus 5: SAM can send instances whose masks hold no pixel.
    nothing = (0, 0, 0, 0)  # an all-False mask
    empty = [
        instance(0, (0, 300, 640, 480), mask_xyxy=nothing),
        instance(1, (0, 0, 100, 100), mask_xyxy=nothing),
    ]
    assert water_found(floodwater(*empty)) is False
    pixel = instance(2, (0, 300, 640, 480), mask_xyxy=(10, 400, 11, 401))
    assert int(pixel.mask.sum()) == 1
    assert water_found(floodwater(pixel)) is True
    assert water_found(floodwater(*empty, pixel)) is True
    assert water_found(floodwater()) is False


@pytest.mark.parametrize(
    ("share", "share_max", "expected"),
    [
        pytest.param(
            0.30, 0.25, WATER_UNSURE, id="water-past-the-share-unsettles-a-no"
        ),
        pytest.param(0.25, 0.25, Outcome.no_flood(), id="at-the-share-the-no-stands"),
        pytest.param(1.0, 1.0, Outcome.no_flood(), id="off-at-start"),
    ],
)
def test_a_wide_water_mask_unsettles_a_no(share, share_max, expected):
    # C93: when SAM's water covers more than no_flood_share_max of the image's lower
    # half, a "no" on standing water can't be trusted, so the photo is refused.
    given = answer(standing_water="no")
    assert (
        gate(given, has_water=True, water_share=share, no_flood_share_max=share_max)
        == expected
    )


def test_the_water_share_never_changes_a_yes():
    given = answer()
    assert gate(given, has_water=True, water_share=1.0, no_flood_share_max=0.0) is None
