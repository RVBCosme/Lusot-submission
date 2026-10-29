"""Rules §3 and §9: why a photo is excluded before scoring (C404).

Exclusion reads the manifest's facts and the alerts' labels, never a result, so
Lusot's output can't exclude a photo (rules §9).
"""

from __future__ import annotations

from collections.abc import Sequence

from scoring.labels import ClassLabel, LevelLabel
from scoring.rows import Facts
from scoring.scale import level_index

_NOT_GOVERNMENT = "not posted by MMDA or a city government"
_LABEL_SHOWN = "depth or passability label visible in the image"
_NO_MATCH = "no matching alert"
_UNMAPPED = "unmapped label"
_CONFLICTING = "conflicting alerts"
_DUPLICATE = "duplicate or repost"
_OUTSIDE = "outside Metro Manila"
_UNDECODABLE = "the file can't be decoded"

# Rules §9's reasons, in its order and words.
REASONS: tuple[str, ...] = (
    _NOT_GOVERNMENT,
    _LABEL_SHOWN,
    _NO_MATCH,
    _UNMAPPED,
    _CONFLICTING,
    _DUPLICATE,
    _OUTSIDE,
    _UNDECODABLE,
)


def set_a_exclusion(
    facts: Facts, level: LevelLabel, cls: ClassLabel, others: Sequence[LevelLabel]
) -> str | None:
    """The first of REASONS that applies to a Set A photo, or None. `level` and `cls`
    are the main alert's labels and `others` the other matching alerts' level
    labels, each mapped by rules §2. Beside a mapped level, an unmapped `cls`
    excludes nothing: it leaves the photo out of passability only (MS6E-Q1, item 2)."""
    if facts.poster_kind not in ("mmda", "city"):
        return _NOT_GOVERNMENT
    if facts.label_in_image == "yes":
        return _LABEL_SHOWN
    if facts.match == "none" or level.kind == "status":
        return _NO_MATCH
    # A blank depth beside a blank or unmapped class gives no ground truth (MS6E-Q1,
    # item 14), and an unmapped other alert leaves a conflict impossible to rule
    # out (C404).
    if (
        level.kind == "unmapped"
        or (level.kind == "blank" and cls.kind in ("blank", "unmapped"))
        or any(other.kind == "unmapped" for other in others)
    ):
        return _UNMAPPED
    # Statuses and blanks give no level, so only levels can conflict (rules §3; C404).
    levels = [label.level for label in (level, *others) if label.kind == "level"]
    indexes = [level_index(name) for name in levels]
    if indexes and max(indexes) - min(indexes) > 1:
        return _CONFLICTING
    if facts.duplicate:
        return _DUPLICATE
    if not facts.metro_manila:
        return _OUTSIDE
    if not facts.decodes:
        return _UNDECODABLE
    return None


def a_neg_exclusion(facts: Facts) -> str | None:
    """An A-neg photo's reason, or None: only a duplicate or a file that can't be
    decoded is excluded (MS6E-Q1, item 6)."""
    if facts.duplicate:
        return _DUPLICATE
    if not facts.decodes:
        return _UNDECODABLE
    return None
