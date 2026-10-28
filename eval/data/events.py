"""Flood events for Set A and A-neg (C203), and near-identical photos (§5.5).

The split keeps each event whole on one side, so an event that is too big costs only
balance, while one that is too small can leak a flood across the two sides (W18). So
rows join on any shared name, whatever their city, and an empty key joins the date's
other empty keys.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import places

NEAR_BITS = 6
_DHASH = re.compile(r"[0-9a-f]{16}")
_EVENT_ID = re.compile(r"E([0-9]+)")


@dataclass(frozen=True)
class EventInput:
    """One photo: its id, its Manila date (YYYY-MM-DD), its spot key and the ids it
    links in same_spot_as."""

    photo_id: str
    date: str
    key: str
    links: frozenset[str]


def group_events(
    rows: Sequence[EventInput], joined: Iterable[tuple[str, str]] = ()
) -> dict[str, str]:
    """Each row's event id, E01, E02… with at least two digits, numbered by each
    event's lowest photo id. The rows are one set's.

    Two rows join on the same date when they have the same key, an empty one included,
    or share a name. They also join when either links the other, and as a joined pair.
    A link to an id that isn't a row is left out, since the intake reports it
    (bad_link). A joined pair naming an id that isn't a row raises KeyError.
    """
    parent = {row.photo_id: row.photo_id for row in rows}

    def find(photo_id: str) -> str:
        while parent[photo_id] != photo_id:
            parent[photo_id] = parent[parent[photo_id]]
            photo_id = parent[photo_id]
        return photo_id

    def join(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    first: dict[tuple[str, str, str], str] = {}  # the first row with a date and mark
    for row in rows:
        marks = [("key", row.key)]
        marks += [("name", name) for name in places.names_of(row.key)]
        for kind, value in marks:
            join(first.setdefault((row.date, kind, value), row.photo_id), row.photo_id)
        for link in row.links:
            if link in parent:
                join(link, row.photo_id)
    for a, b in joined:
        join(a, b)
    # The ids in order, so each event first shows up at its lowest id.
    members: dict[str, list[str]] = {}
    for photo_id in sorted(parent):
        members.setdefault(find(photo_id), []).append(photo_id)
    return {
        photo_id: f"E{number:02d}"
        for number, ids in enumerate(members.values(), start=1)
        for photo_id in ids
    }


def event_number(event_id: str) -> int:
    """The number in an event id, so that E100 sorts after E99."""
    match = _EVENT_ID.fullmatch(event_id)
    if match is None:
        raise ValueError("not an event id")
    return int(match.group(1))


def near(a: str, b: str) -> bool:
    """True when two dHashes, each 16 lowercase hex digits, differ in at most NEAR_BITS
    of their 64 bits (§5.5).

    A blank one, from a photo that doesn't decode, is never near. Any other text raises
    ValueError.
    """
    if not a or not b:
        return False
    if _DHASH.fullmatch(a) is None or _DHASH.fullmatch(b) is None:
        raise ValueError("not a dHash of 16 lowercase hex digits")
    return (int(a, 16) ^ int(b, 16)).bit_count() <= NEAR_BITS
