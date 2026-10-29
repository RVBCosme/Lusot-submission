"""The split's stratified draw (C204).

The split keeps each event whole on one side (C203), and a few deep floods could all
fall on one side of a single shuffle. So each set draws its deep events, those with a
row that states NPLV or NPATV, apart from the rest: each group walks its own shuffle,
and a group of 2 or more events ends with an event on each side. The seed is fixed
here, before any row exists, so the split can't be redrawn until one suits.
"""

import random
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from events import event_number

SPLIT_SEED = 20261030
# Each set's target and cap, as shares of a group's rows: the walk stops once the
# sealed side holds the target, and never takes it past the cap.
SHARES = {
    "A": (Fraction(2, 5), Fraction(9, 20)),
    "A-neg": (Fraction(1, 3), Fraction(2, 5)),
}


class TooFewEvents(ValueError):
    """A set with fewer than 2 events can't have one on each side, so the split stops.
    The one argument is the set's name, which the split prints, and nothing else
    (C201)."""


@dataclass(frozen=True)
class GroupDraw:
    """One group's draw: the events on each side, and the group's rows and the sealed
    side's. moved is smallest_to_sealed when the walk sealed nothing and the group's
    smallest event moved to sealed, otherwise None. The cap keeps the walk under half
    the rows, so the dev side is never empty."""

    group: str
    sealed: frozenset[str]
    dev: frozenset[str]
    rows: int
    sealed_rows: int
    moved: str | None


def draw_group(
    sizes: Mapping[str, int],
    *,
    group: str,
    target: Fraction,
    cap: Fraction,
    seed: int = SPLIT_SEED,
) -> GroupDraw:
    """Draw one group, given each event's rows.

    The events, sorted by number, are shuffled with a fresh random.Random(seed), so the
    draw depends on neither the mapping's order nor another group's draw. Walking that
    order, an event goes to sealed only if the sealed rows then stay at or under cap ×
    rows, and the walk stops once they reach target × rows. Both comparisons are exact,
    in Fractions, so no rounding decides an event that lands on the cap or the target.

    When the walk seals nothing in a group of 2 or more events, the smallest event, by
    rows and then by number, moves to sealed, even past the cap; the record shows the
    share. A single event stays dev.
    """
    order = sorted(sizes, key=event_number)
    random.Random(seed).shuffle(order)
    rows = sum(sizes.values())
    sealed: set[str] = set()
    sealed_rows = 0
    for event_id in order:
        if sealed_rows >= target * rows:
            break
        if sealed_rows + sizes[event_id] <= cap * rows:
            sealed.add(event_id)
            sealed_rows += sizes[event_id]
    moved = None
    if not sealed and len(sizes) >= 2:
        smallest = min(
            sizes, key=lambda event_id: (sizes[event_id], event_number(event_id))
        )
        sealed.add(smallest)
        sealed_rows = sizes[smallest]
        moved = "smallest_to_sealed"
    return GroupDraw(
        group, frozenset(sealed), frozenset(sizes) - sealed, rows, sealed_rows, moved
    )


def draw_set(
    set_name: str, events: Mapping[str, tuple[int, bool]], *, seed: int = SPLIT_SEED
) -> dict[str, GroupDraw]:
    """Draw a set, given each event's rows and whether it is deep. The deep and other
    groups each walk with the seed and the set's SHARES, and an empty group is left
    out, so A-neg, which states no class, draws other alone. The split passes no seed.

    Raises TooFewEvents when the set has fewer than 2 events.
    """
    if len(events) < 2:
        raise TooFewEvents(set_name)
    target, cap = SHARES[set_name]
    groups: dict[str, dict[str, int]] = {"deep": {}, "other": {}}
    for event_id, (rows, deep) in events.items():
        groups["deep" if deep else "other"][event_id] = rows
    return {
        group: draw_group(sizes, group=group, target=target, cap=cap, seed=seed)
        for group, sizes in groups.items()
        if sizes
    }
