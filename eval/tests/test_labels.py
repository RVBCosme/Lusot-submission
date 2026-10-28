"""Label mapping against rules §2 (C404, C408, C420)."""

from __future__ import annotations

import re

import rules_md
from scoring.labels import (
    LABEL_WORDS,
    OTHER_WORDS,
    STATUS_WORDS,
    ClassLabel,
    LevelLabel,
    label_words_ok,
    map_level_label,
    map_passability,
)

# The two notes in §2's first column that aren't part of any label.
ANNOTATIONS = (" (off-scale)", " (over a person's head)")
UNIT_WORDS = {
    "in",
    "inch",
    "inches",
    "cm",
    "centimeter",
    "centimeters",
    "centimetre",
    "centimetres",
}
# Words real alerts write that v0.6's §2 doesn't list: "ankle" beside inches, and
# "head" as "lagpas tao" (MS6E-Q1, items 15 and 16).
ALERT_WORDS = {"ankle", "head"}
UNMAPPED = LevelLabel("unmapped", None)


def level_rows() -> list[list[str]]:
    return rules_md.tables(rules_md.section(2))[0]


def passability_rows() -> list[list[str]]:
    return rules_md.tables(rules_md.section(2))[1]


def without_annotations(cell: str) -> str:
    for annotation in ANNOTATIONS:
        cell = cell.replace(annotation, "")
    return cell


def level(name: str) -> LevelLabel:
    return LevelLabel("level", name)


def assert_levels(cases: dict[str, LevelLabel]) -> None:
    for raw, expected in cases.items():
        assert map_level_label(raw) == expected, raw


def test_label_table_matches_rules_md():
    rows = level_rows()
    assert len(rows) == 11
    for label, name in rows:
        # Without a trailing note such as "(off-scale)", and without the quotes.
        words = label.split(" (")[0].strip('"')
        assert map_level_label(words) == level(name), label


def test_listed_variants():
    assert_levels(
        {
            "half knee": level("half_knee"),
            "half-knee": level("half_knee"),
            "Half Gutter": level("below_gutter"),
            "gutter-deep": level("gutter"),
            "above gutter deep": level("half_knee"),
        }
    )


def test_words_beat_numbers():
    assert_levels(
        {
            'Gutter deep, 8"': level("gutter"),
            "knee deep (10 inches)": level("knee"),
        }
    )


def test_single_number():
    assert_levels(
        {
            '10"': level("half_knee"),
            '12"': level("half_tire"),
            "37 inches": level("waist"),
            "19 in": level("knee"),
        }
    )


def test_range_takes_its_upper_value():
    assert_levels(
        {
            "13-18 inches": level("knee"),
            "8 to 10 inches": level("half_knee"),
        }
    )


def test_centimetres():
    assert_levels(
        {
            "25 cm": level("half_knee"),  # 9.84 in
            "33 cm": level("half_tire"),  # 12.99 in
        }
    )


def test_label_spacing_case_and_units():
    assert_levels(
        {
            "Knee  Deep": level("knee"),
            "10”": level("half_knee"),
            "13 - 18 inches": level("knee"),
            "13–18 inches": level("knee"),
            "25 centimeters": level("half_knee"),
        }
    )


def test_bare_number_and_suffixes():
    assert_levels(
        {
            "25": UNMAPPED,  # a number with no unit maps to nothing (MS6E-Q1, item 11)
            "knee level": level("knee"),  # "level" and "deep" are alike (item 12)
            "waist level": level("waist"),
            # A real Valenzuela form: the words map, and words beat the range.
            '13-18 inches ("half tire level")': level("half_tire"),
            "above knee level": level("tire"),
            "above knee deep": level("tire"),
            "knee": level("knee"),  # the suffix may be left off
        }
    )


def test_ranges_and_two_units():
    assert_levels(
        {
            '13"-18"': level("knee"),  # a range with a unit on each number
            "13 in - 18 in": level("knee"),
            "24 in (61 cm)": level("tire"),  # one depth in two units, both tire
            "61 cm / 24 in": level("tire"),
            "8 in (25 cm)": UNMAPPED,  # 8 in gives gutter, 25 cm half_knee
            # A status counts only as the whole label.
            "knee deep, subsided": UNMAPPED,
        }
    )


def test_status_blank_and_unmapped():
    assert_levels(
        {
            "subsided": LevelLabel("status", None),
            "": LevelLabel("blank", None),
            "  ": LevelLabel("blank", None),
            "neck deep": UNMAPPED,
            "ankle deep": UNMAPPED,
            "deep": UNMAPPED,
            OTHER_WORDS: UNMAPPED,
        }
    )


def test_measures_decide_unmapped_words():
    # Words that aren't a phrase leave the measures to decide (MS6E-Q1, item 15),
    # unless they hold a number without its unit or a status.
    assert_levels(
        {
            "ANKLE DEEP (9 inches)": level("half_knee"),  # as Quezon City writes it
            'Ankle deep, 4"': level("below_gutter"),
            "ankle deep (61 cm)": level("tire"),  # 24.02 in
            "Ankle Deep": UNMAPPED,  # words alone, as Manila's DRRMO writes them
            "knee deep (25 inches)": level("knee"),  # words that map still win
            "8 (25 cm)": UNMAPPED,  # the bare 8 could contradict 25 cm (item 11)
            "25 (10 inches)": UNMAPPED,
            "knee deep, subsided (19 in)": UNMAPPED,  # the water may have gone down
            "subsided (19 in)": LevelLabel("status", None),  # a status alone, as now
        }
    )


def test_head_plus():
    # "Head" maps as "lagpas tao" does, and "N+" is at least N, which maps only
    # when that is over 45 in (MS6E-Q1, item 16).
    assert_levels(
        {
            "Head+ (60+ inches)": level("above_chest"),
            "Head+": level("above_chest"),
            "head deep": level("above_chest"),
            "head level": level("above_chest"),
            "60+ inches": level("above_chest"),
            "60+ in": level("above_chest"),
            '60+"': level("above_chest"),
            "120+ cm": level("above_chest"),  # 47.24 in
            "13+ in": UNMAPPED,  # at least 13 in could be deeper than half tire
            "45+ in": UNMAPPED,  # 45 in itself is chest
            "100+ cm": UNMAPPED,  # 39.37 in
            "13+ in (35 cm)": UNMAPPED,  # a floor never lets the other unit decide
            # Words win over a floor too, so the "+" must leave them just "head".
            "Head+ (13+ in)": level("above_chest"),
            # A "+" after the unit is a floor too.
            "13 in+": UNMAPPED,
            "13 in +": UNMAPPED,
            "60 in+": level("above_chest"),
            "120 cm+": level("above_chest"),
        }
    )


def test_passability_table_matches_rules_md():
    rows = passability_rows()
    assert len(rows) == 3
    for phrases, cls in rows:
        for phrase in phrases.split(", "):
            kept = phrase.replace("(", "").replace(")", "")
            dropped = re.sub(r" \([^()]*\)", "", phrase)
            for form in (phrase, kept, dropped):
                assert map_passability(form) == ClassLabel("class", cls), form


def test_passability_forms():
    cases = {
        "NPLV": ClassLabel("class", "NPLV"),
        "not passable to light vehicles (NPLV)": ClassLabel("class", "NPLV"),
        "Passable to light vehicles": ClassLabel("class", "PATV"),
        "NPATV (passable to all vehicles)": ClassLabel("unmapped", None),
        "": ClassLabel("blank", None),
        "closed": ClassLabel("unmapped", None),
    }
    for raw, expected in cases.items():
        assert map_passability(raw) == expected, raw


def test_label_words():
    labels = [without_annotations(label) for label, _ in level_rows()]
    passability_cells = [cell for cell, _ in passability_rows()]
    phrases = [p for cell in passability_cells for p in cell.split(", ")]
    allowed = [*labels, *phrases, 'Gutter deep, 8"', "13-18 inches", "25cm", "NPLV"]
    for raw in [*allowed, "", OTHER_WORDS]:
        assert label_words_ok(raw), raw
    refused = [
        "Espana Maceda",
        "8:00 AM",
        "knee deep (Espana)",
        "2026 knee",
        "knee deep, http://x",
        "knee deep @",
    ]
    for raw in refused:
        assert not label_words_ok(raw), raw
    first_column = " ".join([*labels, *passability_cells])
    rules_words = set(re.findall(r"[a-z]+", first_column.lower()))
    # Every word of §2's labels, and nothing but those, the units, "to", the statuses
    # and the alerts' own words.
    assert LABEL_WORDS == rules_words | UNIT_WORDS | {"to"} | STATUS_WORDS | ALERT_WORDS


def test_label_words_take_ankle_head_and_plus():
    for raw in ("ANKLE DEEP (9 inches)", "Head+ (60+ inches)"):
        assert label_words_ok(raw), raw
    for raw in ("Espana Maceda", "knee deep 8:00 AM"):
        assert not label_words_ok(raw), raw
    assert {"ankle", "head"} <= LABEL_WORDS
