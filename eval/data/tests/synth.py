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

import formats
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


def set_a_row(**cells: str) -> dict[str, str]:
    """A row of Set A's log that passes every check: MMDA's photo, in the same post as
    its alert, at a two-name spot in Manila (C209, C224). It holds the template's 20
    columns, so a log on the 17-column template simply leaves the last three out.

    Each keyword sets one cell. photo_file follows candidate_id unless it is given.
    """
    row = {
        "candidate_id": "A001",
        "logged_on": "2026-10-29",
        "platform": "facebook",
        "post_url": "https://example.invalid/post/1",
        "poster": "MMDA",
        "post_time_pht": "2026-08-09 08:20",
        "alert_time_pht": "",
        "spot_text": "España Blvd. cor. Lacson Ave.",
        "city": "Manila",
        "level_label_raw": 'Gutter deep, 8"',
        "passability_raw": "PATV",
        "photo_in_alert_post": "yes",
        "photo_file": f"{cells.get('candidate_id', 'A001')}.jpg",
        "reference_visible": "wheel",
        "label_in_image": "no",
        "faces_or_plates": "no",
        "notes": "",
        "same_spot_as": "",
        "alert_poster": "",
        "alert_spot_text": "",
    }
    row.update(cells)
    return row


def a_neg_row(**cells: str) -> dict[str, str]:
    """A row of A-neg's log that passes every check: Rene's own photo of a dry street at
    a two-name spot in Manila, with the level none, and the post's and the alert's
    columns blank, as the guide has them (C209).

    Each keyword sets one cell. photo_file follows candidate_id unless it is given.
    """
    row = {
        "candidate_id": "N001",
        "logged_on": "2026-10-29",
        "platform": "",
        "post_url": "",
        "poster": "own",
        "post_time_pht": "2026-10-27 16:05",
        "alert_time_pht": "",
        "spot_text": "Taft Ave. cor. Pedro Gil",
        "city": "Manila",
        "level_label_raw": "none",
        "passability_raw": "",
        "photo_in_alert_post": "",
        "photo_file": f"{cells.get('candidate_id', 'N001')}.jpg",
        "reference_visible": "wheel",
        "label_in_image": "no",
        "faces_or_plates": "no",
        "notes": "",
        "surface": "dry",
        "same_spot_as": "",
    }
    row.update(cells)
    return row


# split_inputs' photos: each one's number, date, spot word and whether its alert states
# NPLV. Set A's events are Task 10's golden input once A007 and A009 join A001 as its
# copies: each of the three is logged at its own spot, so only their bytes join them
# (Task 13's addition 9). Every other event has a spot word of its own.
_SET_A_PHOTOS = (
    (1, "2026-08-09", "Alfa", False),  # E01, with A007 and A009
    (2, "2026-08-09", "Bravo", True),  # E02
    (3, "2026-08-09", "Bravo", True),
    (4, "2026-08-09", "Charlie", False),  # E03
    (5, "2026-08-09", "Charlie", False),
    (6, "2026-08-09", "Delta", True),  # E04
    (7, "2026-08-10", "Echo", False),  # A001's bytes
    (8, "2026-08-09", "Delta", True),
    (9, "2026-08-10", "Foxtrot", False),  # A001 re-encoded
    (10, "2026-08-09", "Golf", False),  # E05
    (11, "2026-08-09", "Golf", False),
    (12, "2026-08-09", "Hotel", True),  # E06
    (13, "2026-08-09", "Hotel", True),
    (14, "2026-08-10", "India", False),  # E07
    (15, "2026-08-10", "India", False),
    (16, "2026-08-10", "Juliett", False),  # E08
    (17, "2026-08-10", "Kilo", True),  # E09
    (18, "2026-08-10", "Lima", False),  # E10
    (19, "2026-08-10", "Mike", True),  # E11
    (20, "2026-08-10", "November", False),  # E12
)
_A_NEG_PHOTOS = (
    (1, "2026-10-27", "Oscar"),  # E01
    (2, "2026-10-27", "Oscar"),
    (3, "2026-10-27", "Papa"),  # E02
    (4, "2026-10-27", "Papa"),
    (5, "2026-10-27", "Quebec"),  # E03
    (6, "2026-10-28", "Romeo"),  # E04
    (7, "2026-10-28", "Sierra"),  # E05
    (8, "2026-10-28", "Tango"),  # E06
)


def split_inputs(root: Path) -> dict[str, Path]:
    """Lay out a synthetic data folder like lusot-data under root, as Rene leaves it
    for the split, and return each of the split's flags with its path.

    Set A has 20 photos, A001 to A020, each on one same-post row of its log, in 12
    events of 3, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1 and 1 photos over two dates. The 2nd,
    4th, 6th, 9th and 11th events are deep: their alerts state NPLV. A007 holds A001's
    bytes and A009 is A001 re-encoded, so they join A001's event as its copies. A-neg
    has 8 photos, N001 to N008, in 6 events of 2, 2, 1, 1, 1 and 1. M8 gives each Set A
    photo its photo row. The outputs don't exist yet, but the archive's folder, named
    sealed, does, and the record lies outside it.
    """
    # Imported here, as in jpeg, so the decode cap photos.py sets holds (R25).
    import cv2

    set_a = root / "set_a"
    a_neg = root / "a_neg"
    paths = {
        "--set-a-log": write_csv(
            set_a / "set_a_log.csv",
            formats.TEMPLATES["set_a_log.csv"],
            [
                set_a_row(
                    candidate_id=f"A{number:03d}",
                    post_time_pht=f"{date} 08:{number:02d}",
                    spot_text=f"{spot} St.",
                    passability_raw="NPLV" if deep else "PATV",
                )
                for number, date, spot, deep in _SET_A_PHOTOS
            ],
        ),
        "--set-a-photos": set_a / "raw",
        "--a-neg-log": write_csv(
            a_neg / "a_neg_log.csv",
            formats.TEMPLATES["a_neg_log.csv"],
            [
                a_neg_row(
                    candidate_id=f"N{number:03d}",
                    post_time_pht=f"{date} 16:{number:02d}",
                    spot_text=f"{spot} St.",
                )
                for number, date, spot in _A_NEG_PHOTOS
            ],
        ),
        "--a-neg-photos": a_neg / "raw",
        "--m8": write_csv(
            set_a / "m8_labels.csv",
            formats.M8_COLUMNS,
            [
                {
                    "photo_id": f"A{number:03d}",
                    "ref_id": "P1",
                    "kind": "photo",
                    "quality": "ok",
                }
                for number, *_ in _SET_A_PHOTOS
            ],
        ),
        "--set-a-dev": set_a / "dev",
        "--a-neg-dev": a_neg / "dev",
        "--archive": root / "sealed" / "lusot-sealed.7z",
        "--record": root / "records" / "split.json",
    }
    for folder in (set_a / "raw", a_neg / "raw", root / "sealed"):
        folder.mkdir(parents=True)
    photos = {f"A{number:03d}": jpeg(number) for number, *_ in _SET_A_PHOTOS}
    image = cv2.imdecode(np.frombuffer(photos["A001"], np.uint8), cv2.IMREAD_COLOR)
    photos["A007"] = photos["A001"]
    reencoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 70])[1]
    photos["A009"] = reencoded.tobytes()
    for photo_id, data in photos.items():
        (set_a / "raw" / f"{photo_id}.jpg").write_bytes(data)
    for number, *_ in _A_NEG_PHOTOS:
        (a_neg / "raw" / f"N{number:03d}.jpg").write_bytes(jpeg(100 + number))
    return paths


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
