"""Tests for the face blur, the pipeline's first step (C20, F1)."""

import dataclasses
import hashlib
from pathlib import Path

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


def jpeg(bgr: np.ndarray) -> bytes:
    return cv2.imencode(".jpg", bgr)[1].tobytes()


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
    assert sharpness(out[box]) <= 0.1 * sharpness(img[box])
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
    assert sharpness(blurred.bgr()[region]) <= 0.1 * sharpness(portrait[region])


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
