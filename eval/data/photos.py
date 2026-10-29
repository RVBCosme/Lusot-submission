"""Photo facts for the split (spec §5.5, step 2): each photo's SHA-256, its 64-bit
difference hash (dHash), and whether OpenCV decodes it under the pipeline's 50 MP cap.

The facts come from bytes the tool has already read by name, so the hashed bytes are
the ones it archives. A photo that doesn't decode keeps its SHA-256, so identical files
still join one duplicate group, and it gets a blank dHash, which events.near never
calls near (Review Focus 2).
"""

import os
from dataclasses import dataclass

# OpenCV refuses to decode an image over 50 MP, before allocating it (R25): a JPEG of
# under 1 KB can declare 60 MP. OpenCV reads this once, when cv2 loads, so it is set
# before the import below, replacing any value from outside. A process that loaded
# cv2 earlier keeps OpenCV's 1 GP default.
os.environ["OPENCV_IO_MAX_IMAGE_PIXELS"] = "50000000"

import cv2
import numpy as np
import table


@dataclass(frozen=True)
class PhotoFacts:
    """A photo's SHA-256 and dHash, whether it decodes, and its decoded columns (width)
    and rows (height). A photo that doesn't decode has a blank dHash and no sizes."""

    sha256: str
    dhash: str
    decodes: bool
    width: int | None
    height: int | None


def photo_facts(data: bytes) -> PhotoFacts:
    """The facts of one photo's bytes. Nothing raises for bytes that don't decode, such
    as a HEIC saved as .jpg, a cut-off file or a header that declares over 50 MP."""
    sha256 = table.sha256_bytes(data)
    try:
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    except cv2.error:  # an empty buffer, or a size over the cap, raises
        image = None
    if image is None:
        return PhotoFacts(sha256, "", False, None, None)
    height, width = image.shape[:2]
    return PhotoFacts(sha256, _dhash(image), True, width, height)


def _dhash(image: np.ndarray) -> str:
    """The dHash as 16 lowercase hex digits.

    The photo is made gray and shrunk to 9 columns by 8 rows. Each bit is 1 where a
    pixel is brighter than its right neighbour. packbits makes row 0's first pair the
    most significant bit, so the hex reads row by row.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)  # (width, height)
    return np.packbits(small[:, :-1] > small[:, 1:]).tobytes().hex()
