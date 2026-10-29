"""Tests for the check of Set B's cars.csv, eval/set_b/cars.py (spec §5.6, §5.9; C210,
C218, C221, C222).

Every cars.csv and owner's OK is synthetic, under tmp_path. The check reads the log's
text and looks for each owner's OK with a stat.
"""

import re

import cars
import formats
import pytest
import synth
from table import Fact, Finding


def check(folder, rows, side="dev") -> cars.CarsCheck:
    """check_cars on the rows, written with their owners' OKs as folder/cars.csv."""
    return cars.check_cars(synth.set_b_cars(folder, rows), side=side)


def test_clean_log_passes(tmp_path):
    rows = [
        synth.car_row(),
        synth.car_row(photo_file="B01-2.jpg", view="angled"),
        synth.car_row(car_id="B03", vehicle_type="suv_mpv", tire_code="205/55R16"),
    ]
    found = check(tmp_path, rows)
    assert (found.problems, found.warnings, found.drops) == ([], [], {})
    assert [row["photo_file"] for row in found.rows] == [
        "B01-1.jpg",
        "B01-2.jpg",
        "B03-1.jpg",
    ]
    assert [row["#"] for row in found.rows] == ["1", "2", "3"]


def test_missing_column(tmp_path):
    columns = [column for column in formats.CARS_COLUMNS if column != "view"]
    path = synth.write_csv(tmp_path / "cars.csv", columns, [synth.car_row()])
    found = cars.check_cars(path, side="dev")
    assert found.problems == [Finding("cars log", "view", "missing_column")]
    assert (found.warnings, found.drops) == ([], {})


# One problem each, as the cells changed on B01's row and the problem they give.
PROBLEMS = {
    "car_id bad": (
        {"car_id": "B1", "photo_file": "B1-1.jpg"},
        ("row 1", "car_id", "bad_id"),
    ),
    "car_id lowercase": ({"car_id": "b01"}, ("row 1", "car_id", "bad_id")),
    "car_id blank": (
        {"car_id": "", "photo_file": "B01-1.jpg"},
        ("row 1", "car_id", "missing"),
    ),
    "photo_file blank": ({"photo_file": ""}, ("B01", "photo_file", "missing")),
    "photo_file shape": (
        {"photo_file": "B01_1.jpg"},
        ("B01", "photo_file", "bad_name"),
    ),
    "photo_file kind": (
        {"photo_file": "B01-1.heic"},
        ("B01", "photo_file", "bad_name"),
    ),
    "photo_file folder": (
        {"photo_file": "x/B01-1.jpg"},
        ("B01", "photo_file", "bad_name"),
    ),
    "photo_file other car": (
        {"photo_file": "B03-1.jpg"},
        ("B01", "photo_file", "bad_name"),
    ),
    "vehicle_type blank": ({"vehicle_type": ""}, ("B01", "vehicle_type", "missing")),
    "vehicle_type pickup": (
        {"vehicle_type": "pickup"},
        ("B01", "vehicle_type", "not_in_list"),
    ),
    "view blank": ({"view": ""}, ("B01", "view", "missing")),
    "view front": ({"view": "front"}, ("B01", "view", "not_in_list")),
    "taken_on blank": ({"taken_on": ""}, ("B01", "taken_on", "missing")),
    "taken_on no such day": (
        {"taken_on": "2026-10-32"},
        ("B01", "taken_on", "bad_date"),
    ),
    "taken_on shape": ({"taken_on": "29/10/2026"}, ("B01", "taken_on", "bad_date")),
}


@pytest.mark.parametrize(("cells", "expected"), PROBLEMS.values(), ids=list(PROBLEMS))
def test_each_problem(tmp_path, cells, expected):
    found = check(tmp_path, [synth.car_row(**cells)])
    assert found.problems == [Finding(*expected)]


@pytest.mark.parametrize(
    "consent",
    ["../b01-ok.png", "a/../b01-ok.png", "C:/b01-ok.png", "C:b01-ok.png", "/b01-ok.png"]
    + ["\\b01-ok.png", "\\\\server\\share\\b01-ok.png", "b01-ok.png:x", "./b01-ok.png"]
    + ["a//b01-ok.png", "a\\..\\b01-ok.png", "oks/b01-ok.png", "oks\\b01-ok.png"]
    + ["..", ".", "cars.csv", "CARS.CSV"],
)
def test_consent_file_must_be_a_bare_name(tmp_path, consent):
    """S-R29's M3 (amends addition 3): an owner's OK is a bare file name beside
    cars.csv, as set_b_masks takes it, and never cars.csv's own name. Any other is a
    problem, and is never looked for. A subfolder that holds the file doesn't help."""
    folder = tmp_path / "set_b" / "dev"
    (folder / "oks").mkdir(parents=True)
    (folder / "oks" / "b01-ok.png").write_bytes(b"ok")
    path = synth.write_csv(
        folder / "cars.csv",
        formats.CARS_COLUMNS,
        [synth.car_row(consent_file=consent)],
    )
    found = cars.check_cars(path, side="dev")
    assert found.problems == [Finding("B01", "consent_file", "bad_path")]
    assert found.drops == {}


def test_dev_consent_path_inside_sealed_is_refused(tmp_path, capsys):
    """C222: on the development side an owner's OK named sealed is refused before its
    stat."""
    path = synth.write_csv(
        tmp_path / "cars.csv",
        formats.CARS_COLUMNS,
        [synth.car_row(consent_file="sealed")],
    )
    with pytest.raises(SystemExit) as stop:
        cars.check_cars(path, side="dev")
    assert stop.value.code == 2
    assert capsys.readouterr() == ("", "refused: path inside a folder named sealed\n")


@pytest.mark.parametrize("column", ["model", "vehicle_type", "tire_code"])
def test_rows_of_a_car_agree(tmp_path, column):
    """A car's rows must agree on its model, type and tire code: its problem names the
    car once, however many rows differ."""
    other = {"model": "Honda City", "vehicle_type": "van", "tire_code": "185/60R15"}
    rows = [
        synth.car_row(),
        synth.car_row(photo_file="B01-2.jpg", **{column: other[column]}),
        synth.car_row(photo_file="B01-3.jpg", **{column: other[column]}),
    ]
    found = check(tmp_path, rows)
    assert found.problems == [Finding("B01", column, "inconsistent")]


def test_photo_numbers_are_unique(tmp_path):
    """A photo's crops are numbered by its car and photo number, so B01-1.jpg beside
    B01-01.JPG would give two crops one id."""
    rows = [synth.car_row(), synth.car_row(photo_file="B01-01.JPG")]
    assert check(tmp_path, rows).problems == [Finding("B01", "photo_file", "duplicate")]


def test_photo_file_in_any_case(tmp_path):
    found = check(tmp_path, [synth.car_row(photo_file="b01-1.JPEG")])
    assert (found.problems, found.drops) == ([], {})


@pytest.mark.parametrize(
    ("tire_code", "cause"),
    [
        ("195R14C", "no_aspect_ratio"),
        ("7.00R16", "no_aspect_ratio"),
        ("7.50-16", "bad_tire_code"),
        ("295/80R22.5", "bad_tire_code"),
        ("", "bad_tire_code"),
    ],
)
def test_tire_code_drops_the_car(tmp_path, tire_code, cause):
    rows = [synth.car_row(tire_code=tire_code), synth.car_row(car_id="B03")]
    found = check(tmp_path, rows)
    assert (found.problems, found.drops) == ([], {"B01": cause})


def test_blank_consent_drops_the_car(tmp_path):
    rows = [synth.car_row(), synth.car_row(photo_file="B01-2.jpg", consent_file="")]
    found = check(tmp_path, rows)
    assert (found.problems, found.drops) == ([], {"B01": "no_consent"})


def test_missing_consent_file_drops_the_car(tmp_path):
    rows = [synth.car_row(), synth.car_row(car_id="B03")]
    synth.set_b_cars(tmp_path, rows)
    (tmp_path / "b03-ok.png").unlink()
    found = cars.check_cars(tmp_path / "cars.csv", side="dev")
    assert (found.problems, found.drops) == ([], {"B03": "no_consent"})


def test_no_consent_comes_before_the_tire_code(tmp_path):
    """A car without its owner's OK is dropped as no_consent whatever its tire code, so
    nothing of it is ever archived."""
    rows = [synth.car_row(tire_code="195R14C", consent_file="")]
    assert check(tmp_path, rows).drops == {"B01": "no_consent"}


def test_unapproved_version_warns(tmp_path):
    """C218: a version Rene hasn't approved, a blank one included, only warns, once per
    row on either side (S-R29's M4), so the record counts rows."""
    rows = [
        synth.car_row(consent_version="SETB-v0"),
        synth.car_row(photo_file="B01-2.jpg", consent_version="SETB-v0"),
        synth.car_row(car_id="B03", consent_version=""),
    ]
    found = check(tmp_path, rows)
    assert found.warnings == [
        Fact("B01", "consent_version", "unapproved"),
        Fact("B01", "consent_version", "unapproved"),
        Fact("B03", "consent_version", "unapproved"),
    ]
    assert (found.problems, found.drops) == ([], {})
    assert formats.APPROVED_CONSENT["set_b"] == {"SETB-v1"}


def test_final_side_needs_even_numbers(tmp_path):
    """C210: odd numbers are development cars and even ones final."""
    final = check(tmp_path / "a", [synth.car_row(car_id="B02")], side="final")
    assert final.problems == []
    odd = check(tmp_path / "b", [synth.car_row(car_id="B03")], side="final")
    assert odd.problems == [Finding("row 1", "car_id", "wrong_side")]
    even = check(tmp_path / "c", [synth.car_row(car_id="B02")], side="dev")
    assert even.problems == [Finding("B02", "car_id", "wrong_side")]


def test_final_refs_are_row_numbers(tmp_path):
    """C202: on the final side every problem and warning names its row, never a final
    car's id; drops stay keyed by car, which nothing prints."""
    rows = [
        synth.car_row(car_id="B02", consent_version="SETB-v0"),
        synth.car_row(car_id="B02", photo_file="B02-2.jpg", model="Honda City"),
        synth.car_row(car_id="B04", view="front", taken_on="2026-13-01"),
        synth.car_row(car_id="B04", photo_file="B04-1.png", consent_file="../x.png"),
        synth.car_row(car_id="B06", tire_code="195R14C", photo_file="B06-1.heic"),
        synth.car_row(car_id="B1", photo_file="B1-1.jpg"),
    ]
    synth.set_b_cars(tmp_path, rows[:3])
    path = synth.write_csv(tmp_path / "cars.csv", formats.CARS_COLUMNS, rows)
    found = cars.check_cars(path, side="final")
    assert found.problems == [
        Finding("row 2", "model", "inconsistent"),
        Finding("row 3", "view", "not_in_list"),
        Finding("row 3", "taken_on", "bad_date"),
        Finding("row 4", "photo_file", "duplicate"),
        Finding("row 4", "consent_file", "bad_path"),
        Finding("row 5", "photo_file", "bad_name"),
        Finding("row 6", "car_id", "bad_id"),
    ]
    assert found.warnings == [Fact("row 1", "consent_version", "unapproved")]
    assert found.drops == {"B06": "no_consent"}
    for item in [*found.problems, *found.warnings]:
        assert re.fullmatch(r"row [0-9]+", item.ref)
        assert re.search(r"B0[246]", str(item)) is None


def test_side_must_be_dev_or_final(tmp_path):
    path = synth.set_b_cars(tmp_path, [synth.car_row()])
    with pytest.raises(ValueError, match="side"):
        cars.check_cars(path, side="sealed")
