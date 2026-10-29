"""Tests for Set B's drawn water (C211): every pixel at or below the line is opaque
muddy water, with ripples and the scene mirrored about the line, and every pixel above
it is the photo's own."""

import numpy as np
import record_io
import water

SHAPE = (120, 160)  # (height, width), numpy's order


def scene(seed: int) -> np.ndarray:
    """A random BGR image of SHAPE."""
    return np.random.default_rng(seed).integers(0, 256, (*SHAPE, 3), dtype=np.uint8)


def sloped_rows() -> np.ndarray:
    """A line that falls from row 50 at the left to row 89 at the right."""
    return 50 + np.arange(SHAPE[1]) // 4


def below(rows: np.ndarray) -> np.ndarray:
    """The rule the water mask must follow: True exactly where y >= rows[x]."""
    return np.arange(SHAPE[0])[:, None] >= rows[None, :]


def test_water_hides_everything_below_the_line():
    """Two images equal above the line and different below it give identical
    composites: the water is opaque, and the mirror reads only the scene above."""
    rows = sloped_rows()
    a, b = scene(1), scene(2)
    b[~below(rows)] = a[~below(rows)]
    assert not np.array_equal(a, b)
    out_a, water_a = water.composite(a, rows, np.random.default_rng(5))
    out_b, water_b = water.composite(b, rows, np.random.default_rng(5))
    assert np.array_equal(out_a, out_b) and np.array_equal(water_a, water_b)


def test_pixels_above_the_line_are_unchanged():
    """Above the line the composite is the photo, the photo itself is left as it was,
    and below it every pixel is drawn."""
    rows = sloped_rows()
    image = scene(1)
    kept = image.copy()
    out, mask = water.composite(image, rows, np.random.default_rng(5))
    assert np.array_equal(image, kept)
    assert out.dtype == np.uint8 and out.shape == image.shape
    assert np.array_equal(out[~mask], image[~mask])
    assert np.count_nonzero((out != image).any(axis=2) & mask) > 0.9 * mask.sum()


def test_water_mask_is_exactly_below_the_rows():
    """Addition 4: the mask is bool, of shape (H, W), and True exactly where
    y >= rows[x], checked pixel by pixel."""
    rows = sloped_rows()
    _, mask = water.composite(scene(1), rows, np.random.default_rng(5))
    assert mask.dtype == bool and mask.shape == SHAPE
    for x in range(SHAPE[1]):
        for y in range(SHAPE[0]):
            assert mask[y, x] == (y >= rows[x])


def test_same_seed_same_water():
    """The texture comes from the generator alone: the same seed gives the same
    composite, and another seed other water."""
    rows = sloped_rows()
    first = water.composite(scene(1), rows, np.random.default_rng(5))
    again = water.composite(scene(1), rows, np.random.default_rng(5))
    other = water.composite(scene(1), rows, np.random.default_rng(6))
    assert np.array_equal(first[0], again[0]) and np.array_equal(first[1], again[1])
    assert not np.array_equal(first[0], other[0])


def test_line_partly_outside_the_frame():
    """Addition 3: line_rows doesn't clip, so a line can run from above the frame to
    below it. A row at or above 0 floods the whole column, and one at or past the
    height leaves the column dry. A flooded column has no scene above the line to
    mirror, so its water, the banded base alone, is the same for any photo."""
    rows = np.linspace(-60, SHAPE[0] + 60, SHAPE[1]).round().astype(np.int64)
    assert rows[0] < 0 and rows[-1] > SHAPE[0]
    a, b = scene(1), scene(2)
    out_a, mask = water.composite(a, rows, np.random.default_rng(5))
    out_b, _ = water.composite(b, rows, np.random.default_rng(5))
    assert np.array_equal(mask, below(rows))
    flooded, dry = rows <= 0, rows >= SHAPE[0]
    assert flooded.any() and dry.any()
    assert mask[:, flooded].all() and not mask[:, dry].any()
    assert np.array_equal(out_a[:, flooded], out_b[:, flooded])
    assert np.array_equal(out_a[:, dry], a[:, dry])
    column = out_a[:, np.flatnonzero(flooded)[0]].astype(int)
    assert len(np.unique(column.sum(axis=1))) > 1  # the ripples band it


def test_the_scene_is_mirrored_about_the_line():
    """Each pixel j rows above a column's line shows only in the pixel j rows below
    it, row r - 1 - j in row r + j. Past twice the line's depth the mirror's source
    row would lie above the frame, so the base alone fills those pixels."""
    rows = np.full(SHAPE[1], 30, np.int64)
    image = scene(1)
    out, _ = water.composite(image, rows, np.random.default_rng(5))
    for j in (0, 7, 29):
        changed = image.copy()
        # Each channel moves by at least 128, so the darkened blend still shows it.
        changed[29 - j, 40] = np.where(changed[29 - j, 40] > 127, 0, 255)
        out_changed, _ = water.composite(changed, rows, np.random.default_rng(5))
        moved = np.argwhere((out_changed != out).any(axis=2))
        assert moved.tolist() == [[29 - j, 40], [30 + j, 40]]
    other, _ = water.composite(scene(2), rows, np.random.default_rng(5))
    assert np.array_equal(out[60:], other[60:])


def test_generator_version_passes_the_record_guard():
    """Addition 7: the version stays set-b-gen-v1, which the records' id check (S-R16)
    lets through, as it never would V1."""
    assert water.GENERATOR_VERSION == "set-b-gen-v1"
    record_io.record_bytes({"generator_version": water.GENERATOR_VERSION})
