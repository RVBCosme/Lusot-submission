"""Tests for the manifest and M8 rows, and the counts per fact value (C207, §5.9).

Every photo and row is synthetic, built here.
"""

from datetime import datetime

import formats
import manifest
import photos
import setlogs

FACTS = photos.PhotoFacts(
    sha256="a1" * 32, dhash="9ca95593565bb5b7", decodes=True, width=1600, height=1200
)


def photo(**fields: object) -> setlogs.Photo:
    """A Set A photo with every fact its log rows give, from a separate post that two
    other alerts also fit. Each keyword sets one field."""
    values: dict[str, object] = {
        "photo_id": "A005",
        "set": "A",
        "photo_file": "A005.JPG",
        "event_date": "2026-08-09",
        "post_time": datetime(2026, 8, 9, 8, 20),
        "city": "Quezon City",
        "metro_manila": "yes",
        "spot_key": "edsa|kamuning",
        "same_spot_as": frozenset({"A012", "A003"}),
        "poster_kind": "city",
        "match": "separate_post",
        "level_label_raw": 'Gutter deep, 8"',
        "passability_raw": "NPLV",
        "other_alerts_raw": 'Half-knee deep, 10";Knee deep, 19"',
        "label_in_image": "cropped",
        "reference_visible": "both",
        "faces_or_plates": "yes",
        "surface": "",
        "notes": "reposted twice | tilted",
        "rows": 3,
    }
    values.update(fields)
    return setlogs.Photo(**values)


def cells(photo_id: str, event_id: str, **facts: str) -> dict[str, str]:
    """A manifest row with every column, blank unless given. Each keyword sets one cell."""
    row = dict.fromkeys(formats.MANIFEST_COLUMNS, "")
    row.update(photo_id=photo_id, event_id=event_id, city="Manila", **facts)
    return row


def m8_row(number: int, **values: str) -> dict[str, str]:
    """A row as the intake reads Rene's export: every M8 column, blank unless given, the
    row's number under "#", and a column his export may add."""
    row = dict.fromkeys(formats.M8_COLUMNS, "")
    row.update(values)
    row["#"] = str(number)
    row["comment"] = "Sentinel comment"
    return row


def test_manifest_columns_and_values():
    """Every column of §5.9's manifest, from the photo's facts, its event and its side.
    same_spot_as is sorted and joined by ;."""
    row = manifest.manifest_row(
        photo(), FACTS, event_id="E02", split="sealed", duplicate_of=""
    )
    assert row.keys() == set(formats.MANIFEST_COLUMNS)
    assert row == {
        "photo_id": "A005",
        "set": "A",
        "split": "sealed",
        "event_id": "E02",
        "event_date": "2026-08-09",
        "city": "Quezon City",
        "metro_manila": "yes",
        "spot_key": "edsa|kamuning",
        "same_spot_as": "A003;A012",
        "poster_kind": "city",
        "match": "separate_post",
        "level_label_raw": 'Gutter deep, 8"',
        "passability_raw": "NPLV",
        "other_alerts_raw": 'Half-knee deep, 10";Knee deep, 19"',
        "label_in_image": "cropped",
        "reference_visible": "both",
        "faces_or_plates": "yes",
        "surface": "",
        "duplicate": "no",
        "duplicate_of": "",
        "decodes": "yes",
        "photo_file": "A005.JPG",
        "photo_sha256": "a1" * 32,
        "photo_dhash": "9ca95593565bb5b7",
        "width": "1600",
        "height": "1200",
        "notes": "reposted twice | tilted",
    }


def test_a_neg_row_keeps_its_surface():
    """An A-neg photo has no alert and no link here, its poster is other, and its
    surface is set."""
    neg = photo(
        photo_id="N002",
        set="A-neg",
        photo_file="N002.jpg",
        same_spot_as=frozenset(),
        poster_kind="other",
        match="",
        level_label_raw="none",
        passability_raw="",
        other_alerts_raw="",
        surface="wet",
    )
    row = manifest.manifest_row(
        neg, FACTS, event_id="E01", split="dev", duplicate_of=""
    )
    assert (row["set"], row["surface"], row["poster_kind"]) == ("A-neg", "wet", "other")
    labels = (row["match"], row["level_label_raw"], row["passability_raw"])
    assert (labels, row["same_spot_as"]) == (("", "none", ""), "")


def test_duplicate_fields():
    """§5.5 step 2: a duplicate group's lowest id, A003, stands for the group. It keeps
    duplicate = no and names itself; the others say yes and name A003. A photo in no
    group says no and leaves duplicate_of blank."""

    def fields(photo_id: str, duplicate_of: str) -> tuple[str, str]:
        row = manifest.manifest_row(
            photo(photo_id=photo_id, photo_file=f"{photo_id}.jpg"),
            FACTS,
            event_id="E01",
            split="dev",
            duplicate_of=duplicate_of,
        )
        return row["duplicate"], row["duplicate_of"]

    assert fields("A003", "A003") == ("no", "A003")
    assert fields("A007", "A003") == ("yes", "A003")
    assert fields("A009", "A003") == ("yes", "A003")
    assert fields("A004", "") == ("no", "")


def test_undecodable_row():
    """A photo OpenCV doesn't decode keeps its SHA-256, so identical files still join,
    and its dHash, width and height are blank (Review Focus 2, Task 9)."""
    facts = photos.PhotoFacts(
        sha256="c4" * 32, dhash="", decodes=False, width=None, height=None
    )
    row = manifest.manifest_row(
        photo(), facts, event_id="E01", split="dev", duplicate_of=""
    )
    columns = ("decodes", "photo_sha256", "photo_dhash", "width", "height")
    assert [row[column] for column in columns] == ["no", "c4" * 32, "", "", ""]


def test_m8_rows_keep_the_photos_rows_in_input_order():
    """The rows of the photos asked for, in the export's order, each cut to M8's ten
    columns: the reader's row number and a column Rene's export adds stay out."""
    rows = [
        m8_row(1, photo_id="A002", ref_id="P1", kind="photo", quality="ok"),
        m8_row(
            2,
            photo_id="A001",
            ref_id="P1",
            kind="photo",
            quality="dark",
            subsets="reflection;splash",
        ),
        m8_row(3, photo_id="A003", ref_id="P1", kind="photo", quality="ok"),
        m8_row(
            4,
            photo_id="A001",
            ref_id="R1",
            kind="wheel",
            x="0.25",
            y="0.75",
            waterline="hub",
        ),
        m8_row(
            5,
            photo_id="A002",
            ref_id="R1",
            kind="person",
            x="0.5",
            y="0.4",
            waterline="knee",
        ),
    ]
    blank = dict.fromkeys(formats.M8_COLUMNS, "")
    assert manifest.m8_rows(rows, ["A002", "A001"]) == [
        blank | {"photo_id": "A002", "ref_id": "P1", "kind": "photo", "quality": "ok"},
        blank
        | {
            "photo_id": "A001",
            "ref_id": "P1",
            "kind": "photo",
            "quality": "dark",
            "subsets": "reflection;splash",
        },
        blank
        | {
            "photo_id": "A001",
            "ref_id": "R1",
            "kind": "wheel",
            "x": "0.25",
            "y": "0.75",
            "waterline": "hub",
        },
        blank
        | {
            "photo_id": "A002",
            "ref_id": "R1",
            "kind": "person",
            "x": "0.5",
            "y": "0.4",
            "waterline": "knee",
        },
    ]


def test_counts_by_fact_value():
    """Set A's rows and events, and each fact's values counted. The city and the other
    text columns are never counted, and Set A's facts have no surface."""
    rows = [
        cells(
            "A001",
            "E01",
            poster_kind="mmda",
            match="same_post",
            metro_manila="yes",
            label_in_image="no",
            reference_visible="wheel",
            faces_or_plates="yes",
            duplicate="no",
            decodes="yes",
        ),
        cells(
            "A002",
            "E01",
            poster_kind="city",
            match="separate_post",
            metro_manila="yes",
            label_in_image="cropped",
            reference_visible="person",
            faces_or_plates="no",
            duplicate="yes",
            decodes="yes",
        ),
        cells(
            "A003",
            "E02",
            poster_kind="other",
            match="none",
            metro_manila="no",
            label_in_image="yes",
            reference_visible="both",
            faces_or_plates="no",
            duplicate="no",
            decodes="no",
        ),
        cells(
            "A004",
            "E03",
            poster_kind="mmda",
            match="same_post",
            metro_manila="yes",
            label_in_image="no",
            reference_visible="wheel",
            faces_or_plates="no",
            duplicate="no",
            decodes="yes",
        ),
    ]
    assert manifest.counts(rows) == {
        "rows": 4,
        "events": 3,
        "facts": {
            "poster_kind": {"mmda": 2, "city": 1, "other": 1},
            "match": {"same_post": 2, "separate_post": 1, "none": 1},
            "metro_manila": {"yes": 3, "no": 1},
            "label_in_image": {"no": 2, "cropped": 1, "yes": 1},
            "reference_visible": {"wheel": 2, "person": 1, "both": 1},
            "duplicate": {"no": 3, "yes": 1},
            "decodes": {"yes": 3, "no": 1},
        },
    }


def test_counts_count_a_negs_surface():
    """A-neg's rows carry a surface, so it is counted too. Its match is blank."""
    a_neg = {
        "poster_kind": "other",
        "match": "",
        "metro_manila": "yes",
        "label_in_image": "no",
        "reference_visible": "none",
        "duplicate": "no",
        "decodes": "yes",
    }
    rows = [
        cells("N001", "E01", surface="wet", **a_neg),
        cells("N002", "E01", surface="dry", **a_neg),
        cells("N003", "E02", surface="dry", **a_neg),
    ]
    assert manifest.counts(rows) == {
        "rows": 3,
        "events": 2,
        "facts": {
            "poster_kind": {"other": 3},
            "match": {"": 3},
            "metro_manila": {"yes": 3},
            "label_in_image": {"no": 3},
            "reference_visible": {"none": 3},
            "duplicate": {"no": 3},
            "decodes": {"yes": 3},
            "surface": {"wet": 1, "dry": 2},
        },
    }
