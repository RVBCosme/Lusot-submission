"""Rules §1: the 9 ordered levels, their upper limits in inches and their classes."""

from __future__ import annotations

from decimal import Decimal

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
# Each level's upper limit, in inches; above_chest is anything deeper than chest.
UPPER_IN: tuple[Decimal | None, ...] = (
    Decimal(5),
    Decimal(8),
    Decimal(10),
    Decimal(13),
    Decimal(19),
    Decimal(26),
    Decimal(37),
    Decimal(45),
    None,
)
CLASS_NAMES: tuple[str, ...] = ("PATV", "NPLV", "NPATV")
CLASSES: dict[str, str] = {
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
# "No flood seen" scores one step below below_gutter (C405).
NO_FLOOD_INDEX: int = -1


def level_index(level: str) -> int:
    """The level's place on the scale, 0 to 8. An unknown level raises ValueError."""
    return LEVELS.index(level)


def level_for_inches(depth: Decimal) -> str:
    """The shallowest level whose upper limit is at or above `depth`, so an
    in-between depth rounds deeper (rules §1). A depth below 0 raises ValueError."""
    if depth < 0:
        raise ValueError("a depth can't be below 0")
    for level, upper in zip(LEVELS, UPPER_IN):
        if upper is not None and depth <= upper:
            return level
    return LEVELS[-1]
