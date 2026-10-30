# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = []
# ///
r"""The data freeze's record (C216, V8): the SHA-256 of each dataset file, each sealed
set's record with its archive block, the generator version and C213's looks, so MS6
freezes the dataset versions from one committed file.

Run from the repo root at MS2's close (Claude runs this one):
    uv run --locked --script eval/data/freeze_record.py --data <data>
        --file set_a/dev/manifest.csv --file set_a/dev/m8.csv
        --file a_neg/dev/manifest.csv --file set_b/dev/generated/truth.csv
        --file set_c/sturm_flooddepth/manifest.csv
        --record eval\data\records\<date>-split.json
        --record eval\data\records\<date>-set-b-final.json
        --look eval\data\records\set-b-look-1.json
        --out eval\data\records\<date>-freeze.json
--data is absolute. Each --file is relative to it, with no drive, root, stream, "." or
".." part, and the record keys it as given, with /. A \ counts as / on every system,
for the key and for the path that is opened. Each --record is keyed by its bare
file name, with its SHA-256 and a copy of its archive block, or null when it has none.
The generator version is read from set_b/dev/generated/truth.csv when that --file is
given, spelled exactly so, and is null otherwise. Each --look is copied whole, in the
order given. The record holds no id: one that would, as through a --file's or a
--record's name, is refused before anything is written (S-R16).

It prints the file count and the record's SHA-256. Exit codes: 0 written; 1 a record
that would hold an id, or an error, of which only the class prints; 2 refused: a path
inside a folder named sealed, a relative --data, a --file that leaves --data or names
truth.csv in another case, two --record or two --look files whose names match, or an
--out that exists.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import guards
import record_io
import table

REPO = Path(__file__).resolve().parents[2]
TOOL = "eval/data/freeze_record.py"
TRUTH = "set_b/dev/generated/truth.csv"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="The data freeze's record (C216, V8): each dataset file's "
        "SHA-256, each sealed set's archive block, the generator version and C213's "
        "looks, printing the file count and the record's SHA-256."
    )
    parser.add_argument(
        "--data", required=True, type=Path, help="the data folder, an absolute path"
    )
    parser.add_argument(
        "--file",
        required=True,
        action="append",
        help="a dataset file, relative to --data, such as set_a/dev/manifest.csv; "
        "repeatable",
    )
    parser.add_argument(
        "--record",
        action="append",
        default=[],
        type=Path,
        help="a committed record: the split's, Set B final's or Set D's; repeatable",
    )
    parser.add_argument(
        "--look",
        action="append",
        default=[],
        type=Path,
        help="a look record of the freeze check's (C213); repeatable",
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="the freeze record to create, under eval\\data\\records",
    )
    args = parser.parse_args(argv)
    return guards.quiet(lambda: _run(args))


def _run(args: argparse.Namespace) -> int:
    # The path rules, on the strings (addition 5, C222), then --out, which must not
    # exist yet.
    if not args.data.is_absolute():
        return _refuse("--data must be absolute")
    if not all(_inside(rel) for rel in args.file):
        return _refuse("--file must stay inside --data")
    # The key is the --file with / for \, and the path joins the key's parts onto --data,
    # so a \ is a separator on every system, not only on Windows.
    keys = [rel.replace("\\", "/") for rel in args.file]
    paths = {key: args.data.joinpath(*key.split("/")) for key in keys}
    # The keys MS6 reads stay as written, and no entry replaces another's (S-R30).
    if any(rel.casefold() == TRUTH and rel != TRUTH for rel in paths):
        return _refuse(f"--file must be spelled {TRUTH}")
    for flag, given in (("--record", args.record), ("--look", args.look)):
        names = [path.name.casefold() for path in given]
        if len(set(names)) != len(names):
            return _refuse(f"two {flag} files share a name")
    guards.refuse_sealed(args.data, *paths.values(), *args.record, *args.look, args.out)
    if args.out.exists():
        print("--out exists: a record is never rewritten", file=sys.stderr)
        return 2
    records = {}
    for path in args.record:
        data = path.read_bytes()
        records[path.name] = {
            "sha256": table.sha256_bytes(data),
            "archive": json.loads(data).get("archive"),
        }
    version = _generator_version(paths[TRUTH]) if TRUTH in paths else None
    record = record_io.base_record(TOOL, REPO) | {
        "files": {rel: table.sha256_file(path) for rel, path in paths.items()},
        "records": records,
        "generator_version": version,
        "looks": [json.loads(path.read_bytes()) for path in args.look],
    }
    # Encoded first, so a record that would hold an id stops before any write (S-R16).
    try:
        record_io.record_bytes(record)
    except ValueError:
        print("refused: the record would hold an id", file=sys.stderr)
        return 1
    digest = record_io.write_record(args.out, record)
    print(f"files={len(paths)}")
    print(f"record sha256 {digest}")
    return 0


def _inside(rel: str) -> bool:
    """True for a --file that stays inside --data: no ":", so no drive or stream, and
    each part, split on / and \\, holds more than dots and spaces, so there is no root,
    no "." or "..", and no empty part."""
    parts = rel.replace("\\", "/").split("/")
    return ":" not in rel and all(part.rstrip(". ") for part in parts)


def _generator_version(truth: Path) -> str:
    """The one generator version in truth.csv's rows, as generate writes it. Rows of
    another number of versions raise ValueError."""
    (version,) = {row["generator_version"] for row in table.read_table(truth).rows}
    return version


def _refuse(text: str) -> int:
    print(f"refused: {text}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
