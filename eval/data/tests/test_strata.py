"""Tests for the passability class an alert states, which puts each event in the split's
deep group or its other group (C204, eval/rules.md §2)."""

import re
from pathlib import Path

import pytest
import strata

RULES = Path(__file__).resolve().parents[3] / "eval" / "rules.md"
HEADER = "| Passability as written | Class |"


def passability_table() -> dict[str, tuple[str, ...]]:
    """rules.md §2's passability table: each class and its variants, as written there.

    The table is found by its header row, since §2's level table comes first."""
    text = RULES.read_text(encoding="utf-8")
    lines = text[text.index("\n## 2.") : text.index("\n## 3.")].splitlines()
    table = {}
    for line in lines[lines.index(HEADER) + 2 :]:  # past the header and its |---|
        if not line.startswith("|"):
            break
        written, name = (cell.strip() for cell in line.strip().strip("|").split("|"))
        table[name] = tuple(variant.strip() for variant in written.split(","))
    return table


def test_rules_md_passability_table():
    """Each row's variants, with and without (types of) and (sedan), give the row's
    class, and strata holds the table as rules.md writes it."""
    table = passability_table()
    assert list(table) == ["PATV", "NPLV", "NPATV"]
    assert strata.PASSABILITY == table
    written = [variant for variants in table.values() for variant in variants]
    optional = {part for variant in written for part in re.findall(r"\(.*?\)", variant)}
    assert optional == {"(types of)", "(sedan)"}
    for name, variants in table.items():
        for variant in variants:
            kept = variant.replace("(", "").replace(")", "")
            dropped = " ".join(re.sub(r"\(.*?\)", "", variant).split())
            for form in (variant, kept, dropped):
                assert strata.class_of(form) == name, form


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("nplv", "NPLV"),
        (" NPLV. ", "NPLV"),
        ("Not Passable to Light Vehicles!", "NPLV"),
        ("not-passable to all types of vehicles", "NPATV"),
        ("PASSABLE TO ALL VEHICLES", "PATV"),
        ("Not passable to motorcycles and cars (Sedan)", "NPLV"),
        ("N.P.L.V.", None),
        ("NPLV PATV", None),
        ("NPLV (knee deep)", None),
        ("not passable", None),
        ("passable to all types of vehicle", None),
    ],
)
def test_class_of_needs_a_whole_variant(text, name):
    """Case and punctuation don't count, but the folded text must be a whole variant."""
    assert strata.class_of(text) == name


@pytest.mark.parametrize(
    ("passability", "deep"),
    [
        ("NPLV", True),
        ("NPATV", True),
        ("Not passable to light vehicles", True),
        ("not passable to all types of vehicles", True),
        ("PATV", False),
        ("passable to light vehicles", False),
        ("", False),
        ("closed to traffic", False),
        ("knee deep", False),  # a level label in the class column states no class
    ],
)
def test_deep_rows(passability, deep):
    assert strata.deep_row(passability) is deep
