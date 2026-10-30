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
from dataclasses import dataclass

from lusot_analysis import rules
from lusot_analysis.pipeline.combine import tie_order
from lusot_analysis.pipeline.geometry import GeometryReading, KeptReading, keep_reading
from lusot_analysis.pipeline.references import Kept
from lusot_analysis.pipeline.types import Reference


@dataclass(frozen=True)
class Measured:
    """Step 5's result, with what each box gave, for the evidence record (C328).

    - `references`, `drops`: measure's pair.
    - `causes`: each dropped box's first cause, by box id. Every drop counts in
      `drops`, so a vehicle whose body step 3 dropped, and which has no reading left,
      counts twice there but keeps its step 3 cause here.
    - `readings`: the reading each box gives, by box id, for every box of a vehicle
      that isn't dropped and every adult with a reading, deciding or not. A box with
      two readings gives the one that can decide (R147): a wheel of a type kept for
      geometry gives its geometry reading over its floor (R143, M5).
    """

    references: list[Reference]
    drops: Counter[str]
    causes: dict[int, str]
    readings: dict[int, KeptReading]


def measure(
    kept: Kept,
    *,
    step3_drops: Mapping[int, str] | None = None,
    geometry: Mapping[int, GeometryReading] | None = None,
) -> tuple[list[Reference], Counter[str]]:
    """The references of the kept vehicles and adults, and the drops.

    These are measure_boxes' `references` and `drops`, as MS3a's step 5 returned
    them.
    """
    m = measure_boxes(kept, step3_drops=step3_drops, geometry=geometry)
    return m.references, m.drops


def measure_boxes(
    kept: Kept,
    *,
    step3_drops: Mapping[int, str] | None = None,
    geometry: Mapping[int, GeometryReading] | None = None,
) -> Measured:
    """The references of the kept vehicles and adults, the drops, and each box's.

    `step3_drops` maps a box id to its step 3 cause: a wheel's, a person's, or a
    vehicle's for its body. `geometry` maps a wheel id to its geometry reading. With
    neither, this is MS3a's step 5.

    The vehicles' references come first, then the adults', each in id order as `kept`
    holds them. A vehicle gives the reference that speaks for it, then those step 3
    dropped. It is read in this order, and a drop counts under its first cause:
    1. For rules.READING_TYPES, a `wheel_covered` wheel beside a body waterline at
       `door_sill` or lower drops it as `vehicle_body_below_covered_wheel` (C53). Like
       the body reading, this rule is for sedans and SUVs only (R142).
    2. Each wheel's reading. Its landmark is its Table 8 row for rules.READING_TYPES,
       and none for a type kept for geometry (C318). A wheel step 3 dropped gives its
       landmark reading, if it has one, as a reference that doesn't decide (C317).
       Otherwise keep_reading gives G4's reading, or drops the wheel as
       `wheel_methods_disagree`. Each wheel of a type kept for geometry whose answer
       has a Table 8 row also gives that sedan row's level as a floor, as a reference
       that doesn't decide: water at a larger wheel's mark is at least as deep (M5,
       Rene, Oct 30). A covered wheel's tire floor is one case (R143). This floor
       holds whether or not step 3 dropped the wheel (C317), and not_visible gives
       none.
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

    Measured's `causes` and `readings` follow the same counting: a vehicle dropped in
    1 or 3 gives no reading, and its boxes' causes are its own and
    `wheel_vehicle_dropped`.
    """
    step3_drops = step3_drops or {}
    geometry = geometry or {}
    references: list[Reference] = []
    counted: list[tuple[int, str]] = []  # (box id, cause) for each drop that counts
    readings: dict[int, KeptReading] = {}
    for vehicle in kept.vehicles:
        reads_rows = vehicle.vehicle_type in rules.READING_TYPES  # C45, C318
        wheels: list[Reference] = []  # the wheel readings that may decide
        held: list[Reference] = []  # never decide: step 3's drops, M5's floors (C317)
        # The causes and readings that count only if the vehicle stays.
        found: list[tuple[int, str]] = []
        given: dict[int, KeptReading] = {}
        for wheel_id, line in vehicle.wheels:
            row = rules.WHEEL_ROWS[line]
            landmark = row if reads_rows else None
            if not reads_rows and row is not None:
                # The sedan row bounds any larger wheel from below, so it is held as a
                # floor to refuse a shallower exact result, never to decide (M5, Rene,
                # Oct 30). A covered wheel's tire floor is one case (R143). It holds
                # whether or not step 3 dropped the wheel (C317).
                floor = rules.Reading(row.level, floor=True)
                held.append(Reference("wheel", wheel_id, line, floor, decides=False))
                given[wheel_id] = KeptReading(floor, "landmark", None)
            if wheel_id in step3_drops:
                found.append((wheel_id, step3_drops[wheel_id]))
                if landmark is not None:
                    held.append(
                        Reference("wheel", wheel_id, line, landmark, decides=False)
                    )
                    given[wheel_id] = KeptReading(landmark, "landmark", None)
                continue
            kept_reading = keep_reading(landmark, geometry.get(wheel_id))  # G4
            if isinstance(kept_reading, str):  # wheel_methods_disagree
                found.append((wheel_id, kept_reading))
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
                given[wheel_id] = kept_reading  # over M5's floor (R147)
        covered = any(line == "wheel_covered" for _, line in vehicle.wheels)
        low_body = vehicle.body_waterline in rules.BODY_AT_OR_BELOW_SILL
        if reads_rows and covered and low_body:  # C53, sedans and SUVs only (R142)
            cause = "vehicle_body_below_covered_wheel"
        elif rules.disagree(r.reading for r in wheels):
            cause = "vehicle_wheels_disagree"  # C43, with C54's test
        else:
            cause = None
        if cause is not None:
            counted.append((vehicle.id, cause))
            counted += [(w, "wheel_vehicle_dropped") for w, _ in vehicle.wheels]
            continue
        candidates = wheels
        body = rules.BODY_ROWS[vehicle.body_waterline]
        if reads_rows and vehicle.wheels_hidden and body is not None:  # C53
            given[vehicle.id] = KeptReading(body, "landmark", None)
            if vehicle.id in step3_drops:
                found.append((vehicle.id, step3_drops[vehicle.id]))
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
        counted += found
        readings |= given
        if candidates:
            # The deepest speaks for the vehicle (C43). A tie goes in C54's order (C78).
            level = max((r.reading.level for r in candidates), key=rules.level_index)
            deepest = [r for r in candidates if r.reading.level == level]
            references.append(min(deepest, key=tie_order))
        else:
            counted.append((vehicle.id, "vehicle_no_reading"))
        references += held
    for person in kept.people:
        reading = rules.PEOPLE_ROWS[person.waterline]
        if reading is None:
            counted.append((person.id, "person_no_reading"))
            continue
        readings[person.id] = KeptReading(reading, "landmark", None)
        if person.id in step3_drops:
            counted.append((person.id, step3_drops[person.id]))
            references.append(
                Reference("person", person.id, person.waterline, reading, decides=False)
            )
        else:
            references.append(Reference("person", person.id, person.waterline, reading))
    causes: dict[int, str] = {}
    for box_id, cause in counted:
        causes.setdefault(box_id, cause)  # the box's first cause
    return Measured(
        references, Counter(cause for _, cause in counted), causes, readings
    )
