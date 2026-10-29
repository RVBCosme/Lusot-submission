# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = []
# ///
r"""Set C's manifests (C215). sturm lists the STURM-FloodDepth download: each image's
path, its level from its folder and its SHA-256, so users draw their seeded subsets
from it and the data freeze's record holds its hash (C216, V8).

Run from the repo root (Claude runs this one):
    uv run --locked --script eval/data/setc.py sturm
        --root <data>\set_c\sturm_flooddepth
        --out <data>\set_c\sturm_flooddepth\manifest.csv
Both paths are absolute, and neither may lie inside a folder named sealed. --out must
not exist yet: a manifest is created once and never rewritten, so a rerun needs a new
path.

The walk is the one folder listing MS2's tools make (spec §5.2). It goes top-down,
descends no symbolic link, and never descends a folder whose name guards.is_sealed_name
calls sealed, the rule the path guard applies. A folder it can't read stops the run before
--out is written. An image (.jpg, .jpeg or .png, in any case) gets a row when a folder
below --root named Level0 to Level4, in any case, holds it, and the nearest such
folder sets its level. Every other file counts as skipped. The rows, sorted by path,
go into a CSV of path (relative to --root, with /), level and sha256.

It prints files=<n>, the count per level and skipped=<k>, never a file name or path.
Exit codes: 0 written; 1 a folder the walk can't read, or another error, of which only
the class prints; 2 refused: a path inside a folder named sealed, a relative path, or
an --out that exists.
"""

import argparse
import os
import re
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import guards
import table

COLUMNS = ("path", "level", "sha256")
IMAGES = (".jpg", ".jpeg", ".png")
LEVEL = re.compile(r"level([0-4])", re.IGNORECASE)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Set C's manifests (C215).")
    commands = parser.add_subparsers(dest="command", required=True)
    sturm = commands.add_parser(
        "sturm",
        description="The STURM-FloodDepth download's manifest: each image's path, "
        "level and SHA-256, printing the counts by level.",
        help="the STURM-FloodDepth manifest",
    )
    sturm.add_argument(
        "--root",
        required=True,
        type=Path,
        help="the download's folder, an absolute path",
    )
    sturm.add_argument(
        "--out",
        required=True,
        type=Path,
        help="the manifest.csv to create, an absolute path that doesn't exist yet",
    )
    args = parser.parse_args(argv)
    return guards.quiet(lambda: _sturm(args.root, args.out))


def _sturm(root: Path, out: Path) -> int:
    # The path rules, on the strings (C222, S-R8), then --out, which must not exist
    # yet: all before the walk.
    guards.refuse_sealed(root, out)
    for flag, path in (("--root", root), ("--out", out)):
        if not path.is_absolute():
            print(f"refused: {flag} must be absolute", file=sys.stderr)
            return 2
    if out.exists():
        print("--out exists: a manifest is never rewritten", file=sys.stderr)
        return 2
    rows = []
    skipped = 0
    for folder, subfolders, files in os.walk(
        root, topdown=True, onerror=_stop, followlinks=False
    ):
        # Pruned in place, so the walk never descends a sealed folder (PF-C27).
        subfolders[:] = [name for name in subfolders if not guards.is_sealed_name(name)]
        parts = Path(folder).relative_to(root).parts
        level = _level(parts)
        for name in files:
            if level is None or Path(name).suffix.lower() not in IMAGES:
                skipped += 1
                continue
            rows.append(
                {
                    "path": "/".join((*parts, name)),
                    "level": str(level),
                    "sha256": table.sha256_file(Path(folder, name)),
                }
            )
    rows.sort(key=lambda row: row["path"])
    table.write_new(out, table.csv_bytes(COLUMNS, rows))
    levels = Counter(row["level"] for row in rows)
    print(f"files={len(rows)}")
    print(" ".join(f"level{n}={levels[str(n)]}" for n in range(5)))
    print(f"skipped={skipped}")
    return 0


def _level(parts: Sequence[str]) -> int | None:
    """The level of the Level0 to Level4 folder nearest the file, or None."""
    for part in reversed(parts):
        if match := LEVEL.fullmatch(part):
            return int(match[1])
    return None


def _stop(error: OSError) -> None:
    """The walk's onerror: a folder it can't read stops the run (addition 1)."""
    raise error


if __name__ == "__main__":
    sys.exit(main())
