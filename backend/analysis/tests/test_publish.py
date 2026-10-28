"""Tests for step 8.1: the face-and-plate blur before storage (C48, B4)."""

import cv2
import numpy as np
import pytest
from fakes import instance, noise_jpeg, sam_results

from lusot_analysis.face_blur import FaceBox, blur_for_meta, decode_image
from lusot_analysis.meta_client import SamInstance, SamResult
from lusot_analysis.pipeline.publish import publish_boxes, publish_jpeg, publish_pixels

SIZE = (400, 300)  # width, height


def noise() -> np.ndarray:
    """A 400 x 300 noise image: sharp everywhere, so any blur shows."""
    return np.random.default_rng(0).integers(0, 256, (300, 400, 3), np.uint8)


def sharpness(bgr: np.ndarray) -> float:
    """Variance of the Laplacian: high for detail, near zero after a heavy blur."""
    return cv2.Laplacian(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()


def with_faces(*faces: SamInstance) -> dict[str, SamResult]:
    """SAM's results for all 7 phrases, with these `face` matches and nothing else."""
    sam = sam_results({}, size=SIZE)
    sam["face"] = SamResult("face", list(faces), elapsed_s=0.5, raw="")
    return sam


def assert_blurred_inside_only(
    before: np.ndarray, after: np.ndarray, boxes: list[tuple[slice, slice]]
) -> None:
    """Pixels outside `boxes` are identical, and each box loses 90% of its sharpness."""
    inside = np.zeros(before.shape[:2], bool)
    for box in boxes:
        inside[box] = True
    assert np.array_equal(after[~inside], before[~inside])
    for box in boxes:
        assert sharpness(after[box]) <= 0.1 * sharpness(before[box])


def test_face_and_plate_boxes_are_blurred_and_nothing_else_changes():
    # Every other phrase has a match too, away from both blurred areas.
    sam = sam_results(
        {
            "face": [(100, 80, 160, 140)],  # pixels x 100 to 159, y 80 to 139
            "license plate": [(200, 150, 260, 170)],  # x 200 to 259, y 150 to 169
            "floodwater": [(100, 200, 400, 300)],
            "wheel": [(20, 240, 60, 280)],
            "wheel rim": [(30, 250, 50, 270)],
            "vehicle": [(10, 200, 90, 290)],
            "person": [(300, 20, 380, 140)],
        },
        size=SIZE,
    )
    assert publish_boxes(sam) == [
        FaceBox(100, 80, 60, 60, 0.9),
        FaceBox(200, 150, 60, 20, 0.9),
    ]
    img = noise()
    # Each box grows by 25% of its size on every side: the face's 60 x 60 by 15 px,
    # the plate's 60 x 20 by 15 px across and 5 px up and down.
    grown = [np.s_[65:155, 85:175], np.s_[145:175, 185:275]]
    assert_blurred_inside_only(img, publish_pixels(img, sam), grown)


def test_blur_covers_the_mask_box_not_the_sam_box():
    face = instance(0, (50, 50, 250, 250), size=SIZE, mask_xyxy=(100, 100, 140, 140))
    sam = with_faces(face)  # the mask covers only x and y 100 to 139
    assert publish_boxes(sam) == [FaceBox(100, 100, 40, 40, 0.9)]
    img = noise()
    # The 40 px box grows by 10 px on every side: x and y 90 to 149.
    grown = np.s_[90:150, 90:150]
    assert_blurred_inside_only(img, publish_pixels(img, sam), [grown])


@pytest.mark.parametrize(
    ("xyxy", "box", "grown"),
    [
        # The 40 px box grows by 10 px on every side.
        ((100, 100, 140, 140), FaceBox(100, 100, 40, 40, 0.9), np.s_[90:150, 90:150]),
        # Rounded outward to the half-open (99, 100, 140, 141): 41 px a side, which
        # grows by 11 px.
        (
            (99.5, 100.25, 139.5, 140.75),
            FaceBox(99, 100, 41, 41, 0.9),
            np.s_[89:152, 88:151],
        ),
    ],
    ids=["whole-pixels", "rounded-outward"],
)
def test_empty_mask_falls_back_to_the_sam_box(xyxy, box, grown):
    empty = np.zeros((SIZE[1], SIZE[0]), bool)
    sam = with_faces(SamInstance(0, tuple(map(float, xyxy)), empty, 0.9))
    assert publish_boxes(sam) == [box]
    img = noise()
    assert_blurred_inside_only(img, publish_pixels(img, sam), [grown])


def test_a_match_with_no_score_gets_0():
    # A SAM record can lack its confidence, but a FaceBox's score is a float.
    face = instance(0, (100, 100, 140, 140), size=SIZE, score=None)
    assert publish_boxes(with_faces(face)) == [FaceBox(100, 100, 40, 40, 0.0)]


def test_publish_jpeg_keeps_the_image_size():
    image = blur_for_meta(noise_jpeg(*SIZE))
    sam = sam_results({"face": [(100, 80, 160, 140)]}, size=SIZE)
    out = publish_jpeg(image, sam)
    assert out.startswith(b"\xff\xd8")
    assert decode_image(out).shape == (image.height, image.width, 3)
    # It is publish_pixels on the face-blurred image, as a JPEG at quality 90.
    pixels = publish_pixels(image.bgr(), sam)
    quality_90 = cv2.imencode(".jpg", pixels, [cv2.IMWRITE_JPEG_QUALITY, 90])[1]
    assert out == quality_90.tobytes()
