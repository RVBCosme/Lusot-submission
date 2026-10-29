"""Tests for the checks of the Set A and A-neg logs, the match of each photo to its
alerts and each photo's facts (spec §5.3, §5.9, C201, C209, C223, C224, S-R4, S-R9).

Every log is synthetic, and each photo it names is an empty file, since the check only
stats it (C201).
"""

from datetime import datetime, timedelta
from pathlib import Path

import formats
import pytest
import setlogs
import synth
import table
from table import Fact, Finding

REPO = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = REPO / "eval" / "templates"
GUIDE = REPO / "docs" / "data" / "set-a-collection-guide.md"
# synth's Set A rows are at España cor. Lacson, posted at this time. The same corner
# written another way is the same spot, through two shared names (C224, S-R9).
POSTED = synth.set_a_row()["post_time_pht"]
SAME_SPOT = "Lacson Avenue corner Espana Boulevard"
# A text that no finding or fact may hold (C201).
SENTINEL = "Zqxjv"


def check(base, rows, *, set_name="A", columns=None, photos=None):
    """Check the rows as one set's log, written in base with the columns, by default the
    set's template's. Each photo the rows name, or each of photos when given, is an
    empty file in base/raw."""
    if columns is None:
        template = "set_a_log.csv" if set_name == "A" else "a_neg_log.csv"
        columns = formats.TEMPLATES[template]
    log = synth.write_csv(base / "log.csv", columns, rows)
    raw = base / "raw"
    raw.mkdir()
    if photos is None:
        photos = {row["photo_file"] for row in rows if row.get("photo_file")}
    for name in photos:
        (raw / name).touch()
    return setlogs.check_set_log(log, raw, set_name=set_name)


def separate(minutes=10, **cells):
    """A Set A row for an alert in another post: MMDA's, at the same spot written
    another way, posted the given minutes after the photo (before it when negative)."""
    alert = formats.parse_time(POSTED) + timedelta(minutes=minutes)
    alert_cells = {
        "photo_in_alert_post": "no",
        "alert_poster": "MMDA",
        "alert_spot_text": SAME_SPOT,
        "alert_time_pht": alert.strftime("%Y-%m-%d %H:%M"),
    }
    return synth.set_a_row(**(alert_cells | cells))


def only_photo(found):
    """The one photo of a check that found no problem."""
    assert found.problems == []
    [photo] = found.photos
    return photo


def labels(photo):
    return (
        photo.match,
        photo.level_label_raw,
        photo.passability_raw,
        photo.other_alerts_raw,
    )


WITHOUT_CITY = tuple(c for c in formats.TEMPLATES["set_a_log.csv"] if c != "city")
# Set A's template with same_spot_as misspelt, the 18th name.
MISSPELT_LINK = formats.SET_A_COLUMNS + ("same_spot", "alert_poster", "alert_spot_text")
# Each kind of problem, alone. A name that isn't the photo's own is never looked for,
# so the photo it names needn't exist.
PROBLEM_CASES = [
    pytest.param(
        [synth.set_a_row()],
        {"columns": WITHOUT_CITY},
        [Finding("log", "city", "missing_column")],
        id="missing_column",
    ),
    pytest.param(
        [synth.set_a_row(candidate_id="A01")],
        {},
        [Finding("row 1", "candidate_id", "bad_id")],
        id="bad_id",
    ),
    pytest.param(
        [synth.set_a_row(photo_file="A002.jpg")],
        {"photos": ()},
        [Finding("A001", "photo_file", "id_file_mismatch")],
        id="id_file_mismatch",
    ),
    pytest.param(
        [synth.set_a_row(), synth.set_a_row(spot_text=SAME_SPOT)],
        {},
        [Finding("A001", "spot_text", "differs")],
        id="differs",
    ),
    pytest.param(
        [synth.set_a_row()],
        {"photos": ()},
        [Finding("A001", "photo_file", "file_missing")],
        id="file_missing",
    ),
    pytest.param(
        [synth.set_a_row(logged_on="29/10/2026")],
        {},
        [Finding("A001", "logged_on", "bad_date")],
        id="bad_date",
    ),
    pytest.param(
        [synth.set_a_row(post_time_pht="2026-08-09 8:20")],
        {},
        [Finding("A001", "post_time_pht", "bad_time")],
        id="bad_time",
    ),
    pytest.param(
        [synth.set_a_row(reference_visible="tire")],
        {},
        [Finding("A001", "reference_visible", "not_in_list")],
        id="not_in_list",
    ),
    pytest.param(
        [synth.set_a_row(logged_on="")],
        {},
        [Finding("A001", "logged_on", "missing")],
        id="missing",
    ),
    pytest.param(
        [synth.set_a_row(same_spot_as="A009")],
        {},
        [Finding("A001", "same_spot_as", "bad_link")],
        id="bad_link",
    ),
    pytest.param(
        [
            synth.set_a_row(same_spot_as="A002"),
            synth.set_a_row(candidate_id="A002", post_time_pht="2026-08-10 08:20"),
        ],
        {},
        [Finding("A001", "same_spot_as", "bad_link")],
        id="bad_link_to_another_date",
    ),
    pytest.param(
        [synth.set_a_row(level_label_raw="knee deep; 19 in")],
        {},
        [Finding("A001", "level_label_raw", "semicolon")],
        id="semicolon_in_level",
    ),
    pytest.param(
        [synth.set_a_row(passability_raw="NPLV; PATV")],
        {},
        [Finding("A001", "passability_raw", "semicolon")],
        id="semicolon_in_passability",
    ),
    pytest.param(
        [synth.set_a_row()],
        {"columns": MISSPELT_LINK},
        [Finding("log", "column 18", "unknown")],
        id="unknown_column",
    ),
]


@pytest.mark.parametrize(("rows", "options", "expected"), PROBLEM_CASES)
def test_each_problem_kind(tmp_path, rows, options, expected):
    assert check(tmp_path, rows, **options).problems == expected


SET_A_REQUIRED = (
    "candidate_id",
    "logged_on",
    "platform",
    "post_url",
    "poster",
    "post_time_pht",
    "spot_text",
    "city",
    "photo_in_alert_post",
    "photo_file",
    "reference_visible",
    "label_in_image",
    "faces_or_plates",
)
SEPARATE_POST_REQUIRED = ("alert_poster", "alert_spot_text", "alert_time_pht")
A_NEG_REQUIRED = (
    "candidate_id",
    "logged_on",
    "poster",
    "post_time_pht",
    "spot_text",
    "city",
    "photo_file",
    "reference_visible",
    "label_in_image",
    "faces_or_plates",
    "level_label_raw",
    "surface",
)
ROW_MAKERS = {
    "same_post": synth.set_a_row,
    "separate_post": separate,
    "a_neg": synth.a_neg_row,
}


@pytest.mark.parametrize(
    ("set_name", "maker", "column"),
    [("A", "same_post", column) for column in SET_A_REQUIRED]
    + [("A", "separate_post", column) for column in SEPARATE_POST_REQUIRED]
    + [("A-neg", "a_neg", column) for column in A_NEG_REQUIRED],
)
def test_each_required_value(tmp_path, set_name, maker, column):
    """A blank required value is missing. A blank id leaves only the row to name."""
    row = ROW_MAKERS[maker](**{column: ""})
    ref = "row 1" if column == "candidate_id" else row["candidate_id"]
    found = check(tmp_path, [row], set_name=set_name)
    assert found.problems == [Finding(ref, column, "missing")]


def test_set_a_labels_may_be_blank(tmp_path):
    """MS2 checks no label (C207): the harness reports a blank one as unmapped."""
    found = check(tmp_path, [synth.set_a_row(level_label_raw="", passability_raw="")])
    assert labels(only_photo(found)) == ("same_post", "", "", "")
    assert found.warnings == []


def test_bad_id_names_the_row_not_the_cell(tmp_path):
    found = check(tmp_path, [synth.set_a_row(candidate_id="Espana")])
    assert found.problems == [Finding("row 1", "candidate_id", "bad_id")]
    assert (found.photos, found.warnings, found.rows) == ([], [], 1)
    printed = [str(item) for item in found.problems + found.warnings]
    assert [line for line in printed if "Espana" in line] == []


@pytest.mark.parametrize(
    ("set_name", "row"),
    [
        ("A", synth.set_a_row(candidate_id="N001")),
        ("A-neg", synth.a_neg_row(candidate_id="A001")),
    ],
    ids=["a_neg_id_in_set_a", "set_a_id_in_a_neg"],
)
def test_each_set_takes_its_own_ids(tmp_path, set_name, row):
    found = check(tmp_path, [row], set_name=set_name)
    assert found.problems == [Finding("row 1", "candidate_id", "bad_id")]


def test_a_problem_on_several_rows_of_a_photo_is_listed_once(tmp_path):
    rows = [synth.set_a_row(logged_on=""), synth.set_a_row(logged_on="")]
    assert check(tmp_path, rows).problems == [Finding("A001", "logged_on", "missing")]


def test_todays_17_column_template_works(tmp_path):
    """Rows logged on the template before C209 have none of its three optional columns,
    and a same-post row needs none of them."""
    rows = [synth.set_a_row(), synth.set_a_row(candidate_id="A002")]
    found = check(tmp_path, rows, columns=formats.SET_A_COLUMNS)
    assert (found.problems, found.warnings) == ([], [])
    assert [photo.match for photo in found.photos] == ["same_post", "same_post"]


def test_separate_post_row_needs_its_alert_columns(tmp_path):
    """On the 17-column template a separate-post row has no alert poster or spot, so it
    is missing both, and it can't fit."""
    found = check(tmp_path, [separate()], columns=formats.SET_A_COLUMNS)
    assert found.problems == [
        Finding("A001", "alert_poster", "missing"),
        Finding("A001", "alert_spot_text", "missing"),
    ]
    assert found.warnings == [Fact("A001", "match", "none")]


def test_same_post_alert_fits(tmp_path):
    """An alert in the photo's own post fits by construction, whatever its spot and its
    time (rules §3)."""
    row = synth.set_a_row(
        spot_text="EDSA Kamuning (SB)",
        alert_time_pht="2026-08-09 11:20",
        level_label_raw="knee deep",
        passability_raw="NPLV",
    )
    found = check(tmp_path, [row])
    assert labels(only_photo(found)) == ("same_post", "knee deep", "NPLV", "")
    assert found.warnings == []


@pytest.mark.parametrize("poster", ["MMDA", "Manila Public Information Office"])
def test_separate_alert_fits_within_30_minutes_at_the_same_spot(tmp_path, poster):
    row = separate(
        minutes=-20,
        alert_poster=poster,
        level_label_raw="half tire",
        passability_raw="NPLV",
    )
    found = check(tmp_path, [row])
    assert labels(only_photo(found)) == ("separate_post", "half tire", "NPLV", "")
    assert found.warnings == []


@pytest.mark.parametrize("minutes", [30, -30])
def test_thirty_minutes_is_inclusive(tmp_path, minutes):
    photo = only_photo(check(tmp_path, [separate(minutes=minutes)]))
    assert photo.match == "separate_post"


@pytest.mark.parametrize(
    ("cells", "warnings"),
    [
        ({"minutes": 31}, [Fact("A001", "match", "none")]),
        ({"minutes": -31}, [Fact("A001", "match", "none")]),
        (
            {"alert_spot_text": "España Blvd. cor. A. Maceda St."},
            [Fact("A001", "match", "none")],
        ),
        (
            {"alert_poster": "Manila Bulletin"},
            [Fact("A001", "alert_poster", "other"), Fact("A001", "match", "none")],
        ),
    ],
    ids=["31_minutes_after", "31_minutes_before", "one_shared_name", "manila_bulletin"],
)
def test_separate_alert_misses(tmp_path, cells, warnings):
    found = check(tmp_path, [separate(**cells)])
    assert labels(only_photo(found)) == ("none", "", "", "")
    assert found.warnings == warnings


@pytest.mark.parametrize(
    ("spot", "alert_spot"),
    [
        ("EDSA Kamuning (SB)", "EDSA Kamuning (SB)"),
        ("Taft Ave.", "Taft Avenue"),
        (
            "Araneta - Baloy, Brgy. Doña Imelda",
            "Araneta - E. Rodriguez, Brgy. Doña Imelda",
        ),
    ],
    ids=["one_name_written_alike", "a_lone_street", "a_street_and_a_barangay"],
)
def test_a_spot_without_two_shared_names_never_matches(tmp_path, spot, alert_spot):
    """S-R9: the same spot needs two shared names that aren't a barangay's, a zone's or
    a Manila district's, so a one-name spot never fits, even written alike."""
    found = check(tmp_path, [separate(spot_text=spot, alert_spot_text=alert_spot)])
    assert labels(only_photo(found)) == ("none", "", "", "")
    assert found.warnings == [Fact("A001", "match", "none")]


def test_nearest_of_several_alerts(tmp_path):
    rows = [
        separate(minutes=25, level_label_raw="knee deep"),
        separate(minutes=5, level_label_raw="half knee", passability_raw="NPLV"),
        separate(minutes=15, level_label_raw="gutter deep"),
    ]
    found = check(tmp_path, rows)
    photo = only_photo(found)
    assert labels(photo) == (
        "separate_post",
        "half knee",
        "NPLV",
        "knee deep;gutter deep",
    )
    assert (photo.rows, found.rows, found.warnings) == (3, 3, [])


def test_ties_go_to_same_post_rows_then_log_order(tmp_path):
    """A same-post row without an alert time counts as 0 minutes away, so it wins a tie
    with a separate alert posted with the photo, even when logged second. Two separate
    alerts 10 minutes either side tie, and the first in the log wins. Each tie's labels
    differ, so each is a warning (S-R10)."""
    rows = [
        separate(minutes=0, level_label_raw="knee deep"),
        synth.set_a_row(level_label_raw="half knee"),
    ]
    found = check(tmp_path / "same_post", rows)
    assert labels(only_photo(found)) == ("same_post", "half knee", "PATV", "knee deep")
    assert found.warnings == [Fact("A001", "nearest", "tied")]
    rows = [
        separate(minutes=10, level_label_raw="knee deep"),
        separate(minutes=-10, level_label_raw="half knee"),
    ]
    found = check(tmp_path / "log_order", rows)
    assert labels(only_photo(found)) == (
        "separate_post",
        "knee deep",
        "PATV",
        "half knee",
    )
    assert found.warnings == [Fact("A001", "nearest", "tied")]


@pytest.mark.parametrize(
    ("cells", "warnings"),
    [
        ({"level_label_raw": "knee deep"}, [Fact("A001", "nearest", "tied")]),
        ({"passability_raw": "NPATV"}, [Fact("A001", "nearest", "tied")]),
        ({}, []),
        ({"minutes": -15, "level_label_raw": "knee deep"}, []),
    ],
    ids=["level_differs", "passability_differs", "same_labels", "not_as_near"],
)
def test_a_tie_with_other_labels_is_a_warning(tmp_path, cells, warnings):
    """S-R10: two fitting alerts as near as each other, such as one spot's NB and SB
    alerts (direction words are dropped), tie, and the log's order picks the labels.
    The intake warns when the tied alerts' labels differ."""
    rows = [separate(minutes=10), separate(**({"minutes": -10} | cells))]
    found = check(tmp_path, rows)
    photo = only_photo(found)
    assert (photo.match, photo.level_label_raw, photo.passability_raw) == (
        "separate_post",
        'Gutter deep, 8"',
        "PATV",
    )
    assert found.warnings == warnings


def test_several_same_post_rows_are_a_warning(tmp_path):
    """S-R10: a post listing several spots holds one alert for the photo's own spot, so
    a photo with two or more same-post rows is a warning. Without alert times the rows
    tie and the log's order picks the labels; with times, another corner's alert can be
    the nearer one."""
    other_corner = synth.set_a_row(level_label_raw="half knee")
    own_corner = synth.set_a_row(level_label_raw="gutter deep")
    found = check(tmp_path / "untimed", [other_corner, own_corner])
    assert labels(only_photo(found)) == (
        "same_post",
        "half knee",
        "PATV",
        "gutter deep",
    )
    assert found.warnings == [
        Fact("A001", "same_post", "several"),
        Fact("A001", "nearest", "tied"),
    ]
    rows = [
        other_corner | {"alert_time_pht": POSTED},
        own_corner | {"alert_time_pht": "2026-08-09 08:10"},
    ]
    found = check(tmp_path / "timed", rows)
    assert labels(only_photo(found)) == (
        "same_post",
        "half knee",
        "PATV",
        "gutter deep",
    )
    assert found.warnings == [Fact("A001", "same_post", "several")]


def test_an_unknown_column_is_named_by_its_place(tmp_path):
    """S-R10: a misspelt header name, such as same_spot for same_spot_as, would leave
    Rene's links out in silence. It is a problem named by its place in the header,
    never by its text, and the rows are still checked. A misspelt required column is
    also missing, and then no row is checked."""
    rows = [
        synth.set_a_row(same_spot="A002"),
        synth.set_a_row(candidate_id="A002", logged_on=""),
    ]
    found = check(tmp_path / "optional", rows, columns=MISSPELT_LINK)
    assert found.problems == [
        Finding("log", "column 18", "unknown"),
        Finding("A002", "logged_on", "missing"),
    ]
    assert found.photos[0].same_spot_as == frozenset()
    misspelt = tuple(
        "cty" if column == "city" else column
        for column in formats.TEMPLATES["set_a_log.csv"]
    )
    rows = [synth.set_a_row(cty="Manila")]
    found = check(tmp_path / "required", rows, columns=misspelt)
    assert found.problems == [
        Finding("log", "city", "missing_column"),
        Finding("log", "column 9", "unknown"),
    ]
    assert found.photos == []


def test_other_alerts_leave_out_blank_labels(tmp_path):
    """A fitting alert logged without depth words adds nothing to other_alerts_raw,
    since a blank cell means none."""
    rows = [
        synth.set_a_row(),
        separate(minutes=5, level_label_raw=""),
        separate(minutes=10, level_label_raw="knee deep"),
    ]
    assert only_photo(check(tmp_path, rows)).other_alerts_raw == "knee deep"


def test_unrecognised_alert_poster_is_a_warning(tmp_path):
    """S-R4: an alert whose poster counts as other never fits, so it can't reach
    other_alerts_raw, where it could have set off rules §3's conflict exclusion. So the
    intake warns, as it does for the photo's own poster."""
    rows = [
        synth.set_a_row(),
        separate(minutes=5, alert_poster="Manila DRRM Office", level_label_raw="waist"),
    ]
    found = check(tmp_path, rows)
    assert labels(only_photo(found)) == ("same_post", 'Gutter deep, 8"', "PATV", "")
    assert found.warnings == [Fact("A001", "alert_poster", "other")]


def test_outside_metro_manila_is_a_warning(tmp_path):
    found = check(tmp_path, [synth.set_a_row(city="Calamba")])
    photo = only_photo(found)
    assert (photo.city, photo.metro_manila) == ("Calamba", "no")
    assert found.warnings == [Fact("A001", "metro_manila", "no")]


def test_poster_other_is_a_warning(tmp_path):
    """The photo's own poster: a news outlet counts as other (rules §9). The match is a
    separate fact, so a same-post alert still fits."""
    found = check(tmp_path, [synth.set_a_row(poster="Manila Bulletin")])
    photo = only_photo(found)
    assert (photo.poster_kind, photo.match) == ("other", "same_post")
    assert found.warnings == [Fact("A001", "poster_kind", "other")]


def test_notes_join_in_log_order(tmp_path):
    rows = [synth.set_a_row(notes="a"), synth.set_a_row(notes="b")]
    assert only_photo(check(tmp_path / "two", rows)).notes == "a | b"
    # Distinct notes only, and a blank one adds nothing.
    rows += [synth.set_a_row(notes="a"), synth.set_a_row()]
    assert only_photo(check(tmp_path / "four", rows)).notes == "a | b"


def test_differs_ignores_case_only_in_list_columns(tmp_path):
    """A photo's rows may differ in capitals only in a list column, such as
    reference_visible, or A-neg's poster and surface."""
    rows = [synth.set_a_row(), synth.set_a_row(reference_visible="Wheel")]
    assert check(tmp_path / "list", rows).problems == []
    rows = [synth.set_a_row(), synth.set_a_row(poster="Mmda")]
    found = check(tmp_path / "text", rows)
    assert found.problems == [Finding("A001", "poster", "differs")]
    rows = [synth.a_neg_row(), synth.a_neg_row(poster="Own", surface="DRY")]
    assert check(tmp_path / "a_neg", rows, set_name="A-neg").problems == []


def test_same_spot_as_links_photos_of_its_date(tmp_path):
    """Rene's link names other photos of the set from the same date, separated by ;."""
    rows = [
        synth.set_a_row(same_spot_as="A002; A003"),
        synth.set_a_row(candidate_id="A002"),
        synth.set_a_row(candidate_id="A003"),
    ]
    found = check(tmp_path, rows)
    assert found.problems == []
    assert found.photos[0].same_spot_as == frozenset({"A002", "A003"})


def test_photo_facts(tmp_path):
    """Every fact of a photo, its city and poster in forms the tools read (MS2-Q4). The
    photos keep the log's order."""
    rows = [
        synth.set_a_row(
            city="City of Manila",
            poster="Manila Public Information Office",
            same_spot_as="A002",
        ),
        synth.set_a_row(candidate_id="A002"),
    ]
    found = check(tmp_path, rows)
    assert (found.problems, found.warnings, found.rows) == ([], [], 2)
    assert [photo.photo_id for photo in found.photos] == ["A001", "A002"]
    assert found.photos[0] == setlogs.Photo(
        photo_id="A001",
        set="A",
        photo_file="A001.jpg",
        event_date="2026-08-09",
        post_time=datetime(2026, 8, 9, 8, 20),
        city="Manila",
        metro_manila="yes",
        spot_key="espana|lacson",
        same_spot_as=frozenset({"A002"}),
        poster_kind="city",
        match="same_post",
        level_label_raw='Gutter deep, 8"',
        passability_raw="PATV",
        other_alerts_raw="",
        label_in_image="no",
        reference_visible="wheel",
        faces_or_plates="no",
        surface="",
        notes="",
        rows=1,
    )


def test_a_photo_without_a_post_time_has_no_date(tmp_path):
    """A post time that isn't one is a problem, and the photo's time and date stay
    blank."""
    found = check(tmp_path, [synth.set_a_row(post_time_pht="9 Aug 2026")])
    assert found.problems == [Finding("A001", "post_time_pht", "bad_time")]
    [photo] = found.photos
    assert (photo.post_time, photo.event_date) == (None, "")


def test_a_neg_rows(tmp_path):
    found = check(tmp_path / "own", [synth.a_neg_row()], set_name="A-neg")
    assert (found.problems, found.warnings) == ([], [])
    [photo] = found.photos
    assert (photo.set, photo.poster_kind, photo.surface) == ("A-neg", "other", "dry")
    assert labels(photo) == ("", "none", "", "")
    cases = [
        ({"poster": "stranger"}, Finding("N001", "poster", "not_in_list")),
        ({"level_label_raw": "dry"}, Finding("N001", "level_label_raw", "not_in_list")),
        ({"surface": ""}, Finding("N001", "surface", "missing")),
    ]
    for number, (cells, problem) in enumerate(cases):
        rows = [synth.a_neg_row(**cells)]
        found = check(tmp_path / str(number), rows, set_name="A-neg")
        assert found.problems == [problem]
    # surface is a photo column in A-neg, so a photo's rows must repeat it.
    rows = [synth.a_neg_row(), synth.a_neg_row(surface="wet")]
    found = check(tmp_path / "repeated", rows, set_name="A-neg")
    assert found.problems == [Finding("N001", "surface", "differs")]


def test_a_neg_log_made_from_the_checklist_reads_cleanly(tmp_path):
    """C209: the tracker's checklist v2 has Rene copy the 17-column Set A template and
    add surface, with no optional column."""
    rows = [synth.a_neg_row(), synth.a_neg_row(candidate_id="N002", surface="wet")]
    columns = formats.SET_A_COLUMNS + ("surface",)
    found = check(tmp_path, rows, set_name="A-neg", columns=columns)
    assert (found.problems, found.warnings) == ([], [])
    assert [photo.surface for photo in found.photos] == ["dry", "wet"]


def test_a_neg_log_from_the_template_reads_cleanly(tmp_path):
    """A-neg's template, with the alert columns of Set A's added: A-neg ignores them,
    blank or filled."""
    template = table.read_table(TEMPLATE_DIR / "a_neg_log.csv").columns
    columns = template + ("alert_poster", "alert_spot_text")
    blank = synth.a_neg_row()
    found = check(tmp_path / "blank", [blank], set_name="A-neg", columns=columns)
    assert (found.problems, found.warnings) == ([], [])
    filled = synth.a_neg_row(alert_poster="Manila Bulletin", alert_spot_text="Taft")
    found = check(tmp_path / "filled", [filled], set_name="A-neg", columns=columns)
    assert (found.problems, found.warnings) == ([], [])


def commons_row(**cells):
    """A-neg's row for a Wikimedia Commons photo, as the tracker fills one (C209, S-R20):
    its file page in post_url, the date taken at 00:00 when the page gives no time, and
    its licence and credit. Each keyword sets one cell."""
    commons = {
        "platform": "other",
        "post_url": "https://example.invalid/file/1",
        "poster": "commons",
        "post_time_pht": "2026-10-27 00:00",
        "notes": "time unknown",
        "licence": "cc-by-4.0",
        "credit": "A. Photographer",
    }
    return synth.a_neg_row(**(commons | cells))


def test_a_neg_accepts_commons_rows(tmp_path):
    """A Commons row reads with no problem beside Rene's own, its licence in any case,
    as the log's other list values are. Every A-neg poster stays other (§5.9)."""
    rows = [
        commons_row(),
        synth.a_neg_row(candidate_id="N002"),
        commons_row(candidate_id="N003", licence="CC0"),
    ]
    found = check(tmp_path, rows, set_name="A-neg")
    assert (found.problems, found.warnings) == ([], [])
    assert [photo.poster_kind for photo in found.photos] == ["other"] * 3


@pytest.mark.parametrize(
    ("cells", "problem"),
    [
        ({"licence": ""}, Finding("N001", "licence", "missing")),
        ({"licence": "cc-by-sa-4.0"}, Finding("N001", "licence", "not_in_list")),
        ({"credit": ""}, Finding("N001", "credit", "missing")),
        ({"poster": "Commons", "licence": ""}, Finding("N001", "licence", "missing")),
    ],
    ids=["blank_licence", "by_sa", "blank_credit", "poster_in_capitals"],
)
def test_commons_row_needs_licence_and_credit(tmp_path, cells, problem):
    """A Commons row needs a licence from formats.COMMONS_LICENCES, never BY-SA, and a
    credit. A finding names the row's id and column only: the credit is free text, like
    notes, and never prints."""
    row = commons_row(**({"credit": SENTINEL} | cells))
    found = check(tmp_path, [row], set_name="A-neg")
    assert found.problems == [problem]
    printed = [str(item) for item in found.problems + found.warnings]
    assert [line for line in printed if SENTINEL.casefold() in line.casefold()] == []


def test_own_and_friend_rows_leave_licence_and_credit_unread(tmp_path):
    """On Rene's own or a friend's row, licence and credit may be blank and aren't
    checked, even when filled."""
    rows = [
        synth.a_neg_row(licence="cc-by-sa-4.0"),
        synth.a_neg_row(candidate_id="N002", poster="friend", credit=SENTINEL),
    ]
    columns = formats.A_NEG_COLUMNS + ("same_spot_as", "licence", "credit")
    found = check(tmp_path, rows, set_name="A-neg", columns=columns)
    assert (found.problems, found.warnings) == ([], [])


def test_a_neg_log_without_the_new_columns_still_reads(tmp_path):
    """A log on A-neg's template before S-R20, with no licence or credit column, still
    reads for Rene's own and a friend's photos."""
    rows = [synth.a_neg_row(), synth.a_neg_row(candidate_id="N002", poster="friend")]
    columns = formats.A_NEG_COLUMNS + ("same_spot_as",)
    found = check(tmp_path, rows, set_name="A-neg", columns=columns)
    assert (found.problems, found.warnings) == ([], [])


def test_spreadsheet_saved_log_reads_cleanly(tmp_path):
    """Review Focus 1: a log saved from Excel or Google Sheets, with a BOM, CRLF endings,
    capitals in list values, stray spaces, A001.JPG and blank rows at the end, reads
    cleanly, and its list values come out in lower case."""
    columns = formats.TEMPLATES["set_a_log.csv"]
    row = synth.set_a_row(
        platform="Facebook",
        photo_in_alert_post="Yes",
        photo_file="A001.JPG",
        reference_visible="Wheel",
        label_in_image="CROPPED",
        faces_or_plates="No",
    )
    padded = {column: f" {value}  " for column, value in row.items()}
    text = table.csv_bytes(columns, [padded]).decode("utf-8").replace("\n", "\r\n")
    blank_rows = "," * (len(columns) - 1) + "\r\n" + "\r\n"
    log = tmp_path / "log.csv"
    log.write_bytes(b"\xef\xbb\xbf" + (text + blank_rows).encode("utf-8"))
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "A001.JPG").touch()
    found = setlogs.check_set_log(log, raw, set_name="A")
    assert (found.problems, found.warnings, found.rows) == ([], [], 1)
    [photo] = found.photos
    assert (photo.match, photo.photo_file) == ("same_post", "A001.JPG")
    assert (photo.reference_visible, photo.label_in_image, photo.faces_or_plates) == (
        "wheel",
        "cropped",
        "no",
    )


def test_findings_hold_no_cell_text(tmp_path):
    """C201: with a sentinel in every column of rows with problems, and as a header
    name, no finding or fact holds it. The rows reach every kind that reads a cell's
    text."""
    columns = formats.TEMPLATES["set_a_log.csv"] + (SENTINEL,)
    everywhere = dict.fromkeys(columns, SENTINEL)
    same_post = everywhere | {"candidate_id": "A003", "photo_in_alert_post": "yes"}
    set_a = check(
        tmp_path / "set_a",
        [
            everywhere,
            everywhere | {"candidate_id": "A001"},
            everywhere | {"candidate_id": "A001", "spot_text": f"{SENTINEL} Ave."},
            everywhere | {"candidate_id": "A002", "photo_in_alert_post": "no"},
            same_post,
            same_post | {"level_label_raw": f"{SENTINEL}; {SENTINEL}"},
        ],
        columns=columns,
    )
    a_neg_columns = formats.TEMPLATES["a_neg_log.csv"] + (SENTINEL,)
    a_neg = check(
        tmp_path / "a_neg",
        [dict.fromkeys(a_neg_columns, SENTINEL) | {"candidate_id": "N001"}],
        set_name="A-neg",
        columns=a_neg_columns,
    )
    assert {problem.kind for problem in set_a.problems} == {
        "unknown",
        "bad_id",
        "bad_date",
        "bad_time",
        "not_in_list",
        "id_file_mismatch",
        "semicolon",
        "differs",
        "bad_link",
    }
    assert {fact.fact for fact in set_a.warnings} == {
        "metro_manila",
        "poster_kind",
        "alert_poster",
        "same_post",
        "nearest",
        "match",
    }
    assert a_neg.problems and a_neg.warnings
    printed = [
        str(item)
        for found in (set_a, a_neg)
        for item in [*found.problems, *found.warnings]
    ]
    assert [line for line in printed if SENTINEL.casefold() in line.casefold()] == []


def test_guide_explains_the_kinds_and_warnings_to_check():
    """The guide says what these problem kinds and warnings mean, since their names
    alone don't (S-R10). Each is in backticks, as the intake prints it."""
    guide = GUIDE.read_text(encoding="utf-8")
    named = [
        "missing",
        "file_missing",
        "semicolon",
        "unknown",
        "alert_poster=other",
        "same_post=several",
        "nearest=tied",
    ]
    assert [text for text in named if f"`{text}`" not in guide] == []
