r"""Set B's masks: each car photo face-blurred, then SAM's vehicle, wheel and wheel rim
masks (spec §5.6; C200, C210, C213, C214, C218).

Run from the repo root, with MODEL_API_KEY set for that one command:

    uv run --locked --directory backend/analysis python probes/set_b_masks.py
        --cars <data>\set_b\dev\cars.csv --photos <data>\set_b\dev\photos
        --out <data>\set_b\dev\masks

<data> is the full data path, since uv's --directory changes the working folder. A
relative --out is refused: it would put blurred photos inside the repo.

It sends each photo cars.csv names whose car is on this side (C210) and has its owner's
OK on record (C218). blur_for_meta blurs the faces and shrinks the photo to 1,600 px at
most, then SAM gets one call per phrase, one call at a time on one client. The photo's
folder, <out>\<photo stem>\, gets blurred.jpg, each phrase's raw text and masks, and
meta.json last; <out>\files.txt names every file written, with its SHA-256. A photo
whose meta.json exists is skipped, so a rerun pays nothing.

With --water <data>\set_b\dev\generated\truth.csv in place of --cars and --photos, each
development crop gets one floodwater call, saved in <out>\water\<crop_id>\, for the
freeze check (C213). A crop is segmented again whenever its bytes or the generator's
version change.

--final, with the paths inside set_b\sealed\, is Rene's alone (C202, C214). It starts
only from his own console, asks him to type yes before any call, and names a photo by
its row in cars.csv, never by its car.

It prints each skip as <car or photo> skipped: <cause>, the planned calls and their
cost, then photos=<n> skipped=<k> sam_calls=<c> seconds=<s>. Exit codes: 0 done; 1 a
problem in cars.csv or truth.csv, printed as <ref> <column>: <kind>, or a MetaApiError,
printed as its class and status only, with the photos finished before it kept, or any
other failure, printed as its class only; 2 a refusal, or a missing MODEL_API_KEY.

MS1's calls are used as on main, positionally: blur_for_meta(data) and
MetaClient.segment(image, phrase). save_result re-implements run_probe.save_sam, since
importing run_probe would read its data folder setting at import.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from functools import partial
from pathlib import Path

import numpy as np

from lusot_analysis.face_blur import BlurredImage, UndecodableImage, blur_for_meta
from lusot_analysis.meta_client import (
    MetaApiError,
    MetaClient,
    MissingApiKey,
    SamResult,
)

PHRASES = ("vehicle", "wheel", "wheel rim")
WATER_PHRASE = "floodwater"
# SAM's price per image, from dev.meta.ai on Oct 26, as run_probe has it.
USD_PER_CALL = 0.0025
# The columns read from cars.csv and truth.csv, as eval/data/formats.py names them.
CARS_READ = ("car_id", "photo_file", "consent_file")
TRUTH_READ = ("crop_id", "crop_file", "generator_version")
CAR_ID = re.compile(r"B[0-9]{2}")
PHOTO_NAME = re.compile(r"B[0-9]{2}-[0-9]{1,2}\.(jpg|jpeg|png)", re.IGNORECASE)
# A crop's id is its car, its photo, then its number (§5.9), inside C221's pattern.
CROP_ID = re.compile(r"B[0-9]{2}-[0-9]{1,2}-[0-9]{1,3}")

# A call to make: the label a skip prints, the file to send, its folder under --out,
# and the function that sends it.
type Job = tuple[str, Path, Path, Callable[[MetaClient, bytes, Path], int]]


# The seven guards below are eval/data/guards.py's, copied verbatim, because this
# package can't import eval/ (C200). eval/data/tests/test_guard_copies.py checks that
# each copy's ast.dump matches its source. C222 names MS3a's runner helper here
# instead; it isn't on main yet, and it replaces these copies when it is (a D7 default).


def is_sealed_name(name: str) -> bool:
    """True when one path part names sealed as Windows reads it: in any case, by its
    name before any ":" (so the NTFS stream sealed::$INDEX_ALLOCATION counts), and
    without trailing dots and spaces (so "sealed." and "sealed " count)."""
    return name.split(":", 1)[0].rstrip(". ").casefold() == "sealed"


def refuse_sealed(*paths: str | os.PathLike) -> None:
    """Exit 2 when any part of a path, as given or made absolute and normalised, names
    sealed (C222). It reads the strings only, never the disk."""
    for path in paths:
        given = os.fspath(path)
        for form in (given, os.path.normpath(os.path.abspath(given))):
            if any(is_sealed_name(part) for part in form.replace("\\", "/").split("/")):
                print("refused: path inside a folder named sealed", file=sys.stderr)
                sys.exit(2)


def require_sealed(path: str | os.PathLike, *, flag: str) -> None:
    """Exit 2 unless a part of the path, made absolute and normalised, names sealed
    (C202). It reads the string only, never the disk."""
    normal = os.path.normpath(os.path.abspath(os.fspath(path)))
    if not any(is_sealed_name(part) for part in normal.replace("\\", "/").split("/")):
        print(f"refused: {flag} must be inside a folder named sealed", file=sys.stderr)
        sys.exit(2)


def console_ok(*, is_console: Callable[[int], bool] | None = None) -> bool:
    """True when stdin and stdout are both consoles (C202).

    On Windows the default check is GetConsoleMode, which fails on NUL and on a pipe;
    os.isatty there calls NUL a terminal. Elsewhere it is os.isatty.
    """
    if is_console is None and sys.platform == "win32":
        import msvcrt
        from ctypes import byref, windll, wintypes

        def get_console_mode(fd: int) -> bool:
            mode = wintypes.DWORD()
            try:
                handle = wintypes.HANDLE(msvcrt.get_osfhandle(fd))
            except OSError:  # the descriptor isn't open
                return False
            return windll.kernel32.GetConsoleMode(handle, byref(mode)) != 0

        is_console = get_console_mode
    elif is_console is None:
        is_console = os.isatty
    return is_console(0) and is_console(1)


def require_console() -> None:
    """Exit 2 unless stdin and stdout are both a console, as in Rene's window (C202)."""
    if not console_ok():
        print(
            "refused: run this yourself, in a Windows PowerShell window",
            file=sys.stderr,
        )
        sys.exit(2)


def confirm(summary: str, *, ask: Callable[[str], str] | None = None) -> None:
    """Print the summary, then exit 2 unless Rene types yes (C202).

    ask defaults to input, looked up at each call so tests can replace it.
    """
    if ask is None:
        ask = input
    print(summary)
    if ask("Type yes to continue: ").strip() != "yes":
        print("stopped: nothing was done", file=sys.stderr)
        sys.exit(2)


def quiet(run: Callable[[], int]) -> int:
    """Return run(). Any exception, and Ctrl+C, prints only its class and returns 1, so
    no traceback names a photo. SystemExit passes through."""
    try:
        return run()
    except (Exception, KeyboardInterrupt) as error:  # noqa: BLE001
        print(f"stopped: {type(error).__name__}", file=sys.stderr)
        return 1


def check_cars(cars: Path, *, final: bool) -> tuple[list[str], dict[str, str]]:
    """The photo files to send, in cars.csv's order, and each skipped car with its
    cause (§5.6, C210, C218).

    It reads only car_id, photo_file and consent_file. A car is skipped as wrong_side
    when its number is even without --final, or odd with it; else as no_consent when
    any of its rows has a blank consent_file or one that names no file beside cars.csv,
    found by a stat. The skips are keyed by car id, or under final by "row <n>" for
    each of the car's rows, so no final car id is kept. The consent version isn't
    checked here: generate warns on one Rene hasn't approved (C218).

    These print their row and exit 1, before any file is checked: a car_id that isn't
    B and two digits; a photo_file that isn't the car's own <car>-<n>.<jpg|jpeg|png> in
    any case, or whose stem another row has, in any case, since a photo's masks are
    filed by its stem; and a consent_file that isn't a bare file name, or is cars.csv's
    own. Without final, a consent path that names sealed is refused before its stat.
    """
    rows = _read_rows(cars, CARS_READ)
    problems = []
    stems = set()
    for row in rows:
        ref = f"row {row['#']}"
        car, name, consent = row["car_id"], row["photo_file"], row["consent_file"]
        stem = Path(name).stem.casefold()
        if CAR_ID.fullmatch(car) is None:
            problems.append(f"{ref} car_id: bad_id")
        elif PHOTO_NAME.fullmatch(name) is None or name[:3].upper() != car:
            problems.append(f"{ref} photo_file: id_file_mismatch")
        elif stem in stems:  # one photo twice, or B01-1.jpg beside B01-1.png
            problems.append(f"{ref} photo_file: duplicate")
        stems.add(stem)
        if consent and (
            Path(consent).name != consent or consent.casefold() == cars.name.casefold()
        ):
            problems.append(f"{ref} consent_file: bad_name")
    _stop_on(problems)
    causes: dict[str, str] = {}  # by car id, which this function alone holds
    for row in rows:
        car, consent = row["car_id"], row["consent_file"]
        if (int(car[1:]) % 2 == 0) != final:  # odd cars are development cars (C210)
            causes[car] = "wrong_side"
            continue
        if consent and not final:
            refuse_sealed(cars.parent / consent)
        if not consent or not (cars.parent / consent).is_file():
            causes[car] = "no_consent"
    send = [row["photo_file"] for row in rows if row["car_id"] not in causes]
    if not final:
        return send, causes
    by_row = {
        f"row {row['#']}": causes[row["car_id"]]
        for row in rows
        if row["car_id"] in causes
    }
    return send, by_row


def save_result(folder: Path, result: SamResult, shape: tuple[int, int]) -> list[Path]:
    """Write one phrase's raw text (R11) and its masks, as run_probe.save_sam does, and
    return the two files.

    The stem is the phrase with spaces as _: "wheel rim" gives sam_wheel_rim.txt and
    sam_wheel_rim_masks.npz. The npz holds ids, boxes (N x 4 floats, half-open),
    scores (NaN for None) and masks (N x height x width bool); shape is the image's
    (height, width). The text is written as bytes, so a replay reads it exactly.
    """
    stem = "sam_" + result.phrase.replace(" ", "_")
    text, masks = folder / f"{stem}.txt", folder / f"{stem}_masks.npz"
    text.write_bytes(result.raw.encode("utf-8"))
    found = result.instances
    np.savez_compressed(
        masks,
        ids=np.array([i.id for i in found], int),
        boxes=np.array([i.box for i in found], float).reshape(-1, 4),
        scores=np.array([np.nan if i.score is None else i.score for i in found]),
        masks=np.array([i.mask for i in found], bool).reshape(-1, *shape),
    )
    return [text, masks]


def mask_photo(client: MetaClient, data: bytes, folder: Path) -> int:
    """Blur the photo, then send it to SAM once per phrase. Return the calls made.

    blur_for_meta comes first, so a photo it refuses (UndecodableImage) leaves nothing
    written. The folder gets blurred.jpg, each phrase's files, and meta.json last, so a
    folder with meta.json is complete.
    """
    image = blur_for_meta(data)
    folder.mkdir(parents=True, exist_ok=True)
    blurred = folder / "blurred.jpg"
    blurred.write_bytes(image.jpeg)
    written, results = [blurred], []
    for phrase in PHRASES:
        result = client.segment(image, phrase)
        written += save_result(folder, result, (image.height, image.width))
        results.append(result)
    _write_meta(folder, image, results, written)
    return len(results)


def water_crop(
    client: MetaClient, data: bytes, folder: Path, *, generator_version: str
) -> int:
    """Blur the crop, then send it to SAM for floodwater. Return the calls made (C213).

    meta.json, written last, also holds the crop's SHA-256, as crop_sha256, and the
    generator_version, so a crop whose bytes or version change is segmented again.
    """
    image = blur_for_meta(data)
    result = client.segment(image, WATER_PHRASE)
    folder.mkdir(parents=True, exist_ok=True)
    written = save_result(folder, result, (image.height, image.width))
    _write_meta(
        folder,
        image,
        [result],
        written,
        crop_sha256=hashlib.sha256(data).hexdigest(),
        generator_version=generator_version,
    )
    return 1


def write_files_txt(out: Path, written: Iterable[Path]) -> None:
    """Merge the written files, hashed, into out/files.txt: lines of "<sha256>  <path
    relative to out, with />", sorted by path.

    The entries already there are kept, unless a written file replaces one, so a
    --water run keeps the photos' entries. files.txt is opened by its name, never found
    by a listing, and its bytes stay as they are when nothing changed.
    """
    listing = out / "files.txt"
    old = listing.read_bytes() if listing.is_file() else b""
    entries = {}
    for line in old.decode("utf-8").splitlines():
        digest, path = line.split("  ", 1)
        entries[path] = digest
    for path in written:
        entries[path.relative_to(out).as_posix()] = _sha256(path)
    new = "".join(f"{entries[path]}  {path}\n" for path in sorted(entries))
    if new.encode("utf-8") != old:
        listing.write_bytes(new.encode("utf-8"))


def main(
    argv: Sequence[str] | None = None,
    *,
    make_client: Callable[[], MetaClient] = MetaClient,
) -> int:
    """Run the command the module's docstring describes, its body through quiet."""
    return quiet(lambda: _run(argv, make_client))


def _run(argv: Sequence[str] | None, make_client: Callable[[], MetaClient]) -> int:
    args = _parse(argv)
    # 1. The path checks, on the strings alone. 2. Under --final, the console, before
    # any stat of a sealed path and before the prompt (C202).
    if args.final:
        require_sealed(args.cars, flag="--cars")
        require_sealed(args.photos, flag="--photos")
        require_sealed(args.out, flag="--out")
        require_console()
    else:
        given = (args.cars, args.photos, args.water, args.out)
        refuse_sealed(*[path for path in given if path is not None])
    out = Path(args.out)
    # 3. What to send, what is skipped, and the folders earlier runs finished.
    if args.water:
        jobs, skips, finished = _crop_jobs(Path(args.water), out)
    else:
        jobs, skips, finished = _photo_jobs(
            Path(args.cars), Path(args.photos), out, final=args.final
        )
    for label, cause in skips:
        print(f"{label} skipped: {cause}")
    # 4. The summary. 5. Under --final, Rene's yes, before anything is written.
    planned = len(jobs) * (1 if args.water else len(PHRASES))
    summary = (
        f"planned photos={len(jobs)} sam_calls={planned} "
        f"cost=${planned * USD_PER_CALL:.4f}"
    )
    if args.final:
        confirm(summary)
    else:
        print(summary)
    # A run stopped between a folder's meta.json and the files.txt merge left that
    # folder unlisted, so the finished folders are merged again: a no-op when listed.
    write_files_txt(out, [path for folder in finished for path in _written(folder)])
    # 6. The client, made only when there is a call to make, then the calls in turn.
    started = time.monotonic()
    try:
        client = make_client() if jobs else None
    except MissingApiKey as error:
        print(f"stopped: {type(error).__name__}", file=sys.stderr)
        return 2
    photos, skipped, calls = 0, len(skips), 0
    for label, path, folder, send in jobs:
        try:
            calls += send(client, path.read_bytes(), folder)
        except UndecodableImage:  # it doesn't decode, or a side is 32 px or less
            print(f"{label} skipped: undecodable")
            skipped += 1
            continue
        except MetaApiError as error:  # DeadlineExceeded too, once MS3a merges
            status = f"status={error.status}"
            print(f"stopped: {type(error).__name__} {status}", file=sys.stderr)
            return 1
        write_files_txt(out, _written(folder))
        photos += 1
    seconds = time.monotonic() - started
    print(f"photos={photos} skipped={skipped} sam_calls={calls} seconds={seconds:.1f}")
    return 0


def _parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Face-blurred SAM masks for Set B's car photos (C200)."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--cars", help="cars.csv, with --photos")
    source.add_argument(
        "--water", help="the development truth.csv: one floodwater call per crop"
    )
    parser.add_argument("--photos", help="the folder of the photos cars.csv names")
    parser.add_argument("--out", required=True, help="the masks folder")
    parser.add_argument(
        "--final",
        action="store_true",
        help="Rene's final-car run, with the paths inside sealed (C214)",
    )
    args = parser.parse_args(argv)
    if not Path(args.out).is_absolute():  # uv's --directory runs this in the repo
        parser.error("--out must be an absolute path")
    if args.cars is not None and args.photos is None:
        parser.error("--cars needs --photos")
    if args.water is not None and args.final:
        parser.error("--water runs on development crops only, never with --final")
    return args


def _photo_jobs(
    cars: Path, photos: Path, out: Path, *, final: bool
) -> tuple[list[Job], list[tuple[str, str]], list[Path]]:
    """A job for each photo check_cars sends and no earlier run finished, the skips,
    and the folders earlier runs finished.

    A photo prints by its stem, or under final by its row in cars.csv (C202). A photo
    to send that isn't in the photos folder, found by a stat, prints as
    <photo> photo_file: missing and exits 1, so a run never pays and then stops.
    """
    names, skipped = check_cars(cars, final=final)
    rows: dict[str, str] = {}
    if final:  # check_cars has refused any photo named twice
        for row in _read_rows(cars, CARS_READ):
            rows[row["photo_file"]] = f"row {row['#']}"
    jobs, skips, finished, missing = [], list(skipped.items()), [], []
    for name in names:
        stem = Path(name).stem
        label = rows[name] if final else stem
        folder = out / stem
        if (folder / "meta.json").is_file():
            skips.append((label, "done"))
            finished.append(folder)
        elif not (photos / name).is_file():
            missing.append(f"{label} photo_file: missing")
        else:
            jobs.append((label, photos / name, folder, mask_photo))
    _stop_on(missing)
    return jobs, skips, finished


def _crop_jobs(
    truth: Path, out: Path
) -> tuple[list[Job], list[tuple[str, str]], list[Path]]:
    """A job for each distinct crop_file in truth.csv, read from crops/ beside it,
    unless its meta.json holds the crop's SHA-256 and its rows' generator_version
    (C213); the skips; and the folders earlier runs finished.

    These print and exit 1, before any call: a crop_id that isn't a Set B crop's id,
    since it names the crop's folder under --out; a final car's crop, by its row, as
    --water is for development crops only (C210); a crop_file that isn't
    <crop_id>.jpg; and a crop missing from crops/.
    """
    rows = _read_rows(truth, TRUTH_READ)
    problems = []
    for row in rows:
        ref, crop = f"row {row['#']}", row["crop_id"]
        if CROP_ID.fullmatch(crop) is None:
            problems.append(f"{ref} crop_id: bad_id")
        elif int(crop[1:3]) % 2 == 0:  # a final car's crop (C210)
            problems.append(f"{ref} crop_id: wrong_side")
        elif row["crop_file"] != crop + ".jpg":
            problems.append(f"{ref} crop_file: id_file_mismatch")
    _stop_on(problems)
    crops: dict[str, dict[str, str]] = {}
    for row in rows:  # one row per wheel
        crops.setdefault(row["crop_file"], row)
    jobs, skips, finished, missing = [], [], [], []
    for name, row in crops.items():
        crop, version = row["crop_id"], row["generator_version"]
        path, folder = truth.parent / "crops" / name, out / "water" / crop
        if not path.is_file():
            missing.append(f"{crop} crop_file: missing")
            continue
        meta = folder / "meta.json"
        if meta.is_file():
            done = json.loads(meta.read_bytes())
            if (done.get("crop_sha256"), done.get("generator_version")) == (
                _sha256(path),
                version,
            ):
                skips.append((crop, "done"))
                finished.append(folder)
                continue
        send = partial(water_crop, generator_version=version)
        jobs.append((crop, path, folder, send))
    _stop_on(missing)
    return jobs, skips, finished


def _read_rows(path: Path, needed: Sequence[str]) -> list[dict[str, str]]:
    """A CSV's rows that aren't all blank, read as eval/data/table.py reads them: with
    or without a BOM, with either line ending, and each cell stripped. "#" is the row's
    number among the data rows, blank rows counted, as in Rene's spreadsheet.

    As table.py does, it refuses what would shift or hide a value, each by number and
    kind, never by its text, and exits 1: a header name that is blank, "#" or
    repeated (header column <n>: blank, reserved or duplicate), then a missing column
    (log <column>: missing_column), then a row whose cells don't line up with the
    header (row <n> cells: too_many or too_few).
    """
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        columns = [cell.strip() for cell in next(reader, [])]
        for number, name in enumerate(columns, start=1):
            if not name:
                kind = "blank"
            elif name == "#":
                kind = "reserved"
            elif name in columns[: number - 1]:
                kind = "duplicate"
            else:
                continue
            _stop_on([f"header column {number}: {kind}"])
        missing = [name for name in needed if name not in columns]
        _stop_on([f"log {name}: missing_column" for name in missing])
        rows = []
        for number, cells in enumerate(reader, start=1):
            cells = [cell.strip() for cell in cells]
            if not any(cells):
                continue
            if len(cells) != len(columns):
                kind = "too_many" if len(cells) > len(columns) else "too_few"
                _stop_on([f"row {number} cells: {kind}"])
            rows.append({**dict(zip(columns, cells, strict=True)), "#": str(number)})
    return rows


def _stop_on(problems: list[str]) -> None:
    """Print each problem, then exit 1 when there was one."""
    for problem in problems:
        print(problem)
    if problems:
        sys.exit(1)


def _write_meta(
    folder: Path,
    image: BlurredImage,
    results: list[SamResult],
    written: list[Path],
    **extra: str,
) -> None:
    """Write folder/meta.json, last: the blurred image's size and blur record, each
    phrase's instances and seconds, the files written before it, and any extra keys. It
    is JSON with sorted keys, a two-space indent, ASCII only and a final newline."""
    meta = {
        "width": image.width,
        "height": image.height,
        "faces": image.faces,
        "blur_version": image.blur_version,
        "instances": {result.phrase: len(result.instances) for result in results},
        "seconds": {result.phrase: round(result.elapsed_s, 3) for result in results},
        "files": [path.name for path in written],
        **extra,
    }
    text = json.dumps(meta, indent=2, sort_keys=True) + "\n"
    (folder / "meta.json").write_bytes(text.encode("ascii"))


def _written(folder: Path) -> list[Path]:
    """The files a finished folder's meta.json names, then meta.json itself: names from
    a file list, not a listing."""
    meta = folder / "meta.json"
    return [folder / name for name in json.loads(meta.read_bytes())["files"]] + [meta]


def _sha256(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


if __name__ == "__main__":
    sys.exit(main())
