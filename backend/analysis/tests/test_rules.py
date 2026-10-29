"""Tests for the level scale and Table 8's reading rules (eval/rules.md §1 and §6)."""

import json
import math
import subprocess
import sys
from importlib.resources import files

import pytest

from lusot_analysis.rules import (
    ABOVE_LOWEST_MARK,
    BODY_AT_OR_BELOW_SILL,
    BODY_ROWS,
    GEOMETRY_ONLY_TYPES,
    HIDDEN_WHEEL,
    LEVELS,
    PASSABILITY,
    PEOPLE_ROWS,
    READING_TYPES,
    TIRE_CODES_VERSION,
    WHEEL_ROWS,
    Reading,
    TireCode,
    disagree,
    level_for_inches,
    level_index,
    round_out,
    tire_codes,
)

SEDAN_CODES = ["175/65R14", "185/55R15", "185/60R15", "195/55R16"]
SUV_CODES = [
    "205/55R16",
    "205/55R17",
    "185/65R15",
    "195/60R16",
    "205/65R16",
    "205/60R17",
    "215/55R17",
]
VAN_CODES = ["215/70R16C"]


def exact(level: str) -> Reading:
    return Reading(level, False)


def floor(level: str) -> Reading:
    """This level or deeper (C54)."""
    return Reading(level, True)


def test_levels_are_the_nine_in_order():
    assert LEVELS == (
        "below_gutter",
        "gutter",
        "half_knee",
        "half_tire",
        "knee",
        "tire",
        "waist",
        "chest",
        "above_chest",
    )
    assert level_index("gutter") == 1
    assert level_index("knee") == 4
    with pytest.raises(ValueError):
        level_index("deep")


def test_passability_for_every_level():
    assert PASSABILITY == {
        "below_gutter": "PATV",
        "gutter": "PATV",
        "half_knee": "PATV",
        "half_tire": "NPLV",
        "knee": "NPLV",
        "tire": "NPATV",
        "waist": "NPATV",
        "chest": "NPATV",
        "above_chest": "NPATV",
    }


def test_wheel_rows_match_table_8():
    assert WHEEL_ROWS == {
        "tire_only": exact("below_gutter"),
        "rim_quarter": exact("half_knee"),
        "hub": exact("half_tire"),
        "rim_three_quarters": exact("knee"),
        "rim_top": exact("tire"),
        "wheel_covered": floor("tire"),
        "not_visible": None,
    }


def test_people_rows_match_table_8():
    assert PEOPLE_ROWS == {
        "ankle": exact("below_gutter"),
        "mid_shin": exact("half_knee"),
        "knee": exact("knee"),
        "mid_thigh": exact("tire"),
        "waist": exact("waist"),
        "chest": exact("chest"),
        "above_chest": exact("above_chest"),
        "not_visible": None,
    }


def test_body_rows_and_sets():
    assert BODY_ROWS == {
        "mid_door": floor("tire"),
        "window": floor("tire"),
        "below_bumper": None,
        "bumper": None,
        "door_sill": None,
        "not_visible": None,
    }
    assert BODY_AT_OR_BELOW_SILL == {"below_bumper", "bumper", "door_sill"}
    assert HIDDEN_WHEEL == {"wheel_covered", "not_visible"}
    assert READING_TYPES == {"sedan_hatch", "suv_mpv"}
    assert ABOVE_LOWEST_MARK == {
        "wheel": {
            "rim_quarter",
            "hub",
            "rim_three_quarters",
            "rim_top",
            "wheel_covered",
        },
        "person": {"mid_shin", "knee", "mid_thigh", "waist", "chest", "above_chest"},
        "body": {"bumper", "door_sill", "mid_door", "window"},
    }


@pytest.mark.parametrize(
    ("readings", "expected"),
    [
        pytest.param(
            [floor("tire"), exact("chest")], False, id="floor-and-deeper-chest"
        ),
        pytest.param([floor("tire"), exact("half_tire")], True, id="floor-and-2-below"),
        pytest.param([floor("tire"), exact("knee")], False, id="floor-and-1-below"),
        pytest.param([exact("knee"), exact("chest")], True, id="knee-and-chest"),
        pytest.param(
            [exact("below_gutter"), exact("half_knee")], True, id="the-gutter-gap"
        ),
        pytest.param([exact("knee"), exact("tire")], False, id="1-level-apart"),
        pytest.param(
            [floor("tire"), exact("above_chest")], False, id="floor-and-above-chest"
        ),
        pytest.param([exact("waist")], False, id="one-reading"),
        pytest.param([], False, id="no-reading"),
    ],
)
def test_disagree_follows_c54(readings, expected):
    assert disagree(readings) is expected
    assert disagree(iter(readings)) is expected  # any iterable, read once


@pytest.mark.parametrize(
    ("depth", "level"),
    [
        (0.1, "below_gutter"),
        (5.0, "below_gutter"),
        (5.01, "gutter"),
        (8.0, "gutter"),
        (8.01, "half_knee"),
        (10.0, "half_knee"),
        (13.0, "half_tire"),
        (13.01, "knee"),
        (19.0, "knee"),
        (26.0, "tire"),
        (37.0, "waist"),
        (45.0, "chest"),
        (45.01, "above_chest"),
    ],
)
def test_level_for_inches_follows_the_level_rule(depth, level):
    # The shallowest level whose upper limit is at or above the depth (eval/rules.md
    # §1), so every in-between depth rounds deeper.
    assert level_for_inches(depth) == level


@pytest.mark.parametrize("depth", [0.0, -1.0, math.nan, math.inf])
def test_level_for_inches_rejects_impossible_depths(depth):
    with pytest.raises(ValueError):
        level_for_inches(depth)


@pytest.mark.parametrize(
    ("depths", "stored"),
    [
        ((8.291619, 8.793869), (8.2, 8.8)),
        ((8.3, 8.3), (8.3, 8.3)),  # a tenth stays as it is
        ((7.0, 7.96), (7.0, 8.0)),
        ((0.05, 0.05), (0.0, 0.1)),
        # 5.0 alone would be below_gutter, where the depth is gutter (M1).
        ((5.00000001, 5.00000001), (5.0, 5.1)),
        # A positive depth that rounds to 0.0 would have no level at all.
        ((1e-9, 1e-9), (0.0, 0.1)),
    ],
)
def test_round_out(depths, stored):
    # C308: min down and max up, to 0.1 in.
    assert round_out(*depths) == stored


@pytest.mark.parametrize(
    "depth",
    [4.96, 5.0, 5.00000001, 7.96, 8.0, 12.95, 13.0, 13.00000001, 18.99, 44.99],
)
def test_a_rebuild_never_lands_shallower(depth):
    # C308: a level rebuilt from the stored max is the unrounded depth's level.
    assert level_for_inches(round_out(depth, depth)[1]) == level_for_inches(depth)


def test_tire_codes_match_the_spec():
    # Spec §4's table (C304), in its order. unknown runs every code, without repeats.
    assert [c.code for c in tire_codes("sedan_hatch")] == SEDAN_CODES
    assert [c.code for c in tire_codes("suv_mpv")] == SUV_CODES
    assert [c.code for c in tire_codes("van")] == VAN_CODES
    every = tire_codes("unknown")
    assert [c.code for c in every] == SEDAN_CODES + SUV_CODES + VAN_CODES
    assert len(every) == 12
    assert every == tuple(TireCode.parse(c.code) for c in every)
    for vehicle_type in ("pickup", "jeepney", "tricycle", "motorcycle", "bus_truck"):
        assert tire_codes(vehicle_type) == ()


def test_tire_sizes_match_table_7():
    assert TireCode.parse("175/65R14").radius_in == pytest.approx(11.4783, abs=1e-4)
    assert TireCode.parse("215/70R16C").radius_in == pytest.approx(13.9252, abs=1e-4)
    assert TireCode.parse("215/70R16C") == TireCode("215/70R16C", 215, 70, 16)
    diameters = {
        "sedan_hatch": (23.0, 24.4),
        "suv_mpv": (24.5, 26.7),
        "van": (27.9, 27.9),
        "unknown": (23.0, 27.9),
    }
    for vehicle_type, expected in diameters.items():
        sizes = [2 * c.radius_in for c in tire_codes(vehicle_type)]
        assert (round(min(sizes), 1), round(max(sizes), 1)) == expected
    for code in ("265/60R18X", "7.50-16", "175/65R14\n", "175/65 R14"):
        with pytest.raises(ValueError):
            TireCode.parse(code)


def test_every_code_names_its_source():
    # The data file as the package ships it, read the way rules.py reads it.
    text = files("lusot_analysis").joinpath("tire_codes.json").read_text("utf-8")
    data = json.loads(text)
    assert data["version"] == TIRE_CODES_VERSION == "tire-codes-v1"
    assert list(data["types"]) == ["sedan_hatch", "suv_mpv", "van"]
    for entries in data["types"].values():
        for entry in entries:
            assert set(entry) == {"code", "vehicle", "source"}
            assert entry["vehicle"].strip()
            assert entry["source"].strip()


def test_geometry_only_types():
    # The types with codes, less the ones Table 8's wheel rows read (C318).
    assert GEOMETRY_ONLY_TYPES == {"van", "unknown"}
    assert isinstance(GEOMETRY_ONLY_TYPES, frozenset)


def test_rules_load_without_the_meta_client():
    # R80: loading the rules never loads the Meta client or the OpenAI SDK.
    script = (
        "import lusot_analysis.rules, sys; "
        'print("lusot_analysis.meta_client" in sys.modules, "openai" in sys.modules)'
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False False"
