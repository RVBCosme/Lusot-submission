# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["numpy==2.5.4", "opencv-python-headless==4.14.0.94"]
# ///
r"""Set B's freeze check (spec §5.6; C213): SAM's floodwater masks on the development
crops, scored against the water the generator drew. Each run is one look, written as
its own record. After the third look the generator freezes as it is.

Run from the repo root, after set_b_masks --water (Claude runs this one):
    uv run --locked --script eval/set_b/water_check.py
        --truth <data>\set_b\dev\generated\truth.csv
        --sam <data>\set_b\dev\masks\water --looks-dir eval\data\records

Each crop in truth.csv, by its first row, passes when SAM's water covers at least a
quarter of the drawn water, or fails as:
- bad_row: its crop_id isn't an id (C221), or its crop_file isn't a bare name, so no
  cell steers a path; nothing is opened for it
- no_result: <sam>\<crop_id>\ holds no meta.json or no sam_floodwater_masks.npz
- stale_result: meta.json's crop_sha256 isn't the SHA-256 of crops\<crop_file> beside
  truth.csv, or its generator_version isn't the rows', so a new look is never scored
  against old masks
- low_coverage: SAM's water, the union of the npz's masks, covers less than a quarter
  of the drawn water, water\<crop_id>.png beside truth.csv
The look passes when at least three quarters of its crops pass. It is written to
<looks-dir>\set-b-look-<n>.json, n the first of 1 to 3 whose file doesn't exist, and
holds counts, causes and the share, never a crop id.

It prints the failed crops by cause, then the look's number, its counts, its share and
its result. Exit codes: 0 the look is written, whether it passes or fails; 1 truth.csv's
rows don't share one generator_version, or an error, of which only the class prints; 2
refused: a path inside a folder named sealed, or three looks are used.
"""

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))

# photos first: it sets OpenCV's 50 MP decode cap before cv2 loads (R25, S-R26). So
# isort's order, which would put it after cv2, is turned off for this block.
import photos  # noqa: F401, I001

import cv2
import guards
import numpy as np
import record_io
import table
from table import Finding

REPO = Path(__file__).resolve().parents[2]
TOOL = "eval/set_b/water_check.py"
# C213's criterion, fixed before any look.
CROP_PASS = Fraction(1, 4)
LOOK_PASS = Fraction(3, 4)
MAX_LOOKS = 3
# The files set_b_masks --water writes in each crop's folder, meta.json last.
META, MASKS = "meta.json", "sam_floodwater_masks.npz"


def coverage(sam: np.ndarray, drawn: np.ndarray) -> Fraction:
    """The share of the drawn water SAM's water covers: the pixels true in both, over
    the pixels true in drawn, exactly. Masks of different shapes raise ValueError
    instead of broadcasting."""
    if sam.shape != drawn.shape:
        raise ValueError("the masks' shapes differ")
    shared = np.count_nonzero(np.logical_and(sam, drawn))
    return Fraction(int(shared), int(np.count_nonzero(drawn)))


def check_crop(
    row: Mapping[str, str], truth_dir: Path, sam: Path, version: str
) -> str | None:
    """None when the crop passes, or the cause it fails, as the module's docstring
    lists them. Each path is refused before it opens (C222)."""
    crop_id, crop_file = row["crop_id"], row["crop_file"]
    if not table.is_id(crop_id) or not _bare(crop_file):
        return "bad_row"
    crop = truth_dir / "crops" / crop_file
    drawn = truth_dir / "water" / f"{crop_id}.png"
    meta, masks = sam / crop_id / META, sam / crop_id / MASKS
    guards.refuse_sealed(crop, drawn, meta, masks)
    if not (meta.is_file() and masks.is_file()):
        return "no_result"
    done = json.loads(meta.read_bytes())
    if (done.get("crop_sha256"), done.get("generator_version")) != (
        table.sha256_file(crop),
        version,
    ):
        return "stale_result"
    with np.load(masks, allow_pickle=False) as found:
        union = found["masks"].any(axis=0)
    if coverage(union, _drawn(drawn)) < CROP_PASS:
        return "low_coverage"
    return None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Set B's freeze check (C213): SAM's floodwater masks on the "
        "development crops against the drawn water, written as the next look record, "
        "printing counts and the result."
    )
    for flag, text in (
        ("--truth", "the development truth.csv: set_b\\dev\\generated\\truth.csv"),
        ("--sam", "set_b_masks --water's folder: set_b\\dev\\masks\\water"),
        ("--looks-dir", "the look records' folder: eval\\data\\records"),
    ):
        parser.add_argument(flag, required=True, type=Path, help=text)
    args = parser.parse_args(argv)
    return guards.quiet(lambda: _run(args))


def _run(args: argparse.Namespace) -> int:
    # The path rules, on the strings, before anything is read (C222). Then the look's
    # number, each file checked by name.
    guards.refuse_sealed(args.truth, args.sam, args.looks_dir)
    free = [n for n in range(1, MAX_LOOKS + 1) if not _look(args.looks_dir, n).exists()]
    if not free:
        print(
            "three looks are used: the generator freezes as it is (C213)",
            file=sys.stderr,
        )
        return 2
    rows = table.read_table(args.truth).rows
    versions = {row["generator_version"] for row in rows}
    if len(versions) != 1:
        print(Finding("truth", "generator_version", "mixed" if versions else "none"))
        return 1
    (version,) = versions
    crops: dict[str, Mapping[str, str]] = {}
    for row in rows:  # one row per wheel
        crops.setdefault(row["crop_id"], row)
    causes: Counter[str] = Counter()
    for row in crops.values():
        cause = check_crop(row, args.truth.parent, args.sam, version)
        if cause is not None:
            causes[cause] += 1
    total, passed = len(crops), len(crops) - causes.total()
    result = "pass" if Fraction(passed, total) >= LOOK_PASS else "fail"
    record = record_io.base_record(TOOL, REPO) | {
        "look": free[0],
        "generator_version": version,
        "crops": total,
        "passed": passed,
        "failed_by_cause": dict(sorted(causes.items())),
        "share": f"{passed}/{total}",
        "result": result,
    }
    record_io.write_record(_look(args.looks_dir, free[0]), record)
    failed = " ".join(f"{cause}={n}" for cause, n in sorted(causes.items()))
    print(f"failed: {failed or 'none'}")
    print(
        f"look={free[0]} crops={total} passed={passed} share={passed}/{total} "
        f"result={result}"
    )
    return 0


def _look(looks_dir: Path, n: int) -> Path:
    return looks_dir / f"set-b-look-{n}.json"


def _bare(name: str) -> bool:
    """True for a bare file name, which can't lead out of its folder: not empty, and
    with no folder, drive, stream or .. (addition 1, as audit checks photo_file)."""
    return (
        bool(name)
        and Path(name).name == name
        and not any(mark in name for mark in (":", "/", "\\", ".."))
    )


def _drawn(path: Path) -> np.ndarray:
    """The drawn water, read from the PNG generate wrote, 255 where there is water."""
    data = np.frombuffer(path.read_bytes(), np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_GRAYSCALE) > 0


if __name__ == "__main__":
    sys.exit(main())
