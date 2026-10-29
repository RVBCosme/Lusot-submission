"""Set B's tire codes (plan Table 7; C212).

A car's tire code, as on its sidewall, gives the tire's overall diameter, and that sets
each wheel's scale (G3). Only metric radial codes with a whole-inch rim are read, since
Set B is passenger cars. A radial size without an aspect ratio, such as 195R14C or
7.00R16, can't give a diameter. Anything else, such as the bias-ply 7.50-16 or the
truck size 295/80R22.5, isn't read at all: a rim of 22.5 must never pass as 22.
"""

import re
from dataclasses import dataclass

# The rim's whole number, an optional C, then the end, or a space before anything else,
# such as the load index and speed rating. So no digit and no ".5" can join the rim.
_RIM = r"\s*Z?R\s*(\d{2})C?(?:\s.*)?"
# A metric radial code, in any case: an optional P or LT prefix, the width in mm, the
# aspect ratio, an optional Z, then R and the rim. Spaces around the R, as some
# sidewalls print it (205/55 R 16), are allowed.
_METRIC = re.compile(r"(?:P|LT)?(\d{3})/(\d{2})" + _RIM, re.IGNORECASE)
# A radial size without an aspect ratio: its width in mm (195) or in inches (7.00).
_NO_ASPECT = re.compile(r"(?:P|LT)?(?:\d{3}|\d{1,2}\.\d{2})" + _RIM, re.IGNORECASE)
MM_PER_IN = 25.4


@dataclass(frozen=True)
class TireSize:
    """A metric radial size: the width in mm, the aspect ratio in percent (the
    sidewall's height over the width), and the rim's diameter in whole inches."""

    width_mm: int
    aspect: int
    rim_in: int


def parse_tire_code(code: str) -> TireSize | str:
    """The size a tire code gives, or its cause: no_aspect_ratio for a radial size
    without one, and bad_tire_code for anything else.

    It accepts any case, surrounding spaces, an optional P or LT prefix, a Z before the
    R (205/55ZR16), a C suffix (215/70R16C), and anything after the rim once a space
    separates it, such as the load index and speed rating (205/55R16 91V).
    """
    text = code.strip()
    found = _METRIC.fullmatch(text)
    if found is not None:
        width, aspect, rim = found.groups()
        return TireSize(int(width), int(aspect), int(rim))
    if _NO_ASPECT.fullmatch(text) is not None:
        return "no_aspect_ratio"
    return "bad_tire_code"


def diameter_in(size: TireSize) -> float:
    """The tire's overall diameter in inches, as plan Table 7 gives it: the rim plus two
    sidewalls, each the width times the aspect ratio."""
    return size.rim_in + 2 * size.width_mm * size.aspect / 100 / MM_PER_IN
