"""Tests for photo facts: the SHA-256, the dHash and whether OpenCV decodes the photo
under the pipeline's 50 MP cap (§5.5, R25). Every image is built in the test.

cv2 is imported inside the helpers only, as synth.jpeg does, so photos loads it first,
under its cap (R25).
"""

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

import events
import numpy as np
import photos
import synth

DATA = Path(__file__).resolve().parents[1]  # eval/data

# For a fresh interpreter: whether photos decodes the bytes on stdin.
DECODES = (
    "import photos, sys; print(photos.photo_facts(sys.stdin.buffer.read()).decodes)"
)


def declare_size(data: bytes, width: int, height: int) -> bytes:
    """Rewrite a baseline JPEG's frame header (SOF0) so it declares another size.

    Copied from MS1's backend/analysis/tests/test_face_blur.py (R25).
    """
    i = 2  # after the start-of-image marker
    while data[i + 1] != 0xC0:
        i += 2 + int.from_bytes(data[i + 2 : i + 4], "big")
    size = height.to_bytes(2, "big") + width.to_bytes(2, "big")
    return data[: i + 5] + size + data[i + 9 :]


def decodes_in_fresh_process(data: bytes) -> str:
    """Whether photos decodes the bytes in a new interpreter: "True" or "False".

    OpenCV reads its pixel cap once, when cv2 loads, and this process loaded cv2
    already. The variable is removed from the child's environment, so the cap must come
    from photos itself (MS1's R25 method).
    """
    env = {k: v for k, v in os.environ.items() if k != "OPENCV_IO_MAX_IMAGE_PIXELS"}
    env["PYTHONPATH"] = str(DATA)
    done = subprocess.run(
        [sys.executable, "-c", DECODES],
        input=data,
        capture_output=True,
        env=env,
        timeout=synth.TIMEOUT,
        check=True,
    )
    return done.stdout.decode().strip()


def jpeg_copy(data: bytes, quality: int) -> bytes:
    """The photo decoded and saved again as a JPEG of that quality, as a repost is."""
    import cv2

    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    return cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes()


def ramp(start: int, stop: int) -> np.ndarray:
    """A gray image, 80 rows by 90 columns, whose brightness runs from start at the
    left to stop at the right. dHash's 9 by 8 grid shrinks each 10 by 10 block to one
    pixel."""
    return np.tile(np.linspace(start, stop, 90).astype(np.uint8), (80, 1))


def png(image: np.ndarray) -> bytes:
    """A lossless file, so each pixel decodes exactly as built."""
    import cv2

    return cv2.imencode(".png", image)[1].tobytes()


def textured(seed: int) -> np.ndarray:
    """A 240 by 320 photo: dHash's grid of 8 by 9 seeded colour blocks, with seeded
    noise on every pixel, so the gray conversion and the shrink each change the hash."""
    rng = np.random.default_rng(seed)
    blocks = rng.integers(0, 256, (8, 9, 3), dtype=np.uint8)
    rows = np.arange(240)[:, None] * 8 // 240
    columns = np.arange(320)[None, :] * 9 // 320
    noise = rng.integers(-50, 51, (240, 320, 3))
    return np.clip(blocks[rows, columns] + noise, 0, 255).astype(np.uint8)


def test_photo_facts_of_a_jpeg():
    data = synth.jpeg(1, (120, 200))  # 120 rows by 200 columns
    facts = photos.photo_facts(data)
    assert facts.sha256 == hashlib.sha256(data).hexdigest()
    assert (facts.decodes, facts.width, facts.height) == (True, 200, 120)
    assert re.fullmatch("[0-9a-f]{16}", facts.dhash)


def test_reencoded_copy_is_near():
    a, b = (photos.photo_facts(jpeg_copy(synth.jpeg(3), q)) for q in (95, 70))
    assert a.sha256 != b.sha256
    assert events.near(a.dhash, b.dhash)


def test_different_photos_are_far():
    a, b = (photos.photo_facts(synth.jpeg(seed)) for seed in (1, 2))
    assert not events.near(a.dhash, b.dhash)


def test_dhash_bit_order():
    """Row 0's first pair is the most significant bit, so the hex reads row by row."""
    top_only = np.full((80, 90), 128, np.uint8)
    top_only[:10] = ramp(250, 70)[:10]  # the top eighth is dHash's first row
    corner = np.full((80, 90), 128, np.uint8)
    corner[:10, :10] = 200  # only the first pixel is brighter than its neighbour
    assert photos.photo_facts(png(ramp(250, 70))).dhash == "ffffffffffffffff"
    assert photos.photo_facts(png(ramp(70, 250))).dhash == "0000000000000000"
    assert photos.photo_facts(png(top_only)).dhash == "ff00000000000000"
    assert photos.photo_facts(png(corner)).dhash == "8000000000000000"


def test_dhash_golden():
    """A textured photo's dHash, worked out beforehand with direct cv2 calls: imdecode,
    cvtColor with COLOR_BGR2GRAY, resize to (9, 8) with INTER_AREA, the comparisons,
    then packing with the first pair most significant. COLOR_RGB2GRAY or INTER_LINEAR
    each move it by 5 bits, inside near's 6, so only the exact hash pins them."""
    assert photos.photo_facts(png(textured(20261029))).dhash == "9ca95593565bb5b7"


def test_photo_facts_for_files_that_do_not_decode(capsys):
    """Review Focus 2: random bytes, a JPEG cut off inside its header, and no bytes at
    all. Each keeps its SHA-256, and nothing raises or prints."""
    for data in (np.random.default_rng(0).bytes(4096), synth.jpeg(1)[:64], b""):
        assert photos.photo_facts(data) == photos.PhotoFacts(
            hashlib.sha256(data).hexdigest(), "", False, None, None
        )
    assert capsys.readouterr() == ("", "")


def test_decodes_is_no_over_50_megapixels():
    small = synth.jpeg(0, (16, 16))
    huge = declare_size(small, 10_000, 6_000)  # 60 MP, declared in under 1 KB
    assert decodes_in_fresh_process(small) == "True"
    assert decodes_in_fresh_process(huge) == "False"
