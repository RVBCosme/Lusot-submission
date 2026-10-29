"""Set B's drawn water (C211): opaque muddy water below a waterline, composited onto a
car photo or a crop of it.

Every pixel at or below the line's row in its column is water, and every pixel above
it is the photo's own. The water's base is a muddy colour whose brightness ripples in
low-frequency bands that follow the line. Over it the scene above the line is mirrored
about the line, darkened and blended in. The mirror reads only the scene above the
line, in the pixel's own column, so nothing of the photo below the line shows. The
texture is drawn from the photo's generator alone, the same number of draws for any
line, so the same seed gives the same water.
"""

import numpy as np

# The version of the generator that draws Set B's water and crops, written in every
# truth row. It reads set-b-gen-v1, never an id-shaped V1, which records refuse (S-R16).
GENERATOR_VERSION = "set-b-gen-v1"

# The water's base colour in BGR, a muddy brown. Each photo's water shifts it by up to
# MUD_SHIFT in each channel.
MUD = np.array([60.0, 90.0, 115.0])
MUD_SHIFT = 12.0


def composite(
    image: np.ndarray, rows: np.ndarray, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """The BGR image with water drawn below the line, and the water mask.

    rows holds the line's row in each of the image's columns, as truth.line_rows gives
    it, unclipped. The mask is bool, of the image's (height, width), and True exactly
    where y >= rows[x]: a row at or above 0 floods the whole column, and one at or past
    the height leaves it dry. A water pixel j rows below its column's line, row r + j,
    mirrors row r - 1 - j. Where that row would lie above the frame, the base alone
    fills the pixel. The image itself is left as it was.
    """
    height, width = image.shape[:2]
    water = np.arange(height)[:, None] >= rows[None, :]
    colour = MUD + rng.uniform(-MUD_SHIFT, MUD_SHIFT, 3)
    # The ripples: bands spaced 2 to 5 % of the image's height apart, so a shrunk
    # crop's ripples look like a full one's. They sway gently across the width, and
    # brighten or darken the base by 8 to 15 % at most.
    period = height * rng.uniform(0.02, 0.05)
    phase, sway_phase = rng.uniform(0, 2 * np.pi, 2)
    sway = rng.uniform(0.5, 2.0)  # radians of phase the bands sway by
    sway_period = width * rng.uniform(0.3, 0.8)
    strength = rng.uniform(0.08, 0.15)
    # The mirror: how much of the scene shows, and how darkened.
    blend = rng.uniform(0.25, 0.45)
    dark = rng.uniform(0.45, 0.65)

    ys, xs = np.nonzero(water)
    depth = ys - rows[xs]  # rows below the line, 0 on it
    angle = 2 * np.pi * depth / period + phase
    angle += sway * np.sin(2 * np.pi * xs / sway_period + sway_phase)
    surface = (1 + strength * np.sin(angle))[:, None] * colour
    source = rows[xs] - 1 - depth
    seen = source >= 0
    mirrored = dark * image[source[seen], xs[seen]]
    surface[seen] = (1 - blend) * surface[seen] + blend * mirrored
    out = image.copy()
    out[ys, xs] = np.clip(np.rint(surface), 0, 255).astype(np.uint8)
    return out, water
