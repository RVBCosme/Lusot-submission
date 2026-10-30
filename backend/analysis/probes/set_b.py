r"""Set B's rows for MS6's harness, and the early rim check (C314, C323, C327).

Run from backend/analysis:

    uv run python probes/set_b.py segment --truth F [--yes]
    uv run python probes/set_b.py export --truth F --out DIR --rules-version V
        [--geometry-default on|off|dropped] [--dropped-reason TOKEN]
    uv run python probes/set_b.py overlay --truth F --crop ID --wheel N
    uv run python probes/set_b.py rims --folder DIR [--yes]

F is MS2's truth.csv, <data>\set_b\dev\generated\truth.csv, with the crops in the
crops folder beside it (MS2's §5.9). Its pixels are the crop's own, so each row is
scaled to the image SAM sees, as blur_for_meta shrinks the crop (scale_row).

- segment: for each crop without saved results, once whatever its wheels, the face
  blur and then SAM for floodwater, wheel and wheel rim, saved under
  <data>/set_b_runs/<crop_id>/: sam/ (save_sam_results), then run.json, written last,
  with the crop's SHA-256, the phrases, the SAM model, the blur version and the size
  SAM saw. It spends Meta credits, so it prints the calls and the estimated cost
  first, at $0.0025 a call, and stops there unless given --yes. Its floodwater call
  repeats the one MS2's set_b_masks --water made: the duplicate is accepted (R135,
  M16).
- export: run.json and set_b.jsonl in --out, one set_b_row per wheel, from the saved
  results, with no Meta call. --geometry-default and --dropped-reason are recorded
  in run.json as dev_eval.py's export records them (MS6's C418). It prints the
  wheels, the measured count per variant, the wheels whose known-waterline fit fails
  check 9, by axis ratio, and k_estimate with its number of cars, beside the median
  of MS2's rim_edge_ratio, the dry rim mask's cross-check (MS2's C212; C310).
- overlay (P4): the crop as SAM saw it, with the wheel's SAM wheel mask and box, its
  linked rims, its known-waterline fit and the known waterline drawn, written to
  <data>/set_b_overlays/<crop_id>-wheel<N>.jpg. Task 17 checks by eye whether a rim
  that fails check 9 is the true rim.
- rims (C323): the early rim check, on the Commons car photos in DIR, before Set B
  exists. Each cars_meta.csv row joins attribution.csv by title, and that row's
  file_name names the photo in DIR\images\ (P2). cars_meta.csv's sha1 is the Commons
  original's, so it only names the saved folder. Each photo with tire_code_candidates
  and a credit line goes through the face blur, then SAM for wheel and wheel rim,
  saved under <data>/set_c_rims/<sha1>/ as segment saves a crop, and paid for as
  segment is. For each wheel it prints the linked rims, the whole rim's fit (no
  waterline: y_w lies below the image), check 9 at the candidates' bounds with SAM's
  box, and the rim-edge ratio 2 r ÷ (box height ÷ D) ÷ rim over the candidates. It is
  diagnostic only: nothing is tuned on it (C310), and dry cars give no depth.

<data> is LUSOT_DATA_DIR, or the runner's default. Every path given, and every crop,
photo and saved folder, is refused when it lies inside a folder named sealed, before
it is opened (C66). A data folder that segment, rims or overlay write under must lie
outside the repo (R131), and export's --out under the data folder, outside
set_b_runs and the repo. Nothing printed holds a photo's name, a path or a key, and
every line masks runs of 12 digits.

Exit codes: 0 done; 2 refused, invalid input, a rejected key, or a paid run without
--yes; 3 the run couldn't read or write what it needed, or a Meta call failed, with
the error's class only (R110). argparse's own usage errors exit 2 too.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import statistics
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from decimal import ROUND_UP, Decimal
from pathlib import Path
from typing import NoReturn

import cv2
import numpy as np

from lusot_analysis import export
from lusot_analysis.face_blur import blur_for_meta, decode_image, shrink_to_max_side
from lusot_analysis.meta_client import (
    SAM_MODEL,
    SPARK_MODEL,
    MetaApiError,
    MissingApiKey,
    SamResult,
)
from lusot_analysis.pipeline.geometry import (
    fit_rim,
    link_rims,
    rim_points,
    rim_size_bounds,
)
from lusot_analysis.pipeline.quality import quality_scores
from lusot_analysis.pipeline.references import water_found
from lusot_analysis.pipeline.saved import load_sam_results, save_sam_results
from lusot_analysis.pipeline.segment import box_xyxy, segment_all
from lusot_analysis.pipeline.types import KEY_REJECTED_STATUSES, ModelClient
from lusot_analysis.prompts import load_prompt
from lusot_analysis.rules import TireCode
from lusot_analysis.tuning import TUNING, Tuning


def _load_runner():
    """The offline runner, loaded from its file beside this one, as its tests load it."""
    path = Path(__file__).resolve().with_name("run_pipeline.py")
    spec = importlib.util.spec_from_file_location("run_pipeline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()
say = runner.say
SET_B_PHRASES = ("floodwater", "wheel", "wheel rim")
RIM_PHRASES = ("wheel", "wheel rim")  # a dry car has no water to find (C323)
SAM_CALL_USD = Decimal("0.0025")  # the estimated cost of one SAM call
CROPS = "crops"  # beside truth.csv (MS2's §5.9)
RUNS = "set_b_runs"  # under the data folder: each crop's saved results
OVERLAYS = "set_b_overlays"
RIMS = "set_c_rims"
RECORD = "run.json"  # a saved folder's record, written last
# A saved folder's key, from cars_meta.csv's sha1: letters and digits only.
_KEY = re.compile("[0-9A-Za-z]{1,64}")
# A bare file name, as export reads a crop's (R156).
_FILE_NAME = re.compile("[A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_-])?")
_TOKEN = re.compile("[a-z][a-z0-9_]{0,31}")
_MANILA = timezone(timedelta(hours=8))  # Manila keeps no daylight saving time
# The overlay's colours, in BGR.
_WHEEL_COLOUR = (0, 255, 255)
_RIM_COLOUR = (255, 255, 0)
_FIT_COLOUR = (255, 0, 255)
_WATERLINE_COLOUR = (0, 0, 255)


def read_wheels(path: Path, data_dir: Path) -> list[export.WheelRow]:
    """MS2's truth.csv at `path`, each row scaled to the image SAM sees.

    refuse_sealed runs on the truth file, the data folder and the crops folder beside
    the file before the file is opened, and on every crop it names before any is
    opened. A crop's factor is blur_for_meta's: the crop, decoded and shrunk as it
    shrinks it, has its width over the crop's (export.scale_row).
    """
    crops = path.parent / CROPS
    runner.refuse_sealed(path, data_dir, crops)
    rows = export.parse_truth(path.read_text(encoding="utf-8"))
    runner.refuse_sealed(*(crops / row.crop_file for row in rows))
    factors: dict[str, float] = {}
    for row in rows:
        if row.crop_id not in factors:
            bgr = decode_image((crops / row.crop_file).read_bytes())
            factors[row.crop_id] = shrink_to_max_side(bgr).shape[1] / bgr.shape[1]
    return [export.scale_row(row, factors[row.crop_id]) for row in rows]


def segment_command(args: argparse.Namespace, *, tuning: Tuning) -> int:
    """`segment`: SAM's three phrases for each crop not yet saved, after --yes."""
    data_dir = _data_dir()
    runner.refuse_sealed(args.truth, data_dir)
    runner.refuse_data_in_repo(data_dir)  # R131
    crops = _crops(args.truth, read_wheels(args.truth, data_dir))
    pending = [
        (path, data_dir / RUNS / crop_id)
        for crop_id, path in crops.items()
        if _pending(data_dir / RUNS / crop_id)
    ]
    _cost(pending, SET_B_PHRASES)
    saved = len(crops) - len(pending)
    say(f"crops: {len(crops)} in the truth file, {saved} already saved")
    if pending and not args.yes:
        _refuse_unpaid()
    _send_all(pending, SET_B_PHRASES)
    say(f"crops saved: {len(pending)}")
    return 0


def export_command(args: argparse.Namespace, *, tuning: Tuning) -> int:
    """`export`: run.json and set_b.jsonl in --out, from each crop's saved results.

    Every refusal comes before anything is written.
    """
    data_dir = _data_dir()
    runner.refuse_sealed(args.truth, args.out, data_dir)
    out = args.out.resolve()
    if out.is_relative_to(runner.REPO):
        _refuse("--out is inside the repo")
    if not out.is_relative_to(data_dir.resolve()):
        _refuse("--out must lie under the data folder")
    if out.is_relative_to((data_dir / RUNS).resolve()):  # beside the masks
        _refuse("--out must lie outside set_b_runs")
    if (args.geometry_default == "dropped") != (args.dropped_reason is not None):
        _refuse(
            "--geometry-default dropped needs --dropped-reason, and only it takes one"
        )
    # The harness would score another export's rows beside this run.json.
    if any((args.out / name).exists() for name in ("set_a.jsonl", "a_neg.jsonl")):
        _refuse("--out holds another export's rows: use a new folder")
    rows = read_wheels(args.truth, data_dir)
    if not rows:
        _refuse("the truth file holds no rows")
    saved = {}
    for crop_id, path in _crops(args.truth, rows).items():
        data = path.read_bytes()
        record, sam = _load(data_dir / RUNS / crop_id, data)
        saved[crop_id] = (record, sam, quality_scores(data).brightness)
    records = [record for record, _, _ in saved.values()]
    for key in ("phrases", "models", "blur_version"):
        if len({json.dumps(record[key], sort_keys=True) for record in records}) > 1:
            _refuse(
                "the saved results differ in their phrases, model or blur, which"
                " run.json states once"
            )

    written = []
    measured: Counter[str] = Counter(dict.fromkeys(export.SET_B_VARIANTS, 0))
    fails: Counter[str] = Counter()
    ratios: dict[str, list[float]] = {}
    for row in rows:
        _, sam, brightness = saved[row.crop_id]
        estimates = export.wheel_estimates(row, sam, brightness, tuning=tuning)
        written.append(export.set_b_row(row, estimates, water_found(sam["floodwater"])))
        measured.update(name for name, found in estimates.items() if found["measured"])
        known = estimates["known_waterline_uncalibrated"]
        if known["measured"] or known["fail"] == "rim_size":
            fit = export.known_waterline_fit(row, sam, tuning=tuning)
            if known["measured"]:
                ratios.setdefault(row.car_id, []).append(export.k_ratio(row, fit))
            else:
                fails[_band(fit.axis_ratio)] += 1

    prompt = load_prompt(runner.PROMPTS)
    # What the models were sent: SAM's phrases, its model and the blur come from the
    # saved records, and the prompt is the repo's, which Set B never sends.
    sent = {
        "models": {"sam": records[0]["models"]["sam"], "spark": SPARK_MODEL},
        "prompt_version": prompt.version,
        "schema_name": prompt.schema_name,
        "blur_version": records[0]["blur_version"],
        "phrases": records[0]["phrases"],
    }
    manifest = export.results_manifest(
        date=datetime.now(_MANILA).date().isoformat(),
        rules_version=args.rules_version,
        tuning=tuning,
        saved_run=sent,
        geometry_default=args.geometry_default,
        dropped_reason=args.dropped_reason,
        datasets={},
    )
    args.out.mkdir(parents=True, exist_ok=True)
    _write(args.out / "run.json", json.dumps(manifest, indent=2) + "\n")
    _write(args.out / "set_b.jsonl", "".join(json.dumps(r) + "\n" for r in written))

    say(f"wheels: {len(rows)}")
    say(f"measured: {json.dumps(dict(measured))}")
    say(
        "check 9 fails at the known waterline, by axis ratio:"
        f" {json.dumps(dict(sorted(fails.items())))}"
    )
    k = export.k_estimate(ratios)
    cars = sum(1 for found in ratios.values() if found)
    say(f"k_estimate: {'none' if k is None else f'{k:.4f}'} (cars: {cars})")
    edges = [row.rim_edge_ratio for row in rows if row.rim_edge_ratio is not None]
    median = f"median {statistics.median(edges):.4f}" if edges else "none"
    say(f"rim_edge_ratio, MS2's: {median} (wheels: {len(edges)})")
    say(
        "next: python eval/run_eval.py --from-saved --results <the --out folder> --write"
    )
    return 0


def overlay_command(args: argparse.Namespace, *, tuning: Tuning) -> int:
    """`overlay`: one wheel's SAM masks and known-waterline fit, drawn on its crop."""
    data_dir = _data_dir()
    runner.refuse_sealed(args.truth, data_dir)
    runner.refuse_data_in_repo(data_dir)  # it writes under the data folder
    rows = read_wheels(args.truth, data_dir)
    row = next(
        (
            found
            for found in rows
            if (found.crop_id, found.wheel) == (args.crop, args.wheel)
        ),
        None,
    )
    if row is None:
        _refuse("the truth file has no such crop and wheel")
    data = _crops(args.truth, [row])[row.crop_id].read_bytes()
    _, sam = _load(data_dir / RUNS / row.crop_id, data)
    canvas = blur_for_meta(data).bgr()  # the image SAM saw
    wheels = sam["wheel"].instances
    index = export.sam_wheel(row, wheels)
    if index is not None:
        wheel = wheels[index]
        _outline(canvas, wheel.mask, _WHEEL_COLOUR)
        x0, y0, x1, y1 = (round(value) for value in box_xyxy(wheel))
        cv2.rectangle(canvas, (x0, y0), (x1 - 1, y1 - 1), _WHEEL_COLOUR, 1)
        for rim in link_rims(wheels, sam["wheel rim"].instances)[index]:
            _outline(canvas, rim.mask, _RIM_COLOUR)
    fit = export.known_waterline_fit(row, sam, tuning=tuning)
    if fit is not None:
        box = ((fit.centre_x, fit.centre_y), fit.axes, fit.angle_deg)
        cv2.ellipse(canvas, box, _FIT_COLOUR, 1)
    line = round(row.waterline_row)
    cv2.line(canvas, (0, line), (canvas.shape[1] - 1, line), _WATERLINE_COLOUR, 1)
    out = data_dir / OVERLAYS / f"{row.crop_id}-wheel{row.wheel}.jpg"
    runner.refuse_sealed(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(cv2.imencode(".jpg", canvas)[1].tobytes())
    say("overlays written: 1")
    return 0


def rims_command(args: argparse.Namespace, *, tuning: Tuning) -> int:
    """`rims`: the early rim check on the Commons car photos in --folder (C323)."""
    data_dir = _data_dir()
    runner.refuse_sealed(args.folder, data_dir)
    runner.refuse_data_in_repo(data_dir)  # R131
    photos, skipped, listed = _rim_photos(args.folder)
    runner.refuse_sealed(*(path for _, path, _ in photos))
    for _, path, _ in photos:
        runner.refuse_sturm_live(path)  # C87: STURM never goes to Meta
    pending = [
        (path, data_dir / RIMS / key)
        for key, path, _ in photos
        if _pending(data_dir / RIMS / key)
    ]
    _cost(pending, RIM_PHRASES)
    say(
        f"photos: {listed} listed, {skipped['unmatched']} unmatched,"
        f" {skipped['no_codes']} without codes, {skipped['no_credit']} without a"
        f" credit line, {len(photos)} to check"
    )
    if pending and not args.yes:
        _refuse_unpaid()
    _send_all(pending, RIM_PHRASES)
    tally: Counter[str] = Counter()
    for number, (key, path, codes) in enumerate(photos, start=1):
        _, sam = _load(data_dir / RIMS / key, path.read_bytes())
        _say_rims(number, sam, codes, tuning, tally)
    say(
        f"wheels: {tally['wheels']}, one rim linked {tally['linked']}, fitted"
        f" {tally['fitted']}, check 9 passes {tally['passes']}"
    )
    return 0


def main(argv: list[str] | None = None, *, tuning: Tuning = TUNING) -> int:
    """The commands. `tuning` is what export, overlay and rims measure with.

    A test that pins start values passes START, since a default bound at import
    can't be patched (R128).
    """
    args = _parser().parse_args(argv)
    commands = {
        "segment": segment_command,
        "export": export_command,
        "overlay": overlay_command,
        "rims": rims_command,
    }
    try:
        return commands[args.command](args, tuning=tuning)
    except SystemExit as exc:  # a refusal, which said why
        return exc.code
    except export.InputError as exc:  # it names a row, or an opaque crop id, only
        say(f"invalid: {exc}")
        return 2
    except MissingApiKey:
        say("refused: MODEL_API_KEY is missing or too short")
        return 2
    except MetaApiError as exc:  # a RuntimeError; its message is never printed
        if exc.status in KEY_REJECTED_STATUSES:  # C73
            say(f"refused: Meta rejected the key or the account (HTTP {exc.status})")
            return 2
        status = "" if exc.status is None else f" (HTTP {exc.status})"
        say(f"failed: {type(exc).__name__}{status}")
        return 3
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # R110: the class only, as an error's text can hold a path or a value.
        say(f"failed: {type(exc).__name__}")
        return 3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    segment = commands.add_parser("segment", help="SAM's masks for each crop (paid)")
    segment.add_argument("--truth", type=Path, required=True)
    segment.add_argument("--yes", action="store_true", help="pay for the calls")
    rows = commands.add_parser("export", help="set_b.jsonl for MS6's harness (free)")
    rows.add_argument("--truth", type=Path, required=True)
    rows.add_argument("--out", type=Path, required=True)
    rows.add_argument("--rules-version", required=True)
    rows.add_argument(
        "--geometry-default", choices=("on", "off", "dropped"), default="on"
    )
    rows.add_argument("--dropped-reason", type=_token, metavar="TOKEN")
    overlay = commands.add_parser("overlay", help="a wheel's masks and fit (free)")
    overlay.add_argument("--truth", type=Path, required=True)
    overlay.add_argument("--crop", required=True, metavar="ID")
    overlay.add_argument("--wheel", type=int, choices=(1, 2), required=True)
    rims = commands.add_parser("rims", help="the rim check on Commons cars (paid)")
    rims.add_argument("--folder", type=Path, required=True)
    rims.add_argument("--yes", action="store_true", help="pay for the calls")
    return parser


def _token(text: str) -> str:
    """A lowercase token, so no free text reaches run.json."""
    if not _TOKEN.fullmatch(text):
        raise argparse.ArgumentTypeError("must be a lowercase token, such as a_reason")
    return text


def _refuse(message: str) -> NoReturn:
    say(f"refused: {message}")
    raise SystemExit(2)


def _refuse_unpaid() -> NoReturn:
    say("stopped: add --yes to pay for these calls")
    raise SystemExit(2)


def _data_dir() -> Path:
    return Path(os.environ.get("LUSOT_DATA_DIR") or runner.DATA_DIR)


def _crops(truth: Path, rows: Sequence[export.WheelRow]) -> dict[str, Path]:
    """Each crop's file, by crop id, in the truth file's order."""
    return {row.crop_id: truth.parent / CROPS / row.crop_file for row in rows}


def _pending(run_dir: Path) -> bool:
    """Whether `run_dir` still needs SAM's results: it has no run.json. A folder
    without one stopped partway, and is refused, since what to do with it is a
    choice to make by hand."""
    runner.refuse_sealed(run_dir)
    if (run_dir / RECORD).is_file():
        return False
    if run_dir.exists():
        _refuse("a saved folder without its run.json exists: remove it first")
    return True


def _cost(pending: Sequence[tuple[Path, Path]], phrases: Sequence[str]) -> None:
    """The calls to make and their cost, rounded up to the cent, so a paid run
    never reads as free."""
    calls = len(pending) * len(phrases)
    cost = (SAM_CALL_USD * calls).quantize(Decimal("0.01"), rounding=ROUND_UP)
    say(f"{calls} SAM calls, about ${cost}")


def _send_all(pending: Sequence[tuple[Path, Path]], phrases: Sequence[str]) -> None:
    """Send each pending photo, with one client built only when there is one."""
    if not pending:
        return
    client = runner.make_client()
    for path, run_dir in pending:
        _send(client, path.read_bytes(), phrases, run_dir)


def _send(
    client: ModelClient, data: bytes, phrases: Sequence[str], run_dir: Path
) -> None:
    """The face blur, then SAM for `phrases`, saved in `run_dir`: sam/ first, then
    run.json, so a folder without one is incomplete."""
    image = blur_for_meta(data)  # before any Meta call (C20)
    sam = segment_all(client, image, phrases)
    save_sam_results(run_dir, sam)
    record = {
        "photo_sha256": hashlib.sha256(data).hexdigest(),
        "phrases": list(phrases),
        "models": {"sam": SAM_MODEL},
        "blur_version": image.blur_version,
        "image": {"width": image.width, "height": image.height},
    }
    _write(run_dir / RECORD, json.dumps(record, indent=2) + "\n")


def _load(run_dir: Path, data: bytes) -> tuple[dict, dict[str, SamResult]]:
    """The record and SAM's results saved in `run_dir` for the photo `data`."""
    runner.refuse_sealed(run_dir)
    if not (run_dir / RECORD).is_file():
        _refuse("a crop has no saved SAM results: run `set_b.py segment` first")
    record = json.loads((run_dir / RECORD).read_text(encoding="utf-8"))
    if record["photo_sha256"] != hashlib.sha256(data).hexdigest():
        _refuse("saved results belong to another photo")
    return record, load_sam_results(run_dir)


def _band(axis_ratio: float) -> str:
    """The axis ratio's tenth, such as 0.6-0.7."""
    low = math.floor(axis_ratio * 10) / 10
    return f"{low:.1f}-{low + 0.1:.1f}"


def _outline(canvas: np.ndarray, mask: np.ndarray, colour: tuple[int, ...]) -> None:
    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
    )
    cv2.drawContours(canvas, contours, -1, colour, 1)


def _table(path: Path, needs: Sequence[str]) -> list[dict[str, str]]:
    """A CSV file's rows, a byte-order mark dropped, blank or missing cells as ""."""
    reader = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")))
    for column in needs:
        if column not in (reader.fieldnames or ()):
            raise export.InputError(f"{path.name} has no {column} column")
    return [{key: row[key] or "" for key in needs} for row in reader]


def _rim_photos(
    folder: Path,
) -> tuple[list[tuple[str, Path, tuple[TireCode, ...]]], Counter[str], int]:
    """The Commons car photos to check, each with its saved folder's key and its
    candidate codes; the rows skipped, by cause; and how many cars_meta.csv lists.

    Each cars_meta.csv row joins attribution.csv by title (P2). A row with no
    attribution.csv row is unmatched; one whose candidates give no code, or whose
    credit line is blank, is skipped too (R102), and none of them is sent.
    """
    meta = _table(folder / "cars_meta.csv", ("title", "sha1", "tire_code_candidates"))
    credits = {
        row["title"]: row
        for row in _table(
            folder / "attribution.csv", ("title", "file_name", "credit_line")
        )
    }
    photos = []
    skipped: Counter[str] = Counter(
        dict.fromkeys(("unmatched", "no_codes", "no_credit"), 0)
    )
    for number, row in enumerate(meta, start=1):
        credit = credits.get(row["title"])
        if credit is None:
            skipped["unmatched"] += 1
            continue
        codes = _candidates(row["tire_code_candidates"], number)
        if not codes:
            skipped["no_codes"] += 1
        elif not credit["credit_line"].strip():
            skipped["no_credit"] += 1
        else:
            key, name = row["sha1"], credit["file_name"]
            if not _KEY.fullmatch(key) or key in {found for found, _, _ in photos}:
                raise export.InputError(
                    f"cars_meta.csv row {number}: sha1 must be letters and digits,"
                    " once each"
                )
            if not _FILE_NAME.fullmatch(name) or ".." in name:
                raise export.InputError(
                    f"cars_meta.csv row {number}: its file_name in attribution.csv"
                    " must be a bare file name"
                )
            photos.append((key, folder / "images" / name, codes))
    return photos, skipped, len(meta)


def _candidates(text: str, number: int) -> tuple[TireCode, ...]:
    """A tire_code_candidates cell's codes, separated by spaces, `;`, `,` or `|`."""
    codes = []
    for part in re.split(r"[\s;,|]+", text):
        if not part:
            continue
        try:
            codes.append(TireCode.parse(part))
        except ValueError:
            raise export.InputError(
                f"cars_meta.csv row {number}: a tire_code_candidates entry isn't a"
                " metric radial code"
            ) from None
    return tuple(codes)


def _say_rims(
    number: int,
    sam: Mapping[str, SamResult],
    codes: Sequence[TireCode],
    tuning: Tuning,
    tally: Counter[str],
) -> None:
    """Photo `number`'s wheels, one line each, with numbers only."""
    wheels = sam["wheel"].instances
    links = link_rims(wheels, sam["wheel rim"].instances)
    for index, (wheel, rims) in enumerate(zip(wheels, links, strict=True), start=1):
        tally["wheels"] += 1
        line = f"photo {number} wheel {index}: rims linked {len(rims)}"
        fit = None
        if len(rims) == 1:
            tally["linked"] += 1
            # No waterline: y_w lies T below the image, so every point is fitted.
            below = rims[0].mask.shape[0] + tuning.touch_tolerance_px
            fit = fit_rim(rim_points(rims[0].mask, below, tuning.touch_tolerance_px))
            if fit is None:
                line += ", no fit"
        if fit is not None:
            tally["fitted"] += 1
            x0, y0, x1, y1 = box_xyxy(wheel)
            low, high = rim_size_bounds(codes, fit.axis_ratio, tuning)
            size = fit.width_x / (x1 - x0)
            passes = low <= size <= high
            tally["passes"] += passes
            # Each candidate's scale is the box's height over its diameter, D.
            edges = [
                2 * fit.r / ((y1 - y0) / (2 * code.radius_in)) / code.rim_in
                for code in codes
            ]
            line += (
                f", fit points {fit.points}, axis ratio {fit.axis_ratio:.3f}, check 9"
                f" {'passes' if passes else 'fails'} ({size:.3f} against {low:.3f} to"
                f" {high:.3f}), rim-edge ratio {min(edges):.3f} to {max(edges):.3f}"
            )
        say(line)


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
