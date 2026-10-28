"""The level scale against rules §1, and the rules version (C408)."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest
import rules_md
from scoring import RULES_VERSION
from scoring.scale import (
    CLASS_NAMES,
    CLASSES,
    LEVELS,
    NO_FLOOD_INDEX,
    UPPER_IN,
    level_for_inches,
    level_index,
)


def test_scale_matches_rules_md():
    rows = rules_md.tables(rules_md.section(1))[0]
    assert len(rows) == len(LEVELS) == len(UPPER_IN) == 9
    for i, (index, level, limit, cls) in enumerate(rows):
        assert int(index) == i
        assert level == LEVELS[i]
        bound = re.fullmatch(r"d (≤|>) ([0-9]+)", limit)
        assert bound, limit
        relation, number = bound.groups()
        if relation == "≤":
            assert UPPER_IN[i] == Decimal(number), level
        else:
            # Only the deepest level is open-ended, just past the level above it.
            assert i == len(LEVELS) - 1 and UPPER_IN[i] is None
            assert Decimal(number) == UPPER_IN[i - 1]
        assert cls == CLASSES[level], level
    assert list(CLASSES) == list(LEVELS)
    assert list(dict.fromkeys(row[3] for row in rows)) == list(CLASS_NAMES)


def test_level_for_inches():
    expected = {
        "0": "below_gutter",
        "5": "below_gutter",
        "5.01": "gutter",
        "8": "gutter",
        "13": "half_tire",
        "13.2": "knee",
        "26": "tire",
        "45": "chest",
        "45.1": "above_chest",
    }
    for depth, level in expected.items():
        assert level_for_inches(Decimal(depth)) == level, depth
    with pytest.raises(ValueError):
        level_for_inches(Decimal("-0.1"))


def test_level_index():
    assert level_index("knee") == 4
    with pytest.raises(ValueError):
        level_index("ankle")
    # "No flood seen" sits one step below the scale (C405).
    assert NO_FLOOD_INDEX == level_index("below_gutter") - 1


def test_rules_version_matches_rules_md():
    assert RULES_VERSION == rules_md.version()
