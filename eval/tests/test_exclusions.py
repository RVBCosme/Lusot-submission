"""Exclusions against rules §3 and §9 (C404, C408; MS6E-Q1, items 2, 6 to 8, 14)."""

from __future__ import annotations

import dataclasses
import itertools

import rules_md
from scoring.exclusions import REASONS, a_neg_exclusion, set_a_exclusion
from scoring.labels import map_level_label, map_passability
from scoring.rows import Facts

CLEAN = Facts("mmda", "no", "same_post", False, True, True)

# One trigger per reason, in REASONS order: the facts it changes and the other
# alerts it adds. Each changes only what it needs, so any two combine.
TRIGGERS = (
    ({"poster_kind": "other"}, ()),
    ({"label_in_image": "yes"}, ()),
    ({"match": "none"}, ()),
    ({}, ("(other words)",)),
    ({}, ("waist deep",)),
    ({"duplicate": True}, ()),
    ({"metro_manila": False}, ()),
    ({"decodes": False}, ()),
)


def exclusion(
    facts: Facts = CLEAN,
    label: str = "knee deep",
    passability: str = "NPLV",
    others: tuple[str, ...] = (),
) -> str | None:
    """set_a_exclusion on raw labels, mapped by rules §2 as the harness maps them."""
    return set_a_exclusion(
        facts,
        map_level_label(label),
        map_passability(passability),
        [map_level_label(raw) for raw in others],
    )


def triggered(*indexes: int) -> str | None:
    """The exclusion of a knee-deep NPLV photo with the given triggers applied."""
    changes: dict[str, object] = {}
    others: tuple[str, ...] = ()
    for index in indexes:
        fact_changes, extra = TRIGGERS[index]
        changes.update(fact_changes)
        others += extra
    return exclusion(dataclasses.replace(CLEAN, **changes), others=others)


def test_reasons_match_rules_md():
    section = rules_md.section(9).splitlines()
    bullets = [line[2:] for line in section if line.startswith("- ")]
    # Without the backticked parenthetical, (`label_in_image` = `yes`).
    assert tuple(bullet.split(" (`")[0] for bullet in bullets) == REASONS


def test_each_reason():
    assert exclusion() is None
    for index, reason in enumerate(REASONS):
        assert triggered(index) == reason, reason
    # A row that triggers reasons 2 and 6 gives 2.
    assert triggered(1, 5) == REASONS[1]
    # A city poster, a cropped label and a separate post all pass.
    for changes in (
        {"poster_kind": "city"},
        {"label_in_image": "cropped"},
        {"match": "separate_post"},
    ):
        assert exclusion(dataclasses.replace(CLEAN, **changes)) is None, changes


def test_the_first_reason_wins():
    for first, second in itertools.combinations(range(len(REASONS)), 2):
        assert triggered(first, second) == REASONS[first], (first, second)


def test_status_and_blank_labels():
    assert exclusion(label="subsided") == "no matching alert"
    assert exclusion(label="", passability="") == "unmapped label"
    # A blank depth beside a class phrase that maps to nothing gives no ground
    # truth either (MS6E-Q1, item 14).
    assert exclusion(label="", passability="closed") == "unmapped label"
    # An alert with only a class.
    assert exclusion(label="", passability="NPLV") is None
    # Beside a mapped level, an unmapped passability phrase leaves the photo out of
    # passability only (MS6E-Q1, item 2).
    assert exclusion(label="knee deep", passability="closed") is None


def test_other_alerts():
    cases = {
        "half-tire deep": None,  # one level apart
        "waist deep": "conflicting alerts",
        "subsided": None,  # a status is ignored
        "(other words)": "unmapped label",
        "": None,  # an alert that gave only a class
    }
    for other, expected in cases.items():
        assert exclusion(label="knee deep", others=(other,)) == expected, other


def test_a_neg_reasons():
    a_neg = Facts("other", "no", None, False, True, True)
    # poster_kind is ignored.
    assert a_neg_exclusion(a_neg) is None
    assert a_neg_exclusion(dataclasses.replace(a_neg, duplicate=True)) == REASONS[5]
    assert a_neg_exclusion(dataclasses.replace(a_neg, decodes=False)) == REASONS[7]
    both = dataclasses.replace(a_neg, duplicate=True, decodes=False)
    assert a_neg_exclusion(both) == REASONS[5]
    # Only those two count for A-neg (MS6E-Q1, item 6).
    others = dataclasses.replace(a_neg, label_in_image="yes", metro_manila=False)
    assert a_neg_exclusion(others) is None
