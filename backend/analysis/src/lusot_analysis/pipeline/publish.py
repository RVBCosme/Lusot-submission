"""Step 8.1: the blur before storage (spec §3.2; C48, C61).

Only a level result stores a photo, as `blurred/{id}.jpg`. Plates reach Meta
unblurred, so before the photo is stored, SAM's `face` and `license plate` matches are
blurred on the face-blurred image, with MS1's blur_faces: plates for the first time,
faces again. The blur covers each mask's bounding box, grown by 25% on every side. The
box holds the whole mask and the margin covers its ragged edge, so no dilation size
needs tuning (C48).
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import cv2
import numpy as np

from lusot_analysis.face_blur import BlurredImage, FaceBox, blur_faces
from lusot_analysis.meta_client import SamResult
from lusot_analysis.pipeline.segment import box_xyxy

PUBLISH_PHRASES = ("face", "license plate")
PUBLISH_MARGIN = 0.25
PUBLISH_JPEG_QUALITY = 90


def publish_boxes(sam: Mapping[str, SamResult]) -> list[FaceBox]:
    """A box for each face and plate SAM found, in PUBLISH_PHRASES' order, then SAM's.

    - The box is the mask's bounding box: a mask from pixel x0 to x1 and y0 to y1
      gives FaceBox(x0, y0, x1 - x0 + 1, y1 - y0 + 1).
    - An empty mask falls back to SAM's box, which is half-open (R61). It is rounded
      outward first, floor the start and ceil the end, so its width is
      ceil(x1) - floor(x0), with no + 1.
    - The score is SAM's, or 0.0 when SAM sent none. blur_faces doesn't read it.
    - Both phrases' results must be in `sam`. A missing one raises KeyError, so a photo
      is never stored with its faces or plates unchecked (CLAUDE.md, §13).
    """
    boxes = []
    for phrase in PUBLISH_PHRASES:
        for inst in sam[phrase].instances:
            score = 0.0 if inst.score is None else inst.score
            columns = np.flatnonzero(inst.mask.any(axis=0))
            rows = np.flatnonzero(inst.mask.any(axis=1))
            if columns.size:
                x0, x1 = int(columns[0]), int(columns[-1])
                y0, y1 = int(rows[0]), int(rows[-1])
                boxes.append(FaceBox(x0, y0, x1 - x0 + 1, y1 - y0 + 1, score))
            else:
                bx0, by0, bx1, by1 = box_xyxy(inst)
                x0, y0 = math.floor(bx0), math.floor(by0)
                w, h = math.ceil(bx1) - x0, math.ceil(by1) - y0
                boxes.append(FaceBox(x0, y0, w, h, score))
    return boxes


def publish_pixels(bgr: np.ndarray, sam: Mapping[str, SamResult]) -> np.ndarray:
    """`bgr` with each of publish_boxes' boxes blurred, grown by PUBLISH_MARGIN."""
    return blur_faces(bgr, publish_boxes(sam), margin=PUBLISH_MARGIN)


def publish_jpeg(image: BlurredImage, sam: Mapping[str, SamResult]) -> bytes:
    """The photo to store, as a JPEG at PUBLISH_JPEG_QUALITY.

    It is publish_pixels on the face-blurred image.
    """
    pixels = publish_pixels(image.bgr(), sam)
    ok, buf = cv2.imencode(
        ".jpg", pixels, [cv2.IMWRITE_JPEG_QUALITY, PUBLISH_JPEG_QUALITY]
    )
    if not ok:
        raise ValueError("JPEG encoding failed")
    return buf.tobytes()
