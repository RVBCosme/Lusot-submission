"""CSV, hash and finding helpers for MS2's data tools (the plan's file rules, C221).

A CSV is read with or without a BOM and with either line ending, and written as UTF-8
without a BOM, with LF line endings. A blank cell means none. A CSV whose header or
rows don't line up is refused, never repaired. An output file is created exclusively
and never rewritten.
"""

import csv
import hashlib
import io
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

ID_PATTERN = r"[A-Z]{1,3}[0-9]{1,4}(-[0-9]{1,3}){0,2}"


def is_id(text: str) -> bool:
    """True when the whole text is an opaque id in MS6's pattern (C221)."""
    return re.fullmatch(ID_PATTERN, text) is not None


@dataclass
class Table:
    """A CSV's columns and its rows that aren't all blank.

    Each row maps every column to its stripped cell, plus "#", the row's 1-based number
    among the file's data rows. A dropped blank row keeps its number, so data row n is
    spreadsheet row n + 1, the header being row 1.
    """

    columns: tuple[str, ...]
    rows: list[dict[str, str]]


class MalformedCsv(ValueError):
    """A CSV that can't be read as a table without shifting or losing a value.

    Its one argument is a Finding that names the row or the header column by number,
    never by its text.
    """


def read_table(path: Path) -> Table:
    """Read a CSV whose first row names the columns.

    A column name that is blank, repeated or "#", or a row whose cell count differs
    from the header's, raises MalformedCsv. No value is shifted or dropped in silence.
    """
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        columns = tuple(cell.strip() for cell in next(reader, []))
        for number, name in enumerate(columns, start=1):
            if not name:
                raise MalformedCsv(Finding("header", f"column {number}", "blank"))
            if name == "#":
                raise MalformedCsv(Finding("header", f"column {number}", "reserved"))
            if name in columns[: number - 1]:
                raise MalformedCsv(Finding("header", f"column {number}", "duplicate"))
        rows = []
        for number, cells in enumerate(reader, start=1):
            cells = [cell.strip() for cell in cells]
            if not any(cells):
                continue
            if len(cells) != len(columns):
                kind = "too_many" if len(cells) > len(columns) else "too_few"
                raise MalformedCsv(Finding(f"row {number}", "cells", kind))
            row = dict(zip(columns, cells, strict=True))
            row["#"] = str(number)
            rows.append(row)
    return Table(columns, rows)


def csv_bytes(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> bytes:
    """The rows as a CSV with the columns in the order given.

    A column a row lacks is a blank cell, and a key outside the columns, such as "#", is
    left out.
    """
    text = io.StringIO()
    writer = csv.DictWriter(text, columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return text.getvalue().encode("utf-8")


def write_new(path: Path, data: bytes) -> str:
    """Create the file, and any missing parent folders, and return the data's SHA-256.

    An existing file raises FileExistsError and keeps its bytes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as file:
        file.write(data)
    return sha256_bytes(data)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


@dataclass(frozen=True)
class Finding:
    """A problem, printed as `<ref> <column>: <kind>`."""

    ref: str
    column: str
    kind: str

    def __str__(self) -> str:
        return f"{self.ref} {self.column}: {self.kind}"


@dataclass(frozen=True)
class Fact:
    """A warning, printed as `<ref> <fact>=<value>`."""

    ref: str
    fact: str
    value: str

    def __str__(self) -> str:
        return f"{self.ref} {self.fact}={self.value}"
