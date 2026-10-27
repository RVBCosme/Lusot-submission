"""Face blur, the pipeline's first step (C20, F1).

Every photo is face-blurred here before any Meta call. The result is a BlurredImage,
the only image type the Meta client accepts (C37), and only this module can build one.
"""

from __future__ import annotations

import functools
import math
import threading
from collections.abc import Sequence
from dataclasses import InitVar, dataclass, field
from pathlib import Path

import cv2
import numpy as np

FACE_BLUR_VERSION = "yunet-2023mar/multiscale-1-0.5-0.25/pixelate-gauss-v2"
YUNET_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"

_MODEL_PATH = Path(__file__).parent / "models" / "face_detection_yunet_2023mar.onnx"
_TOKEN = object()  # proves a BlurredImage was built in this module
_DETECTOR_LOCK = threading.Lock()  # one shared detector, and setInputSize changes it


class UndecodableImage(ValueError):
    """The bytes are not an image OpenCV can decode."""


@dataclass(frozen=True)
class FaceBox:
    x: int
    y: int
    w: int
    h: int
    score: float


@dataclass(frozen=True)
class BlurredImage:
    """A JPEG whose faces this module blurred, with its blur record.

    `faces` is the number of face boxes blurred; boxes from different scales may
    overlap the same face.
    """

    jpeg: bytes = field(repr=False)  # keeps the photo out of logs and error messages
    width: int
    height: int
    faces: int
    blur_version: str
    _token: InitVar[object] = None

    def __post_init__(self, _token: object) -> None:
        if _token is not _TOKEN:
            raise TypeError(
                "a BlurredImage comes only from blur_for_meta or BlurredImage.derive"
            )

    def bgr(self) -> np.ndarray:
        return decode_image(self.jpeg)

    @classmethod
    def derive(cls, bgr: np.ndarray, base: BlurredImage) -> BlurredImage:
        """Wrap pixels drawn on `base`, keeping its `faces` and `blur_version`."""
        if not isinstance(base, BlurredImage):
            raise TypeError("base must be a BlurredImage")
        return _encode(bgr, faces=base.faces, blur_version=base.blur_version)


def decode_image(data: bytes) -> np.ndarray:
    """Decode to 8-bit BGR, upright: OpenCV applies the EXIF orientation."""
    try:
        bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    except cv2.error as exc:  # an empty buffer raises instead of returning None
        raise UndecodableImage("not a decodable image") from exc
    if bgr is None:
        raise UndecodableImage("not a decodable image")
    return bgr


@functools.cache
def _detector() -> cv2.FaceDetectorYN:
    return cv2.FaceDetectorYN.create(str(_MODEL_PATH), "", (320, 320))


def detect_faces(bgr: np.ndarray, *, score_threshold: float = 0.6) -> list[FaceBox]:
    """Run YuNet at full, half and quarter size, and return every pass's boxes.

    YuNet boxes faces of up to about 300 px well, so the smaller passes box larger
    faces whole (checked up to a face filling 85% of a 1600 px frame). The passes
    aren't merged: overlapping boxes only add blur.
    """
    height, width = bgr.shape[:2]
    images = [bgr] + [
        cv2.resize(
            bgr, (max(1, width // n), max(1, height // n)), interpolation=cv2.INTER_AREA
        )
        for n in (2, 4)  # half and quarter size, as FACE_BLUR_VERSION records
    ]
    boxes = []
    with _DETECTOR_LOCK:
        detector = _detector()
        detector.setScoreThreshold(score_threshold)
        for image in images:
            detector.setInputSize((image.shape[1], image.shape[0]))
            _, rows = detector.detect(image)
            if rows is None:
                continue
            sx, sy = width / image.shape[1], height / image.shape[0]
            for row in rows:  # x, y, w, h, five landmark points, then the score
                x, y, w, h = np.rint(row[:4] * (sx, sy, sx, sy)).astype(int).tolist()
                boxes.append(FaceBox(x, y, w, h, float(row[14])))
    return boxes


def blur_faces(
    bgr: np.ndarray, faces: Sequence[FaceBox], *, margin: float = 0.25
) -> np.ndarray:
    """Blur each face box, grown by `margin` of its size on every side.

    Returns a new array and leaves `bgr` unchanged.
    """
    out = bgr.copy()
    height, width = out.shape[:2]
    for face in faces:
        dx, dy = math.ceil(face.w * margin), math.ceil(face.h * margin)
        x0, y0 = max(0, face.x - dx), max(0, face.y - dy)
        x1, y1 = min(width, face.x + face.w + dx), min(height, face.y + face.h + dy)
        if x0 >= x1 or y0 >= y1:
            continue
        # Pixelate to about a 10 x 10 grid, then smooth it with an odd Gaussian kernel.
        roi_w, roi_h = x1 - x0, y1 - y0
        cells = cv2.resize(
            out[y0:y1, x0:x1],
            (min(10, roi_w), min(10, roi_h)),
            interpolation=cv2.INTER_AREA,
        )
        pixelated = cv2.resize(cells, (roi_w, roi_h), interpolation=cv2.INTER_NEAREST)
        kernel = (max(face.w, face.h) // 3) | 1
        out[y0:y1, x0:x1] = cv2.GaussianBlur(pixelated, (kernel, kernel), 0)
    return out


def blur_for_meta(data: bytes, *, max_side: int = 1600) -> BlurredImage:
    """Decode, shrink to `max_side` with INTER_AREA, blur the faces, encode as JPEG."""
    bgr = decode_image(data)
    height, width = bgr.shape[:2]
    if max(height, width) > max_side:
        scale = max_side / max(height, width)
        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        bgr = cv2.resize(bgr, size, interpolation=cv2.INTER_AREA)
    faces = detect_faces(bgr)
    return _encode(
        blur_faces(bgr, faces), faces=len(faces), blur_version=FACE_BLUR_VERSION
    )


def _encode(bgr: np.ndarray, *, faces: int, blur_version: str) -> BlurredImage:
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise ValueError("JPEG encoding failed")
    height, width = bgr.shape[:2]
    return BlurredImage(buf.tobytes(), width, height, faces, blur_version, _TOKEN)
