"""Tests for the committed records: their kinds, fields, bytes and writing (C216, §5.9).

Every row, draw and archive fact is synthetic, built here. git runs only in folders
under tmp_path.
"""

import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import archive
import draw
import formats
import pytest
import record_io
import synth

DATA = Path(__file__).resolve().parents[1]  # eval/data
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+08:00")
UNKNOWN = {"commit": "unknown", "dirty": True}
BASE = {"tool", "git", "date", "python"}
# The ids no record may hold: Set A's and A-neg's photos, events, Set B's cars and Set
# D's photos.
IDS = re.compile(rb"\b[AN][0-9]{3}\b|\bE[0-9]{2,}\b|\bB[0-9]{2}\b|\bD[0-9]{2}\b")
PREFIX = {"A": "A", "A-neg": "N"}

INPUTS = {"set_a_log": "1a" * 32, "a_neg_log": "2b" * 32, "m8": "3c" * 32}
DEV_FILES = {
    "set_a_manifest": "4d" * 32,
    "set_a_m8": "5e" * 32,
    "a_neg_manifest": "6f" * 32,
}
# Task 13's synthetic Set A, each event's rows, and Task 10's golden draw of it.
SET_A_EVENTS = {
    "E01": 3,
    "E02": 2,
    "E03": 2,
    "E04": 2,
    "E05": 2,
    "E06": 2,
    "E07": 2,
    "E08": 1,
    "E09": 1,
    "E10": 1,
    "E11": 1,
    "E12": 1,
}
SET_A_DRAW = {
    "deep": draw.GroupDraw(
        group="deep",
        sealed=frozenset({"E02", "E09"}),
        dev=frozenset({"E04", "E06", "E11"}),
        rows=8,
        sealed_rows=3,
        moved=None,
    ),
    "other": draw.GroupDraw(
        group="other",
        sealed=frozenset({"E01", "E07"}),
        dev=frozenset({"E03", "E05", "E08", "E10", "E12"}),
        rows=12,
        sealed_rows=5,
        moved=None,
    ),
}
# Two one-row A-neg events: the walk seals neither, so E01 moves to sealed (C204), and
# the share, 1 of 2, is over A-neg's cap.
A_NEG_EVENTS = {"E01": 1, "E02": 1}
A_NEG_DRAW = {
    "other": draw.GroupDraw(
        group="other",
        sealed=frozenset({"E01"}),
        dev=frozenset({"E02"}),
        rows=2,
        sealed_rows=1,
        moved="smallest_to_sealed",
    )
}
# Set B's and Set D's counts as their tools sum them, with no id (Tasks 16 and 18).
SET_B_INPUTS = {"cars": "7a" * 32, "masks_files": "8b" * 32, "dev_cars": "9c" * 32}
SET_B_COUNTS = {
    "cars": 5,
    "photos": 6,
    "crops": 24,
    "wheels": 12,
    "wheels_without_rim": 1,
    "drops": {"no_consent": 1, "no_aspect_ratio": 1},
    "warnings": 2,
    "band": {"below_gutter": 6, "gutter": 6, "half_knee": 6, "half_tire": 6},
    "size_bin": {"full": 12, "small": 12},
    "vehicle_type": {"sedan_hatch": 16, "suv_mpv": 8},
    "view": {"side": 20, "angled": 4},
}
SET_D_INPUTS = {"set_d_log": "ad" * 32}
SET_D_COUNTS = {
    "photos": 3,
    "vehicle_type": {"jeepney": 2, "sedan_hatch": 1},
    "wheel": {"left": 2, "right": 1},
}
FREEZE = {"file": "2026-11-01-freeze.json", "sha256": "be" * 32}


def cells(set_name: str, photo_id: str, event_id: str, split: str) -> dict[str, str]:
    """A manifest row as the split writes it. The fact columns hold list values, as the
    intake guarantees, and the id columns ids. Every other cell holds a sentinel, which
    no record may hold."""
    row = {column: f"Sentinel {column}" for column in formats.MANIFEST_COLUMNS}
    row.update(
        photo_id=photo_id,
        set=set_name,
        split=split,
        event_id=event_id,
        same_spot_as=photo_id,
        duplicate_of=photo_id,
        photo_file=f"{photo_id}.jpg",
        poster_kind="mmda" if set_name == "A" else "other",
        match="same_post" if set_name == "A" else "",
        metro_manila="yes",
        label_in_image="no",
        reference_visible="wheel",
        duplicate="no",
        decodes="yes",
        surface="" if set_name == "A" else "dry",
    )
    return row


def layout(
    set_name: str, events: dict[str, int], sealed: frozenset[str]
) -> dict[str, list[dict[str, str]]]:
    """Each side's manifest rows: each event's photos, numbered in event order, on its
    side."""
    sides: dict[str, list[dict[str, str]]] = {"dev": [], "sealed": []}
    number = 0
    for event_id, count in events.items():
        split = "sealed" if event_id in sealed else "dev"
        for _ in range(count):
            number += 1
            photo_id = f"{PREFIX[set_name]}{number:03d}"
            sides[split].append(cells(set_name, photo_id, event_id, split))
    return sides


def golden_split(repo: Path) -> dict:
    """The split record of Task 13's layout under Task 10's golden draw, beside the
    two-event A-neg above, with one missing M8 photo row allowed."""
    set_a_sealed = SET_A_DRAW["deep"].sealed | SET_A_DRAW["other"].sealed
    return record_io.split_record(
        repo=repo,
        inputs=INPUTS,
        draws={"A": SET_A_DRAW, "A-neg": A_NEG_DRAW},
        sides={
            "A": layout("A", SET_A_EVENTS, set_a_sealed),
            "A-neg": layout("A-neg", A_NEG_EVENTS, A_NEG_DRAW["other"].sealed),
        },
        missing_m8=1,
        dev_files=DEV_FILES,
    )


@pytest.fixture
def git_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """git as on a fresh install: no user or system config, so no identity, hook or
    signing of this PC's, and no repo looked for above tmp_path."""
    config = tmp_path / "empty.gitconfig"
    config.write_bytes(b"")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def git(folder: Path, *args: str) -> str:
    """Run git in the folder, as a synthetic author, and return what it prints."""
    done = subprocess.run(
        ["git", "-c", "user.name=synthetic", "-c", "user.email=synthetic", *args],
        cwd=folder,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=True,
    )
    return done.stdout


def test_split_record_per_group_counts(tmp_path):
    """C204's record: each group's draw reaches it exactly, beside each side's counts
    per fact value and the set's share, with the seed, the inputs' and the development
    files' hashes, the audit and the M8 photo rows allowed missing."""
    record = golden_split(tmp_path)
    assert record.keys() == BASE | {
        "seed",
        "inputs",
        "sets",
        "missing_m8_photo_rows",
        "audit",
        "dev_files",
    }
    assert record["tool"] == "eval/data/split.py"
    assert (record["seed"], record["missing_m8_photo_rows"], record["audit"]) == (
        20261030,
        1,
        "PASS",
    )
    assert record["inputs"] == {
        "set_a_log": "1a" * 32,
        "a_neg_log": "2b" * 32,
        "m8": "3c" * 32,
    }
    assert record["dev_files"] == {
        "set_a_manifest": "4d" * 32,
        "set_a_m8": "5e" * 32,
        "a_neg_manifest": "6f" * 32,
    }
    assert record["sets"]["A"]["groups"] == {
        "deep": {
            "events": 5,
            "rows": 8,
            "dev": {"events": 3, "rows": 5},
            "sealed": {"events": 2, "rows": 3},
            "moved": None,
        },
        "other": {
            "events": 7,
            "rows": 12,
            "dev": {"events": 5, "rows": 7},
            "sealed": {"events": 2, "rows": 5},
            "moved": None,
        },
    }
    assert record["sets"]["A-neg"]["groups"] == {
        "other": {
            "events": 2,
            "rows": 2,
            "dev": {"events": 1, "rows": 1},
            "sealed": {"events": 1, "rows": 1},
            "moved": "smallest_to_sealed",
        }
    }
    set_a = record["sets"]["A"]
    assert (set_a["share"], set_a["share_in_range"]) == ("8/20", True)
    assert set_a["dev"] == {
        "rows": 12,
        "events": 8,
        "facts": {
            "poster_kind": {"mmda": 12},
            "match": {"same_post": 12},
            "metro_manila": {"yes": 12},
            "label_in_image": {"no": 12},
            "reference_visible": {"wheel": 12},
            "duplicate": {"no": 12},
            "decodes": {"yes": 12},
        },
    }
    assert set_a["sealed"] == {
        "rows": 8,
        "events": 4,
        "facts": {
            "poster_kind": {"mmda": 8},
            "match": {"same_post": 8},
            "metro_manila": {"yes": 8},
            "label_in_image": {"no": 8},
            "reference_visible": {"wheel": 8},
            "duplicate": {"no": 8},
            "decodes": {"yes": 8},
        },
    }
    a_neg = record["sets"]["A-neg"]
    assert (a_neg["share"], a_neg["share_in_range"]) == ("1/2", False)
    a_neg_side = {
        "rows": 1,
        "events": 1,
        "facts": {
            "poster_kind": {"other": 1},
            "match": {"": 1},
            "metro_manila": {"yes": 1},
            "label_in_image": {"no": 1},
            "reference_visible": {"wheel": 1},
            "duplicate": {"no": 1},
            "decodes": {"yes": 1},
            "surface": {"dry": 1},
        },
    }
    assert (a_neg["dev"], a_neg["sealed"]) == (a_neg_side, a_neg_side)


@pytest.mark.parametrize(
    ("set_name", "sealed", "rows", "share", "in_range"),
    [
        ("A", 8, 20, "8/20", True),  # 2/5, which a float 0.4 lies above (Task 10)
        ("A", 120, 300, "120/300", True),  # 2/5, the target
        ("A", 135, 300, "135/300", True),  # 9/20, the cap
        ("A", 119, 300, "119/300", False),
        ("A", 136, 300, "136/300", False),
        ("A-neg", 100, 300, "100/300", True),  # 1/3, the target
        ("A-neg", 120, 300, "120/300", True),  # 2/5, the cap
        ("A-neg", 99, 300, "99/300", False),
        ("A-neg", 121, 300, "121/300", False),
    ],
)
def test_share_is_exact_and_its_range_inclusive(
    tmp_path, set_name, sealed, rows, share, in_range
):
    """The share is the set's sealed rows over all its rows, never reduced, and its
    range runs from the set's target to its cap, both included, compared exactly."""
    photo_id = f"{PREFIX[set_name]}001"
    sides = {
        set_name: {
            "dev": [cells(set_name, photo_id, "E02", "dev")] * (rows - sealed),
            "sealed": [cells(set_name, photo_id, "E01", "sealed")] * sealed,
        }
    }
    draws = {
        set_name: {
            "other": draw.GroupDraw(
                group="other",
                sealed=frozenset({"E01"}),
                dev=frozenset({"E02"}),
                rows=rows,
                sealed_rows=sealed,
                moved=None,
            )
        }
    }
    record = record_io.split_record(
        repo=tmp_path,
        inputs=INPUTS,
        draws=draws,
        sides=sides,
        missing_m8=0,
        dev_files=DEV_FILES,
    )
    found = record["sets"][set_name]
    assert (found["share"], found["share_in_range"]) == (share, in_range)


def test_record_kinds(tmp_path):
    """The audit tells records apart by their tool (C220), also once read back. Any
    other tool, Task 17's freeze record's among them, has no kind, and the error names
    none of the three tools."""
    records = {
        "split": record_io.split_record(
            repo=tmp_path,
            inputs=INPUTS,
            draws={},
            sides={},
            missing_m8=0,
            dev_files=DEV_FILES,
        ),
        "set_b_final": record_io.set_b_final_record(
            repo=tmp_path,
            counts=SET_B_COUNTS,
            generator_version="g1",
            generator_seed=7,
            inputs=SET_B_INPUTS,
        ),
        "set_d": record_io.set_d_record(
            repo=tmp_path, counts=SET_D_COUNTS, inputs=SET_D_INPUTS, extends=None
        ),
    }
    for kind, record in records.items():
        assert record_io.record_kind(record) == kind
        assert record_io.record_kind(json.loads(record_io.record_bytes(record))) == kind
    others = [
        record_io.base_record("eval/data/freeze_record.py", tmp_path),
        {"tool": "eval\\data\\split.py"},
        {"tool": ["eval/data/split.py"]},
        {"tool": None},
        {},
    ]
    for record in others:
        with pytest.raises(ValueError) as refused:
            record_io.record_kind(record)
        assert [
            tool for tool in record_io.RECORD_KINDS if tool in str(refused.value)
        ] == []


def test_set_b_and_set_d_records_hold_their_input_hashes(tmp_path):
    """Set B's final-car record and Set D's record hold their inputs' hashes and their
    counts as given, and Set D's names the freeze record it extends, when there is one
    (C216)."""
    set_b = record_io.set_b_final_record(
        repo=tmp_path,
        counts=SET_B_COUNTS,
        generator_version="g1",
        generator_seed=20261101,
        inputs=SET_B_INPUTS,
    )
    assert set_b["tool"] == "eval/set_b/generate.py"
    assert {key: set_b[key] for key in set_b.keys() - BASE} == {
        "generator_version": "g1",
        "generator_seed": 20261101,
        "inputs": {"cars": "7a" * 32, "masks_files": "8b" * 32, "dev_cars": "9c" * 32},
        "counts": SET_B_COUNTS,
        "overlap_check": "PASS",
    }
    set_d = record_io.set_d_record(
        repo=tmp_path, counts=SET_D_COUNTS, inputs=SET_D_INPUTS, extends=FREEZE
    )
    assert set_d["tool"] == "eval/data/seal_set_d.py"
    assert {key: set_d[key] for key in set_d.keys() - BASE} == {
        "inputs": {"set_d_log": "ad" * 32},
        "counts": SET_D_COUNTS,
        "extends": {"file": "2026-11-01-freeze.json", "sha256": "be" * 32},
    }
    alone = record_io.set_d_record(
        repo=tmp_path, counts=SET_D_COUNTS, inputs=SET_D_INPUTS, extends=None
    )
    assert alone.keys() - BASE == {"inputs", "counts"}


def test_record_holds_no_ids_labels_links_or_spots(tmp_path):
    """§5.9: no record holds an id, a label, a link, a spot or any other text of a row.
    The split's manifest rows hold a sentinel in every text cell and ids in their id
    cells. Set B's and Set D's builders take counts, not rows, so they get counts as
    their tools sum them. Every builder gets a repo folder named with a sentinel and
    ids, a path no record may hold."""
    repo = tmp_path / "Sentinel A001 N001 E01 B02 D01"
    repo.mkdir()
    facts = archive.ArchiveFacts(file="lusot-sealed.7z", size=4096, sha256="0f" * 32)
    records = [
        golden_split(repo) | {"archive": record_io.archive_block(facts)},
        record_io.set_b_final_record(
            repo=repo,
            counts=SET_B_COUNTS,
            generator_version="g1",
            generator_seed=20261101,
            inputs=SET_B_INPUTS,
        ),
        record_io.set_d_record(
            repo=repo, counts=SET_D_COUNTS, inputs=SET_D_INPUTS, extends=FREEZE
        ),
    ]
    for record in records:
        data = record_io.record_bytes(record)
        assert b"sentinel" not in data.lower()
        assert IDS.findall(data) == []


def test_record_bytes_are_stable():
    """The same record in another key order, nested too, gives the same bytes: sorted
    keys, a two-space indent, ASCII only and a final newline."""
    first = {"b": {"y": 1, "x": [2, "Parañaque"]}, "a": True, "c": None}
    second = {"c": None, "a": True, "b": {"x": [2, "Parañaque"], "y": 1}}
    data = record_io.record_bytes(first)
    assert data == record_io.record_bytes(second)
    assert data == (
        b'{\n  "a": true,\n  "b": {\n    "x": [\n      2,\n      "Para\\u00f1aque"\n'
        b'    ],\n    "y": 1\n  },\n  "c": null\n}\n'
    )


def test_write_record_never_overwrites(tmp_path):
    """C216: a record is created once, in a new folder if need be, and never rewritten.
    write_record returns the SHA-256 of the bytes it wrote."""
    path = tmp_path / "records" / "2026-10-30-split.json"
    digest = record_io.write_record(
        path, {"tool": "eval/data/split.py", "seed": 20261030}
    )
    written = b'{\n  "seed": 20261030,\n  "tool": "eval/data/split.py"\n}\n'
    assert path.read_bytes() == written
    assert digest == hashlib.sha256(written).hexdigest()
    with pytest.raises(FileExistsError):
        record_io.write_record(path, {"tool": "eval/data/split.py", "seed": 1})
    assert path.read_bytes() == written


def test_write_record_takes_a_path_from_the_repo_root(tmp_path, monkeypatch):
    """Rene's commands give a record's path from the repo root, as
    eval\\data\\records\\<date>-split.json, so it lands in the checkout that holds the
    tools (S-R13)."""
    monkeypatch.chdir(tmp_path)
    record_io.write_record(Path("eval", "data", "records", "r.json"), {"a": 1})
    written = tmp_path / "eval" / "data" / "records" / "r.json"
    assert written.read_bytes() == b'{\n  "a": 1\n}\n'


def test_archive_block_names_the_file_its_size_and_hash():
    """The sealed run finds the archive as run_dir.parent / file and checks its hash
    first (C220), so the file is the bare name, copied as given."""
    facts = archive.ArchiveFacts(file="lusot-sealed.7z", size=4096, sha256="0f" * 32)
    assert record_io.archive_block(facts) == {
        "file": "lusot-sealed.7z",
        "size": 4096,
        "sha256": "0f" * 32,
    }


def test_git_state_of_a_repo(tmp_path, git_alone, capfd):
    """The commit checked out, and whether the tree differs from it: an untracked file
    or a changed one makes it dirty. git's own output never reaches the console."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "a.txt").write_bytes(b"a\n")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "synthetic")
    head = git(repo, "rev-parse", "HEAD").strip()
    assert re.fullmatch("[0-9a-f]{40}", head)
    capfd.readouterr()
    assert record_io.git_state(repo) == {"commit": head, "dirty": False}
    (repo / "b.txt").write_bytes(b"b\n")
    assert record_io.git_state(repo) == {"commit": head, "dirty": True}
    (repo / "b.txt").unlink()
    (repo / "a.txt").write_bytes(b"changed\n")
    assert record_io.git_state(repo) == {"commit": head, "dirty": True}
    assert capfd.readouterr() == ("", "")


def test_git_state_outside_a_repo(tmp_path, git_alone, capfd):
    """A folder that isn't a repo, or doesn't exist, gives an unknown commit and a dirty
    tree, since a record must never claim a clean tree it couldn't check. git's error
    never reaches the console."""
    plain = tmp_path / "plain"
    plain.mkdir()
    assert record_io.git_state(plain) == UNKNOWN
    assert record_io.git_state(tmp_path / "missing") == UNKNOWN
    assert capfd.readouterr() == ("", "")


@pytest.mark.parametrize(
    "error",
    [subprocess.TimeoutExpired("git", 30), FileNotFoundError("git")],
    ids=["timeout", "no_git"],
)
def test_git_state_fails_closed_when_git_cant_answer(tmp_path, monkeypatch, error):
    """A git that times out, or none on the PATH, gives unknown and dirty. Each call has
    a timeout, so a git that hangs can't hold up a tool."""
    timeouts = []

    def run(args, **kwargs):
        timeouts.append(kwargs.get("timeout"))
        raise error

    monkeypatch.setattr(subprocess, "run", run)
    assert record_io.git_state(tmp_path) == UNKNOWN
    assert len(timeouts) == 1
    assert timeouts[0] is not None and timeouts[0] > 0


def test_git_state_needs_a_full_commit_hash(tmp_path, monkeypatch):
    """A commit that isn't 40 hex digits, such as a SHA-256 repo's 64, is unknown, and
    the tree counts as dirty."""

    def run(args, **kwargs):
        out = b"f" * 64 + b"\n" if "rev-parse" in args else b""
        return subprocess.CompletedProcess(args, 0, stdout=out, stderr=b"")

    monkeypatch.setattr(subprocess, "run", run)
    assert record_io.git_state(tmp_path) == UNKNOWN


def test_manila_now_is_manila_time_to_the_second():
    """+08:00 all year: Manila keeps no daylight saving, and zoneinfo would need the
    tzdata package on Windows."""
    before = datetime.now(UTC).replace(microsecond=0)
    now = record_io.manila_now()
    after = datetime.now(UTC)
    assert DATE.fullmatch(now)
    assert before <= datetime.fromisoformat(now) <= after


def test_base_record_starts_every_record(tmp_path, git_alone):
    """Every record, Task 17's look and freeze records too, starts with its tool, the
    repo's git state, the Manila date and the Python version."""
    plain = tmp_path / "plain"
    plain.mkdir()
    record = record_io.base_record("eval/data/freeze_record.py", plain)
    assert record.keys() == BASE
    assert (record["tool"], record["git"]) == ("eval/data/freeze_record.py", UNKNOWN)
    assert DATE.fullmatch(record["date"])
    assert record["python"] == "{}.{}.{}".format(*sys.version_info[:3])


def test_record_io_imports_only_the_standard_library(tmp_path):
    """The audit, seal_set_d, water_check and freeze_record import record_io, and their
    environments hold no numpy, OpenCV or py7zr (C1). A fresh interpreter that imports
    record_io and manifest, and builds and encodes a record, loads none of them, nor
    photos, archive or setlogs, and prints nothing else."""
    probe = (
        f"import sys; sys.path.insert(0, {json.dumps(str(DATA))}); "
        "from pathlib import Path; import manifest, record_io; "
        "manifest.counts([]); "
        "record_io.record_bytes(record_io.set_d_record("
        "repo=Path('.'), counts={}, inputs={}, extends=None)); "
        "print(sorted({'numpy', 'cv2', 'py7zr', 'photos', 'archive', 'setlogs'} "
        "& set(sys.modules)))"
    )
    done = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "[]\n", "")
