"""Tests for Set B's rows and the early rim check (C314, C323, C327): the Set B
functions in lusot_analysis.export, which are path-free, and probes/set_b.py.

The tool isn't a package module, so it is loaded from its file, and it loads the
offline runner the same way. SAM's results are fakes.wheel_scene's masks, served by a
FakeClient, so no Meta call is made. truth.csv is CSV in tmp_path, in MS2's columns
(its §5.9), and each crop is a noise_jpeg. LUSOT_DATA_DIR is tmp_path/data and
MODEL_API_KEY is unset, so no test reaches Meta or the real data folder. Expected
numbers come from the start values, so the tests pass START (R128).

The estimates carry MS6's names, as its loader on Window 4's branch checks them
(eval/scoring/rows.py): every estimate holds `measured`, `depthInPoint`,
`depthInMin`, `depthInMax` and `fail`, the failed check's token, or null.
"""

import csv
import dataclasses
import hashlib
import importlib.util
import io
import json
import re
import threading
from decimal import Decimal
from pathlib import Path

import cv2
import numpy as np
import pytest
from fakes import (
    FakeClient,
    FakeSpend,
    geometry_case,
    instance,
    noise_jpeg,
    wheel_scene,
)

from lusot_analysis import export
from lusot_analysis.face_blur import BlurredImage
from lusot_analysis.meta_client import MetaApiError, SamResult
from lusot_analysis.spend import cost_of
from lusot_analysis.tuning import START

TOOL = Path(__file__).parents[1] / "probes" / "set_b.py"
BRIGHT = 127.0  # a daylight brightness, over check 4's 80
# MS2's truth.csv columns (its formats.TRUTH_COLUMNS, on ms2-data).
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
# geometry_case's wheel box, which is also the truth rows' box.
WHEEL_BOX = (263, 183, 378, 257)
VARIANTS = (
    "geometry",
    "geometry_uncalibrated",
    "known_waterline",
    "known_waterline_uncalibrated",
)
NUMBERS = ("depthInPoint", "depthInMin", "depthInMax")
ESTIMATE_FIELDS = {"measured", *NUMBERS, "fail"}
# MS6's §4.3 fields of a Set B row, as its loader checks them.
ROW_FIELDS = {
    "crop_id",
    "wheel",
    "car_id",
    "vehicle_type",
    "tire_code",
    "true_depth_in",
    "sam_water_found",
    "bins",
    "estimates",
}
# C87's attribution.csv columns, which the Commons car folder shares.
CREDIT_COLUMNS = (
    "file_name",
    "title",
    "commons_page_url",
    "author",
    "licence",
    "licence_url",
    "credit_line",
    "fetch_mode",
    "flags",
)
META_COLUMNS = ("title", "sha1", "model", "tire_code_candidates", "notes")
NOTE = "NOTE-MARKER-41"  # cars_meta.csv's free text, which nothing printed may hold
FAILS = "check 9 fails at the known waterline, by axis ratio: "  # export's line
# rims' line of counts, before any call.
PHOTOS = (
    "photos: {listed} listed, {unmatched} unmatched, {codes} without codes,"
    " {credit} without a credit line, {checked} to check"
)


def load_tool():
    spec = importlib.util.spec_from_file_location("set_b_script", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load_tool()


def no_client():
    raise AssertionError("a Meta client was built")


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(tool.runner, "make_client", no_client)
    monkeypatch.setattr(tool.runner, "check_before_paying", FakeSpend)  # no AWS


def csv_text(columns, rows) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def truth_row(crop_id: str = "B01-1-1", wheel: str = "1", **cells: str) -> dict:
    """A truth.csv row in MS2's columns: geometry_case's wheel, a sedan_hatch on
    175/65R14 at 5.0 px an inch, with the drawn waterline at row 257."""
    x0, y0, x1, y1 = WHEEL_BOX
    row = {
        "crop_id": crop_id,
        "car_id": crop_id.split("-")[0],
        "split": "dev",
        "photo_file": crop_id.rsplit("-", 1)[0] + ".jpg",
        "crop_file": f"{crop_id}.jpg",
        "wheel": wheel,
        "view": "side",
        "vehicle_type": "sedan_hatch",
        "tire_code": "175/65R14",
        "rim_in": "14",
        "diameter_in": "22.9567",
        "crop_scale": "1.0",
        "size_bin": "full",
        "x0": str(x0),
        "y0": str(y0),
        "x1": str(x1),
        "y1": str(y1),
        "ground_row": "297",
        "top_row": "183",
        "px_per_in": "5.0",
        "waterline_left_row": "257",
        "waterline_right_row": "257",
        "waterline_row": "257",
        "true_depth_in": "8.08",
        "band": "half_knee",
        "rim_edge_ratio": "1.0",
        "generator_version": "setb-gen-v1",
    }
    return row | cells


def one_row(**cells: str) -> export.WheelRow:
    (row,) = export.parse_truth(csv_text(TRUTH_COLUMNS, [truth_row(**cells)]))
    return row


def set_b_sam(*, water=True, wheel_boxes=(WHEEL_BOX,)) -> dict[str, SamResult]:
    """SAM's results for Set B's three phrases: geometry_case's rim and water, and a
    wheel for each of `wheel_boxes`, each holding geometry_case's wheel mask."""
    sam = geometry_case()[1]
    mask = sam["wheel"].instances[0].mask
    wheels = [instance(i, box, mask=mask) for i, box in enumerate(wheel_boxes)]
    floodwater = sam["floodwater"] if water else SamResult("floodwater", [], 0.5, "")
    return {
        "floodwater": floodwater,
        "wheel": SamResult("wheel", wheels, 0.5, ""),
        "wheel rim": sam["wheel rim"],
    }


def dry_sam() -> dict[str, SamResult]:
    """A dry car's wheel and rim, whole: wheel_scene with no water in the image."""
    wheel_mask, rim_mask, _ = wheel_scene(y_true=480)
    return {
        "wheel": SamResult(
            "wheel", [instance(0, (263, 183, 378, 298), mask=wheel_mask)], 0.5, ""
        ),
        "wheel rim": SamResult(
            "wheel rim", [instance(0, (285, 205, 356, 276), mask=rim_mask)], 0.5, ""
        ),
    }


def places(value: float) -> int:
    """How many decimal places `value` is written with in JSON."""
    return max(0, -Decimal(json.dumps(value)).as_tuple().exponent)


def decimals(value):
    """Every non-integer number in a row parsed with parse_float=Decimal."""
    if isinstance(value, dict):
        for item in value.values():
            yield from decimals(item)
    elif isinstance(value, list):
        for item in value:
            yield from decimals(item)
    elif isinstance(value, Decimal):
        yield value


@dataclasses.dataclass
class SetB:
    """MS2's Set B development side in tmp_path: the paths the tool is given."""

    root: Path  # LUSOT_DATA_DIR
    truth: Path

    def crop(self, name: str = "B01-1-1.jpg") -> Path:
        return self.truth.parent / "crops" / name

    def run_dir(self, crop_id: str = "B01-1-1") -> Path:
        return self.root / "set_b_runs" / crop_id


def write_set_b(tmp_path, rows=None, *, size=(640, 480), side="dev") -> SetB:
    """truth.csv under tmp_path/data/set_b/<side>/generated, with a noise crop of
    `size` for each crop file it names."""
    root = tmp_path / "data"
    generated = root / "set_b" / side / "generated"
    (generated / "crops").mkdir(parents=True)
    rows = [truth_row()] if rows is None else rows
    truth = generated / "truth.csv"
    truth.write_text(csv_text(TRUTH_COLUMNS, rows), encoding="utf-8")
    for name in dict.fromkeys(row["crop_file"] for row in rows):
        (generated / "crops" / name).write_bytes(noise_jpeg(*size))
    return SetB(root, truth)


def segment(monkeypatch, data: SetB, sam=None) -> FakeClient:
    """`segment --yes` on `data`'s truth file, through a FakeClient."""
    fake = FakeClient(sam or set_b_sam())
    monkeypatch.setattr(tool.runner, "make_client", lambda: fake)
    argv = ["segment", "--truth", str(data.truth), "--yes"]
    assert tool.main(argv, tuning=START) == 0
    monkeypatch.setattr(tool.runner, "make_client", no_client)
    return fake


def export_argv(data: SetB, out: Path) -> list[str]:
    return ["export", "--truth", str(data.truth), "--out", str(out)] + [
        "--rules-version",
        "0.7",
    ]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_cars(tmp_path, cars, *, folder=None) -> Path:
    """The Commons car folder: cars_meta.csv, attribution.csv and the photos.

    Each car is a dict with its `title`, `sha1`, `candidates`, `file` (its photo's
    name, or None for a title with no attribution.csv row) and `credit`.
    """
    folder = folder or tmp_path / "data" / "set_c" / "commons-cars-side"
    (folder / "images").mkdir(parents=True)
    meta = [
        {
            "title": car["title"],
            "sha1": car["sha1"],
            "model": "MODEL-MARKER",
            "tire_code_candidates": car["candidates"],
            "notes": NOTE,
        }
        for car in cars
    ]
    (folder / "cars_meta.csv").write_text(
        csv_text(META_COLUMNS, meta), encoding="utf-8"
    )
    credits = []
    for number, car in enumerate(cars):
        if car["file"] is None:
            continue
        credits.append(
            dict.fromkeys(CREDIT_COLUMNS, "")
            | {"file_name": car["file"], "title": car["title"]}
            | {"credit_line": car["credit"], "author": "AUTHOR-MARKER"}
        )
        (folder / "images" / car["file"]).write_bytes(noise_jpeg(seed=number))
    (folder / "attribution.csv").write_text(
        chr(0xFEFF) + csv_text(CREDIT_COLUMNS, credits), encoding="utf-8"
    )
    return folder


def test_read_wheels_validates(tmp_path):
    # A 2000 x 1500 crop is sent at 1600 x 1200, so its pixel values scale by 0.8.
    # Its inches and ratios don't: rows and pixels are the crop's own (MS2's §5.9).
    data = write_set_b(tmp_path, size=(2000, 1500))
    (row,) = tool.read_wheels(data.truth, data.root)
    assert row.box == pytest.approx(tuple(0.8 * value for value in WHEEL_BOX))
    assert row.px_per_in == pytest.approx(4.0)
    assert row.waterline_row == pytest.approx(205.6)
    assert (row.true_depth_in, row.rim_edge_ratio) == (8.08, 1.0)
    # A crop the app's size or under it is sent as it is.
    small = write_set_b(tmp_path / "small")
    (row,) = tool.read_wheels(small.truth, small.root)
    assert (row.box, row.px_per_in, row.waterline_row) == (WHEEL_BOX, 5.0, 257.0)
    assert (row.crop_id, row.wheel, row.car_id) == ("B01-1-1", 1, "B01")
    assert (row.view, row.size_bin, row.vehicle_type) == ("side", "full", "sedan_hatch")
    # MS2 copies the code as on the sidewall, and reads it in any case, with a load
    # index after a space: the row keeps the code MS6's loader takes.
    assert one_row(tire_code=" 175/65 r14 82T").tire_code.code == "175/65R14"
    van = one_row(tire_code="215/70R16C 113/111R", vehicle_type="van")
    assert (van.tire_code.code, van.tire_code.rim_in) == ("215/70R16C", 16)
    assert one_row(rim_edge_ratio="").rim_edge_ratio is None  # MS2 found no rim
    # Each bad field is a ValueError naming the crop and the wheel, from the text and
    # from the file.
    for cells in (
        {"tire_code": ""},  # missing
        {"px_per_in": ""},
        {"vehicle_type": "bus_truck"},  # not a Set B type
        {"vehicle_type": "unknown"},
        {"tire_code": "195R14C"},  # no aspect ratio
        {"tire_code": "7.50-16"},  # bias-ply
        {"px_per_in": "0"},
        {"x1": "200"},  # left of x0
        {"waterline_row": "nan"},
        {"true_depth_in": "8.08001"},  # more than MS6's 4 decimal places
        {"view": "front"},
        {"size_bin": "tiny"},
        {"car_id": "car 1"},  # not an opaque id
        {"crop_file": "../../sealed/B01-1-1.jpg"},  # not a bare file name
        {"crop_file": "B01-1-2.jpg"},  # another file than the crop's first row
    ):
        text = csv_text(TRUTH_COLUMNS, [truth_row(), truth_row(wheel="2", **cells)])
        with pytest.raises(ValueError, match="crop B01-1-1 wheel 2"):
            export.parse_truth(text)
        data.truth.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match="crop B01-1-1 wheel 2"):
            tool.read_wheels(data.truth, data.root)
    # A repeated crop and wheel, a bad id or wheel number, and a missing column.
    with pytest.raises(ValueError, match="crop B01-1-1 wheel 1: .*repeat"):
        export.parse_truth(csv_text(TRUTH_COLUMNS, [truth_row(), truth_row()]))
    for cells in ({"crop_id": "2026-10-30"}, {"wheel": "3"}):
        with pytest.raises(ValueError, match="truth.csv row 1"):
            export.parse_truth(csv_text(TRUTH_COLUMNS, [truth_row(**cells)]))
    columns = [column for column in TRUTH_COLUMNS if column != "waterline_row"]
    row = {key: value for key, value in truth_row().items() if key in columns}
    with pytest.raises(ValueError, match="no waterline_row column"):
        export.parse_truth(csv_text(columns, [row]))


def test_wheel_estimates_at_k_1():
    estimates = export.wheel_estimates(one_row(), set_b_sam(), BRIGHT, tuning=START)
    assert tuple(estimates) == VARIANTS
    for estimate in estimates.values():
        assert set(estimate) == ESTIMATE_FIELDS
        assert (estimate["measured"], estimate["fail"]) == (True, None)
        assert estimate["depthInPoint"] == pytest.approx(7.94, abs=0.02)
        assert estimate["depthInMin"] == pytest.approx(7.720, abs=0.02)
        assert estimate["depthInMax"] == pytest.approx(8.184, abs=0.02)
        assert all(places(estimate[key]) <= 4 for key in NUMBERS)


def test_wheel_estimates_with_a_calibrated_k():
    tuning = dataclasses.replace(START, rim_edge_k=1.05)
    estimates = export.wheel_estimates(one_row(), set_b_sam(), BRIGHT, tuning=tuning)
    for variant in ("geometry", "known_waterline"):
        estimate = estimates[variant]
        assert estimate["depthInPoint"] == pytest.approx(7.77, abs=0.02)
        assert estimate["depthInMin"] == pytest.approx(7.53, abs=0.02)
        assert estimate["depthInMax"] == pytest.approx(7.98, abs=0.02)
    for variant in ("geometry_uncalibrated", "known_waterline_uncalibrated"):
        estimate = estimates[variant]
        assert estimate["depthInPoint"] == pytest.approx(7.94, abs=0.02)
        assert estimate["depthInMin"] == pytest.approx(7.720, abs=0.02)
        assert estimate["depthInMax"] == pytest.approx(8.184, abs=0.02)
    for estimate in estimates.values():
        assert all(places(estimate[key]) <= 4 for key in NUMBERS)


def test_the_true_box_only_picks_the_sam_wheel():
    # Finding 6: MS2's true box only picks the SAM wheel. Rim linking and checks 6
    # and 9 use SAM's box, as the pipeline does.
    row = one_row()
    x0, y0, x1, y1 = WHEEL_BOX

    def estimates(*boxes):
        sam = set_b_sam(wheel_boxes=boxes)
        return export.wheel_estimates(row, sam, BRIGHT, tuning=START)

    def fails(*boxes):
        return {estimate["fail"] for estimate in estimates(*boxes).values()}

    # A SAM box 6 px off the true box still holds its centre: that wheel is picked,
    # its rim links, and it measures as SAM's box on the true box does.
    box = (x0 + 6, y0, x1 + 6, y1)
    wheels = set_b_sam(wheel_boxes=[WHEEL_BOX, (0, 0, 100, 100), box])["wheel"]
    assert export.sam_wheel(row, wheels.instances[1:]) == 1
    shifted = estimates(box)
    assert all(estimate["measured"] for estimate in shifted.values())
    assert shifted == estimates(WHEEL_BOX)
    # Check 6 reads SAM's box: one cut off above the fit's centre, though it still
    # holds the true centre and the rim's, puts the fit off the wheel.
    assert fails((x0, y0, x1, 235)) == {"rim_fit_off_wheel"}
    # Check 9 reads SAM's box too: one 60 px wider makes the rim too small for it.
    assert fails((x0 - 30, y0, x1 + 30, y1)) == {"rim_size"}
    # No SAM wheel, or two, holding the true box's centre: wheel_not_found.
    assert fails((0, 0, 100, 100)) == {"wheel_not_found"}
    assert fails(WHEEL_BOX, (x0 - 10, y0 - 10, x1 + 10, y1 + 10)) == {"wheel_not_found"}
    assert fails() == {"wheel_not_found"}


def test_sam_missing_water_still_measures_the_known_waterline(
    tmp_path, monkeypatch, capsys
):
    # Review Focus 5: SAM finds none of the composited water.
    sam = set_b_sam(water=False)
    estimates = export.wheel_estimates(one_row(), sam, BRIGHT, tuning=START)
    unmeasured = dict.fromkeys(NUMBERS) | {"measured": False}
    unmeasured["fail"] = "no_water_contact"
    assert estimates["geometry"] == estimates["geometry_uncalibrated"] == unmeasured
    for variant in ("known_waterline", "known_waterline_uncalibrated"):
        assert estimates[variant]["measured"] is True
        assert estimates[variant]["depthInPoint"] == pytest.approx(7.94, abs=0.02)
    # Through the tool, the row says SAM found no water.
    data = write_set_b(tmp_path)
    segment(monkeypatch, data, sam)
    out = data.root / "results" / "no-water"
    assert tool.main(export_argv(data, out), tuning=START) == 0
    (row,) = read_lines(out / "set_b.jsonl")
    assert row["sam_water_found"] is False
    assert row["estimates"] == estimates


def test_k_is_the_median_of_car_medians():
    ratios = {"car01": [0.98, 1.00], "car02": [1.04], "car03": [1.10, 1.12, 1.08]}
    assert export.k_estimate(ratios) == pytest.approx(1.04)
    assert export.k_estimate({}) is None
    # A wheel's ratio is its known-waterline fit's rim diameter at the true scale over
    # the code's rim: geometry_case's rim has a 35 px radius, 14 in across at 5 px an
    # inch, a 175/65R14's rim.
    row = one_row()
    fit = export.known_waterline_fit(row, set_b_sam(), tuning=START)
    assert export.k_ratio(row, fit) == pytest.approx(1.0, abs=0.03)
    # No fit without one SAM wheel holding the true centre.
    sam = set_b_sam(wheel_boxes=[(0, 0, 100, 100)])
    assert export.known_waterline_fit(row, sam, tuning=START) is None


def test_segment_prints_cost_and_needs_yes(tmp_path, monkeypatch, capsys):
    ids = [f"B{car:02}-1-{crop}" for car in (1, 3, 5, 7, 9) for crop in (1, 2, 3, 4)]
    data = write_set_b(tmp_path, [truth_row(i) for i in ids], size=(64, 48))
    argv = ["segment", "--truth", str(data.truth)]
    # Without --yes: the calls and the cost first, then exit 2, with no client built.
    assert tool.main(argv, tuning=START) == 2
    assert capsys.readouterr().out.splitlines() == [
        "60 SAM calls, about $0.15",
        "crops: 20 in the truth file, 0 already saved",
        "stopped: add --yes to pay for these calls",
    ]
    assert not (data.root / "set_b_runs").exists()
    # A crop with two wheel rows is sent once, after the face blur, with the three
    # phrases.
    two = write_set_b(tmp_path / "two", [truth_row(), truth_row(wheel="2")])
    monkeypatch.setenv("LUSOT_DATA_DIR", str(two.root))
    fake = segment(monkeypatch, two)
    assert capsys.readouterr().out.splitlines() == [
        "3 SAM calls, about $0.01",
        "crops: 1 in the truth file, 0 already saved",
        "crops saved: 1",
    ]
    assert sorted(phrase for _, phrase, _ in fake.calls) == sorted(tool.SET_B_PHRASES)
    assert {(kind, image) for kind, _, image in fake.calls} == {
        ("segment", BlurredImage)
    }
    saved = two.run_dir()
    assert sorted(path.name for path in (saved / "sam").glob("*.json")) == [
        "floodwater.json",
        "wheel.json",
        "wheel_rim.json",
    ]
    record = read_json(saved / "run.json")
    assert record["photo_sha256"] == hashlib.sha256(two.crop().read_bytes()).hexdigest()
    assert record["phrases"] == ["floodwater", "wheel", "wheel rim"]
    assert record["image"] == {"width": 640, "height": 480}
    # A saved crop is skipped, so a rerun pays nothing and builds no client.
    assert tool.main(["segment", "--truth", str(two.truth), "--yes"], tuning=START) == 0
    assert capsys.readouterr().out.splitlines() == [
        "0 SAM calls, about $0.00",
        "crops: 1 in the truth file, 1 already saved",
        "crops saved: 0",
    ]
    # A crop folder without its run.json stopped partway, and is refused before any
    # call.
    (saved / "run.json").unlink()
    assert tool.main(["segment", "--truth", str(two.truth), "--yes"], tuning=START) == 2
    assert "remove it first" in capsys.readouterr().out


def test_set_b_paths_are_refused(tmp_path, monkeypatch, capsys):
    sealed_line = "refused: path inside a folder named sealed\n"
    # A truth file under set_b\sealed\, as MS2 lays out the final cars: refused by
    # every command before anything is read or written.
    sealed = write_set_b(tmp_path, side="sealed")
    overlay = ["overlay", "--truth", str(sealed.truth), "--crop", "B01-1-1"]
    for argv in (
        ["segment", "--truth", str(sealed.truth), "--yes"],
        export_argv(sealed, sealed.root / "results" / "x"),
        [*overlay, "--wheel", "1"],
    ):
        assert tool.main(argv, tuning=START) == 2
        assert capsys.readouterr().out == sealed_line
    assert [path.name for path in sealed.root.iterdir()] == ["set_b"]
    # A crop under a folder named sealed: refused before any crop is opened. One
    # named so is refused by refuse_sealed, one led out of crops\ by its name.
    data = write_set_b(tmp_path / "dev")
    monkeypatch.setenv("LUSOT_DATA_DIR", str(data.root))
    argv = ["segment", "--truth", str(data.truth), "--yes"]
    for crop_file, printed in (
        ("Sealed", sealed_line),
        ("..\\..\\sealed\\B01-1-1.jpg", "invalid: crop B01-1-1 wheel 1:"),
    ):
        rows = [truth_row(crop_file=crop_file)]
        data.truth.write_text(csv_text(TRUTH_COLUMNS, rows), encoding="utf-8")
        assert tool.main(argv, tuning=START) == 2
        assert capsys.readouterr().out.startswith(printed)
    assert not (data.root / "set_b_runs").exists()
    # export's --out: under a folder named sealed, inside the repo, outside the data
    # folder, or beside the saved results. Each is refused before anything is read.
    data = write_set_b(tmp_path / "out")
    monkeypatch.setenv("LUSOT_DATA_DIR", str(data.root))
    for out, printed in (
        (data.root / "results" / "Sealed." / "x", sealed_line),
        (TOOL.parents[1] / "results-set-b-test", "refused: --out is inside the repo\n"),
        (tmp_path / "elsewhere", "refused: --out must lie under the data folder\n"),
        (
            data.root / "set_b_runs" / "rows",
            "refused: --out must lie outside set_b_runs\n",
        ),
    ):
        assert tool.main(export_argv(data, out), tuning=START) == 2
        assert capsys.readouterr().out == printed
        assert not out.exists()
    assert not (data.root / "set_b_runs").exists()


@pytest.mark.parametrize("command", ["segment", "rims"])
def test_paid_commands_refuse_a_data_dir_in_the_repo(
    tmp_path, monkeypatch, capsys, command
):
    # R131: the data folder passes refuse_data_in_repo before any call.
    data = write_set_b(tmp_path)
    cars = write_cars(
        tmp_path,
        [
            {
                "title": "File:CAR-MARKER-1.jpg",
                "sha1": "ab" * 20,
                "candidates": "175/65R14",
                "file": "car-one.jpg",
                "credit": "CC0",
            }
        ],
    )
    inside = TOOL.parents[1] / "data-set-b-r131-test"
    monkeypatch.setenv("LUSOT_DATA_DIR", str(inside))
    argv = {
        "segment": ["segment", "--truth", str(data.truth), "--yes"],
        "rims": ["rims", "--folder", str(cars), "--yes"],
    }[command]
    assert tool.main(argv, tuning=START) == 2
    assert capsys.readouterr().out == "refused: the data folder is inside the repo\n"
    assert not inside.exists()


def test_rows_are_the_contracts(tmp_path, monkeypatch, capsys):
    data = write_set_b(tmp_path)
    segment(monkeypatch, data)
    capsys.readouterr()
    out = data.root / "results" / "set-b"
    assert tool.main(export_argv(data, out), tuning=START) == 0
    printed = capsys.readouterr().out
    (line,) = (out / "set_b.jsonl").read_text(encoding="utf-8").splitlines()
    row = json.loads(line, parse_float=Decimal)
    # Exactly MS6's fields, keyed by crop_id and wheel, with MS2's bins (C423).
    assert set(row) == ROW_FIELDS
    assert (row["crop_id"], row["wheel"], row["car_id"]) == ("B01-1-1", 1, "B01")
    assert (row["vehicle_type"], row["tire_code"]) == ("sedan_hatch", "175/65R14")
    assert row["true_depth_in"] == Decimal("8.08")
    assert row["bins"] == {"view": "side", "size_bin": "full"}
    assert row["sam_water_found"] is True
    assert tuple(row["estimates"]) == VARIANTS
    assert all(set(found) == ESTIMATE_FIELDS for found in row["estimates"].values())
    assert all(number.as_tuple().exponent >= -4 for number in decimals(row))
    manifest = read_json(out / "run.json")
    assert (manifest["kind"], manifest["rules_version"]) == ("development", "0.7")
    assert manifest["frozen"]["sam_phrases"] == "floodwater,wheel,wheel rim"
    assert manifest["frozen"]["rim_edge_k"] == "1.0"
    assert manifest["geometry_default"] == "on"
    assert manifest["datasets"] == {}
    # The printout: counts, k beside MS2's cross-check, then the harness command.
    lines = printed.splitlines()
    assert lines[:3] == [
        "wheels: 1",
        "measured: " + json.dumps(dict.fromkeys(VARIANTS, 1)),
        FAILS + "{}",
    ]
    k, cars = lines[3].removeprefix("k_estimate: ").split(" (cars: ")
    assert (float(k), cars) == (pytest.approx(1.0, abs=0.03), "1)")
    assert lines[4] == "rim_edge_ratio, MS2's: median 1.0000 (wheels: 1)"
    assert lines[5].startswith("next: python eval/run_eval.py --from-saved")
    for text in (printed, (out / "run.json").read_text(encoding="utf-8")):
        assert str(tmp_path) not in text
        assert "B01-1-1.jpg" not in text
    # A rim too small for SAM's box fails check 9: it is counted by its fit's axis
    # ratio, and gives k nothing.
    wide = write_set_b(tmp_path / "wide")
    monkeypatch.setenv("LUSOT_DATA_DIR", str(wide.root))
    x0, y0, x1, y1 = WHEEL_BOX
    segment(monkeypatch, wide, set_b_sam(wheel_boxes=[(x0 - 30, y0, x1 + 30, y1)]))
    capsys.readouterr()
    assert tool.main(export_argv(wide, wide.root / "results" / "x"), tuning=START) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1] == "measured: " + json.dumps(dict.fromkeys(VARIANTS, 0))
    assert lines[2].startswith(FAILS)
    assert sum(json.loads(lines[2].removeprefix(FAILS)).values()) == 1
    assert lines[3] == "k_estimate: none (cars: 0)"
    # A folder that holds another export's rows is refused, since the harness would
    # score them beside this run.json. Nothing is rewritten.
    (out / "set_a.jsonl").write_text("{}\n", encoding="utf-8")
    kept = (out / "set_b.jsonl").read_bytes()
    monkeypatch.setenv("LUSOT_DATA_DIR", str(data.root))
    assert tool.main(export_argv(data, out), tuning=START) == 2
    assert "another export's rows" in capsys.readouterr().out
    assert (out / "set_b.jsonl").read_bytes() == kept
    # Results saved for another crop, and a crop without saved results, are refused
    # before anything is written.
    other = data.root / "results" / "other"
    data.crop().write_bytes(noise_jpeg(seed=7))
    assert tool.main(export_argv(data, other), tuning=START) == 2
    assert capsys.readouterr().out == (
        "refused: saved results belong to another photo\n"
    )
    (data.run_dir() / "run.json").unlink()
    assert tool.main(export_argv(data, other), tuning=START) == 2
    assert "run `set_b.py segment` first" in capsys.readouterr().out
    assert not other.exists()


CARS = [
    {
        "title": "File:CAR-MARKER-1 Avanza.jpg",
        "sha1": "ab" * 20,
        "candidates": "185/65R15; 195/60R16",
        "file": "car-one-1920px.jpg",
        "credit": "Jane Doe, CC BY 4.0",
    },
    {
        "title": "File:CAR-MARKER-2 Hiace.jpg",
        "sha1": "cd" * 20,
        "candidates": "215/70R16C",
        "file": "car-two-1920px.jpg",
        "credit": "CC0",
    },
    {
        "title": "File:CAR-MARKER-3.jpg",
        "sha1": "ef" * 20,
        "candidates": " ; ",  # no plan Table 7 code
        "file": "car-three-1920px.jpg",
        "credit": "CC0",
    },
    {
        "title": "File:CAR-MARKER-4 Raize.jpg",
        "sha1": "fa" * 20,
        "candidates": "205/65R16",
        "file": "car-four-1920px.jpg",
        "credit": "",  # no credit line
    },
]


def test_rims_check_prints_counts_only(tmp_path, monkeypatch, capsys):
    folder = write_cars(tmp_path, CARS)
    blurred = []
    real_blur = tool.blur_for_meta
    monkeypatch.setattr(
        tool, "blur_for_meta", lambda data: blurred.append(data) or real_blur(data)
    )
    argv = ["rims", "--folder", str(folder)]
    # Without --yes: the cost and the counts, then exit 2, with nothing sent.
    assert tool.main(argv, tuning=START) == 2
    assert capsys.readouterr().out.splitlines() == [
        "4 SAM calls, about $0.01",
        PHOTOS.format(listed=4, unmatched=0, codes=1, credit=1, checked=2),
        "stopped: add --yes to pay for these calls",
    ]
    assert blurred == []
    # With it: only the photos with codes and a credit line, each after the face blur,
    # with exactly the two phrases.
    fake = FakeClient(dry_sam())
    monkeypatch.setattr(tool.runner, "make_client", lambda: fake)
    assert tool.main([*argv, "--yes"], tuning=START) == 0
    printed = capsys.readouterr().out
    sent = [(folder / "images" / car["file"]).read_bytes() for car in CARS[:2]]
    assert sorted(blurred) == sorted(sent)
    assert sorted(phrase for _, phrase, _ in fake.calls) == [
        "wheel",
        "wheel",
        "wheel rim",
        "wheel rim",
    ]
    assert {image for _, _, image in fake.calls} == {BlurredImage}
    saved = sorted(path.name for path in (tmp_path / "data" / "set_c_rims").iterdir())
    assert saved == sorted(car["sha1"] for car in CARS[:2])
    # Per wheel: one linked rim, the whole rim's fit, check 9 at the candidates'
    # bounds with SAM's box, and the rim-edge ratio over the candidates.
    lines = printed.splitlines()
    for number in (1, 2):
        (wheel,) = [line for line in lines if line.startswith(f"photo {number} ")]
        assert wheel.startswith(f"photo {number} wheel 1: rims linked 1, fit points ")
        axis = float(re.search("axis ratio ([0-9.]+)", wheel).group(1))
        assert axis == pytest.approx(1.0, abs=0.02)  # a side-on rim, fitted whole
        assert "check 9 passes" in wheel
        low, high = re.search("rim-edge ratio ([0-9.]+) to ([0-9.]+)", wheel).groups()
        assert float(low) <= float(high)
    assert lines[-1] == "wheels: 2, one rim linked 2, fitted 2, check 9 passes 2"
    # Counts only: no title, file name, model, note, credit, key or path.
    for car in CARS:
        assert car["title"] not in printed
        assert car["file"] not in printed
        assert car["sha1"] not in printed
    for marker in ("CAR-MARKER", "MODEL-MARKER", NOTE, "AUTHOR-MARKER", "Jane Doe"):
        assert marker not in printed
    assert str(tmp_path) not in printed
    # A rerun sends nothing: the saved results are read again.
    monkeypatch.setattr(tool.runner, "make_client", no_client)
    assert tool.main([*argv, "--yes"], tuning=START) == 0
    assert capsys.readouterr().out.splitlines()[0] == "0 SAM calls, about $0.00"
    # A folder under one named sealed is refused before anything is read.
    sealed = tmp_path / "x" / "sealed" / "commons-cars-side"
    assert tool.main(["rims", "--folder", str(sealed), "--yes"], tuning=START) == 2
    assert capsys.readouterr().out == "refused: path inside a folder named sealed\n"


def test_rims_check_joins_by_title(tmp_path, monkeypatch, capsys):
    # P2: cars_meta.csv has no file_name, and its sha1 is the Commons original's, not
    # the thumbnail's. The photo is found through attribution.csv's title.
    cars = [
        {
            "title": "File:CAR-MARKER-5.jpg",
            "sha1": "0e" * 20,  # matches no file's hash or name
            "candidates": "175/65R14",
            "file": "a-renamed-thumbnail.jpg",
            "credit": "CC0",
        },
        {
            "title": "File:CAR-MARKER-6.jpg",
            "sha1": "1f" * 20,
            "candidates": "175/65R14",
            "file": None,  # no attribution.csv row
            "credit": "",
        },
    ]
    folder = write_cars(tmp_path, cars)
    fake = FakeClient(dry_sam())
    monkeypatch.setattr(tool.runner, "make_client", lambda: fake)
    assert tool.main(["rims", "--folder", str(folder), "--yes"], tuning=START) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[:2] == [
        "2 SAM calls, about $0.01",
        PHOTOS.format(listed=2, unmatched=1, codes=0, credit=0, checked=1),
    ]
    assert len(fake.calls) == 2
    # Saved under the sha1 key, with the hash of the file actually sent.
    record = read_json(tmp_path / "data" / "set_c_rims" / ("0e" * 20) / "run.json")
    photo = (folder / "images" / "a-renamed-thumbnail.jpg").read_bytes()
    assert record["photo_sha256"] == hashlib.sha256(photo).hexdigest()
    assert record["phrases"] == ["wheel", "wheel rim"]
    assert not (tmp_path / "data" / "set_c_rims" / ("1f" * 20)).exists()
    # A candidate no metric radial code fits is invalid, before any call.
    other = write_cars(tmp_path / "other", [cars[0] | {"candidates": "195R15C"}])
    monkeypatch.setattr(tool.runner, "make_client", no_client)
    assert tool.main(["rims", "--folder", str(other), "--yes"], tuning=START) == 2
    assert capsys.readouterr().out == (
        "invalid: cars_meta.csv row 1: a tire_code_candidates entry isn't a metric"
        " radial code\n"
    )


def test_overlay_writes_under_the_data_dir(tmp_path, monkeypatch, capsys):
    data = write_set_b(tmp_path)
    segment(monkeypatch, data)
    capsys.readouterr()
    argv = ["overlay", "--truth", str(data.truth), "--crop", "B01-1-1", "--wheel"]
    assert tool.main([*argv, "1"], tuning=START) == 0
    assert capsys.readouterr().out == "overlays written: 1\n"  # no path
    (written,) = (data.root / "set_b_overlays").iterdir()
    image = cv2.imdecode(
        np.frombuffer(written.read_bytes(), np.uint8), cv2.IMREAD_COLOR
    )
    assert image.shape == (480, 640, 3)  # the crop as SAM saw it
    # A wheel the truth file doesn't name is refused, and nothing more is written.
    assert tool.main([*argv, "2"], tuning=START) == 2
    assert capsys.readouterr().out == (
        "refused: the truth file has no such crop and wheel\n"
    )
    assert len(list((data.root / "set_b_overlays").iterdir())) == 1
    # Never in the repo: a data folder inside it is refused before anything is read.
    inside = TOOL.parents[1] / "data-set-b-p4-test"
    monkeypatch.setenv("LUSOT_DATA_DIR", str(inside))
    assert tool.main([*argv, "1"], tuning=START) == 2
    assert capsys.readouterr().out == "refused: the data folder is inside the repo\n"
    assert not inside.exists()
    # A data folder under one named sealed is refused too.
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "Sealed" / "data"))
    assert tool.main([*argv, "1"], tuning=START) == 2
    assert capsys.readouterr().out == "refused: path inside a folder named sealed\n"
    assert not (tmp_path / "Sealed").exists()


def no_counter():
    raise AssertionError("the spend counter was read")


def counted(monkeypatch, fake, folder: Path) -> tuple[FakeSpend, list[str]]:
    """A FakeSpend as the runner's check_before_paying, and `fake` as its client,
    with each check, client and record in order, each record with the run.json files
    saved under `folder` by then."""
    events = []

    def recorded():
        events.append(f"record, {len(list(folder.rglob('run.json')))} saved")

    spend = FakeSpend(on_record=recorded)
    monkeypatch.setattr(
        tool.runner, "check_before_paying", lambda: events.append("check") or spend
    )
    monkeypatch.setattr(
        tool.runner, "make_client", lambda: events.append("client") or fake
    )
    return spend, events


def test_segment_and_rims_record_each_photo_once_saved(tmp_path, monkeypatch):
    # Task 12b (C527): the counter is read after --yes and before the one client,
    # and each crop's or photo's SAM calls are recorded once its run.json is saved.
    data = write_set_b(tmp_path, [truth_row("B01-1-1"), truth_row("B03-1-1")])
    spend, events = counted(monkeypatch, FakeClient(set_b_sam()), data.root)
    argv = ["segment", "--truth", str(data.truth)]
    assert tool.main(argv, tuning=START) == 2  # without --yes: nothing to check
    assert events == []
    assert tool.main([*argv, "--yes"], tuning=START) == 0
    assert events == ["check", "client", "record, 1 saved", "record, 2 saved"]
    assert spend.records == [(cost_of(sam_images=3), "set_b")] * 2
    # rims: two phrases for each of the two photos with codes and a credit line.
    folder = write_cars(tmp_path, CARS)
    spend, events = counted(monkeypatch, FakeClient(dry_sam()), data.root)
    assert tool.main(["rims", "--folder", str(folder), "--yes"], tuning=START) == 0
    assert events == ["check", "client", "record, 3 saved", "record, 4 saved"]
    assert spend.records == [(cost_of(sam_images=2), "set_b")] * 2
    # Nothing left to send, an export and an overlay make no Meta call: none reads
    # the counter.
    monkeypatch.setattr(tool.runner, "check_before_paying", no_counter)
    monkeypatch.setattr(tool.runner, "make_client", no_client)
    assert tool.main([*argv, "--yes"], tuning=START) == 0
    assert tool.main(["rims", "--folder", str(folder), "--yes"], tuning=START) == 0
    out = data.root / "results" / "set-b-1"
    assert tool.main(export_argv(data, out), tuning=START) == 0
    overlay = ["overlay", "--truth", str(data.truth), "--crop", "B01-1-1"]
    assert tool.main([*overlay, "--wheel", "1"], tuning=START) == 0


def test_a_failed_send_still_records_what_was_paid(tmp_path, monkeypatch, capsys):
    # The second crop's wheel call fails with Meta's 503 after its other two returned:
    # the first crop and those two calls are recorded, the failed one isn't billed.
    data = write_set_b(tmp_path, [truth_row("B01-1-1"), truth_row("B03-1-1")])
    seen = []
    lock = threading.Lock()

    def fail_the_fifth(phrase):
        with lock:  # the phrases run in parallel
            seen.append(phrase)
            fifth = len(seen) == 5
        if fifth:
            raise MetaApiError("HTTP 503", status=503)

    fake = FakeClient(set_b_sam(), on_segment=fail_the_fifth)
    spend, _ = counted(monkeypatch, fake, data.root)
    argv = ["segment", "--truth", str(data.truth), "--yes"]
    assert tool.main(argv, tuning=START) == 3
    assert capsys.readouterr().out.splitlines()[-1] == "failed: MetaApiError (HTTP 503)"
    assert spend.records == [
        (cost_of(sam_images=3), "set_b"),
        (cost_of(sam_images=2), "set_b"),
    ]
