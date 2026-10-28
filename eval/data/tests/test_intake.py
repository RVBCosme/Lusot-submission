"""Tests for the intake command, eval/data/intake.py (spec §5.3, C201, C204, C208,
C218, C222, and Task 7's M7).

Every log and file is synthetic, under tmp_path. Each photo is an empty file, since the
intake only stats it, and synth.opened_paths proves that it never reads one (C201).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import formats
import intake
import pytest
import synth
import table

DATA = Path(__file__).resolve().parents[1]  # eval/data
INTAKE = DATA / "intake.py"
GUIDE = DATA.parents[1] / "docs" / "data" / "set-a-collection-guide.md"
SET_A_COLUMNS = formats.TEMPLATES["set_a_log.csv"]
A_NEG_COLUMNS = formats.TEMPLATES["a_neg_log.csv"]
FLAGS = (
    "--set-a-log",
    "--set-a-photos",
    "--a-neg-log",
    "--a-neg-photos",
    "--m8",
    "--consented",
    "--sidewalls",
)
# A text that the output may never hold (C201).
SENTINEL = "Zqxjv"
REFUSED = "refused: path inside a folder named sealed\n"

# A row of each other log that passes every check, once its consent text's version is
# approved. APPROVED_CONSENT is empty until Rene approves a text (C218).
M8_PHOTO = {"photo_id": "A001", "ref_id": "P1", "kind": "photo", "quality": "ok"}
CONSENTED = {
    "item_id": "S001",
    "file": "S001.jpg",
    "kind": "photo",
    "taken_pht": "2026-08-09 08:20",
    "lat": "14.6100",
    "lon": "120.9900",
    "consent_file": "S001-ok.png",
    "consent_version": "M9-v3",
}
SIDEWALL = {
    "photo_file": "jeepney-1.jpg",
    "vehicle": "jeepney",
    "tire_code": "7.50-16",
    "taken_on": "2026-10-29",
    "consent_file": "jeepney-ok.png",
    "consent_version": "M11-v1",
}


def files(folder, rows, *columns):
    """Make each file the rows name in these columns an empty file in the folder."""
    folder.mkdir(parents=True, exist_ok=True)
    for name in {row.get(column, "") for row in rows for column in columns} - {""}:
        (folder / name).touch()
    return folder


def write_inputs(
    base,
    set_a=None,
    a_neg=None,
    *,
    set_a_columns=SET_A_COLUMNS,
    a_neg_columns=A_NEG_COLUMNS,
    m8=None,
    consented=None,
    sidewalls=None,
):
    """Write the logs under base as Rene keeps them, each photo in its set's raw folder
    and each other file beside its log. Return each flag's path, in the intake's order.

    Set A and A-neg default to synth's one-row logs. The other logs are written only
    when their rows are given."""
    set_a = [synth.set_a_row()] if set_a is None else set_a
    a_neg = [synth.a_neg_row()] if a_neg is None else a_neg
    paths = {
        "--set-a-log": synth.write_csv(
            base / "set_a" / "set_a_log.csv", set_a_columns, set_a
        ),
        "--set-a-photos": files(base / "set_a" / "raw", set_a, "photo_file"),
        "--a-neg-log": synth.write_csv(
            base / "a_neg" / "a_neg_log.csv", a_neg_columns, a_neg
        ),
        "--a-neg-photos": files(base / "a_neg" / "raw", a_neg, "photo_file"),
    }
    if m8 is not None:
        paths["--m8"] = synth.write_csv(
            base / "set_a" / "m8_labels.csv", formats.M8_COLUMNS, m8
        )
    if consented is not None:
        paths["--consented"] = synth.write_csv(
            base / "consented" / "consented_log.csv",
            formats.CONSENTED_COLUMNS,
            consented,
        )
        files(base / "consented", consented, "file", "consent_file")
    if sidewalls is not None:
        paths["--sidewalls"] = synth.write_csv(
            base / "sidewalls" / "sidewalls.csv", formats.SIDEWALLS_COLUMNS, sidewalls
        )
        files(base / "sidewalls", sidewalls, "photo_file", "consent_file")
    return paths


def arguments(paths):
    return [text for flag, path in paths.items() for text in (flag, str(path))]


def run(paths):
    return intake.main(arguments(paths))


def run_script(args):
    """Run the intake as `python intake.py <args...>`, with stdin on NUL."""
    return subprocess.run(
        [sys.executable, str(INTAKE), *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=False,
    )


def inside(path, folder):
    absolute = Path(os.path.abspath(path))
    return absolute == folder or folder in absolute.parents


def test_intake_prints_counts_problems_warnings_and_events(
    tmp_path, capsys, monkeypatch
):
    """The exact lines for a small data set, in order: the counts, each problem, then
    each warning, the events and the totals. A ref that names no id starts with its
    log's name (Task 7's M7). Set A's events join by date and spot, and by Rene's link
    (C203): A001 and A002, then A003 and A004, then A006 alone. The approved versions
    are set here, so the lines don't change when Rene approves a text (C218)."""
    monkeypatch.setitem(formats.APPROVED_CONSENT, "m9", frozenset({"M9-v3"}))
    monkeypatch.setitem(formats.APPROVED_CONSENT, "m11", frozenset({"M11-v2"}))
    set_a = [
        synth.set_a_row(passability_raw="NPLV"),
        # The same corner written another way, on the same date: one event with A001.
        synth.set_a_row(
            candidate_id="A002", spot_text="Lacson Avenue corner Espana Boulevard"
        ),
        # An alert at another corner never fits, so the photo has no alert's labels.
        synth.set_a_row(
            candidate_id="A003",
            post_time_pht="2026-08-10 07:00",
            spot_text="Taft Ave. cor. Pedro Gil",
            photo_in_alert_post="no",
            alert_poster="MMDA",
            alert_spot_text="Roxas Blvd. cor. Kalaw Ave.",
            alert_time_pht="2026-08-10 07:10",
        ),
        # Another spot of the same date, which Rene links to A003.
        synth.set_a_row(
            candidate_id="A004",
            post_time_pht="2026-08-10 09:00",
            spot_text="Araneta Ave. cor. Ma. Clara St.",
            same_spot_as="A003",
            logged_on="",
        ),
        synth.set_a_row(candidate_id="A05"),
        # A001's spot on A003's date, with no stated class.
        synth.set_a_row(
            candidate_id="A006", post_time_pht="2026-08-10 09:30", passability_raw=""
        ),
    ]
    a_neg = [
        synth.a_neg_row(),
        synth.a_neg_row(
            candidate_id="N002",
            post_time_pht="2026-10-28 10:00",
            spot_text="Roxas Blvd. cor. Kalaw Ave.",
            surface="wet",
        ),
    ]
    wheel = {"photo_id": "A001", "ref_id": "R1", "kind": "wheel", "waterline": "hub"}
    m8 = [
        M8_PHOTO,
        wheel | {"x": "1.5", "y": "0.5"},
        M8_PHOTO | {"photo_id": "A002"},
        M8_PHOTO | {"photo_id": "A004"},
        M8_PHOTO | {"photo_id": "A006"},
    ]
    consented = [
        CONSENTED,
        CONSENTED | {"item_id": "S002", "file": "S002.jpg", "consent_version": "M9-v2"},
    ]
    paths = write_inputs(
        tmp_path,
        set_a,
        a_neg,
        a_neg_columns=A_NEG_COLUMNS + ("colour",),
        m8=m8,
        consented=consented,
        sidewalls=[SIDEWALL | {"checked_code": "7.50-15"}],
    )
    assert run(paths) == 1
    assert capsys.readouterr().out.splitlines() == [
        "set_a rows=6 photos=5 no_class=2",
        "a_neg rows=2 photos=2",
        "m8 rows=5 photo_rows=4",
        "A004 logged_on: missing",
        "set_a row 5 candidate_id: bad_id",
        "a_neg log column 20: unknown",
        "A001 R1.x: out_of_range",
        "A003 m8: no_photo_row",
        "S002 consent_version: not_approved",
        "A003 match=none",
        "sidewalls row 1 consent_version=unapproved",
        "sidewalls row 1 code=mismatch",
        "events set_a=3 largest=2 single=1",
        "events a_neg=2 largest=1 single=2",
        "problems=6 warnings=3",
    ]


def test_intake_counts_photos_without_a_class(tmp_path, capsys):
    """no_class counts the Set A photos whose nearest alert states no class: a blank one,
    or one given in inches only, which C204 can't count as deep. A003's nearest alert,
    in its own post, gives 12", though a later one gives NPLV."""
    set_a = [
        synth.set_a_row(passability_raw="NPLV"),
        synth.set_a_row(candidate_id="A002", passability_raw=""),
        synth.set_a_row(candidate_id="A003", passability_raw='12"'),
        synth.set_a_row(
            candidate_id="A003",
            photo_in_alert_post="no",
            alert_poster="MMDA",
            alert_spot_text="Lacson Avenue corner Espana Boulevard",
            alert_time_pht="2026-08-09 08:45",
            passability_raw="NPLV",
        ),
    ]
    assert run(write_inputs(tmp_path, set_a)) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "set_a rows=4 photos=3 no_class=2"
    assert lines[-1] == "problems=0 warnings=0"


def test_intake_exit_codes(tmp_path):
    """Run as a script: 0 with no problem, 1 with one, and 2 for a usage error or a path
    inside a folder named sealed (C222)."""
    clean = write_inputs(tmp_path / "clean")
    done = run_script(arguments(clean))
    assert (done.returncode, done.stdout.splitlines()[-1]) == (
        0,
        "problems=0 warnings=0",
    )
    problem = write_inputs(tmp_path / "problem", [synth.set_a_row(logged_on="")])
    done = run_script(arguments(problem))
    assert (done.returncode, done.stdout.splitlines()[-1]) == (
        1,
        "problems=1 warnings=0",
    )
    sealed = clean | {"--m8": tmp_path / "sealed" / "m8_labels.csv"}
    done = run_script(arguments(sealed))
    assert (done.returncode, done.stdout, done.stderr) == (2, "", REFUSED)
    assert run_script([]).returncode == 2


def test_run_intake_lets_the_split_allow_missing_m8(tmp_path):
    """The split reuses run_intake (C204). With allow_missing_m8, a Set A photo without
    its photo row is no problem, but it is still listed for the split's record."""
    paths = write_inputs(
        tmp_path,
        [synth.set_a_row(), synth.set_a_row(candidate_id="A002")],
        m8=[M8_PHOTO],
    )
    inputs = {
        "set_a_log": paths["--set-a-log"],
        "set_a_photos": paths["--set-a-photos"],
        "a_neg_log": paths["--a-neg-log"],
        "a_neg_photos": paths["--a-neg-photos"],
        "m8": paths["--m8"],
    }
    found = intake.run_intake(**inputs)
    assert (found.problems, found.warnings) == (
        [table.Finding("A002", "m8", "no_photo_row")],
        [],
    )
    found = intake.run_intake(**inputs, allow_missing_m8=True)
    assert (found.problems, found.warnings) == ([], [])
    assert [photo.photo_id for photo in found.set_a.photos] == ["A001", "A002"]
    assert [photo.photo_id for photo in found.a_neg.photos] == ["N001"]
    assert found.m8.missing_photo_rows == ["A002"]


@pytest.mark.parametrize(
    ("flag", "header", "expected"),
    [
        ("--set-a-log", None, "set_a row 1 cells: too_many"),
        ("--set-a-log", b"candidate_id,,photo_file", "set_a header column 2: blank"),
        ("--a-neg-log", None, "a_neg row 1 cells: too_many"),
        ("--m8", None, "m8 row 1 cells: too_many"),
        ("--consented", None, "consented row 1 cells: too_many"),
        ("--sidewalls", None, "sidewalls row 1 cells: too_many"),
    ],
)
def test_intake_names_a_malformed_log(tmp_path, capsys, flag, header, expected):
    """A log that can't be read whole stops the intake with exit 1, and only its finding
    is printed, led by the log's name and naming the row or column by number, never
    its text (controller addition 2)."""
    paths = write_inputs(
        tmp_path, m8=[M8_PHOTO], consented=[CONSENTED], sidewalls=[SIDEWALL]
    )
    log = paths[flag]
    if header is None:
        header = log.read_bytes().split(b"\n")[0]
    cells = [SENTINEL.encode()] * (header.count(b",") + 2)  # one cell too many
    log.write_bytes(header + b"\n" + b",".join(cells) + b"\n")
    assert run(paths) == 1
    assert capsys.readouterr().out == expected + "\n"


def test_intake_reads_no_photo_bytes(tmp_path):
    """Before the split, a photo is only statted, never opened or listed (C201). Under
    tmp_path the intake opens the logs alone, each once and in order, so nothing in
    either photos folder, and no sidewall photo or permission, is opened or listed."""
    paths = write_inputs(
        tmp_path,
        [synth.set_a_row(), synth.set_a_row(candidate_id="A002")],
        [synth.a_neg_row(), synth.a_neg_row(candidate_id="N002")],
        m8=[M8_PHOTO, M8_PHOTO | {"photo_id": "A002"}],
        sidewalls=[SIDEWALL],
    )
    code, events = synth.opened_paths(INTAKE, arguments(paths))
    assert code == 0
    logs = [
        paths[flag] for flag in ("--set-a-log", "--a-neg-log", "--m8", "--sidewalls")
    ]
    assert [item for item in events if inside(item[1], tmp_path)] == [
        ("open", str(log)) for log in logs
    ]


def snapshot(folder):
    """Each file and folder under folder: its time of last change, and a file's bytes."""
    return {
        path.relative_to(folder).as_posix(): (
            path.stat().st_mtime_ns,
            path.read_bytes() if path.is_file() else None,
        )
        for path in folder.rglob("*")
    }


def test_intake_writes_nothing(tmp_path, capsys, monkeypatch):
    monkeypatch.setitem(formats.APPROVED_CONSENT, "m9", frozenset({"M9-v3"}))
    paths = write_inputs(
        tmp_path, m8=[M8_PHOTO], consented=[CONSENTED], sidewalls=[SIDEWALL]
    )
    before = snapshot(tmp_path)
    assert run(paths) == 0
    assert snapshot(tmp_path) == before


def test_intake_output_holds_no_log_text(tmp_path, capsys):
    """C201: with a sentinel in every text column of every log, and as an unknown header
    name, the output never holds it. The rows reach each check that reads a cell:
    links, spots, labels, notes, posters, cities, alert columns and file names."""

    def everywhere(columns, **cells):
        return dict.fromkeys(columns, SENTINEL) | cells

    set_a_columns = SET_A_COLUMNS + (SENTINEL,)
    a_neg_columns = A_NEG_COLUMNS + (SENTINEL,)
    set_a = [
        everywhere(set_a_columns, candidate_id="A001", photo_in_alert_post="yes"),
        everywhere(set_a_columns, candidate_id="A002", photo_in_alert_post="no"),
        everywhere(
            set_a_columns,
            candidate_id="A002",
            photo_in_alert_post="no",
            spot_text=f"{SENTINEL} Ave.",
        ),
        everywhere(set_a_columns),  # a bad id
    ]
    m8 = [
        everywhere(formats.M8_COLUMNS, photo_id="A001", ref_id="P1", kind="photo"),
        everywhere(formats.M8_COLUMNS, photo_id="A001", ref_id="R1", kind="vehicle"),
        everywhere(formats.M8_COLUMNS, photo_id="A001", ref_id="R2"),
        everywhere(formats.M8_COLUMNS, photo_id="A001"),
        everywhere(formats.M8_COLUMNS),
    ]
    paths = write_inputs(
        tmp_path,
        set_a,
        [everywhere(a_neg_columns, candidate_id="N001")],
        set_a_columns=set_a_columns,
        a_neg_columns=a_neg_columns,
        m8=m8,
        consented=[
            everywhere(formats.CONSENTED_COLUMNS, item_id="S001"),
            everywhere(formats.CONSENTED_COLUMNS),
        ],
        sidewalls=[
            everywhere(formats.SIDEWALLS_COLUMNS, checked_code=f"{SENTINEL}2"),
        ],
    )
    assert run(paths) == 1
    printed = capsys.readouterr()
    assert {
        "set_a log column 21: unknown",
        "set_a row 4 candidate_id: bad_id",
        "A001 logged_on: bad_date",
        "A002 spot_text: differs",
        "a_neg log column 20: unknown",
        "A001 P1.quality: not_in_list",
        "A001 R1.x: out_of_range",
        "A001 R1.vehicle_type: not_in_list",
        "A001 R2.kind: not_in_list",
        "m8 row 4 ref_id: bad_ref",
        "m8 row 5 photo_id: unknown_photo",
        "S001 kind: not_in_list",
        "S001 lat: out_of_range",
        "consented row 2 item_id: bad_id",
        "sidewalls row 1 vehicle: not_in_list",
        "A001 metro_manila=no",
        "A001 poster_kind=other",
        "A002 alert_poster=other",
        "A002 match=none",
        "sidewalls row 1 code=mismatch",
    } <= set(printed.out.splitlines())
    assert SENTINEL.casefold() not in (printed.out + printed.err).casefold()


@pytest.mark.parametrize("flag", FLAGS)
def test_intake_refuses_sealed_paths(tmp_path, capsys, flag):
    """A path with a part named sealed is refused before anything opens (C222), whichever
    flag gives it: nothing under tmp_path is opened. The sealed folder is a name only,
    and none is created."""
    paths = write_inputs(
        tmp_path, m8=[M8_PHOTO], consented=[CONSENTED], sidewalls=[SIDEWALL]
    )
    paths[flag] = tmp_path / "sealed" / paths[flag].name
    with pytest.raises(SystemExit) as stop:
        run(paths)
    assert stop.value.code == 2
    assert capsys.readouterr() == ("", REFUSED)
    code, events = synth.opened_paths(INTAKE, arguments(paths))
    assert code == 2
    assert [item for item in events if inside(item[1], tmp_path)] == []
    assert not (tmp_path / "sealed").exists()


def test_intake_imports_only_the_standard_library():
    """A fresh interpreter that imports the intake loads no numpy, OpenCV or py7zr, so
    the script runs with dependencies = []."""
    probe = (
        f"import sys; sys.path.insert(0, {json.dumps(str(DATA))}); import intake; "
        "print(sorted({'numpy', 'cv2', 'py7zr'} & set(sys.modules)))"
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


def test_guide_examples_are_lines_the_intake_prints(tmp_path, capsys):
    """Task 7's M7: the guide's examples of a ref that names no id, a row, a header
    column and a missing column, are lines the intake prints, led by the log's name."""
    guide = GUIDE.read_text(encoding="utf-8")
    bad_id = [
        synth.set_a_row(),
        synth.set_a_row(candidate_id="A002"),
        synth.set_a_row(candidate_id="A3"),
    ]
    misspelt = formats.SET_A_COLUMNS + ("same_spot", "surface")
    no_city = tuple(column for column in SET_A_COLUMNS if column != "city")
    runs = [
        (write_inputs(tmp_path / "row", bad_id), "set_a row 3 candidate_id: bad_id"),
        (
            write_inputs(tmp_path / "column", a_neg_columns=misspelt),
            "a_neg log column 18: unknown",
        ),
        (
            write_inputs(tmp_path / "log", set_a_columns=no_city),
            "set_a log city: missing_column",
        ),
    ]
    for paths, line in runs:
        assert run(paths) == 1
        assert line in capsys.readouterr().out.splitlines()
        assert f"`{line}`" in guide
