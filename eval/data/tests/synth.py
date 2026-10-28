"""Synthetic data and test doubles for the tests of MS2's data tools.

Nothing here reads real data.
"""

import builtins
import getpass
import json
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

import guards
import numpy as np
import pytest
import table

# The password the tests give every synthetic archive (C206). Its spaces keep gitleaks'
# generic rule from matching.
TEST_PHRASE = "test phrase for synthetic archives"

# Seconds a test's subprocess may run, so a tool that waits for input fails instead of
# hanging the suite. On Windows, getpass reads the console itself, which NUL can't feed.
TIMEOUT = 60


def jpeg(seed: int, size: tuple[int, int] = (240, 320)) -> bytes:
    """A JPEG of seeded random colour blocks. size is (height, width), numpy's order.

    The blocks lie on dHash's grid of 8 rows by 9 columns, so each dHash bit compares
    two random blocks, and two seeds' dHashes differ in about half their 64 bits, far
    beyond the 6 that make a near duplicate.
    """
    # Imported here: OpenCV reads its decode cap once, when cv2 loads, and photos.py
    # sets the cap before it imports cv2 (R25). Importing cv2 when this module loads
    # would leave the test process without the cap.
    import cv2

    rng = np.random.default_rng(seed)
    blocks = rng.integers(0, 256, size=(8, 9, 3), dtype=np.uint8)
    image = cv2.resize(blocks, (size[1], size[0]), interpolation=cv2.INTER_NEAREST)
    return cv2.imencode(".jpg", image)[1].tobytes()


def write_csv(
    path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> Path:
    """Write the rows as the tools write a CSV, creating any missing parent folders."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(table.csv_bytes(columns, rows))
    return path


def console(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make guards.console_ok() hold, as it does in Rene's own window."""
    monkeypatch.setattr(guards, "console_ok", lambda **_: True)


def typed(monkeypatch: pytest.MonkeyPatch, *answers: str) -> None:
    """Answer each getpass.getpass and input prompt with the next answer, in order."""
    replies = iter(answers)

    def reply(prompt: str = "") -> str:
        return next(replies)

    monkeypatch.setattr(getpass, "getpass", reply)
    monkeypatch.setattr(builtins, "input", reply)


# opened_paths runs this as `python -c _AUDIT <out> <script> <args...>`. Its first act
# adds the audit hook. It then runs the script as __main__, with the script's folder
# first on sys.path as `python <script>` sets it, and at the end writes what the hook
# saw to <out>.
_AUDIT = """\
import sys

seen = []
watching = True


def hook(event, args):
    if watching and event in ("open", "os.scandir", "os.listdir"):
        seen.append((event, args[0]))


sys.addaudithook(hook)

import json
import os
import runpy


def text(path):
    # os.listdir() and os.scandir() with no argument read the current folder.
    if path is None:
        return os.curdir
    if isinstance(path, int):  # a file descriptor
        return str(path)
    return os.fsdecode(path)


out, script = sys.argv[1:3]
sys.argv = sys.argv[2:]
sys.path[0] = os.path.dirname(os.path.abspath(script))
try:
    runpy.run_path(script, run_name="__main__")
finally:
    watching = False
    with open(out, "w", encoding="utf-8") as file:
        json.dump([[event, text(path)] for event, path in seen], file)
"""


def opened_paths(
    script: Path, argv: Sequence[str]
) -> tuple[int, list[tuple[str, str]]]:
    """Run the script as `python <script> <argv...>` would, with stdin on NUL, in a
    fresh interpreter that watches its audit events.

    It returns the exit code and each (event, path) of the open, os.scandir and
    os.listdir events, in order. open covers builtins.open, io.open, os.open and
    pathlib's reads, and also the interpreter's own reads, such as each module it
    imports. An open inside a C extension, such as cv2.imread's, raises no event.

    A run longer than TIMEOUT seconds is killed, and subprocess.TimeoutExpired
    propagates.
    """
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder, "events.json")
        done = subprocess.run(
            [sys.executable, "-c", _AUDIT, str(out), str(script), *argv],
            stdin=subprocess.DEVNULL,
            timeout=TIMEOUT,
            check=False,
        )
        events = json.loads(out.read_text(encoding="utf-8"))
    return done.returncode, [(event, path) for event, path in events]
