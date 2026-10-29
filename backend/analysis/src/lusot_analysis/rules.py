"""The level scale and Table 8's reading rules (eval/rules.md §1 and §6, spec §3.3).

Muse Spark answers in these categories, and only code turns them into levels. The
tables are plain literals, so each line can be checked against the spec. The tire codes
that geometry measures with are in the package's tire_codes.json (C304).
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib.resources import files

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


# Each level's upper limit in inches (eval/rules.md §1). above_chest is over 45 in.
_UPPER_LIMITS_IN: Mapping[str, float] = {
    "below_gutter": 5.0,
    "gutter": 8.0,
    "half_knee": 10.0,
    "half_tire": 13.0,
    "knee": 19.0,
    "tire": 26.0,
    "waist": 37.0,
    "chest": 45.0,
}


def level_for_inches(depth_in: float) -> str:
    """The shallowest level whose upper limit is at or above the depth (§1's rule).

    Every in-between depth rounds deeper. A depth of 0 or less, or one that isn't
    finite, raises ValueError.
    """
    if not math.isfinite(depth_in) or depth_in <= 0:
        raise ValueError(f"impossible depth: {depth_in!r}")
    for level, upper in _UPPER_LIMITS_IN.items():
        if depth_in <= upper:
            return level
    return "above_chest"


def round_out(depth_min: float, depth_max: float) -> tuple[float, float]:
    """The stored inches: the min rounded down and the max up, to 0.1 in (C308).

    Rounding to 6 places in tenths first keeps a float such as 8.299999999999999 at
    8.3. That can leave the max up to 5e-8 in below the depth, so when the rounded
    max's level is shallower than the depth's, it gains 0.1 in: a rebuild from the
    stored max never lands shallower (R135, M1). `depth_max` must be a depth
    level_for_inches accepts.
    """
    level = level_index(level_for_inches(depth_max))
    low = math.floor(round(depth_min * 10, 6))
    high = math.ceil(round(depth_max * 10, 6))
    if high <= 0 or level_index(level_for_inches(high / 10)) < level:
        high += 1
    return low / 10, high / 10


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


_TIRE_CODE = re.compile(r"^(\d{3})/(\d{2})R(\d{2})C?$", re.ASCII)  # \d is 0 to 9


@dataclass(frozen=True)
class TireCode:
    """A metric radial tire code, such as 175/65R14 (plan Table 7, C304)."""

    code: str
    width_mm: int
    aspect: int
    rim_in: int

    @classmethod
    def parse(cls, code: str) -> TireCode:
        """The code's width, aspect and rim size.

        Any other shape raises ValueError, a bias-ply size such as 7.50-16 too (R124).
        """
        match = _TIRE_CODE.fullmatch(code)
        if match is None:
            raise ValueError(f"not a metric radial tire code: {code!r}")
        width_mm, aspect, rim_in = (int(part) for part in match.groups())
        return cls(code, width_mm, aspect, rim_in)

    @property
    def radius_in(self) -> float:
        """The tire's radius in inches: half the rim, plus the sidewall."""
        return self.rim_in / 2 + self.width_mm * self.aspect / 100 / 25.4


def _load_tire_codes() -> tuple[str, dict[str, tuple[TireCode, ...]]]:
    """The data file's version, and each type's codes in the file's order.

    unknown runs every listed code once, in file order (C304).
    """
    text = files("lusot_analysis").joinpath("tire_codes.json").read_text("utf-8")
    data = json.loads(text)
    by_type = {
        vehicle_type: tuple(TireCode.parse(entry["code"]) for entry in entries)
        for vehicle_type, entries in data["types"].items()
    }
    every = dict.fromkeys(code for codes in by_type.values() for code in codes)
    by_type["unknown"] = tuple(every)
    return data["version"], by_type


# Read once, when the rules load.
TIRE_CODES_VERSION, _TIRE_CODES = _load_tire_codes()


def tire_codes(vehicle_type: str) -> tuple[TireCode, ...]:
    """The type's tire codes. A type with none, a pickup among them, gets () (C304)."""
    return _TIRE_CODES.get(vehicle_type, ())


# The types only geometry reads: they have tire codes, but Table 8's wheel rows don't
# cover them (C318).
GEOMETRY_ONLY_TYPES: frozenset[str] = frozenset(
    t for t, codes in _TIRE_CODES.items() if codes and t not in READING_TYPES
)
