"""Step 5: each kept vehicle and adult gives at most one deciding reading (spec §3.3).

A vehicle reads its wheels and, when its wheels are hidden, C53's rows for its body.
A wheel's reading is G4's: the deeper of its Table 8 row and its geometry reading, and
a type kept for geometry has its geometry reading alone (C318). The deepest of these
speaks for the vehicle (C43). An adult reads Table 8's people rows (D13). A reading
step 3 dropped never decides, but it stays, so that combine can refuse with it (C317).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from lusot_analysis import rules
from lusot_analysis.pipeline.combine import tie_order
from lusot_analysis.pipeline.geometry import GeometryReading, keep_reading
from lusot_analysis.pipeline.references import Kept
from lusot_analysis.pipeline.types import Reference


def measure(
    kept: Kept,
    *,
    step3_drops: Mapping[int, str] | None = None,
    geometry: Mapping[int, GeometryReading] | None = None,
) -> tuple[list[Reference], Counter[str]]:
    """The references of the kept vehicles and adults, and the drops.

    `step3_drops` maps a box id to its step 3 cause: a wheel's, a person's, or a
    vehicle's for its body. `geometry` maps a wheel id to its geometry reading. With
    neither, this is MS3a's step 5.

    The vehicles' references come first, then the adults', each in id order as `kept`
    holds them. A vehicle gives the reference that speaks for it, then those step 3
    dropped. It is read in this order, and a drop counts under its first cause:
    1. A `wheel_covered` wheel beside a body waterline at `door_sill` or lower drops
       it as `vehicle_body_below_covered_wheel` (C53).
    2. Each wheel's reading. Its landmark is its Table 8 row for rules.READING_TYPES,
       and none for a type kept for geometry (C318). A wheel step 3 dropped gives its
       landmark reading, if it has one, as a reference that doesn't decide (C317).
       Otherwise keep_reading gives G4's reading, or drops the wheel as
       `wheel_methods_disagree`.
    3. Deciding wheel readings that fail C54's test drop it as
       `vehicle_wheels_disagree`: an exact one sits more than one level below the
       deepest (C43).
    4. Its candidates are its deciding wheel readings and, for rules.READING_TYPES
       whose wheels are hidden, its body's (C53). A body step 3 dropped doesn't
       decide. With no candidate, it counts as `vehicle_no_reading`.
    5. Otherwise the deepest candidate speaks for it. A tie goes in C54's order: a
       floor first, then a wheel before the body, then the lowest box id (C78).

    Each box counts once, when its vehicle's fate is known. A vehicle dropped in 1 or
    3 gives no reference, not even one that can't decide, and takes each of its wheels
    with it as `wheel_vehicle_dropped`, whatever step 3 or G4 found for them (C317).
    Otherwise each wheel or body that step 3 or G4 dropped counts under its cause. A
    vehicle with no reading doesn't take its wheels, as they gave nothing.

    An adult whose waterline gives no reading counts as `person_no_reading`. One that
    step 3 dropped gives a reference that doesn't decide, and counts under its cause.
    """
    step3_drops = step3_drops or {}
    geometry = geometry or {}
    references: list[Reference] = []
    causes: list[str] = []
    for vehicle in kept.vehicles:
        reads_rows = vehicle.vehicle_type in rules.READING_TYPES  # C45, C318
        wheels: list[Reference] = []  # the wheel readings that may decide
        held: list[Reference] = []  # step 3's drops, which never decide (C317)
        found: list[str] = []  # the causes that count only if the vehicle stays
        for wheel_id, line in vehicle.wheels:
            landmark = rules.WHEEL_ROWS[line] if reads_rows else None
            if wheel_id in step3_drops:
                found.append(step3_drops[wheel_id])
                if landmark is not None:
                    held.append(
                        Reference("wheel", wheel_id, line, landmark, decides=False)
                    )
                continue
            kept_reading = keep_reading(landmark, geometry.get(wheel_id))  # G4
            if isinstance(kept_reading, str):  # wheel_methods_disagree
                found.append(kept_reading)
            elif kept_reading is not None:
                wheels.append(
                    Reference(
                        "wheel",
                        wheel_id,
                        line,
                        kept_reading.reading,
                        level_from=kept_reading.level_from,
                        depth_in=kept_reading.depth_in,
                    )
                )
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
        candidates = wheels
        body = rules.BODY_ROWS[vehicle.body_waterline]
        if reads_rows and vehicle.wheels_hidden and body is not None:  # C53
            if vehicle.id in step3_drops:
                found.append(step3_drops[vehicle.id])
                held.append(
                    Reference(
                        "body", vehicle.id, vehicle.body_waterline, body, decides=False
                    )
                )
            else:
                candidates = [
                    *wheels,
                    Reference("body", vehicle.id, vehicle.body_waterline, body),
                ]
        causes += found
        if candidates:
            # The deepest speaks for the vehicle (C43). A tie goes in C54's order (C78).
            level = max((r.reading.level for r in candidates), key=rules.level_index)
            deepest = [r for r in candidates if r.reading.level == level]
            references.append(min(deepest, key=tie_order))
        else:
            causes.append("vehicle_no_reading")
        references += held
    for person in kept.people:
        reading = rules.PEOPLE_ROWS[person.waterline]
        if reading is None:
            causes.append("person_no_reading")
        elif person.id in step3_drops:
            causes.append(step3_drops[person.id])
            references.append(
                Reference("person", person.id, person.waterline, reading, decides=False)
            )
        else:
            references.append(Reference("person", person.id, person.waterline, reading))
    return references, Counter(causes)
