"""Step 5: each kept vehicle and adult gives at most one landmark reading (spec §3.3).

A vehicle reads Table 8's wheel rows for its wheels and, when its wheels are hidden,
C53's rows for its body. The deepest of these speaks for it (C43). An adult reads
Table 8's people rows (D13).
"""

from __future__ import annotations

from collections import Counter

from lusot_analysis import rules
from lusot_analysis.pipeline.combine import tie_order
from lusot_analysis.pipeline.references import Kept
from lusot_analysis.pipeline.types import Reference


def measure(kept: Kept) -> tuple[list[Reference], Counter[str]]:
    """One reference per kept vehicle and adult with a reading, and the drops.

    The vehicles' references come first, then the adults', each in id order as `kept`
    holds them. A vehicle is read in this order, and a drop counts under its first
    cause:
    1. A `wheel_covered` wheel beside a body waterline at `door_sill` or lower drops
       it as `vehicle_body_below_covered_wheel` (C53).
    2. Wheel readings that fail C54's test drop it as `vehicle_wheels_disagree`: an
       exact one sits more than one level below the deepest (C43).
    3. Its candidates are its wheel readings and, when its wheels are hidden, its
       body's (C53). With none, it counts as `vehicle_no_reading`.
    4. Otherwise the deepest candidate speaks for it. A tie goes in C54's order: a
       floor first, then a wheel before the body, then the lowest box id (C78).

    A vehicle dropped in 1 or 2 takes each of its wheels with it, as
    `wheel_vehicle_dropped`. One with no reading doesn't, as its wheels gave nothing.
    An adult whose waterline gives no reading counts as `person_no_reading`.
    """
    references: list[Reference] = []
    causes: list[str] = []
    for vehicle in kept.vehicles:
        wheels = [
            Reference("wheel", wheel_id, line, rules.WHEEL_ROWS[line])
            for wheel_id, line in vehicle.wheels
            if rules.WHEEL_ROWS[line] is not None
        ]
        covered = any(line == "wheel_covered" for _, line in vehicle.wheels)
        if covered and vehicle.body_waterline in rules.BODY_AT_OR_BELOW_SILL:
            cause = "vehicle_body_below_covered_wheel"  # C53
        elif rules.disagree(r.reading for r in wheels):
            cause = "vehicle_wheels_disagree"  # C43, with C54's test
        else:
            cause = None
        if cause is not None:
            causes += [cause] + ["wheel_vehicle_dropped"] * len(vehicle.wheels)
            continue
        body = rules.BODY_ROWS[vehicle.body_waterline]
        if vehicle.wheels_hidden and body is not None:  # C53
            candidates = [
                *wheels,
                Reference("body", vehicle.id, vehicle.body_waterline, body),
            ]
        else:
            candidates = wheels
        if not candidates:
            causes.append("vehicle_no_reading")
            continue
        # The deepest speaks for the vehicle (C43). A tie goes in C54's order (C78).
        level = max((r.reading.level for r in candidates), key=rules.level_index)
        deepest = [r for r in candidates if r.reading.level == level]
        references.append(min(deepest, key=tie_order))
    for person in kept.people:
        reading = rules.PEOPLE_ROWS[person.waterline]
        if reading is None:
            causes.append("person_no_reading")
        else:
            references.append(Reference("person", person.id, person.waterline, reading))
    return references, Counter(causes)
