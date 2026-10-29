"""Tests for the data freeze's record, eval/data/freeze_record.py (C216, C222, V8).

Every dataset file, record and look is synthetic, under tmp_path: the data folder in
tmp_path/"data", laid out like lusot-data, and the committed records in
tmp_path/"records". No test runs git: each record's git state is fixed.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import formats
import freeze_record
import pytest
import record_io
import synth

DATA = Path(__file__).resolve().parents[1]  # eval/data
FREEZE = DATA / "freeze_record.py"
REFUSED = "refused: path inside a folder named sealed\n"
OUTSIDE = "refused: --file must stay inside --data\n"
HOLDS_ID = "refused: the record would hold an id\n"
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+08:00")
UNKNOWN = {"commit": "unknown", "dirty": True}
TRUTH = "set_b/dev/generated/truth.csv"
FILES = ("set_a/dev/manifest.csv", "a_neg/dev/manifest.csv", TRUTH)
# The ids the synthetic files hold, which the record must never hold.
IDS = ("A001", "A002", "N001", "E01", "B01", "B01-1-1", "B01-1-2")
SPLIT_ARCHIVE = {"file": "lusot-sealed.7z", "size": 4096, "sha256": "ab" * 32}


@pytest.fixture(autouse=True)
def no_git(monkeypatch):
    """Every record's git state is fixed, so no test runs git."""
    monkeypatch.setattr(record_io, "git_state", lambda repo: UNKNOWN)


def write_json(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    path.write_bytes(text.encode("ascii"))
    return path


@pytest.fixture
def given(tmp_path) -> dict:
    """The data folder's files, each holding ids, two records, one with an archive
    block and one without, two looks, and the record to write."""
    data = tmp_path / "data"
    manifest = [{"photo_id": "A001", "event_id": "E01"}, {"photo_id": "A002"}]
    synth.write_csv(data / FILES[0], ["photo_id", "event_id"], manifest)
    synth.write_csv(data / FILES[1], ["photo_id"], [{"photo_id": "N001"}])
    truth = [
        {"crop_id": crop, "car_id": "B01", "generator_version": "set-b-gen-v1"}
        for crop in ("B01-1-1", "B01-1-2")
    ]
    synth.write_csv(data / TRUTH, formats.TRUTH_COLUMNS, truth)
    records = tmp_path / "records"
    split = write_json(
        records / "2026-10-30-split.json",
        {"tool": "eval/data/split.py", "seed": 20261030, "archive": SPLIT_ARCHIVE},
    )
    plain = write_json(records / "2026-10-31-other.json", {"tool": "eval/x.py"})
    looks = [
        write_json(
            records / f"set-b-look-{n}.json",
            {"look": n, "share": f"{n + 1}/4", "result": "fail" if n == 1 else "pass"},
        )
        for n in (1, 2)
    ]
    return {
        "--data": data,
        "--file": list(FILES),
        "--record": [split, plain],
        "--look": looks,
        "--out": records / "2026-11-01-freeze.json",
    }


def args(given: dict) -> list[str]:
    found = ["--data", str(given["--data"])]
    for flag in ("--file", "--record", "--look"):
        for value in given[flag]:
            found += [flag, str(value)]
    return [*found, "--out", str(given["--out"])]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_freeze_record_holds_the_hashes(given, capsys):
    """Each file's SHA-256 equals hashlib's, keyed by its path as given with /; each
    record's SHA-256 and its archive block are copied, or null without one; the
    generator version comes from truth.csv; and the looks are included, in order."""
    given["--file"][0] = FILES[0].replace("/", "\\")
    assert freeze_record.main(args(given)) == 0
    data, out = given["--data"], given["--out"]
    found = json.loads(out.read_bytes())
    assert DATE.fullmatch(found.pop("date"))
    split, plain = given["--record"]
    assert found == {
        "tool": "eval/data/freeze_record.py",
        "git": UNKNOWN,
        "python": "{}.{}.{}".format(*sys.version_info[:3]),
        "files": {rel: sha256(data / rel) for rel in FILES},
        "records": {
            split.name: {"sha256": sha256(split), "archive": SPLIT_ARCHIVE},
            plain.name: {"sha256": sha256(plain), "archive": None},
        },
        "generator_version": "set-b-gen-v1",
        "looks": [json.loads(path.read_bytes()) for path in given["--look"]],
    }
    assert capsys.readouterr() == (f"files=3\nrecord sha256 {sha256(out)}\n", "")


def test_no_truth_listed_leaves_the_generator_version_null(given):
    given["--file"] = list(FILES[:2])
    given["--record"], given["--look"] = [], []
    assert freeze_record.main(args(given)) == 0
    found = json.loads(given["--out"].read_bytes())
    assert (found["generator_version"], found["records"], found["looks"]) == (
        None,
        {},
        [],
    )


def test_freeze_record_holds_no_ids(given):
    """The synthetic files' ids appear nowhere in the record, nor any id-shaped token."""
    assert freeze_record.main(args(given)) == 0
    text = given["--out"].read_text(encoding="ascii")
    assert [found for found in IDS if found in text] == []
    assert record_io.ID_TOKEN.search(text) is None


@pytest.mark.parametrize("where", ["--file", "--record"])
def test_a_record_that_would_hold_an_id_is_refused(given, capsys, where):
    """Addition 4: a files key or a records key holding an id-shaped token stops the run
    before anything is written."""
    if where == "--file":
        rel = "set_b/dev/generated/crops/B01-1-1.jpg"
        crop = given["--data"] / rel
        crop.parent.mkdir(parents=True)
        crop.write_bytes(b"synthetic crop")
        given["--file"].append(rel)
    else:
        given["--record"].append(write_json(given["--out"].parent / "B02.json", {}))
    assert freeze_record.main(args(given)) == 1
    assert capsys.readouterr() == ("", HOLDS_ID)
    assert not given["--out"].exists()


@pytest.mark.parametrize("flag", ["--data", "--file", "--record", "--look", "--out"])
def test_freeze_record_refuses_sealed_paths(given, tmp_path, capsys, flag):
    """Each path inside a folder named sealed, and each --file that joins --data into
    one, is refused before anything opens, though the files are there to read (C222)."""
    if flag == "--data":
        moved = tmp_path / "sealed" / "data"
        moved.parent.mkdir()
        given["--data"].rename(moved)
        given["--data"] = moved
    elif flag == "--file":
        rel = "set_c/sealed/manifest.csv"
        synth.write_csv(given["--data"] / rel, ["file"], [{"file": "x.jpg"}])
        given["--file"].append(rel)
    elif flag == "--out":
        given["--out"] = tmp_path / "sealed" / "freeze.json"
    else:
        path = given[flag][0]
        moved = tmp_path / "sealed" / path.name
        moved.parent.mkdir()
        path.rename(moved)
        given[flag][0] = moved
    with pytest.raises(SystemExit) as stop:
        freeze_record.main(args(given))
    assert stop.value.code == 2
    assert capsys.readouterr() == ("", REFUSED)
    code, events = synth.opened_paths(FREEZE, args(given))
    assert code == 2
    assert [item for item in events if inside(item[1], tmp_path)] == []
    assert not given["--out"].exists()


def inside(path: str, folder: Path) -> bool:
    absolute = Path(os.path.abspath(path))
    return absolute == folder or folder in absolute.parents


@pytest.mark.parametrize(
    "rel",
    ["..\\x.csv", "../x.csv", "set_a/../../x.csv", "C:x.csv", "C:\\x.csv", "\\x.csv"]
    + ["/x.csv", "\\\\server\\share\\x.csv", "x.csv:stream", "", "set_a//x.csv"]
    + ["./x.csv", "set_a/.. /x.csv", "set_a/.../x.csv", "set_a/"],
)
def test_a_file_must_stay_inside_data(given, tmp_path, capsys, rel):
    """Addition 5: a --file with a drive, a root, a ":", a ".." or any other part of
    dots and spaces alone, or an empty part, is refused before anything opens."""
    given["--file"].append(rel)
    assert freeze_record.main(args(given)) == 2
    assert capsys.readouterr() == ("", OUTSIDE)
    code, events = synth.opened_paths(FREEZE, args(given))
    assert code == 2
    assert [item for item in events if inside(item[1], tmp_path)] == []
    assert not given["--out"].exists()


def test_data_must_be_absolute(given, capsys, monkeypatch):
    monkeypatch.chdir(given["--data"].parent)
    given["--data"] = Path("data")
    assert freeze_record.main(args(given)) == 2
    assert capsys.readouterr() == ("", "refused: --data must be absolute\n")
    assert not given["--out"].exists()


def test_out_may_be_relative(given, monkeypatch):
    """--out is a record path, given from the repo root (S-R13)."""
    monkeypatch.chdir(given["--out"].parent)
    given["--out"] = Path("freeze.json")
    assert freeze_record.main(args(given)) == 0
    assert json.loads(Path("freeze.json").read_bytes())["tool"] == (
        "eval/data/freeze_record.py"
    )


def test_freeze_record_never_overwrites(given, capsys):
    """An --out that exists is refused before anything is read, and keeps its bytes."""
    given["--out"].write_bytes(b"an earlier freeze record")
    assert freeze_record.main(args(given)) == 2
    assert capsys.readouterr() == ("", "--out exists: a record is never rewritten\n")
    assert given["--out"].read_bytes() == b"an earlier freeze record"


def test_freeze_record_imports_only_the_standard_library():
    """A fresh interpreter that imports freeze_record loads no numpy, OpenCV or py7zr,
    nor photos or archive, which load them, so the script runs with dependencies = []."""
    probe = (
        f"import sys; sys.path.insert(0, {json.dumps(str(DATA))}); "
        "import freeze_record; "
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


def test_freeze_record_help_exits_0():
    done = subprocess.run(
        [sys.executable, str(FREEZE), "--help"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stderr) == (0, "")
    for flag in ("--data", "--file", "--record", "--look", "--out"):
        assert flag in done.stdout
