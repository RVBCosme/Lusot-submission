"""Tests for the split, eval/data/split.py (M19, spec §5.5, C202, C204, C205, C219,
C220, C221, C222, S-R19).

Every log, photo, archive and record is synthetic, laid out by synth.split_inputs
under tmp_path, whose archive folder is named sealed, as in lusot-data. Only test code
opens an archive, with the test phrase (C206), and no test runs git: each record's git
state is fixed.
"""

import getpass
import json
import os
import random
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import audit
import draw
import events
import formats
import intake
import photos
import py7zr
import pytest
import record_io
import split
import strata
import synth
import table

DATA = Path(__file__).resolve().parents[1]  # eval/data
SPLIT = DATA / "split.py"
FLAGS = (
    "--set-a-log",
    "--set-a-photos",
    "--a-neg-log",
    "--a-neg-photos",
    "--m8",
    "--set-a-dev",
    "--a-neg-dev",
    "--archive",
    "--record",
)
OUTPUTS = ("--archive", "--record", "--set-a-dev", "--a-neg-dev")
DEV = {"A": "--set-a-dev", "A-neg": "--a-neg-dev"}
SIDES = ("dev", "sealed")
REFUSED = "refused: path inside a folder named sealed\n"
NO_CONSOLE = "refused: run this yourself, in a Windows PowerShell window\n"
PROMPTS = ["Archive password: ", "Type it again: "]
# A text that the output and the record may never hold (C201).
SENTINEL = "Zqxjv"
# C221's id head, as a token inside any text, as record_io refuses it.
ID_TOKEN = re.compile(r"(?<![A-Za-z0-9])[A-Z]{1,3}[0-9]{1,4}(?![A-Za-z0-9])")

# Task 10's golden input, which the layout's Set A groups into once A007 and A009
# join A001 (addition 9): each event's photos and whether it is deep.
GOLDEN = {
    "E01": (3, False),
    "E02": (2, True),
    "E03": (2, False),
    "E04": (2, True),
    "E05": (2, False),
    "E06": (2, True),
    "E07": (2, False),
    "E08": (1, False),
    "E09": (1, True),
    "E10": (1, False),
    "E11": (1, True),
    "E12": (1, False),
}
# Under SPLIT_SEED, the golden draw seals these: 8 of 20 rows, exactly 2/5.
SEALED_EVENTS = {"E01", "E02", "E07", "E09"}
# The layout's A-neg: each event's photos.
A_NEG_EVENTS = {
    "E01": ["N001", "N002"],
    "E02": ["N003", "N004"],
    "E03": ["N005"],
    "E04": ["N006"],
    "E05": ["N007"],
    "E06": ["N008"],
}
# The text columns of each log, each of which the sentinel test fills.
SET_A_TEXT = (
    "post_url",
    "poster",
    "spot_text",
    "city",
    "level_label_raw",
    "passability_raw",
    "notes",
    "alert_poster",
    "alert_spot_text",
)
A_NEG_TEXT = ("post_url", "spot_text", "city", "passability_raw", "notes")
# What the layout's run prints for Set A, before its counts per fact value.
SET_A_COUNTS = [
    "A dev rows=12 events=8",
    "A sealed rows=8 events=4",
    "A deep dev events=3 rows=5",
    "A deep sealed events=2 rows=3",
    "A other dev events=5 rows=7",
    "A other sealed events=2 rows=5",
]


@pytest.fixture(autouse=True)
def no_git(monkeypatch):
    """Every record's git state is fixed, so no test runs git."""
    monkeypatch.setattr(
        record_io, "git_state", lambda repo: {"commit": "unknown", "dirty": True}
    )


@pytest.fixture
def paths(tmp_path):
    return synth.split_inputs(tmp_path / "data")


@pytest.fixture
def prompts(monkeypatch) -> list[str]:
    """Rene's console, with the test phrase typed twice. The list records each
    password prompt the split shows, so a test can prove getpass was never called."""
    synth.console(monkeypatch)
    synth.typed(monkeypatch, synth.TEST_PHRASE, synth.TEST_PHRASE)
    answer = getpass.getpass
    shown = []

    def ask(prompt: str = "") -> str:
        shown.append(prompt)
        return answer(prompt)

    monkeypatch.setattr(getpass, "getpass", ask)
    return shown


def arguments(paths, *extra: str) -> list[str]:
    given = [text for flag, path in paths.items() for text in (flag, str(path))]
    return given + list(extra)


def run(paths, *extra: str) -> int:
    """The split's exit code, whether main returns it or a guard exits."""
    try:
        return split.main(arguments(paths, *extra))
    except SystemExit as stop:
        return stop.code


def nothing_written(paths) -> bool:
    return not any(paths[flag].exists() for flag in OUTPUTS)


def rows_of(path: Path) -> list[dict[str, str]]:
    return [
        {column: cell for column, cell in row.items() if column != "#"}
        for row in table.read_table(path).rows
    ]


def extract(archive: Path, out: Path) -> list[str]:
    """The archive's member names, in its order, after extracting it to out."""
    with py7zr.SevenZipFile(archive, "r", password=synth.TEST_PHRASE) as sealed:
        names = sealed.getnames()
        sealed.extractall(path=out)
    return names


def written(paths, out: Path) -> dict:
    """What a split wrote: the archive's member names, once it is extracted to out, the
    committed record, and each set's manifest rows on each side, the sealed ones from
    out."""
    names = extract(paths["--archive"], out)
    sides = {
        set_name: {
            "dev": rows_of(paths[DEV[set_name]] / "manifest.csv"),
            "sealed": rows_of(out / folder / "manifest.csv"),
        }
        for set_name, folder in audit.FOLDERS.items()
    }
    record = json.loads(paths["--record"].read_bytes().decode("ascii"))
    return {"names": names, "record": record, "sides": sides}


def by_group(sides) -> dict[str, dict[str, list[dict[str, str]]]]:
    """One set's rows on each side, in each C204 group: an event is deep when a row of
    it states NPLV or NPATV."""
    deep = {
        row["event_id"]
        for rows in sides.values()
        for row in rows
        if strata.deep_row(row["passability_raw"])
    }
    return {
        group: {
            side: [
                row for row in rows if (row["event_id"] in deep) == (group == "deep")
            ]
            for side, rows in sides.items()
        }
        for group in ("deep", "other")
    }


def rewrite(path: Path, columns, rows) -> None:
    path.unlink()
    synth.write_csv(path, columns, rows)


def inside(path, folder) -> bool:
    absolute = Path(os.path.abspath(path))
    return absolute == folder or folder in absolute.parents


def test_layout_groups_into_the_golden_events(paths):
    """Checked with group_events before the split relies on it (addition 9). The text
    alone gives 14 events: A007 and A009 join A001 only as its copies."""
    result = intake.run_intake(
        set_a_log=paths["--set-a-log"],
        set_a_photos=paths["--set-a-photos"],
        a_neg_log=paths["--a-neg-log"],
        a_neg_photos=paths["--a-neg-photos"],
        m8=paths["--m8"],
    )
    assert (result.problems, result.warnings) == ([], [])
    inputs = [
        events.EventInput(p.photo_id, p.event_date, p.spot_key, p.same_spot_as)
        for p in result.set_a.photos
    ]
    assert len(set(events.group_events(inputs).values())) == 14
    event_of = events.group_events(inputs, [("A007", "A001"), ("A009", "A001")])
    deep = {
        event_of[p.photo_id]
        for p in result.set_a.photos
        if strata.deep_row(p.passability_raw)
    }
    sizes = Counter(event_of.values())
    assert {event: (n, event in deep) for event, n in sizes.items()} == GOLDEN
    a_neg = [
        events.EventInput(p.photo_id, p.event_date, p.spot_key, p.same_spot_as)
        for p in result.a_neg.photos
    ]
    a_neg_events = events.group_events(a_neg)
    assert {
        event: sorted(i for i, e in a_neg_events.items() if e == event)
        for event in set(a_neg_events.values())
    } == A_NEG_EVENTS
    raw = paths["--set-a-photos"]
    first, copy, again = (
        photos.photo_facts((raw / f"{photo_id}.jpg").read_bytes())
        for photo_id in ("A001", "A007", "A009")
    )
    assert copy == first
    assert again.sha256 != first.sha256
    assert events.near(again.dhash, first.dhash)


def test_split_end_to_end(paths, prompts, tmp_path, capsys):
    assert run(paths) == 0
    assert prompts == PROMPTS
    out, err = capsys.readouterr()
    assert err == ""
    found = written(paths, tmp_path / "extracted")
    sides, record = found["sides"], found["record"]
    data = paths["--archive"].read_bytes()

    # The members, exactly and in order, and the source bytes as given.
    sealed_a, sealed_n = sides["A"]["sealed"], sides["A-neg"]["sealed"]
    assert found["names"] == [
        "records/split.json",
        "set_a/manifest.csv",
        "set_a/m8.csv",
        *(f"set_a/photos/{row['photo_file']}" for row in sealed_a),
        "set_a/source/set_a_log.csv",
        "set_a/source/m8_labels.csv",
        "a_neg/manifest.csv",
        *(f"a_neg/photos/{row['photo_file']}" for row in sealed_n),
        "a_neg/source/a_neg_log.csv",
    ]
    out_dir = tmp_path / "extracted"
    for member, source in (
        ("set_a/source/set_a_log.csv", "--set-a-log"),
        ("set_a/source/m8_labels.csv", "--m8"),
        ("a_neg/source/a_neg_log.csv", "--a-neg-log"),
    ):
        assert (out_dir / member).read_bytes() == paths[source].read_bytes()

    # Each side holds its own rows, every photo is on one side, and the golden draw
    # holds: Set A seals E01, E02, E07 and E09, and A-neg 3 of its 8 rows.
    for set_name, folder in audit.FOLDERS.items():
        on = sides[set_name]
        assert {row["split"] for row in on["dev"]} == {"dev"}
        assert {row["split"] for row in on["sealed"]} == {"sealed"}
        assert (
            table.read_table(out_dir / folder / "manifest.csv").columns
            == table.read_table(paths[DEV[set_name]] / "manifest.csv").columns
            == formats.MANIFEST_COLUMNS
        )
    assert sorted(row["photo_id"] for side in SIDES for row in sides["A"][side]) == [
        f"A{n:03d}" for n in range(1, 21)
    ]
    assert {row["event_id"] for row in sealed_a} == SEALED_EVENTS
    assert len(sealed_a) == 8
    assert len(sealed_n) == 3
    assert [row["photo_id"] for row in rows_of(out_dir / "set_a" / "m8.csv")] == [
        row["photo_id"] for row in sealed_a
    ]
    dev_m8 = rows_of(paths["--set-a-dev"] / "m8.csv")
    assert [row["photo_id"] for row in dev_m8] == [
        row["photo_id"] for row in sides["A"]["dev"]
    ]

    # Each dev copy is its raw file's bytes, and no sealed photo is in a dev folder.
    sealed_hashes = {row["photo_sha256"] for s in sides.values() for row in s["sealed"]}
    for set_name, raw in (("A", "--set-a-photos"), ("A-neg", "--a-neg-photos")):
        copies = paths[DEV[set_name]] / "photos"
        dev_rows = sides[set_name]["dev"]
        assert sorted(path.name for path in copies.iterdir()) == sorted(
            row["photo_file"] for row in dev_rows
        )
        for row in dev_rows:
            copy = (copies / row["photo_file"]).read_bytes()
            assert copy == (paths[raw] / row["photo_file"]).read_bytes()
            assert table.sha256_bytes(copy) not in sealed_hashes

    # The committed record: the archive's facts, the copy check, the dev files, and
    # inside the archive, the core alone.
    assert record["archive"] == {
        "file": "lusot-sealed.7z",
        "size": len(data),
        "sha256": table.sha256_bytes(data),
    }
    assert record["copy_check"] == {"rehash_ok": "17/17", "matched_sealed": 0}
    assert record["dev_files"] == {
        "set_a_manifest": table.sha256_file(paths["--set-a-dev"] / "manifest.csv"),
        "set_a_m8": table.sha256_file(paths["--set-a-dev"] / "m8.csv"),
        "a_neg_manifest": table.sha256_file(paths["--a-neg-dev"] / "manifest.csv"),
    }
    assert record["inputs"] == {
        "set_a_log": table.sha256_file(paths["--set-a-log"]),
        "a_neg_log": table.sha256_file(paths["--a-neg-log"]),
        "m8": table.sha256_file(paths["--m8"]),
    }
    assert record["sets"]["A"]["share"] == "8/20"
    assert record["sets"]["A-neg"]["share"] == "3/8"
    core = {k: v for k, v in record.items() if k not in ("archive", "copy_check")}
    assert (out_dir / "records" / "split.json").read_bytes() == (
        record_io.record_bytes(core)
    )

    # Every id the manifests hold is in C221's pattern.
    for on in sides.values():
        for row in on["dev"] + on["sealed"]:
            assert table.is_id(row["photo_id"])
            assert table.is_id(row["event_id"])
            assert row["duplicate_of"] == "" or table.is_id(row["duplicate_of"])

    # The output: counts, the audit, the copy check and the archive, and no id.
    lines = out.splitlines()
    assert lines[0] == "warnings=0"
    assert lines[1:7] == SET_A_COUNTS
    assert "A dev decodes: yes=12" in lines
    assert "A sealed duplicate: no=6 yes=2" in lines
    assert "A-neg dev match: (blank)=5" in lines
    assert lines[-3:] == [
        "audit PASS",
        "copy check 17 of 17",
        f"archive {len(data)} bytes sha256 {table.sha256_bytes(data)}",
    ]
    assert ID_TOKEN.search(out) is None


def test_split_is_deterministic(paths, prompts, tmp_path, monkeypatch):
    shutil.copytree(tmp_path / "data", tmp_path / "copy")
    again = {
        flag: tmp_path / "copy" / path.relative_to(tmp_path / "data")
        for flag, path in paths.items()
    }
    assert run(paths) == 0
    synth.typed(monkeypatch, synth.TEST_PHRASE, synth.TEST_PHRASE)
    assert run(again) == 0
    first, second = written(paths, tmp_path / "x1"), written(again, tmp_path / "x2")
    assert first["names"] == second["names"]
    assert first["sides"] == second["sides"]
    for name in ("set_a/manifest.csv", "set_a/m8.csv", "a_neg/manifest.csv"):
        assert (tmp_path / "x1" / name).read_bytes() == (
            tmp_path / "x2" / name
        ).read_bytes()
    for name in ("manifest.csv", "m8.csv"):
        assert (paths["--set-a-dev"] / name).read_bytes() == (
            again["--set-a-dev"] / name
        ).read_bytes()
    assert (paths["--a-neg-dev"] / "manifest.csv").read_bytes() == (
        again["--a-neg-dev"] / "manifest.csv"
    ).read_bytes()
    cores = [
        json.loads((tmp_path / x / "records" / "split.json").read_bytes())
        for x in ("x1", "x2")
    ]
    records = [first["record"], second["record"]]
    for found in cores + records:
        for key in ("archive", "date", "git"):
            found.pop(key, None)
    assert cores[0] == cores[1]
    assert records[0] == records[1]


def test_deep_events_reach_both_sides(paths, prompts, tmp_path):
    assert run(paths) == 0
    grouped = by_group(written(paths, tmp_path / "x")["sides"]["A"])
    assert grouped["deep"]["dev"] and grouped["deep"]["sealed"]


def test_every_group_of_two_or_more_has_both_sides(paths, prompts, tmp_path):
    assert run(paths) == 0
    for set_name, sides in written(paths, tmp_path / "x")["sides"].items():
        for group, on in by_group(sides).items():
            events_of = {side: {row["event_id"] for row in on[side]} for side in SIDES}
            if len(events_of["dev"] | events_of["sealed"]) >= 2:
                assert all(events_of.values()), (set_name, group)


def test_record_group_counts_are_right(paths, prompts, tmp_path):
    assert run(paths) == 0
    found = written(paths, tmp_path / "x")
    for set_name, sides in found["sides"].items():
        expected = {}
        for group, on in by_group(sides).items():
            if not any(on.values()):
                continue
            counts = {
                side: {
                    "events": len({row["event_id"] for row in rows}),
                    "rows": len(rows),
                }
                for side, rows in on.items()
            }
            expected[group] = {
                "events": counts["dev"]["events"] + counts["sealed"]["events"],
                "rows": counts["dev"]["rows"] + counts["sealed"]["rows"],
                **counts,
                "moved": None,
            }
        assert found["record"]["sets"][set_name]["groups"] == expected


def test_audit_sealed_passes_on_the_split_it_wrote(paths, prompts, tmp_path):
    """C220: the sealed run's audit, on the archive extracted where Rene extracts it,
    against the committed record."""
    assert run(paths) == 0
    data = tmp_path / "data"
    run_dir = data / "sealed" / "run-1"
    extract(paths["--archive"], run_dir)
    assert audit.audit_sealed(run_dir, data, [paths["--record"]]) == []
    archive = bytearray(paths["--archive"].read_bytes())
    archive[len(archive) // 2] ^= 1
    paths["--archive"].write_bytes(bytes(archive))
    assert audit.audit_sealed(run_dir, data, [paths["--record"]]) == [
        "archive_hash lusot-sealed.7z"
    ]


def test_duplicates_join_one_event(paths, prompts, tmp_path):
    raw = paths["--set-a-photos"]
    assert (raw / "A007.jpg").read_bytes() == (raw / "A001.jpg").read_bytes()
    assert (raw / "A009.jpg").read_bytes() != (raw / "A001.jpg").read_bytes()
    assert run(paths) == 0
    sides = written(paths, tmp_path / "x")["sides"]["A"]
    rows = {row["photo_id"]: row for side in SIDES for row in sides[side]}
    copies = [rows[photo_id] for photo_id in ("A001", "A007", "A009")]
    assert len({row["event_id"] for row in copies}) == 1
    assert [row["duplicate_of"] for row in copies] == ["A001"] * 3
    assert [row["duplicate"] for row in copies] == ["no", "yes", "yes"]
    others = [
        row
        for photo_id, row in rows.items()
        if photo_id not in ("A001", "A007", "A009")
    ]
    assert {(row["duplicate"], row["duplicate_of"]) for row in others} == {("no", "")}


@pytest.mark.parametrize("flag", FLAGS)
def test_split_path_rules(paths, prompts, tmp_path, capsys, flag):
    """An input, the record or a dev folder inside a folder named sealed is refused,
    and so is an archive outside one, on the strings, before anything opens (C202,
    C222). Each file is there to read."""
    data = tmp_path / "data"
    given = dict(paths)
    if flag == "--archive":
        given[flag] = data / "outside" / "lusot-sealed.7z"
        given[flag].parent.mkdir()
        expected = "refused: --archive must be inside a folder named sealed\n"
    else:
        given[flag] = data / "sealed" / "moved" / paths[flag].name
        if paths[flag].is_dir():
            shutil.copytree(paths[flag], given[flag])
        elif paths[flag].is_file():
            given[flag].parent.mkdir()
            shutil.copyfile(paths[flag], given[flag])
        expected = REFUSED
    assert run(given) == 2
    assert capsys.readouterr() == ("", expected)
    code, opened = synth.opened_paths(SPLIT, arguments(given))
    assert code == 2
    assert [item for item in opened if inside(item[1], tmp_path)] == []
    assert prompts == []
    assert not any(given[out].exists() or paths[out].exists() for out in OUTPUTS)


# Write paths refused on their strings (addition 1, S-R19's Q2), each with the path
# it gives its flag, relative to the test's working folder, and the refusal.
WRITE_RULES = {
    "relative archive": (
        "--archive",
        lambda data: Path("sealed", "lusot-sealed.7z"),
        "refused: --archive must be absolute\n",
    ),
    "archive not 7z": (
        "--archive",
        lambda data: data / "sealed" / "lusot-sealed.zip",
        "refused: --archive name\n",
    ),
    "archive an NTFS stream": (
        "--archive",
        lambda data: data / "sealed" / "sealed:a.7z",
        "refused: --archive name\n",
    ),
    "archive name with an id": (
        "--archive",
        lambda data: data / "sealed" / "A001.7z",
        "refused: --archive name\n",
    ),
    "archive name with a space": (
        "--archive",
        lambda data: data / "sealed" / "lusot sealed.7z",
        "refused: --archive name\n",
    ),
    "relative set_a dev": (
        "--set-a-dev",
        lambda data: Path("set_a", "dev"),
        "refused: --set-a-dev must be absolute\n",
    ),
    "relative a_neg dev": (
        "--a-neg-dev",
        lambda data: Path("a_neg", "dev"),
        "refused: --a-neg-dev must be absolute\n",
    ),
}


@pytest.mark.parametrize("rule", WRITE_RULES.values(), ids=list(WRITE_RULES))
def test_split_write_path_rules(paths, prompts, tmp_path, monkeypatch, capsys, rule):
    """Each refusal names its flag only, before anything opens or is created. The
    test runs in an empty folder of its own, so a relative path would land there."""
    flag, make, expected = rule
    data = tmp_path / "data"
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    given = dict(paths) | {flag: make(data)}
    assert run(given) == 2
    assert capsys.readouterr() == ("", expected)
    code, opened = synth.opened_paths(SPLIT, arguments(given))
    assert code == 2
    assert [item for item in opened if inside(item[1], data)] == []
    assert prompts == []
    assert list(cwd.iterdir()) == []
    assert nothing_written(paths)
    assert not Path(os.path.abspath(given[flag])).exists()


def test_split_refuses_without_a_console(paths):
    """With stdin on NUL and stdout piped, as in Claude's shell, the split stops at the
    console check, before it stats or reads anything (C202)."""
    done = subprocess.run(
        [sys.executable, str(SPLIT), *arguments(paths)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (2, "", NO_CONSOLE)
    assert nothing_written(paths)


def test_rerun_names_the_partial_outputs(paths, prompts, capsys):
    """Review Focus 3: a run stopped after writing leaves its outputs, and the rerun
    names each one by its flag and changes nothing."""
    paths["--archive"].write_bytes(b"a partial archive")
    paths["--set-a-dev"].mkdir()
    assert run(paths) == 2
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        "--archive exists: delete it before rerunning",
        "--set-a-dev exists: delete it before rerunning",
    ]
    assert err == ""
    assert paths["--archive"].read_bytes() == b"a partial archive"
    assert list(paths["--set-a-dev"].iterdir()) == []
    assert not paths["--a-neg-dev"].exists()
    assert not paths["--record"].exists()
    assert prompts == []


@pytest.mark.parametrize("flag", OUTPUTS)
def test_rerun_names_each_existing_output(paths, prompts, capsys, flag):
    if flag in DEV.values():
        paths[flag].mkdir()
    else:
        paths[flag].parent.mkdir(exist_ok=True)
        paths[flag].write_bytes(b"x")
    assert run(paths) == 2
    assert capsys.readouterr() == (f"{flag} exists: delete it before rerunning\n", "")
    assert prompts == []


def test_archive_folder_must_exist(paths, prompts, capsys):
    """Addition 2: no code creates a folder inside sealed, so a missing archive folder
    is refused before anything is read."""
    paths["--archive"] = paths["--archive"].parent / "missing" / "lusot-sealed.7z"
    assert run(paths) == 2
    assert capsys.readouterr() == ("--archive folder missing: create it first\n", "")
    assert not paths["--archive"].parent.exists()
    assert nothing_written(paths)
    assert prompts == []


def test_password_mismatch_writes_nothing(paths, prompts, monkeypatch, capsys):
    """The password comes last, after every check (S-R19), and a mismatch writes
    nothing."""
    synth.typed(monkeypatch, synth.TEST_PHRASE, "another phrase")
    assert run(paths) == 2
    assert capsys.readouterr() == (
        "warnings=0\n",
        "refused: the two entries differ; nothing was written\n",
    )
    assert nothing_written(paths)


def test_intake_problem_stops_the_split(paths, prompts, capsys):
    (paths["--set-a-photos"] / "A005.jpg").unlink()
    assert run(paths) == 1
    assert capsys.readouterr() == ("A005 photo_file: file_missing\nwarnings=0\n", "")
    assert nothing_written(paths)
    assert prompts == []


@pytest.mark.parametrize("kind", ["not_utf8", "file_missing"])
def test_unreadable_log_stops_the_split(paths, prompts, capsys, kind):
    """Addition 4: the intake's finding names the log, never its text or path."""
    if kind == "not_utf8":
        log = paths["--set-a-log"]
        log.write_bytes(log.read_bytes().replace(b"Alfa", b"Alf\xe1"))
        expected = "set_a log: not_utf8\n"
    else:
        paths["--a-neg-log"].unlink()
        expected = "a_neg log: file_missing\n"
    assert run(paths) == 1
    assert capsys.readouterr() == (expected, "")
    assert nothing_written(paths)
    assert prompts == []


def test_one_event_set_stops(paths, prompts, capsys):
    rewrite(
        paths["--a-neg-log"],
        formats.TEMPLATES["a_neg_log.csv"],
        [
            synth.a_neg_row(
                candidate_id=f"N{n:03d}",
                post_time_pht=f"2026-10-27 16:{n:02d}",
                spot_text="Oscar St.",
            )
            for n in range(1, 9)
        ],
    )
    assert run(paths) == 1
    assert capsys.readouterr() == (
        "warnings=0\nsplit stopped: set A-neg has fewer than 2 events\n",
        "",
    )
    assert nothing_written(paths)
    assert prompts == []


def test_missing_m8_photo_row(paths, prompts, monkeypatch, capsys):
    m8 = [row for row in rows_of(paths["--m8"]) if row["photo_id"] != "A003"]
    rewrite(paths["--m8"], formats.M8_COLUMNS, m8)
    assert run(paths) == 1
    assert capsys.readouterr() == ("A003 m8: no_photo_row\nwarnings=0\n", "")
    assert nothing_written(paths)
    assert prompts == []
    synth.typed(monkeypatch, synth.TEST_PHRASE, synth.TEST_PHRASE)
    assert run(paths, "--allow-missing-m8") == 0
    record = json.loads(paths["--record"].read_bytes())
    assert record["missing_m8_photo_rows"] == 1


def test_split_keeps_an_undecodable_photo(paths, prompts):
    """Review Focus 2: A005, in the dev event E03, is random bytes. It keeps its
    SHA-256, gets decodes = no and a blank dHash and sizes, and is split like any
    other."""
    junk = random.Random(5).randbytes(4096)
    (paths["--set-a-photos"] / "A005.jpg").write_bytes(junk)
    assert run(paths) == 0
    rows = {
        row["photo_id"]: row for row in rows_of(paths["--set-a-dev"] / "manifest.csv")
    }
    row = rows["A005"]
    assert (row["decodes"], row["photo_dhash"], row["width"], row["height"]) == (
        "no",
        "",
        "",
        "",
    )
    assert row["photo_sha256"] == table.sha256_bytes(junk)
    assert row["event_id"] == rows["A004"]["event_id"]
    record = json.loads(paths["--record"].read_bytes())
    assert record["sets"]["A"]["dev"]["facts"]["decodes"] == {"yes": 11, "no": 1}


def test_changed_copy_stops_the_split(paths, prompts, monkeypatch, capsys):
    """C219: a copy whose bytes on disk differ from its manifest row stops the split
    before the record, however the writer reported it."""
    write_new = table.write_new

    def altered(path, data):
        if path.name == "A004.jpg":
            data = data[:-1] + bytes([data[-1] ^ 1])
        return write_new(path, data)

    monkeypatch.setattr(table, "write_new", altered)
    assert run(paths) == 1
    out, err = capsys.readouterr()
    assert out.splitlines()[-1] == "copy check: A004 changed on disk"
    assert err == ""
    assert not paths["--record"].exists()


def test_copy_check_stops_before_the_password(paths, prompts, capsys):
    """C219, before copying: an A-neg dev photo that is a sealed Set A photo's bytes
    is named by its dev id, and the split stops before writing."""
    sizes = {event: (len(ids), False) for event, ids in A_NEG_EVENTS.items()}
    dev_event = min(draw.draw_set("A-neg", sizes)["other"].dev)
    dev_id = A_NEG_EVENTS[dev_event][0]
    sealed_a = (paths["--set-a-photos"] / "A002.jpg").read_bytes()  # E02 is sealed
    (paths["--a-neg-photos"] / f"{dev_id}.jpg").write_bytes(sealed_a)
    assert run(paths) == 1
    assert capsys.readouterr() == (
        f"warnings=0\ncopy check: {dev_id} matches a sealed photo\n",
        "",
    )
    assert nothing_written(paths)
    assert prompts == []


def test_audit_fail_stops_before_the_password(paths, prompts, capsys):
    """S-R14: a Set A of one deep and one other event seals nothing, so the audit in
    step 9 fails, and the split stops before writing."""
    rewrite(
        paths["--set-a-log"],
        formats.TEMPLATES["set_a_log.csv"],
        [
            synth.set_a_row(candidate_id="A001", spot_text="Alfa St."),
            synth.set_a_row(
                candidate_id="A002", spot_text="Bravo St.", passability_raw="NPLV"
            ),
        ],
    )
    m8 = [row for row in rows_of(paths["--m8"]) if row["photo_id"] in ("A001", "A002")]
    rewrite(paths["--m8"], formats.M8_COLUMNS, m8)
    assert run(paths) == 1
    assert capsys.readouterr() == ("warnings=0\nFAIL\nset_one_sided A\n", "")
    assert nothing_written(paths)
    assert prompts == []


def test_record_refusal_stops_before_the_password(paths, prompts, monkeypatch, capsys):
    """Addition 11: a record that would hold an id-shaped token, here an inputs key, is
    refused before the password, so no archive or record exists."""
    split_record = record_io.split_record

    def with_an_id(**kwargs):
        return split_record(**kwargs | {"inputs": kwargs["inputs"] | {"A001": "x"}})

    monkeypatch.setattr(record_io, "split_record", with_an_id)
    assert run(paths) == 1
    assert capsys.readouterr() == (
        "warnings=0\nthe record holds an id-shaped token\n",
        "",
    )
    assert nothing_written(paths)
    assert prompts == []


def test_unexpected_error_names_no_photo(paths, prompts, monkeypatch, capsys):
    def fails(data):
        raise OSError("A001.jpg can't be read")

    monkeypatch.setattr(photos, "photo_facts", fails)
    assert run(paths) == 1
    out, err = capsys.readouterr()
    assert (out, err) == ("warnings=0\n", "stopped: OSError\n")
    assert nothing_written(paths)
    assert prompts == []


def test_split_output_and_record_hold_no_log_text(paths, prompts, capsys):
    """C201: a sentinel in every text column of both logs reaches the manifests, but
    never the output or the record. In spot_text it joins the spot's word, so each
    event keeps a name of its own."""
    for flag, columns, text in (
        ("--set-a-log", formats.TEMPLATES["set_a_log.csv"], SET_A_TEXT),
        ("--a-neg-log", formats.TEMPLATES["a_neg_log.csv"], A_NEG_TEXT),
    ):
        rows = rows_of(paths[flag])
        for row in rows:
            for column in text:
                if column == "spot_text":
                    row[column] = row[column].replace(" St.", f"{SENTINEL} St.")
                else:
                    row[column] = f"{row[column]} {SENTINEL}".strip()
        rewrite(paths[flag], columns, rows)
    assert run(paths) == 0
    out, err = capsys.readouterr()
    record = paths["--record"].read_text(encoding="ascii")
    for text in (out, err, record):
        assert SENTINEL.casefold() not in text.casefold()
    # Each Set A photo now warns of its poster, its city and its alert poster, and
    # each A-neg photo of its city. Their lines name ids that may be sealed, so only
    # the count prints (S-R19).
    assert out.splitlines()[0] == "warnings=68"
    assert ID_TOKEN.search(out) is None
    for folder in ("--set-a-dev", "--a-neg-dev"):
        manifest = (paths[folder] / "manifest.csv").read_text(encoding="utf-8")
        assert SENTINEL in manifest


def test_record_holds_no_photo_or_event_id(paths, prompts):
    assert run(paths) == 0
    record = paths["--record"].read_text(encoding="ascii")
    assert ID_TOKEN.search(record) is None
    for photo_id in [f"A{n:03d}" for n in range(1, 21)] + [
        f"N{n:03d}" for n in range(1, 9)
    ]:
        assert photo_id not in record
    for event_id in GOLDEN:
        assert event_id not in record


def test_split_help_exits_0():
    done = subprocess.run(
        [sys.executable, str(SPLIT), "--help"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stderr) == (0, "")
    for flag in FLAGS + ("--allow-missing-m8",):
        assert flag in done.stdout
