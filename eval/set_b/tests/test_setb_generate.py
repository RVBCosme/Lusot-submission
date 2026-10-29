"""Tests for Set B's generator, eval/set_b/generate.py (spec §5.6, §5.9; C202, C205,
C206, C210 to C214, C218, C220, C221, C222).

Every cars.csv, photo, mask, archive and record is synthetic, under tmp_path/"data",
laid out like lusot-data: the development cars in set_b/dev, the final cars in
set_b/sealed, and the archive's folder, sealed. The masks folders come from
synth.masks_folder, as set_b_masks lays them out. Only test code opens an archive, with
the test phrase (C206), and no test runs git: each record's git state is fixed.
"""

import getpass
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import audit
import cars
import crops
import cv2
import events
import generate
import numpy as np
import photos
import py7zr
import pytest
import record_io
import synth
import table
import tires
import truth

SET_B = Path(__file__).resolve().parents[1]  # eval/set_b
GENERATE = SET_B / "generate.py"
SHAPE = (360, 640)  # (height, width), numpy's order
REFUSED = "refused: path inside a folder named sealed\n"
NO_CONSOLE = "refused: run this yourself, in a Windows PowerShell window\n"
PROMPTS = ["Archive password: ", "Type it again: "]
FINAL_FLAGS = (
    "--cars",
    "--masks",
    "--dev-cars",
    "--dev-masks",
    "--archive",
    "--record",
)


def rect(y0: int, x0: int, y1: int, x1: int) -> np.ndarray:
    """A mask of SHAPE, true in rows y0 to y1 - 1 and columns x0 to x1 - 1."""
    mask = np.zeros(SHAPE, bool)
    mask[y0:y1, x0:x1] = True
    return mask


VEHICLE = rect(120, 60, 330, 580)
# Two wheels whose lowest rows are 300 and 294, as in Task 15's crops tests: the near
# one on the left, 101 rows tall, and the far one on the right, 89 rows tall. Each
# rim lies inside its wheel.
WHEELS = [
    synth.ellipse_mask(SHAPE, (250, 150), 50, 45),
    synth.ellipse_mask(SHAPE, (250, 470), 44, 40),
]
RIMS = [
    synth.ellipse_mask(SHAPE, (250, 150), 30, 27),
    synth.ellipse_mask(SHAPE, (250, 470), 26, 24),
]
# The final cars: B02 with two photos and B04 with one, whose owners' OK is one file,
# and B06 with its own OK, each a bare name beside cars.csv (S-R29's M3). Their rows
# are rows 1 to 4 of the final cars.csv.
FINAL_ROWS = (
    {"car_id": "B02", "consent_file": "owner.png"},
    {
        "car_id": "B02",
        "photo_file": "B02-2.jpg",
        "view": "angled",
        "consent_file": "owner.png",
    },
    {
        "car_id": "B04",
        "vehicle_type": "suv_mpv",
        "tire_code": "205/55R16",
        "consent_file": "owner.png",
    },
    {"car_id": "B06"},
)


def seed(stem: str) -> int:
    """A photo's own seed for synth.jpeg, from its car and photo number: B02-1 gives
    201. Its raw photo takes the seed plus 50."""
    car, number = stem.split("-")
    return int(car[1:]) * 100 + int(number)


def photo_masks(
    masks: Path,
    stem: str,
    *,
    vehicle: bool = True,
    wheels: int = 2,
    rims: int = 2,
    photo: bytes | None = None,
) -> None:
    """One photo's masks folder, as set_b_masks leaves it: its blurred photo, the
    vehicle, the first wheels of WHEELS and the first rims of RIMS."""
    if photo is None:
        photo = synth.jpeg(seed(stem), SHAPE)
    synth.masks_folder(
        masks,
        stem,
        photo,
        [VEHICLE] if vehicle else [],
        WHEELS[:wheels],
        RIMS[:rims],
    )


def dev_layout(data: Path) -> dict[str, Path]:
    """The development cars, B01 and B03, one photo each with two wheels: their
    cars.csv, with each owner's OK beside it, and their masks."""
    folder = data / "set_b" / "dev"
    synth.set_b_cars(folder, [synth.car_row(), synth.car_row(car_id="B03")])
    for stem in ("B01-1", "B03-1"):
        photo_masks(folder / "masks", stem)
    return {"--cars": folder / "cars.csv", "--masks": folder / "masks"}


def final_layout(data: Path, rows=FINAL_ROWS) -> dict[str, Path]:
    """The development layout, then the final cars, each photo with its raw copy in
    photos/ and its masks, and the archive's folder, named sealed. Return each of
    --final's flags with its path; neither output exists yet."""
    dev = dev_layout(data)
    folder = data / "set_b" / "sealed"
    final = [synth.car_row(**cells) for cells in rows]
    synth.set_b_cars(folder, final)
    (folder / "photos").mkdir()
    for row in final:
        stem = Path(row["photo_file"]).stem
        photo_masks(folder / "masks", stem)
        raw = synth.jpeg(seed(stem) + 50, SHAPE)
        (folder / "photos" / row["photo_file"]).write_bytes(raw)
    (data / "sealed").mkdir()
    return {
        "--cars": folder / "cars.csv",
        "--masks": folder / "masks",
        "--dev-cars": dev["--cars"],
        "--dev-masks": dev["--masks"],
        "--archive": data / "sealed" / "lusot-sealed-set-b.7z",
        "--record": data / "records" / "set-b-final.json",
    }


@pytest.fixture(autouse=True)
def no_git(monkeypatch):
    """Every record's git state is fixed, so no test runs git."""
    monkeypatch.setattr(
        record_io, "git_state", lambda repo: {"commit": "unknown", "dirty": True}
    )


@pytest.fixture
def data(tmp_path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def prompts(monkeypatch) -> list[str]:
    """Rene's console, with the test phrase typed twice. The list records each
    password prompt shown, so a test can prove getpass was never called."""
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
    """The generator's exit code, whether main returns it or a guard exits."""
    try:
        return generate.main(arguments(paths, *extra))
    except SystemExit as stop:
        return stop.code


def nothing_written(paths) -> bool:
    return not paths["--archive"].exists() and not paths["--record"].exists()


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


def files_under(folder: Path) -> set[Path]:
    return {path for path in folder.rglob("*") if path.is_file()}


def inside(path, folder) -> bool:
    absolute = Path(os.path.abspath(path))
    return absolute == folder or folder in absolute.parents


def jpeg_95(image: np.ndarray) -> bytes:
    return cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tobytes()


def generated(paths, side: str = "dev") -> tuple[cars.CarsCheck, generate.Generated]:
    """check_cars and generate called directly on a layout's cars and masks."""
    check = cars.check_cars(paths["--cars"], side=side)
    return check, generate.generate(check, paths["--masks"], split="dev")


# --- the development run ---


def test_dev_generation_writes_crops_truth_overlays(data, capsys):
    dev = dev_layout(data)
    out = data / "set_b" / "dev" / "generated"
    assert run(dev | {"--out": out}) == 0
    stdout, stderr = capsys.readouterr()
    assert stderr == ""
    lines = stdout.splitlines()
    assert lines[:2] == [
        "drops: none",
        "cars=2 photos=2 crops=8 wheels=4 wheels_without_rim=0",
    ]
    assert re.fullmatch(r"seconds=[0-9]+\.[0-9]", lines[2])
    assert len(lines) == 3
    rows = rows_of(out / "truth.csv")
    assert len(rows) == 16
    crop_ids = sorted({row["crop_id"] for row in rows})
    assert crop_ids == [f"{car}-1-{n}" for car in ("B01", "B03") for n in range(1, 5)]
    for row in rows:
        assert table.is_id(row["crop_id"]) and table.is_id(row["car_id"])
        assert row["split"] == "dev"
        assert row["crop_file"] == f"{row['crop_id']}.jpg"
        assert row["generator_version"] == "set-b-gen-v1"
        assert re.fullmatch(r"[0-9]+(\.[0-9]{1,4})?", row["true_depth_in"])
        assert row["diameter_in"] == "22.9567"
        assert re.fullmatch(r"[0-9]+\.[0-9]{1,4}", row["rim_edge_ratio"])
    each_crop = {row["crop_id"]: row for row in rows}.values()
    assert Counter(row["size_bin"] for row in each_crop) == {"small": 4, "full": 4}
    expected = {"truth.csv"} | {
        f"{folder}/{crop_id}.{ext}"
        for crop_id in crop_ids
        for folder, ext in (("crops", "jpg"), ("water", "png"), ("overlays", "jpg"))
    }
    files = {path.relative_to(out).as_posix() for path in files_under(out)}
    assert files == expected | {"files.txt"}
    assert (out / "files.txt").read_bytes().decode("ascii") == "".join(
        f"{table.sha256_file(out / name)}  {name}\n" for name in sorted(expected)
    )
    for crop_id in crop_ids:
        crop = cv2.imdecode(
            np.frombuffer((out / "crops" / f"{crop_id}.jpg").read_bytes(), np.uint8),
            cv2.IMREAD_COLOR,
        )
        water = cv2.imdecode(
            np.frombuffer((out / "water" / f"{crop_id}.png").read_bytes(), np.uint8),
            cv2.IMREAD_UNCHANGED,
        )
        overlay = cv2.imdecode(
            np.frombuffer((out / "overlays" / f"{crop_id}.jpg").read_bytes(), np.uint8),
            cv2.IMREAD_COLOR,
        )
        assert crop.shape == overlay.shape
        assert water.shape == crop.shape[:2]
        assert set(np.unique(water)) <= {0, 255}


def test_truth_rows_hold_each_crops_own_truth(data):
    """Addition 8: each crop's rows hold its own wheels' geometry and truth, wheel 1 the
    leftmost; rim_edge_ratio comes from the unshrunk masks, rounded to 4 decimals like
    true_depth_in and diameter_in."""
    _, made = generated(dev_layout(data))
    assert (len(made.crops), len(made.rows)) == (8, 16)
    assert (made.drops, made.wheels_without_rim) == (Counter(), 0)
    diameter = tires.diameter_in(tires.parse_tire_code("175/65R14"))
    ratios = [
        truth.rim_edge_ratio(rim, truth.wheel_geom(wheel, diameter).px_per_in, 14)
        for wheel, rim in zip(WHEELS, RIMS, strict=True)
    ]
    by_crop: dict[str, list[dict[str, str]]] = {}
    for row in made.rows:
        by_crop.setdefault(row["crop_id"], []).append(row)
    assert list(by_crop) == [crop.plan.crop_id for crop in made.crops]
    for crop in made.crops:
        found = by_crop[crop.plan.crop_id]
        assert [row["wheel"] for row in found] == ["1", "2"]
        for row, (geom, (left, right, line, depth)), ratio in zip(
            found, crop.wheels, ratios, strict=True
        ):
            assert row["car_id"] == crop.plan.crop_id[:3]
            assert row["photo_file"] == f"{crop.plan.crop_id[:5]}.jpg"
            assert (row["view"], row["vehicle_type"]) == ("side", "sedan_hatch")
            assert (row["tire_code"], row["rim_in"]) == ("175/65R14", "14")
            assert row["crop_scale"] == str(crop.scale)
            assert row["size_bin"] == ("small" if crop.plan.shrink else "full")
            assert [row[key] for key in ("x0", "y0", "x1", "y1")] == [
                str(geom.x0),
                str(geom.y0),
                str(geom.x1),
                str(geom.y1),
            ]
            assert (row["ground_row"], row["top_row"]) == (
                str(geom.ground_row),
                str(geom.top_row),
            )
            assert float(row["px_per_in"]) == geom.px_per_in
            assert row["waterline_left_row"] == str(left)
            assert row["waterline_right_row"] == str(right)
            assert row["waterline_row"] == str(line)
            assert row["true_depth_in"] == str(depth)
            assert row["band"] == crop.plan.band
            assert row["rim_edge_ratio"] == str(round(ratio, 4))
            assert row["diameter_in"] == str(round(diameter, 4))


def test_overlay_draws_the_line_and_the_boxes(data):
    """The overlay draws the waterline's row in each column in red, exactly where the
    water starts, over each chosen wheel's box in yellow, and leaves the crop as it
    was."""
    _, made = generated(dev_layout(data))
    for crop in made.crops:
        before = crop.image.copy()
        image = generate.draw_overlay(crop)
        assert np.array_equal(crop.image, before)
        height, width = crop.image.shape[:2]
        rows = truth.line_rows(
            [geom for geom, _ in crop.wheels], crop.plan.depth_in, width
        )
        for x in range(width):
            if 0 <= rows[x] < height:
                assert tuple(image[rows[x], x]) == (0, 0, 255)
                assert crop.water[rows[x], x]
                assert rows[x] == 0 or not crop.water[rows[x] - 1, x]
        for geom, _ in crop.wheels:
            assert tuple(image[geom.y0, geom.x0]) == (0, 255, 255)
            assert tuple(image[geom.y1 - 1, geom.x1 - 1]) == (0, 255, 255)


def test_drops_are_counted_by_cause(data, capsys):
    """Addition 1: drops print as counts by cause, never by car. B05's 195R14C has no
    aspect ratio, B07 has no owner's OK, B09's masks hold no vehicle, B11 has no
    masks, B13's none of its wheels, and B15's blurred photo doesn't decode."""
    dev = dev_layout(data)
    rows = [synth.car_row(), synth.car_row(car_id="B03")]
    rows += [synth.car_row(car_id="B05", tire_code="195R14C")]
    rows += [synth.car_row(car_id=car) for car in ("B07", "B09", "B11", "B13", "B15")]
    folder = dev["--cars"].parent
    synth.set_b_cars(folder, rows)
    (folder / "b07-ok.png").unlink()
    for stem in ("B05-1", "B07-1", "B15-1"):
        photo_masks(dev["--masks"], stem)
    photo_masks(dev["--masks"], "B09-1", vehicle=False)
    photo_masks(dev["--masks"], "B13-1", wheels=0)
    (dev["--masks"] / "B15-1" / "blurred.jpg").write_bytes(b"not a photo")
    out = data / "set_b" / "dev" / "generated"
    assert run(dev | {"--out": out}) == 0
    stdout, stderr = capsys.readouterr()
    assert stdout.splitlines()[:2] == [
        (
            "drops: no_aspect_ratio=1 no_consent=1 no_masks=1 no_vehicle=1 "
            "no_wheel=1 undecodable=1"
        ),
        "cars=2 photos=2 crops=8 wheels=4 wheels_without_rim=0",
    ]
    assert re.search(r"B(05|07|09|11|13|15)", stdout + stderr) is None
    check, made = generated(dev)
    assert check.drops == {"B05": "no_aspect_ratio", "B07": "no_consent"}
    assert made.drops == Counter(no_masks=1, no_vehicle=1, no_wheel=1, undecodable=1)


def test_wheel_without_a_rim(data, capsys):
    """Addition 8: a wheel with no linked rim gets a blank rim_edge_ratio in each of its
    crops' rows, and counts once in wheels_without_rim."""
    dev = dev_layout(data)
    photo_masks(dev["--masks"], "B01-1", rims=1)  # the far wheel's rim is gone
    _, made = generated(dev)
    assert made.wheels_without_rim == 1
    for row in made.rows:
        blank = (row["car_id"], row["wheel"]) == ("B01", "2")
        assert (row["rim_edge_ratio"] == "") == blank
    assert run(dev | {"--out": data / "out"}) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1] == "cars=2 photos=2 crops=8 wheels=4 wheels_without_rim=1"


def test_unapproved_consent_only_warns(data, capsys):
    """C218: the warning prints, and the car's crops are made all the same."""
    dev = dev_layout(data)
    rows = [synth.car_row(consent_version="SETB-v0"), synth.car_row(car_id="B03")]
    synth.set_b_cars(dev["--cars"].parent, rows)
    assert run(dev | {"--out": data / "out"}) == 0
    assert capsys.readouterr().out.splitlines()[:3] == [
        "B01 consent_version=unapproved",
        "drops: none",
        "cars=2 photos=2 crops=8 wheels=4 wheels_without_rim=0",
    ]


def test_shrink_out_of_range_is_a_drop(data, monkeypatch):
    """Addition 9: a shrunk crop make_crop refuses is left out of the truth and counted
    as shrink_out_of_range, by cause."""
    make_crop = crops.make_crop

    def refuses_shrunk(blurred, masks, diameter, plan, rng):
        if plan.shrink:
            raise crops.ShrinkOutOfRange("a shrunk wheel is outside 50 to 80 px")
        return make_crop(blurred, masks, diameter, plan, rng)

    monkeypatch.setattr(crops, "make_crop", refuses_shrunk)
    _, made = generated(dev_layout(data))
    assert made.drops == Counter(shrink_out_of_range=4)
    assert len(made.crops) == 4
    assert {row["size_bin"] for row in made.rows} == {"full"}
    assert {row["crop_id"] for row in made.rows} == {
        crop.plan.crop_id for crop in made.crops
    }


def test_problem_stops_the_development_run(data, capsys):
    dev = dev_layout(data)
    rows = [synth.car_row(view="front"), synth.car_row(car_id="B03")]
    synth.set_b_cars(dev["--cars"].parent, rows)
    assert run(dev | {"--out": data / "out"}) == 1
    assert capsys.readouterr() == ("B01 view: not_in_list\n", "")
    assert not (data / "out").exists()


# Development paths refused, each with the flag it changes, the path it gives, and the
# refusal.
DEV_REFUSALS = {
    "cars inside sealed": (
        "--cars",
        lambda data: data / "sealed" / "cars.csv",
        REFUSED,
    ),
    "masks inside sealed": (
        "--masks",
        lambda data: data / "set_b" / "sealed" / "masks",
        REFUSED,
    ),
    "out inside sealed": ("--out", lambda data: data / "sealed" / "out", REFUSED),
    "existing out": (
        "--out",
        lambda data: data / "set_b" / "dev",
        "--out exists: delete it before rerunning\n",
    ),
    "relative cars": (
        "--cars",
        lambda data: Path("set_b", "dev", "cars.csv"),
        "refused: --cars must be absolute\n",
    ),
    "relative masks": (
        "--masks",
        lambda data: Path("masks"),
        "refused: --masks must be absolute\n",
    ),
    "relative out": (
        "--out",
        lambda data: Path("out"),
        "refused: --out must be absolute\n",
    ),
}


@pytest.mark.parametrize("rule", DEV_REFUSALS.values(), ids=list(DEV_REFUSALS))
def test_dev_refuses_sealed_paths_and_existing_out(
    data, tmp_path, monkeypatch, capsys, rule
):
    """C222 and addition 2: on the strings, or for --out, a stat, before anything is
    read or written. The test runs in an empty folder of its own."""
    flag, make, expected = rule
    dev = dev_layout(data)
    before = files_under(data)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    given = dev | {"--out": data / "out"} | {flag: make(data)}
    assert run(given) == 2
    assert capsys.readouterr() == ("", expected)
    assert files_under(data) == before
    assert list(cwd.iterdir()) == []


# --- the final run ---


@pytest.mark.parametrize("flag", FINAL_FLAGS)
def test_final_path_rules(data, prompts, capsys, flag):
    """C202, C222: --cars, --masks or --archive outside a folder named sealed, or
    --dev-cars, --dev-masks or --record inside one, exits 2 on the strings, before
    anything is read. Each file is there to read."""
    paths = final_layout(data)
    given = dict(paths)
    if flag in ("--cars", "--masks", "--archive"):
        given[flag] = data / "outside" / paths[flag].name
        expected = f"refused: {flag} must be inside a folder named sealed\n"
    else:
        given[flag] = data / "sealed" / "moved" / paths[flag].name
        expected = REFUSED
    assert run(given, "--final") == 2
    assert capsys.readouterr() == ("", expected)
    code, opened = synth.opened_paths(GENERATE, arguments(given, "--final"))
    assert code == 2
    assert [item for item in opened if inside(item[1], data)] == []
    assert prompts == []
    assert nothing_written(paths)


# --final's paths refused on their strings (addition 2), each with the flag, the path
# it gives, relative to the test's working folder, and the refusal.
WRITE_RULES = {
    "relative cars": (
        "--cars",
        lambda data: Path("sealed", "cars.csv"),
        "refused: --cars must be absolute\n",
    ),
    "relative masks": (
        "--masks",
        lambda data: Path("sealed", "masks"),
        "refused: --masks must be absolute\n",
    ),
    "relative dev cars": (
        "--dev-cars",
        lambda data: Path("dev", "cars.csv"),
        "refused: --dev-cars must be absolute\n",
    ),
    "relative dev masks": (
        "--dev-masks",
        lambda data: Path("dev", "masks"),
        "refused: --dev-masks must be absolute\n",
    ),
    "relative archive": (
        "--archive",
        lambda data: Path("sealed", "lusot-sealed-set-b.7z"),
        "refused: --archive must be absolute\n",
    ),
    "archive not 7z": (
        "--archive",
        lambda data: data / "sealed" / "lusot-sealed-set-b.zip",
        "refused: --archive name\n",
    ),
    "archive an NTFS stream": (
        "--archive",
        lambda data: data / "sealed" / "sealed:b.7z",
        "refused: --archive name\n",
    ),
    "archive under a colon": (
        "--archive",
        lambda data: Path(f"{data / 'sealed'}/x:y/set-b.7z"),
        "refused: --archive name\n",
    ),
    "archive name with an id": (
        "--archive",
        lambda data: data / "sealed" / "B02.7z",
        "refused: --archive name\n",
    ),
    "archive name with a space": (
        "--archive",
        lambda data: data / "sealed" / "set b.7z",
        "refused: --archive name\n",
    ),
}


@pytest.mark.parametrize("rule", WRITE_RULES.values(), ids=list(WRITE_RULES))
def test_final_write_path_rules(data, tmp_path, prompts, monkeypatch, capsys, rule):
    """Each refusal names its flag only, before anything opens or is created."""
    flag, make, expected = rule
    paths = final_layout(data)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    given = dict(paths) | {flag: make(data)}
    assert run(given, "--final") == 2
    assert capsys.readouterr() == ("", expected)
    code, opened = synth.opened_paths(GENERATE, arguments(given, "--final"))
    assert code == 2
    assert [item for item in opened if inside(item[1], data)] == []
    assert prompts == []
    assert list(cwd.iterdir()) == []
    assert nothing_written(paths)


def test_final_refuses_without_a_console(data):
    """With stdin on NUL and stdout piped, as in Claude's shell, --final stops at the
    console check, before it stats or reads anything (C202)."""
    paths = final_layout(data)
    done = subprocess.run(
        [sys.executable, str(GENERATE), *arguments(paths, "--final")],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (2, "", NO_CONSOLE)
    assert nothing_written(paths)


@pytest.mark.parametrize("flags", [("--archive",), ("--record",), FINAL_FLAGS[4:]])
def test_rerun_names_each_existing_output(data, prompts, capsys, flags):
    """Addition 2: a rerun names each output left by an earlier run, and changes
    nothing."""
    paths = final_layout(data)
    for flag in flags:
        paths[flag].parent.mkdir(exist_ok=True)
        paths[flag].write_bytes(b"x")
    assert run(paths, "--final") == 2
    assert capsys.readouterr() == (
        "",
        "".join(f"{flag} exists: delete it before rerunning\n" for flag in flags),
    )
    assert all(paths[flag].read_bytes() == b"x" for flag in flags)
    assert prompts == []


def test_archive_folder_must_exist(data, prompts, capsys):
    """Addition 2: no code creates a folder inside sealed."""
    paths = final_layout(data)
    paths["--archive"] = data / "sealed" / "missing" / "lusot-sealed-set-b.7z"
    assert run(paths, "--final") == 2
    assert capsys.readouterr() == ("", "--archive folder missing: create it first\n")
    assert not paths["--archive"].parent.exists()
    assert nothing_written(paths)
    assert prompts == []


# Missing inputs, each as the flag it changes, the path it gives, and the refusal.
# --dev-masks must hold set_b_masks' files.txt, so a folder that exists but isn't the
# development masks can't let the overlap check compare nothing (S-R29's M1).
MISSING_INPUTS = {
    "cars": (
        "--cars",
        lambda paths: paths["--cars"].parent / "missing",
        "--cars missing\n",
    ),
    "masks": (
        "--masks",
        lambda paths: paths["--masks"].parent / "missing",
        "--masks missing\n",
    ),
    "dev cars": (
        "--dev-cars",
        lambda paths: paths["--dev-cars"].parent / "missing",
        "--dev-cars missing\n",
    ),
    "dev masks": (
        "--dev-masks",
        lambda paths: paths["--dev-masks"].parent / "missing",
        "--dev-masks files.txt missing\n",
    ),
    "dev masks without files.txt": (
        "--dev-masks",
        lambda paths: paths["--dev-cars"].parent,
        "--dev-masks files.txt missing\n",
    ),
}


@pytest.mark.parametrize("case", MISSING_INPUTS.values(), ids=list(MISSING_INPUTS))
def test_missing_input_is_refused(data, prompts, capsys, case):
    """A missing input is named by its flag, before the password."""
    flag, make, expected = case
    paths = final_layout(data)
    paths[flag] = make(paths)
    assert run(paths, "--final") == 2
    assert capsys.readouterr() == ("", expected)
    assert nothing_written(paths)
    assert prompts == []


def test_missing_source_stops_before_the_password(data, prompts, capsys):
    """A source the archive would hold is checked by a stat before the password: a raw
    photo, and a file the masks' files.txt lists, each named by its photo's row."""
    paths = final_layout(data)
    (paths["--cars"].parent / "photos" / "B04-1.jpg").unlink()
    (paths["--masks"] / "B02-2" / "sam_wheel_rim_masks.npz").unlink()
    assert run(paths, "--final") == 1
    assert capsys.readouterr() == (
        "row 3 photo_file: missing\nrow 2 masks: missing\n",
        "",
    )
    (paths["--masks"] / "files.txt").unlink()
    assert run(paths, "--final") == 1
    assert capsys.readouterr().out.splitlines()[-1] == "masks files.txt: missing"
    assert nothing_written(paths)
    assert prompts == []


def rewrite_listing(listing: Path, keep) -> None:
    """Rewrite a masks folder's files.txt with the lines keep returns True for, and in
    place of a line, any text keep returns for it."""
    lines = []
    for line in listing.read_text(encoding="utf-8").splitlines():
        kept = keep(line)
        if kept:
            lines.append(line if kept is True else kept)
    listing.write_bytes("".join(f"{line}\n" for line in lines).encode("utf-8"))


def changed_byte(paths) -> None:
    path = paths["--masks"] / "B04-1" / "sam_wheel_masks.npz"
    data = bytearray(path.read_bytes())
    data[-1] ^= 1
    path.write_bytes(bytes(data))


def unlisted_mask(paths) -> None:
    rewrite_listing(
        paths["--masks"] / "files.txt",
        lambda line: not line.endswith("  B02-2/sam_vehicle_masks.npz"),
    )


def bad_digest(paths) -> None:
    rewrite_listing(
        paths["--masks"] / "files.txt",
        lambda line: (
            "x" * 64 + "  B04-1/blurred.jpg"
            if line.endswith("  B04-1/blurred.jpg")
            else True
        ),
    )


MASK_GAPS = {
    "changed byte": (changed_byte, "row 3 masks: hash_mismatch"),
    "used but unlisted": (unlisted_mask, "row 2 masks: unlisted"),
    "bad line": (bad_digest, "row 3 masks: bad_line"),
}


@pytest.mark.parametrize("case", MASK_GAPS.values(), ids=list(MASK_GAPS))
def test_masks_are_verified_before_the_password(data, prompts, capsys, case):
    """S-R29's M2: each masks file to be archived is hashed again against its files.txt
    line, and each one generate reads must be listed, all before the password. A stop
    names the photo's row, never a file."""
    change, expected = case
    paths = final_layout(data)
    change(paths)
    assert run(paths, "--final") == 1
    out, err = capsys.readouterr()
    assert (out, err) == (f"{expected}\n", "")
    printed_nothing_final(out)
    assert nothing_written(paths)
    assert prompts == []


def no_masks_folder(paths) -> None:
    """set_b_masks --final stopped before B04-1, row 3: it has no folder and no line."""
    folder = paths["--masks"] / "B04-1"
    for name in ("blurred.jpg", *generate.MASK_FILES):
        (folder / name).unlink()
    folder.rmdir()
    rewrite_listing(paths["--masks"] / "files.txt", lambda line: "  B04-1/" not in line)


def one_mask_file_gone(paths) -> None:
    """B02-2, row 2, lacks its rim masks, and files.txt lacks their line."""
    (paths["--masks"] / "B02-2" / "sam_wheel_rim_masks.npz").unlink()
    rewrite_listing(
        paths["--masks"] / "files.txt",
        lambda line: not line.endswith("  B02-2/sam_wheel_rim_masks.npz"),
    )


def dropped_car_unmasked(paths) -> None:
    """B06, row 4, is dropped for its 195R14C but has its owner's OK, so set_b_masks
    masks it too; it has no folder and no line."""
    rows = (*FINAL_ROWS[:3], {"car_id": "B06", "tire_code": "195R14C"})
    synth.set_b_cars(paths["--cars"].parent, [synth.car_row(**r) for r in rows])
    folder = paths["--masks"] / "B06-1"
    for name in ("blurred.jpg", *generate.MASK_FILES):
        (folder / name).unlink()
    folder.rmdir()
    rewrite_listing(paths["--masks"] / "files.txt", lambda line: "  B06-1/" not in line)


UNMASKED = {
    "no masks folder": (no_masks_folder, "row 3 masks: missing"),
    "one file gone": (one_mask_file_gone, "row 2 masks: missing"),
    "a dropped car's photo": (dropped_car_unmasked, "row 4 masks: missing"),
}


@pytest.mark.parametrize("case", UNMASKED.values(), ids=list(UNMASKED))
def test_final_photo_without_masks_stops_before_the_password(
    data, prompts, capsys, case
):
    """I-1: a final photo with its owner's OK whose masks folder, or one of its four
    files, isn't there, because set_b_masks --final stopped partway or skipped it, stops
    the run before the password, naming its row, so the sealed set is never short.
    set_b_masks masks each such photo whatever its tire code. The development run
    counts the same gap as no_masks instead (test_drops_are_counted_by_cause)."""
    change, expected = case
    paths = final_layout(data)
    change(paths)
    assert run(paths, "--final") == 1
    out, err = capsys.readouterr()
    assert (out, err) == (f"{expected}\n", "")
    printed_nothing_final(out)
    assert nothing_written(paths)
    assert prompts == []


def dev_unlisted(paths) -> None:
    rewrite_listing(
        paths["--dev-masks"] / "files.txt",
        lambda line: not line.endswith("  B01-1/blurred.jpg"),
    )


def dev_missing(paths) -> None:
    (paths["--dev-masks"] / "B01-1" / "blurred.jpg").unlink()


DEV_GAPS = {
    "unlisted": (dev_unlisted, "dev row 1 masks: unlisted"),
    "missing": (dev_missing, "dev row 1 masks: missing"),
}


@pytest.mark.parametrize("case", DEV_GAPS.values(), ids=list(DEV_GAPS))
def test_dev_masks_must_hold_the_compared_photos(data, prompts, capsys, case):
    """S-R29's M1: each development photo set_b_masks would have masked must be listed
    in --dev-masks' files.txt and there, or the overlap check stops before the
    password, naming the development row."""
    change, expected = case
    paths = final_layout(data)
    change(paths)
    assert run(paths, "--final") == 1
    assert capsys.readouterr() == (f"{expected}\n", "")
    assert nothing_written(paths)
    assert prompts == []


def test_dev_car_without_consent_needs_no_masks(data, prompts):
    """A development car without its owner's OK was never masked, so the overlap check
    doesn't ask for its photo."""
    paths = final_layout(data)
    folder = paths["--dev-cars"].parent
    rows = [synth.car_row(), synth.car_row(car_id="B03"), synth.car_row(car_id="B05")]
    synth.set_b_cars(folder, rows)
    (folder / "b05-ok.png").unlink()
    assert run(paths, "--final") == 0


def same_photo(paths) -> None:
    """Final B02-1's blurred photo holds development B01-1's bytes."""
    dev_photo = (paths["--dev-masks"] / "B01-1" / "blurred.jpg").read_bytes()
    photo_masks(paths["--masks"], "B02-1", photo=dev_photo)


def reencoded_photo(paths) -> None:
    """Final B02-1's blurred photo is development B01-1's, saved again at quality 70."""
    dev_photo = (paths["--dev-masks"] / "B01-1" / "blurred.jpg").read_bytes()
    image = cv2.imdecode(np.frombuffer(dev_photo, np.uint8), cv2.IMREAD_COLOR)
    again = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()
    first, second = photos.photo_facts(dev_photo), photos.photo_facts(again)
    assert first.sha256 != second.sha256
    assert events.near(first.dhash, second.dhash)
    photo_masks(paths["--masks"], "B02-1", photo=again)


def odd_final_car(paths) -> None:
    """The final cars.csv names B03, a development car's odd number, on row 3."""
    rows = [synth.car_row(**cells) for cells in FINAL_ROWS]
    rows[2] |= {"car_id": "B03", "photo_file": "B03-1.jpg"}
    synth.set_b_cars(paths["--cars"].parent, rows)


def final_id_in_dev(paths) -> None:
    """The development cars.csv names B02, a final car, on row 3."""
    rows = [synth.car_row(), synth.car_row(car_id="B03")]
    rows.append(synth.car_row(car_id="B02", photo_file="B02-9.jpg"))
    synth.set_b_cars(paths["--dev-cars"].parent, rows)


OVERLAPS = {
    "identical blurred photo": (same_photo, "overlap: B01"),
    "re-encoded blurred photo": (reencoded_photo, "overlap: B01"),
    "odd final car": (odd_final_car, "row 3 car_id: wrong_side"),
    "final id in the dev cars": (final_id_in_dev, "overlap: dev row 3"),
}


@pytest.mark.parametrize("case", OVERLAPS.values(), ids=list(OVERLAPS))
def test_final_overlap_stops_before_the_password(data, prompts, capsys, case):
    """C214: a final car sharing an id, an identical blurred photo or a near-identical
    one with the development side stops the run, naming a development id or row only,
    before the password and before anything is written."""
    change, expected = case
    paths = final_layout(data)
    change(paths)
    assert run(paths, "--final") == 1
    out, err = capsys.readouterr()
    assert out.splitlines() == [expected]
    assert err == ""
    assert prompts == []
    assert nothing_written(paths)


def test_final_writes_no_plaintext(data, tmp_path, prompts, monkeypatch, capsys):
    """C214: the run adds exactly two files, the archive and the record. The archive
    holds the record, the truth and the crops, cars.csv, the raw photos, each owner's
    OK once (B02's two photos and B04 name one file), and every file the masks'
    files.txt lists. Its truth equals generate's, called directly, apart from split."""
    paths = final_layout(data)
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    paths["--record"] = Path("records", "set-b-final.json")  # relative (S-R13)
    record_path = repo / "records" / "set-b-final.json"
    before = files_under(tmp_path)
    assert run(paths, "--final") == 0
    after = files_under(tmp_path)
    assert after - before == {paths["--archive"], record_path}
    assert before <= after
    assert prompts == PROMPTS
    lines = capsys.readouterr().out.splitlines()
    size, digest = (
        paths["--archive"].stat().st_size,
        table.sha256_file(paths["--archive"]),
    )
    assert lines[:3] == [
        f"archive {size} bytes sha256 {digest}",
        "drops: none",
        "cars=3 photos=4 crops=16 wheels=8 wheels_without_rim=0",
    ]
    assert len(lines) == 4

    out = tmp_path / "x"
    names = extract(paths["--archive"], out)
    _, direct = generated(paths, side="final")
    listing = (paths["--masks"] / "files.txt").read_text(encoding="utf-8")
    masks = [line.split("  ", 1)[1] for line in listing.splitlines()]
    raw = ["B02-1.jpg", "B02-2.jpg", "B04-1.jpg", "B06-1.jpg"]
    assert names == [
        "records/set_b_final.json",
        "set_b/truth.csv",
        *[f"set_b/crops/{crop.plan.crop_id}.jpg" for crop in direct.crops],
        "set_b/source/cars.csv",
        *[f"set_b/source/photos/{name}" for name in raw],
        "set_b/source/owner.png",
        "set_b/source/b06-ok.png",
        *[f"set_b/source/masks/{name}" for name in masks],
        "set_b/source/masks/files.txt",
    ]
    assert len(direct.crops) == 16
    assert rows_of(out / "set_b" / "truth.csv") == [
        row | {"split": "sealed"} for row in direct.rows
    ]
    for crop in direct.crops:
        member = out / "set_b" / "crops" / f"{crop.plan.crop_id}.jpg"
        assert member.read_bytes() == jpeg_95(crop.image)
    source = out / "set_b" / "source"
    folder = paths["--cars"].parent
    assert (source / "cars.csv").read_bytes() == paths["--cars"].read_bytes()
    for name in raw:
        assert (source / "photos" / name).read_bytes() == (
            folder / "photos" / name
        ).read_bytes()
    for name in ("owner.png", "b06-ok.png"):
        assert (source / name).read_bytes() == (folder / name).read_bytes()
    for name in masks:
        assert (source / "masks" / name).read_bytes() == (
            paths["--masks"] / name
        ).read_bytes()
    record = json.loads(record_path.read_bytes().decode("ascii"))
    archived = json.loads((out / "records" / "set_b_final.json").read_bytes())
    assert record == archived | {
        "archive": {"file": "lusot-sealed-set-b.7z", "size": size, "sha256": digest}
    }
    # Every photo's masks are archived here, so the archived files.txt is the whole
    # listing, and the record's hash can be checked from the archive (S-R29's M2).
    archived_listing = (source / "masks" / "files.txt").read_bytes()
    assert archived_listing == (paths["--masks"] / "files.txt").read_bytes()
    assert record["inputs"] == {
        "cars": table.sha256_file(paths["--cars"]),
        "masks_files": table.sha256_bytes(archived_listing),
        "dev_cars": table.sha256_file(paths["--dev-cars"]),
    }
    assert record["overlap_check"] == "PASS"
    assert (record["generator_version"], record["generator_seed"]) == (
        "set-b-gen-v1",
        20261029,
    )


def test_final_car_without_consent_leaves_only_its_row(data, tmp_path, prompts):
    """C218, S-R29's I1: a final car without its owner's OK is dropped as no_consent,
    and nothing of it but its row in cars.csv reaches the archive: no crop, raw photo,
    OK or mask, though files.txt still lists the masks an earlier run made while its OK
    stood. Nor do the masks of B08, which isn't in cars.csv at all; its blurred photo,
    deleted but still listed, is never looked for."""
    paths = final_layout(data)
    (paths["--cars"].parent / "b06-ok.png").unlink()
    photo_masks(paths["--masks"], "B08-1")
    (paths["--masks"] / "B08-1" / "blurred.jpg").unlink()
    assert run(paths, "--final") == 0
    out = tmp_path / "x"
    names = extract(paths["--archive"], out)
    assert [name for name in names if re.search("B0[68]", name)] == []
    assert "set_b/source/b06-ok.png" not in names
    archived_listing = (out / "set_b" / "source" / "masks" / "files.txt").read_bytes()
    listed = [line.split("  ", 1)[1] for line in archived_listing.decode().splitlines()]
    assert listed == [
        name.removeprefix("set_b/source/masks/")
        for name in names
        if name.startswith("set_b/source/masks/") and not name.endswith("files.txt")
    ]
    assert {name.split("/")[0] for name in listed} == {"B02-1", "B02-2", "B04-1"}
    record = json.loads(paths["--record"].read_bytes().decode("ascii"))
    assert record["inputs"]["masks_files"] == table.sha256_bytes(archived_listing)
    assert record["counts"]["drops"] == {"no_consent": 1}
    assert record["counts"]["cars"] == 2


def test_audit_sealed_passes_on_the_final_cars_it_wrote(data, prompts):
    """C220: the sealed run's audit, on the archive extracted where Rene extracts it,
    beside a development run. B06 is dropped (195R14C), so counts.cars leaves it out,
    as the truth does (addition 1)."""
    rows = (*FINAL_ROWS[:3], {"car_id": "B06", "tire_code": "195R14C"})
    paths = final_layout(data, rows)
    dev = {"--cars": paths["--dev-cars"], "--masks": paths["--dev-masks"]}
    assert run(dev | {"--out": data / "set_b" / "dev" / "generated"}) == 0
    assert run(paths, "--final") == 0
    record = json.loads(paths["--record"].read_bytes().decode("ascii"))
    assert record["counts"]["cars"] == 2
    assert record["counts"]["drops"] == {"no_aspect_ratio": 1}
    run_dir = data / "sealed" / "run-1"
    extract(paths["--archive"], run_dir)
    assert audit.audit_sealed(run_dir, data, [paths["--record"]]) == []
    archive = bytearray(paths["--archive"].read_bytes())
    archive[len(archive) // 2] ^= 1
    paths["--archive"].write_bytes(bytes(archive))
    assert audit.audit_sealed(run_dir, data, [paths["--record"]]) == [
        "archive_hash lusot-sealed-set-b.7z"
    ]


# What --final may never print (addition 6): a final car's id, a model, a tire code, a
# file name or a path.
NEVER_PRINTED = ("Toyota", "Vios", "175/65R14", "205/55R16", "195R14C", ".jpg", ".png")
NEVER_PRINTED += ("owner", "sealed", "set_b", "data")


def printed_nothing_final(text: str) -> None:
    assert re.search(r"B0[246]", text) is None
    for word in NEVER_PRINTED:
        assert word not in text


def test_final_prints_no_final_car_id(data, prompts, capsys):
    """C202, addition 6: a run with a drop and a warning, then one with a problem,
    prints rows and counts only."""
    rows = list(FINAL_ROWS)
    rows[2] = rows[2] | {"consent_version": "SETB-v0"}
    rows[3] = {"car_id": "B06", "tire_code": "195R14C"}
    paths = final_layout(data, rows)
    assert run(paths, "--final") == 0
    out, err = capsys.readouterr()
    lines = out.splitlines()
    assert lines[0] == "row 3 consent_version=unapproved"
    assert lines[1].startswith("archive ")
    assert lines[2:4] == [
        "drops: no_aspect_ratio=1",
        "cars=2 photos=3 crops=12 wheels=6 wheels_without_rim=0",
    ]
    printed_nothing_final(out + err)
    record = json.loads(paths["--record"].read_bytes().decode("ascii"))
    assert record["counts"]["warnings"] == {"consent_version=unapproved": 1}

    paths["--archive"].unlink()
    paths["--record"].unlink()
    rows[2] = rows[2] | {"view": "front"}
    synth.set_b_cars(paths["--cars"].parent, [synth.car_row(**r) for r in rows])
    assert run(paths, "--final") == 1
    out, err = capsys.readouterr()
    assert (out, err) == (
        "row 3 view: not_in_list\nrow 3 consent_version=unapproved\n",
        "",
    )
    printed_nothing_final(out + err)
    assert nothing_written(paths)
    assert prompts == PROMPTS  # the first run's only


def test_final_record_holds_no_ids(data, prompts):
    paths = final_layout(data)
    assert run(paths, "--final") == 0
    text = paths["--record"].read_text(encoding="ascii")
    assert record_io.ID_TOKEN.search(text) is None
    for word in ("B01", "B02", "B03", "B04", "B06", "Vios", "175/65R14", ".jpg"):
        assert word not in text
    record = json.loads(text)
    assert record["counts"] == {
        "cars": 3,
        "photos": 4,
        "crops": 16,
        "wheels": 8,
        "wheels_without_rim": 0,
        "drops": {},
        "warnings": {},
        "band": {"below_gutter": 4, "gutter": 4, "half_knee": 4, "half_tire": 4},
        "size_bin": {"full": 8, "small": 8},
        "vehicle_type": {"sedan_hatch": 12, "suv_mpv": 4},
        "view": {"side": 12, "angled": 4},
    }


def test_record_refusal_stops_before_the_password(data, prompts, monkeypatch, capsys):
    """Addition 1 (S-R16): a record that would hold an id-shaped token, here a count
    keyed by B02, is refused before the password, so no archive or record exists."""
    build = record_io.set_b_final_record

    def with_an_id(**kwargs):
        return build(**kwargs | {"counts": kwargs["counts"] | {"B02": 1}})

    monkeypatch.setattr(record_io, "set_b_final_record", with_an_id)
    paths = final_layout(data)
    assert run(paths, "--final") == 1
    assert capsys.readouterr() == ("the record holds an id-shaped token\n", "")
    assert nothing_written(paths)
    assert prompts == []


def test_archive_hash_prints_before_the_record(data, prompts, monkeypatch, capsys):
    """S-R29's M4: the archive's size and SHA-256 print as soon as it is written, so a
    record write that fails still leaves Rene its hash."""

    def fails(path, record):
        raise OSError("the record can't be written")

    monkeypatch.setattr(record_io, "write_record", fails)
    paths = final_layout(data)
    assert run(paths, "--final") == 1
    size, digest = (
        paths["--archive"].stat().st_size,
        table.sha256_file(paths["--archive"]),
    )
    assert capsys.readouterr() == (
        f"archive {size} bytes sha256 {digest}\n",
        "stopped: OSError\n",
    )
    assert not paths["--record"].exists()


def test_password_mismatch_writes_nothing(data, prompts, monkeypatch, capsys):
    paths = final_layout(data)
    synth.typed(monkeypatch, synth.TEST_PHRASE, "another phrase")
    assert run(paths, "--final") == 2
    assert capsys.readouterr().err.endswith(
        "refused: the two entries differ; nothing was written\n"
    )
    assert nothing_written(paths)


def test_final_error_names_no_photo(data, prompts, monkeypatch, capsys):
    def fails(*args, **kwargs):
        raise OSError("B02-1.jpg can't be read")

    monkeypatch.setattr(generate, "generate", fails)
    paths = final_layout(data)
    assert run(paths, "--final") == 1
    assert capsys.readouterr() == ("", "stopped: OSError\n")
    assert nothing_written(paths)
    assert prompts == []


@pytest.mark.parametrize(
    "extra",
    [
        [],  # neither --out nor --final
        ["--out", "C:/out", "--archive", "C:/sealed/a.7z"],
        ["--final", "--out", "C:/out", "--dev-cars", "a", "--dev-masks", "b"],
        ["--final", "--dev-cars", "a", "--dev-masks", "b", "--archive", "c.7z"],
    ],
)
def test_flags_must_match_the_mode(extra, capsys):
    with pytest.raises(SystemExit) as stop:
        generate.main(["--cars", "C:/cars.csv", "--masks", "C:/masks", *extra])
    assert stop.value.code == 2
    assert capsys.readouterr().out == ""


def declare_size(data: bytes, width: int, height: int) -> bytes:
    """Rewrite a baseline JPEG's frame header (SOF0) so it declares another size.

    Copied from eval/data/tests/test_photos.py, which copied MS1's (R25).
    """
    i = 2  # after the start-of-image marker
    while data[i + 1] != 0xC0:
        i += 2 + int.from_bytes(data[i + 2 : i + 4], "big")
    size = height.to_bytes(2, "big") + width.to_bytes(2, "big")
    return data[: i + 5] + size + data[i + 9 :]


# For a fresh interpreter: the cap after `import generate`, whether photos loaded
# before crops and water, and whether cv2 decodes the bytes on stdin. sys.modules
# keeps the order modules finished loading in, so cv2, which photos loads, comes before
# photos, and crops and water after it only when generate imported them after photos.
FIRST = """\
import os, sys
import generate
import cv2
import numpy as np
names = list(sys.modules)
print(os.environ["OPENCV_IO_MAX_IMAGE_PIXELS"])
print(all(names.index("photos") < names.index(n) for n in ("crops", "water")))
data = np.frombuffer(sys.stdin.buffer.read(), np.uint8)
try:
    decoded = cv2.imdecode(data, cv2.IMREAD_COLOR) is not None
except cv2.error:
    decoded = False
print(decoded)
"""


def test_generate_loads_photos_first():
    """Addition 9 (R25): generate imports photos, which sets OpenCV's 50 MP cap, before
    crops, water or cv2 load, so a JPEG declaring 60 MP doesn't decode. The variable is
    removed from the child's environment, so the cap must come from generate's own
    imports."""
    huge = declare_size(synth.jpeg(0, (16, 16)), 10_000, 6_000)
    env = {k: v for k, v in os.environ.items() if k != "OPENCV_IO_MAX_IMAGE_PIXELS"}
    env["PYTHONPATH"] = str(SET_B)
    done = subprocess.run(
        [sys.executable, "-c", FIRST],
        input=huge,
        capture_output=True,
        env=env,
        timeout=synth.TIMEOUT,
        check=True,
    )
    assert done.stdout.decode().split() == ["50000000", "True", "False"]


def test_generate_help_exits_0():
    done = subprocess.run(
        [sys.executable, str(GENERATE), "--help"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stderr) == (0, "")
    for flag in ("--final", "--out", *FINAL_FLAGS):
        assert flag in done.stdout
