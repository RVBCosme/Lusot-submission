"""Tests for the formats: the log templates, Table 5's lists, the id patterns (C221),
dates and times, the consent versions (C218) and the collection guide (spec §5.9, §8)."""

import json
import re
from datetime import datetime
from pathlib import Path

import formats
import pytest
import table

REPO = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = REPO / "eval" / "templates"
GUIDE = REPO / "docs" / "data" / "set-a-collection-guide.md"
SCHEMA = REPO / "backend" / "analysis" / "prompts" / "muse_spark_photo_v1.schema.json"

# Set A's template before C209, written out here so that no edit to formats.py can move
# it: rows Rene logged on it must still read.
TODAYS_TEMPLATE = (
    "candidate_id",
    "logged_on",
    "platform",
    "post_url",
    "poster",
    "post_time_pht",
    "alert_time_pht",
    "spot_text",
    "city",
    "level_label_raw",
    "passability_raw",
    "photo_in_alert_post",
    "photo_file",
    "reference_visible",
    "label_in_image",
    "faces_or_plates",
    "notes",
)


def test_templates_match_the_constants():
    """Each template is its header line alone: UTF-8 without a BOM, ending in \\n."""
    assert formats.TEMPLATES == {
        "set_a_log.csv": formats.SET_A_COLUMNS + formats.SET_A_OPTIONAL,
        "a_neg_log.csv": formats.A_NEG_COLUMNS + ("same_spot_as",),
        "m8_labels.csv": formats.M8_COLUMNS,
        "set_b_cars.csv": formats.CARS_COLUMNS,
        "set_d_log.csv": formats.SET_D_COLUMNS,
        "consented_log.csv": formats.CONSENTED_COLUMNS,
        "sidewalls.csv": formats.SIDEWALLS_COLUMNS,
    }
    for name, columns in formats.TEMPLATES.items():
        path = TEMPLATE_DIR / name
        assert path.read_bytes() == (",".join(columns) + "\n").encode("utf-8"), name
        assert table.read_table(path) == table.Table(columns, []), name


def test_output_columns_are_counted():
    """The manifest and truth.csv hold §5.9's 27 columns each, every name once, so the
    tools that read them back can (table.read_table refuses a repeated name)."""
    for columns in (formats.MANIFEST_COLUMNS, formats.TRUTH_COLUMNS):
        assert len(set(columns)) == len(columns) == 27


def test_set_a_template_keeps_the_17_columns_first():
    """Rows logged on today's 17-column template still read, because C209's optional
    columns come last. A-neg's required columns are those 17 plus surface: the log the
    tracker's checklist v2 has Rene make."""
    columns = table.read_table(TEMPLATE_DIR / "set_a_log.csv").columns
    assert columns[:17] == TODAYS_TEMPLATE
    assert columns[17:] == formats.SET_A_OPTIONAL
    assert formats.SET_A_OPTIONAL == ("same_spot_as", "alert_poster", "alert_spot_text")
    assert formats.SET_A_COLUMNS == TODAYS_TEMPLATE
    assert formats.A_NEG_COLUMNS == TODAYS_TEMPLATE + ("surface",)


def test_table5_lists_match_schema_v1():
    """Table 5's lists are schema v1's enums, in its order. The schema is read as data,
    since eval/ never imports lusot_analysis (C200)."""
    properties = json.loads(SCHEMA.read_text(encoding="utf-8"))["properties"]

    def enum(group: str, field: str) -> tuple[str, ...]:
        return tuple(properties[group]["items"]["properties"][field]["enum"])

    assert formats.VEHICLE_TYPES == enum("vehicles", "type")
    assert formats.BODY_WATERLINES == enum("vehicles", "body_waterline")
    assert formats.WHEEL_WATERLINES == enum("wheels", "waterline")
    assert formats.PERSON_WATERLINES == enum("people", "waterline")
    lists = (
        formats.VEHICLE_TYPES,
        formats.BODY_WATERLINES,
        formats.WHEEL_WATERLINES,
        formats.PERSON_WATERLINES,
    )
    assert [len(values) for values in lists] == [9, 6, 7, 8]


@pytest.mark.parametrize(
    ("name", "example", "near_miss"),
    [
        ("SET_A_ID", "A001", "N001"),
        ("A_NEG_ID", "N015", "A015"),
        ("ITEM_ID", "S001", "S01"),
        ("CAR_ID", "B01", "B001"),
        ("SET_D_ID", "D01", "D1"),
    ],
)
def test_patterns_fit_c221(name, example, near_miss):
    """An example fits its own pattern and C221's, which MS6's loader requires, and a
    near miss doesn't fit the pattern."""
    pattern = getattr(formats, name)
    assert re.fullmatch(pattern, example)
    assert table.is_id(example)
    assert not re.fullmatch(pattern, near_miss)


def test_dates_and_times():
    """Dates are YYYY-MM-DD and times YYYY-MM-DD HH:MM on the 24-hour clock, each a
    real one. A refused time's error never holds the cell's text."""
    assert formats.is_date("2026-08-09")
    bad_dates = ["2026-8-9", "09/08/2026", "2026-02-30"]
    assert [text for text in bad_dates if formats.is_date(text)] == []
    assert formats.is_time("2026-08-09 08:20")
    assert formats.is_time("2026-07-10 14:50")
    bad_times = ["2026-08-09 8:20", "2026-08-09 08:20 AM", "2026-08-09T08:20"]
    assert [text for text in bad_times if formats.is_time(text)] == []
    assert formats.parse_time("2026-07-10 14:50") == datetime(2026, 7, 10, 14, 50)
    with pytest.raises(ValueError) as error:
        formats.parse_time("2026-08-09 8:20")
    assert "8:20" not in str(error.value)


def test_approved_consent_versions():
    """The three consent texts approved on Oct 29 by Claude under Rene's delegation
    (C218). Only M9-v4 counts for M9: no donor answered an earlier version, and v3 was
    never sent. This test changes with the constant when another text is approved."""
    assert formats.APPROVED_CONSENT == {
        "m9": frozenset({"M9-v4"}),
        "set_b": frozenset({"SETB-v1"}),
        "m11": frozenset({"M11-v1"}),
    }


def test_guide_names_every_column():
    """Rene's guide explains every column of every template (spec §8)."""
    guide = GUIDE.read_text(encoding="utf-8")
    missing = {
        column
        for columns in formats.TEMPLATES.values()
        for column in columns
        if f"`{column}`" not in guide
    }
    assert sorted(missing) == []


def test_guide_lists_the_17_city_names():
    """The guide lists, in backticks, each of Metro Manila's 16 cities and Pateros as
    the tools spell it, since Rene writes `city` as listed there."""
    guide = GUIDE.read_text(encoding="utf-8")
    assert len(set(formats.METRO_MANILA)) == len(formats.METRO_MANILA) == 17
    assert [name for name in formats.METRO_MANILA if f"`{name}`" not in guide] == []
