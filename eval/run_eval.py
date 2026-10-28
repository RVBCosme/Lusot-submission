"""The one command (spec §4.1; C401, C411, C420, C421, C426).

    python eval/run_eval.py --from-saved [--results DIR] [--write]
    python eval/run_eval.py --label-words

It rebuilds Lusot's evaluation report from saved results, with no install, no key and
no network. It refuses a path inside a folder named sealed before anything is read
(C411), loads the results folder (eval/results/ beside this script, unless --results
names another), and builds every report file in memory. Then it compares them with
the committed copies in the folder's report/, or with --write writes them there. When
the folder holds rules §10's one disclosed rerun in rerun/, it does the same for the
rerun, beside the first run (C421). --label-words prints the words a committed label
may hold, for the export (C420).

Exit codes: 0 identical or written, 1 different, 2 refused or invalid. Every printed
line is ASCII, with any run of 12 digits masked.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NoReturn

# Under python -I, sys.path doesn't hold this script's folder, so scoring couldn't be
# imported without it.
_EVAL = str(Path(__file__).resolve().parent)
if _EVAL not in sys.path:
    sys.path.insert(0, _EVAL)

from scoring import rows
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
    """Run the command on `argv` (sys.argv's when None) and return its exit code."""
    try:
        return _run(argv)
    except _Stop as stop:
        _say(str(stop))
        return 2


def _run(argv: list[str] | None) -> int:
    args = _parser().parse_args(argv)
    if args.label_words:
        for word in sorted(LABEL_WORDS):
            _say(word)
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
    first, code = _rebuild(results, None, write=args.write)
    rerun = results / "rerun"
    if (rerun / "run.json").is_file():
        _say(f"results: {rerun}")
        _, rerun_code = _rebuild(rerun, first, write=args.write)
        code = max(code, rerun_code)
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
    return parser


def _rebuild(
    folder: Path, first_run: rows.Run | None, *, write: bool
) -> tuple[rows.Run, int]:
    """Load one results folder, build its report in memory and print its figures,
    then write the files or compare them. Returns the run, which a rerun's report
    sets beside its own, and the exit code."""
    try:
        run = rows.load_run(folder)
    except rows.RowError as error:
        raise _Stop(f"invalid: {error}") from None
    try:
        files = build_report(run, first_run=first_run)
    except ValueError as error:  # Task 8's copy guard, or C421's first_run
        raise _Stop(f"invalid: {error}") from None
    review = build_review(run) if write else None
    _say_figures(json.loads(files["summary.json"]), synthetic=run.synthetic)
    if write:
        return run, _write(folder / "report", files, review)
    return run, _compare(folder / "report", files)


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
