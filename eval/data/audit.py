# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = []
# ///
r"""Audit a split for leaks between the development side and the sealed side (W18, C219,
C220, spec §5.5).

The audit rebuilds each set's flood events from the manifests alone, by C203's rule,
joining photos posted twice: a duplicate_of, an equal SHA-256 or a near dHash. It then
checks that no rebuilt event, event id, SHA-256 or near-identical photo sits on both
sides, that each C204 group of 2 or more events has an event on each side, and that the
counts per group match the record. The split runs check_split before it writes
anything, and its copy check is copy_check (C219), so the two never drift apart.

Usage, from the repo root. Claude runs this one after the split, for Set A and A-neg:
    uv run --locked --script eval/data/audit.py
        --dev <data>\set_a\dev\manifest.csv --record eval\data\records\<date>-split.json
It checks the manifest's SHA-256 against the record, that every row is dev, the dev
counts per group, and that each copy in photos\ beside the manifest hashes to its row.

Rene alone runs this one, at the sealed run (C202, C220):
    uv run --locked --script eval/data/audit.py --sealed <data>\sealed\run-1
        --dev-root <data> --record <split record> [--record <record> ...]
For each record it first hashes the archive the record names, beside RUN_DIR. Then it
checks the split's two sides, or Set B's final cars against the development cars; a Set
D record has its hash checked only. It reads only the files the records and this
layout name, and lists no folder.

It prints PASS or FAIL, the counts per set, group and side, then each violation. Only
development ids print: a violation two rows share names the dev row, and the counts are
numbers. Exit codes: 0 PASS; 1 FAIL, or an error, of which only the class prints; 2
refused: a sealed path where none may be, a RUN_DIR outside sealed, no console, a
missing path (<flag> missing), a --dev record that isn't the split's, or no yes.
"""

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from itertools import combinations
from pathlib import Path

import formats
import guards
import record_io
import strata
import table
from events import EventInput, group_events, near

GROUPS = ("deep", "other")
# Each set's folder in the data folder, and its manifest's key in the record's
# dev_files.
FOLDERS = {"A": "set_a", "A-neg": "a_neg"}
DEV_FILES = {"A": "set_a_manifest", "A-neg": "a_neg_manifest"}
_ZERO = {"events": 0, "rows": 0}
_NOT_WRITTEN = "not a file the tools wrote"
# An archive's file name, as a record gives it: a bare ASCII name, at most 100
# characters before .7z, which is safe to open beside RUN_DIR and to print (S-R18).
_ARCHIVE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.7z")

Row = Mapping[str, str]


def rebuild_events(rows: Sequence[Row]) -> dict[str, str]:
    """Each row's event id, rebuilt by group_events from one set's manifest rows (C203):
    each row's date, spot key and same_spot_as links, with the photos posted twice
    joined, by duplicate_of, an equal SHA-256 or a near dHash (§5.5).

    A duplicate_of naming no row raises KeyError, as group_events does.
    """
    inputs = [
        EventInput(
            row["photo_id"],
            row["event_date"],
            row["spot_key"],
            frozenset(link for link in row["same_spot_as"].split(";") if link),
        )
        for row in rows
    ]
    joined = [
        (row["photo_id"], row["duplicate_of"]) for row in rows if row["duplicate_of"]
    ]
    joined += [
        (a["photo_id"], b["photo_id"])
        for a, b in combinations(rows, 2)
        if a["photo_sha256"] == b["photo_sha256"]
        or near(a["photo_dhash"], b["photo_dhash"])
    ]
    return group_events(inputs, joined)


def copy_check(dev: Sequence[Row], sealed: Sequence[Row]) -> list[tuple[str, str]]:
    """The dev rows that share a photo with the sealed side, across both sets (C219):
    (<dev id>, "sha256") when a row's SHA-256 equals a sealed row's, otherwise
    (<dev id>, "near_identical") when its dHash is near one's. A blank dHash is near
    nothing."""
    hashes = {row["photo_sha256"] for row in sealed}
    found = []
    for row in dev:
        if row["photo_sha256"] in hashes:
            found.append((row["photo_id"], "sha256"))
        elif any(near(row["photo_dhash"], other["photo_dhash"]) for other in sealed):
            found.append((row["photo_id"], "near_identical"))
    return found


def check_split(
    sides: Mapping[str, Sequence[Row]], groups: Mapping[str, Mapping] | None
) -> list[str]:
    """The violations of a split, naming dev ids only.

    sides is {"dev": rows, "sealed": rows}, each side holding both sets' manifest rows,
    told apart by their set. groups is {set: record["sets"][set]["groups"]}, or None
    before the record exists, which skips count_mismatch. With groups, a set the record
    names is checked even when neither side holds a row of it. Events and event ids are
    compared within each set, since ids are numbered per set (§5.9), and photos across
    both sets, by copy_check.
    """
    return _split(sides, groups)[1]


def _split(
    sides: Mapping[str, Sequence[Row]], groups: Mapping[str, Mapping] | None
) -> tuple[list[str], list[str]]:
    """check_split's count lines and violations."""
    counts: list[str] = []
    violations: list[str] = []
    names = {row["set"] for rows in sides.values() for row in rows}
    if groups is not None:
        # S-R18: a set the record names but neither side holds, as when both its
        # manifests are emptied, is compared too, so it can't pass unseen.
        names |= groups.keys()
    for set_name in sorted(names):
        own = {
            side: [row for row in rows if row["set"] == set_name]
            for side, rows in sides.items()
        }
        # S-R14: a set whose rows all sit on one side, such as a Set A of one deep and
        # one other event, whose one-event groups both stay dev.
        if not all(own.values()):
            violations.append(f"set_one_sided {set_name}")
        events = rebuild_events(own["dev"] + own["sealed"])
        sealed_events = {events[row["photo_id"]] for row in own["sealed"]}
        sealed_ids = {row["event_id"] for row in own["sealed"]}
        for row in own["dev"]:
            if events[row["photo_id"]] in sealed_events:
                violations.append(f"event_on_both_sides {row['photo_id']}")
            if row["event_id"] in sealed_ids:
                violations.append(f"event_id_on_both_sides {row['photo_id']}")
        grouped = _by_group(own, events)
        for group in GROUPS:
            on = {
                side: {events[row["photo_id"]] for row in rows}
                for side, rows in grouped[group].items()
            }
            if len(on["dev"] | on["sealed"]) >= 2 and not all(on.values()):
                violations.append(f"group_one_sided {set_name} {group}")
        if groups is not None:
            violations += _mismatches(
                set_name, grouped, events, groups.get(set_name, {})
            )
        counts += _count_lines(set_name, grouped, events)
    violations += [
        f"{kind}_on_both_sides {photo_id}"
        for photo_id, kind in copy_check(sides["dev"], sides["sealed"])
    ]
    return counts, violations


def _by_group(
    sides: Mapping[str, Sequence[Row]], events: Mapping[str, str]
) -> dict[str, dict[str, list[Row]]]:
    """Each side's rows in each C204 group, by the rebuilt events: an event is deep when
    deep_row holds on any of its rows' passability_raw."""
    deep = {
        events[row["photo_id"]]
        for rows in sides.values()
        for row in rows
        if strata.deep_row(row["passability_raw"])
    }
    return {
        group: {
            side: [
                row
                for row in rows
                if (events[row["photo_id"]] in deep) == (group == "deep")
            ]
            for side, rows in sides.items()
        }
        for group in GROUPS
    }


def _count(rows: Sequence[Row], events: Mapping[str, str]) -> dict[str, int]:
    return {"events": len({events[row["photo_id"]] for row in rows}), "rows": len(rows)}


def _mismatches(
    set_name: str,
    grouped: Mapping[str, Mapping[str, Sequence[Row]]],
    events: Mapping[str, str],
    recorded: Mapping,
) -> list[str]:
    """count_mismatch for each group and side whose events or rows differ from the
    record's groups. A group missing from either counts as empty."""
    return [
        f"count_mismatch {set_name} {group} {side}"
        for group in GROUPS
        for side, rows in grouped[group].items()
        if _count(rows, events) != recorded.get(group, {}).get(side, _ZERO)
    ]


def _count_lines(
    set_name: str,
    grouped: Mapping[str, Mapping[str, Sequence[Row]]],
    events: Mapping[str, str],
) -> list[str]:
    """`<set> <group> <side> events=<n> rows=<m>` for each side of each group that has
    rows."""
    lines = []
    for group in GROUPS:
        if any(grouped[group].values()):
            for side, rows in grouped[group].items():
                count = _count(rows, events)
                lines.append(
                    f"{set_name} {group} {side} "
                    f"events={count['events']} rows={count['rows']}"
                )
    return lines


def audit_dev(manifest: Path, record: Path) -> list[str]:
    """The violations of a development manifest, against the split's committed record:
    manifest_hash, split_value <id>, count_mismatch <set> <group> dev, photo_file <id>,
    copy_missing <id> and copy_hash <id>.

    A record that isn't UTF-8 JSON, or isn't the split's, raises ValueError, and so does
    a manifest the split didn't write.
    """
    return _dev(manifest, _split_record(record))[1]


def _split_record(path: Path) -> Mapping:
    """The split's record. Any other raises ValueError, naming nothing of it."""
    record = _record(path)
    if record_io.record_kind(record) != "split":
        raise ValueError("not the split's record")
    return record


def _record(path: Path) -> object:
    return json.loads(path.read_bytes().decode("utf-8"))


def _dev(manifest: Path, record: Mapping) -> tuple[list[str], list[str]]:
    """audit_dev's count lines and violations."""
    rows = _manifest(manifest)
    sets = {row["set"] for row in rows}
    if len(sets) != 1 or not sets <= DEV_FILES.keys():
        raise ValueError(_NOT_WRITTEN)
    (set_name,) = sets
    violations = []
    if table.sha256_file(manifest) != record["dev_files"][DEV_FILES[set_name]]:
        violations.append("manifest_hash")
    violations += [
        f"split_value {row['photo_id']}" for row in rows if row["split"] != "dev"
    ]
    events = rebuild_events(rows)
    grouped = _by_group({"dev": rows}, events)
    recorded = _record_groups(record).get(set_name, {})
    violations += _mismatches(set_name, grouped, events, recorded)
    # C219: each copy re-hashed. A cell must never steer the audit out of photos\.
    photos = manifest.parent / "photos"
    for row in rows:
        name, photo_id = row["photo_file"], row["photo_id"]
        if not _bare(name):
            violations.append(f"photo_file {photo_id}")
            continue
        copy = photos / name
        guards.refuse_sealed(copy)
        if not copy.is_file():
            violations.append(f"copy_missing {photo_id}")
        elif table.sha256_file(copy) != row["photo_sha256"]:
            violations.append(f"copy_hash {photo_id}")
    return _count_lines(set_name, grouped, events), violations


def _manifest(path: Path) -> list[dict[str, str]]:
    """A manifest's rows. One with another header, or a photo_id outside C221's
    pattern, isn't the split's and raises ValueError, naming nothing of it, so every
    id a violation names is an id."""
    read = table.read_table(path)
    if read.columns != formats.MANIFEST_COLUMNS or not all(
        table.is_id(row["photo_id"]) for row in read.rows
    ):
        raise ValueError(_NOT_WRITTEN)
    return read.rows


def _record_groups(record: Mapping) -> dict[str, Mapping]:
    """The record's groups by set. Its set names may print in a violation, so a record
    naming a set other than A and A-neg isn't the split's and raises ValueError."""
    if not record["sets"].keys() <= FOLDERS.keys():
        raise ValueError(_NOT_WRITTEN)
    return {name: found["groups"] for name, found in record["sets"].items()}


def _bare(name: str) -> bool:
    """True for a bare file name, which can't lead out of its folder: not empty, and
    with no folder, drive, stream or .."""
    return (
        bool(name)
        and Path(name).name == name
        and not any(mark in name for mark in (":", "/", "\\", ".."))
    )


def audit_sealed(run_dir: Path, dev_root: Path, records: Sequence[Path]) -> list[str]:
    """The violations at the sealed run (C220), record by record. First archive_name,
    when the record's archive.file isn't a plain ASCII name ending in .7z (S-R18), or
    archive_hash <file>, when run_dir.parent / <file> is missing or doesn't hash to the
    record's archive.sha256. Then, by the record's kind:
    - split: check_split on Set A's and A-neg's dev manifests under dev_root and the
      sealed manifests under run_dir, with the record's groups
    - set_b_final: car_on_both_sides <dev car id> across the final truth.csv under
      run_dir and the development one under dev_root, and count_mismatch set_b
      against the record's counts.cars and counts.crops
    - set_d: the hash only

    A record with no record kind raises ValueError (S-R16), and so does a manifest or
    truth file the tools didn't write.
    """
    return _sealed(run_dir, dev_root, records)[1]


def _sealed(
    run_dir: Path, dev_root: Path, records: Sequence[Path]
) -> tuple[list[str], list[str]]:
    """audit_sealed's count lines and violations."""
    checks = {"split": _sealed_split, "set_b_final": _set_b}
    counts: list[str] = []
    violations: list[str] = []
    for path in records:
        record = _record(path)
        kind = record_io.record_kind(record)
        violations += _archive(run_dir, record)
        if kind in checks:
            found = checks[kind](run_dir, dev_root, record)
            counts += found[0]
            violations += found[1]
    return counts, violations


def _archive(run_dir: Path, record: Mapping) -> list[str]:
    """The record's archive, beside run_dir, checked against its hash (C220). The name
    is opened and printed only when it is _ARCHIVE_NAME's, so a record can neither steer
    the read elsewhere nor print text of its own."""
    name = record["archive"]["file"]
    if not isinstance(name, str) or _ARCHIVE_NAME.fullmatch(name) is None:
        return ["archive_name"]
    path = run_dir.parent / name
    if not path.is_file() or table.sha256_file(path) != record["archive"]["sha256"]:
        return [f"archive_hash {name}"]
    return []


def _sealed_split(
    run_dir: Path, dev_root: Path, record: Mapping
) -> tuple[list[str], list[str]]:
    """The split's two sides, from the dev manifests and the sealed copy's."""
    sides: dict[str, list[Row]] = {"dev": [], "sealed": []}
    for set_name, folder in FOLDERS.items():
        for side, path in (
            ("dev", dev_root / folder / "dev" / "manifest.csv"),
            ("sealed", run_dir / folder / "manifest.csv"),
        ):
            rows = _manifest(path)
            if any(row["set"] != set_name for row in rows):
                raise ValueError(_NOT_WRITTEN)
            sides[side] += rows
    return _split(sides, _record_groups(record))


def _set_b(
    run_dir: Path, dev_root: Path, record: Mapping
) -> tuple[list[str], list[str]]:
    """Set B's final cars against the development cars (C214), and the final truth's
    cars and crops against the record's counts, which leave dropped cars out."""
    found = {
        "dev": _truth(dev_root / "set_b" / "dev" / "generated" / "truth.csv"),
        "sealed": _truth(run_dir / "set_b" / "truth.csv"),
    }
    final_cars = {row["car_id"] for row in found["sealed"]}
    violations = [
        f"car_on_both_sides {car}"
        for car in dict.fromkeys(row["car_id"] for row in found["dev"])
        if car in final_cars
    ]
    tally = {
        side: {
            "cars": len({row["car_id"] for row in rows}),
            "crops": len({row["crop_id"] for row in rows}),
        }
        for side, rows in found.items()
    }
    counts = record["counts"]
    if tally["sealed"] != {"cars": counts["cars"], "crops": counts["crops"]}:
        violations.append("count_mismatch set_b")
    lines = [
        f"set_b {side} cars={count['cars']} crops={count['crops']}"
        for side, count in tally.items()
    ]
    return lines, violations


def _truth(path: Path) -> list[dict[str, str]]:
    """A truth file's rows. One with another header, or a car_id outside C221's
    pattern, isn't the generator's and raises ValueError, naming nothing of it."""
    read = table.read_table(path)
    if read.columns != formats.TRUTH_COLUMNS or not all(
        table.is_id(row["car_id"]) for row in read.rows
    ):
        raise ValueError(_NOT_WRITTEN)
    return read.rows


def _report(counts: Sequence[str], violations: Sequence[str]) -> int:
    print("FAIL" if violations else "PASS")
    for line in [*counts, *violations]:
        print(line)
    return 1 if violations else 0


def _run_dev(manifest: Path, record_path: Path) -> int:
    """--dev: the paths refused on their strings, then checked to exist, then the
    record read, before the manifest."""
    guards.refuse_sealed(manifest, record_path)
    missing = [
        flag
        for flag, path in (("--dev", manifest), ("--record", record_path))
        if not path.is_file()
    ]
    for flag in missing:
        print(f"{flag} missing")
    if missing:
        return 2
    try:
        record = _split_record(record_path)
    except ValueError:  # not UTF-8 JSON, no record kind, or not the split's (S-R16)
        print("--record unreadable")
        return 2
    return _report(*_dev(manifest, record))


def _run_sealed(run_dir: Path, dev_root: Path, records: Sequence[Path]) -> int:
    """--sealed, in Rene's order (C202): the path rules on the strings, the console,
    the existence checks, then yes. The body runs through quiet."""
    guards.require_sealed(run_dir, flag="--sealed")
    guards.refuse_sealed(dev_root, *records)
    guards.require_console()
    missing = [
        flag
        for flag, found in (
            ("--sealed", run_dir.is_dir()),
            ("--dev-root", dev_root.is_dir()),
        )
        if not found
    ]
    missing += ["--record" for record in records if not record.is_file()]
    for flag in missing:
        print(f"{flag} missing")
    if missing:
        return 2
    guards.confirm(
        f"Audit the sealed copy against {len(records)} record(s). Nothing is written."
    )
    return guards.quiet(lambda: _report(*_sealed(run_dir, dev_root, records)))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit the split for leaks between the development side and the "
        "sealed side, printing development ids only (W18)."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dev",
        type=Path,
        metavar="MANIFEST",
        help="a development manifest: set_a\\dev\\manifest.csv or "
        "a_neg\\dev\\manifest.csv",
    )
    mode.add_argument(
        "--sealed",
        type=Path,
        metavar="RUN_DIR",
        help="Rene only: the sealed copy extracted for the sealed run, inside a folder "
        "named sealed (C220)",
    )
    parser.add_argument(
        "--dev-root",
        type=Path,
        metavar="DATA",
        help="with --sealed: the data folder that holds the development side",
    )
    parser.add_argument(
        "--record",
        type=Path,
        action="append",
        required=True,
        help="a committed record: the split's with --dev; with --sealed, each record "
        "whose archive and sides to check",
    )
    args = parser.parse_args(argv)
    if args.dev is not None:
        if args.dev_root is not None or len(args.record) != 1:
            parser.error("--dev takes one --record and no --dev-root")
        return _run_dev(args.dev, args.record[0])
    if args.dev_root is None:
        parser.error("--sealed needs --dev-root")
    return _run_sealed(args.sealed, args.dev_root, args.record)


if __name__ == "__main__":
    sys.exit(guards.quiet(main))
