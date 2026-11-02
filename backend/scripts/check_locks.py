"""The lock-drift guard (MS7 Task 14; spec D-l, R51), part of `npm run check:py`.

It names each lockfile that no longer matches what uv would write:
- `backend/analysis/uv.lock`, by `uv lock --check`
- `backend/analysis/requirements.lock.txt`, the analysis image's runtime pins, against a fresh
  `uv export --frozen --no-dev --no-emit-project --format requirements-txt` sent to stdout.
  `--frozen` keeps uv from re-locking, and there is never an `-o`, which would overwrite the
  file being checked. The requirement lines are compared; the header, which names the
  command that wrote the file, is not.
- each laptop script's `.py.lock` in `backend/scripts`, MS6's `eval/tests/run_tests.py` if it
  exists, and MS2's data tools in `eval/data`, `eval/data/tests` and `eval/set_b` (added
  Nov 2, when these locks were found unchecked: docs/log/2026-11-02.md), by `uv lock --script <script> --check`

Standard library only. Run from the repo root: uv run --python 3.13 backend/scripts/check_locks.py
Exit codes: 0 clean, 1 a lock drifted, 2 uv couldn't be run.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXPORT = [
    "uv",
    "export",
    "--frozen",
    "--no-dev",
    "--no-emit-project",
    "--format",
    "requirements-txt",
]

Runner = Callable[[list[str], Path], tuple[int, str]]


def run(args: list[str], cwd: Path) -> tuple[int, str]:
    """Runs a command; returns its exit code and its stdout. Its stderr is left to the console."""
    done = subprocess.run(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return done.returncode, done.stdout


def requirement_lines(text: str) -> list[str]:
    """The export's lines after its header: the comment lines it starts with are dropped."""
    lines = [line.rstrip() for line in text.splitlines()]
    start = 0
    while start < len(lines) and (not lines[start] or lines[start].startswith("#")):
        start += 1
    return lines[start:]


# The folders whose scripts carry their own lock: a script beside a `<name>.py.lock`.
LOCKED_FOLDERS = (
    ("backend", "scripts"),
    ("eval", "tests"),
    ("eval", "data"),
    ("eval", "data", "tests"),
    ("eval", "set_b"),
)


def locked_scripts(repo: Path) -> list[Path]:
    return [
        p
        for folder in LOCKED_FOLDERS
        for p in sorted(repo.joinpath(*folder).glob("*.py"))
        if p.with_name(p.name + ".lock").is_file()
    ]


def check(runner: Runner, repo: Path) -> list[str]:
    """The lockfiles that drifted, as repo-relative paths, in the order they were checked."""
    drifted = []
    analysis = repo / "backend" / "analysis"
    code, _ = runner(["uv", "lock", "--check"], analysis)
    if code != 0:
        drifted.append("backend/analysis/uv.lock")
    code, exported = runner(list(EXPORT), analysis)
    try:
        committed = (analysis / "requirements.lock.txt").read_text(encoding="utf-8")
    except FileNotFoundError:
        committed = None  # a missing lock has drifted from any export
    if (
        code != 0
        or committed is None
        or requirement_lines(exported) != requirement_lines(committed)
    ):
        drifted.append("backend/analysis/requirements.lock.txt")
    for script in locked_scripts(repo):
        relative = script.relative_to(repo).as_posix()
        code, _ = runner(["uv", "lock", "--script", relative, "--check"], repo)
        if code != 0:
            drifted.append(f"{relative}.lock")
    return drifted


def main() -> int:
    try:
        drifted = check(run, REPO)
    except OSError as error:
        print(
            f"check_locks: can't run uv ({error.__class__.__name__}: {error.filename})",
            file=sys.stderr,
        )
        return 2
    for path in drifted:
        print(f"lock drift: {path}")
    print(f"locks: {len(drifted)} drifted" if drifted else "locks: clean")
    return 1 if drifted else 0


if __name__ == "__main__":
    raise SystemExit(main())
