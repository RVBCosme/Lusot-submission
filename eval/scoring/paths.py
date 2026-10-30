"""C411: the harness reads nothing inside a folder named sealed.

The check reads the path's text alone and never touches the disk, so a sealed folder
is never read, listed or even looked up.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePath


class SealedPath(ValueError):
    """A path inside a folder named sealed. The message never names the path."""

    def __init__(self) -> None:
        super().__init__("path inside a folder named sealed")


def refuse_sealed(path: Path) -> None:
    """Raise SealedPath when any part of `path`, as given or in its absolute,
    normalised form, is named sealed in any case."""
    absolute = os.path.normpath(os.path.abspath(path))
    parts = (*PurePath(path).parts, *PurePath(absolute).parts)
    if any(_names_sealed(part) for part in parts):
        raise SealedPath()


def _names_sealed(part: str) -> bool:
    """Windows opens "sealed." and "sealed " as "sealed", and "sealed::$INDEX_ALLOCATION"
    as the folder itself, so a stream suffix and trailing dots and spaces are dropped
    first (R156; the rule MS2's eval/data/guards.py uses)."""
    return part.split(":", 1)[0].rstrip(". ").casefold() == "sealed"
