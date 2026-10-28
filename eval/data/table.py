"""CSV, hash and finding helpers for MS2's data tools (the plan's file rules, C221).

A CSV is read with or without a BOM and with either line ending, and written as UTF-8
without a BOM, with LF line endings. A blank cell means none. An output file is created
exclusively and never rewritten.
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
    among the file's data rows. A dropped blank row keeps its number, so `row <n>` names
    the row Rene sees.
    """

    columns: tuple[str, ...]
    rows: list[dict[str, str]]


def read_table(path: Path) -> Table:
    """Read a CSV whose first row names the columns. A missing cell reads as blank."""
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        columns = tuple(cell.strip() for cell in next(reader, []))
        rows = []
        for number, cells in enumerate(reader, start=1):
            cells = [cell.strip() for cell in cells]
            if any(cells):
                row = dict(zip(columns, cells + [""] * (len(columns) - len(cells))))
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
