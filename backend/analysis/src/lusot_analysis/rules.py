"""The level scale and Table 8's reading rules (eval/rules.md §1 and §6, spec §3.3).

Muse Spark answers in these categories, and only code turns them into levels. The
tables are plain literals, so each line can be checked against the spec.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

# The 9 ordered levels: MMDA's 7 gauge levels plus below_gutter and above_chest.
LEVELS: tuple[str, ...] = (
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

# The passability class of each level (eval/rules.md §1).
PASSABILITY: Mapping[str, str] = {
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


def level_index(level: str) -> int:
    """The level's place on the scale, from 0 for below_gutter to 8 for above_chest."""
    if level not in LEVELS:
        raise ValueError(f"unknown level: {level!r}")
    return LEVELS.index(level)


@dataclass(frozen=True)
class Reading:
    """A level read from one landmark. A floor means "this level or deeper" (C54)."""

    level: str
    floor: bool


# Table 8's wheel rows, as written (G4). Only sedan_hatch and suv_mpv wheels are read
# (C45).
WHEEL_ROWS: Mapping[str, Reading | None] = {
    "tire_only": Reading("below_gutter", floor=False),
    "rim_quarter": Reading("half_knee", floor=False),
    "hub": Reading("half_tire", floor=False),
    "rim_three_quarters": Reading("knee", floor=False),
    "rim_top": Reading("tire", floor=False),
    "wheel_covered": Reading("tire", floor=True),
    "not_visible": None,
}

# Table 8's people rows, for adults (D13, C57).
PEOPLE_ROWS: Mapping[str, Reading | None] = {
    "ankle": Reading("below_gutter", floor=False),
    "mid_shin": Reading("half_knee", floor=False),
    "knee": Reading("knee", floor=False),
    "mid_thigh": Reading("tire", floor=False),
    "waist": Reading("waist", floor=False),
    "chest": Reading("chest", floor=False),
    "above_chest": Reading("above_chest", floor=False),
    "not_visible": None,
}

# The body waterline (C53). It is read only for a sedan_hatch or suv_mpv whose wheels
# are all hidden.
BODY_ROWS: Mapping[str, Reading | None] = {
    "mid_door": Reading("tire", floor=True),
    "window": Reading("tire", floor=True),
    "below_bumper": None,
    "bumper": None,
    "door_sill": None,
    "not_visible": None,
}

# A covered wheel beside a body waterline at one of these drops the vehicle (C53).
BODY_AT_OR_BELOW_SILL = frozenset({"below_bumper", "bumper", "door_sill"})

# A wheel answered at one of these counts as hidden (C53).
HIDDEN_WHEEL = frozenset({"wheel_covered", "not_visible"})

# The vehicle types whose wheels and body give readings (C45).
READING_TYPES = frozenset({"sedan_hatch", "suv_mpv"})

# The waterlines that put water above an item's lowest mark. A "no" on standing water
# counts only when no answered item sits at one of these (C52).
ABOVE_LOWEST_MARK: Mapping[str, frozenset[str]] = {
    "wheel": frozenset(WHEEL_ROWS) - {"tire_only", "not_visible"},
    "person": frozenset(PEOPLE_ROWS) - {"ankle", "not_visible"},
    "body": frozenset(BODY_ROWS) - {"below_bumper", "not_visible"},
}


def disagree(readings: Iterable[Reading]) -> bool:
    """True when an exact reading sits more than one level below the deepest (C54).

    A floor means "this level or deeper" (Rene's Q4, eval/rules.md §6 v0.6). It counts
    at its own level when finding the deepest, and it is never too shallow itself.
    """
    readings = tuple(readings)
    deepest = max((level_index(r.level) for r in readings), default=0)
    return any(deepest - level_index(r.level) > 1 for r in readings if not r.floor)
