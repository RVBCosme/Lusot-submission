"""Lusot photo analysis: the face blur, the Meta client, the probes and the analysis Lambda."""

import os

# OpenCV refuses to decode an image over 50 MP (R25). It reads the cap once, when cv2
# loads, and any module of this package may be the first to load it (R26).
os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", "50000000")
