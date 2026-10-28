"""Tests for flood events (C203) and near-identical dHashes (§5.5)."""

import events
import places
import pytest
import table


def photo(photo_id, spot, date="2026-08-09", links=()):
    """One photo's event input, its key made from its spot text as the intake makes it."""
    key = places.spot_key(places.spot_names(spot))
    return events.EventInput(photo_id, date, key, frozenset(links))


def test_same_date_and_key_join():
    rows = [
        photo("A001", "España Blvd. cor. Lacson Ave."),
        photo("A002", "Lacson Avenue corner Espana Boulevard"),
        photo("A003", "Araneta Ave. - Ma. Clara St."),
    ]
    assert events.group_events(rows) == {"A001": "E01", "A002": "E01", "A003": "E02"}


def test_shared_name_joins_across_cities():
    """One shared street on one date joins, whatever the two cities (C203)."""
    rows = [
        photo("A001", "EDSA cor. Ortigas Ave., Mandaluyong"),
        photo("A002", "EDSA cor. Kamuning Rd., Quezon City"),
    ]
    assert events.group_events(rows) == {"A001": "E01", "A002": "E01"}


def test_other_dates_never_join():
    rows = [
        photo("A001", "España Blvd. cor. Lacson Ave.", "2026-08-09"),
        photo("A002", "España Blvd. cor. Lacson Ave.", "2026-08-10"),
    ]
    assert events.group_events(rows) == {"A001": "E01", "A002": "E02"}


def test_links_join_both_ways():
    """A link on either photo is enough, as the guide tells Rene. A link to an id that
    isn't a row is left out, since the intake reports it as bad_link."""
    taft, roxas = "Taft Ave. cor. Pedro Gil", "Roxas Blvd. - Kalaw"
    one_way = [photo("A001", taft, links={"A002"}), photo("A002", roxas)]
    other_way = [photo("A001", taft), photo("A002", roxas, links={"A001"})]
    unlinked = [photo("A001", taft), photo("A002", roxas, links={"A009"})]
    assert events.group_events(one_way) == {"A001": "E01", "A002": "E01"}
    assert events.group_events(other_way) == {"A001": "E01", "A002": "E01"}
    assert events.group_events(unlinked) == {"A001": "E01", "A002": "E02"}


def test_a_link_joins_whatever_its_dates():
    rows = [
        photo("A001", "Taft Ave. cor. Pedro Gil", "2026-08-09", links={"A002"}),
        photo("A002", "Roxas Blvd. - Kalaw", "2026-08-10"),
    ]
    assert events.group_events(rows) == {"A001": "E01", "A002": "E01"}


# S-R9 (b): one corner written two ways on one date. A name of one sits as a whole run
# of words inside a name of the other.
RUN_TOGETHER = [
    ("EDSA Kamuning (SB)", "EDSA cor. Kamuning Rd."),
    ("Espana Maceda", "España Blvd. cor. A. Maceda St."),
    ("UN Ave. Taft", "Taft Ave. cor. UN Ave."),
    ("Araneta E. Rodriguez (SB/NB)", "E Rodriguez - G. Araneta Intersection"),
    ("Roxas Edsa intersection", "Roxas Blvd. - EDSA Intersection"),
    ("España-Lacson", "España cor. Lacson"),
    ("C-5 Ortigas", "C5 Ortigas"),
]


@pytest.mark.parametrize(("a", "b"), RUN_TOGETHER)
def test_a_name_inside_another_joins_on_one_date(a, b):
    """The rule is for events only: on two dates the rows stay apart, and same_spot
    still says no."""
    one_date = [photo("A001", a), photo("A002", b)]
    two_dates = [photo("A001", a, "2026-08-09"), photo("A002", b, "2026-08-10")]
    assert events.group_events(one_date) == {"A001": "E01", "A002": "E01"}
    assert events.group_events(two_dates) == {"A001": "E01", "A002": "E02"}
    assert not places.same_spot(places.spot_names(a), places.spot_names(b))


def test_a_shared_word_alone_never_joins():
    """edsa kamuning and edsa ortigas share a word, but neither name sits whole inside
    the other, so they are two events."""
    rows = [photo("A001", "EDSA Kamuning"), photo("A002", "EDSA Ortigas")]
    assert events.group_events(rows) == {"A001": "E01", "A002": "E02"}


def test_joined_pairs_join():
    """A joined pair, such as two duplicate photos, joins whatever its dates and spots.
    A pair must name two of the rows."""
    rows = [
        photo("A001", "Taft Ave. cor. Pedro Gil", "2026-08-09"),
        photo("A002", "Roxas Blvd. - Kalaw", "2026-08-10"),
        photo("A003", "Araneta Ave. - Ma. Clara St.", "2026-08-10"),
    ]
    assert events.group_events(rows, [("A002", "A001")]) == {
        "A001": "E01",
        "A002": "E01",
        "A003": "E02",
    }
    with pytest.raises(KeyError):
        events.group_events(rows, [("A001", "A009")])


def test_empty_keys_join_on_one_date():
    """Spot text that names only a city gives an empty key. Such rows of one date join
    one another, the conservative choice for W18, but no row with a named spot."""
    same_date = [
        photo("A001", "Manila"),
        photo("A002", "Manila"),
        photo("A003", "España Blvd."),
    ]
    assert [row.key for row in same_date] == ["", "", "espana"]
    assert events.group_events(same_date) == {
        "A001": "E01",
        "A002": "E01",
        "A003": "E02",
    }
    two_dates = [
        photo("A001", "Manila", "2026-08-09"),
        photo("A002", "Manila", "2026-08-10"),
    ]
    assert events.group_events(two_dates) == {"A001": "E01", "A002": "E02"}


def test_city_names_never_join_events():
    """Review Focus 4: a city named in both spot texts is no shared name."""
    manila = [
        photo("A001", "A. Maceda St., Manila"),
        photo("A002", "Dimasalang St., Manila"),
    ]
    quezon_city = [
        photo("A001", "Quezon Ave., Quezon City"),
        photo("A002", "Kamuning Rd., Quezon City"),
    ]
    for rows in (manila, quezon_city):
        assert events.group_events(rows) == {"A001": "E01", "A002": "E02"}


def test_event_ids_follow_the_lowest_photo_id():
    rows = [
        photo("A003", "España Blvd. cor. Lacson Ave."),
        photo("A002", "Roxas Blvd. - Kalaw"),
        photo("A004", "Roxas Blvd. - Kalaw"),
        photo("A001", "Lacson Avenue corner Espana Boulevard"),
    ]
    found = events.group_events(rows)
    assert found == {"A001": "E01", "A003": "E01", "A002": "E02", "A004": "E02"}
    assert [event_id for event_id in found.values() if not table.is_id(event_id)] == []


def test_event_numbers_sort_past_99():
    """A hundred events number E01 to E100, and E100 sorts after E99."""
    rows = [
        events.EventInput(f"A{n:03d}", "2026-08-09", f"spot {n}", frozenset())
        for n in range(1, 101)
    ]
    found = events.group_events(rows)
    assert (found["A001"], found["A099"], found["A100"]) == ("E01", "E99", "E100")
    assert [event_id for event_id in found.values() if not table.is_id(event_id)] == []
    assert sorted(["E100", "E99", "E01"], key=events.event_number) == [
        "E01",
        "E99",
        "E100",
    ]
    assert events.event_number("E100") == 100
    with pytest.raises(ValueError):
        events.event_number("A001")


def test_near():
    """dHashes within 6 bits are near (§5.5). A blank one, from a photo that doesn't
    decode, is never near, and any other text is refused."""
    zero = "0" * 16
    assert events.NEAR_BITS == 6
    assert events.near(zero, zero)
    assert events.near(zero, "000000000000003f")  # 6 bits apart
    assert not events.near(zero, "000000000000007f")  # 7 bits apart
    assert events.near("ffffffffffffffff", "c0ffffffffffffff")  # 6, in the top byte
    assert not events.near("ffffffffffffffff", "80ffffffffffffff")  # 7, in the top byte
    assert [
        pair for pair in [("", zero), (zero, ""), ("", "")] if events.near(*pair)
    ] == []
    for bad in ("0" * 15, "0" * 17, "000000000000003F", "0x0000000000003f"):
        with pytest.raises(ValueError):
            events.near(zero, bad)
