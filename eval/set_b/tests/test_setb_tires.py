"""Tests for Set B's tire codes (plan Table 7; C212)."""

import pytest
import tires


@pytest.mark.parametrize(
    ("code", "expected", "diameter"),
    [
        ("175/65R14", (175, 65, 14), 22.9567),
        ("185/55R15", (185, 55, 15), 23.0118),
        ("215/70R16C", (215, 70, 16), 27.8504),
        ("P205/55ZR16 91V", (205, 55, 16), None),
        ("LT235/75R15", (235, 75, 15), None),
        ("p205/55zr16 91v", (205, 55, 16), None),  # any case
        ("215/70R16C 108/106R", (215, 70, 16), None),  # a C, then the load index
        ("205/55 R 16 91 V", (205, 55, 16), None),  # spaces around the R
        ("195R14C", "no_aspect_ratio", None),
        ("7.00R16", "no_aspect_ratio", None),  # a radial width in inches
        ("14 inch", "bad_tire_code", None),
        ("", "bad_tire_code", None),
        ("295/80R22.5", "bad_tire_code", None),  # a half-inch rim, never read as 22
        ("275/70R22.5", "bad_tire_code", None),
        ("7.50-16", "bad_tire_code", None),  # bias-ply
        ("175/65R1491T", "bad_tire_code", None),  # digits glued to the rim
    ],
)
def test_parse_tire_codes(code, expected, diameter):
    """A metric radial code gives its width, aspect ratio and rim, whatever its case,
    prefix, Z, C suffix, load index and speed rating, and Table 7's overall diameter.
    A code without an aspect ratio, or one that isn't a whole-inch metric radial size,
    gives its cause instead."""
    found = tires.parse_tire_code(code)
    if isinstance(expected, str):
        assert found == expected
        return
    assert found == tires.TireSize(*expected)
    if diameter is not None:
        assert tires.diameter_in(found) == pytest.approx(diameter, abs=5e-5)
