"""Steps 6 and 7: one photo's references give one level, or a refusal (spec §3.3).

Step 7 (map) is the class lookup inside Outcome.level_result, so it has no code here.
"""

from __future__ import annotations

from collections.abc import Sequence

from lusot_analysis import rules
from lusot_analysis.pipeline.types import Outcome, Reference

_KIND_ORDER = {"wheel": 0, "body": 1, "person": 2}


def tie_order(reference: Reference) -> tuple[bool, int, int]:
    """C54's tie order, as a key for `min`.

    A floor comes first, then a wheel, a body and a person, then the lowest box id.
    One fixed order keeps replays repeatable (B3). Step 5 uses it inside one vehicle
    too (C78).
    """
    return (not reference.reading.floor, _KIND_ORDER[reference.kind], reference.box_id)


def combine(references: Sequence[Reference]) -> tuple[Outcome, Reference | None]:
    """The deepest believable level, and the reference that decides it (C49, C54).

    A refusal has no deciding reference.
    """
    if not references:
        return Outcome.refused("no_usable_reference"), None
    if rules.disagree(r.reading for r in references):
        return Outcome.refused("references_disagree"), None
    level = max((r.reading.level for r in references), key=rules.level_index)
    at_level = [r for r in references if r.reading.level == level]
    deciding = min(at_level, key=tie_order)
    level_is_floor = any(r.reading.floor for r in at_level)
    basis = {
        "vehicles": sum(r.kind in ("wheel", "body") for r in references),
        "people": sum(r.kind == "person" for r in references),
    }
    outcome = Outcome.level_result(level, deciding.landmark, level_is_floor, basis)
    return outcome, deciding
