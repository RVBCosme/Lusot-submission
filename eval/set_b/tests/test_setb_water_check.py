"""Tests for Set B's freeze check, eval/set_b/water_check.py (spec §5.6; C213, C221,
C222).

Every truth.csv, crop, drawn water mask, SAM result and look record is synthetic, under
tmp_path/"data", laid out as generate and set_b_masks --water leave it: the generated
folder in set_b/dev/generated, and SAM's water in set_b/dev/masks/water. The look
records go to tmp_path/"records". The check only hashes a crop, so a crop's bytes needn't
decode, and no test runs git: each record's git state is fixed.
"""

import json
import os
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import cv2
import formats
import numpy as np
import pytest
import record_io
import synth
import table
import water_check

SET_B = Path(__file__).resolve().parents[1]  # eval/set_b
DATA = SET_B.parent / "data"  # eval/data
WATER_CHECK = SET_B / "water_check.py"
SHAPE = (40, 60)  # (height, width), numpy's order
VERSION = "set-b-gen-v1"
REFUSED = "refused: path inside a folder named sealed\n"
USED = "three looks are used: the generator freezes as it is (C213)\n"
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+08:00")
UNKNOWN = {"commit": "unknown", "dirty": True}


@pytest.fixture(autouse=True)
def no_git(monkeypatch):
    """Every record's git state is fixed, so no test runs git."""
    monkeypatch.setattr(record_io, "git_state", lambda repo: UNKNOWN)


def rows_mask(y0: int, y1: int, *, x0: int = 0, x1: int = SHAPE[1]) -> np.ndarray:
    """A mask of SHAPE, true in rows y0 to y1 - 1 and columns x0 to x1 - 1."""
    mask = np.zeros(SHAPE, bool)
    mask[y0:y1, x0:x1] = True
    return mask


# The drawn water: the lower half, rows 20 to 39, 1,200 pixels. SAM's water over rows
# 20 to 24 covers 300 of them, exactly a quarter.
DRAWN = rows_mask(20, 40)
FULL = [DRAWN]
QUARTER = [rows_mask(20, 25)]
LOW = [rows_mask(20, 23)]  # 180 of 1,200


@pytest.fixture
def layout(tmp_path) -> dict[str, Path]:
    data = tmp_path / "data"
    generated = data / "set_b" / "dev" / "generated"
    return {
        "data": data,
        "generated": generated,
        "--truth": generated / "truth.csv",
        "--sam": data / "set_b" / "dev" / "masks" / "water",
        "--looks-dir": tmp_path / "records",
    }


def args(layout: dict[str, Path]) -> list[str]:
    return [
        part
        for flag in ("--truth", "--sam", "--looks-dir")
        for part in (flag, str(layout[flag]))
    ]


def truth_rows(crop_id: str, /, **cells: str) -> list[dict[str, str]]:
    """The crop's two truth rows, wheels 1 and 2, as generate writes them. Each keyword
    sets one cell in both, crop_id included. Only crop_id, crop_file and
    generator_version are read."""
    rows = []
    for wheel in ("1", "2"):
        row = dict.fromkeys(formats.TRUTH_COLUMNS, "")
        row |= {
            "crop_id": crop_id,
            "car_id": crop_id[:3],
            "split": "dev",
            "crop_file": f"{crop_id}.jpg",
            "wheel": wheel,
            "generator_version": VERSION,
        }
        rows.append(row | cells)
    return rows


def lay_crop(
    layout: dict[str, Path],
    crop_id: str,
    sam: list[np.ndarray] | None,
    *,
    drawn: np.ndarray = DRAWN,
    meta: dict | None = None,
) -> Path:
    """The crop's files: crops/<crop_id>.jpg and the drawn water, water/<crop_id>.png,
    as generate writes it, 255 for water. Then, unless sam is None, SAM's result as
    set_b_masks --water writes it: <sam>/<crop_id>/sam_floodwater_masks.npz, holding
    the masks given, and meta.json, with the crop's SHA-256 and the generator version,
    each key of meta replacing one of those. Return the crop's folder under --sam."""
    crop = f"synthetic crop {crop_id}".encode("ascii")
    generated = layout["generated"]
    (generated / "crops").mkdir(parents=True, exist_ok=True)
    (generated / "water").mkdir(parents=True, exist_ok=True)
    (generated / "crops" / f"{crop_id}.jpg").write_bytes(crop)
    png = cv2.imencode(".png", drawn.astype(np.uint8) * 255)[1].tobytes()
    (generated / "water" / f"{crop_id}.png").write_bytes(png)
    folder = layout["--sam"] / crop_id
    if sam is None:
        return folder
    folder.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        folder / "sam_floodwater_masks.npz",
        ids=np.arange(len(sam)),
        boxes=np.zeros((len(sam), 4)),
        scores=np.full(len(sam), np.nan),
        masks=np.array(sam, bool).reshape(-1, *SHAPE),
    )
    found = {
        "crop_sha256": table.sha256_bytes(crop),
        "generator_version": VERSION,
        "files": ["sam_floodwater.txt", "sam_floodwater_masks.npz"],
    }
    text = json.dumps(found | (meta or {}), indent=2, sort_keys=True) + "\n"
    (folder / "meta.json").write_bytes(text.encode("ascii"))
    return folder


def write_truth(layout: dict[str, Path], rows: list[dict[str, str]]) -> None:
    synth.write_csv(layout["--truth"], formats.TRUTH_COLUMNS, rows)


def look(layout: dict[str, Path], n: int = 1) -> dict:
    path = layout["--looks-dir"] / f"set-b-look-{n}.json"
    return json.loads(path.read_bytes())


def lay_look(layout: dict[str, Path], sams: dict[str, list[np.ndarray] | None]) -> None:
    """One crop per entry, each with its two truth rows."""
    rows = []
    for crop_id, sam in sams.items():
        lay_crop(layout, crop_id, sam)
        rows += truth_rows(crop_id)
    write_truth(layout, rows)


def test_thresholds():
    assert water_check.CROP_PASS == Fraction(1, 4)
    assert water_check.LOOK_PASS == Fraction(3, 4)
    assert water_check.MAX_LOOKS == 3


@pytest.mark.parametrize(
    ("sam", "share"),
    [
        (rows_mask(20, 25), Fraction(1, 4)),
        (rows_mask(0, 25), Fraction(1, 4)),  # SAM's water above the line counts not
        (rows_mask(20, 40), Fraction(1)),
        (np.zeros(SHAPE, bool), Fraction(0)),
        (rows_mask(39, 40, x0=0, x1=1), Fraction(1, 1200)),
        (rows_mask(20, 30, x0=0, x1=20), Fraction(200, 1200)),
    ],
)
def test_coverage(sam, share):
    assert water_check.coverage(sam, DRAWN) == share
    assert isinstance(water_check.coverage(sam, DRAWN), Fraction)


def test_coverage_refuses_masks_of_other_shapes():
    """A mask of another shape raises instead of broadcasting, as a single row would."""
    with pytest.raises(ValueError):
        water_check.coverage(np.ones((1, SHAPE[1]), bool), DRAWN)


def test_crop_pass_is_inclusive(layout):
    """Exactly a quarter passes; one pixel less is low_coverage."""
    under = rows_mask(20, 25)
    under[24, 59] = False  # 299 of 1,200
    lay_look(layout, {"B01-1-1": QUARTER, "B01-1-2": [under]})
    assert water_check.main(args(layout)) == 0
    found = look(layout)
    assert (found["crops"], found["passed"]) == (2, 1)
    assert found["failed_by_cause"] == {"low_coverage": 1}


@pytest.mark.parametrize(
    ("sams", "share", "result"),
    [
        ([FULL, FULL, QUARTER, LOW], "3/4", "pass"),
        ([FULL, QUARTER, LOW, LOW], "2/4", "fail"),
    ],
)
def test_look_passes_at_three_quarters(layout, capsys, sams, share, result):
    """3 of 4 crops pass the look, 2 of 4 fail it. The record holds the counts, the
    causes and the unreduced share, after base_record's fields; the run prints the
    causes, then the counts and the result."""
    lay_look(layout, {f"B01-1-{n}": sam for n, sam in enumerate(sams, start=1)})
    assert water_check.main(args(layout)) == 0
    passed = int(share[0])
    found = look(layout)
    assert DATE.fullmatch(found.pop("date"))
    assert found == {
        "tool": "eval/set_b/water_check.py",
        "git": UNKNOWN,
        "python": "{}.{}.{}".format(*sys.version_info[:3]),
        "look": 1,
        "generator_version": VERSION,
        "crops": 4,
        "passed": passed,
        "failed_by_cause": {"low_coverage": 4 - passed},
        "share": share,
        "result": result,
    }
    printed = (
        f"failed: low_coverage={4 - passed}\n"
        f"look=1 crops=4 passed={passed} share={share} result={result}\n"
    )
    assert capsys.readouterr() == (printed, "")


def test_sam_water_is_the_union_of_its_masks(layout):
    """SAM's water is the union of its masks: two that overlap count once, two that
    tile the quarter count in full, and none is no water."""
    lay_look(
        layout,
        {
            "B01-1-1": [rows_mask(20, 23), rows_mask(20, 23)],  # 180, not 360
            "B01-1-2": [rows_mask(20, 23), rows_mask(23, 25)],  # 300, the quarter
            "B01-1-3": [],
        },
    )
    assert water_check.main(args(layout)) == 0
    found = look(layout)
    assert (found["passed"], found["failed_by_cause"]) == (1, {"low_coverage": 2})


@pytest.mark.parametrize("missing", ["folder", "meta.json", "sam_floodwater_masks.npz"])
def test_missing_sam_result_fails_the_crop(layout, missing):
    lay_look(layout, {"B01-1-1": FULL, "B01-1-2": FULL})
    folder = layout["--sam"] / "B01-1-2"
    if missing == "folder":
        for name in ("meta.json", "sam_floodwater_masks.npz"):
            (folder / name).unlink()
        folder.rmdir()
    else:
        (folder / missing).unlink()
    assert water_check.main(args(layout)) == 0
    found = look(layout)
    assert (found["crops"], found["passed"]) == (2, 1)
    assert found["failed_by_cause"] == {"no_result": 1}


def test_stale_sam_result_fails_the_crop(layout):
    """A crop whose bytes changed after its SAM run, and one whose meta.json names an
    older generator version, fail as stale_result, though SAM's water covers all of the
    drawn water: a new look is never scored against old masks (C213)."""
    lay_look(layout, {"B01-1-1": FULL, "B01-1-2": FULL, "B01-1-3": FULL})
    (layout["generated"] / "crops" / "B01-1-2.jpg").write_bytes(b"a regenerated crop")
    lay_crop(layout, "B01-1-3", FULL, meta={"generator_version": "set-b-gen-v0"})
    assert water_check.main(args(layout)) == 0
    found = look(layout)
    assert (found["crops"], found["passed"]) == (3, 1)
    assert found["failed_by_cause"] == {"stale_result": 2}
    assert found["result"] == "fail"


def test_looks_are_numbered_and_capped(layout, capsys):
    """Three runs write set-b-look-1.json to -3.json. A fourth exits 2, and no file is
    rewritten or added."""
    lay_look(layout, {"B01-1-1": FULL})
    for n in (1, 2, 3):
        assert water_check.main(args(layout)) == 0
        assert look(layout, n)["look"] == n
    looks = layout["--looks-dir"]
    before = {n: (looks / f"set-b-look-{n}.json").read_bytes() for n in (1, 2, 3)}
    capsys.readouterr()
    assert water_check.main(args(layout)) == 2
    assert capsys.readouterr() == ("", USED)
    after = {n: (looks / f"set-b-look-{n}.json").read_bytes() for n in (1, 2, 3)}
    assert after == before
    assert not (looks / "set-b-look-4.json").exists()


def test_a_look_takes_the_first_free_number(layout):
    """The number is the first of 1 to 3 whose file doesn't exist, checked by name."""
    lay_look(layout, {"B01-1-1": FULL})
    layout["--looks-dir"].mkdir()
    (layout["--looks-dir"] / "set-b-look-1.json").write_bytes(b"an earlier look")
    assert water_check.main(args(layout)) == 0
    assert look(layout, 2)["look"] == 2


@pytest.mark.parametrize(
    ("versions", "kind"), [(["set-b-gen-v1", "set-b-gen-v2"], "mixed"), ([], "none")]
)
def test_mixed_generator_versions_stop(layout, capsys, versions, kind):
    """The rows must share one generator_version, so no look is written for rows of two
    versions, or for none."""
    rows = []
    for n, version in enumerate(versions, start=1):
        lay_crop(layout, f"B01-1-{n}", FULL, meta={"generator_version": version})
        rows += truth_rows(f"B01-1-{n}", generator_version=version)
    write_truth(layout, rows)
    assert water_check.main(args(layout)) == 1
    assert capsys.readouterr() == (f"truth generator_version: {kind}\n", "")
    assert not layout["--looks-dir"].exists()


@pytest.mark.parametrize("flag", ["--truth", "--sam", "--looks-dir"])
def test_water_check_refuses_sealed_paths(layout, tmp_path, capsys, flag):
    """Each path inside a folder named sealed is refused before anything opens, though
    the files are there to read (C222)."""
    lay_look(layout, {"B01-1-1": FULL})
    moved = tmp_path / "sealed" / "data"
    given = dict(layout)
    given[flag] = moved / layout[flag].relative_to(tmp_path)
    given[flag].parent.mkdir(parents=True, exist_ok=True)
    if flag != "--looks-dir":
        layout[flag].rename(given[flag])
    with pytest.raises(SystemExit) as stop:
        water_check.main(args(given))
    assert stop.value.code == 2
    assert capsys.readouterr() == ("", REFUSED)
    code, events = synth.opened_paths(WATER_CHECK, args(given))
    assert code == 2
    assert [item for item in events if inside(item[1], tmp_path)] == []
    assert not layout["--looks-dir"].exists()
    assert not (moved / "records").exists()


def inside(path: str, folder: Path) -> bool:
    absolute = Path(os.path.abspath(path))
    return absolute == folder or folder in absolute.parents


@pytest.mark.parametrize(
    "cells",
    [
        {"crop_id": "..\\sealed\\x", "crop_file": "B03-1-1.jpg"},
        {"crop_id": "../x", "crop_file": "B03-1-1.jpg"},
        {"crop_id": "b03-1-1", "crop_file": "B03-1-1.jpg"},
        {"crop_id": "B03-1-1.jpg", "crop_file": "B03-1-1.jpg"},
        {"crop_id": "B03-1-1-1", "crop_file": "B03-1-1.jpg"},
    ]
    + [
        {"crop_id": "B03-1-1", "crop_file": name}
        for name in ["..\\sealed\\x.jpg", "../x.jpg", "sub\\B03-1-1.jpg"]
        + ["sub/B03-1-1.jpg", "C:B03-1-1.jpg", "B03-1-1.jpg:stream", "..", "."]
        + ["B03-1-1..jpg", ""]
    ],
)
def test_a_bad_row_fails_its_crop(layout, cells):
    """Addition 1: a crop_id outside C221's pattern, or a crop_file that isn't a bare
    name, fails its crop as bad_row, so no cell steers a path."""
    lay_crop(layout, "B03-1-1", FULL)
    lay_crop(layout, "B01-1-1", FULL)
    write_truth(layout, truth_rows("B01-1-1") + truth_rows("B03-1-1", **cells))
    assert water_check.main(args(layout)) == 0
    found = look(layout)
    assert (found["crops"], found["passed"]) == (2, 1)
    assert found["failed_by_cause"] == {"bad_row": 1}


# opened_paths runs this as the script: it fixes the record's git state, as no_git
# does, so no test runs git, then runs water_check's main on the arguments.
RUNNER = """\
import sys
sys.path[:0] = [{set_b!r}, {data!r}]
import record_io
record_io.git_state = lambda repo: {{"commit": "unknown", "dirty": True}}
import water_check
sys.exit(water_check.main())
"""


def test_a_bad_row_opens_nothing(layout, tmp_path):
    """Addition 1: with a crop_id of ..\\sealed\\x and, where its cells would lead, a SAM
    result and drawn water that would pass, the check opens only truth.csv, the good
    crop's four files and the look it writes."""
    lay_crop(layout, "B01-1-1", FULL)
    lay_crop(layout, "B03-1-1", FULL)
    decoy = layout["--sam"].parent / "sealed" / "x"
    decoy.mkdir(parents=True)
    for name in ("meta.json", "sam_floodwater_masks.npz"):
        (decoy / name).write_bytes((layout["--sam"] / "B03-1-1" / name).read_bytes())
    drawn = layout["generated"] / "sealed" / "x.png"
    drawn.parent.mkdir()
    drawn.write_bytes((layout["generated"] / "water" / "B03-1-1.png").read_bytes())
    bad = {"crop_id": "..\\sealed\\x", "crop_file": "B03-1-1.jpg"}
    write_truth(layout, truth_rows("B01-1-1") + truth_rows("B03-1-1", **bad))
    runner = tmp_path / "runner" / "run_water_check.py"
    runner.parent.mkdir()
    runner.write_text(RUNNER.format(set_b=str(SET_B), data=str(DATA)), encoding="utf-8")
    code, events = synth.opened_paths(runner, args(layout))
    assert code == 0
    opened = {
        Path(path)
        for _, path in events
        if inside(path, layout["data"]) or inside(path, layout["--looks-dir"])
    }
    sam, generated = layout["--sam"] / "B01-1-1", layout["generated"]
    assert opened == {
        layout["--truth"],
        generated / "crops" / "B01-1-1.jpg",
        generated / "water" / "B01-1-1.png",
        sam / "meta.json",
        sam / "sam_floodwater_masks.npz",
        layout["--looks-dir"] / "set-b-look-1.json",
    }
    assert look(layout)["failed_by_cause"] == {"bad_row": 1}


def test_a_crop_file_named_sealed_is_refused(layout, capsys):
    """A bare crop_file named sealed would lead into crops\\sealed, so its path is refused
    before it opens (C222), and no look is written."""
    lay_crop(layout, "B01-1-1", FULL)
    write_truth(layout, truth_rows("B01-1-1", crop_file="Sealed"))
    with pytest.raises(SystemExit) as stop:
        water_check.main(args(layout))
    assert stop.value.code == 2
    assert capsys.readouterr() == ("", REFUSED)
    assert not layout["--looks-dir"].exists()


def test_the_look_holds_no_id(layout):
    """Addition 4: the look holds counts, causes and the share, never a crop id."""
    lay_look(layout, {"B01-1-1": FULL, "B01-1-2": LOW, "B01-1-3": None})
    assert water_check.main(args(layout)) == 0
    text = (layout["--looks-dir"] / "set-b-look-1.json").read_text(encoding="ascii")
    assert record_io.ID_TOKEN.search(text) is None
    assert "B01" not in text


def declare_size(data: bytes, width: int, height: int) -> bytes:
    """Rewrite a baseline JPEG's frame header (SOF0) so it declares another size.

    Copied from eval/data/tests/test_photos.py, which copied MS1's (R25).
    """
    i = 2  # after the start-of-image marker
    while data[i + 1] != 0xC0:
        i += 2 + int.from_bytes(data[i + 2 : i + 4], "big")
    size = height.to_bytes(2, "big") + width.to_bytes(2, "big")
    return data[: i + 5] + size + data[i + 9 :]


# For a fresh interpreter: whether cv2 decodes the bytes on stdin after `import
# water_check`.
DECODES = """\
import sys
import water_check
import cv2
import numpy as np
data = np.frombuffer(sys.stdin.buffer.read(), np.uint8)
try:
    decoded = cv2.imdecode(data, cv2.IMREAD_COLOR) is not None
except cv2.error:
    decoded = False
print(decoded)
"""


def test_water_check_loads_photos_first():
    """R25: water_check imports photos, which sets OpenCV's 50 MP cap, before cv2 loads,
    so a JPEG declaring 60 MP doesn't decode. The variable is removed from the child's
    environment, so the cap must come from water_check's own imports."""
    huge = declare_size(synth.jpeg(0, (16, 16)), 10_000, 6_000)
    env = {k: v for k, v in os.environ.items() if k != "OPENCV_IO_MAX_IMAGE_PIXELS"}
    env["PYTHONPATH"] = str(SET_B)
    done = subprocess.run(
        [sys.executable, "-c", DECODES],
        input=huge,
        capture_output=True,
        env=env,
        timeout=synth.TIMEOUT,
        check=True,
    )
    assert done.stdout.decode().split() == ["False"]


def test_water_check_loads_no_py7zr():
    """Its script holds numpy and OpenCV only, so importing it loads no py7zr."""
    probe = (
        f"import sys; sys.path.insert(0, {json.dumps(str(SET_B))}); "
        "import water_check; print('py7zr' in sys.modules)"
    )
    done = subprocess.run(
        [sys.executable, "-c", probe],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "False\n", "")


def test_water_check_help_exits_0():
    done = subprocess.run(
        [sys.executable, str(WATER_CHECK), "--help"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stderr) == (0, "")
    for flag in ("--truth", "--sam", "--looks-dir"):
        assert flag in done.stdout
