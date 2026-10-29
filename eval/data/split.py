# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["numpy==2.5.4", "opencv-python-headless==4.14.0.94", "py7zr==1.1.4"]
# ///
r"""Split Set A and A-neg by flood event into a development side and a write-once
encrypted archive (M19, spec §5.5, C204, C205, C219).

Rene alone runs this, once, from his own console (C202). It checks the logs again,
reads each photo once by name, joins the photos posted twice, draws each set's events
with the fixed seed (C204) and audits the draw. Only then does it ask for the archive
password, the last step before anything is written (S-R19). It writes the sealed side
into one archive, from the very bytes it hashed, then the development side, whose
copies it hashes again from disk (C219), then the committed record (C216). A stop
before the password writes nothing.

Usage, from the repo root, in Rene's own Windows PowerShell window:
    uv run --locked --script eval/data/split.py
        --set-a-log <data>\set_a\set_a_log.csv --set-a-photos <data>\set_a\raw
        --a-neg-log <data>\a_neg\a_neg_log.csv --a-neg-photos <data>\a_neg\raw
        --m8 <data>\set_a\m8_labels.csv
        --set-a-dev <data>\set_a\dev --a-neg-dev <data>\a_neg\dev
        --archive <data>\sealed\lusot-sealed.7z
        --record eval\data\records\<date>-split.json [--allow-missing-m8]
The archive and the dev folders are absolute paths, and the archive's folder, named
sealed, must exist. None of the four outputs may exist yet: a rerun names each one left
by a stopped run, which Rene deletes first.

It prints the intake's warnings as a count, then, once written, the rows and events per
set, side and group, the counts per fact value, audit PASS, copy check <k> of <n>, and
the archive's size and SHA-256. No id prints there. A problem in the logs prints as
<id> <column>: <kind>, before any photo is sealed, and a copy-check stop names a
development id only.

Exit codes: 0 written; 1 a problem in the logs, a log that can't be read, a set with
fewer than 2 events, a copy check or audit that fails, a record that would hold an id,
or an error, of which only the class prints; 2 refused: a path rule, no console, an
output that exists, a missing archive folder, or the password.
"""

import argparse
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import combinations
from pathlib import Path

import archive
import audit
import draw
import events
import formats
import guards
import intake
import manifest
import photos
import record_io
import strata
import table
from setlogs import SetCheck

REPO = Path(__file__).resolve().parents[2]
SIDES = ("dev", "sealed")
# Each source's file name in its set's source folder in the archive, and its key in
# the record's inputs.
SOURCES = {
    "A": (("set_a_log.csv", "set_a_log"), ("m8_labels.csv", "m8")),
    "A-neg": (("a_neg_log.csv", "a_neg_log"),),
}

Row = dict[str, str]


def duplicate_groups(facts: Mapping[str, photos.PhotoFacts]) -> dict[str, str]:
    """Each photo of one set posted twice or more, mapped to its duplicate group's
    lowest id (§5.5). Two photos join when their SHA-256s are identical or their dHashes
    near, and a group holds every photo joined to it, directly or through another. A
    photo in no group is left out."""
    group = {photo_id: photo_id for photo_id in sorted(facts)}
    for a, b in combinations(sorted(facts), 2):
        if facts[a].sha256 == facts[b].sha256 or events.near(
            facts[a].dhash, facts[b].dhash
        ):
            low, high = sorted((group[a], group[b]))
            for photo_id, lowest in group.items():
                if lowest == high:
                    group[photo_id] = low
    sizes = Counter(group.values())
    return {photo_id: lowest for photo_id, lowest in group.items() if sizes[lowest] > 1}


def _archive_name_ok(name: str) -> bool:
    """True when the sealed run's audit opens an archive of this name (S-R18) and the
    committed record, which holds it, holds no id (S-R16). The two rules are theirs, so
    the three tools never drift apart (S-R19)."""
    return (
        audit._ARCHIVE_NAME.fullmatch(name) is not None
        and record_io._ID_TOKEN.search(name) is None
    )


def _refuse(text: str) -> int:
    print(f"refused: {text}", file=sys.stderr)
    return 2


def _draw(
    set_name: str, check: SetCheck, folder: Path, kept: dict[str, bytes]
) -> tuple[dict[str, draw.GroupDraw], list[Row]]:
    """Steps 6 to 8 for one set: each photo read once by name, its bytes kept and its
    facts taken; the duplicates joined; the events grouped, with each copy joined to
    its group's lowest id; and the draw. Return the draw and the set's manifest rows,
    sorted by id. A set with fewer than 2 events raises draw.TooFewEvents."""
    facts = {}
    for photo in check.photos:
        kept[photo.photo_id] = (folder / photo.photo_file).read_bytes()
        facts[photo.photo_id] = photos.photo_facts(kept[photo.photo_id])
    copies = duplicate_groups(facts)
    event_of = events.group_events(
        [
            events.EventInput(
                photo.photo_id, photo.event_date, photo.spot_key, photo.same_spot_as
            )
            for photo in check.photos
        ],
        copies.items(),
    )
    deep = {
        event_of[photo.photo_id]
        for photo in check.photos
        if strata.deep_row(photo.passability_raw)
    }
    sizes = Counter(event_of.values())
    draws = draw.draw_set(
        set_name, {event: (n, event in deep) for event, n in sizes.items()}
    )
    sealed = {event for found in draws.values() for event in found.sealed}
    rows = [
        manifest.manifest_row(
            photo,
            facts[photo.photo_id],
            event_id=event_of[photo.photo_id],
            split="sealed" if event_of[photo.photo_id] in sealed else "dev",
            duplicate_of=copies.get(photo.photo_id, ""),
        )
        for photo in check.photos
    ]
    return draws, sorted(rows, key=lambda row: row["photo_id"])


def _side_files(
    sides: Mapping[str, Mapping[str, list[Row]]], m8_rows: list[Row]
) -> dict[str, dict[str, dict[str, bytes]]]:
    """Each side's files, by set and file name: each set's manifest.csv, and Set A's
    m8.csv, which holds the M8 rows of that side's photos (C208)."""
    files = {}
    for side in SIDES:
        files[side] = {
            set_name: {
                "manifest.csv": table.csv_bytes(formats.MANIFEST_COLUMNS, on[side])
            }
            for set_name, on in sides.items()
        }
        ids = [row["photo_id"] for row in sides["A"][side]]
        files[side]["A"]["m8.csv"] = table.csv_bytes(
            formats.M8_COLUMNS, manifest.m8_rows(m8_rows, ids)
        )
    return files


def _members(
    core: bytes,
    files: Mapping[str, Mapping[str, bytes]],
    sealed: Mapping[str, list[Row]],
    kept: Mapping[str, bytes],
    sources: Mapping[str, bytes],
) -> list[tuple[str, bytes]]:
    """The archive's members, in step 10's order: the core record, then for each set
    its sealed files, its sealed photos and its sources, each from memory."""
    members = [("records/split.json", core)]
    for set_name, folder in audit.FOLDERS.items():
        members += [
            (f"{folder}/{name}", data) for name, data in files[set_name].items()
        ]
        members += [
            (f"{folder}/photos/{row['photo_file']}", kept[row["photo_id"]])
            for row in sealed[set_name]
        ]
        members += [
            (f"{folder}/source/{name}", sources[key]) for name, key in SOURCES[set_name]
        ]
    return members


def _write_dev(
    folders: Mapping[str, Path],
    files: Mapping[str, Mapping[str, bytes]],
    dev: Mapping[str, list[Row]],
    kept: Mapping[str, bytes],
) -> tuple[int, list[str]]:
    """Step 11: create each set's dev folder, write its files and a copy of each dev
    photo from its kept bytes, then hash each copy again from disk (C219). Return the
    copies whose hash matched their manifest row, and the ids of those that didn't."""
    matched, changed = 0, []
    for set_name, folder in folders.items():
        folder.mkdir(parents=True)
        for name, data in files[set_name].items():
            table.write_new(folder / name, data)
        for row in dev[set_name]:
            table.write_new(
                folder / "photos" / row["photo_file"], kept[row["photo_id"]]
            )
        for row in dev[set_name]:
            copy = folder / "photos" / row["photo_file"]
            if table.sha256_file(copy) == row["photo_sha256"]:
                matched += 1
            else:
                changed.append(row["photo_id"])
    return matched, changed


def _print_counts(sets: Mapping[str, Mapping]) -> None:
    """The record's counts: the rows and events per set and side, then per group and
    side, then the counts per fact value. A blank value prints as (blank)."""
    for set_name, found in sets.items():
        for side in SIDES:
            print(
                f"{set_name} {side} rows={found[side]['rows']} "
                f"events={found[side]['events']}"
            )
        for group, counts in found["groups"].items():
            for side in SIDES:
                print(
                    f"{set_name} {group} {side} events={counts[side]['events']} "
                    f"rows={counts[side]['rows']}"
                )
        for side in SIDES:
            for fact, values in found[side]["facts"].items():
                tally = " ".join(
                    f"{value or '(blank)'}={n}" for value, n in sorted(values.items())
                )
                print(f"{set_name} {side} {fact}: {tally}")


def _split(args: argparse.Namespace) -> int:
    # 1. The path rules, on the strings alone (C202, C222, S-R8, S-R13, S-R19).
    guards.require_sealed(args.archive, flag="--archive")
    if not args.archive.is_absolute():
        return _refuse("--archive must be absolute")
    if not _archive_name_ok(args.archive.name):
        return _refuse("--archive name")
    guards.refuse_sealed(
        args.set_a_log,
        args.set_a_photos,
        args.a_neg_log,
        args.a_neg_photos,
        args.m8,
        args.set_a_dev,
        args.a_neg_dev,
        args.record,
    )
    for flag, folder in (
        ("--set-a-dev", args.set_a_dev),
        ("--a-neg-dev", args.a_neg_dev),
    ):
        if not folder.is_absolute():
            return _refuse(f"{flag} must be absolute")

    # 2. Rene's own console. 3. The outputs, which must not exist yet, and the archive's
    # folder, which must (Review Focus 3, S-R12).
    guards.require_console()
    stops = [
        f"{flag} exists: delete it before rerunning"
        for flag, path in (
            ("--archive", args.archive),
            ("--record", args.record),
            ("--set-a-dev", args.set_a_dev),
            ("--a-neg-dev", args.a_neg_dev),
        )
        if path.exists()
    ]
    if not args.archive.parent.is_dir():
        stops.append("--archive folder missing: create it first")
    for line in stops:
        print(line)
    if stops:
        return 2

    # 4. The intake's checks again. A warning names an id that may end up sealed, so
    # only their count prints.
    try:
        result = intake.run_intake(
            set_a_log=args.set_a_log,
            set_a_photos=args.set_a_photos,
            a_neg_log=args.a_neg_log,
            a_neg_photos=args.a_neg_photos,
            m8=args.m8,
            allow_missing_m8=args.allow_missing_m8,
        )
    except table.MalformedCsv as error:
        print(error.args[0])
        return 1
    for problem in result.problems:
        print(problem)
    print(f"warnings={len(result.warnings)}")
    if result.problems:
        return 1
    m8_check = result.m8  # read, since a Set A log missing a column is a problem

    # 5. The logs and the M8 export, read once as bytes: hashed into the record and
    # archived as they are (addition 5).
    sources = {
        "set_a_log": args.set_a_log.read_bytes(),
        "a_neg_log": args.a_neg_log.read_bytes(),
        "m8": args.m8.read_bytes(),
    }

    # 6. to 8. The photos, the duplicates, the events and the draw, set by set.
    kept: dict[str, bytes] = {}
    draws, sides = {}, {}
    for set_name, check, folder in (
        ("A", result.set_a, args.set_a_photos),
        ("A-neg", result.a_neg, args.a_neg_photos),
    ):
        try:
            draws[set_name], rows = _draw(set_name, check, folder, kept)
        except draw.TooFewEvents as error:
            print(f"split stopped: set {error.args[0]} has fewer than 2 events")
            return 1
        sides[set_name] = {
            side: [r for r in rows if r["split"] == side] for side in SIDES
        }

    # 9. The copy check before copying (C219), then the audit, over both sets.
    every = {side: [row for on in sides.values() for row in on[side]] for side in SIDES}
    matched = audit.copy_check(every["dev"], every["sealed"])
    for photo_id, _ in matched:
        print(f"copy check: {photo_id} matches a sealed photo")
    if matched:
        return 1
    violations = audit.check_split(every, None)
    if violations:
        print("FAIL")
        for violation in violations:
            print(violation)
        return 1

    # The core record, from this draw, encoded before the password, since a record
    # holding an id is refused (S-R16).
    files = _side_files(sides, m8_check.rows)
    dev_files = files["dev"]
    core = record_io.split_record(
        repo=REPO,
        inputs={key: table.sha256_bytes(data) for key, data in sources.items()},
        draws=draws,
        sides=sides,
        missing_m8=len(m8_check.missing_photo_rows),
        dev_files={
            "set_a_manifest": table.sha256_bytes(dev_files["A"]["manifest.csv"]),
            "set_a_m8": table.sha256_bytes(dev_files["A"]["m8.csv"]),
            "a_neg_manifest": table.sha256_bytes(dev_files["A-neg"]["manifest.csv"]),
        },
    )
    try:
        core_bytes = record_io.record_bytes(core)
    except ValueError as error:
        print(error.args[0])
        return 1

    # 10. The password, C202's confirmation, then the archive in one pass (C205).
    password = guards.ask_password()
    sealed = {set_name: on["sealed"] for set_name, on in sides.items()}
    members = _members(core_bytes, files["sealed"], sealed, kept, sources)
    facts = archive.write_sealed_archive(args.archive, password, members)

    # 11. The development side.
    folders = {"A": args.set_a_dev, "A-neg": args.a_neg_dev}
    dev = {set_name: on["dev"] for set_name, on in sides.items()}
    copied, changed = _write_dev(folders, dev_files, dev, kept)
    for photo_id in changed:
        print(f"copy check: {photo_id} changed on disk")
    if changed:
        return 1

    # 12. The committed record: the core, the archive's facts and the copy check.
    total = len(every["dev"])
    copy_check = {"rehash_ok": f"{copied}/{total}", "matched_sealed": len(matched)}
    record = core | {
        "archive": record_io.archive_block(facts),
        "copy_check": copy_check,
    }
    record_io.write_record(args.record, record)

    # 13. The counts, the audit, the copy check and the archive. No id prints.
    _print_counts(core["sets"])
    print("audit PASS")
    print(f"copy check {copied} of {total}")
    print(f"archive {facts.size} bytes sha256 {facts.sha256}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rene only (M19): split Set A and A-neg by flood event into a "
        "development side and a write-once encrypted archive, then write the "
        "committed record. Prints counts and hashes, never an id."
    )
    archive_help = (
        "the archive to create, an absolute path inside a folder named sealed, such "
        "as lusot-sealed.7z"
    )
    for flag, text in (
        ("--set-a-log", "Set A's log"),
        ("--set-a-photos", "Set A's raw photos folder"),
        ("--a-neg-log", "A-neg's log"),
        ("--a-neg-photos", "A-neg's raw photos folder"),
        ("--m8", "Rene's M8 export, m8_labels.csv"),
        ("--set-a-dev", "Set A's development folder to create, an absolute path"),
        ("--a-neg-dev", "A-neg's development folder to create, an absolute path"),
        ("--archive", archive_help),
        ("--record", "the committed record to create, under eval\\data\\records"),
    ):
        parser.add_argument(flag, required=True, type=Path, help=text)
    parser.add_argument(
        "--allow-missing-m8",
        action="store_true",
        help="split although a Set A photo has no M8 photo row; the record counts them",
    )
    args = parser.parse_args(argv)
    return guards.quiet(lambda: _split(args))


if __name__ == "__main__":
    sys.exit(main())
