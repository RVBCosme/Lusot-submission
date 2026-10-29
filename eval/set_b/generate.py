# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["numpy==2.5.4", "opencv-python-headless==4.14.0.94", "py7zr==1.1.4"]
# ///
r"""Set B's generator: four crops per car photo, each with its drawn water and its
wheels' truth, for the development cars; and Rene's sealed run for the final cars
(spec §5.6; C205, C210 to C214, C218).

For each photo of a kept car, in cars.csv's order, it reads set_b_masks' files by name
from <masks>\<photo stem>\: blurred.jpg and the vehicle, wheel and wheel rim masks. It
picks the wheels, links each one's rim, plans the crops and draws them (C211, C212).

Development cars, from the repo root (Claude runs this one):
    uv run --locked --script eval/set_b/generate.py
        --cars <data>\set_b\dev\cars.csv --masks <data>\set_b\dev\masks
        --out <data>\set_b\dev\generated
--out, an absolute path, must not exist yet. It gets crops\<crop_id>.jpg, the drawn
water as water\<crop_id>.png, overlays\<crop_id>.jpg (the drawn line in red and each
chosen wheel's box in yellow), truth.csv and files.txt.

Final cars, Rene alone, from his own Windows PowerShell window (C202, C214):
    uv run --locked --script eval/set_b/generate.py --final
        --cars <data>\set_b\sealed\cars.csv --masks <data>\set_b\sealed\masks
        --dev-cars <data>\set_b\dev\cars.csv --dev-masks <data>\set_b\dev\masks
        --archive <data>\sealed\lusot-sealed-set-b.7z
        --record eval\data\records\<date>-set-b-final.json
Every path but the record's is absolute, and the archive's folder must exist. It checks
cars.csv, the files the archive will hold and C214's overlap with the development cars,
generates in memory and encodes the record, and only then asks for the password. No
crop, truth row or overlay is ever written in plaintext: they go into the archive in
one pass (C205), with the record, cars.csv, the raw photos, the owners' OKs and the
masks. The committed record follows. A stop before the password writes nothing.

It prints each problem as <ref> <column>: <kind>, each warning as <ref> <fact>=<value>,
then the drops by cause, the cars, photos, crops and wheels, and the seconds; --final
also prints the archive's size and SHA-256. --final names a final car by its row in
cars.csv, never by its id, and prints no model, tire code, file name or path. A stop
on an overlap prints overlap: <dev car id>, or dev row <n>.

Exit codes: 0 written; 1 a problem in cars.csv or the files to archive, an overlap with
the development cars, a record that would hold an id, or an error, of which only the
class prints; 2 refused: a path rule, no console, an output that exists, a missing
input or archive folder, or the password.
"""

import argparse
import os
import re
import sys
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))

# photos first: it sets OpenCV's 50 MP decode cap before cv2 loads, which crops, water
# and cv2 below would otherwise load without it (R25, S-R26). So isort's order, which
# would put it after them, is turned off for this block.
import photos  # noqa: I001

import archive
import audit
import cars
import crops
import cv2
import events
import formats
import guards
import numpy as np
import record_io
import table
import tires
import truth
import water
import wheels
from cars import CarsCheck
from crops import Crop
from table import Finding

REPO = Path(__file__).resolve().parents[2]
SPLITS = ("dev", "sealed")
# The files set_b_masks writes for each photo, besides blurred.jpg: one npz per phrase.
MASK_FILES = (
    "sam_vehicle_masks.npz",
    "sam_wheel_masks.npz",
    "sam_wheel_rim_masks.npz",
)
JPEG_QUALITY = 95
RED, YELLOW = (0, 0, 255), (0, 255, 255)  # BGR
_DIGEST = r"[0-9a-f]{64}"


@dataclass
class Generated:
    """What generate made: the crops; their truth rows, in formats.TRUTH_COLUMNS, one
    per wheel per crop; the photos and shrunk crops dropped, by cause; the chosen
    wheels, of the photos that gave a crop, with no linked rim; and the seconds."""

    crops: list[Crop]
    rows: list[dict[str, str]]
    drops: Counter[str]
    wheels_without_rim: int
    seconds: float


def generate(cars: CarsCheck, masks: Path, *, split: str) -> Generated:
    """The crops and truth of each photo of a car cars.drops keeps, in cars.csv's order,
    with split, dev or sealed, in each row. The caller has refused a check with
    problems, so each kept tire code is a size.

    A photo is dropped as no_masks when one of its four files is missing, undecodable
    when blurred.jpg doesn't decode, or as wheels.pick_wheels' no_vehicle or no_wheel.
    Each chosen wheel is linked to its rim, and rim_edge_ratio is measured on the
    unshrunk masks, since a ratio holds no pixels. Then each crop crops.plan_crops
    plans is made, and one make_crop refuses as crops.ShrinkOutOfRange is dropped as
    shrink_out_of_range (S-R27).
    """
    if split not in SPLITS:
        raise ValueError("split is dev or sealed")
    started = time.monotonic()
    made: list[Crop] = []
    rows: list[dict[str, str]] = []
    drops: Counter[str] = Counter()
    without_rim = 0
    for row in cars.rows:
        if row["car_id"] in cars.drops:
            continue
        loaded = _load(masks / Path(row["photo_file"]).stem)
        if isinstance(loaded, str):
            drops[loaded] += 1
            continue
        image, vehicles, found, rims = loaded
        chosen = wheels.pick_wheels(vehicles, found, image.shape[:2])
        if isinstance(chosen, str):
            drops[chosen] += 1
            continue
        size = tires.parse_tire_code(row["tire_code"])
        diameter = tires.diameter_in(size)
        ratios = []
        for wheel in chosen:
            rim = wheels.link_rim(wheel, rims)
            px_per_in = truth.wheel_geom(wheel.mask, diameter).px_per_in
            rim_mask = None if rim is None else rim.mask
            ratios.append(truth.rim_edge_ratio(rim_mask, px_per_in, size.rim_in))
        plan_rng, water_rng = crops.photo_rngs(row["photo_file"])
        number = _photo_number(row["photo_file"])
        kept = 0
        for plan in crops.plan_crops(row["car_id"], number, diameter, plan_rng):
            try:
                crop = crops.make_crop(
                    image, [wheel.mask for wheel in chosen], diameter, plan, water_rng
                )
            except crops.ShrinkOutOfRange:
                drops["shrink_out_of_range"] += 1
                continue
            made.append(crop)
            rows += _truth_rows(row, crop, size, diameter, ratios, split)
            kept += 1
        if kept:
            without_rim += ratios.count(None)
    return Generated(made, rows, drops, without_rim, time.monotonic() - started)


def draw_overlay(crop: Crop) -> np.ndarray:
    """A copy of the crop with each chosen wheel's box in yellow, then the waterline's
    row in each column in red, the first row of water there, as its truth has it (C213's
    review)."""
    image = crop.image.copy()
    height, width = image.shape[:2]
    for geom, _ in crop.wheels:
        corners = (geom.x0, geom.y0), (geom.x1 - 1, geom.y1 - 1)  # half-open box
        cv2.rectangle(image, *corners, YELLOW, 1)
    rows = truth.line_rows([geom for geom, _ in crop.wheels], crop.plan.depth_in, width)
    columns = np.flatnonzero((rows >= 0) & (rows < height))
    image[rows[columns], columns] = RED
    return image


def counts(check: CarsCheck, made: Generated) -> dict:
    """The record's counts (C214, addition 1), all numbers keyed by fact values, never
    by an id: cars, photos, crops and wheels that reach truth.csv, so a dropped car
    counts under drops alone; wheels_without_rim; drops, the cars' causes and the
    photos' and crops'; warnings by kind; and the crops by band, size_bin,
    vehicle_type and view."""
    rows = made.rows
    each_crop = list({row["crop_id"]: row for row in rows}.values())
    found = {
        "cars": len({row["car_id"] for row in rows}),
        "photos": len({row["photo_file"] for row in rows}),
        "crops": len(each_crop),
        "wheels": len({(row["photo_file"], row["wheel"]) for row in rows}),
        "wheels_without_rim": made.wheels_without_rim,
        "drops": dict(Counter(check.drops.values()) + made.drops),
        "warnings": dict(
            Counter(f"{fact.fact}={fact.value}" for fact in check.warnings)
        ),
    }
    for column in ("band", "size_bin", "vehicle_type", "view"):
        found[column] = dict(Counter(row[column] for row in each_crop))
    return found


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Set B's crops, drawn water and truth (C211, C212). Without "
        "--final, for the development cars, into --out. With --final, Rene only "
        "(C214): the final cars into a write-once encrypted archive, then the "
        "committed record, printing rows and counts, never a final car's id."
    )
    parser.add_argument(
        "--final", action="store_true", help="Rene's final-car run (C202, C214)"
    )
    for flag, text in (
        ("--cars", "cars.csv, an absolute path; with --final, inside set_b\\sealed"),
        ("--masks", "set_b_masks' folder for those cars, an absolute path"),
    ):
        parser.add_argument(flag, required=True, type=Path, help=text)
    for flag, text in (
        ("--out", "without --final: the folder to create, an absolute path"),
        ("--dev-cars", "with --final: the development cars.csv, an absolute path"),
        ("--dev-masks", "with --final: the development masks, an absolute path"),
        (
            "--archive",
            (
                "with --final: the archive to create, an absolute path inside a "
                "folder named sealed, such as lusot-sealed-set-b.7z"
            ),
        ),
        (
            "--record",
            "with --final: the committed record to create, under eval\\data\\records",
        ),
    ):
        parser.add_argument(flag, type=Path, help=text)
    args = parser.parse_args(argv)
    finals = (args.dev_cars, args.dev_masks, args.archive, args.record)
    if args.final:
        if args.out is not None or None in finals:
            parser.error(
                "--final takes --dev-cars, --dev-masks, --archive and --record, "
                "and no --out"
            )
        return guards.quiet(lambda: _final(args))
    if args.out is None or any(path is not None for path in finals):
        parser.error("without --final, give --out and none of --final's flags")
    return guards.quiet(lambda: _dev(args))


def _dev(args: argparse.Namespace) -> int:
    # The path rules, on the strings (C222, addition 2), then --out, which must not
    # exist yet.
    guards.refuse_sealed(args.cars, args.masks, args.out)
    for flag, path in (
        ("--cars", args.cars),
        ("--masks", args.masks),
        ("--out", args.out),
    ):
        if not path.is_absolute():
            return _refuse(f"{flag} must be absolute")
    if args.out.exists():
        print("--out exists: delete it before rerunning", file=sys.stderr)
        return 2
    check = _check(args.cars, side="dev")
    if check is None:
        return 1
    made = generate(check, args.masks, split="dev")
    hashes = {}
    for crop in made.crops:
        crop_id = crop.plan.crop_id
        for name, data in (
            (f"crops/{crop_id}.jpg", _jpeg(crop.image)),
            (f"water/{crop_id}.png", _png(crop.water)),
            (f"overlays/{crop_id}.jpg", _jpeg(draw_overlay(crop))),
        ):
            hashes[name] = table.write_new(args.out / name, data)
    truth_csv = table.csv_bytes(formats.TRUTH_COLUMNS, made.rows)
    hashes["truth.csv"] = table.write_new(args.out / "truth.csv", truth_csv)
    listing = "".join(f"{hashes[name]}  {name}\n" for name in sorted(hashes))
    table.write_new(args.out / "files.txt", listing.encode("ascii"))
    _print_counts(counts(check, made), made.seconds)
    return 0


def _final(args: argparse.Namespace) -> int:
    # 1. The path rules, on the strings alone (C202, C222, addition 2, S-R13, S-R19).
    for flag, path in (
        ("--cars", args.cars),
        ("--masks", args.masks),
        ("--archive", args.archive),
    ):
        guards.require_sealed(path, flag=flag)
    guards.refuse_sealed(args.dev_cars, args.dev_masks, args.record)
    for flag, path in (
        ("--cars", args.cars),
        ("--masks", args.masks),
        ("--dev-cars", args.dev_cars),
        ("--dev-masks", args.dev_masks),
        ("--archive", args.archive),
    ):
        if not path.is_absolute():
            return _refuse(f"{flag} must be absolute")
    if not _archive_name_ok(args.archive):
        return _refuse("--archive name")

    # 2. Rene's own console. 3. The outputs, which must not exist yet, and the inputs
    # and the archive's folder, which must (addition 2). Each one found is a refusal.
    guards.require_console()
    stops = [
        f"{flag} exists: delete it before rerunning"
        for flag, path in (("--archive", args.archive), ("--record", args.record))
        if path.exists()
    ]
    stops += [
        f"{flag} missing"
        for flag, found in (
            ("--cars", args.cars.is_file()),
            ("--masks", args.masks.is_dir()),
            ("--dev-cars", args.dev_cars.is_file()),
            ("--dev-masks", args.dev_masks.is_dir()),
        )
        if not found
    ]
    if not args.archive.parent.is_dir():
        stops.append("--archive folder missing: create it first")
    for line in stops:
        print(line, file=sys.stderr)
    if stops:
        return 2

    # 4. cars.csv, then each file the archive will hold, found by a stat, then C214's
    # overlap check. Each stop comes before the password, and names rows only.
    check = _check(args.cars, side="final")
    if check is None:
        return 1
    # A car without its owner's OK leaves nothing in the archive but its row.
    archived = [
        row for row in check.rows if check.drops.get(row["car_id"]) != "no_consent"
    ]
    photos_folder = args.cars.parent / "photos"
    problems = [
        Finding(f"row {row['#']}", "photo_file", "missing")
        for row in archived
        if not (photos_folder / row["photo_file"]).is_file()
    ]
    listing, mask_files, missing = _masks_listing(args.masks)
    for problem in problems + missing:
        print(problem)
    if problems or missing:
        return 1
    dev = table.read_table(args.dev_cars)
    absent = [
        Finding("dev cars log", column, "missing_column")
        for column in ("car_id", "photo_file")
        if column not in dev.columns
    ]
    for problem in absent:
        print(problem)
    if absent:
        return 1
    found = _overlaps(check, args.masks, dev.rows, args.dev_masks)
    for ref in found:
        print(f"overlap: {ref}")
    if found:
        return 1

    # 5. Generation in memory, then the record's core, encoded before the password, so
    # one that would hold an id stops the run before any archive exists (S-R16).
    cars_bytes = args.cars.read_bytes()
    made = generate(check, args.masks, split="sealed")
    tally = counts(check, made)
    core = record_io.set_b_final_record(
        repo=REPO,
        counts=tally,
        generator_version=water.GENERATOR_VERSION,
        generator_seed=crops.GENERATOR_SEED,
        inputs={
            "cars": table.sha256_bytes(cars_bytes),
            "masks_files": table.sha256_bytes(listing),
            "dev_cars": table.sha256_file(args.dev_cars),
        },
    )
    try:
        core_bytes = record_io.record_bytes(core)
    except ValueError as error:
        print(error.args[0])
        return 1
    members = _members(core_bytes, made, args, cars_bytes, archived, mask_files)

    # 6. The password, C202's confirmation, then the archive in one pass (C205, C206).
    password = guards.ask_password()
    facts = archive.write_sealed_archive(args.archive, password, members)

    # 7. The committed record: the core and the archive's facts (C216).
    record_io.write_record(
        args.record, core | {"archive": record_io.archive_block(facts)}
    )
    _print_counts(tally, made.seconds)
    print(f"archive {facts.size} bytes sha256 {facts.sha256}")
    return 0


def _check(path: Path, *, side: str) -> CarsCheck | None:
    """check_cars, with each problem and then each warning printed. None when there was
    a problem, or the CSV is malformed, whose finding names a row or column number."""
    try:
        check = cars.check_cars(path, side=side)
    except table.MalformedCsv as error:
        print(error.args[0])
        return None
    for line in [*check.problems, *check.warnings]:
        print(line)
    return None if check.problems else check


def _load(folder: Path) -> tuple | str:
    """A photo's decoded blurred image and its vehicles, wheels and rims, each read by
    name from its masks folder, or the cause it is dropped."""
    paths = [folder / "blurred.jpg", *(folder / name for name in MASK_FILES)]
    if not all(path.is_file() for path in paths):
        return "no_masks"
    data = np.frombuffer(paths[0].read_bytes(), np.uint8)
    try:
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    except cv2.error:  # an empty buffer, or a size over the cap, raises
        image = None
    if image is None:
        return "undecodable"
    return image, *(wheels.load_instances(path) for path in paths[1:])


def _truth_rows(
    row: Mapping[str, str],
    crop: Crop,
    size: tires.TireSize,
    diameter: float,
    ratios: Sequence[float | None],
    split: str,
) -> list[dict[str, str]]:
    """The crop's truth rows, one per wheel, 1 the leftmost (§5.9). Its rows and pixels
    are the crop's own. true_depth_in, diameter_in and rim_edge_ratio hold 4 decimals at
    most (addition 8), and rim_edge_ratio is blank without a rim."""
    plan = crop.plan
    found = []
    for number, ((geom, measured), ratio) in enumerate(
        zip(crop.wheels, ratios, strict=True), start=1
    ):
        left, right, line, depth = measured
        found.append(
            {
                "crop_id": plan.crop_id,
                "car_id": row["car_id"],
                "split": split,
                "photo_file": row["photo_file"],
                "crop_file": f"{plan.crop_id}.jpg",
                "wheel": str(number),
                "view": row["view"],
                "vehicle_type": row["vehicle_type"],
                "tire_code": row["tire_code"],
                "rim_in": str(size.rim_in),
                "diameter_in": _decimals(diameter),
                "crop_scale": str(crop.scale),
                "size_bin": "small" if plan.shrink else "full",
                "x0": str(geom.x0),
                "y0": str(geom.y0),
                "x1": str(geom.x1),
                "y1": str(geom.y1),
                "ground_row": str(geom.ground_row),
                "top_row": str(geom.top_row),
                "px_per_in": str(geom.px_per_in),
                "waterline_left_row": str(left),
                "waterline_right_row": str(right),
                "waterline_row": str(line),
                "true_depth_in": _decimals(depth),
                "band": plan.band,
                "rim_edge_ratio": "" if ratio is None else _decimals(ratio),
                "generator_version": water.GENERATOR_VERSION,
            }
        )
    return found


def _photo_number(photo_file: str) -> int:
    """The photo's number in its file name, as B01-2.jpg gives 2."""
    return int(cars.PHOTO_FILE.fullmatch(photo_file).group(1))


def _decimals(value: float) -> str:
    return str(round(value, 4))


def _jpeg(image: np.ndarray) -> bytes:
    return cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])[
        1
    ].tobytes()


def _png(mask: np.ndarray) -> bytes:
    return cv2.imencode(".png", mask.astype(np.uint8) * 255)[1].tobytes()


def _masks_listing(masks: Path) -> tuple[bytes, list[str], list[Finding]]:
    """The final masks' files.txt as read, the paths it lists, and its problems: the
    file missing, or a line that isn't `<sha256>  <path>` with a path inside the masks
    folder (bad_line), or names no file there (missing), each by its line number."""
    path = masks / "files.txt"
    if not path.is_file():
        return b"", [], [Finding("masks", "files.txt", "missing")]
    data = path.read_bytes()
    names, problems = [], []
    for number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        digest, _, name = line.partition("  ")
        where = f"files.txt line {number}"
        if not (
            re.fullmatch(_DIGEST, digest)
            and "\\" not in name
            and cars.inside_folder(name)
        ):
            problems.append(Finding("masks", where, "bad_line"))
        elif not (masks / name).is_file():
            problems.append(Finding("masks", where, "missing"))
        else:
            names.append(name)
    return data, names, problems


def _overlaps(
    check: CarsCheck,
    masks: Path,
    dev_rows: Sequence[Mapping[str, str]],
    dev_masks: Path,
) -> list[str]:
    """C214's overlap check: the development rows a final car shares an id or a photo
    with, each named as its development car id, or as dev row <n> when its id isn't a
    development car's odd number, so no final car id prints.

    A dev row shares an id when its car_id is a final car's. It shares a photo when its
    blurred photo's SHA-256 equals a final blurred photo's, or its dHash is near one's
    (§5.5). Each blurred photo is read by name as <masks>/<stem>/blurred.jpg, and one
    that isn't there, as for a car without its owner's OK, has nothing to compare. An
    odd final car number is check_cars' wrong_side problem, which stops the run first.
    """
    finals = []
    for row in check.rows:
        blurred = masks / Path(row["photo_file"]).stem / "blurred.jpg"
        if blurred.is_file():
            finals.append(photos.photo_facts(blurred.read_bytes()))
    final_ids = {row["car_id"] for row in check.rows}
    found = []
    for row in dev_rows:
        shared = row["car_id"] in final_ids
        if not shared and cars.PHOTO_FILE.fullmatch(row["photo_file"]):
            blurred = dev_masks / Path(row["photo_file"]).stem / "blurred.jpg"
            if blurred.is_file():
                facts = photos.photo_facts(blurred.read_bytes())
                shared = any(
                    facts.sha256 == other.sha256
                    or events.near(facts.dhash, other.dhash)
                    for other in finals
                )
        if shared:
            found.append(_dev_ref(row))
    return list(dict.fromkeys(found))


def _dev_ref(row: Mapping[str, str]) -> str:
    """A development row's name: its car id when that is a development car's, B and an
    odd two-digit number, or else dev row <n>."""
    car = row["car_id"]
    if re.fullmatch(formats.CAR_ID, car) and int(car[1:]) % 2 == 1:
        return car
    return f"dev row {row['#']}"


def _members(
    core: bytes,
    made: Generated,
    args: argparse.Namespace,
    cars_bytes: bytes,
    archived: Sequence[Mapping[str, str]],
    mask_files: Sequence[str],
) -> list[tuple[str, bytes | Path]]:
    """The archive's members, in step 6's order: the core record, the truth and the
    crops, from memory; then cars.csv as read; then by name each archived row's raw
    photo, each distinct owner's OK once, at its path relative to cars.csv with \\
    turned to / and compared by casefold (addition 3), and each file the masks'
    files.txt lists."""
    members: list[tuple[str, bytes | Path]] = [
        ("records/set_b_final.json", core),
        ("set_b/truth.csv", table.csv_bytes(formats.TRUTH_COLUMNS, made.rows)),
    ]
    members += [
        (f"set_b/crops/{crop.plan.crop_id}.jpg", _jpeg(crop.image))
        for crop in made.crops
    ]
    members.append(("set_b/source/cars.csv", cars_bytes))
    folder = args.cars.parent
    members += [
        (
            f"set_b/source/photos/{row['photo_file']}",
            folder / "photos" / row["photo_file"],
        )
        for row in archived
    ]
    seen = set()
    for row in archived:
        arcname = "set_b/source/" + row["consent_file"].replace("\\", "/")
        if arcname.casefold() not in seen:
            seen.add(arcname.casefold())
            members.append((arcname, folder / row["consent_file"]))
    members += [
        (f"set_b/source/masks/{name}", args.masks / name) for name in mask_files
    ]
    return members


def _archive_name_ok(path: Path) -> bool:
    """True when the archive's path holds no ":" after its drive, and its name is one
    the sealed run's audit opens (S-R18) and holds no id-shaped token, since the
    committed record holds it (S-R16). The rules are audit's and record_io's, so the
    tools never drift apart (S-R19)."""
    return (
        ":" not in os.path.splitdrive(str(path))[1]
        and audit.ARCHIVE_NAME.fullmatch(path.name) is not None
        and record_io.ID_TOKEN.search(path.name) is None
    )


def _print_counts(found: Mapping, seconds: float) -> None:
    """The drops by cause, then the cars, photos, crops and wheels, then the seconds."""
    drops = " ".join(f"{cause}={n}" for cause, n in sorted(found["drops"].items()))
    print(f"drops: {drops or 'none'}")
    keys = ("cars", "photos", "crops", "wheels", "wheels_without_rim")
    print(" ".join(f"{key}={found[key]}" for key in keys))
    print(f"seconds={seconds:.1f}")


def _refuse(text: str) -> int:
    print(f"refused: {text}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
