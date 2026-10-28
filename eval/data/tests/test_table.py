"""Tests for the CSV and record helpers: the file rules and the id pattern (C221)."""

import hashlib

import pytest
import table

GOOD_IDS = [
    "A001",
    "N015",
    "E01",
    "E100",
    "B01",
    "B01-1",
    "B01-1-2",
    "D01",
    "S001",
    "P1",
    "R12",
]
BAD_IDS = ["a001", "A001-", "A00001", "2026-10-30", "Espana", "B01-1-2-3", ""]


def test_ids():
    assert [text for text in GOOD_IDS if not table.is_id(text)] == []
    assert [text for text in BAD_IDS if table.is_id(text)] == []


def test_read_table_tolerates_bom_crlf_and_blank_rows(tmp_path):
    path = tmp_path / "log.csv"
    path.write_bytes(b"\xef\xbb\xbfa , b\r\n 1 , x \r\n,\r\n\r\n")
    assert table.read_table(path) == table.Table(
        ("a", "b"), [{"a": "1", "b": "x", "#": "1"}]
    )


def test_row_numbers_count_the_dropped_blank_rows(tmp_path):
    """A dropped blank row keeps its number, so `row <n>` names the row Rene sees."""
    path = tmp_path / "log.csv"
    path.write_bytes(b"a,b\n1,x\n\n,\n2,y\n")
    assert table.read_table(path).rows == [
        {"a": "1", "b": "x", "#": "1"},
        {"a": "2", "b": "y", "#": "4"},
    ]


def test_csv_bytes_are_plain():
    rows = [{"id": "A001", "note": "a, b", "#": "1"}, {"id": "A002"}]
    assert table.csv_bytes(["id", "note"], rows) == b'id,note\nA001,"a, b"\nA002,\n'


def test_write_new_never_overwrites(tmp_path):
    path = tmp_path / "records" / "record.json"
    assert table.write_new(path, b"first") == hashlib.sha256(b"first").hexdigest()
    with pytest.raises(FileExistsError):
        table.write_new(path, b"second")
    assert path.read_bytes() == b"first"
    assert table.sha256_file(path) == table.sha256_bytes(b"first")


def test_findings_print_as_specified():
    assert str(table.Finding("A001", "city", "missing")) == "A001 city: missing"
    assert str(table.Fact("A001", "match", "none")) == "A001 match=none"
