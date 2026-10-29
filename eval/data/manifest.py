"""Set A's and A-neg's manifest and M8 rows, and the counts per fact value that the split
prints and records (C207, C216, spec §5.9).

The manifest keeps the raw labels and §9's facts in MS6's names, with the same columns
on both sides (C207). The harness maps the labels and decides every exclusion, so no
label is checked here.

The audit and the other standard-library tools load this module through record_io, and
photos would bring in numpy and OpenCV. So setlogs' and photos' names are imported for
annotations only.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from typing import TYPE_CHECKING

import formats

if TYPE_CHECKING:
    from photos import PhotoFacts
    from setlogs import Photo

# The facts counted per value, in the split's output and its record. A-neg's surface
# joins them on rows that carry one. Cities, spots, labels and notes stay out (§5.9).
_FACTS = (
    "poster_kind",
    "match",
    "metro_manila",
    "label_in_image",
    "reference_visible",
    "duplicate",
    "decodes",
)


def manifest_row(
    photo: Photo, facts: PhotoFacts, *, event_id: str, split: str, duplicate_of: str
) -> dict[str, str]:
    """The photo's manifest row, a cell for each of formats.MANIFEST_COLUMNS.

    duplicate_of is the duplicate group's lowest id, or blank for a photo in no group.
    Every photo of a group but that lowest one is a duplicate (§5.5). A photo that
    doesn't decode has blank sizes, and its blank dHash stays blank.
    """
    return {
        "photo_id": photo.photo_id,
        "set": photo.set,
        "split": split,
        "event_id": event_id,
        "event_date": photo.event_date,
        "city": photo.city,
        "metro_manila": photo.metro_manila,
        "spot_key": photo.spot_key,
        "same_spot_as": ";".join(sorted(photo.same_spot_as)),
        "poster_kind": photo.poster_kind,
        "match": photo.match,
        "level_label_raw": photo.level_label_raw,
        "passability_raw": photo.passability_raw,
        "other_alerts_raw": photo.other_alerts_raw,
        "label_in_image": photo.label_in_image,
        "reference_visible": photo.reference_visible,
        "faces_or_plates": photo.faces_or_plates,
        "surface": photo.surface,
        "duplicate": "no" if duplicate_of in ("", photo.photo_id) else "yes",
        "duplicate_of": duplicate_of,
        "decodes": "yes" if facts.decodes else "no",
        "photo_file": photo.photo_file,
        "photo_sha256": facts.sha256,
        "photo_dhash": facts.dhash,
        "width": "" if facts.width is None else str(facts.width),
        "height": "" if facts.height is None else str(facts.height),
        "notes": photo.notes,
    }


def m8_rows(
    rows: Sequence[Mapping[str, str]], photo_ids: Collection[str]
) -> list[dict[str, str]]:
    """The M8 rows of the photos given, in the order given, each cut to
    formats.M8_COLUMNS, so a column Rene's export adds never reaches a side (C208)."""
    wanted = set(photo_ids)
    return [
        {column: row[column] for column in formats.M8_COLUMNS}
        for row in rows
        if row["photo_id"] in wanted
    ]


def counts(rows: Sequence[Mapping[str, str]]) -> dict:
    """{"rows", "events", "facts": {fact: {value: count}}} over one set's manifest rows
    on one side. surface is counted only when a row carries one, which only A-neg's
    rows do, so Set A's facts have no surface key."""
    facts = _FACTS + (("surface",) if any(row["surface"] for row in rows) else ())
    return {
        "rows": len(rows),
        "events": len({row["event_id"] for row in rows}),
        "facts": {fact: dict(Counter(row[fact] for row in rows)) for fact in facts},
    }
