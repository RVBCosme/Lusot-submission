"""Tests for the checks of Rene's M8 export (C208), consented items' log (M9) and
sidewall photos' log (M11), with their consent records (spec §5.3, §5.9, C218).

Every log is synthetic. Each file a log names is an empty file beside it, since the
checks only stat it (C201).
"""

import formats
import otherlogs
import pytest
import synth
from table import Fact, Finding

SET_A = ("A001", "A002")
SEALED_NAME = "../sealed/x.png"


@pytest.fixture(autouse=True)
def approved(monkeypatch):
    """Approve the versions the rows below give (C218). The real sets now hold M9-v4,
    SETB-v1 and M11-v1, so these tests patch their own synthetic versions and never
    depend on them. A test that needs another set patches it again."""
    monkeypatch.setitem(formats.APPROVED_CONSENT, "m9", frozenset({"M9-v3"}))
    monkeypatch.setitem(formats.APPROVED_CONSENT, "m11", frozenset({"M11-v1"}))


def m8_photo(photo_id="A001", **cells):
    """The photo row of the M8 export, P1, which holds the photo's marks (C208)."""
    return {
        "photo_id": photo_id,
        "ref_id": "P1",
        "kind": "photo",
        "quality": "ok",
    } | cells


def m8_ref(kind="wheel", **cells):
    """A reference row, A001's R1 unless given: its point and its kind's values."""
    values = {
        "vehicle": {"vehicle_type": "sedan_hatch", "body_waterline": "bumper"},
        "wheel": {"waterline": "hub"},
        "person": {"waterline": "knee"},
    }
    row = {"photo_id": "A001", "ref_id": "R1", "kind": kind, "x": "0.5", "y": "0.25"}
    return row | values.get(kind, {}) | cells


def check_m8(base, rows, *, columns=formats.M8_COLUMNS, ids=SET_A, allow_missing=False):
    path = synth.write_csv(base / "m8_labels.csv", columns, rows)
    return otherlogs.check_m8(path, ids, allow_missing=allow_missing)


# Both Set A photos' photo rows, so that each case below has only its own problem.
PHOTOS = [m8_photo(), m8_photo("A002")]
WITHOUT_X = tuple(column for column in formats.M8_COLUMNS if column != "x")
M8_CASES = [
    pytest.param(
        PHOTOS,
        {"columns": WITHOUT_X},
        [Finding("m8 log", "x", "missing_column")],
        id="missing_column",
    ),
    pytest.param(
        [*PHOTOS, m8_photo("A009")],
        {},
        [Finding("m8 row 3", "photo_id", "unknown_photo")],
        id="unknown_photo",
    ),
    pytest.param(
        [*PHOTOS, m8_photo("N001")],
        {},
        [Finding("m8 row 3", "photo_id", "unknown_photo")],
        id="a_neg_photo",
    ),
    pytest.param(
        [*PHOTOS, m8_ref(photo_id="")],
        {},
        [Finding("m8 row 3", "photo_id", "missing")],
        id="missing_photo_id",
    ),
    pytest.param(
        [*PHOTOS, m8_ref(ref_id="")],
        {},
        [Finding("m8 row 3", "ref_id", "missing")],
        id="missing_ref_id",
    ),
    pytest.param(
        [*PHOTOS, m8_ref(ref_id="R01"), m8_ref(ref_id="r2"), m8_ref(ref_id="P2")],
        {},
        [
            Finding("m8 row 3", "ref_id", "bad_ref"),
            Finding("m8 row 4", "ref_id", "bad_ref"),
            Finding("m8 row 5", "ref_id", "bad_ref"),
        ],
        id="bad_ref",
    ),
    pytest.param(
        [*PHOTOS, m8_ref(ref_id="P1")],
        {},
        [Finding("A001", "P1.ref_id", "bad_ref")],
        id="p1_on_a_wheel",
    ),
    pytest.param(
        [*PHOTOS, m8_photo(ref_id="R1")],
        {},
        [Finding("A001", "R1.ref_id", "bad_ref")],
        id="r1_on_a_photo_row",
    ),
    pytest.param(
        [*PHOTOS, m8_ref(), m8_ref()],
        {},
        [Finding("A001", "R1.ref_id", "duplicate_ref")],
        id="duplicate_ref",
    ),
    pytest.param(
        [*PHOTOS, m8_photo()],
        {},
        [Finding("A001", "P1.ref_id", "duplicate_ref")],
        id="duplicate_photo_row",
    ),
    pytest.param(
        [*PHOTOS, m8_ref(kind="")],
        {},
        [Finding("A001", "R1.kind", "missing")],
        id="missing_kind",
    ),
    pytest.param(
        [*PHOTOS, m8_ref(kind="car")],
        {},
        [Finding("A001", "R1.kind", "not_in_list")],
        id="kind",
    ),
    pytest.param(
        [*PHOTOS, m8_ref("vehicle", vehicle_type="car")],
        {},
        [Finding("A001", "R1.vehicle_type", "not_in_list")],
        id="vehicle_type",
    ),
    pytest.param(
        [*PHOTOS, m8_ref("vehicle", body_waterline="roof")],
        {},
        [Finding("A001", "R1.body_waterline", "not_in_list")],
        id="body_waterline",
    ),
    pytest.param(
        [*PHOTOS, m8_ref("wheel", waterline="knee")],  # a person's value
        {},
        [Finding("A001", "R1.waterline", "not_in_list")],
        id="wheel_waterline",
    ),
    pytest.param(
        [*PHOTOS, m8_ref("person", waterline="hub")],  # a wheel's value
        {},
        [Finding("A001", "R1.waterline", "not_in_list")],
        id="person_waterline",
    ),
    pytest.param(
        [m8_photo(quality="good"), m8_photo("A002")],
        {},
        [Finding("A001", "P1.quality", "not_in_list")],
        id="quality",
    ),
    pytest.param(
        [m8_photo(subsets="splash;rain;snow"), m8_photo("A002")],
        {},
        [Finding("A001", "P1.subsets", "not_in_list")],
        id="subset_tag",
    ),
    pytest.param(
        [*PHOTOS, m8_ref(x="1.5")],
        {},
        [Finding("A001", "R1.x", "out_of_range")],
        id="x_above_1",
    ),
    pytest.param(
        [*PHOTOS, m8_ref(y="-0.25")],
        {},
        [Finding("A001", "R1.y", "out_of_range")],
        id="y_below_0",
    ),
    pytest.param(
        [*PHOTOS, m8_ref(x="middle")],
        {},
        [Finding("A001", "R1.x", "out_of_range")],
        id="x_not_a_number",
    ),
    pytest.param(
        [*PHOTOS, m8_ref(x="")],
        {},
        [Finding("A001", "R1.x", "missing")],
        id="missing_x",
    ),
    pytest.param(
        [*PHOTOS, m8_ref("vehicle", vehicle_type="", body_waterline="")],
        {},
        [
            Finding("A001", "R1.vehicle_type", "missing"),
            Finding("A001", "R1.body_waterline", "missing"),
        ],
        id="missing_vehicle_values",
    ),
    pytest.param(
        [*PHOTOS, m8_ref("person", waterline="")],
        {},
        [Finding("A001", "R1.waterline", "missing")],
        id="missing_waterline",
    ),
    pytest.param(
        [m8_photo(quality=""), m8_photo("A002")],
        {},
        [Finding("A001", "P1.quality", "missing")],
        id="missing_quality",
    ),
    pytest.param(
        [*PHOTOS, m8_ref(waterline="Hub")],  # the page writes its values as listed
        {},
        [Finding("A001", "R1.waterline", "not_in_list")],
        id="value_in_capitals",
    ),
    pytest.param(
        [m8_photo(), m8_ref(photo_id="A002")],  # A002 has a reference, but no marks
        {},
        [Finding("A002", "m8", "no_photo_row")],
        id="no_photo_row",
    ),
]


@pytest.mark.parametrize(("rows", "options", "expected"), M8_CASES)
def test_each_m8_problem_kind(tmp_path, rows, options, expected):
    """Each kind alone. A row whose photo or ref_id can't be read is named by its row,
    after the log's name; the rest read <photo_id> <ref_id>.<column>. A photo row's tags
    outside the list give one problem."""
    assert check_m8(tmp_path, rows, **options).problems == expected


def test_m8_photo_row_only_is_fine(tmp_path):
    """A photo with nothing Rene can read gets its photo row only (C208). The check keeps
    every row as read, numbered."""
    rows = [m8_photo(), m8_photo("A002", quality="dark", subsets="reflection")]
    found = check_m8(tmp_path, rows)
    assert (found.problems, found.missing_photo_rows) == ([], [])
    assert [(row["#"], row["photo_id"]) for row in found.rows] == [
        ("1", "A001"),
        ("2", "A002"),
    ]


def test_m8_export_from_the_page_reads_cleanly(tmp_path):
    """An export as the page writes one: each kind of reference, points from 0 to 1 to
    four decimals, and several subset tags joined by ;."""
    rows = [
        m8_photo(subsets="reflection;splash;moving"),
        m8_ref("vehicle", x="0.1234", y="1", body_waterline="door_sill"),
        m8_ref("wheel", ref_id="R2", x="0", y="0.9999", waterline="rim_top"),
        m8_ref("person", ref_id="R3", x="1", y="0", waterline="above_chest"),
        m8_photo("A002", quality="blurry"),
    ]
    found = check_m8(tmp_path, rows)
    assert (found.problems, found.missing_photo_rows) == ([], [])
    assert len(found.rows) == 5


def test_allow_missing_turns_off_no_photo_row(tmp_path):
    """The split stops on a missing photo row unless Rene passes --allow-missing-m8
    (C204), so the photos without one are listed either way, in id order."""
    rows = [m8_photo("A002")]
    ids = ("A003", "A002", "A001")
    found = check_m8(tmp_path / "default", rows, ids=ids)
    assert found.problems == [
        Finding("A001", "m8", "no_photo_row"),
        Finding("A003", "m8", "no_photo_row"),
    ]
    assert found.missing_photo_rows == ["A001", "A003"]
    found = check_m8(tmp_path / "allowed", rows, ids=ids, allow_missing=True)
    assert (found.problems, found.missing_photo_rows) == ([], ["A001", "A003"])


def consented_row(**cells):
    """A row of the consented items' log that passes every check once its version is
    approved, as the fixture above approves it."""
    row = {
        "item_id": "S001",
        "file": "S001.jpg",
        "kind": "photo",
        "taken_pht": "2026-08-09 08:20",
        "place_text": "España Blvd. cor. Lacson Ave.",
        "lat": "14.6100",
        "lon": "120.9900",
        "people": "nobody",
        "source_note": "taken by a friend",
        "consent_file": "S001-ok.png",
        "consent_version": "M9-v3",
        "notes": "",
    }
    row.update(cells)
    return row


def sidewall_row(**cells):
    """A row of the sidewall photos' log that passes every check, with no warning once
    its version is approved."""
    row = {
        "photo_file": "jeepney-1.jpg",
        "vehicle": "jeepney",
        "model": "",
        "tire_code": "7.50-16",
        "checked_code": "",
        "taken_on": "2026-10-29",
        "consent_file": "jeepney-ok.png",
        "consent_version": "M11-v1",
        "notes": "",
    }
    row.update(cells)
    return row


def named(base, rows, columns, files):
    """Make each file the rows name in these columns an empty file in base, unless files
    names them."""
    if files is None:
        files = {row[column] for row in rows for column in columns if row.get(column)}
    for name in files:
        (base / name).touch()


def check_consented(base, rows, *, columns=formats.CONSENTED_COLUMNS, files=None):
    log = synth.write_csv(base / "consented_log.csv", columns, rows)
    named(base, rows, ("file", "consent_file"), files)
    return otherlogs.check_consented(log)


def check_sidewalls(base, rows, *, columns=formats.SIDEWALLS_COLUMNS, files=None):
    log = synth.write_csv(base / "sidewalls.csv", columns, rows)
    named(base, rows, ("photo_file", "consent_file"), files)
    return otherlogs.check_sidewalls(log)


CONSENTED_CASES = [
    pytest.param(
        [consented_row()],
        {"columns": tuple(c for c in formats.CONSENTED_COLUMNS if c != "lat")},
        [Finding("consented log", "lat", "missing_column")],
        id="missing_column",
    ),
    pytest.param(
        [consented_row(item_id="S01"), consented_row(item_id="A001")],
        {},
        [
            Finding("consented row 1", "item_id", "bad_id"),
            Finding("consented row 2", "item_id", "bad_id"),
        ],
        id="bad_id",
    ),
    pytest.param(
        [consented_row(item_id="")],
        {},
        [Finding("consented row 1", "item_id", "missing")],
        id="missing_id",
    ),
    pytest.param(
        [consented_row(file="")],
        {},
        [Finding("S001", "file", "missing")],
        id="missing_file",
    ),
    pytest.param(
        [consented_row()],
        {"files": {"S001-ok.png"}},
        [Finding("S001", "file", "file_missing")],
        id="file_missing",
    ),
    pytest.param(
        [consented_row(kind="video")],
        {},
        [Finding("S001", "kind", "not_in_list")],
        id="kind",
    ),
    pytest.param(
        [consented_row(taken_pht="2026-08-09")],
        {},
        [Finding("S001", "taken_pht", "bad_time")],
        id="bad_time",
    ),
    pytest.param(
        [consented_row(lat="91"), consented_row(item_id="S002", lat="14.61 N")],
        {},
        [
            Finding("S001", "lat", "out_of_range"),
            Finding("S002", "lat", "out_of_range"),
        ],
        id="lat",
    ),
    pytest.param(
        [consented_row(lon="-180.5")],
        {},
        [Finding("S001", "lon", "out_of_range")],
        id="lon",
    ),
    pytest.param(
        [consented_row(taken_pht="", lat="", lon="")],
        {},
        [
            Finding("S001", "taken_pht", "missing"),
            Finding("S001", "lat", "missing"),
            Finding("S001", "lon", "missing"),
        ],
        id="missing_time_and_place",
    ),
    pytest.param(
        [consented_row(consent_file="")],
        {},
        [Finding("S001", "consent_file", "missing")],
        id="missing_consent_file",
    ),
    pytest.param(
        [consented_row()],
        {"files": {"S001.jpg"}},
        [Finding("S001", "consent_file", "file_missing")],
        id="consent_file_missing",
    ),
    pytest.param(
        [consented_row(consent_version="")],
        {},
        [Finding("S001", "consent_version", "missing")],
        id="missing_version",
    ),
]


@pytest.mark.parametrize(("rows", "options", "expected"), CONSENTED_CASES)
def test_each_consented_problem_kind(tmp_path, rows, options, expected):
    assert check_consented(tmp_path, rows, **options) == (expected, [])


def test_consented_log_reads_cleanly(tmp_path):
    """Each kind of item, in any case, and the coordinates' limits."""
    rows = [
        consented_row(lat="-90", lon="180"),
        consented_row(
            item_id="S002", file="S002.mp4", kind="Clip", lat="90", lon="-180"
        ),
        consented_row(item_id="S003", file="S003.jpg", lat="14", lon="121"),
    ]
    assert check_consented(tmp_path, rows) == ([], [])


def test_a_repeated_item_id_is_a_problem_printed_once(tmp_path):
    """S-R11's M5: each item has one row, and G1's demo pins are keyed by its id, so a
    repeated item_id is a problem, printed once however often it repeats. A repeat is
    checked no further, so the first row's problems print once too."""
    rows = [
        consented_row(kind="video"),
        consented_row(kind="video"),
        consented_row(item_id="S002", file="S002.jpg"),
        consented_row(kind="video"),
    ]
    assert check_consented(tmp_path, rows) == (
        [
            Finding("S001", "kind", "not_in_list"),
            Finding("S001", "item_id", "duplicate"),
        ],
        [],
    )


def test_m9_version_must_be_approved(tmp_path, monkeypatch):
    """The intake accepts only a donor message's version that Rene has approved (C218)."""
    monkeypatch.setitem(formats.APPROVED_CONSENT, "m9", frozenset({"M9-v2"}))
    rows = [consented_row(consent_version="M9-v2")]
    assert check_consented(tmp_path / "v2", rows) == ([], [])
    rows = [consented_row(consent_version="M9-v1")]
    assert check_consented(tmp_path / "v1", rows) == (
        [Finding("S001", "consent_version", "not_approved")],
        [],
    )


SIDEWALL_CASES = [
    pytest.param(
        [sidewall_row()],
        {"columns": tuple(c for c in formats.SIDEWALLS_COLUMNS if c != "vehicle")},
        [Finding("sidewalls log", "vehicle", "missing_column")],
        id="missing_column",
    ),
    pytest.param(
        [sidewall_row(photo_file="")],
        {},
        [Finding("sidewalls row 1", "photo_file", "missing")],
        id="missing_photo_file",
    ),
    pytest.param(
        [sidewall_row()],
        {"files": {"jeepney-ok.png"}},
        [Finding("sidewalls row 1", "photo_file", "file_missing")],
        id="photo_file_missing",
    ),
    pytest.param(
        [sidewall_row(vehicle="")],
        {},
        [Finding("sidewalls row 1", "vehicle", "missing")],
        id="missing_vehicle",
    ),
    pytest.param(
        [sidewall_row(), sidewall_row(photo_file="truck-1.jpg", vehicle="truck")],
        {},
        [Finding("sidewalls row 2", "vehicle", "not_in_list")],
        id="vehicle",
    ),
    pytest.param(
        [sidewall_row(taken_on="")],
        {},
        [Finding("sidewalls row 1", "taken_on", "missing")],
        id="missing_date",
    ),
    pytest.param(
        [sidewall_row(taken_on="29/10/2026")],
        {},
        [Finding("sidewalls row 1", "taken_on", "bad_date")],
        id="bad_date",
    ),
    pytest.param(
        [sidewall_row(consent_file="")],
        {},
        [Finding("sidewalls row 1", "consent_file", "missing")],
        id="missing_consent_file",
    ),
    pytest.param(
        [sidewall_row()],
        {"files": {"jeepney-1.jpg"}},
        [Finding("sidewalls row 1", "consent_file", "file_missing")],
        id="consent_file_missing",
    ),
]


@pytest.mark.parametrize(("rows", "options", "expected"), SIDEWALL_CASES)
def test_each_sidewall_problem_kind(tmp_path, rows, options, expected):
    """The log has no id column, so each problem names its row, after the log's name."""
    assert check_sidewalls(tmp_path, rows, **options) == (expected, [])


def test_sidewalls_log_reads_cleanly(tmp_path):
    """Each vehicle in any case, and a model and checked code left blank."""
    rows = [
        sidewall_row(),
        sidewall_row(photo_file="tricycle-1.jpg", vehicle="Tricycle"),
        sidewall_row(photo_file="bus-1.jpg", vehicle="BUS", tire_code="11R22.5"),
    ]
    assert check_sidewalls(tmp_path, rows) == ([], [])


def test_m11_version_only_warns(tmp_path, monkeypatch):
    """A driver's permission whose text Rene hasn't approved, or with no version, is a
    warning, so M11 isn't held up (C218)."""
    monkeypatch.setitem(formats.APPROVED_CONSENT, "m11", frozenset({"M11-v2"}))
    rows = [sidewall_row(consent_version="M11-v2")]
    assert check_sidewalls(tmp_path / "v2", rows) == ([], [])
    for version in ("M11-v1", ""):
        rows = [sidewall_row(consent_version=version)]
        assert check_sidewalls(tmp_path / (version or "blank"), rows) == (
            [],
            [Fact("sidewalls row 1", "consent_version", "unapproved")],
        )


@pytest.mark.parametrize(
    ("tire_code", "checked_code", "warned"),
    [
        ("185/60R15", "", False),
        ("185/60 R15", "185/60r15", False),
        ("7.50-16", "7.50 - 16", False),
        ("185/60R15", "185/65R15", True),
        ("", "185/65R15", True),
    ],
)
def test_sidewall_code_mismatch_warns(tmp_path, tire_code, checked_code, warned):
    """Claude's reading, once filled, must be Rene's, compared in capitals without
    spaces. A mismatch is a warning."""
    rows = [sidewall_row(tire_code=tire_code, checked_code=checked_code)]
    expected = [Fact("sidewalls row 1", "code", "mismatch")] if warned else []
    assert check_sidewalls(tmp_path, rows) == ([], expected)


@pytest.mark.parametrize("log", ["consented", "sidewalls"])
def test_a_checked_column_without_its_own_check_raises(tmp_path, monkeypatch, log):
    """S-R11's M4: a column added to a log's checked columns without a check of its own
    stops the run, instead of being checked as another column is."""
    error = pytest.raises(ValueError, match="no check for the column notes")
    if log == "consented":
        checked = otherlogs._CONSENTED_CHECKED + ("notes",)
        monkeypatch.setattr(otherlogs, "_CONSENTED_CHECKED", checked)
        with error:
            check_consented(tmp_path, [consented_row(notes="x")])
    else:
        checked = otherlogs._SIDEWALLS_CHECKED + ("notes",)
        monkeypatch.setattr(otherlogs, "_SIDEWALLS_CHECKED", checked)
        with error:
            check_sidewalls(tmp_path, [sidewall_row(notes="x")])


@pytest.mark.parametrize(
    ("log", "column"),
    [
        ("consented", "file"),
        ("consented", "consent_file"),
        ("sidewalls", "photo_file"),
        ("sidewalls", "consent_file"),
    ],
)
def test_a_named_file_in_a_sealed_folder_is_refused(tmp_path, capsys, log, column):
    """A file a log names is refused before its stat when a part of its path names
    sealed (C222), as the M8 sheet refuses a photo's. The sealed folder is a name only,
    and none is created."""
    base = tmp_path / "log"
    base.mkdir()
    if log == "consented":
        row = consented_row(**{column: SEALED_NAME})
        files = {row["file"], row["consent_file"]} - {SEALED_NAME}
        with pytest.raises(SystemExit) as stop:
            check_consented(base, [row], files=files)
    else:
        row = sidewall_row(**{column: SEALED_NAME})
        files = {row["photo_file"], row["consent_file"]} - {SEALED_NAME}
        with pytest.raises(SystemExit) as stop:
            check_sidewalls(base, [row], files=files)
    assert stop.value.code == 2
    assert capsys.readouterr().err == "refused: path inside a folder named sealed\n"
    assert not (tmp_path / "sealed").exists()
