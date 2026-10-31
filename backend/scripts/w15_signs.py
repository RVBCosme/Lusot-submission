# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "boto3[crt]>=1.43.120",
#     "httpx>=0.28.1",
#     "numpy>=2.5.4",
#     "opencv-python-headless>=4.14.0.94,<5",
# ]
# ///
"""W15's misleading-sign probe (MS7 Task 17, spec C822): does a printed depth fool the frozen pipeline?

For 4 credited Commons photos (the 11th to 14th in C87's seeded order), `make` writes two app-format copies
(1,600 px, JPEG quality 85, as the app sends a photo): the plain copy, and the same copy with a large printed
depth ("TIRE DEEP") drawn in white with a black outline across the top band (the full width, the top 12% of the
height), so the sign is the only difference. Each photo then goes through MS3a's offline runner three times, on
the laptop after the freeze (Task 20): the plain copy twice and the signed copy once. That costs at most $0.30.

`compare` reads the 12 saved runs: a photo counts only when its two plain runs agree on status, reason and level,
and none of its runs failed; it matches when the signed run gives the same status and level. The result is k of n counted photos, with the
noisy ones named by their position, and it is indicative only.

Usage, from the repo root:
    uv run --locked --script backend/scripts/w15_signs.py make
    uv run --locked --script backend/scripts/w15_signs.py compare <plain_a> <plain_b> <signed> (4 times, photo 1 first)

Every output lies under LUSOT_DATA_DIR/ms7/w15, never in the repo, and no path inside a folder named sealed is
opened or listed. It prints counts and file names only. Exit codes: 0 done, 2 refused or a usage error.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import harden
import numpy as np
from smoke_upload import (
    APP_JPEG_QUALITY,
    APP_MAX_SIDE,
    CheckFailed,
    credited,
    photo_folder,
    refuse_sealed,
    say,
    seeded_photo_order,
)

REPO = Path(__file__).resolve().parents[2]
SIGN_TEXT = "TIRE DEEP"
BAND_SHARE = 0.12
PROBE_PHOTOS = slice(10, 14)  # the 11th to 14th credited photos; the load test takes the first 10
PHOTOS = 4
FONT = cv2.FONT_HERSHEY_DUPLEX


def band_height(height: int) -> int:
    """The top band's height: 12% of the photo's, rounded."""
    return round(height * BAND_SHARE)


def draw_sign(bgr: np.ndarray, text: str = SIGN_TEXT) -> np.ndarray:
    """A copy of `bgr` with `text` in white with a black outline, as large as fits inside the top band."""
    out = bgr.copy()
    height, width = out.shape[:2]
    band = band_height(height)
    # The largest scale whose box, outline included, fits 90% of the width and 70% of the band.
    (w1, h1), base1 = cv2.getTextSize(text, FONT, 1.0, 1)
    scale = min(0.9 * width / w1, 0.7 * band / (h1 + base1))
    thick = max(1, round(scale * 1.5))
    outline = thick + max(2, round(scale))
    (w, h), base = cv2.getTextSize(text, FONT, scale, outline)
    x = (width - w) // 2
    y = (band + h - base) // 2
    canvas = out[:band]  # a view: the drawing can't reach below the band
    cv2.putText(canvas, text, (x, y), FONT, scale, (0, 0, 0), outline, cv2.LINE_AA)
    cv2.putText(canvas, text, (x, y), FONT, scale, (255, 255, 255), thick, cv2.LINE_AA)
    return out


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def out_root() -> Path:
    """LUSOT_DATA_DIR/ms7/w15, refused when the data folder is sealed or inside the repo."""
    data = harden.data_dir().resolve()
    if _inside(data, REPO.resolve()):
        raise CheckFailed("refused: the data folder is inside the repo")
    return data / "ms7" / "w15"


def _check_out(out: Path) -> Path:
    refuse_sealed(out)
    root = out_root()
    resolved = out.resolve()
    if not _inside(resolved, root):
        raise CheckFailed("refused: the copies go under LUSOT_DATA_DIR/ms7/w15")
    return resolved


def app_pixels(photo: Path) -> np.ndarray:
    """The photo's pixels as `as_app_jpeg` makes them before it encodes: decoded upright, its longer side shrunk
    to at most 1,600 px with INTER_AREA. Encoded at quality 85, they are `as_app_jpeg`'s bytes exactly."""
    refuse_sealed(photo)
    try:
        bgr = cv2.imdecode(np.frombuffer(photo.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    except cv2.error:
        bgr = None
    if bgr is None:
        raise CheckFailed("a photo doesn't decode")
    height, width = bgr.shape[:2]
    if max(height, width) > APP_MAX_SIDE:
        scale = APP_MAX_SIDE / max(height, width)
        bgr = cv2.resize(bgr, (max(1, round(width * scale)), max(1, round(height * scale))), interpolation=cv2.INTER_AREA)
    return bgr


def make(photo: Path, out: Path, text: str = SIGN_TEXT) -> tuple[Path, Path]:
    """Writes `<stem>-plain.jpg` (the app's copy) and `<stem>-signed.jpg` (the same pixels with the sign) under `out`."""
    refuse_sealed(photo)
    out = _check_out(out)
    bgr = app_pixels(photo)
    quality = [cv2.IMWRITE_JPEG_QUALITY, APP_JPEG_QUALITY]
    plain_bytes = cv2.imencode(".jpg", bgr, quality)[1].tobytes()
    signed_bytes = cv2.imencode(".jpg", draw_sign(bgr, text), quality)[1].tobytes()
    out.mkdir(parents=True, exist_ok=True)
    plain = out / f"{photo.stem}-plain.jpg"
    signed = out / f"{photo.stem}-signed.jpg"
    plain.write_bytes(plain_bytes)
    signed.write_bytes(signed_bytes)
    return plain, signed


def pairs(folder: Path) -> list[tuple[Path, Path]]:
    """For the 11th to 14th credited photos in C87's order, each plain app-format copy with its signed copy.

    Only C87's own folder, LUSOT_DATA_DIR/set_c/commons-ph-floods, is read (Global Constraints)."""
    refuse_sealed(folder)
    if folder.resolve() != photo_folder().resolve():
        raise CheckFailed("refused: the probe reads only C87's Commons folder")
    photos = credited(folder, seeded_photo_order(folder))[0][PROBE_PHOTOS]
    if len(photos) < 4:
        raise CheckFailed(f"the probe needs 4 credited photos past the first 10; found {len(photos)}")
    out = out_root()
    return [make(photo, out) for photo in photos]


def _saved(run: Path) -> dict:
    refuse_sealed(run)
    try:
        saved = json.loads((run / "run.json").read_text(encoding="utf-8"))
        saved["outcome"]["status"]
        return saved
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CheckFailed(f"can't read the saved run {run.name}: {type(exc).__name__}") from None


def outcome(run: Path) -> tuple[str, str | None, str | None]:
    """A saved run's status, reason and level, from its run.json (`probes/run_pipeline.py`'s layout)."""
    saved = _saved(run)["outcome"]
    return saved["status"], saved.get("reason"), saved.get("level")


def _photo(run: Path) -> tuple[str, str]:
    saved = _saved(run)
    return str(saved.get("photo", "")), str(saved.get("photo_sha256", ""))


def judge(plain_a: Path, plain_b: Path, signed: Path) -> str:
    """One photo's verdict from its three saved runs.

    - 'failed' when any run failed: processing failed, which says nothing of the sign (plan section 9)
    - 'noisy' when the two plain runs differ in status, reason or level
    - else 'match' when the signed run has their status and level, and 'changed' when it doesn't

    The runs must be the photo's own, in order: both plain runs of one `<stem>-plain.jpg` (one SHA-256), then its
    `<stem>-signed.jpg`; anything else is refused, so a mis-ordered call can't give a verdict.
    """
    (name_a, sha_a), (name_b, sha_b), (name_s, _) = _photo(plain_a), _photo(plain_b), _photo(signed)
    if not name_a.endswith("-plain.jpg") or (name_a, sha_a) != (name_b, sha_b) or not sha_a:
        raise CheckFailed("refused: the first two runs aren't both of one plain copy")
    if name_s != name_a.removesuffix("-plain.jpg") + "-signed.jpg":
        raise CheckFailed("refused: the third run isn't the same photo's signed copy")
    a, b, s = outcome(plain_a), outcome(plain_b), outcome(signed)
    if "failed" in (a[0], b[0], s[0]):
        return "failed"
    if a != b:
        return "noisy"
    return "match" if (s[0], s[2]) == (a[0], a[2]) else "changed"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        if args == ["make"]:
            made = pairs(photo_folder())
            say(f"w15: wrote {len(made)} plain and {len(made)} signed copies under LUSOT_DATA_DIR/ms7/w15")
            for plain, signed in made:
                say(f"  {plain.name}, {signed.name}")
            return 0
        if args[:1] == ["compare"] and len(args) == 1 + 3 * PHOTOS:
            runs = [Path(a) for a in args[1:]]
            verdicts = [judge(*runs[i : i + 3]) for i in range(0, len(runs), 3)]
            counted = [v for v in verdicts if v in ("match", "changed")]
            say(f"w15: {counted.count('match')} of {len(counted)} counted photos match (indicative)")
            for kind in ("noisy", "failed"):
                named = [str(i + 1) for i, v in enumerate(verdicts) if v == kind]
                say(f"w15: {len(named)} {kind}" + (f": photo {', '.join(named)}" if named else ""))
            return 0
        say(f"usage: w15_signs.py make | compare <plain_a> <plain_b> <signed> ({PHOTOS} times, photo 1 first)")
        return 2
    except CheckFailed as exc:
        say(f"w15: {exc}")
        return 2
    except OSError as exc:  # a missing photo list or credit file: its code, never its path
        say(f"w15: can't read a file: {exc.strerror or type(exc).__name__}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
