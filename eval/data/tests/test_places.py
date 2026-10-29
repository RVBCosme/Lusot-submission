"""Tests for the spot, city and poster names (C203, C224, MS2-Q4), and for the guide's
list of the office words a city's poster may end with."""

import re
from pathlib import Path

import formats
import places
import pytest

REPO = Path(__file__).resolve().parents[3]
GUIDE = REPO / "docs" / "data" / "set-a-collection-guide.md"


def test_fold_strips_marks_and_case():
    assert places.fold("España Blvd.") == "espana blvd"


@pytest.mark.parametrize(
    ("text", "names"),
    [
        ("España Blvd. cor. Lacson Ave.", {"espana", "lacson"}),
        ("Lacson Avenue corner Espana Boulevard", {"espana", "lacson"}),
        ("EDSA Kamuning (SB)", {"edsa kamuning"}),
        ("A. Maceda St., Sampaloc, Manila", {"maceda", "sampaloc"}),
        ("Quezon Ave., Quezon City", {"quezon"}),
        ("Sto. Domingo St.", {"santo domingo"}),
        ("Araneta Ave. - Ma. Clara St.", {"araneta", "ma clara"}),
        ("Manila", set()),
        # An unspaced hyphen stays inside its name, and a spaced en dash splits.
        ("EDSA-Kamuning", {"edsa kamuning"}),
        ("Roxas Blvd. \N{EN DASH} Kalaw", {"roxas", "kalaw"}),
        ("Epifanio de los Santos Ave. cor. Kamuning Rd.", {"edsa", "kamuning"}),
        ("Ramon Magsaysay Blvd., Sta. Mesa", {"ramon magsaysay", "santa mesa"}),
        # A single letter is dropped, as in A. Maceda, but a single digit stays.
        ("Valle Verde 6 (SB)", {"valle verde 6"}),
        # Additions to the plan's lists (spec §10): "to" and "front of" split the alert
        # index's spans, and "of" is dropped.
        (
            "Dr. A. Santos Ave., Olivarez School to Canaynay",
            {"santos", "olivarez school", "canaynay"},
        ),
        ("Taft Avenue, Pedro Gil to front of PGH (NB)", {"taft", "pedro gil", "pgh"}),
        ("Intersection of EDSA and Ortigas Ave.", {"edsa", "ortigas"}),
        # S-R9 (a): a barangay's or a zone's segment is one marked name, and lane notes
        # are dropped.
        ("Kapiligan, Brgy. Doña Imelda", {"kapiligan", "brgy dona imelda"}),
        ("Barangay Doña Imelda", {"brgy dona imelda"}),
        ("Zone 5, Tondo", {"zone 5", "tondo"}),
        ("EDSA cor. Kamuning (SB, innermost lane)", {"edsa", "kamuning"}),
        ("Roxas Blvd. - Buendia Flyover SB (pagbaba)", {"roxas", "buendia flyover"}),
        # S-R9 (M1): a lone letter joins the number after it.
        ("C-5 Ortigas", {"c5 ortigas"}),
        ("C 5", {"c5"}),
        ("C5", {"c5"}),
        ("R-10", {"r10"}),
        ("K-115", {"k115"}),
    ],
)
def test_spot_names(text, names):
    assert places.spot_names(text) == names


def test_marked_names():
    """Each of Manila's 16 districts gives one marked name, and so does a barangay's or
    a zone's segment (S-R9 (a)). A street's name is never marked."""
    assert len(set(places.MANILA_DISTRICTS)) == len(places.MANILA_DISTRICTS) == 16
    assert [
        district
        for district in places.MANILA_DISTRICTS
        if [places.marked(name) for name in places.spot_names(district)] != [True]
    ] == []
    marked_names = ["brgy dona imelda", "brgy 123", "zone 5", "sampaloc", "santa mesa"]
    assert [name for name in marked_names if not places.marked(name)] == []
    streets = ["kapiligan", "espana", "c5 ortigas", "edsa kamuning"]
    assert [name for name in streets if places.marked(name)] == []


def test_same_spot():
    """At least two shared names that aren't marked (C224, S-R9 (a))."""
    assert places.same_spot(
        places.spot_names("España Blvd. cor. Lacson Ave."),
        places.spot_names("Lacson Avenue corner Espana Boulevard"),
    )
    assert places.same_spot(
        places.spot_names("Araneta - Baloy, Brgy. Doña Imelda"),
        places.spot_names("Araneta Ave. cor. Baloy St."),
    )
    assert places.same_spot(
        frozenset({"espana", "lacson"}), frozenset({"lacson", "espana"})
    )
    assert not places.same_spot(frozenset({"araneta", "quezon"}), frozenset({"quezon"}))
    # S-R9 (a) reverses the plan's case: one equal name each is not the same spot.
    assert not places.same_spot(
        frozenset({"edsa kamuning"}), frozenset({"edsa kamuning"})
    )
    assert not places.same_spot(frozenset({"espana"}), frozenset({"lacson"}))
    assert not places.same_spot(frozenset({"a"}), frozenset({"a", "b"}))
    assert not places.same_spot(frozenset(), frozenset())


# S-R9 (a): different corners that used to share two names, through a barangay, a
# district, a lane note or a bare number. None is the same spot.
DIFFERENT_CORNERS = [
    ("Araneta - Baloy, Brgy. Doña Imelda", "Araneta - E. Rodriguez, Brgy. Doña Imelda"),
    ("España cor. Lacson, Brgy 123", "España cor. Blumentritt, Brgy 123"),
    ("España cor. Lacson, Sampaloc", "España cor. Maceda, Sampaloc"),
    (
        "EDSA cor. Kamuning (SB, innermost lane)",
        "EDSA cor. Ortigas (SB, innermost lane)",
    ),
    ("C-5 cor. Kalayaan", "Kalayaan Ave., Brgy. 5"),
]


@pytest.mark.parametrize(("a", "b"), DIFFERENT_CORNERS)
def test_different_corners_are_not_the_same_spot(a, b):
    assert not places.same_spot(places.spot_names(a), places.spot_names(b))


def test_spot_key_round_trips():
    """The manifest's spot_key holds the names sorted and joined by |. An empty key, from
    spot text that names only a city, has no names."""
    names = places.spot_names("Lacson Avenue corner Espana Boulevard")
    assert places.spot_key(names) == "espana|lacson"
    assert places.names_of("espana|lacson") == names
    assert places.spot_key(places.spot_names("Manila")) == ""
    assert places.names_of("") == frozenset()


def test_city_name():
    """The display name for each form city_name finds, and for each of the 17 names as
    formats lists them. Plain quezon is the province."""
    found = {
        "Las Piñas": "Las Piñas",
        "QC": "Quezon City",
        "City of Manila": "Manila",
        "Pateros": "Pateros",
        "Las Pinas City": "Las Piñas",
        "Q.C.": "Quezon City",
        "Municipality of Pateros": "Pateros",
    }
    assert {text: places.city_name(text) for text in found} == found
    assert [
        name for name in formats.METRO_MANILA if places.city_name(name) != name
    ] == []
    assert places.city_name("quezon") is None
    assert places.city_name("Calamba") is None


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("MMDA", "mmda"),
        ("Metropolitan Manila Development Authority", "mmda"),
        ("Metro Manila Development Authority", "mmda"),
        ("Quezon City", "city"),
        ("Quezon City DRRMO", "city"),
        ("Quezon City Government", "city"),
        ("Manila Public Information Office", "city"),
        ("City of Manila", "city"),
        ("Pasig City Information Office", "city"),
        ("Brgy. Damayang Lagi", "other"),
        ("Barangay Tumana", "other"),
        ("QC Police District", "other"),
        ("BFP Manila", "other"),
        ("Manila Bulletin", "other"),
        ("Mayor Juan dela Cruz", "other"),
        ("Quezon", "other"),
        # The guide's example of a natural spelling that isn't listed.
        ("Manila DRRM Office", "other"),
    ],
)
def test_poster_kind(text, kind):
    assert places.poster_kind(text) == kind


def test_guide_lists_the_office_words():
    """The guide lists, in backticks, exactly the office words that poster_kind takes
    after a city's name, since Rene writes a city office's poster that way (MS2-Q4)."""
    guide = GUIDE.read_text(encoding="utf-8")
    sentence = re.search(r"one of these office words: (.+?)\. ", guide)
    assert sentence is not None
    listed = re.findall(r"`([^`]+)`", sentence.group(1))
    assert len(set(places.OFFICE_WORDS)) == len(places.OFFICE_WORDS) == 9
    assert sorted(places.fold(word) for word in listed) == sorted(places.OFFICE_WORDS)
    assert [
        word for word in listed if places.poster_kind(f"Manila {word}") != "city"
    ] == []


def test_guide_examples_read_as_one_name():
    """The guide's examples of a corner written without a break each read as one name,
    which is why Rene links such photos himself (S-R9 (b)). Each break the guide names
    does split a corner."""
    guide = GUIDE.read_text(encoding="utf-8")
    examples = ["Espana Maceda", "UN Ave. Taft", "EDSA Kamuning", "España-Lacson"]
    assert [text for text in examples if f"`{text}`" not in guide] == []
    assert [text for text in examples if len(places.spot_names(text)) != 1] == []
    corners = [
        "Taft cor. Kalaw",
        "Taft corner Kalaw",
        "Taft near Kalaw",
        "Taft at Kalaw",
        "Taft and Kalaw",
        "Taft to Kalaw",
        "Taft, Kalaw",
        "Taft/Kalaw",
        "Taft & Kalaw",
        "Taft - Kalaw",
    ]
    assert [
        text for text in corners if places.spot_names(text) != {"taft", "kalaw"}
    ] == []
