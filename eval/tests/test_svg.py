"""The report's charts as plain SVG: the level matrix and Set B's error plot (C410)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal
from xml.etree import ElementTree

import pytest
from scoring.scale import LEVELS, NO_FLOOD_INDEX
from scoring.svg import error_plot_svg, level_matrix_svg

SVG = "{http://www.w3.org/2000/svg}"
DARK = "@media (prefers-color-scheme: dark)"

# (the alert's index, Lusot's index, count), as SetAScores.matrix gives them. Each count
# differs, so each can be found by its text, and 8 is the largest.
MATRIX = (
    (0, NO_FLOOD_INDEX, 1),  # below_gutter, read as no flood seen
    (2, 2, 3),  # half_knee, exactly
    (4, 3, 2),  # knee, read as half_tire
    (4, 4, 8),  # knee, exactly
    (5, 7, 5),  # tire, read as chest
)
# Measured wheels' errors in inches, unsorted.
ERRORS = (Decimal(4), Decimal("0.75"), Decimal("1.5"), Decimal("0.25"), Decimal(2))

# The colour roles and the matrix's steps, as the brief gives them (C410).
LIGHT_ROLES = (
    "--surface: #fcfcfb;",
    "--ink: #0b0b0b;",
    "--ink-2: #52514e;",
    "--muted: #898781;",
    "--grid: #e1e0d9;",
    "--axis: #c3c2b7;",
)
DARK_ROLES = (
    "--surface: #1a1a19;",
    "--ink: #f0efec;",
    "--ink-2: #c3c2b7;",
    "--muted: #898781;",
    "--grid: #2c2c2a;",
    "--axis: #383835;",
)
# Each step's fill and its count's ink.
LIGHT_STEPS = (
    ("#86b6ef", "#0b0b0b"),
    ("#3987e5", "#ffffff"),
    ("#1c5cab", "#ffffff"),
    ("#0d366b", "#ffffff"),
)
DARK_STEPS = (
    ("#184f95", "#ffffff"),
    ("#2a78d6", "#ffffff"),
    ("#6da7ec", "#0b0b0b"),
    ("#b7d3f6", "#0b0b0b"),
)
FONT = 'font-family: system-ui, -apple-system, "Segoe UI", sans-serif;'


def matrix_svg(matrix: Sequence[tuple[int, int, int]] = MATRIX) -> str:
    """A level matrix with a fixed title and description."""
    return level_matrix_svg(
        matrix, title="Levels: Landmark alone", description="Counts by level."
    )


def plot_svg(
    errors: Sequence[Decimal] = ERRORS, target: Decimal = Decimal("2.5")
) -> str:
    """An error plot with a fixed title and description."""
    return error_plot_svg(
        errors, target=target, title="Set B errors", description="Errors by wheel."
    )


def classes(element: ElementTree.Element) -> list[str]:
    return element.get("class", "").split()


def number(element: ElementTree.Element, name: str) -> float:
    return float(element.get(name))


def cells(root: ElementTree.Element) -> list[ElementTree.Element]:
    """The matrix's cells, filled or not."""
    return [rect for rect in root.iter(SVG + "rect") if "cell" in classes(rect)]


def titled_cells(root: ElementTree.Element) -> dict[str, ElementTree.Element]:
    """Each filled cell's rect, by its tooltip."""
    return {
        group.find(SVG + "title").text: group.find(SVG + "rect")
        for group in root.iter(SVG + "g")
        if group.find(SVG + "title") is not None
    }


def texts(root: ElementTree.Element) -> list[str]:
    return [element.text for element in root.iter(SVG + "text")]


def lines(root: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [line for line in root.iter(SVG + "line") if name in classes(line)]


def step_of(element: ElementTree.Element, prefix: str) -> str | None:
    """The element's step class, such as s2 for a fill or n2 for an ink."""
    found = [name for name in classes(element) if re.fullmatch(prefix + "[1-4]", name)]
    return found[0] if found else None


def test_level_matrix_parses():
    text = matrix_svg()
    root = ElementTree.fromstring(text)
    assert root.tag == SVG + "svg"
    assert (root.get("role"), root.get("aria-labelledby")) == ("img", "title desc")
    assert [title.get("id") for title in root.findall(SVG + "title")] == ["title"]
    assert [desc.get("id") for desc in root.findall(SVG + "desc")] == ["desc"]
    shown = texts(root)
    assert [shown.count(str(count)) for _, _, count in MATRIX] == [1] * len(MATRIX)
    assert "0" not in shown
    assert len(cells(root)) == 9 * 10
    filled = [rect for rect in cells(root) if step_of(rect, "s")]
    titled = titled_cells(root)
    assert len(filled) == len(titled) == len(MATRIX)
    assert {id(rect) for rect in titled.values()} == {id(rect) for rect in filled}
    assert "alert knee, Lusot half_tire: 2" in titled
    assert "MMDA's level" not in text
    assert "safe" not in text.lower()


def test_cells_run_deepest_first():
    root = ElementTree.fromstring(matrix_svg(((8, NO_FLOOD_INDEX, 1), (0, 8, 2))))
    titled = titled_cells(root)
    xs = [number(rect, "x") for rect in cells(root)]
    ys = [number(rect, "y") for rect in cells(root)]
    top_left = titled["alert above_chest, Lusot no flood seen: 1"]
    bottom_right = titled["alert below_gutter, Lusot above_chest: 2"]
    assert (number(top_left, "x"), number(top_left, "y")) == (min(xs), min(ys))
    assert (number(bottom_right, "x"), number(bottom_right, "y")) == (max(xs), max(ys))
    # The row labels sit left of the grid, the column labels below it.
    ticks = [text for text in root.iter(SVG + "text") if "tick" in classes(text)]
    bottom = max(number(rect, "y") + number(rect, "height") for rect in cells(root))
    rows = sorted(
        (text for text in ticks if number(text, "x") < min(xs)),
        key=lambda text: number(text, "y"),
    )
    columns = sorted(
        (text for text in ticks if number(text, "y") > bottom),
        key=lambda text: number(text, "x"),
    )
    assert [text.text for text in rows] == list(reversed(LEVELS))
    assert [text.text for text in columns] == ["no flood seen", *LEVELS]
    assert "Alert's level (MMDA or city)" in texts(root)
    assert "Lusot's level" in texts(root)


def test_shallower_label_sits_above_the_diagonal():
    root = ElementTree.fromstring(matrix_svg())
    (label,) = [
        text
        for text in root.iter(SVG + "text")
        if text.text == "shallower than the alert"
    ]
    diagonal = sorted(
        (rect for rect in cells(root) if "diag" in classes(rect)),
        key=lambda rect: number(rect, "x"),
    )
    # One outlined cell per row, rising from the bottom left to the top right, and
    # none under "no flood seen".
    heights = [number(rect, "y") for rect in diagonal]
    assert len(diagonal) == 9
    assert heights == sorted(set(heights), reverse=True)
    left = min(number(rect, "x") for rect in cells(root))
    assert number(diagonal[0], "x") > left
    titled = titled_cells(root)
    assert "diag" in classes(titled["alert knee, Lusot knee: 8"])
    assert "diag" not in classes(titled["alert knee, Lusot half_tire: 2"])
    # Left of the top row's diagonal cell, and above the grid, clear of every count.
    top = min(number(rect, "y") for rect in cells(root))
    bottom_row = max(number(rect, "y") for rect in cells(root))
    assert number(label, "x") < number(diagonal[-1], "x")
    assert number(label, "y") < bottom_row
    assert number(label, "y") < top


def test_counts_take_their_steps():
    # ceil(4 c / max_count): with 8 the largest, 1 and 2 take step 1, 3 step 2,
    # 5 step 3 and 8 step 4; with 3 the largest, 1 takes step 2.
    for matrix, expected in (
        (MATRIX, {1: 1, 2: 1, 3: 2, 5: 3, 8: 4}),
        (((4, 4, 1), (5, 5, 2), (6, 6, 3)), {1: 2, 2: 3, 3: 4}),
    ):
        root = ElementTree.fromstring(matrix_svg(matrix))
        found = {}
        for group in root.iter(SVG + "g"):
            rect, count = group.find(SVG + "rect"), group.find(SVG + "text")
            found[int(count.text)] = (step_of(rect, "s"), step_of(count, "n"))
        assert found == {
            count: (f"s{step}", f"n{step}") for count, step in expected.items()
        }
        # No fill is written on a cell: the style's classes give every colour.
        assert all(
            rect.get("fill") is None and rect.get("style") is None
            for rect in cells(root)
        )
    light, dark = matrix_svg().split(DARK)
    for step, (fill, ink) in enumerate(LIGHT_STEPS, 1):
        assert f".s{step} {{ fill: {fill}; }}" in light
        assert f".n{step} {{ fill: {ink}; }}" in light
    for step, (fill, ink) in enumerate(DARK_STEPS, 1):
        assert f".s{step} {{ fill: {fill}; }}" in dark
        assert f".n{step} {{ fill: {ink}; }}" in dark
    assert ".cell { fill: var(--surface); }" in light
    assert ".diag { stroke: var(--axis); stroke-width: 1px; }" in light


def test_error_plot_parses():
    text = plot_svg()
    root = ElementTree.fromstring(text)
    assert root.tag == SVG + "svg"
    assert (root.get("role"), root.get("aria-labelledby")) == ("img", "title desc")
    assert [title.get("id") for title in root.findall(SVG + "title")] == ["title"]
    assert [desc.get("id") for desc in root.findall(SVG + "desc")] == ["desc"]
    # One 8 px dot per wheel, in rank order: evenly spaced, each higher than the last.
    dots = list(root.iter(SVG + "circle"))
    assert [dot.find(SVG + "title").text for dot in dots] == [
        "wheel 1: 0.25 in",
        "wheel 2: 0.75 in",
        "wheel 3: 1.50 in",
        "wheel 4: 2.00 in",
        "wheel 5: 4.00 in",
    ]
    assert {dot.get("r") for dot in dots} == {"4"}
    xs = [number(dot, "cx") for dot in dots]
    spacing = xs[1] - xs[0]
    assert spacing > 0
    assert all(abs(x - xs[0] - rank * spacing) < 0.02 for rank, x in enumerate(xs))
    ys = [number(dot, "cy") for dot in dots]
    assert ys == sorted(set(ys), reverse=True)
    # The target's line, labelled from the target, just above it.
    (target,) = lines(root, "target")
    assert target.get("y1") == target.get("y2")
    (label,) = [
        text
        for text in root.iter(SVG + "text")
        if text.text == "release-gate target: 2.5 in"
    ]
    assert 0 < number(target, "y1") - number(label, "y") < 12
    # The median's short tick, labelled.
    (tick,) = lines(root, "median")
    assert tick.get("y1") == tick.get("y2")
    assert number(tick, "x2") - number(tick, "x1") < 20
    assert "median" in texts(root)
    assert "safe" not in text.lower()


def test_median_tick_sits_at_the_median():
    # An odd count: the tick is level with the middle dot.
    root = ElementTree.fromstring(
        plot_svg((Decimal("0.5"), Decimal("1.25"), Decimal(4)), Decimal(3))
    )
    (tick,) = lines(root, "median")
    middle = list(root.iter(SVG + "circle"))[1]
    assert tick.get("y1") == tick.get("y2") == middle.get("cy")
    assert "release-gate target: 3 in" in texts(root)
    # An even count: the mean of the middle two, here 3 in, level with the target.
    root = ElementTree.fromstring(
        plot_svg(tuple(Decimal(value) for value in ("1", "2", "4", "9")), Decimal(3))
    )
    (tick,) = lines(root, "median")
    (target,) = lines(root, "target")
    assert tick.get("y1") == tick.get("y2") == target.get("y1")


def test_error_plot_scale_and_axis():
    # A peak of 4 in from an error gives steps of 1 in. A peak of 6.3 in from the
    # target gives steps of 2 in, so the target must set the scale too.
    for errors, target, ticks, wheel, value in (
        (ERRORS, Decimal("2.5"), ["0", "1", "2", "3", "4"], "wheel 4: 2.00 in", "2"),
        (
            (Decimal("0.5"), Decimal(4)),
            Decimal("6.3"),
            ["0", "2", "4", "6", "8"],
            "wheel 2: 4.00 in",
            "4",
        ),
    ):
        root = ElementTree.fromstring(plot_svg(errors, target))
        # The gridlines and their labels, from the axis up.
        gridlines = sorted(
            lines(root, "axis") + lines(root, "grid"),
            key=lambda line: -number(line, "y1"),
        )
        labels = sorted(
            (text for text in root.iter(SVG + "text") if "tick" in classes(text)),
            key=lambda text: -number(text, "y"),
        )
        assert [label.text for label in labels] == ticks
        assert len(gridlines) == len(ticks)
        assert "axis" in classes(gridlines[0])
        # Each label sits 4 px below its gridline.
        for line, label in zip(gridlines, labels):
            assert Decimal(label.get("y")) - Decimal(line.get("y1")) == 4
        # The dot of a value on the scale sits on that value's gridline.
        by_label = {label.text: line for line, label in zip(gridlines, labels)}
        dots = list(root.iter(SVG + "circle"))
        (marked,) = [dot for dot in dots if dot.find(SVG + "title").text == wheel]
        assert marked.get("cy") == by_label[value].get("y1")
        # Every dot lies between the top gridline and the axis.
        axis, top = number(gridlines[0], "y1"), number(gridlines[-1], "y1")
        assert all(top <= number(dot, "cy") <= axis for dot in dots)
        # Both lie inside the canvas, which a scale moving the gridlines and the
        # dots together would break.
        assert 0 <= top < axis <= number(root, "height")


def test_charts_are_deterministic():
    # Three wheels and a 3 in top make thirds, which round to 2 decimals.
    thirds = (Decimal("0.1"), Decimal(1), Decimal("2.9"))
    charts = (matrix_svg(), plot_svg(), plot_svg(thirds, Decimal(3)))
    assert (matrix_svg(), plot_svg(), plot_svg(thirds, Decimal(3))) == charts
    # The same counts, or the same errors, in another order draw the same chart.
    assert matrix_svg(tuple(reversed(MATRIX))) == charts[0]
    assert plot_svg(tuple(sorted(ERRORS))) == charts[1]
    places = ("x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "width", "height")
    for text in charts:
        for element in ElementTree.fromstring(text).iter():
            values = [element.get(name) for name in places if element.get(name)]
            values += re.findall("[-0-9.]+", element.get("transform", ""))
            for value in values:
                assert re.fullmatch("-?[0-9]+(\\.[0-9]{1,2})?", value), value


def test_dark_mode_and_no_dashes():
    for text in (matrix_svg(), plot_svg()):
        assert "prefers-color-scheme: dark" in text
        assert "stroke-dasharray" not in text
        light, dark = text.split(DARK)
        assert [role for role in LIGHT_ROLES if role not in light] == []
        assert [role for role in DARK_ROLES if role not in dark] == []
        assert FONT in light
    light, dark = plot_svg().split(DARK)
    assert "--dot: #2a78d6;" in light
    assert "--dot: #3987e5;" in dark


def test_empty_inputs():
    for text, message in (
        (matrix_svg(()), "no answered photos"),
        (matrix_svg(((4, 4, 0),)), "no answered photos"),
        (plot_svg(()), "no measured wheels"),
    ):
        root = ElementTree.fromstring(text)
        assert root.tag == SVG + "svg"
        assert (root.get("role"), root.get("aria-labelledby")) == ("img", "title desc")
        assert texts(root) == [message]
        assert "prefers-color-scheme: dark" in text


@pytest.mark.parametrize(
    "entry", [(9, 0, 1), (-1, 0, 1), (0, NO_FLOOD_INDEX - 1, 1), (0, 9, 1)]
)
def test_an_index_off_the_scale_raises(entry):
    with pytest.raises(ValueError, match="outside the scale"):
        matrix_svg((entry,))


def test_caller_text_is_escaped():
    title = "Levels <landmark> & geometry"
    description = "Counts by \"level\" & 'class' </desc>"
    for text in (
        level_matrix_svg(MATRIX, title=title, description=description),
        level_matrix_svg((), title=title, description=description),
        error_plot_svg(ERRORS, target=Decimal(3), title=title, description=description),
    ):
        root = ElementTree.fromstring(text)
        assert root.find(SVG + "title").text == title
        assert root.find(SVG + "desc").text == description
