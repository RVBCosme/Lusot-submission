"""Tests for the split audit, eval/data/audit.py (W18, C202, C219, C220, C222).

Every manifest, copy, truth file, record and archive is synthetic, under tmp_path. The
sealed run's folders are named sealed there, as in lusot-data, and only test code reads
them. Each archive is written by write_sealed_archive with the test phrase (C206), and
no test runs git: each record's git state is fixed.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import archive
import audit
import draw
import formats
import pytest
import record_io
import synth
import table

DATA = Path(__file__).resolve().parents[1]  # eval/data
AUDIT = DATA / "audit.py"
REFUSED = "refused: path inside a folder named sealed\n"
NO_CONSOLE = "refused: run this yourself, in a Windows PowerShell window\n"
# A text that the output may never hold.
SENTINEL = "Zqxjv"
SIDES = ("dev", "sealed")
FOLDERS = {"A": "set_a", "A-neg": "a_neg"}

# The clean split: each photo's id, set, side, event id, date, spot key and stated
# passability. Each event has its own date, so only a test's change joins two events.
# Set A's deep group (E01, E02), its other group (E03 to E05) and A-neg's other group
# each have an event on each side. Set A's E01 is dev, and A-neg's E01 sealed.
LAYOUT = (
    ("A001", "A", "dev", "E01", "2026-08-01", "espana|lacson", "NPLV"),
    ("A002", "A", "dev", "E01", "2026-08-01", "espana|lacson", "NPLV"),
    ("A003", "A", "sealed", "E02", "2026-08-02", "dapitan|maceda", "NPATV"),
    ("A004", "A", "dev", "E03", "2026-08-03", "quezon|recto", "PATV"),
    ("A005", "A", "sealed", "E04", "2026-08-04", "pedro gil|taft", "PATV"),
    ("A006", "A", "dev", "E05", "2026-08-05", "edsa|kamuning", "PATV"),
    ("N001", "A-neg", "sealed", "E01", "2026-10-01", "pedro gil|taft", ""),
    ("N002", "A-neg", "dev", "E02", "2026-10-02", "espana|lacson", ""),
    ("N003", "A-neg", "dev", "E02", "2026-10-02", "espana|lacson", ""),
    ("N004", "A-neg", "dev", "E03", "2026-10-03", "dapitan|maceda", ""),
)
A_NEG_LAYOUT = tuple(photo for photo in LAYOUT if photo[1] == "A-neg")
# The clean split's draw: each group's events on each side, and its rows.
DRAWS = {
    "A": {
        "deep": draw.GroupDraw(
            "deep", frozenset({"E02"}), frozenset({"E01"}), 3, 1, None
        ),
        "other": draw.GroupDraw(
            "other", frozenset({"E04"}), frozenset({"E03", "E05"}), 3, 1, None
        ),
    },
    "A-neg": {
        "other": draw.GroupDraw(
            "other", frozenset({"E01"}), frozenset({"E02", "E03"}), 4, 1, None
        ),
    },
}
# Task 10's one case with an empty sealed side: a Set A of exactly 2 events, one deep
# and one other, whose one-event groups both stay dev (S-R14).
TWO_EVENT_A = (
    ("A001", "A", "dev", "E01", "2026-08-01", "espana|lacson", "NPLV"),
    ("A002", "A", "dev", "E02", "2026-08-02", "quezon|recto", "PATV"),
)
ONE_SIDED_DRAWS = {
    "A": {
        "deep": draw.GroupDraw("deep", frozenset(), frozenset({"E01"}), 1, 0, None),
        "other": draw.GroupDraw("other", frozenset(), frozenset({"E02"}), 1, 0, None),
    },
    "A-neg": DRAWS["A-neg"],
}
INPUTS = {"set_a_log": "1a" * 32, "a_neg_log": "2b" * 32, "m8": "3c" * 32}
DEV_FILES = {
    "set_a_manifest": "4d" * 32,
    "set_a_m8": "5e" * 32,
    "a_neg_manifest": "6f" * 32,
}
SET_B_INPUTS = {"cars": "7a" * 32, "masks_files": "8b" * 32, "dev_cars": "9c" * 32}
SET_B_COUNTS = {
    "cars": 2,
    "photos": 2,
    "crops": 4,
    "wheels": 4,
    "wheels_without_rim": 0,
    "drops": {},
    "warnings": 0,
}
# What the clean split prints after PASS, in --dev and in --sealed.
SET_A_DEV_COUNTS = ["A deep dev events=1 rows=2", "A other dev events=2 rows=2"]
A_NEG_DEV_COUNTS = ["A-neg other dev events=2 rows=3"]
SET_A_SPLIT_COUNTS = [
    "A deep dev events=1 rows=2",
    "A deep sealed events=1 rows=1",
    "A other dev events=2 rows=2",
    "A other sealed events=1 rows=1",
]
SPLIT_COUNTS = SET_A_SPLIT_COUNTS + [
    "A-neg other dev events=2 rows=3",
    "A-neg other sealed events=1 rows=1",
]


def summary(records: int) -> str:
    return f"Audit the sealed copy against {records} record(s). Nothing is written."


@pytest.fixture(autouse=True)
def no_git(monkeypatch):
    """Every record's git state is fixed, so no test runs git."""
    monkeypatch.setattr(
        record_io, "git_state", lambda repo: {"commit": "unknown", "dirty": True}
    )


def photo(photo_id: str) -> bytes:
    """A dev copy's bytes. The audit only hashes a copy, so it needn't decode."""
    return f"synthetic photo {photo_id}".encode("ascii")


def manifest_rows(layout=LAYOUT) -> dict[str, dict[str, str]]:
    """Each photo's manifest row, by id, as the split writes it. Each SHA-256 is its
    copy's. Each dHash is the photo's number as two hex digits, eight times, so every
    two photos' dHashes differ in at least 8 bits, beyond the 6 that make them near."""
    rows = {}
    for number, facts in enumerate(layout, start=1):
        photo_id, set_name, split, event_id, date, spot, passability = facts
        rows[photo_id] = dict.fromkeys(formats.MANIFEST_COLUMNS, "") | {
            "photo_id": photo_id,
            "set": set_name,
            "split": split,
            "event_id": event_id,
            "event_date": date,
            "city": "Manila",
            "metro_manila": "yes",
            "spot_key": spot,
            "poster_kind": "mmda" if set_name == "A" else "other",
            "match": "same_post" if set_name == "A" else "",
            "level_label_raw": "Gutter deep" if set_name == "A" else "none",
            "passability_raw": passability,
            "label_in_image": "no",
            "reference_visible": "wheel",
            "faces_or_plates": "no",
            "surface": "" if set_name == "A" else "dry",
            "duplicate": "no",
            "decodes": "yes",
            "photo_file": f"{photo_id}.jpg",
            "photo_sha256": hashlib.sha256(photo(photo_id)).hexdigest(),
            "photo_dhash": f"{number:02x}" * 8,
            "width": "320",
            "height": "240",
        }
    return rows


def flip(dhash: str, bits: int) -> str:
    """The dHash with its lowest bits flipped, so it lies that many bits away."""
    return f"{int(dhash, 16) ^ ((1 << bits) - 1):016x}"


def sides_of(rows) -> dict[str, list[dict[str, str]]]:
    """check_split's sides: each side's rows of both sets, by their split."""
    return {
        side: [row for row in rows.values() if row["split"] == side] for side in SIDES
    }


def core_record(sides, draws=DRAWS, dev_files=DEV_FILES) -> dict:
    """The split's record of these sides and draws, as record_io builds it."""
    return record_io.split_record(
        repo=Path(),
        inputs=INPUTS,
        draws=draws,
        sides={
            set_name: {
                side: [row for row in sides[side] if row["set"] == set_name]
                for side in SIDES
            }
            for set_name in FOLDERS
        },
        missing_m8=0,
        dev_files=dev_files,
    )


def groups_of(record) -> dict:
    return {name: found["groups"] for name, found in record["sets"].items()}


def committed(root: Path, name: str, core: dict, tweak=None) -> Path:
    """Seal the core record into data/sealed/<name>.7z, as each sealing step does, and
    write the committed record, which adds the archive's block, to records/<name>.json.
    tweak, when given, changes the committed record before it is written."""
    sealed = root / "data" / "sealed"
    sealed.mkdir(parents=True, exist_ok=True)
    facts = archive.write_sealed_archive(
        sealed / f"{name}.7z",
        synth.TEST_PHRASE,
        [("records/record.json", record_io.record_bytes(core))],
    )
    record = core | {"archive": record_io.archive_block(facts)}
    if tweak is not None:
        tweak(record)
    path = root / "records" / f"{name}.json"
    record_io.write_record(path, record)
    return path


def lay_out(root: Path, sides=None, *, draws=DRAWS, tweak=None) -> dict[str, Path]:
    """Write a split under root/data as the split and Rene leave it, and its committed
    record under root/records, and return each path by name.

    The development side holds each set's dev manifest and a copy of each dev photo,
    named by its id. The sealed side holds the archive, sealed/lusot-sealed.7z, and its
    extracted copy's manifests in sealed/run-1. The record is built from the sides and
    draws, with the dev manifests' hashes, and tweak changes it before it is written.
    """
    sides = sides_of(manifest_rows()) if sides is None else sides
    data = root / "data"
    paths = {"data": data, "run_dir": data / "sealed" / "run-1"}
    for set_name, folder in FOLDERS.items():
        dev = [row for row in sides["dev"] if row["set"] == set_name]
        sealed = [row for row in sides["sealed"] if row["set"] == set_name]
        paths[set_name] = synth.write_csv(
            data / folder / "dev" / "manifest.csv", formats.MANIFEST_COLUMNS, dev
        )
        for row in dev:
            photos = data / folder / "dev" / "photos"
            photos.mkdir(exist_ok=True)
            (photos / f"{row['photo_id']}.jpg").write_bytes(photo(row["photo_id"]))
        synth.write_csv(
            paths["run_dir"] / folder / "manifest.csv", formats.MANIFEST_COLUMNS, sealed
        )
    dev_files = DEV_FILES | {
        "set_a_manifest": table.sha256_file(paths["A"]),
        "a_neg_manifest": table.sha256_file(paths["A-neg"]),
    }
    paths["record"] = committed(
        root, "lusot-sealed", core_record(sides, draws, dev_files), tweak
    )
    return paths


def truth_rows(cars, split: str) -> list[dict[str, str]]:
    """Each car's truth rows as generate writes them: one photo, two crops, and a row
    per wheel per crop."""
    return [
        dict.fromkeys(formats.TRUTH_COLUMNS, "")
        | {
            "crop_id": f"{car}-1-{crop}",
            "car_id": car,
            "split": split,
            "photo_file": f"{car}-1.jpg",
            "crop_file": f"{car}-1-{crop}.jpg",
            "wheel": wheel,
            "generator_version": "set-b-gen-v1",
        }
        for car in cars
        for crop in (1, 2)
        for wheel in ("left", "right")
    ]


def lay_out_set_b(root: Path, dev_cars, final_cars, counts=SET_B_COUNTS) -> Path:
    """Write Set B's development truth and the final truth as extracted at the sealed
    run, and the final cars' committed record. Return the record's path."""
    data = root / "data"
    synth.write_csv(
        data / "set_b" / "dev" / "generated" / "truth.csv",
        formats.TRUTH_COLUMNS,
        truth_rows(dev_cars, "dev"),
    )
    synth.write_csv(
        data / "sealed" / "run-1" / "set_b" / "truth.csv",
        formats.TRUTH_COLUMNS,
        truth_rows(final_cars, "sealed"),
    )
    core = record_io.set_b_final_record(
        repo=Path(),
        counts=counts,
        generator_version="set-b-gen-v1",
        generator_seed=20261101,
        inputs=SET_B_INPUTS,
    )
    return committed(root, "lusot-sealed-set-b", core)


def set_d_core() -> dict:
    return record_io.set_d_record(
        repo=Path(),
        counts={"photos": 3, "vehicle_type": {"jeepney": 3}, "wheel": {"left": 3}},
        inputs={"set_d_log": "ad" * 32},
        extends=None,
    )


def change_a_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 1
    path.write_bytes(bytes(data))


def inside(path, folder) -> bool:
    absolute = Path(os.path.abspath(path))
    return absolute == folder or folder in absolute.parents


def dev_args(manifest: Path, record: Path) -> list[str]:
    return ["--dev", str(manifest), "--record", str(record)]


def sealed_args(run_dir: Path, data: Path, *records: Path) -> list[str]:
    args = ["--sealed", str(run_dir), "--dev-root", str(data)]
    for record in records:
        args += ["--record", str(record)]
    return args


@pytest.fixture(params=["split", "sealed_run"])
def audit_of(request, tmp_path):
    """The violations of a split against the clean split's record: as the split's own
    check finds them in memory, or as the sealed run finds them on disk, beside the
    record's archive. tweak, when given, changes the record first."""

    def run(rows, tweak=None):
        sides = sides_of(rows)
        if request.param == "split":
            record = core_record(sides)
            if tweak is not None:
                tweak(record)
            return audit.check_split(sides, groups_of(record))
        paths = lay_out(tmp_path, sides, tweak=tweak)
        return audit.audit_sealed(paths["run_dir"], paths["data"], [paths["record"]])

    return run


# On both sides: the split's check, and --sealed.


def test_clean_split_passes(audit_of):
    assert audit_of(manifest_rows()) == []


@pytest.mark.parametrize(
    "join",
    [
        {"A005": {"event_date": "2026-08-03", "spot_key": "quezon|recto"}},
        {"A005": {"event_date": "2026-08-03", "spot_key": "pedro gil|quezon"}},
        {"A005": {"event_date": "2026-08-03", "spot_key": "quezon market|taft"}},
        {"A004": {"same_spot_as": "A005"}},
        {"A005": {"duplicate": "yes", "duplicate_of": "A004"}},
    ],
    ids=["same_spot", "a_shared_name", "a_name_inside_a_name", "linked", "duplicate"],
)
def test_event_split_across_sides(audit_of, join):
    """C203's event, rebuilt from the manifests alone, has a dev row and a sealed one,
    under different event ids: the same date and spot, a shared name, a name inside a
    name, a same_spot_as link, or a duplicate_of. Only the dev row is named."""
    rows = manifest_rows()
    for photo_id, cells in join.items():
        rows[photo_id].update(cells)
    assert rows["A004"]["event_id"] != rows["A005"]["event_id"]
    assert audit_of(rows) == ["event_on_both_sides A004"]


def test_event_split_names_every_dev_row(audit_of):
    """A sealed photo at E01's date and spot splits an event of two dev rows: each dev
    row is named, and the sealed one never."""
    rows = manifest_rows()
    rows["A003"].update(event_date="2026-08-01", spot_key="espana|lacson")
    assert audit_of(rows) == [
        "event_on_both_sides A001",
        "event_on_both_sides A002",
    ]


def test_event_id_on_both_sides(audit_of):
    rows = manifest_rows()
    rows["A004"]["event_id"] = rows["A005"]["event_id"]
    assert audit_of(rows) == ["event_id_on_both_sides A004"]


def test_identical_photo_on_both_sides(audit_of):
    """A photo posted twice joins one event, so the two sides also share an event."""
    rows = manifest_rows()
    rows["A004"]["photo_sha256"] = rows["A005"]["photo_sha256"]
    assert audit_of(rows) == [
        "event_on_both_sides A004",
        "sha256_on_both_sides A004",
    ]


def test_same_event_id_in_two_sets_is_not_a_violation(audit_of):
    """Event ids are numbered per set (§5.9), so Set A's E01 on the dev side and
    A-neg's E01 on the sealed side are two events, as are A-neg's dev E02 and Set A's
    sealed E02."""
    rows = manifest_rows()
    assert [rows[photo_id]["event_id"] for photo_id in ("A001", "N001")] == [
        "E01",
        "E01",
    ]
    assert [rows[photo_id]["split"] for photo_id in ("A001", "N001")] == [
        "dev",
        "sealed",
    ]
    assert rows["A003"]["event_id"] == rows["N002"]["event_id"] == "E02"
    assert audit_of(rows) == []


@pytest.mark.parametrize(
    ("bits", "expected"),
    [
        (6, ["event_on_both_sides A004", "near_identical_on_both_sides A004"]),
        (7, []),
    ],
)
def test_near_identical_photo_on_both_sides(audit_of, bits, expected):
    """dHashes within 6 bits are one photo posted twice (§5.5); 7 bits apart are two."""
    rows = manifest_rows()
    rows["A004"]["photo_dhash"] = flip(rows["A005"]["photo_dhash"], bits)
    assert audit_of(rows) == expected


def test_copy_check_catches_identical_and_near_photos(audit_of):
    """C219's one cross-side photo check compares both sets: a dev row whose SHA-256
    equals a sealed row's in the other set gives sha256, even when its dHash is near
    too, one whose dHash is 6 bits from one gives near_identical, and 7 bits gives
    nothing. check_split reports exactly what copy_check finds."""
    rows = manifest_rows()
    rows["A004"].update(
        photo_sha256=rows["N001"]["photo_sha256"],
        photo_dhash=rows["N001"]["photo_dhash"],
    )
    rows["N002"]["photo_dhash"] = flip(rows["A003"]["photo_dhash"], 6)
    rows["N003"]["photo_dhash"] = flip(rows["A005"]["photo_dhash"], 7)
    sides = sides_of(rows)
    assert audit.copy_check(sides["dev"], sides["sealed"]) == [
        ("A004", "sha256"),
        ("N002", "near_identical"),
    ]
    assert audit_of(rows) == [
        "sha256_on_both_sides A004",
        "near_identical_on_both_sides N002",
    ]


def test_blank_dhash_on_either_side_is_never_near(audit_of):
    """A photo that doesn't decode has a blank dHash (Task 9), which pairs with
    nothing, a blank one included, so only its SHA-256 could join it."""
    rows = manifest_rows()
    for photo_id in ("A004", "A005", "N001", "N002"):
        rows[photo_id].update(photo_dhash="", decodes="no", width="", height="")
    sides = sides_of(rows)
    assert audit.copy_check(sides["dev"], sides["sealed"]) == []
    assert audit_of(rows) == []


def test_group_one_sided(audit_of):
    """Set A's deep group of 2 events, both dev, leaves the sealed side no deep flood
    (C204), and its counts no longer match the record."""
    rows = manifest_rows()
    rows["A003"]["split"] = "dev"
    assert audit_of(rows) == [
        "group_one_sided A deep",
        "count_mismatch A deep dev",
        "count_mismatch A deep sealed",
    ]


def set_group(set_name: str, group: str, side: str, key: str, value: int):
    def tweak(record):
        record["sets"][set_name]["groups"][group][side][key] = value

    return tweak


def drop_group(set_name: str, group: str):
    def tweak(record):
        del record["sets"][set_name]["groups"][group]

    return tweak


def add_group(set_name: str, group: str, like: str):
    def tweak(record):
        groups = record["sets"][set_name]["groups"]
        groups[group] = json.loads(json.dumps(groups[like]))

    return tweak


@pytest.mark.parametrize(
    ("tweak", "expected"),
    [
        (
            set_group("A", "other", "sealed", "rows", 2),
            ["count_mismatch A other sealed"],
        ),
        (set_group("A", "deep", "dev", "events", 2), ["count_mismatch A deep dev"]),
        (
            drop_group("A-neg", "other"),
            ["count_mismatch A-neg other dev", "count_mismatch A-neg other sealed"],
        ),
        (
            add_group("A-neg", "deep", like="other"),
            ["count_mismatch A-neg deep dev", "count_mismatch A-neg deep sealed"],
        ),
    ],
    ids=["rows", "events", "a_missing_group", "an_extra_group"],
)
def test_group_counts_must_match_the_record(audit_of, tweak, expected):
    """Each group's events and rows on each side, from the rebuilt events, match the
    record's groups: a group missing from either counts as empty."""
    assert audit_of(manifest_rows(), tweak) == expected


def test_check_split_without_a_record_skips_the_counts():
    """The split checks before its record exists, so groups=None skips count_mismatch
    (Task 13, step 9)."""
    rows = manifest_rows()
    rows["A003"]["split"] = "dev"
    assert audit.check_split(sides_of(rows), None) == ["group_one_sided A deep"]


def test_a_set_gone_from_both_sides_fails(tmp_path, monkeypatch, capsys):
    """S-R18: a set the record names, whose two manifests are both header-only, can't
    match the record's counts, so the split's check given the record's groups, and the
    sealed run, both fail on it. groups=None, the split's own call, sees only the sets
    that have rows. The sealed run also finds the emptied dev manifest's hash changed
    (M-2)."""
    record = core_record(sides_of(manifest_rows()))
    rows = {key: row for key, row in manifest_rows().items() if row["set"] == "A"}
    expected = [
        "set_one_sided A-neg",
        "count_mismatch A-neg other dev",
        "count_mismatch A-neg other sealed",
    ]
    assert audit.check_split(sides_of(rows), groups_of(record)) == expected
    assert audit.check_split(sides_of(rows), None) == []

    paths = lay_out(tmp_path)
    for manifest in (paths["A-neg"], paths["run_dir"] / "a_neg" / "manifest.csv"):
        manifest.unlink()
        synth.write_csv(manifest, formats.MANIFEST_COLUMNS, [])
    found = audit.audit_sealed(paths["run_dir"], paths["data"], [paths["record"]])
    assert found == ["manifest_hash A-neg", *expected]
    synth.console(monkeypatch)
    synth.typed(monkeypatch, "yes")
    args = sealed_args(paths["run_dir"], paths["data"], paths["record"])
    assert audit.main(args) == 1
    printed = [summary(1), "FAIL", *SET_A_SPLIT_COUNTS, *found]
    assert capsys.readouterr() == ("\n".join(printed) + "\n", "")


def test_a_record_naming_another_set_is_refused(tmp_path, monkeypatch, capsys):
    """A set the record names may now print in a violation, so a record naming a set
    other than A and A-neg isn't the split's: --dev and --sealed raise ValueError, and
    the name never prints."""

    def tweak(record):
        record["sets"][SENTINEL] = json.loads(json.dumps(record["sets"]["A-neg"]))

    paths = lay_out(tmp_path, tweak=tweak)
    with pytest.raises(ValueError):
        audit.audit_dev(paths["A"], paths["record"])
    synth.console(monkeypatch)
    synth.typed(monkeypatch, "yes")
    args = sealed_args(paths["run_dir"], paths["data"], paths["record"])
    assert audit.main(args) == 1
    assert capsys.readouterr() == (summary(1) + "\n", "stopped: ValueError\n")


def test_set_on_one_side_only(tmp_path):
    """S-R14: a Set A of exactly 2 events, one deep and one other, passes TooFewEvents
    but seals nothing, so its rows sit on one side only. The split stops on it, and so
    does the sealed run. A set whose rows all sit on the sealed side stops too, and the
    clean split, whose sets each have both sides, has no such violation."""
    found = draw.draw_set("A", {"E01": (1, True), "E02": (1, False)})
    assert found == ONE_SIDED_DRAWS["A"]
    sides = sides_of(manifest_rows(TWO_EVENT_A + A_NEG_LAYOUT))
    assert audit.check_split(sides, None) == ["set_one_sided A"]
    paths = lay_out(tmp_path, sides, draws=ONE_SIDED_DRAWS)
    found = audit.audit_sealed(paths["run_dir"], paths["data"], [paths["record"]])
    assert found == ["set_one_sided A"]

    rows = manifest_rows()
    for row in rows.values():
        if row["set"] == "A-neg":
            row["split"] = "sealed"
    assert audit.check_split(sides_of(rows), None) == [
        "set_one_sided A-neg",
        "group_one_sided A-neg other",
    ]
    assert audit.check_split(sides_of(manifest_rows()), None) == []


def test_only_dev_ids_print(tmp_path, monkeypatch, capsys):
    """Every violation names a dev id, in the split's check and in --sealed, and the
    output holds no sealed photo id, event id, car id, crop id, hash, spot, label, path
    or file text. Every text cell of the sealed rows, and of the final truth, holds a
    sentinel, and every sealed date no dev row shares is one no output may hold. An
    event, an event id, an identical photo, a near photo and a car sit on both sides."""
    rows = manifest_rows()
    rows["A005"].update(event_date="2026-08-03", spot_key=f"quezon|{SENTINEL}")
    rows["A006"]["event_id"] = rows["A003"]["event_id"]
    rows["N002"]["photo_sha256"] = rows["A003"]["photo_sha256"]
    rows["N004"]["photo_dhash"] = flip(rows["A005"]["photo_dhash"], 3)
    kept = {"photo_id", "set", "split", "event_id", "event_date", "spot_key"}
    kept |= {"duplicate_of", "photo_sha256", "photo_dhash"}
    sealed = [row for row in rows.values() if row["split"] == "sealed"]
    for number, row in enumerate(sealed, start=1):
        row.update(
            {
                column: SENTINEL
                for column in formats.MANIFEST_COLUMNS
                if column not in kept
            }
        )
        # A005 keeps A004's date and a name of its spot, to join its event. Each other
        # sealed row gets a date no dev row has, which must never print.
        if row["photo_id"] != "A005":
            row.update(spot_key=SENTINEL, event_date=f"1999-12-{number:02d}")
    dev_ids = {row["photo_id"] for row in rows.values() if row["split"] == "dev"}
    sides = sides_of(rows)
    in_split = audit.check_split(sides, None)
    named = [word for line in in_split for word in line.split() if table.is_id(word)]
    assert named and set(named) <= dev_ids

    paths = lay_out(tmp_path, sides)
    set_b = lay_out_set_b(tmp_path, ["B01", "B03"], ["B02", "B03"])
    final = paths["run_dir"] / "set_b" / "truth.csv"
    final_rows = table.read_table(final).rows
    for row in final_rows:
        row.update(
            {
                column: SENTINEL
                for column in formats.TRUTH_COLUMNS
                if column not in ("crop_id", "car_id", "split")
            }
        )
    final.unlink()
    synth.write_csv(final, formats.TRUTH_COLUMNS, final_rows)
    synth.console(monkeypatch)
    synth.typed(monkeypatch, "yes")
    args = sealed_args(paths["run_dir"], paths["data"], paths["record"], set_b)
    assert audit.main(args) == 1

    printed = capsys.readouterr()
    text = printed.out + printed.err
    lines = printed.out.splitlines()
    assert {
        "FAIL",
        "event_on_both_sides A004",
        "event_id_on_both_sides A006",
        "sha256_on_both_sides N002",
        "near_identical_on_both_sides N004",
        "car_on_both_sides B03",
    } <= set(lines)
    named = [word for line in lines for word in line.split() if table.is_id(word)]
    assert set(named) <= dev_ids | {"B01", "B03"}
    assert SENTINEL.casefold() not in text.casefold()
    for row in sealed:
        for column in ("photo_id", "photo_sha256", "photo_dhash"):
            assert row[column] not in text
    assert [row["event_date"] for row in sealed if row["event_date"] in text] == []
    assert "1999" not in text
    assert re.search(r"E[0-9]", text) is None
    assert "B02" not in text and "B03-" not in text
    assert str(tmp_path) not in text


# In --dev.


@pytest.mark.parametrize(
    ("set_name", "counts"),
    [("A", SET_A_DEV_COUNTS), ("A-neg", A_NEG_DEV_COUNTS)],
)
def test_dev_audit_passes_on_a_true_copy(tmp_path, capsys, set_name, counts):
    paths = lay_out(tmp_path)
    assert audit.audit_dev(paths[set_name], paths["record"]) == []
    assert audit.main(dev_args(paths[set_name], paths["record"])) == 0
    assert capsys.readouterr() == ("\n".join(["PASS", *counts]) + "\n", "")


def test_dev_manifest_hash_mismatch(tmp_path):
    """Each manifest is checked against its own set's dev_files entry: A-neg's against
    a_neg_manifest, and Set A's against set_a_manifest."""
    paths = lay_out(
        tmp_path,
        tweak=lambda record: record["dev_files"].update(a_neg_manifest="0" * 64),
    )
    assert audit.audit_dev(paths["A"], paths["record"]) == []
    assert audit.audit_dev(paths["A-neg"], paths["record"]) == ["manifest_hash"]


def test_dev_copy_changed(tmp_path, capsys):
    """One changed byte in a copy gives copy_hash (C219). FAIL prints first, then the
    counts, then each violation."""
    paths = lay_out(tmp_path)
    change_a_byte(paths["data"] / "set_a" / "dev" / "photos" / "A002.jpg")
    assert audit.audit_dev(paths["A"], paths["record"]) == ["copy_hash A002"]
    assert audit.main(dev_args(paths["A"], paths["record"])) == 1
    expected = ["FAIL", *SET_A_DEV_COUNTS, "copy_hash A002"]
    assert capsys.readouterr() == ("\n".join(expected) + "\n", "")


def test_dev_copy_missing(tmp_path):
    paths = lay_out(tmp_path)
    (paths["data"] / "set_a" / "dev" / "photos" / "A004.jpg").unlink()
    assert audit.audit_dev(paths["A"], paths["record"]) == ["copy_missing A004"]


def test_dev_split_value(tmp_path):
    """A row the dev manifest calls sealed, although its hash is the record's."""
    sides = sides_of(manifest_rows())
    sides["dev"][1]["split"] = "sealed"
    assert sides["dev"][1]["photo_id"] == "A002"
    paths = lay_out(tmp_path, sides)
    assert audit.audit_dev(paths["A"], paths["record"]) == ["split_value A002"]


@pytest.mark.parametrize(
    ("tweak", "expected"),
    [
        (set_group("A", "other", "dev", "rows", 3), ["count_mismatch A other dev"]),
        (set_group("A", "deep", "dev", "events", 2), ["count_mismatch A deep dev"]),
        (drop_group("A", "deep"), ["count_mismatch A deep dev"]),
        (set_group("A", "other", "sealed", "rows", 2), []),
    ],
    ids=["rows", "events", "a_missing_group", "sealed_side_unseen"],
)
def test_dev_counts_mismatch(tmp_path, tweak, expected):
    """The dev counts per group match the record's. --dev sees the dev side only."""
    paths = lay_out(tmp_path, tweak=tweak)
    assert audit.audit_dev(paths["A"], paths["record"]) == expected


@pytest.mark.parametrize(
    "name",
    ["..\\sealed\\x.jpg", "../sealed/x.jpg", "sub\\A001.jpg", "C:A001.jpg"]
    + ["A001.jpg:stream", "..", "A001..jpg", ""],
)
def test_dev_photo_file_must_be_a_bare_name(tmp_path, name):
    """A manifest cell can't steer the copy check out of photos\\: a photo_file with a
    folder, a drive, a stream or .., or none at all, is a violation and isn't opened."""
    rows = manifest_rows()
    rows["A001"]["photo_file"] = name
    paths = lay_out(tmp_path, sides_of(rows))
    assert audit.audit_dev(paths["A"], paths["record"]) == ["photo_file A001"]


def test_dev_never_opens_a_file_outside_photos(tmp_path):
    """With a photo_file of ..\\sealed\\x.jpg and a file there that would hash right,
    the audit opens only the record, the manifest and copies inside photos\\."""
    rows = manifest_rows()
    rows["A001"]["photo_file"] = "..\\sealed\\x.jpg"
    paths = lay_out(tmp_path, sides_of(rows))
    decoy = paths["data"] / "set_a" / "dev" / "sealed" / "x.jpg"
    decoy.parent.mkdir()
    decoy.write_bytes(photo("A001"))
    code, events = synth.opened_paths(AUDIT, dev_args(paths["A"], paths["record"]))
    assert code == 1
    opened = {Path(path) for _, path in events if inside(path, tmp_path)}
    photos = paths["data"] / "set_a" / "dev" / "photos"
    assert opened == {
        paths["record"],
        paths["A"],
        photos / "A002.jpg",
        photos / "A004.jpg",
        photos / "A006.jpg",
    }


def test_dev_refuses_a_photo_file_named_sealed(tmp_path, capsys):
    """A copy's path is checked like any other before it opens (C222)."""
    rows = manifest_rows()
    rows["A001"]["photo_file"] = "Sealed"
    paths = lay_out(tmp_path, sides_of(rows))
    with pytest.raises(SystemExit) as stop:
        audit.audit_dev(paths["A"], paths["record"])
    assert stop.value.code == 2
    assert capsys.readouterr() == ("", REFUSED)


@pytest.mark.parametrize("flag", ["--dev", "--record"])
def test_dev_refuses_sealed_paths(tmp_path, capsys, flag):
    """--dev or --record inside a folder named sealed is refused before anything opens,
    although the file is there to read (C222)."""
    paths = lay_out(tmp_path)
    given = {"--dev": paths["A"], "--record": paths["record"]}
    moved = tmp_path / "sealed" / given[flag].name
    moved.parent.mkdir()
    shutil.copyfile(given[flag], moved)
    given[flag] = moved
    args = dev_args(given["--dev"], given["--record"])
    with pytest.raises(SystemExit) as stop:
        audit.main(args)
    assert stop.value.code == 2
    assert capsys.readouterr() == ("", REFUSED)
    code, events = synth.opened_paths(AUDIT, args)
    assert code == 2
    assert [item for item in events if inside(item[1], tmp_path)] == []


@pytest.mark.parametrize("flag", ["--dev", "--record"])
def test_dev_names_a_missing_path(tmp_path, capsys, flag):
    """A missing file is named by its flag alone, before anything is read."""
    paths = lay_out(tmp_path)
    given = {"--dev": paths["A"], "--record": paths["record"]}
    given[flag] = tmp_path / "missing" / "x.csv"
    assert audit.main(dev_args(given["--dev"], given["--record"])) == 2
    assert capsys.readouterr() == (f"{flag} missing\n", "")


@pytest.mark.parametrize(
    "data",
    [
        b"\xff\xfe{}",
        b"{",
        b"[]\n",
        b"null\n",
        b"{}\n",
        b'{"tool": "eval/data/other.py"}\n',
        record_io.record_bytes({"tool": "eval/data/seal_set_d.py"}),
    ],
    ids=["not_utf8", "not_json", "a_list", "null", "no_tool", "other_tool", "set_d"],
)
def test_dev_record_unreadable(tmp_path, capsys, data):
    """A record that isn't UTF-8 JSON, has no record kind, or isn't the split's, is
    refused naming no path (S-R16)."""
    paths = lay_out(tmp_path)
    bad = tmp_path / "records" / "bad.json"
    bad.write_bytes(data)
    assert audit.main(dev_args(paths["A"], bad)) == 2
    assert capsys.readouterr() == ("--record unreadable\n", "")


@pytest.mark.parametrize("change", ["header", "two_sets", "bad_id"])
def test_dev_manifest_the_split_did_not_write(tmp_path, change):
    """A manifest with another header, rows of two sets, or an id outside C221's
    pattern raises ValueError, whose message names nothing of it."""
    rows = manifest_rows()
    columns = formats.MANIFEST_COLUMNS
    dev = [row for row in rows.values() if row["split"] == "dev"]
    if change == "header":
        columns = columns + (SENTINEL,)
    elif change == "bad_id":
        dev[0]["photo_id"] = SENTINEL
    else:
        dev = [row for row in dev if row["set"] == "A"] + [rows["N002"]]
    paths = lay_out(tmp_path)
    paths["A"].unlink()
    synth.write_csv(paths["A"], columns, dev)
    with pytest.raises(ValueError) as refused:
        audit.audit_dev(paths["A"], paths["record"])
    assert SENTINEL not in str(refused.value)
    assert re.search(r"[AN][0-9]{3}", str(refused.value)) is None


# In --sealed.


def test_sealed_run_prints_pass_and_the_counts(tmp_path, monkeypatch, capsys):
    """Rene's run, after yes: PASS, then each set's counts per group and side, and Set
    B's cars and crops per side. A Set D record adds no count."""
    paths = lay_out(tmp_path)
    set_b = lay_out_set_b(tmp_path, ["B01", "B03"], ["B02", "B04"])
    set_d = committed(tmp_path, "lusot-sealed-set-d", set_d_core())
    synth.console(monkeypatch)
    synth.typed(monkeypatch, "yes")
    args = sealed_args(paths["run_dir"], paths["data"], paths["record"], set_b, set_d)
    assert audit.main(args) == 0
    expected = [summary(3), "PASS", *SPLIT_COUNTS]
    expected += ["set_b dev cars=2 crops=4", "set_b sealed cars=2 crops=4"]
    assert capsys.readouterr() == ("\n".join(expected) + "\n", "")


def test_sealed_audit_hashes_each_archive(tmp_path):
    """Each record's archive, beside RUN_DIR, must hash to the record's archive.sha256
    (C220): a changed byte, or a missing file, gives archive_hash."""
    paths = lay_out(tmp_path)
    set_d = committed(tmp_path, "lusot-sealed-set-d", set_d_core())
    records = [paths["record"], set_d]
    sealed = paths["data"] / "sealed"
    assert audit.audit_sealed(paths["run_dir"], paths["data"], records) == []
    change_a_byte(sealed / "lusot-sealed.7z")
    assert audit.audit_sealed(paths["run_dir"], paths["data"], records) == [
        "archive_hash lusot-sealed.7z"
    ]
    (sealed / "lusot-sealed-set-d.7z").unlink()
    assert audit.audit_sealed(paths["run_dir"], paths["data"], records) == [
        "archive_hash lusot-sealed.7z",
        "archive_hash lusot-sealed-set-d.7z",
    ]


@pytest.mark.parametrize("set_name", ["A", "A-neg"])
def test_sealed_rechecks_each_dev_manifest_hash(tmp_path, set_name):
    """M-2: --sealed checks each development manifest's SHA-256 against the record's
    dev_files entry, as --dev does. One changed byte, in a cell no check reads, gives
    manifest_hash and the set's name, and nothing else."""
    paths = lay_out(tmp_path)
    manifest = paths[set_name]
    manifest.write_bytes(manifest.read_bytes().replace(b"Manila", b"Manilo", 1))
    found = audit.audit_sealed(paths["run_dir"], paths["data"], [paths["record"]])
    assert found == [f"manifest_hash {set_name}"]


@pytest.mark.parametrize(
    "name",
    [
        "../lusot-sealed-set-d.7z",
        "..\\lusot-sealed-set-d.7z",
        "run-1/lusot-sealed-set-d.7z",
        "C:lusot-sealed-set-d.7z",
        "lusot-sealed-set-d.7z:x.7z",
        "lusot-sealed-set-d.zip",
        "",
        "lusot sealed.7z",
        "lusot-se\N{LATIN SMALL LETTER N WITH TILDE}al.7z",
        "a" * 101 + ".7z",
        ".lusot.7z",
        5,
    ],
    ids=[
        "parent",
        "parent_backslash",
        "folder",
        "drive",
        "stream",
        "zip",
        "empty",
        "a_space",
        "not_ascii",
        "too_long",
        "a_leading_dot",
        "not_text",
    ],
)
def test_sealed_archive_name_must_be_bare(tmp_path, monkeypatch, name):
    """A record can't steer the hash check out of RUN_DIR's parent, or print what it
    likes: an archive.file that isn't 1 to 100 ASCII letters, digits, dots, hyphens or
    underscores, starting with a letter or digit, then .7z (S-R18), is a violation, and
    nothing is hashed or printed."""
    hashed = []

    def spy(path):
        hashed.append(path)
        return "0" * 64

    set_d = committed(
        tmp_path,
        "lusot-sealed-set-d",
        set_d_core(),
        tweak=lambda record: record["archive"].update(file=name),
    )
    run_dir = tmp_path / "data" / "sealed" / "run-1"
    run_dir.mkdir()
    monkeypatch.setattr(table, "sha256_file", spy)
    assert audit.audit_sealed(run_dir, tmp_path / "data", [set_d]) == ["archive_name"]
    assert hashed == []


def test_sealed_archive_name_may_be_103_characters(tmp_path):
    """The longest name the pattern takes, 100 characters before .7z, is checked by
    its hash."""
    set_d = committed(tmp_path, "a" * 100, set_d_core())
    data = tmp_path / "data"
    run_dir = data / "sealed" / "run-1"
    run_dir.mkdir()
    assert audit.audit_sealed(run_dir, data, [set_d]) == []
    change_a_byte(data / "sealed" / ("a" * 100 + ".7z"))
    assert audit.audit_sealed(run_dir, data, [set_d]) == [
        "archive_hash " + "a" * 100 + ".7z"
    ]


@pytest.mark.parametrize(
    ("final_cars", "counts", "expected"),
    [
        (["B02", "B04"], SET_B_COUNTS, []),
        (["B02", "B03"], SET_B_COUNTS, ["car_on_both_sides B03"]),
        (["B02", "B04"], SET_B_COUNTS | {"cars": 3}, ["count_mismatch set_b"]),
        (["B02", "B04"], SET_B_COUNTS | {"crops": 5}, ["count_mismatch set_b"]),
    ],
    ids=["clean", "a_car_on_both_sides", "cars", "crops"],
)
def test_sealed_set_b_cars_on_both_sides(tmp_path, final_cars, counts, expected):
    """A final car in the development truth is named by that dev id, and the final
    truth's cars and crops match the record's counts (C214)."""
    set_b = lay_out_set_b(tmp_path, ["B01", "B03"], final_cars, counts)
    data = tmp_path / "data"
    assert audit.audit_sealed(data / "sealed" / "run-1", data, [set_b]) == expected


def test_sealed_set_d_record_checks_the_hash_only(tmp_path):
    """RUN_DIR and the data folder hold nothing else, so a read would fail."""
    set_d = committed(tmp_path, "lusot-sealed-set-d", set_d_core())
    data = tmp_path / "data"
    run_dir = data / "sealed" / "run-1"
    run_dir.mkdir()
    assert audit.audit_sealed(run_dir, data, [set_d]) == []
    change_a_byte(data / "sealed" / "lusot-sealed-set-d.7z")
    assert audit.audit_sealed(run_dir, data, [set_d]) == [
        "archive_hash lusot-sealed-set-d.7z"
    ]


@pytest.mark.parametrize(
    "case", ["run_dir_outside", "dev_root_inside", "record_inside"]
)
def test_sealed_path_rules(tmp_path, capsys, case):
    """On the strings alone, before the console check and before anything is read:
    RUN_DIR must be inside a folder named sealed, and --dev-root and every --record
    must not be (C202)."""
    paths = lay_out(tmp_path)
    run_dir, data, records = paths["run_dir"], paths["data"], [paths["record"]]
    expected = REFUSED
    if case == "run_dir_outside":
        run_dir = data / "run-1"
        expected = "refused: --sealed must be inside a folder named sealed\n"
    elif case == "dev_root_inside":
        data = data / "sealed"
    else:
        records.append(data / "sealed" / "split.json")
        shutil.copyfile(paths["record"], records[-1])
    args = sealed_args(run_dir, data, *records)
    with pytest.raises(SystemExit) as stop:
        audit.main(args)
    assert stop.value.code == 2
    assert capsys.readouterr() == ("", expected)
    code, events = synth.opened_paths(AUDIT, args)
    assert code == 2
    assert [item for item in events if inside(item[1], tmp_path)] == []


def test_sealed_refuses_without_a_console(tmp_path):
    """With stdin on NUL and stdout piped, --sealed stops at the console check, before
    any given path is statted or read. None of them exists, so an existence check
    would have said so."""
    data = tmp_path / "data"
    args = sealed_args(data / "sealed" / "run-1", data, tmp_path / "records" / "s.json")
    done = subprocess.run(
        [sys.executable, str(AUDIT), *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (2, "", NO_CONSOLE)
    assert not data.exists()


def test_sealed_needs_yes(tmp_path, monkeypatch, capsys):
    """Without yes, the audit reads nothing and prints no result."""
    paths = lay_out(tmp_path)
    synth.console(monkeypatch)
    synth.typed(monkeypatch, "no")
    with pytest.raises(SystemExit) as stop:
        audit.main(sealed_args(paths["run_dir"], paths["data"], paths["record"]))
    assert stop.value.code == 2
    assert capsys.readouterr() == (summary(1) + "\n", "stopped: nothing was done\n")


@pytest.mark.parametrize("flag", ["--sealed", "--dev-root", "--record"])
def test_sealed_names_a_missing_path(tmp_path, monkeypatch, capsys, flag):
    """After the console check and before yes, a missing path is named by its flag."""
    paths = lay_out(tmp_path)
    run_dir, data, records = paths["run_dir"], paths["data"], [paths["record"]]
    if flag == "--sealed":
        run_dir = data / "sealed" / "run-2"
    elif flag == "--dev-root":
        data = tmp_path / "other"
    else:
        records.append(tmp_path / "records" / "missing.json")
    synth.console(monkeypatch)
    synth.typed(monkeypatch)  # no answer: yes is never asked
    assert audit.main(sealed_args(run_dir, data, *records)) == 2
    assert capsys.readouterr() == (f"{flag} missing\n", "")


@pytest.mark.parametrize("change", ["header", "other_set"])
def test_sealed_stops_on_a_manifest_the_split_did_not_write(
    tmp_path, monkeypatch, capsys, change
):
    """A manifest the split didn't write raises, which --sealed prints as its class
    alone, failing closed."""
    paths = lay_out(tmp_path)
    rows = manifest_rows()
    manifest = paths["run_dir"] / "set_a" / "manifest.csv"
    manifest.unlink()
    if change == "header":
        columns = formats.MANIFEST_COLUMNS + ("extra",)
        synth.write_csv(manifest, columns, [rows["A003"], rows["A005"]])
    else:
        synth.write_csv(manifest, formats.MANIFEST_COLUMNS, [rows["N001"]])
    synth.console(monkeypatch)
    synth.typed(monkeypatch, "yes")
    args = sealed_args(paths["run_dir"], paths["data"], paths["record"])
    assert audit.main(args) == 1
    assert capsys.readouterr() == (summary(1) + "\n", "stopped: ValueError\n")


@pytest.mark.parametrize(
    "data", [b"[]\n", b"null\n", b'{"tool": "eval/data/other.py"}\n']
)
def test_sealed_stops_on_a_malformed_record(tmp_path, monkeypatch, capsys, data):
    """A record with no record kind stops the run as ValueError (S-R16)."""
    paths = lay_out(tmp_path)
    bad = tmp_path / "records" / "bad.json"
    bad.write_bytes(data)
    synth.console(monkeypatch)
    synth.typed(monkeypatch, "yes")
    args = sealed_args(paths["run_dir"], paths["data"], paths["record"], bad)
    assert audit.main(args) == 1
    assert capsys.readouterr() == (summary(2) + "\n", "stopped: ValueError\n")


@pytest.mark.parametrize(
    "args",
    [
        ["--dev", "m.csv"],
        ["--dev", "m.csv", "--record", "a.json", "--record", "b.json"],
        ["--dev", "m.csv", "--record", "a.json", "--dev-root", "d"],
        ["--sealed", "sealed", "--record", "a.json"],
        ["--dev", "m.csv", "--sealed", "sealed", "--record", "a.json"],
    ],
    ids=["no_record", "two_records", "dev_root", "no_dev_root", "both_modes"],
)
def test_usage_errors(capsys, args):
    with pytest.raises(SystemExit) as stop:
        audit.main(args)
    assert stop.value.code == 2
    assert capsys.readouterr().out == ""


def test_audit_imports_only_the_standard_library():
    """A fresh interpreter that imports the audit loads no numpy, OpenCV or py7zr, nor
    photos or archive, which load them, so the script runs with dependencies = []."""
    probe = (
        f"import sys; sys.path.insert(0, {json.dumps(str(DATA))}); import audit; "
        "print(sorted({'numpy', 'cv2', 'py7zr', 'photos', 'archive'} "
        "& set(sys.modules)))"
    )
    done = subprocess.run(
        [sys.executable, "-c", probe],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "[]\n", "")
