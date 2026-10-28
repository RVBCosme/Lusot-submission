"""Checks of Rene's other logs before the split: his M8 export (C208), the consented
items' log (M9) and the sidewall photos' log (M11), each with its consent records (spec
§5.3, §5.9, C218).

The checks read only each log's text. A file a log names lies beside the log. Its path
is refused if a part of it names sealed (C222), and the file is then looked for with a
stat, which never reads its bytes (C201). A problem or a warning holds ids, row numbers,
column names and fixed words, never a cell's text. A ref that names no id starts with
its log's name, as in m8 row 3, consented log or sidewalls row 2 (Task 7's M7). A
malformed CSV raises table.MalformedCsv.

A list value that Rene types, in the consented and sidewall logs, is read in any case,
as in Set A's log. The M8 export is the page's own, so its values must be the page's.
"""

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

import formats
import guards
import table
from table import Fact, Finding

# Each kind of reference and its values, each with its list (Table 5, C208). A photo's
# own row, P1, holds its marks instead.
_REF_VALUES = {
    "vehicle": {
        "vehicle_type": formats.VEHICLE_TYPES,
        "body_waterline": formats.BODY_WATERLINES,
    },
    "wheel": {"waterline": formats.WHEEL_WATERLINES},
    "person": {"waterline": formats.PERSON_WATERLINES},
}
_REF_ID = r"P1|R[1-9][0-9]*"
# A point's x or y as the page writes it, a decimal (m8_sheet.js's DECIMAL), and a
# latitude or longitude in decimal degrees.
_FRACTION = r"[0-9]+(\.[0-9]+)?"
_DEGREES = r"-?[0-9]+(\.[0-9]+)?"
# The columns of the other two logs that are checked, in the template's order.
_CONSENTED_CHECKED = (
    "file",
    "kind",
    "taken_pht",
    "lat",
    "lon",
    "consent_file",
    "consent_version",
)
_SIDEWALLS_CHECKED = ("photo_file", "vehicle", "taken_on", "consent_file")


@dataclass
class M8Check:
    """Rene's M8 export: its rows as read, their problems, and the Set A photos it gives
    no photo row, in id order."""

    rows: list[dict[str, str]]
    problems: list[Finding]
    missing_photo_rows: list[str]


def check_m8(
    path: Path, set_a_ids: Collection[str], *, allow_missing: bool = False
) -> M8Check:
    """Check Rene's M8 export against the Set A log's photos (C208).

    A missing column gives `m8 log <column>: missing_column`, and then no row is checked.
    Otherwise each row is read as a photo's reference. Its ref, `<photo_id> <ref_id>`,
    must be readable first, or the row is named as m8 row n and checked no further:
    - photo_id: missing, or unknown_photo when it isn't a Set A photo
    - ref_id: missing, or bad_ref unless it is P1 or R<n>

    The rest read `<photo_id> <ref_id>.<column>`, as in A001 R2.x: out_of_range:
    - kind: missing, or not_in_list; a row with either is checked no further
    - ref_id: bad_ref unless it is P1 on a photo row and R<n> on another, and
      duplicate_ref when the photo already has that ref
    - a photo row: its quality, and each of its subsets, separated by ;
    - another row: its point, x and y, each a number from 0 to 1 (out_of_range), then
      its kind's values
    A blank required value is missing, and a value outside its list is not_in_list.
    Then each Set A photo without a photo row gives `<id> m8: no_photo_row`, unless
    allow_missing.
    """
    found = table.read_table(path)
    missing = _missing_columns("m8", found, formats.M8_COLUMNS)
    if missing:
        return M8Check(found.rows, missing, [])
    photos = set(set_a_ids)
    problems: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for row in found.rows:
        problem = _m8_ref_problem(row, photos)
        if problem is None and (row["photo_id"], row["ref_id"]) in seen:
            problem = Finding(
                row["photo_id"], f"{row['ref_id']}.ref_id", "duplicate_ref"
            )
        if problem is not None:
            problems.append(problem)
            continue
        seen.add((row["photo_id"], row["ref_id"]))
        problems += _m8_value_problems(row)
    marked = {photo_id for photo_id, ref_id in seen if ref_id == "P1"}
    missing_photo_rows = sorted(photos - marked)
    if not allow_missing:
        problems += [
            Finding(photo_id, "m8", "no_photo_row") for photo_id in missing_photo_rows
        ]
    return M8Check(found.rows, problems, missing_photo_rows)


def _m8_ref_problem(row: Mapping[str, str], photos: Collection[str]) -> Finding | None:
    """The problem that keeps a row from being read as its photo's reference, if any."""
    photo_id, ref_id, kind = row["photo_id"], row["ref_id"], row["kind"]
    where = f"m8 row {row['#']}"
    if photo_id not in photos:
        return Finding(where, "photo_id", "unknown_photo" if photo_id else "missing")
    if re.fullmatch(_REF_ID, ref_id) is None:
        return Finding(where, "ref_id", "bad_ref" if ref_id else "missing")
    if kind not in formats.M8_KINDS:
        return Finding(photo_id, f"{ref_id}.kind", "not_in_list" if kind else "missing")
    if (kind == "photo") != (ref_id == "P1"):
        return Finding(photo_id, f"{ref_id}.ref_id", "bad_ref")
    return None


def _m8_value_problems(row: Mapping[str, str]) -> list[Finding]:
    """A photo row's marks, or a reference's point and its kind's values, in the
    export's column order."""
    found: dict[str, str | None] = {}
    if row["kind"] == "photo":
        found["quality"] = _list_problem(row["quality"], formats.QUALITIES)
        tags = [tag.strip() for tag in row["subsets"].split(";")]
        if any(tag and tag not in formats.SUBSET_TAGS for tag in tags):
            found["subsets"] = "not_in_list"
    else:
        for column in ("x", "y"):
            found[column] = _fraction_problem(row[column])
        for column, values in _REF_VALUES[row["kind"]].items():
            found[column] = _list_problem(row[column], values)
    return [
        Finding(row["photo_id"], f"{row['ref_id']}.{column}", problem)
        for column, problem in found.items()
        if problem is not None
    ]


def _list_problem(value: str, values: tuple[str, ...]) -> str | None:
    if not value:
        return "missing"
    return None if value in values else "not_in_list"


def _fraction_problem(value: str) -> str | None:
    if not value:
        return "missing"
    if re.fullmatch(_FRACTION, value) is None or float(value) > 1:
        return "out_of_range"
    return None


def check_consented(path: Path) -> tuple[list[Finding], list[Fact]]:
    """Check the consented items' log (M9, C218), beside which lie each item's file and
    its written OK. It gives no warning, so the second list is always empty.

    A missing column gives `consented log <column>: missing_column`, and then no row is
    checked. A row whose item_id is blank or isn't S and three digits is named as
    consented row n. A row that repeats an earlier row's item_id gives
    `<id> item_id: duplicate`, once for each id, since each item has one row and G1's
    demo pins are keyed by the id (S-R11's M5). Neither is checked further. The rest
    name the item, column by column; each column checked needs a value, or it is
    missing:
    - file and consent_file: file_missing unless the file lies beside the log
    - kind: not_in_list unless photo or clip
    - taken_pht: bad_time unless YYYY-MM-DD HH:MM
    - lat and lon: out_of_range unless decimals from -90 to 90 and -180 to 180
    - consent_version: not_approved unless Rene has approved it (APPROVED_CONSENT)
    """
    found = table.read_table(path)
    missing = _missing_columns("consented", found, formats.CONSENTED_COLUMNS)
    if missing:
        return missing, []
    problems: list[Finding] = []
    seen: set[str] = set()
    for row in found.rows:
        item_id = row["item_id"]
        if re.fullmatch(formats.ITEM_ID, item_id) is None:
            kind = "bad_id" if item_id else "missing"
            problems.append(Finding(f"consented row {row['#']}", "item_id", kind))
            continue
        if item_id in seen:
            duplicate = Finding(item_id, "item_id", "duplicate")
            if duplicate not in problems:
                problems.append(duplicate)
            continue
        seen.add(item_id)
        for column in _CONSENTED_CHECKED:
            kind = _consented_problem(path, column, row[column])
            if kind is not None:
                problems.append(Finding(item_id, column, kind))
    return problems, []


def _consented_problem(log: Path, column: str, value: str) -> str | None:
    """One checked column's problem, if any. A column with no check of its own raises
    ValueError, so that one added to _CONSENTED_CHECKED is never checked as another
    (S-R11's M4)."""
    if not value:
        return "missing"
    if column in ("file", "consent_file"):
        return _file_problem(log, value)
    if column == "kind":
        return None if value.lower() in formats.ITEM_KINDS else "not_in_list"
    if column == "taken_pht":
        return None if formats.is_time(value) else "bad_time"
    if column in ("lat", "lon"):
        limit = 90 if column == "lat" else 180
        if re.fullmatch(_DEGREES, value) is None or abs(float(value)) > limit:
            return "out_of_range"
        return None
    if column == "consent_version":
        return None if value in formats.APPROVED_CONSENT["m9"] else "not_approved"
    raise ValueError(f"no check for the column {column}")


def check_sidewalls(path: Path) -> tuple[list[Finding], list[Fact]]:
    """Check the sidewall photos' log (M11, C218), beside which lie each photo and each
    driver's permission. The log has no id column, so each problem and warning names
    its row, as sidewalls row n.

    A missing column gives `sidewalls log <column>: missing_column`, and then no row is
    checked. Otherwise photo_file, vehicle, taken_on and consent_file each need a value,
    or it is missing:
    - photo_file and consent_file: file_missing unless the file lies beside the log
    - vehicle: not_in_list unless one of formats.SIDEWALL_VEHICLES
    - taken_on: bad_date unless YYYY-MM-DD
    Two warnings: consent_version=unapproved for a version Rene hasn't approved, a
    blank one included, and code=mismatch when checked_code is filled and differs from
    tire_code, the two compared in capitals and without spaces.
    """
    found = table.read_table(path)
    missing = _missing_columns("sidewalls", found, formats.SIDEWALLS_COLUMNS)
    if missing:
        return missing, []
    problems, warnings = [], []
    for row in found.rows:
        where = f"sidewalls row {row['#']}"
        for column in _SIDEWALLS_CHECKED:
            kind = _sidewall_problem(path, column, row[column])
            if kind is not None:
                problems.append(Finding(where, column, kind))
        if row["consent_version"] not in formats.APPROVED_CONSENT["m11"]:
            warnings.append(Fact(where, "consent_version", "unapproved"))
        checked = row["checked_code"]
        if checked and _code(checked) != _code(row["tire_code"]):
            warnings.append(Fact(where, "code", "mismatch"))
    return problems, warnings


def _sidewall_problem(log: Path, column: str, value: str) -> str | None:
    """One checked column's problem, if any. A column with no check of its own raises
    ValueError, so that one added to _SIDEWALLS_CHECKED is never checked as another
    (S-R11's M4)."""
    if not value:
        return "missing"
    if column in ("photo_file", "consent_file"):
        return _file_problem(log, value)
    if column == "vehicle":
        return None if value.lower() in formats.SIDEWALL_VEHICLES else "not_in_list"
    if column == "taken_on":
        return None if formats.is_date(value) else "bad_date"
    raise ValueError(f"no check for the column {column}")


def _code(code: str) -> str:
    return "".join(code.split()).upper()


def _missing_columns(
    log: str, found: table.Table, columns: tuple[str, ...]
) -> list[Finding]:
    return [
        Finding(f"{log} log", column, "missing_column")
        for column in columns
        if column not in found.columns
    ]


def _file_problem(log: Path, name: str) -> str | None:
    """file_missing unless the named file lies beside the log. Its path is refused first
    if a part of it names sealed (C222), and the file is looked for with a stat (C201)."""
    path = log.parent / name
    guards.refuse_sealed(path)
    return None if path.is_file() else "file_missing"
