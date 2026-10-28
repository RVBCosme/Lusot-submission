"""Tests for the level scale and Table 8's reading rules (eval/rules.md §1 and §6)."""

import subprocess
import sys

import pytest

from lusot_analysis.rules import (
    ABOVE_LOWEST_MARK,
    BODY_AT_OR_BELOW_SILL,
    BODY_ROWS,
    HIDDEN_WHEEL,
    LEVELS,
    PASSABILITY,
    PEOPLE_ROWS,
    READING_TYPES,
    WHEEL_ROWS,
    Reading,
    disagree,
    level_index,
)


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
