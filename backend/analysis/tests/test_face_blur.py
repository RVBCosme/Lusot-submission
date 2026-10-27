"""Tests for the face blur, the pipeline's first step (C20, F1)."""

import dataclasses
import hashlib
import os
import subprocess
import sys
import warnings
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from lusot_analysis import face_blur
from lusot_analysis.face_blur import (
    FACE_BLUR_VERSION,
    YUNET_SHA256,
    BlurredImage,
    FaceBox,
    UndecodableImage,
    blur_faces,
    blur_for_meta,
    decode_image,
    detect_faces,
)

PORTRAIT = Path(__file__).parent / "fixtures" / "faces" / "portrait.jpg"


def noise(width: int, height: int) -> np.ndarray:
    return np.random.default_rng(0).integers(0, 256, (height, width, 3), dtype=np.uint8)


def sharpness(bgr: np.ndarray) -> float:
    """Variance of the Laplacian: high for detail, near zero after a heavy blur."""
    return cv2.Laplacian(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()


def assert_heavy_blur(before: np.ndarray, after: np.ndarray) -> None:
    """Sharpness drops by at least 90%, at full size and at a quarter of it.

    A light Gaussian passes at full size alone and leaves a face recognisable. At a
    quarter of the size, only a heavy blur removes the face's coarse structure.
    """

    def quarter(img: np.ndarray) -> np.ndarray:
        size = (img.shape[1] // 4, img.shape[0] // 4)
        return cv2.resize(img, size, interpolation=cv2.INTER_AREA)

    assert sharpness(after) <= 0.1 * sharpness(before)
    assert sharpness(quarter(after)) <= 0.1 * sharpness(quarter(before))


def jpeg(bgr: np.ndarray) -> bytes:
    return cv2.imencode(".jpg", bgr)[1].tobytes()


def fake_yunet(rows: np.ndarray | None = None) -> SimpleNamespace:
    """Stands in for YuNet: records each pass's input size; only the first gets rows."""
    sizes = []
    results = [rows]
    return SimpleNamespace(
        sizes=sizes,
        setScoreThreshold=lambda threshold: None,
        setInputSize=sizes.append,
        detect=lambda image: (1, results.pop() if results else None),
    )


def declare_size(data: bytes, width: int, height: int) -> bytes:
    """Rewrite a baseline JPEG's frame header (SOF0) so it declares another size."""
    i = 2  # after the start-of-image marker
    while data[i + 1] != 0xC0:
        i += 2 + int.from_bytes(data[i + 2 : i + 4], "big")
    size = height.to_bytes(2, "big") + width.to_bytes(2, "big")
    return data[: i + 5] + size + data[i + 9 :]


DECODE_SCRIPT = """
import sys
from lusot_analysis.face_blur import UndecodableImage, decode_image
try:
    decode_image(sys.stdin.buffer.read())
    print("decoded")
except UndecodableImage:
    print("refused")
"""


def decode_in_fresh_process(data: bytes) -> str:
    """Decode in a new interpreter that imports face_blur before cv2, like the Lambda.

    OpenCV reads its pixel cap once, when cv2 loads, and this process loaded cv2 first.
    The variable is removed, so the cap must come from face_blur itself.
    """
    env = {k: v for k, v in os.environ.items() if k != "OPENCV_IO_MAX_IMAGE_PIXELS"}
    result = subprocess.run(
        [sys.executable, "-c", DECODE_SCRIPT],
        input=data,
        capture_output=True,
        env=env,
        check=True,
    )
    return result.stdout.decode().strip()


def test_model_hash_matches():
    assert (
        hashlib.sha256(face_blur._MODEL_PATH.read_bytes()).hexdigest() == YUNET_SHA256
    )


def test_no_faces_leaves_image_unchanged():
    img = noise(400, 300)
    out = blur_faces(img, [])
    assert np.array_equal(out, img)
    assert out is not img


def test_blur_changes_only_the_expanded_box():
    img = noise(400, 300)
    before = img.copy()
    out = blur_faces(img, [FaceBox(100, 80, 60, 60, 0.9)])
    # 25% of 60 px is 15 px on each side: x from 85 to 175, y from 65 to 155.
    box = np.s_[65:155, 85:175]
    inside = np.zeros(img.shape[:2], bool)
    inside[box] = True
    assert np.array_equal(out[~inside], img[~inside])
    assert_heavy_blur(img[box], out[box])
    assert np.array_equal(img, before)


def test_box_at_image_edge_is_clipped():
    img = noise(400, 300)
    out = blur_faces(
        img, [FaceBox(370, 270, 60, 60, 0.9), FaceBox(-20, -30, 50, 50, 0.9)]
    )
    assert out.shape == img.shape and out.dtype == img.dtype
    # The part of each box inside the image is still blurred.
    assert not np.array_equal(out[270:, 370:], img[270:, 370:])
    assert not np.array_equal(out[:20, :30], img[:20, :30])


def test_portrait_face_is_found_and_blurred():
    data = PORTRAIT.read_bytes()
    portrait = decode_image(data)
    faces = detect_faces(portrait)
    assert len(faces) >= 1
    face = max(faces, key=lambda f: f.score)
    blurred = blur_for_meta(data)
    assert blurred.faces >= 1
    assert blurred.blur_version == FACE_BLUR_VERSION
    region = np.s_[face.y : face.y + face.h, face.x : face.x + face.w]
    assert_heavy_blur(portrait[region], blurred.bgr()[region])


def worst_tile_ratio(before: np.ndarray, after: np.ndarray) -> float:
    """The highest after/before sharpness ratio over a 3 x 3 grid of tiles.

    A partly boxed face keeps a sharp tile, even when the whole face's ratio is low.
    """
    ys = np.linspace(0, before.shape[0], 4).astype(int)
    xs = np.linspace(0, before.shape[1], 4).astype(int)
    return max(
        sharpness(after[y0:y1, x0:x1]) / sharpness(before[y0:y1, x0:x1])
        for y0, y1 in pairwise(ys)
        for x0, x1 in pairwise(xs)
    )


def assert_face_blurred_everywhere(
    frame: np.ndarray, box: list[int], face: FaceBox
) -> None:
    """The face in `box` is heavily blurred, and every tile of it loses 90% sharpness.

    The frames are upscales of the fixture with almost no pixel-level detail, so the
    face is measured shrunk back to the fixture's own size, where its detail is.
    """
    x, y, w, h = box
    out = blur_faces(frame, detect_faces(frame))

    def at_fixture_size(img: np.ndarray) -> np.ndarray:
        return cv2.resize(
            img[y : y + h, x : x + w], (face.w, face.h), interpolation=cv2.INTER_AREA
        )

    before, after = at_fixture_size(frame), at_fixture_size(out)
    assert worst_tile_ratio(before, after) <= 0.1
    assert_heavy_blur(before, after)


def test_large_face_is_fully_covered():
    portrait = decode_image(PORTRAIT.read_bytes())
    face = max(detect_faces(portrait), key=lambda f: f.score)
    scale = 7
    assert face.w * scale > 600
    big = cv2.resize(portrait, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    box = [v * scale for v in (face.x, face.y, face.w, face.h)]
    assert_face_blurred_everywhere(big, box, face)


def test_close_up_face_is_fully_covered():
    # A selfie-style close-up: the face fills 85% of the height of a 1200 x 1600 frame.
    portrait = decode_image(PORTRAIT.read_bytes())
    face = max(detect_faces(portrait), key=lambda f: f.score)
    crop_h = round(face.h / 0.85)
    crop_w = round(crop_h * 3 / 4)
    x0, y0 = face.x + (face.w - crop_w) // 2, face.y + (face.h - crop_h) // 2
    crop = portrait[y0 : y0 + crop_h, x0 : x0 + crop_w]
    frame = cv2.resize(crop, (1200, 1600), interpolation=cv2.INTER_CUBIC)
    kx, ky = 1200 / crop_w, 1600 / crop_h
    box = [
        round(v)
        for v in ((face.x - x0) * kx, (face.y - y0) * ky, face.w * kx, face.h * ky)
    ]
    assert_face_blurred_everywhere(frame, box, face)


def test_blur_for_meta_downscales_to_max_side():
    out = blur_for_meta(jpeg(np.full((3000, 4000, 3), 128, np.uint8)))
    assert max(out.width, out.height) == 1600
    assert (out.width, out.height) == (1600, 1200)
    assert out.bgr().shape == (1200, 1600, 3)


@pytest.mark.parametrize("data", [b"not an image", b""])
def test_blur_for_meta_rejects_non_image(data):
    with pytest.raises(UndecodableImage):
        blur_for_meta(data)


def test_blurred_image_cannot_be_built_directly():
    with pytest.raises(TypeError):
        BlurredImage(b"", 1, 1, 0, "x")
    real = blur_for_meta(jpeg(noise(40, 30)))
    with pytest.raises(TypeError):
        dataclasses.replace(real, jpeg=b"unblurred photo")


def test_repr_leaves_out_the_photo():
    # A logged or printed BlurredImage must not carry the photo (never log photos).
    assert "jpeg" not in repr(blur_for_meta(PORTRAIT.read_bytes()))


def test_derive_keeps_blur_record():
    base = blur_for_meta(PORTRAIT.read_bytes())
    drawn = base.bgr()
    cv2.rectangle(drawn, (10, 10), (100, 60), (0, 255, 255), 2)
    out = BlurredImage.derive(drawn, base)
    assert (out.faces, out.blur_version) == (base.faces, base.blur_version)
    assert (out.width, out.height) == (base.width, base.height)
    with pytest.raises(TypeError):
        BlurredImage.derive(drawn, drawn)


def test_derive_rejects_a_different_size():
    base = blur_for_meta(PORTRAIT.read_bytes())
    with pytest.raises(ValueError):
        BlurredImage.derive(np.zeros((base.width, base.height, 3), np.uint8), base)


def test_derive_blurs_an_unblurred_photo():
    data = PORTRAIT.read_bytes()
    base = blur_for_meta(data)
    raw = decode_image(data)  # the same size as base, but never blurred
    out = BlurredImage.derive(raw, base)
    face = max(detect_faces(raw), key=lambda f: f.score)
    region = np.s_[face.y : face.y + face.h, face.x : face.x + face.w]
    assert_heavy_blur(raw[region], out.bgr()[region])


def test_small_image_never_yields_garbage_boxes():
    # The case found in Task 7: right after a large input, YuNet sometimes returned
    # garbage boxes for this face-free image's half and quarter passes, which OpenCV
    # pads to 32 x 32. Some were NaN and warned when cast to int (R24).
    portrait = decode_image(PORTRAIT.read_bytes())
    row = np.linspace(0, 255, 64).astype(np.uint8)
    small = np.dstack([np.tile(row, (48, 1))] * 3)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for _ in range(50):
            detect_faces(portrait)
            assert detect_faces(small) == []


def test_passes_of_32_px_or_less_are_skipped(monkeypatch):
    fake = fake_yunet()
    monkeypatch.setattr(face_blur, "_detector", lambda: fake)
    detect_faces(noise(128, 128))  # the quarter pass, 32 x 32, is skipped
    detect_faces(noise(132, 132))  # the quarter pass, 33 x 33, runs
    assert fake.sizes == [(128, 128), (64, 64), (132, 132), (66, 66), (33, 33)]


def test_non_finite_rows_are_dropped(monkeypatch):
    garbage = [np.nan] * 14 + [1.0]
    valid = [10, 12, 20, 24] + [0] * 10 + [0.75]
    fake = fake_yunet(np.array([garbage, valid], np.float32))
    monkeypatch.setattr(face_blur, "_detector", lambda: fake)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # casting NaN to int warns
        assert detect_faces(noise(200, 200)) == [FaceBox(10, 12, 20, 24, 0.75)]


def test_decoding_refuses_more_than_50_megapixels():
    # A 10 MB JPEG can declare about 669 MP, about 2 GB once decoded, and OpenCV's own
    # cap is 1 GP. The cap refuses it from the header, before allocating (R25).
    small = jpeg(noise(16, 16))
    huge = declare_size(small, 10_000, 6_000)  # 60 MP, in under 1 KB
    assert len(huge) < 1000
    assert decode_in_fresh_process(small) == "decoded"
    assert decode_in_fresh_process(huge) == "refused"
