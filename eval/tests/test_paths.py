"""The sealed-path guard (C411). A path is refused by its text alone, so nothing is
read, listed or created, and these test paths never exist on disk."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from scoring.paths import SealedPath, refuse_sealed

MESSAGE = "path inside a folder named sealed"


@pytest.mark.parametrize(
    "parts",
    [
        ("sealed",),
        ("a", "Sealed", "x"),
        ("sealed", "sub", ".."),
        ("sealed", "..", "x"),
        # Windows drops a name's trailing dots and spaces, so these open "sealed" (R156).
        ("sealed.",),
        ("sealed ", "x"),
        ("a", "SEALED.", "x"),
        ("Sealed ..",),
        # An NTFS stream name after the folder's name opens the folder too.
        ("sealed::$INDEX_ALLOCATION", "x"),
    ],
    ids=[
        "sealed",
        "in another case",
        "inside, then up",
        "up again, as given",
        "a trailing dot",
        "a trailing space",
        "a trailing dot in capitals",
        "trailing spaces and dots",
        "a stream suffix",
    ],
)
def test_refuses_sealed_paths(tmp_path, parts):
    with pytest.raises(SealedPath) as caught:
        refuse_sealed(tmp_path.joinpath(*parts))
    assert isinstance(caught.value, ValueError)
    assert str(caught.value) == MESSAGE
    assert not any(tmp_path.iterdir())


def test_allows_other_paths(tmp_path):
    for path in (
        tmp_path / "unsealed" / "x",
        tmp_path / "sealed_notes",
        tmp_path / "sealedx",
        tmp_path / "sealed.txt",
        tmp_path / "final",
    ):
        refuse_sealed(path)
    assert not any(tmp_path.iterdir())


def test_refuses_a_relative_path_inside_a_sealed_folder(tmp_path):
    # A working directory inside a sealed folder must never exist, so the absolute
    # form stands in for one: "results" there is <tmp_path>/sealed/results.
    inside = os.path.join(tmp_path, "sealed")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(os.path, "abspath", lambda path: os.path.join(inside, path))
        with pytest.raises(SealedPath):
            refuse_sealed(Path("results"))
    assert not any(tmp_path.iterdir())
