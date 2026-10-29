"""Set B's cars.csv: Rene's log of the parked cars, one row per photo (spec §5.6, §5.9;
C210, C218, C221, C222).

The check reads the log's text, and looks for each owner's OK beside cars.csv with a
stat, never reading it. A problem stops the generator, a dropped car is left out and
counted by its cause, and a warning only prints. On the final side each problem and
warning names its row, as row 3, never a final car's id (C202).

generate.py puts eval/data on sys.path before it imports this module, and so do the
tests' conftest files.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import formats
import guards
import table
import tires
from table import Fact, Finding

SIDES = ("dev", "final")
# A photo's file: its car, then the photo's number, in any case, as set_b_masks takes it
# (Task 5). Its masks are filed by its stem, and its crops by its car and number.
PHOTO_FILE = re.compile(
    formats.CAR_ID + r"-([0-9]{1,2})\.(jpg|jpeg|png)", re.IGNORECASE
)
# The columns all of a car's rows must agree on.
CAR_COLUMNS = ("model", "vehicle_type", "tire_code")
# The columns read in any case and lower-cased, as the logs' list values are.
LIST_COLUMNS = ("vehicle_type", "view")


@dataclass
class CarsCheck:
    """cars.csv's rows as read, in its order, each with "#", its row number; their
    problems and warnings; and each dropped car, by its id, with its cause. drops is
    keyed by car id, so it never prints or reaches a record as it is: only its causes
    are counted (S-R16)."""

    rows: list[dict[str, str]]
    problems: list[Finding]
    warnings: list[Fact]
    drops: dict[str, str]


def check_cars(path: Path, *, side: str) -> CarsCheck:
    """Check Set B's cars.csv on one side, dev or final (C210). Any other side raises
    ValueError, and a malformed CSV raises table.MalformedCsv.

    A missing column gives `cars log <column>: missing_column`, and then no row is
    checked. A row whose car_id isn't B and two digits is named as row n, with bad_id
    (missing when blank), and checked no further. Each other problem names the car, or
    on the final side the row, once:
    - car_id: wrong_side for an even number on dev or an odd one on final
    - photo_file: missing; bad_name unless it is the car's own <car>-<n>.<jpg|jpeg|png>
      in any case; duplicate when the car already has a photo n, since its crops are
      numbered by the car and n
    - model, vehicle_type and tire_code: inconsistent where a row differs from the
      car's first row
    - vehicle_type: missing, or not_in_list unless one of formats.SET_B_TYPES
    - view: missing, or not_in_list unless side or angled
    - taken_on: missing, or bad_date unless YYYY-MM-DD
    - consent_file: bad_path unless it is a bare file name beside cars.csv, as
      set_b_masks takes it, and not cars.csv's own name in any case (S-R29's M3,
      amending addition 3)
    vehicle_type and view are read in any case: each is lower-cased in rows first, as
    the logs' list values are, so the truth and the counts hold the list's spelling
    (M-5). Each row whose consent_version Rene hasn't approved, a blank one included, warns
    consent_version=unapproved (C218), once per row on either side, so the warnings
    count rows (S-R29's M4).

    Each car is then dropped by its first cause, in this order: no_consent when any of
    its rows has a blank consent_file or names a file that isn't there, so nothing of a
    car without its owner's OK is ever archived; else no_aspect_ratio or bad_tire_code,
    as tires.parse_tire_code reads its first row's code. A bad_path is never looked
    for. On the dev side each owner's OK is refused if its path names sealed (C222),
    before its stat.
    """
    if side not in SIDES:
        raise ValueError("side is dev or final")
    found = table.read_table(path)
    missing = [
        Finding("cars log", column, "missing_column")
        for column in formats.CARS_COLUMNS
        if column not in found.columns
    ]
    if missing:
        return CarsCheck(found.rows, missing, [], {})
    for row in found.rows:  # a spreadsheet may capitalise a list value (M-5)
        for column in LIST_COLUMNS:
            row[column] = row[column].lower()
    final = side == "final"
    problems: list[Finding] = []
    warnings: list[Fact] = []
    cars: dict[str, list[dict[str, str]]] = {}
    numbers: set[tuple[str, int]] = set()
    for row in found.rows:
        car = row["car_id"]
        if re.fullmatch(formats.CAR_ID, car) is None:
            kind = "bad_id" if car else "missing"
            problems.append(Finding(f"row {row['#']}", "car_id", kind))
            continue
        ref = f"row {row['#']}" if final else car
        first = cars.setdefault(car, [row])[0]
        if row is not first:
            cars[car].append(row)
        for column, kind in _row_problems(row, first, numbers, path, final=final):
            problem = Finding(ref, column, kind)
            if problem not in problems:
                problems.append(problem)
        if row["consent_version"] not in formats.APPROVED_CONSENT["set_b"]:
            warnings.append(Fact(ref, "consent_version", "unapproved"))
    drops = {}
    for car, rows in cars.items():
        cause = _drop(path, rows, final=final)
        if cause is not None:
            drops[car] = cause
    return CarsCheck(found.rows, problems, warnings, drops)


def bare_name(text: str) -> bool:
    """True for a bare file name, which can't lead out of its folder: not empty, "." or
    "..", and with no "/", "\\" or ":" (a drive or an NTFS stream)."""
    return text not in ("", ".", "..") and not any(mark in text for mark in "/\\:")


def _consent_name_ok(name: str, log: Path) -> bool:
    """True when an owner's OK is named as set_b_masks takes it: a bare file name
    beside cars.csv, never cars.csv's own, so its arcname can't clash (S-R29's M3)."""
    return bare_name(name) and name.casefold() != log.name.casefold()


def _row_problems(
    row: dict[str, str],
    first: dict[str, str],
    numbers: set[tuple[str, int]],
    log: Path,
    *,
    final: bool,
) -> list[tuple[str, str]]:
    """One row's (column, kind) problems, in the log's column order. A photo's number,
    once read, joins numbers, the (car, n) pairs seen so far."""
    car = row["car_id"]
    found = []
    if (int(car[1:]) % 2 == 0) != final:  # odd cars are development cars (C210)
        found.append(("car_id", "wrong_side"))
    name = row["photo_file"]
    photo = PHOTO_FILE.fullmatch(name)
    if not name:
        found.append(("photo_file", "missing"))
    elif photo is None or name[:3].upper() != car:
        found.append(("photo_file", "bad_name"))
    elif (car, int(photo.group(1))) in numbers:
        found.append(("photo_file", "duplicate"))
    else:
        numbers.add((car, int(photo.group(1))))
    found += [
        (column, "inconsistent")
        for column in CAR_COLUMNS
        if row[column] != first[column]
    ]
    for column, values in (
        ("vehicle_type", formats.SET_B_TYPES),
        ("view", formats.VIEWS),
    ):
        if not row[column]:
            found.append((column, "missing"))
        elif row[column] not in values:
            found.append((column, "not_in_list"))
    if not row["taken_on"]:
        found.append(("taken_on", "missing"))
    elif not formats.is_date(row["taken_on"]):
        found.append(("taken_on", "bad_date"))
    if row["consent_file"] and not _consent_name_ok(row["consent_file"], log):
        found.append(("consent_file", "bad_path"))
    return found


def _drop(log: Path, rows: list[dict[str, str]], *, final: bool) -> str | None:
    """A car's drop cause, or None to keep it: no_consent first, then its tire code."""
    for row in rows:
        consent = row["consent_file"]
        if not consent:
            return "no_consent"
        if not _consent_name_ok(consent, log):
            continue  # a bad_path problem, never looked for
        file = log.parent / consent
        if not final:
            guards.refuse_sealed(file)
        if not file.is_file():
            return "no_consent"
    size = tires.parse_tire_code(rows[0]["tire_code"])
    return size if isinstance(size, str) else None
