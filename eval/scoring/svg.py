"""The report's two charts as plain SVG (spec C410): a level matrix for each
configuration, and Set B's error per measured wheel.

They follow the dataviz skill: one sequential hue for counts, thin marks, solid
hairlines, colours from its validated palette, and light and dark styles from a media
query inside the SVG. Every data mark, a filled cell or a dot, has a <title> tooltip.
GitHub shows an SVG as an image, where tooltips don't appear, so the report's table
twins carry the values there.
The text is the same on every run: coordinates have at most 2 decimals, attributes come
in a fixed order, and the only ids are the title's and the description's.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from xml.sax.saxutils import escape

from scoring.metrics import fmt_inches
from scoring.scale import LEVELS, NO_FLOOD_INDEX

_WIDTH = 560  # both charts', narrow enough for GitHub to show them at full size
_FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
# The colour roles, as CSS variables: (name, light, dark).
_ROLES = (
    ("surface", "#fcfcfb", "#1a1a19"),
    ("ink", "#0b0b0b", "#f0efec"),
    ("ink-2", "#52514e", "#c3c2b7"),
    ("muted", "#898781", "#898781"),
    ("grid", "#e1e0d9", "#2c2c2a"),
    ("axis", "#c3c2b7", "#383835"),
)
# Both charts' text: tick labels in muted ink, axis titles and notes in secondary ink.
_TEXT_RULES = (
    ".surface { fill: var(--surface); }",
    "text { font-size: 12px; }",
    ".tick { fill: var(--muted); }",
    ".label { fill: var(--ink-2); }",
    ".end { text-anchor: end; }",
    ".mid { text-anchor: middle; }",
)

# The level matrix

# The blue steps for counts, validated in each mode (C410), each as its fill and its
# count's ink, which APCA chose. A larger count stands further from the surface:
# darker in light mode, lighter in dark mode.
_LIGHT_STEPS = (  # blue 250, 400, 550 and 700
    ("#86b6ef", "#0b0b0b"),
    ("#3987e5", "#ffffff"),
    ("#1c5cab", "#ffffff"),
    ("#0d366b", "#ffffff"),
)
_DARK_STEPS = (  # blue 600, 450, 300 and 150
    ("#184f95", "#ffffff"),
    ("#2a78d6", "#ffffff"),
    ("#6da7ec", "#0b0b0b"),
    ("#b7d3f6", "#0b0b0b"),
)


def _step_rules(steps: Sequence[tuple[str, str]]) -> tuple[str, ...]:
    """The classes for each step's fill, s1 to s4, and its count's ink, n1 to n4."""
    return tuple(
        rule
        for step, (fill, ink) in enumerate(steps, 1)
        for rule in (f".s{step} {{ fill: {fill}; }}", f".n{step} {{ fill: {ink}; }}")
    )


# A step's class follows .cell, so a filled cell's step wins over the surface.
_MATRIX_RULES = (
    ".cell { fill: var(--surface); }",
    *_step_rules(_LIGHT_STEPS),
    ".diag { stroke: var(--axis); stroke-width: 1px; }",
    ".count { font-size: 13px; font-weight: 600; text-anchor: middle; }",
)
_CELL = 40  # a cell's pitch: 38 px of fill and a 2 px surface gap
_GRID_LEFT, _GRID_TOP = 136, 32
_MATRIX_HEIGHT = 500


def level_matrix_svg(
    matrix: Sequence[tuple[int, int, int]], *, title: str, description: str
) -> str:
    """One configuration's level matrix (C410). The alert's level runs down the side,
    deepest at the top, and Lusot's across, "no flood seen" first. `matrix` holds (the
    alert's index, Lusot's index, count), as SetAScores.matrix does, with
    NO_FLOOD_INDEX for "no flood seen". An index off the scale raises ValueError, so
    no count is dropped unseen."""
    counts = {}
    for alert, reading, count in matrix:
        if not (0 <= alert < len(LEVELS) and NO_FLOOD_INDEX <= reading < len(LEVELS)):
            raise ValueError("a matrix index lies outside the scale")
        if count:
            counts[alert, reading] = count
    if not counts:
        return _empty(title, description, "no answered photos")
    top = max(counts.values())
    readings = range(NO_FLOOD_INDEX, len(LEVELS))
    body = []
    for row, alert in enumerate(reversed(range(len(LEVELS)))):
        y = _GRID_TOP + row * _CELL
        body.append(_text("tick end", _GRID_LEFT - 8, y + 24, LEVELS[alert]))
        for column, reading in enumerate(readings):
            x = _GRID_LEFT + column * _CELL
            count = counts.get((alert, reading), 0)
            # ceil(4 count / top) in whole numbers, so the largest count takes step 4.
            step = (len(_LIGHT_STEPS) * count + top - 1) // top
            names = "cell" + (f" s{step}" if count else "")
            names += " diag" if reading == alert else ""
            cell = (
                f'<rect class="{names}" x="{x + 1}" y="{y + 1}"'
                f' width="{_CELL - 2}" height="{_CELL - 2}"/>'
            )
            if not count:
                body.append(cell)
                continue
            tooltip = f"alert {LEVELS[alert]}, Lusot {_reading(reading)}: {count}"
            body += [
                "<g>",
                f"<title>{escape(tooltip)}</title>",
                cell,
                _text(f"count n{step}", x + 20, y + 25, str(count)),
                "</g>",
            ]
    bottom = _GRID_TOP + len(LEVELS) * _CELL
    for column, reading in enumerate(readings):
        x = _GRID_LEFT + column * _CELL + 24
        body.append(_text("tick end", x, bottom + 12, _reading(reading), rotate=-45))
    body += [
        _text("label", _GRID_LEFT + 1, _GRID_TOP - 10, "shallower than the alert"),
        _text("label mid", 18, _GRID_TOP + 180, "Alert's level (MMDA or city)", -90),
        _text("label mid", _GRID_LEFT + 200, _MATRIX_HEIGHT - 12, "Lusot's level"),
    ]
    return _svg(
        _MATRIX_HEIGHT,
        title,
        description,
        body,
        rules=_MATRIX_RULES,
        dark_rules=_step_rules(_DARK_STEPS),
    )


def _reading(index: int) -> str:
    """A reading's name on the matrix: its level, or "no flood seen"."""
    return "no flood seen" if index == NO_FLOOD_INDEX else LEVELS[index]


# The error plot

_PLOT_ROLES = (*_ROLES, ("dot", "#2a78d6", "#3987e5"))
_PLOT_RULES = (
    ".grid { stroke: var(--grid); stroke-width: 1px; }",
    ".axis { stroke: var(--axis); stroke-width: 1px; }",
    ".target { stroke: var(--ink-2); stroke-width: 1px; }",
    ".median { stroke: var(--ink); stroke-width: 2px; }",
    # An 8 px dot inside a 2 px surface ring, which is painted first.
    (
        ".dot { fill: var(--dot); stroke: var(--surface); stroke-width: 4px;"
        " paint-order: stroke; }"
    ),
)
_PLOT_LEFT, _PLOT_TOP, _PLOT_RIGHT, _PLOT_BOTTOM = 64, 28, 480, 272
_PLOT_HEIGHT = 320


def error_plot_svg(
    errors: Sequence[Decimal], *, target: Decimal, title: str, description: str
) -> str:
    """Set B's error per measured wheel (C410): one dot per wheel, sorted, so its x is
    its rank; the target as a solid reference line, labelled from `target` itself;
    and the median as a short tick to the right of the dots."""
    ordered = sorted(errors)
    if not ordered:
        return _empty(title, description, "no measured wheels")
    step, top = _scale(max(ordered[-1], target))

    def y(value: Decimal) -> Decimal:
        return _PLOT_BOTTOM - value * (_PLOT_BOTTOM - _PLOT_TOP) / top

    body = []
    for index in range(int(top / step) + 1):
        tick = step * index
        line = "axis" if index == 0 else "grid"
        body += [
            _hline(line, _PLOT_LEFT, _PLOT_RIGHT, y(tick)),
            _text("tick end", _PLOT_LEFT - 8, _n(y(tick) + 4), _n(tick)),
        ]
    body.append(_hline("target", _PLOT_LEFT, _PLOT_RIGHT, y(target)))
    spacing = Decimal(_PLOT_RIGHT - _PLOT_LEFT) / len(ordered)
    for rank, error in enumerate(ordered, 1):
        x = _PLOT_LEFT + (rank - Decimal("0.5")) * spacing
        tooltip = f"wheel {rank}: {fmt_inches(error)}"
        body.append(
            f'<circle class="dot" cx="{_n(x)}" cy="{_n(y(error))}" r="4">'
            f"<title>{escape(tooltip)}</title></circle>"
        )
    median = y(statistics.median(ordered))
    label = f"release-gate target: {format(target, 'f')} in"
    middle = (_PLOT_TOP + _PLOT_BOTTOM) // 2
    body += [
        _hline("median", _PLOT_RIGHT + 4, _PLOT_RIGHT + 16, median),
        _text("label", _PLOT_RIGHT + 20, _n(median + 4), "median"),
        _text("label", _PLOT_LEFT + 4, _n(y(target) - 6), label),
        _text("label mid", 20, middle, "Error (inches)", -90),
        _text(
            "label mid",
            (_PLOT_LEFT + _PLOT_RIGHT) // 2,
            _PLOT_HEIGHT - 12,
            "Measured wheels, smallest error first",
        ),
    ]
    return _svg(
        _PLOT_HEIGHT,
        title,
        description,
        body,
        roles=_PLOT_ROLES,
        rules=_PLOT_RULES,
    )


def _scale(peak: Decimal) -> tuple[Decimal, Decimal]:
    """The y axis's tick step and top: the smallest step of 1, 2 or 5 times a power of
    ten that reaches `peak` within 5 steps, and the first tick at or above `peak`. The
    top is at least one step, so a peak of 0 still gives the axis a height."""
    power = peak.adjusted()
    step = next(
        Decimal(factor).scaleb(exponent)
        for exponent in (power - 1, power)
        for factor in (1, 2, 5)
        if 5 * Decimal(factor).scaleb(exponent) >= peak
    )
    top = (peak / step).to_integral_value(ROUND_CEILING) * step
    return step, max(top, step)


# Both charts


def _svg(
    height: int,
    title: str,
    description: str,
    body: Sequence[str],
    *,
    roles: Sequence[tuple[str, str, str]] = _ROLES,
    rules: Sequence[str] = (),
    dark_rules: Sequence[str] = (),
) -> str:
    """A chart: its title and description, which aria-labelledby names; the style, with
    each colour role a CSS variable that the dark block redefines; the surface; then
    the body. One element to a line, ending with a newline."""
    light = " ".join(f"--{name}: {value};" for name, value, _ in roles)
    dark = " ".join(f"--{name}: {value};" for name, _, value in roles)
    lines = [
        (
            '<svg xmlns="http://www.w3.org/2000/svg"'
            f' width="{_WIDTH}" height="{height}" viewBox="0 0 {_WIDTH} {height}"'
            ' role="img" aria-labelledby="title desc">'
        ),
        f'<title id="title">{escape(title)}</title>',
        f'<desc id="desc">{escape(description)}</desc>',
        "<style>",
        f"svg {{ {light} font-family: {_FONT}; }}",
        *_TEXT_RULES,
        *rules,
        "@media (prefers-color-scheme: dark) {",
        f"  svg {{ {dark} }}",
        *(f"  {rule}" for rule in dark_rules),
        "}",
        "</style>",
        f'<rect class="surface" width="{_WIDTH}" height="{height}"/>',
        *body,
        "</svg>",
    ]
    return "\n".join(lines) + "\n"


def _empty(title: str, description: str, message: str) -> str:
    """A chart with nothing to draw, which says so."""
    return _svg(80, title, description, [_text("label mid", _WIDTH // 2, 44, message)])


def _hline(names: str, left: int, right: int, y: Decimal) -> str:
    """A horizontal line from `left` to `right` at height `y`."""
    at = _n(y)
    return f'<line class="{names}" x1="{left}" y1="{at}" x2="{right}" y2="{at}"/>'


def _text(
    names: str, x: int | str, y: int | str, content: str, rotate: int | None = None
) -> str:
    """A text element with its content escaped, turned `rotate` degrees about its
    anchor when given."""
    turn = "" if rotate is None else f' transform="rotate({rotate} {x} {y})"'
    return f'<text class="{names}" x="{x}" y="{y}"{turn}>{escape(content)}</text>'


def _n(value: Decimal) -> str:
    """A coordinate rounded half up to 2 decimals, without trailing zeros."""
    text = format(value.quantize(Decimal("0.01"), ROUND_HALF_UP), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text
