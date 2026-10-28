"""Tests for the split's stratified draw (C204, as amended)."""

import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import draw
import events
import pytest
import synth

DATA = Path(__file__).resolve().parents[1]  # eval/data
SEEDS = (draw.SPLIT_SEED, *range(1, 8))  # SPLIT_SEED and seven other seeds
# C204's case: 5 deep events of 1 or 2 rows, E04, E08, … E20, among 15 others of 1 to 3.
DEEP = {"E04": 2, "E08": 1, "E12": 2, "E16": 1, "E20": 2}
OTHER = {f"E{n:02d}": 1 + n % 3 for n in range(1, 20) if n % 4}
SET_A = {event: (rows, True) for event, rows in DEEP.items()} | {
    event: (rows, False) for event, rows in OTHER.items()
}


def numbered(sizes: list[int]) -> dict[str, int]:
    """Each size under an event id, E01 first."""
    return {f"E{n:02d}": rows for n, rows in enumerate(sizes, start=1)}


def assert_split(found: draw.GroupDraw, sizes: dict[str, int]) -> None:
    """The two sides split the group's events, and the rows add up."""
    assert found.sealed | found.dev == set(sizes)
    assert not found.sealed & found.dev
    assert found.rows == sum(sizes.values())
    assert found.sealed_rows == sum(sizes[event] for event in found.sealed)


def test_deep_events_land_on_both_sides():
    """C204: drawn apart from the rest, the deep events land on both sides, as the
    others do, whatever the seed."""
    for seed in SEEDS:
        draws = draw.draw_set("A", SET_A, seed=seed)
        assert set(draws) == {"deep", "other"}
        for group, sizes in (("deep", DEEP), ("other", OTHER)):
            assert draws[group].group == group
            assert draws[group].sealed and draws[group].dev
            assert_split(draws[group], sizes)


def test_same_seed_same_split():
    """The draw depends on the events and the seed alone, never on the mapping's order,
    and another seed draws another split."""
    first = draw.draw_set("A", SET_A)
    assert draw.draw_set("A", SET_A) == first
    assert draw.draw_set("A", dict(reversed(SET_A.items()))) == first
    assert draw.draw_set("A", SET_A, seed=draw.SPLIT_SEED + 1) != first


def test_events_sort_by_number_past_e99():
    """The shuffle starts from the events in number order, where E100 follows E99, so
    renumbering a group's events in that order seals the same places."""
    target, cap = draw.SHARES["A"]
    low = draw.draw_group(numbered([1] * 12), group="other", target=target, cap=cap)
    high = draw.draw_group(
        {f"E{n}": 1 for n in range(95, 107)}, group="other", target=target, cap=cap
    )
    assert {events.event_number(event) + 94 for event in low.sealed} == {
        events.event_number(event) for event in high.sealed
    }


@pytest.mark.parametrize("count", range(2, 9))
@pytest.mark.parametrize("set_name", ["A", "A-neg"])
def test_group_of_two_or_more_has_both_sides(set_name, count):
    """Whatever its sizes, a group of 2 or more events ends with an event on each side.
    The walk seals nothing only when no event fits under the cap on its own, and then
    the smallest event moves."""
    target, cap = draw.SHARES[set_name]
    for sizes in (
        [1] * count,
        [3] + [1] * (count - 1),
        [3 * (count - 1)] + [2] * (count - 1),  # one event of 60% of the rows
    ):
        found = draw.draw_group(numbered(sizes), group="other", target=target, cap=cap)
        assert found.sealed and found.dev
        assert_split(found, numbered(sizes))
        nothing_fits = min(sizes) > cap * sum(sizes)
        assert found.moved == ("smallest_to_sealed" if nothing_fits else None)


def test_two_single_row_events_move_the_smallest():
    """1 row is over 9/20 of 2 rows, so the walk seals neither event, and E01, the lower
    number, moves to sealed."""
    target, cap = draw.SHARES["A"]
    found = draw.draw_group({"E01": 1, "E02": 1}, group="deep", target=target, cap=cap)
    assert found == draw.GroupDraw(
        group="deep",
        sealed=frozenset({"E01"}),
        dev=frozenset({"E02"}),
        rows=2,
        sealed_rows=1,
        moved="smallest_to_sealed",
    )


@pytest.mark.parametrize(
    ("sizes", "smallest"),
    [
        ({"E01": 6, "E02": 5}, "E02"),  # 5 rows is over 9/20 of 11, so nothing fits
        ({"E02": 1, "E01": 1}, "E01"),
        ({"E100": 1, "E99": 1}, "E99"),
    ],
)
def test_the_move_takes_the_fewest_rows_then_the_lowest_number(sizes, smallest):
    """Never the mapping's first event, and never the lowest id as text."""
    target, cap = draw.SHARES["A"]
    found = draw.draw_group(sizes, group="other", target=target, cap=cap)
    assert (found.sealed, found.moved) == ({smallest}, "smallest_to_sealed")


def test_shares_and_cap():
    """Set A's walk stops at 2/5 of the rows and never passes 9/20 of them: an event
    that brings the sealed side to 9/20 exactly fits, and one past it never goes to
    sealed by the walk."""
    target, cap = draw.SHARES["A"]
    found = draw.draw_group(numbered([1] * 20), group="other", target=target, cap=cap)
    assert (len(found.sealed), found.sealed_rows, found.moved) == (8, 8, None)
    found = draw.draw_group(
        {"E01": 9, "E02": 11}, group="other", target=target, cap=cap
    )
    assert (found.sealed, found.moved) == ({"E01"}, None)
    big = numbered([1, 1, 1, 1, 10, 1, 1, 1, 1, 1, 1])  # E05 holds 10 of the 20 rows
    for seed in SEEDS:
        found = draw.draw_group(big, group="other", target=target, cap=cap, seed=seed)
        assert "E05" in found.dev
        assert (found.sealed_rows, found.moved) == (8, None)


def test_a_neg_shares():
    """A-neg's walk stops at a third of the rows, and an event that brings the sealed
    side to its cap of 2/5 exactly fits. Its rows state no class, so it draws its other
    group alone."""
    draws = draw.draw_set("A-neg", {f"E{n:02d}": (1, False) for n in range(1, 16)})
    assert set(draws) == {"other"}
    assert (len(draws["other"].sealed), draws["other"].sealed_rows) == (5, 5)
    target, cap = draw.SHARES["A-neg"]
    found = draw.draw_group({"E01": 2, "E02": 3}, group="other", target=target, cap=cap)
    assert (found.sealed, found.moved) == ({"E01"}, None)


def test_shares_are_exact_fractions():
    """C204's shares, exactly. A float 0.4 lies just above 2/5, so an exact share of 8
    in 20 rows, as the golden draw seals in Set A, would compare below it."""
    assert draw.SHARES == {
        "A": (Fraction(2, 5), Fraction(9, 20)),
        "A-neg": (Fraction(1, 3), Fraction(2, 5)),
    }


def test_single_event_group_stays_dev():
    """One event can't be on both sides, and moving it would empty its group's dev
    side, so it stays dev, with no move."""
    draws = draw.draw_set("A", {"E01": (2, True), "E02": (1, False), "E03": (1, False)})
    assert draws["deep"] == draw.GroupDraw(
        group="deep",
        sealed=frozenset(),
        dev=frozenset({"E01"}),
        rows=2,
        sealed_rows=0,
        moved=None,
    )


@pytest.mark.parametrize("set_name", ["A", "A-neg"])
def test_fewer_than_two_events_stops(set_name):
    """The split prints the set's name from args[0], and the error holds nothing else,
    so no event id or count reaches the output (C201)."""
    for few in ({}, {"E01": (3, False)}):
        with pytest.raises(draw.TooFewEvents) as stopped:
            draw.draw_set(set_name, few)
        assert stopped.value.args == (set_name,)
        assert str(stopped.value) == set_name


def test_golden_draw():
    """Pins random.Random(20261030)'s shuffle on Python 3.13, a fresh generator for each
    group. The events are Task 13's synthetic Set A: 3, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1 and
    1 rows, with the 2nd, 4th, 6th, 9th and 11th deep."""
    golden = {
        "E01": (3, False),
        "E02": (2, True),
        "E03": (2, False),
        "E04": (2, True),
        "E05": (2, False),
        "E06": (2, True),
        "E07": (2, False),
        "E08": (1, False),
        "E09": (1, True),
        "E10": (1, False),
        "E11": (1, True),
        "E12": (1, False),
    }
    # Worked out by hand from random.Random(20261030)'s shuffles before draw.py existed.
    assert draw.draw_set("A", golden) == {
        "deep": draw.GroupDraw(
            group="deep",
            sealed=frozenset({"E02", "E09"}),
            dev=frozenset({"E04", "E06", "E11"}),
            rows=8,
            sealed_rows=3,
            moved=None,
        ),
        "other": draw.GroupDraw(
            group="other",
            sealed=frozenset({"E01", "E07"}),
            dev=frozenset({"E03", "E05", "E08", "E10", "E12"}),
            rows=12,
            sealed_rows=5,
            moved=None,
        ),
    }


def test_draw_loads_no_third_party_module_and_prints_nothing():
    """The draw uses the standard library and events alone. Printed ids would name the
    sealed side, so a fresh interpreter that imports it and draws prints only the list
    of numpy, OpenCV and py7zr modules loaded, which is empty."""
    probe = (
        f"import sys; sys.path.insert(0, {json.dumps(str(DATA))}); import draw; "
        "draw.draw_set('A', {'E01': (1, True), 'E02': (1, True), 'E03': (2, False)}); "
        "print(sorted({'numpy', 'cv2', 'py7zr'} & set(sys.modules)))"
    )
    done = subprocess.run(
        [sys.executable, "-c", probe],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "[]\n", "")
