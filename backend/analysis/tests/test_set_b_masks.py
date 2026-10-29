"""Tests for set_b_masks, Set B's face-blurred SAM masks (spec §5.6; C200, C210, C213,
C218, C222).

FakeClient stands in for Meta: it records each image and phrase and answers with
synthetic instances, so no test touches the network. MODEL_API_KEY is removed for every
test, so a real client could only raise MissingApiKey. The photos are synthetic JPEGs
over 32 px on each side, since blur_for_meta refuses smaller ones, and the sealed paths
are folders under tmp_path.
"""

import ast
import builtins
import csv
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from lusot_analysis.face_blur import FACE_BLUR_VERSION, BlurredImage
from lusot_analysis.meta_client import (
    MetaApiError,
    MissingApiKey,
    SamInstance,
    SamResult,
)

PROBE = Path(__file__).parents[1] / "probes" / "set_b_masks.py"
TIMEOUT = 120  # seconds a subprocess may run, so a stray prompt fails instead of hangs

# eval/data/formats.py's columns, written out: backend/analysis can't import eval/.
CARS_COLUMNS = (
    "car_id",
    "photo_file",
    "model",
    "vehicle_type",
    "tire_code",
    "view",
    "taken_on",
    "consent_file",
    "consent_version",
    "notes",
)
TRUTH_COLUMNS = (
    "crop_id",
    "car_id",
    "split",
    "photo_file",
    "crop_file",
    "wheel",
    "view",
    "vehicle_type",
    "tire_code",
    "rim_in",
    "diameter_in",
    "crop_scale",
    "size_bin",
    "x0",
    "y0",
    "x1",
    "y1",
    "ground_row",
    "top_row",
    "px_per_in",
    "waterline_left_row",
    "waterline_right_row",
    "waterline_row",
    "true_depth_in",
    "band",
    "rim_edge_ratio",
    "generator_version",
)
CAR_FACTS = {
    "model": "Vios",
    "vehicle_type": "sedan_hatch",
    "tire_code": "185/60R15",
    "view": "side",
    "taken_on": "2026-10-29",
    "consent_version": "v1",
}
# What each photo's folder holds, in the order the probe writes it, meta.json last.
PHOTO_FILES = [
    "blurred.jpg",
    "sam_vehicle.txt",
    "sam_vehicle_masks.npz",
    "sam_wheel.txt",
    "sam_wheel_masks.npz",
    "sam_wheel_rim.txt",
    "sam_wheel_rim_masks.npz",
    "meta.json",
]
INSTANCES = {"vehicle": 1, "wheel": 2, "wheel rim": 2, "floodwater": 1}
OLD_NS = 1_000_000_000 * 1_000_000_000  # Sep 9, 2001, as nanoseconds since 1970
CONSOLE_REFUSAL = "refused: run this yourself, in a Windows PowerShell window\n"
SEALED_REFUSAL = "refused: path inside a folder named sealed\n"


def load_probe():
    spec = importlib.util.spec_from_file_location("set_b_masks", PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = load_probe()

# The same load, in a fresh interpreter.
LOAD = (
    "import importlib.util, sys\n"
    f"spec = importlib.util.spec_from_file_location('set_b_masks', {str(PROBE)!r})\n"
    "probe = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(probe)\n"
)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)


class FakeClient:
    """Stands in for MetaClient. It records each (image, phrase) it is sent and answers
    with INSTANCES[phrase] small boxes on that image, the second without a score. With
    fail_on=n, the nth call raises MetaApiError("x", status=503) instead."""

    def __init__(self, fail_on: int | None = None) -> None:
        self.sent: list[tuple[BlurredImage, str]] = []
        self.results: list[SamResult] = []
        self.fail_on = fail_on

    def segment(self, image: BlurredImage, phrase: str) -> SamResult:
        self.sent.append((image, phrase))
        if len(self.sent) == self.fail_on:
            raise MetaApiError("x", status=503)
        instances = []
        for n in range(INSTANCES[phrase]):
            mask = np.zeros((image.height, image.width), bool)
            mask[2:7, 4 * n : 4 * n + 3] = True
            box = (4.0 * n, 2.0, 4.0 * n + 3, 7.0)
            instances.append(SamInstance(n + 1, box, mask, None if n == 1 else 0.9))
        result = SamResult(phrase, instances, 0.25, f"raw {phrase}\n")
        self.results.append(result)
        return result


def sizes(client: FakeClient) -> list[tuple[int, int]]:
    """The (height, width) of each image the client was sent, in order."""
    return [(image.height, image.width) for image, _ in client.sent]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def jpeg(seed: int, size: tuple[int, int]) -> bytes:
    """A JPEG of seeded random colour blocks. size is (height, width)."""
    rng = np.random.default_rng(seed)
    blocks = rng.integers(0, 256, size=(6, 8, 3), dtype=np.uint8)
    image = cv2.resize(blocks, (size[1], size[0]), interpolation=cv2.INTER_NEAREST)
    return cv2.imencode(".jpg", image)[1].tobytes()


def write_csv(path: Path, columns, rows) -> Path:
    """The rows as the tools write a CSV: UTF-8, no BOM, LF endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, columns, restval="", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def car_set(folder: Path, rows, *, sizes=None, data=None) -> Path:
    """Write folder/cars.csv, one row per (car_id, photo_file, consent_file), and return
    it. Each photo goes in folder/photos: a JPEG of its size in sizes (120 x 160 by
    default), or its bytes in data. Each consent file is written beside cars.csv, unless
    its name holds "missing"."""
    sizes, data = sizes or {}, data or {}
    (folder / "photos").mkdir(parents=True)
    cells = []
    for seed, (car, photo, consent) in enumerate(rows):
        made = (
            data[photo] if photo in data else jpeg(seed, sizes.get(photo, (120, 160)))
        )
        (folder / "photos" / photo).write_bytes(made)
        if consent and "missing" not in consent:
            (folder / consent).write_text("the owner's OK\n", encoding="utf-8")
        cells.append(
            {"car_id": car, "photo_file": photo, "consent_file": consent, **CAR_FACTS}
        )
    return write_csv(folder / "cars.csv", CARS_COLUMNS, cells)


def truth_rows(crops, version: str) -> list[dict[str, str]]:
    """Two wheel rows per crop id, as the generator writes truth.csv."""
    return [
        {
            "crop_id": crop,
            "car_id": crop[:3],
            "split": "dev",
            "photo_file": crop[:5] + ".jpg",
            "crop_file": crop + ".jpg",
            "wheel": wheel,
            "generator_version": version,
        }
        for crop in crops
        for wheel in ("1", "2")
    ]


def crop_set(folder: Path, crops, *, version: str = "g1") -> Path:
    """Write each crop in folder/crops and folder/truth.csv, and return truth.csv."""
    (folder / "crops").mkdir(parents=True)
    for seed, crop in enumerate(crops):
        (folder / "crops" / f"{crop}.jpg").write_bytes(jpeg(100 + seed, (96, 128)))
    return write_csv(folder / "truth.csv", TRUTH_COLUMNS, truth_rows(crops, version))


def dev_argv(cars: Path, out: Path) -> list:
    return ["--cars", cars, "--photos", cars.parent / "photos", "--out", out]


def run(argv, client) -> int:
    """main's exit code with this client, whether returned or raised as SystemExit."""
    try:
        return probe.main([str(arg) for arg in argv], make_client=lambda: client)
    except SystemExit as stop:
        return stop.code


def typed(monkeypatch, *answers: str) -> None:
    """Answer each input prompt with the next answer, in order."""
    replies = iter(answers)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(replies))


def as_rene(monkeypatch, *answers: str) -> None:
    """Rene's own console, and his answers to the prompts."""
    monkeypatch.setattr(probe, "console_ok", lambda **_: True)
    typed(monkeypatch, *answers)


def snapshot(folder: Path) -> dict[str, tuple[bytes, int]]:
    """Every file under folder, with its bytes and modification time."""
    return {
        path.relative_to(folder).as_posix(): (
            path.read_bytes(),
            path.stat().st_mtime_ns,
        )
        for path in folder.rglob("*")
        if path.is_file()
    }


def backdate(*paths: Path) -> None:
    """Set each file's times back to 2001, so a rewrite shows in its modification time
    even within one tick of the Windows clock."""
    for path in paths:
        os.utime(path, ns=(OLD_NS, OLD_NS))


def listed(out: Path) -> bytes:
    """files.txt as it should read: every other file under out, with its SHA-256,
    sorted by path."""
    paths = sorted(
        (path.relative_to(out).as_posix(), path)
        for path in out.rglob("*")
        if path.is_file() and path != out / "files.txt"
    )
    lines = [f"{sha256(path.read_bytes())}  {name}\n" for name, path in paths]
    return "".join(lines).encode("utf-8")


# The copied guards, tested as eval/data/tests/test_guards.py tests their source.

SEALED_PATHS = [
    ("sealed", "x.csv"),
    ("a", "Sealed", "x.csv"),
    ("SEALED",),
    ("sealed", "sub", "..", "x.csv"),
    ("x", "sealed", "..", "y.csv"),  # refused as given, although it normalises outside
    ("sealed.", "x.csv"),
    pytest.param(
        ("sealed::$INDEX_ALLOCATION", "x.csv"),
        marks=pytest.mark.skipif(sys.platform != "win32", reason="an NTFS stream name"),
    ),
]


@pytest.mark.parametrize("parts", SEALED_PATHS)
def test_copied_refuse_sealed(tmp_path, capsys, parts):
    with pytest.raises(SystemExit) as stop:
        probe.refuse_sealed(tmp_path.joinpath(*parts))
    assert stop.value.code == 2
    assert capsys.readouterr().err == SEALED_REFUSAL


@pytest.mark.skipif(sys.platform != "win32", reason="a drive-relative path")
def test_copied_refuse_sealed_resolves_a_drive_relative_path(capsys):
    # As given, C:sealed\x.csv splits into "C:sealed", whose name before ":" is C. Only
    # its absolute form, under the current folder, names sealed. Nothing is created.
    with pytest.raises(SystemExit) as stop:
        probe.refuse_sealed(os.path.splitdrive(os.getcwd())[0] + "sealed\\x.csv")
    assert stop.value.code == 2
    assert capsys.readouterr().err == SEALED_REFUSAL


def test_copied_refuse_sealed_lets_other_names_pass(tmp_path):
    probe.refuse_sealed(
        tmp_path / "unsealed" / "x.csv",
        tmp_path / "sealed.csv",
        tmp_path / "sealed_notes" / "x",
    )


@pytest.mark.parametrize(
    ("name", "sealed"),
    [
        ("sealed", True),
        ("Sealed", True),
        ("SEALED", True),
        ("sealed.", True),
        ("sealed ", True),
        ("sealed::$INDEX_ALLOCATION", True),
        ("unsealed", False),
        ("sealed.csv", False),
        ("sealed_notes", False),
        ("", False),
    ],
)
def test_copied_is_sealed_name(name, sealed):
    assert probe.is_sealed_name(name) is sealed


def test_copied_require_sealed(tmp_path, capsys):
    probe.require_sealed(tmp_path / "sealed" / "cars.csv", flag="--cars")
    probe.require_sealed(tmp_path / "sealed", flag="--photos")  # the folder itself
    for outside in (tmp_path / "cars.csv", tmp_path / "sealed" / ".." / "cars.csv"):
        with pytest.raises(SystemExit) as stop:
            probe.require_sealed(outside, flag="--cars")
        assert stop.value.code == 2
        assert capsys.readouterr().err == (
            "refused: --cars must be inside a folder named sealed\n"
        )


def test_copied_console_needs_both_handles():
    assert probe.console_ok(is_console=lambda fd: fd in (0, 1)) is True
    assert probe.console_ok(is_console=lambda fd: fd == 0) is False  # stdout piped
    assert probe.console_ok(is_console=lambda fd: fd == 1) is False


def test_copied_console_check_on_nul():
    piped = subprocess.run(
        [sys.executable, "-c", LOAD + "sys.exit(0 if probe.console_ok() else 3)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        timeout=TIMEOUT,
        check=False,
    )
    assert piped.returncode == 3
    if sys.platform == "win32":
        # C412's trap: NUL is a character device, so isatty calls it a terminal.
        trap = subprocess.run(
            [
                sys.executable,
                "-c",
                "import os, sys; sys.exit(0 if os.isatty(0) else 3)",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            timeout=TIMEOUT,
            check=False,
        )
        assert trap.returncode == 0


def test_copied_require_console_message(monkeypatch, capsys):
    monkeypatch.setattr(probe, "console_ok", lambda **_: True)
    probe.require_console()
    monkeypatch.setattr(probe, "console_ok", lambda **_: False)
    with pytest.raises(SystemExit) as stop:
        probe.require_console()
    assert stop.value.code == 2
    assert capsys.readouterr().err == CONSOLE_REFUSAL


def test_copied_confirm_needs_yes(monkeypatch, capsys):
    for answer in ("yes", " yes "):
        typed(monkeypatch, answer)
        probe.confirm("planned photos=1")
        assert capsys.readouterr().out == "planned photos=1\n"

    prompts = []

    def record(prompt):
        prompts.append(prompt)
        return "yes"

    probe.confirm("planned photos=1", ask=record)
    assert prompts == ["Type yes to continue: "]

    for answer in ("y", ""):
        typed(monkeypatch, answer)
        with pytest.raises(SystemExit) as stop:
            probe.confirm("planned photos=1")
        assert stop.value.code == 2
        assert capsys.readouterr().err == "stopped: nothing was done\n"


def test_copied_quiet_prints_the_class_only(capsys):
    assert probe.quiet(lambda: 0) == 0

    def fails():
        raise ValueError("B02-1.jpg")

    assert probe.quiet(fails) == 1
    err = capsys.readouterr().err
    assert err == "stopped: ValueError\n"
    assert "B02" not in err

    def interrupted():
        raise KeyboardInterrupt

    assert probe.quiet(interrupted) == 1
    assert capsys.readouterr().err == "stopped: KeyboardInterrupt\n"

    def refuses():
        raise SystemExit(2)

    with pytest.raises(SystemExit) as stop:
        probe.quiet(refuses)
    assert stop.value.code == 2


# The masks.


def test_masks_every_photo_with_three_phrases(tmp_path, capsys):
    folder = tmp_path / "set_b" / "dev"
    cars = car_set(
        folder,
        [("B01", "B01-1.jpg", "B01.txt"), ("B03", "B03-1.jpg", "B03.txt")],
        sizes={"B03-1.jpg": (90, 150)},
    )
    out = folder / "masks"
    fake = FakeClient()
    assert run(dev_argv(cars, out), fake) == 0
    assert [phrase for _, phrase in fake.sent] == list(probe.PHRASES) * 2
    assert probe.PHRASES == ("vehicle", "wheel", "wheel rim")
    for n, stem in enumerate(("B01-1", "B03-1")):
        photo = out / stem
        assert sorted(path.name for path in photo.iterdir()) == sorted(PHOTO_FILES)
        image = fake.sent[3 * n][0]
        assert (photo / "blurred.jpg").read_bytes() == image.jpeg
        for result in fake.results[3 * n : 3 * n + 3]:
            name = "sam_" + result.phrase.replace(" ", "_")
            # The raw text byte for byte (R11): no CRLF on Windows.
            assert (photo / f"{name}.txt").read_bytes() == result.raw.encode("utf-8")
            found = result.instances
            with np.load(photo / f"{name}_masks.npz") as saved:
                assert saved["ids"].tolist() == [i.id for i in found]
                assert saved["boxes"].tolist() == [list(i.box) for i in found]
                np.testing.assert_array_equal(
                    saved["scores"],
                    [np.nan if i.score is None else i.score for i in found],
                )
                assert saved["masks"].dtype == bool
                assert saved["masks"].shape == (len(found), image.height, image.width)
                assert np.array_equal(saved["masks"], [i.mask for i in found])
        meta = {
            "blur_version": FACE_BLUR_VERSION,
            "faces": image.faces,
            "files": PHOTO_FILES[:-1],
            "height": image.height,
            "instances": {"vehicle": 1, "wheel": 2, "wheel rim": 2},
            "seconds": {"vehicle": 0.25, "wheel": 0.25, "wheel rim": 0.25},
            "width": image.width,
        }
        text = json.dumps(meta, indent=2, sort_keys=True) + "\n"
        assert (photo / "meta.json").read_bytes() == text.encode("ascii")
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "planned photos=2 sam_calls=6 cost=$0.0150"
    assert re.fullmatch(r"photos=2 skipped=0 sam_calls=6 seconds=[0-9.]+", lines[-1])


def test_every_image_sent_is_blurred_first(tmp_path, monkeypatch):
    made = []
    real = probe.blur_for_meta

    def spy(data, **options):
        image = real(data, **options)
        made.append(image)
        return image

    monkeypatch.setattr(probe, "blur_for_meta", spy)
    folder = tmp_path / "set_b" / "dev"
    cars = car_set(
        folder, [("B01", "B01-1.jpg", "B01.txt")], sizes={"B01-1.jpg": (1800, 2400)}
    )
    truth = crop_set(folder / "generated", ["B01-1-1"])
    fake = FakeClient()
    assert run(dev_argv(cars, folder / "masks"), fake) == 0
    assert run(["--water", truth, "--out", folder / "masks"], fake) == 0
    assert len(fake.sent) == 4  # a crop's floodwater call too (C37)
    for image, _ in fake.sent:
        assert type(image) is BlurredImage
        assert any(image is blurred for blurred in made)
        assert max(image.width, image.height) <= 1600
    assert sizes(fake)[0] == (1200, 1600)


def test_cars_without_consent_are_never_sent(tmp_path, capsys):
    folder = tmp_path / "set_b" / "dev"
    cars = car_set(
        folder,
        [
            ("B01", "B01-1.jpg", "B01.txt"),
            ("B03", "B03-1.jpg", ""),
            ("B05", "B05-1.jpg", "B05-missing.txt"),
        ],
        sizes={"B03-1.jpg": (90, 150), "B05-1.jpg": (100, 140)},
    )
    out = folder / "masks"
    fake = FakeClient()
    assert run(dev_argv(cars, out), fake) == 0
    assert sizes(fake) == [(120, 160)] * 3
    lines = capsys.readouterr().out.splitlines()
    assert lines[:2] == ["B03 skipped: no_consent", "B05 skipped: no_consent"]
    assert not (out / "B03-1").exists() and not (out / "B05-1").exists()


def test_wrong_side_cars_are_never_sent(tmp_path, monkeypatch, capsys):
    dev = tmp_path / "set_b" / "dev"
    cars = car_set(
        dev,
        [("B01", "B01-1.jpg", "B01.txt"), ("B02", "B02-1.jpg", "B02.txt")],
        sizes={"B02-1.jpg": (90, 150)},
    )
    fake = FakeClient()
    assert run(dev_argv(cars, dev / "masks"), fake) == 0
    assert sizes(fake) == [(120, 160)] * 3
    assert capsys.readouterr().out.splitlines()[0] == "B02 skipped: wrong_side"

    sealed = tmp_path / "set_b" / "sealed"
    cars = car_set(
        sealed,
        [("B02", "B02-1.jpg", "B02.txt"), ("B03", "B03-1.jpg", "B03.txt")],
        sizes={"B03-1.jpg": (90, 150)},
    )
    as_rene(monkeypatch, "yes")
    fake = FakeClient()
    assert run(["--final", *dev_argv(cars, sealed / "masks")], fake) == 0
    assert sizes(fake) == [(120, 160)] * 3
    captured = capsys.readouterr()
    assert captured.out.splitlines()[0] == "row 2 skipped: wrong_side"
    assert re.search(r"[Bb][0-9]{2}", captured.out + captured.err) is None


def test_check_cars_keys_final_skips_by_row(tmp_path):
    cars = car_set(
        tmp_path,
        [
            ("B01", "B01-1.jpg", "B01.txt"),
            ("B01", "B01-2.jpg", "B01.txt"),
            ("B02", "B02-1.jpg", "B02.txt"),
            ("B03", "B03-1.jpg", ""),
            ("B04", "B04-1.jpg", "B04.txt"),
            ("B04", "B04-2.jpg", ""),  # one row without the OK holds the whole car
        ],
    )
    dev = (
        ["B01-1.jpg", "B01-2.jpg"],
        {"B02": "wrong_side", "B03": "no_consent", "B04": "wrong_side"},
    )
    final = (
        ["B02-1.jpg"],
        {
            "row 1": "wrong_side",
            "row 2": "wrong_side",
            "row 4": "wrong_side",
            "row 5": "no_consent",
            "row 6": "no_consent",
        },
    )
    assert probe.check_cars(cars, final=False) == dev
    assert probe.check_cars(cars, final=True) == final
    # A log saved from a spreadsheet, with a BOM and CRLF endings, reads the same.
    cars.write_bytes(b"\xef\xbb\xbf" + cars.read_bytes().replace(b"\n", b"\r\n"))
    assert probe.check_cars(cars, final=True) == final


def test_bad_rows_exit_1_naming_the_row(tmp_path, capsys):
    folder = tmp_path / "set_b" / "dev"
    cars = car_set(
        folder,
        [
            ("B01", "B01-1.jpg", "B01.txt"),
            ("Espana", "B01-2.jpg", "B01.txt"),
            ("B03", "B03-1.gif", "B03.txt"),
            ("B05", "B07-1.jpg", "B05.txt"),  # another car's photo
            ("B09", "b09-1.JPG", "B09.txt"),  # any case is fine
        ],
    )
    fake = FakeClient()
    assert run(dev_argv(cars, folder / "masks"), fake) == 1
    assert capsys.readouterr().out.splitlines() == [
        "row 2 car_id: bad_id",
        "row 3 photo_file: id_file_mismatch",
        "row 4 photo_file: id_file_mismatch",
    ]
    assert fake.sent == []


def test_malformed_cars_csv_exits_1(tmp_path, capsys):
    cars = tmp_path / "cars.csv"
    argv = dev_argv(cars, tmp_path / "masks")
    cars.write_text("car_id,photo_file\nB01,B01-1.jpg\n", encoding="utf-8")
    assert run(argv, FakeClient()) == 1
    assert capsys.readouterr().out == "log consent_file: missing_column\n"
    # The blank row keeps its number, as in Rene's spreadsheet.
    cars.write_text(
        "car_id,photo_file,consent_file\nB01,B01-1.jpg,B01.txt\n,,\nB03,B03-1.jpg\n",
        encoding="utf-8",
    )
    assert run(argv, FakeClient()) == 1
    assert capsys.readouterr().out == "row 3 cells: too_few\n"


def test_a_photo_named_twice_is_refused_before_any_call(tmp_path, capsys):
    # A photo's masks are filed by its stem. A photo named twice would be paid for
    # twice, and two photos with one stem would overwrite each other's masks.
    folder = tmp_path / "set_b" / "dev"
    cars = car_set(
        folder,
        [
            ("B01", "B01-1.jpg", "B01.txt"),
            ("B01", "B01-1.jpg", "B01.txt"),  # the same row twice
            ("B03", "B03-1.jpg", "B03.txt"),
            ("B03", "B03-1.png", "B03.txt"),  # two files, one stem
            ("B05", "B05-1.jpg", "B05.txt"),
            ("B05", "b05-1.jpg", "B05.txt"),  # one file on NTFS
        ],
    )
    fake = FakeClient()
    assert run(dev_argv(cars, folder / "masks"), fake) == 1
    assert capsys.readouterr().out.splitlines() == [
        "row 2 photo_file: duplicate",
        "row 4 photo_file: duplicate",
        "row 6 photo_file: duplicate",
    ]
    assert fake.sent == []
    assert not (folder / "masks").exists()


def test_consent_file_must_be_a_bare_name_beside_cars_csv(tmp_path, capsys):
    # Any existing file used to pass the stat: cars.csv itself, or a photo.
    folder = tmp_path / "set_b" / "dev"
    cars = car_set(
        folder,
        [
            ("B01", "B01-1.jpg", "B01.txt"),
            ("B03", "B03-1.jpg", "cars.csv"),
            ("B05", "B05-1.jpg", "photos/B05-1.jpg"),
        ],
    )
    fake = FakeClient()
    assert run(dev_argv(cars, folder / "masks"), fake) == 1
    assert capsys.readouterr().out.splitlines() == [
        "row 2 consent_file: bad_name",
        "row 3 consent_file: bad_name",
    ]
    assert fake.sent == []


@pytest.mark.parametrize(
    "consent",
    ["cars.csv::$DATA", "B01.txt:x", "C:B01.txt", "..", "oks\\B01.txt", "oks/B01.txt"],
)
def test_consent_file_is_named_as_the_generator_takes_it(tmp_path, capsys, consent):
    # eval/set_b/cars.py's bare_name: no "/", "\" or ":" (a drive, or an NTFS stream
    # such as cars.csv::$DATA, which is cars.csv itself), and not "." or "..". So the
    # Meta caller is at least as strict as the generator, on every system.
    folder = tmp_path / "set_b" / "dev"
    cars = car_set(folder, [("B01", "B01-1.jpg", "B01.txt")])
    row = {"car_id": "B01", "photo_file": "B01-1.jpg", "consent_file": consent}
    write_csv(cars, CARS_COLUMNS, [row | CAR_FACTS])
    fake = FakeClient()
    assert run(dev_argv(cars, folder / "masks"), fake) == 1
    assert capsys.readouterr().out == "row 1 consent_file: bad_name\n"
    assert fake.sent == []
    assert not (folder / "masks").exists()


@pytest.mark.parametrize(
    ("header", "row", "problem"),
    [
        ("car_id,photo_file,,consent_file", "B01,B01-1.jpg,x,B01.txt", "3: blank"),
        ("car_id,#,photo_file,consent_file", "B01,1,B01-1.jpg,B01.txt", "2: reserved"),
        # A blank first consent_file and a filled second one: no cell may win silently.
        (
            "car_id,photo_file,consent_file,consent_file",
            "B01,B01-1.jpg,,B01.txt",
            "4: duplicate",
        ),
    ],
)
def test_cars_csv_header_is_checked(tmp_path, capsys, header, row, problem):
    folder = tmp_path / "set_b" / "dev"
    cars = car_set(folder, [("B01", "B01-1.jpg", "B01.txt")])
    cars.write_text(f"{header}\n{row}\n", encoding="utf-8")
    fake = FakeClient()
    assert run(dev_argv(cars, folder / "masks"), fake) == 1
    assert capsys.readouterr().out == f"header column {problem}\n"
    assert fake.sent == []


def test_undecodable_photo_is_skipped_in_both_modes(tmp_path, monkeypatch, capsys):
    dev = tmp_path / "set_b" / "dev"
    cars = car_set(
        dev,
        [
            ("B01", "B01-1.jpg", "B01.txt"),
            ("B03", "B03-1.jpg", "B03.txt"),
            ("B05", "B05-1.jpg", "B05.txt"),
        ],
        data={"B03-1.jpg": b"not an image", "B05-1.jpg": jpeg(5, (20, 20))},
    )
    fake = FakeClient()
    assert run(dev_argv(cars, dev / "masks"), fake) == 0
    assert sizes(fake) == [(120, 160)] * 3
    lines = capsys.readouterr().out.splitlines()
    assert "B03-1 skipped: undecodable" in lines
    assert "B05-1 skipped: undecodable" in lines  # a side of 32 px or less (R27)
    assert re.fullmatch(r"photos=1 skipped=2 sam_calls=3 seconds=[0-9.]+", lines[-1])
    assert not (dev / "masks" / "B03-1").exists()

    sealed = tmp_path / "set_b" / "sealed"
    cars = car_set(
        sealed,
        [("B02", "B02-1.jpg", "B02.txt"), ("B04", "B04-1.jpg", "B04.txt")],
        data={"B02-1.jpg": b"not an image"},
    )
    as_rene(monkeypatch, "yes")
    fake = FakeClient()
    assert run(["--final", *dev_argv(cars, sealed / "masks")], fake) == 0
    assert len(fake.sent) == 3
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert "row 1 skipped: undecodable" in lines
    assert re.fullmatch(r"photos=1 skipped=1 sam_calls=3 seconds=[0-9.]+", lines[-1])
    assert re.search(r"[Bb][0-9]{2}", captured.out + captured.err) is None


def test_missing_photos_and_crops_are_named_before_any_call(
    tmp_path, monkeypatch, capsys
):
    dev = tmp_path / "set_b" / "dev"
    cars = car_set(
        dev, [("B01", "B01-1.jpg", "B01.txt"), ("B03", "B03-1.jpg", "B03.txt")]
    )
    (dev / "photos" / "B03-1.jpg").unlink()
    fake = FakeClient()
    assert run(dev_argv(cars, dev / "masks"), fake) == 1
    assert capsys.readouterr().out == "B03-1 photo_file: missing\n"
    assert fake.sent == []

    truth = crop_set(dev / "generated", ["B01-1-1", "B01-1-2"])
    (dev / "generated" / "crops" / "B01-1-2.jpg").unlink()
    assert run(["--water", truth, "--out", dev / "masks"], fake) == 1
    assert capsys.readouterr().out == "B01-1-2 crop_file: missing\n"
    assert fake.sent == []
    assert not (dev / "masks").exists()

    # Under --final, by its row, before Rene is asked anything.
    sealed = tmp_path / "set_b" / "sealed"
    cars = car_set(
        sealed, [("B02", "B02-1.jpg", "B02.txt"), ("B04", "B04-1.jpg", "B04.txt")]
    )
    (sealed / "photos" / "B04-1.jpg").unlink()
    prompts = []
    monkeypatch.setattr(probe, "console_ok", lambda **_: True)
    monkeypatch.setattr(
        builtins, "input", lambda prompt="": prompts.append(prompt) or "yes"
    )
    assert run(["--final", *dev_argv(cars, sealed / "masks")], fake) == 1
    captured = capsys.readouterr()
    assert captured.out == "row 2 photo_file: missing\n"
    assert re.search(r"[Bb][0-9]{2}", captured.out + captured.err) is None
    assert prompts == []
    assert fake.sent == []


def test_rerun_pays_nothing(tmp_path, capsys):
    folder = tmp_path / "set_b" / "dev"
    cars = car_set(
        folder, [("B01", "B01-1.jpg", "B01.txt"), ("B03", "B03-1.jpg", "B03.txt")]
    )
    out = folder / "masks"
    assert run(dev_argv(cars, out), FakeClient()) == 0
    backdate(*(path for path in out.rglob("*") if path.is_file()))
    before = snapshot(out)
    capsys.readouterr()
    again = FakeClient()
    assert run(dev_argv(cars, out), again) == 0
    assert again.sent == []
    assert snapshot(out) == before
    lines = capsys.readouterr().out.splitlines()
    assert lines[:3] == [
        "B01-1 skipped: done",
        "B03-1 skipped: done",
        "planned photos=0 sam_calls=0 cost=$0.0000",
    ]
    assert re.fullmatch(r"photos=0 skipped=2 sam_calls=0 seconds=[0-9.]+", lines[-1])


def test_files_txt_is_repaired_for_finished_folders(tmp_path, monkeypatch):
    # A run stopped between a folder's meta.json and its files.txt merge left that
    # folder finished but unlisted. The next run lists it again, and pays nothing.
    dev = tmp_path / "set_b" / "dev"
    cars = car_set(
        dev, [("B01", "B01-1.jpg", "B01.txt"), ("B03", "B03-1.jpg", "B03.txt")]
    )
    truth = crop_set(dev / "generated", ["B01-1-1"])
    out = dev / "masks"
    water = ["--water", truth, "--out", out]
    assert run(dev_argv(cars, out), FakeClient()) == 0
    assert run(water, FakeClient()) == 0
    full = (out / "files.txt").read_bytes()
    first = [line for line in full.splitlines(keepends=True) if b"  B01-1/" in line]
    (out / "files.txt").write_bytes(b"".join(first))  # B03-1 and the crop unlisted
    for argv in (dev_argv(cars, out), water):
        again = FakeClient()
        assert run(argv, again) == 0
        assert again.sent == []
    assert (out / "files.txt").read_bytes() == full

    # Under --final the repair is a write, so it waits for Rene's yes.
    sealed = tmp_path / "set_b" / "sealed"
    cars = car_set(sealed, [("B02", "B02-1.jpg", "B02.txt")])
    argv = ["--final", *dev_argv(cars, sealed / "masks")]
    listing = sealed / "masks" / "files.txt"
    as_rene(monkeypatch, "yes")
    assert run(argv, FakeClient()) == 0
    full = listing.read_bytes()
    listing.unlink()
    as_rene(monkeypatch, "no")
    assert run(argv, FakeClient()) == 2
    assert not listing.exists()
    as_rene(monkeypatch, "yes")
    again = FakeClient()
    assert run(argv, again) == 0
    assert again.sent == []
    assert listing.read_bytes() == full


def test_write_files_txt_merges_by_name(tmp_path):
    out = tmp_path / "masks"
    (out / "water" / "B01-1-1").mkdir(parents=True)
    photo, crop = out / "photo.bin", out / "water" / "B01-1-1" / "meta.json"
    photo.write_bytes(b"one")
    crop.write_bytes(b"{}\n")
    listing = out / "files.txt"
    crop_line = sha256(b"{}\n") + "  water/B01-1-1/meta.json\n"
    probe.write_files_txt(out, [])
    assert not listing.exists()  # nothing written, so nothing to list
    probe.write_files_txt(out, [crop, photo])
    expected = sha256(b"one") + "  photo.bin\n" + crop_line  # sorted by path
    assert listing.read_bytes() == expected.encode("utf-8")
    # The same bytes again leave files.txt as it was, byte for byte and untouched.
    backdate(listing)
    probe.write_files_txt(out, [photo])
    probe.write_files_txt(out, [])
    assert listing.stat().st_mtime_ns == OLD_NS
    # A rewritten file replaces its own entry and keeps the others.
    photo.write_bytes(b"two")
    probe.write_files_txt(out, [photo])
    expected = sha256(b"two") + "  photo.bin\n" + crop_line
    assert listing.read_bytes() == expected.encode("utf-8")


def test_files_txt_lists_every_file_with_its_hash(tmp_path):
    folder = tmp_path / "set_b" / "dev"
    cars = car_set(
        folder, [("B01", "B01-1.jpg", "B01.txt"), ("B03", "B03-1.jpg", "B03.txt")]
    )
    truth = crop_set(folder / "generated", ["B01-1-1", "B01-1-2"])
    out = folder / "masks"
    assert run(dev_argv(cars, out), FakeClient()) == 0
    photos = (out / "files.txt").read_bytes()
    assert photos == listed(out)
    assert len(photos.splitlines()) == 2 * len(PHOTO_FILES)
    # A --water run keeps the photos' entries and adds its own.
    assert run(["--water", truth, "--out", out], FakeClient()) == 0
    both = (out / "files.txt").read_bytes()
    assert both == listed(out)
    assert set(photos.splitlines()) < set(both.splitlines())
    assert len(both.splitlines()) == 2 * len(PHOTO_FILES) + 2 * 3


def test_water_mode_segments_each_crop_once(tmp_path, capsys):
    generated = tmp_path / "set_b" / "dev" / "generated"
    truth = crop_set(generated, ["B01-1-1", "B01-1-2"])
    out = tmp_path / "set_b" / "dev" / "masks"
    fake = FakeClient()
    assert run(["--water", truth, "--out", out], fake) == 0
    assert [phrase for _, phrase in fake.sent] == [probe.WATER_PHRASE] * 2
    assert probe.WATER_PHRASE == "floodwater"
    for crop, (image, _) in zip(("B01-1-1", "B01-1-2"), fake.sent, strict=True):
        water = out / "water" / crop
        assert sorted(path.name for path in water.iterdir()) == [
            "meta.json",
            "sam_floodwater.txt",
            "sam_floodwater_masks.npz",
        ]
        meta = json.loads((water / "meta.json").read_bytes())
        crop_bytes = (generated / "crops" / f"{crop}.jpg").read_bytes()
        assert meta["crop_sha256"] == sha256(crop_bytes)
        assert meta["generator_version"] == "g1"
        assert (meta["width"], meta["height"]) == (image.width, image.height)
        with np.load(water / "sam_floodwater_masks.npz") as saved:
            assert saved["masks"].shape == (1, image.height, image.width)
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "planned photos=2 sam_calls=2 cost=$0.0050"


def test_water_mode_redoes_a_changed_crop(tmp_path):
    generated = tmp_path / "set_b" / "dev" / "generated"
    truth = crop_set(generated, ["B01-1-1", "B01-1-2"])
    out = tmp_path / "set_b" / "dev" / "masks"
    argv = ["--water", truth, "--out", out]
    assert run(argv, FakeClient()) == 0
    kept = (out / "water" / "B01-1-1" / "meta.json").read_bytes()
    changed = jpeg(999, (100, 140))
    (generated / "crops" / "B01-1-2.jpg").write_bytes(changed)
    again = FakeClient()
    assert run(argv, again) == 0
    assert sizes(again) == [(100, 140)]
    meta = json.loads((out / "water" / "B01-1-2" / "meta.json").read_bytes())
    assert meta["crop_sha256"] == sha256(changed)
    assert (out / "water" / "B01-1-1" / "meta.json").read_bytes() == kept
    # A new look's version segments every crop again (C213).
    write_csv(truth, TRUTH_COLUMNS, truth_rows(["B01-1-1", "B01-1-2"], "g2"))
    look = FakeClient()
    assert run(argv, look) == 0
    assert len(look.sent) == 2
    meta = json.loads((out / "water" / "B01-1-1" / "meta.json").read_bytes())
    assert meta["generator_version"] == "g2"


def test_water_mode_checks_crop_ids(tmp_path, capsys):
    generated = tmp_path / "set_b" / "dev" / "generated"
    rows = truth_rows(["B01-1-1", "B01-1-2", "B01-1-3"], "g1")
    rows[2]["crop_id"] = ".."  # an id becomes a folder name under --out
    rows[4]["crop_file"] = "../../B01-1.jpg"  # a crop is read from crops/ only
    truth = write_csv(generated / "truth.csv", TRUTH_COLUMNS, rows)
    fake = FakeClient()
    assert run(["--water", truth, "--out", tmp_path / "masks"], fake) == 1
    assert capsys.readouterr().out.splitlines() == [
        "row 3 crop_id: bad_id",
        "row 5 crop_file: id_file_mismatch",
    ]
    assert fake.sent == []


def test_water_mode_refuses_a_final_cars_crop(tmp_path, capsys):
    # --water is for development crops only. A final car's crop names its row, never
    # its id, and nothing is sent.
    generated = tmp_path / "set_b" / "dev" / "generated"
    truth = crop_set(generated, ["B01-1-1", "B02-1-1"])
    fake = FakeClient()
    assert run(["--water", truth, "--out", tmp_path / "masks"], fake) == 1
    captured = capsys.readouterr()
    assert captured.out.splitlines() == [
        "row 3 crop_id: wrong_side",
        "row 4 crop_id: wrong_side",
    ]
    assert "B02" not in captured.out + captured.err
    assert fake.sent == []


# The guards in use.


@pytest.mark.parametrize("mode", ["cars", "water"])
def test_out_must_be_absolute(tmp_path, capsys, mode):
    # uv's --directory runs the tool in backend/analysis, so a relative --out would
    # put blurred photos in the repo. It is refused before anything is opened: none of
    # the inputs exists.
    folder = tmp_path / "set_b" / "dev"
    for out in ("set_b_masks_out", "C:set_b_masks_out"):  # also drive-relative
        if mode == "cars":
            argv = ["--cars", folder / "cars.csv", "--photos", folder / "photos"]
        else:
            argv = ["--water", folder / "generated" / "truth.csv"]
        fake = FakeClient()
        assert run([*argv, "--out", out], fake) == 2
        assert capsys.readouterr().err.endswith(
            "error: --out must be an absolute path\n"
        )
        assert fake.sent == []
        assert not Path(out).exists()


@pytest.mark.parametrize(
    ("flags", "sealed_flag"),
    [
        (("--cars", "--photos", "--out"), "--cars"),
        (("--cars", "--photos", "--out"), "--photos"),
        (("--cars", "--photos", "--out"), "--out"),
        (("--water", "--out"), "--water"),
        (("--water", "--out"), "--out"),
    ],
)
def test_dev_mode_refuses_sealed_paths(tmp_path, capsys, flags, sealed_flag):
    # None of these paths exists: the refusal comes from the strings alone.
    argv = []
    for flag in flags:
        side = "sealed" if flag == sealed_flag else "dev"
        argv += [flag, tmp_path / side / flag.strip("-")]
    fake = FakeClient()
    assert run(argv, fake) == 2
    assert capsys.readouterr().err == SEALED_REFUSAL
    assert fake.sent == []


def test_dev_mode_refuses_a_sealed_consent_path(tmp_path, capsys):
    # A consent file is a bare name beside cars.csv, so only a name such as "Sealed."
    # can name sealed. It is refused as a command-line path would be, before its stat.
    # No such file exists, and nothing is made.
    folder = tmp_path / "set_b" / "dev"
    cars = car_set(folder, [("B01", "B01-1.jpg", "B01-missing.txt")])
    row = {"car_id": "B01", "photo_file": "B01-1.jpg", "consent_file": "Sealed."}
    write_csv(cars, CARS_COLUMNS, [{**row, **CAR_FACTS}])
    fake = FakeClient()
    assert run(dev_argv(cars, folder / "masks"), fake) == 2
    assert capsys.readouterr().err == SEALED_REFUSAL
    assert fake.sent == []


def test_water_with_final_is_refused(tmp_path, monkeypatch):
    as_rene(monkeypatch, "yes")
    generated = tmp_path / "set_b" / "sealed" / "generated"
    argv = ["--final", "--water", generated / "truth.csv", "--out", tmp_path / "masks"]
    fake = FakeClient()
    assert run(argv, fake) == 2
    assert fake.sent == []


def test_final_needs_sealed_paths_and_a_console(tmp_path, capsys):
    sealed = tmp_path / "set_b" / "sealed"
    paths = {
        "--cars": sealed / "cars.csv",
        "--photos": sealed / "photos",
        "--out": sealed / "masks",
    }
    # From Claude's shell, with stdin on NUL and stdout piped, the console check
    # refuses. None of the sealed paths exists, and none is made.
    argv = ["--final", *(str(part) for pair in paths.items() for part in pair)]
    shell = subprocess.run(
        [sys.executable, str(PROBE), *argv],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )
    assert shell.returncode == 2
    assert shell.stderr == CONSOLE_REFUSAL
    assert not sealed.exists()
    # Each path outside a folder named sealed is refused, before the console check.
    for flag in paths:
        given = {**paths, flag: tmp_path / "set_b" / "dev" / "elsewhere"}
        fake = FakeClient()
        assert run(["--final", *(p for pair in given.items() for p in pair)], fake) == 2
        assert capsys.readouterr().err == (
            f"refused: {flag} must be inside a folder named sealed\n"
        )
        assert fake.sent == []


def test_final_without_a_console_stops_before_the_prompt(tmp_path, monkeypatch, capsys):
    # S-R2: the console check comes before any prompt, since NUL never answers one.
    # The paths don't exist: the run stops before it reads or stats any of them.
    prompts = []
    monkeypatch.setattr(probe, "console_ok", lambda **_: False)
    monkeypatch.setattr(
        builtins, "input", lambda prompt="": prompts.append(prompt) or "yes"
    )
    sealed = tmp_path / "set_b" / "sealed"
    argv = [
        "--final",
        *dev_argv(sealed / "cars.csv", sealed / "masks"),
    ]
    fake = FakeClient()
    assert run(argv, fake) == 2
    captured = capsys.readouterr()
    assert captured.err == CONSOLE_REFUSAL
    assert captured.out == ""
    assert prompts == []
    assert fake.sent == []


def test_final_needs_yes_before_any_call(tmp_path, monkeypatch, capsys):
    sealed = tmp_path / "set_b" / "sealed"
    cars = car_set(sealed, [("B02", "B02-1.jpg", "B02.txt")])
    argv = ["--final", *dev_argv(cars, sealed / "masks")]
    as_rene(monkeypatch, "no")
    fake = FakeClient()
    assert run(argv, fake) == 2
    captured = capsys.readouterr()
    assert captured.out == "planned photos=1 sam_calls=3 cost=$0.0075\n"
    assert captured.err == "stopped: nothing was done\n"
    assert fake.sent == []
    assert not (sealed / "masks").exists()

    as_rene(monkeypatch, "yes")
    assert run(argv, fake) == 0
    assert [phrase for _, phrase in fake.sent] == list(probe.PHRASES)
    assert (sealed / "masks" / "B02-1" / "meta.json").is_file()
    assert (sealed / "masks" / "files.txt").read_bytes() == listed(sealed / "masks")


def test_meta_error_keeps_finished_photos(tmp_path, capsys):
    folder = tmp_path / "set_b" / "dev"
    cars = car_set(
        folder, [("B01", "B01-1.jpg", "B01.txt"), ("B03", "B03-1.jpg", "B03.txt")]
    )
    out = folder / "masks"
    fake = FakeClient(fail_on=4)
    assert run(dev_argv(cars, out), fake) == 1
    captured = capsys.readouterr()
    assert captured.err == "stopped: MetaApiError status=503\n"
    assert sorted(path.name for path in (out / "B01-1").iterdir()) == sorted(
        PHOTO_FILES
    )
    assert not (out / "B03-1" / "meta.json").exists()
    entries = (out / "files.txt").read_text(encoding="utf-8").splitlines()
    assert [line.split("  ")[1] for line in entries] == sorted(
        f"B01-1/{name}" for name in PHOTO_FILES
    )
    # The rerun sends only the photo that didn't finish.
    again = FakeClient()
    assert run(dev_argv(cars, out), again) == 0
    assert len(again.sent) == 3
    assert (out / "files.txt").read_bytes() == listed(out)


def test_missing_key_exits_2(tmp_path, capsys):
    folder = tmp_path / "set_b" / "dev"
    cars = car_set(folder, [("B01", "B01-1.jpg", "B01.txt")])

    def no_key():
        raise MissingApiKey("MODEL_API_KEY is missing or too short")

    argv = [str(arg) for arg in dev_argv(cars, folder / "masks")]
    assert probe.main(argv, make_client=no_key) == 2
    assert capsys.readouterr().err == "stopped: MissingApiKey\n"
    assert not (folder / "masks").exists()


def test_source_lists_no_folder_and_reads_no_environment():
    text = PROBE.read_text(encoding="utf-8")
    listing = (
        "listdir(",
        "scandir(",
        "os.walk(",
        ".iterdir(",
        ".glob(",
        ".rglob(",
        ".walk(",
        "import glob",
        "copytree(",
        "rmtree(",
    )
    assert [call for call in listing if call in text] == []
    # A from-import hides a listing call from the substrings, as `from os import walk`
    # then `walk(top)` would.
    imported = [
        (node.module, alias.name)
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.ImportFrom) and node.module in ("os", "shutil", "glob")
        for alias in node.names
    ]
    names = {"listdir", "scandir", "walk", "copytree", "rmtree", "*"}
    assert [(m, n) for m, n in imported if m == "glob" or n in names] == []
    assert re.search(r"\benvironb?\b", text) is None  # but not "environment"
    assert "getenv" not in text
    assert "LUSOT_DATA_DIR" not in text
