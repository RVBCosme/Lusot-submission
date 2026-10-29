"""The passability class an alert states, which puts each event in one of the split's
two groups (C204).

The split draws deep events apart from the rest. An event is deep when one of its rows
states NPLV or NPATV in passability_raw, by eval/rules.md §2's passability table. MS2
reads that stated class only and maps no level label, since the harness maps every
label for scoring (C207). The tracker confirmed this reading at 5:15 PM on Oct 28.
"""

import re

import places

# eval/rules.md §2's passability table: each class and its variants, as written there.
# A part in brackets may be left out. test_strata ties the two.
PASSABILITY: dict[str, tuple[str, ...]] = {
    "PATV": (
        "PATV",
        "passable to all (types of) vehicles",
        "passable to light vehicles",
    ),
    "NPLV": (
        "NPLV",
        "not passable to light vehicles",
        "not passable to motorcycles and cars (sedan)",
    ),
    "NPATV": (
        "NPATV",
        "not passable to all (types of) vehicles",
        "not passable to any vehicle",
    ),
}
DEEP = ("NPLV", "NPATV")

# Each variant folded, with its part in brackets and without it, and the variant's class.
_CLASSES = {
    places.fold(form): name
    for name, variants in PASSABILITY.items()
    for variant in variants
    for form in (variant, re.sub(r"\(.*?\)", " ", variant))
}


def class_of(passability: str) -> str | None:
    """PATV, NPLV or NPATV when the folded text is one of the table's variants, whole,
    with or without its (types of) or (sedan); otherwise None, for a blank text too.

    Folding, as places.fold does it, lowers the case and makes punctuation spaces, then
    collapses the spaces, so "Not passable to light vehicles." is NPLV.
    """
    return _CLASSES.get(places.fold(passability))


def deep_row(passability_raw: str) -> bool:
    """True when the row's stated passability is NPLV or NPATV (C204)."""
    return class_of(passability_raw) in DEEP
