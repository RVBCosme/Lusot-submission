"""Step 1: the quality gate, before any Meta call (spec §3.2; C44, C58).

Brightness is the mean grey value, and sharpness the variance of the Laplacian. Both
read the decoded upload before the face blur, shrunk the way blur_for_meta shrinks it.
Plan §7 step 1 runs the same check on the phone, which has no face detector, so only
the photo before the face blur gives the same scores (C58).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2

from lusot_analysis.face_blur import decode_image, shrink_to_max_side
from lusot_analysis.tuning import TUNING, Tuning

# The live cutoffs (C44), from the tuning module, which tunes them on development
# photos (C310). They refuse only the extremes while untuned.
BRIGHTNESS_MIN = TUNING.brightness_min
SHARPNESS_MIN = TUNING.sharpness_min
MAX_SIDE = 1600  # the scores read the photo at this longer side, at most (C58)


@dataclass(frozen=True)
class QualityScores:
    """The photo's mean grey value, and the variance of its Laplacian."""

    brightness: float
    sharpness: float


def quality_scores(data: bytes) -> QualityScores:
    """Decode the upload, shrink it to at most MAX_SIDE, and score its grey image.

    An undecodable file raises UndecodableImage, as in decode_image.
    """
    bgr = shrink_to_max_side(decode_image(data), MAX_SIDE)
    grey = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return QualityScores(
        brightness=float(grey.mean()),
        sharpness=float(cv2.Laplacian(grey, cv2.CV_64F).var()),
    )


def quality_refusal(scores: QualityScores, tuning: Tuning = TUNING) -> str | None:
    """The refusal reason when a score is under its cutoff, or None to go on.

    The cutoffs are `tuning`'s, so a replay can raise them. Dark is checked first, so
    a dark, flat photo reads too_dark.
    """
    if scores.brightness < tuning.brightness_min:
        return "too_dark"
    if scores.sharpness < tuning.sharpness_min:
        return "too_blurry"
    return None
