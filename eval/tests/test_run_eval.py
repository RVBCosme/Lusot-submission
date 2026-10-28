"""The one command (spec §4.1, E10, E11; C401, C411, C421, C426). It rebuilds the
committed fixture's report byte for byte, refuses a sealed path before anything is
read, and prints only ASCII."""

from __future__ import annotations

import ast
import csv
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from builders import a_neg_row, level, run_json, set_a_row, set_b_row, write_run
from run_eval import main
from scoring import rows
from scoring.labels import LABEL_WORDS

EVAL = Path(__file__).resolve().parents[1]
RUN_EVAL = EVAL / "run_eval.py"
FIXTURE = EVAL / "tests" / "fixtures" / "small_run"
REFUSED = "refused: path inside a folder named sealed"

# The fixture's figures, worked out by hand from its rows. A01 to A08 are scored
# (A09 to A12 are excluded), and six are answered: A04 is refused and A05 failed.
# Five answered alerts gave a level: A01 knee, A02 tire, A03 half_knee, A06 knee and
# A07 chest. Landmark alone reads A02 one level low, A03 as no flood seen and A07 one
# level low; geometry reads only A03 low. Of the five stated classes, landmark alone
# misses only A02's NPATV. Set B's envelope holds 4 of 7 measured wheels, below 80%,
# so geometry stays but inches aren't shown.
FIXTURE_FIGURES = [
    "run: sealed, 2026-10-30 (synthetic test data)",
    (
        "landmark: underestimation 3 of 5 (60.0%), passability agreement 4 of 5"
        " (80.0%), coverage 6 of 8 (75.0%)"
    ),
    (
        "geometry: underestimation 1 of 5 (20.0%), passability agreement 5 of 5"
        " (100.0%), coverage 6 of 8 (75.0%)"
    ),
    "decision: geometry ships, inches not shown",
]
FIXTURE_REPORT = [
    "level-matrix-geometry.svg",
    "level-matrix-landmark.svg",
    "report.md",
    "set-b-errors.svg",
    "summary.json",
]
RERUN_REASON = "a fix changed the depth output"
# A stop whose cause brings a banned word into the report (Task 8's copy guard).
SAFETY_STOP = {"at": "21:10", "cause": "Safety restart", "resumed": "21:40"}


# Running the command


def run(capsys, *args: str) -> tuple[int, list[str]]:
    """main(args)'s exit code and the lines it printed. Every run in this file is
    checked here: both streams hold only ASCII, and no run of 12 digits (Review
    Focus 4)."""
    code = main(list(args))
    out, err = capsys.readouterr()
    assert (out + err).isascii(), out + err
    assert re.search("[0-9]{12}", out + err) is None, out + err
    return code, out.splitlines()


def rebuild(capsys, folder: Path, *flags: str) -> tuple[int, list[str]]:
    return run(capsys, "--from-saved", "--results", str(folder), *flags)


def isolated(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    """The script under python -I, from `cwd`, with no environment but what Windows
    needs to start Python."""
    env = {"SYSTEMROOT": os.environ["SYSTEMROOT"]} if os.name == "nt" else {}
    return subprocess.run(
        [sys.executable, "-I", str(script), *args],
        check=False,
        cwd=cwd,
        env=env,
        capture_output=True,
        timeout=120,
    )


# Results folders, all under tmp_path. None is ever named sealed.


def copy_fixture(folder: Path, *, report: bool = True) -> Path:
    """A copy of the fixture at `folder`, with or without its committed report."""
    ignore = None if report else shutil.ignore_patterns("report")
    return Path(shutil.copytree(FIXTURE, folder, ignore=ignore))


def change_result(path: Path, photo_id: str, config: str, **fields: object) -> None:
    """Set `fields` in one photo's result for `config`, keeping every other line."""
    lines = path.read_bytes().decode("utf-8").split("\n")
    for number, line in enumerate(lines):
        if line and json.loads(line)["photo_id"] == photo_id:
            row = json.loads(line)
            row["outcomes"][config].update(fields)
            lines[number] = json.dumps(row)
    path.write_bytes("\n".join(lines).encode("utf-8"))


def break_line(path: Path, number: int) -> None:
    """Cut one line of a JSON Lines file short, so it isn't valid JSON."""
    lines = path.read_bytes().split(b"\n")
    lines[number - 1] = lines[number - 1][:40]
    path.write_bytes(b"\n".join(lines))


def edit_manifest(folder: Path, **fields: object) -> None:
    manifest = json.loads((folder / "run.json").read_bytes())
    manifest.update(fields)
    (folder / "run.json").write_bytes(json.dumps(manifest).encode("utf-8"))


def contents(folder: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in folder.iterdir()}


# The tests


@pytest.mark.parametrize(
    "parts",
    [("sealed",), ("a", "Sealed", "x"), ("sealed", "sub", ".."), ("sealed", "..", "x")],
    ids=["sealed", "in another case", "inside, then up", "up again, as given"],
)
@pytest.mark.parametrize("flags", [(), ("--write",)], ids=["compare", "write"])
def test_refuses_sealed_paths(tmp_path, capsys, monkeypatch, parts, flags):
    def load_run(folder):
        raise AssertionError("the loader was called")

    monkeypatch.setattr(rows, "load_run", load_run)
    # The path is refused by its text alone, so it never exists on disk.
    code, lines = rebuild(capsys, tmp_path.joinpath(*parts), *flags)
    assert code == 2
    # The refusal never names the path.
    assert lines == [REFUSED]
    assert not any(tmp_path.iterdir())


def test_from_saved_is_required(tmp_path, capsys):
    folder = copy_fixture(tmp_path / "run1", report=False)
    for args in ([], ["--results", str(folder)], ["--results", str(folder), "--write"]):
        code, lines = run(capsys, *args)
        assert code == 2, args
        assert lines[-1].startswith("invalid: "), args
        assert "--from-saved" in lines[-1], args
    assert not (folder / "report").exists()


def test_label_words(capsys):
    code, lines = run(capsys, "--label-words")
    assert code == 0
    assert lines == sorted(LABEL_WORDS)


def test_rebuilds_the_fixture_identically(capsys):
    code, lines = rebuild(capsys, FIXTURE)
    assert code == 0
    assert lines == [
        f"results: {FIXTURE}",
        *FIXTURE_FIGURES,
        "report: 5 files identical",
    ]


def test_a_changed_row_gives_exit_1(tmp_path, capsys):
    folder = copy_fixture(tmp_path / "run1")
    # A01's alert gave knee and NPLV, so waist reads two levels over, in NPATV.
    change_result(
        folder / "set_a.jsonl", "A01", "geometry", level="waist", passability="NPATV"
    )
    code, lines = rebuild(capsys, folder)
    assert code == 1
    # The figures printed are the ones just built, not the committed summary's.
    assert (
        "geometry: underestimation 1 of 5 (20.0%), passability agreement 4 of 5"
        " (80.0%), coverage 6 of 8 (75.0%)"
    ) in lines
    assert lines[-1] == (
        "report: differs: level-matrix-geometry.svg, report.md, summary.json"
    )


def test_set_b_only_folder(tmp_path, capsys):
    folder = write_run(
        tmp_path / "dev",
        run=run_json(),
        set_b=[set_b_row("B01", 1), set_b_row("B01", 2)],
    )
    code, lines = rebuild(capsys, folder, "--write")
    assert code == 0
    assert "Set A: not run" in lines
    code, lines = rebuild(capsys, folder)
    assert code == 0
    assert lines == [
        f"results: {folder}",
        "run: development, 2026-10-30",
        "Set A: not run",
        "report: 3 files identical",
    ]


def test_review_sheet_is_written_once(tmp_path, capsys):
    folder = write_run(
        tmp_path / "dev",
        run=run_json(),
        set_a=[set_a_row("A01"), set_a_row("A02", geometry=level("tire"))],
        a_neg=[a_neg_row("N01")],
    )
    code, lines = rebuild(capsys, folder, "--write")
    assert code == 0
    assert "review.csv written" in lines
    sheet = folder / "report" / "review.csv"
    text = sheet.read_bytes().decode("utf-8")
    table = list(csv.reader(io.StringIO(text, newline="")))
    assert [row[:2] for row in table[1:]] == [
        ["set_a", "A01"],
        ["set_a", "A02"],
        ["a_neg", "N01"],
    ]
    # Rene fills in a verdict, and the sheet is saved again with \r\n endings.
    table[1][table[0].index("rene_verdict")] = "agree"
    edited = io.StringIO()
    csv.writer(edited, lineterminator="\r\n").writerows(table)
    sheet.write_bytes(edited.getvalue().encode("utf-8"))
    noted = sheet.read_bytes()
    code, lines = rebuild(capsys, folder, "--write")
    assert code == 0
    assert "review.csv kept (it may hold Rene's notes)" in lines
    assert sheet.read_bytes() == noted
    # The check never reads the sheet.
    code, lines = rebuild(capsys, folder)
    assert code == 0
    assert lines[-1] == "report: 4 files identical"
    # A sealed run gets no sheet (C426).
    assert not (FIXTURE / "report" / "review.csv").exists()


def test_write_then_compare(tmp_path, capsys):
    folder = copy_fixture(tmp_path / "run1", report=False)
    code, lines = rebuild(capsys, folder, "--write")
    assert code == 0
    assert lines[-1] == "report: 5 files written"
    code, lines = rebuild(capsys, folder)
    assert code == 0
    assert lines[-1] == "report: 5 files identical"
    # The committed report's files, and no review sheet for a sealed run (C426).
    assert sorted(contents(folder / "report")) == FIXTURE_REPORT


def test_compare_reads_crlf_and_names_missing_and_extra_files(tmp_path, capsys):
    folder = copy_fixture(tmp_path / "run1", report=False)
    assert rebuild(capsys, folder, "--write")[0] == 0
    report = folder / "report"
    # A checkout with \r\n endings still compares identical, and review.csv is never
    # read or reported.
    for name, data in contents(report).items():
        (report / name).write_bytes(data.replace(b"\n", b"\r\n"))
    (report / "review.csv").write_bytes(b"set,photo_id\r\n")
    code, lines = rebuild(capsys, folder)
    assert code == 0
    assert lines[-1] == "report: 5 files identical"
    (report / "summary.json").unlink()
    (report / "old-chart.svg").write_bytes(b"<svg/>\n")
    (report / "notes.txt").write_bytes(b"kept\n")
    code, lines = rebuild(capsys, folder)
    assert code == 1
    assert lines[-1].startswith("report: differs: ")
    named = lines[-1].removeprefix("report: differs: ").split(", ")
    assert sorted(named) == ["old-chart.svg (extra)", "summary.json (missing)"]


def test_rerun_folder(tmp_path, capsys):
    folder = copy_fixture(tmp_path / "run1")
    rerun = copy_fixture(folder / "rerun", report=False)
    edit_manifest(rerun, date="2026-11-02", rerun_reason=RERUN_REASON)
    code, lines = rebuild(capsys, folder, "--write")
    assert code == 0
    assert lines.count("report: 5 files written") == 2
    # The rerun's report sets the first run's figures beside its own (C421).
    report = (rerun / "report" / "report.md").read_bytes().decode("utf-8")
    assert RERUN_REASON in report
    assert "## First run, for comparison" in report
    assert "The first run's figures, from 2026-10-30," in report
    code, lines = rebuild(capsys, folder)
    assert code == 0
    assert f"results: {rerun}" in lines
    assert [line for line in lines if line.startswith("report: ")] == [
        "report: 5 files identical",
        "report: 5 files identical",
    ]
    change_result(
        rerun / "set_a.jsonl", "A01", "geometry", level="waist", passability="NPATV"
    )
    code, lines = rebuild(capsys, folder)
    assert code == 1
    first, second = [line for line in lines if line.startswith("report: ")]
    assert first == "report: 5 files identical"
    assert second.startswith("report: differs: ")
    assert "report.md" in second


def test_invalid_input_gives_exit_2(tmp_path, capsys):
    folder = copy_fixture(tmp_path / "run1", report=False)
    break_line(folder / "set_a.jsonl", 3)
    for flags in ((), ("--write",)):
        code, printed = rebuild(capsys, folder, *flags)
        assert code == 2
        assert printed[-1] == "invalid: set_a.jsonl:3: the text isn't valid JSON"
    assert not (folder / "report").exists()
    # A results folder that isn't there, and an argument that isn't known.
    missing = tmp_path / "missing"
    code, printed = rebuild(capsys, missing, "--write")
    assert code == 2
    assert printed == [f"results: {missing}", "invalid: no results folder at that path"]
    assert not missing.exists()
    code, printed = run(capsys, "--from-saved", "--colour")
    assert code == 2
    assert printed[-1].startswith("invalid: ")


def test_report_errors_give_exit_2(tmp_path, capsys):
    # Task 8's copy guard: run.json's free text would bring a banned word in.
    folder = copy_fixture(tmp_path / "run1", report=False)
    edit_manifest(folder, stops=[SAFETY_STOP])
    for flags in ((), ("--write",)):
        code, lines = rebuild(capsys, folder, *flags)
        assert code == 2
        assert lines[-1].startswith(
            "invalid: report.md would contain a banned word (safe);"
        )
    assert not (folder / "report").exists()
    # C421: a rerun folder given on its own has no first run beside it.
    rerun = copy_fixture(tmp_path / "run2" / "rerun", report=False)
    edit_manifest(rerun, rerun_reason=RERUN_REASON)
    code, lines = rebuild(capsys, rerun, "--write")
    assert code == 2
    assert lines[-1] == (
        "invalid: first_run comes with a rerun's report, and only then (C421)"
    )
    assert not (rerun / "report").exists()


@pytest.mark.parametrize(
    ("fault", "error"),
    [
        ("row", "invalid: rerun/set_a.jsonl:3: the text isn't valid JSON"),
        ("word", "invalid: rerun/report.md would contain a banned word (safe);"),
    ],
    ids=["broken row", "banned word"],
)
def test_invalid_rerun_writes_nothing(tmp_path, capsys, fault, error):
    # Every file is built before any is written or compared, so a rerun that can't
    # be built leaves the first run's report as it was (the controller's ruling).
    folder = copy_fixture(tmp_path / "run1")
    # A changed row, so a rewritten first report would differ from the committed one.
    change_result(
        folder / "set_a.jsonl", "A01", "geometry", level="waist", passability="NPATV"
    )
    rerun = copy_fixture(folder / "rerun", report=False)
    edit_manifest(rerun, rerun_reason=RERUN_REASON)
    if fault == "row":
        break_line(rerun / "set_a.jsonl", 3)
    else:
        edit_manifest(rerun, stops=[SAFETY_STOP])
    committed = contents(folder / "report")
    for flags in (("--write",), ()):
        code, lines = rebuild(capsys, folder, *flags)
        assert code == 2, flags
        assert contents(folder / "report") == committed, flags
        assert not (rerun / "report").exists(), flags
        assert not [line for line in lines if line.startswith("report: ")], flags
        assert lines[-1].startswith(error), flags


def test_runs_isolated_from_another_folder(tmp_path):
    done = isolated(RUN_EVAL, "--from-saved", "--results", str(FIXTURE), cwd=tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert (done.stdout + done.stderr).isascii()
    assert done.stdout.decode("ascii").splitlines()[-1] == "report: 5 files identical"


def test_default_results_folder(tmp_path):
    # The literal command: eval/results/ beside the script, from any folder.
    copy = tmp_path / "repo" / "eval"
    shutil.copytree(
        EVAL / "scoring", copy / "scoring", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copy2(RUN_EVAL, copy / "run_eval.py")
    copy_fixture(copy / "results")
    (tmp_path / "work").mkdir()
    done = isolated(copy / "run_eval.py", "--from-saved", cwd=tmp_path / "work")
    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.decode("ascii").splitlines()
    assert lines[0] == f"results: {copy / 'results'}"
    assert lines[-1] == "report: 5 files identical"


def test_no_network(monkeypatch, capsys):
    def refuse(*args, **kwargs):
        raise AssertionError("the harness opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    code, _ = rebuild(capsys, FIXTURE)
    assert code == 0


@pytest.mark.parametrize(
    "path",
    [RUN_EVAL, *sorted((EVAL / "scoring").glob("*.py"))],
    ids=lambda path: path.name,
)
def test_standard_library_only(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            # A relative import stays inside scoring.
            imported.append("scoring" if node.level else node.module)
    for name in imported:
        top = name.split(".")[0]
        assert top == "scoring" or top in sys.stdlib_module_names, name
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.name for alias in node.names)
    assert not names & {"environ", "environb", "getenv", "getenvb"}


def test_output_is_ascii(tmp_path, capsys):
    # run() checks every run in this file. A folder's name is the only outside text
    # printed, so here one holds a non-ASCII letter, and one a run of 12 digits like
    # an account ID (built, since the account-ID scan forbids writing one out).
    accented = copy_fixture(tmp_path / "r\N{LATIN SMALL LETTER E WITH ACUTE}sultats")
    code, lines = rebuild(capsys, accented)
    assert code == 0
    assert lines[0] == f"results: {tmp_path}{os.sep}r\\xe9sultats"
    digits = "1" * 12
    account = copy_fixture(tmp_path / f"run{digits}")
    code, lines = rebuild(capsys, account)
    assert code == 0
    assert lines[0] == f"results: {tmp_path}{os.sep}run<account>"
    # argparse's own messages pass through the same mask: here --results was left out.
    code, lines = run(capsys, "--from-saved", str(account))
    assert code == 2
    assert lines[-1].startswith("invalid: ")
    assert "<account>" in lines[-1]
