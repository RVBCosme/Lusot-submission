"""The one command (spec §4.1; C401, C411, C420, C421, C426).

    python eval/run_eval.py --from-saved [--results DIR] [--write]
    python eval/run_eval.py --label-words
    python eval/run_eval.py --rules-version

It rebuilds Lusot's evaluation report from saved results, with no install, no key and
no network. It refuses a path inside a folder named sealed before anything is read
(C411). It loads the results folder (eval/results/ beside this script, unless
--results names another) and, after rules §10's one disclosed rerun, its rerun/
folder, whose report sets the first run's beside its own (C421). It builds every
report file in memory before writing or comparing any, so input that can't be built
writes nothing. Then it compares the files with the committed copies in each
folder's report/, or with --write writes them there. --label-words prints the words a
committed label may hold, for the export (C420). --rules-version prints the rules
version this harness scores, alone and with no results folder, so the sealed-run
entry point can check its own by subprocess before it pays for a run.

Exit codes: 0 identical or written, 1 different, 2 refused or invalid. Every printed
line is ASCII, with any run of 12 digits masked.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

# Under python -I, sys.path doesn't hold this script's folder, so scoring couldn't be
# imported without it.
_EVAL = str(Path(__file__).resolve().parent)
if _EVAL not in sys.path:
    sys.path.insert(0, _EVAL)

from scoring import RULES_VERSION, rows
from scoring.labels import LABEL_WORDS
from scoring.metrics import Rate, fmt_rate
from scoring.paths import SealedPath, refuse_sealed
from scoring.report import build_report, build_review

DEFAULT_RESULTS = Path(__file__).resolve().parent / "results"

# The report's own files in report/. review.csv is Rene's sheet, never compared (C426).
_REPORT_SUFFIXES = (".md", ".json", ".svg")
_ACCOUNT = re.compile("[0-9]{12}")


class _Stop(Exception):
    """The input is refused or invalid: this line is printed, and the exit code is 2."""


class _Parser(argparse.ArgumentParser):
    """argparse, with its errors printed as every other line is."""

    def error(self, message: str) -> NoReturn:
        raise _Stop(f"invalid: {message}")


def main(argv: list[str] | None = None) -> int:
    """Run the command on `argv` (sys.argv's when None) and return its exit code. A
    file that can't be read or written, or a figure that can't be computed, is
    invalid input too. Its line names the file alone, and never repeats the error's
    text, which could hold a path or a value from the rows."""
    try:
        return _run(argv)
    except _Stop as stop:
        _say(str(stop))
    except OSError as error:
        _say(f"invalid: {_file_name(error)} can't be read or written")
    except ArithmeticError:  # decimal.InvalidOperation among them
        _say("invalid: a figure can't be computed from these results")
    return 2


def _file_name(error: OSError) -> str:
    """The name of the file an OSError names, without its folder."""
    try:
        return Path(error.filename).name or "a file"
    except TypeError:  # it names no file, or one by number
        return "a file"


def _run(argv: list[str] | None) -> int:
    args = _parser().parse_args(argv)
    if args.label_words:
        for word in sorted(LABEL_WORDS):
            _say(word)
        return 0
    if args.rules_version:
        _say(RULES_VERSION)
        return 0
    if not args.from_saved:
        raise _Stop(
            "invalid: give --from-saved to rebuild the report from the saved results"
            " (nothing calls a model), or --label-words"
        )
    results = args.results
    # The sealed guard runs here, before anything is read; the loader's own call is
    # the guard for other callers.
    try:
        refuse_sealed(results)
    except SealedPath as refused:
        raise _Stop(f"refused: {refused}") from None
    _say(f"results: {results}")
    if not results.is_dir():
        raise _Stop("invalid: no results folder at that path")
    # Both reports are built before either is written or compared, so a rerun that
    # can't be built leaves the first run's report as it was.
    first = _build(results, None, write=args.write)
    rerun = None
    # A rerun/ folder is always loaded, so one without its run.json is refused (C421).
    if (results / "rerun").is_dir():
        rerun = _build(results / "rerun", first.run, write=args.write, where="rerun/")
    code = _finish(first, write=args.write)
    if rerun is not None:
        _say(f"results: {rerun.folder}")
        code = max(code, _finish(rerun, write=args.write))
    return code


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="run_eval.py",
        description="Rebuild Lusot's evaluation report from saved results, and check"
        " it against the committed copy.",
    )
    parser.add_argument(
        "--from-saved",
        action="store_true",
        help="rebuild from the saved results; nothing calls a model",
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=DEFAULT_RESULTS,
        metavar="DIR",
        help="the results folder (default: eval/results beside this script)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the report's files instead of comparing them",
    )
    parser.add_argument(
        "--label-words",
        action="store_true",
        help="print the words a committed label may hold, one per line",
    )
    parser.add_argument(
        "--rules-version",
        action="store_true",
        help="print the rules version this harness scores, and nothing else",
    )
    return parser


@dataclass(frozen=True)
class _Built:
    """One results folder's report, built in memory: its files, and with --write a
    development run's review sheet (None otherwise)."""

    folder: Path
    run: rows.Run
    files: dict[str, bytes]
    review: bytes | None


def _build(
    folder: Path, first_run: rows.Run | None, *, write: bool, where: str = ""
) -> _Built:
    """Load one results folder and build its report in memory. An error's line names
    the file with `where` before it: "rerun/" for the rerun."""
    try:
        run = rows.load_run(folder)
    except rows.RowError as error:
        raise _Stop(f"invalid: {where}{error}") from None
    try:
        files = build_report(run, first_run=first_run)
    except ValueError as error:  # Task 8's copy guard, or C421's first_run
        raise _Stop(f"invalid: {where}{error}") from None
    return _Built(folder, run, files, build_review(run) if write else None)


def _finish(built: _Built, *, write: bool) -> int:
    """Print a built report's figures, then write its files or compare them, and
    return the exit code."""
    _say_figures(json.loads(built.files["summary.json"]), synthetic=built.run.synthetic)
    if write:
        return _write(built.folder / "report", built.files, built.review)
    return _compare(built.folder / "report", built.files)


def _say_figures(summary: dict, *, synthetic: bool) -> None:
    """From the summary just built: the run's kind and date, each configuration's
    three headline rates, and the decision."""
    marker = " (synthetic test data)" if synthetic else ""
    _say(f"run: {summary['kind']}, {summary['date']}{marker}")
    configurations = summary["configurations"]
    if configurations is None:
        _say("Set A: not run")
        return
    for config in rows.CONFIGS:
        if config in configurations:
            figures = configurations[config]
            _say(
                f"{config}: underestimation {_rate(figures['underestimation'])},"
                f" passability agreement {_rate(figures['passability'])},"
                f" coverage {_rate(figures['coverage'])}"
            )
    inches = "inches shown" if summary["inches_shown"] else "inches not shown"
    _say(f"decision: {summary['shipped']} ships, {inches}")


def _rate(pair: dict) -> str:
    return fmt_rate(Rate(pair["k"], pair["n"]))


def _write(report: Path, files: dict[str, bytes], review: bytes | None) -> int:
    """Write the report's files, and a development run's review sheet only when none
    is there yet, since it may hold Rene's notes (C426)."""
    report.mkdir(exist_ok=True)
    for name, data in sorted(files.items()):
        (report / name).write_bytes(data)
    if review is not None:
        try:
            with (report / "review.csv").open("xb") as sheet:
                sheet.write(review)
        except FileExistsError:
            _say("review.csv kept (it may hold Rene's notes)")
        else:
            _say("review.csv written")
    _say(f"report: {len(files)} files written")
    return 0


def _compare(report: Path, files: dict[str, bytes]) -> int:
    """Compare the built files with the committed ones in report/, reading \\r\\n as
    \\n on both sides. 1 when a file differs or is missing, or when an extra .md,
    .json or .svg file sits there; else 0. review.csv is never read."""
    differs = []
    for name, data in sorted(files.items()):
        committed = report / name
        if not committed.is_file():
            differs.append(f"{name} (missing)")
        elif _lf(committed.read_bytes()) != _lf(data):
            differs.append(name)
    if report.is_dir():
        differs += sorted(
            f"{path.name} (extra)"
            for path in report.iterdir()
            if path.suffix.lower() in _REPORT_SUFFIXES
            and path.name not in files
            and path.is_file()
        )
    if differs:
        _say(f"report: differs: {', '.join(differs)}")
        return 1
    _say(f"report: {len(files)} files identical")
    return 0


def _lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _say(line: str) -> None:
    """Print a line in ASCII, any other character as its backslash escape, with each
    run of 12 digits masked as <account>. The mask runs again after the escapes,
    since an escape's hex digits could join the digits beside it."""
    escaped = _ACCOUNT.sub("<account>", line).encode("ascii", "backslashreplace")
    print(_ACCOUNT.sub("<account>", escaped.decode("ascii")))


if __name__ == "__main__":
    sys.exit(main())
