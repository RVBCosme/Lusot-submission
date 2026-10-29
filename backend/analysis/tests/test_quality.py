"""Tests for step 1, the quality gate: brightness and sharpness (C44, C58)."""

from pathlib import Path

import cv2
import numpy as np
import pytest
from fakes import flat_jpeg, noise_jpeg

from lusot_analysis.face_blur import blur_for_meta, decode_image, shrink_to_max_side
from lusot_analysis.pipeline.quality import (
    QualityScores,
    quality_refusal,
    quality_scores,
)
from lusot_analysis.tuning import START

PORTRAIT = Path(__file__).parent / "fixtures" / "faces" / "portrait.jpg"


def scores_of(bgr: np.ndarray) -> QualityScores:
    """The mean grey value and the Laplacian's variance, read here from pixels."""
    grey = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(grey, cv2.CV_64F)
    return QualityScores(float(grey.mean()), float(laplacian.var()))


def assert_same_scores(actual: QualityScores, expected: QualityScores) -> None:
    """Both scores agree to within 1e-9. rel=0, or approx would allow 1e-6 of each."""
    assert actual.brightness == pytest.approx(expected.brightness, rel=0, abs=1e-9)
    assert actual.sharpness == pytest.approx(expected.sharpness, rel=0, abs=1e-9)


@pytest.mark.parametrize(
    ("brightness", "sharpness", "refusal"),
    [
        (39.99, 100, "too_dark"),
        (40.0, 100, None),
        (100, 24.99, "too_blurry"),
        (100, 25.0, None),
        (10, 1, "too_dark"),  # dark is checked first
    ],
)
def test_cutoffs_are_exact(brightness, sharpness, refusal):
    scores = QualityScores(brightness, sharpness)
    assert quality_refusal(scores, tuning=START) == refusal


@pytest.mark.parametrize(
    ("data", "refusal"),
    [
        (flat_jpeg(10), "too_dark"),
        (flat_jpeg(128), "too_blurry"),
        (noise_jpeg(), None),
    ],
    ids=["flat-10", "flat-128", "noise"],
)
def test_dark_and_flat_photos_are_refused(data, refusal):
    assert quality_refusal(quality_scores(data), tuning=START) == refusal


def test_scores_use_the_photo_before_the_face_blur():
    # The phone runs the same check with no face detector, so only the photo before
    # the face blur gives the same scores (C58). The portrait's faces are blurred in
    # blur_for_meta's copy, which is less sharp.
    data = PORTRAIT.read_bytes()
    scores = quality_scores(data)
    assert_same_scores(scores, scores_of(shrink_to_max_side(decode_image(data))))
    assert scores.sharpness > scores_of(blur_for_meta(data).bgr()).sharpness


def test_scores_use_the_shrunk_photo():
    data = noise_jpeg(4000, 3000)
    full = decode_image(data)
    shrunk = shrink_to_max_side(full)
    assert shrunk.shape == (1200, 1600, 3)
    scores = quality_scores(data)
    assert_same_scores(scores, scores_of(shrunk))
    assert scores_of(full) != scores  # so the test can tell the two apart
