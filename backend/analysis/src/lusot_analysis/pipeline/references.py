"""Step 4: the references in a photo (spec §3.2).

Before numbering (step 4.1; C69, C70), a wheel no rule could read loses its box, and
the caps keep a crowded street's labels few. A box cut there gets no number, so Muse
Spark never answers about it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from lusot_analysis.meta_client import SamInstance, SamResult
from lusot_analysis.pipeline.segment import box_xyxy, link_wheels

MIN_WHEEL_SIDE_PX = 40  # on the longer side of a wheel's SAM box (C56, P2)
MAX_VEHICLES = 6  # both caps are provisional (C70, P6)
MAX_PEOPLE = 6


@dataclass(frozen=True)
class Prepared:
    """SAM's results cut to the boxes that get numbers, and what the cuts were.

    - `sam`: `vehicle`, `wheel` and `person` hold only their kept instances, in SAM's
      order. Every other phrase is SAM's result, unchanged.
    - `wheel_vehicle`: for each kept wheel, its vehicle's position among the kept
      vehicles.
    - `small_wheel_vehicles`: the positions of kept vehicles that lost a linked wheel
      to the 40 px rule. Such a wheel still counts as visible (C53, C69).
    - `drops`: each cut, counted by cause.
    """

    sam: dict[str, SamResult]
    wheel_vehicle: tuple[int, ...]
    small_wheel_vehicles: frozenset[int]
    drops: Counter[str]


def prepare_boxes(sam: Mapping[str, SamResult]) -> Prepared:
    """Cut SAM's results to the boxes Muse Spark gets numbers for.

    A phrase missing from `sam` has no instances. The steps run in this order, which
    decides each drop's cause:
    1. Each wheel links among all of SAM's vehicles (C55). An unlinked wheel is
       dropped as `wheel_unlinked`.
    2. A linked wheel whose box's longer side is under 40 px is dropped as
       `wheel_small`, and its vehicle is marked (C56, C69).
    3. The 6 vehicles with the largest boxes are kept; on equal areas, the earlier in
       SAM's order. The rest are dropped as `vehicle_cap`, and their wheels as
       `wheel_cap` (C70).
    4. The 6 largest people are kept the same way. The rest are `person_cap`.
    """
    vehicles, wheels, people = (
        _instances(sam, phrase) for phrase in ("vehicle", "wheel", "person")
    )
    causes: list[str] = []
    linked: list[tuple[SamInstance, int]] = []  # each wheel left, and its vehicle
    marked: set[int] = set()  # vehicles that lost a wheel to the 40 px rule
    for wheel, vehicle in zip(wheels, link_wheels(vehicles, wheels), strict=True):
        if vehicle is None:
            causes.append("wheel_unlinked")
        elif _longer_side(wheel) < MIN_WHEEL_SIDE_PX:
            causes.append("wheel_small")
            marked.add(vehicle)
        else:
            linked.append((wheel, vehicle))

    kept_vehicles = _largest(vehicles, MAX_VEHICLES)
    causes += ["vehicle_cap"] * (len(vehicles) - len(kept_vehicles))
    position = {index: k for k, index in enumerate(kept_vehicles)}
    kept_wheels = [(wheel, position[v]) for wheel, v in linked if v in position]
    causes += ["wheel_cap"] * (len(linked) - len(kept_wheels))
    kept_people = _largest(people, MAX_PEOPLE)
    causes += ["person_cap"] * (len(people) - len(kept_people))

    kept = {
        "vehicle": [vehicles[index] for index in kept_vehicles],
        "wheel": [wheel for wheel, _ in kept_wheels],
        "person": [people[index] for index in kept_people],
    }
    results = dict(sam)
    for phrase, instances in kept.items():
        if phrase in results:  # a phrase missing from `sam` stays missing
            results[phrase] = replace(results[phrase], instances=instances)
    return Prepared(
        sam=results,
        wheel_vehicle=tuple(k for _, k in kept_wheels),
        small_wheel_vehicles=frozenset(position[v] for v in marked if v in position),
        drops=Counter(causes),
    )


def _instances(sam: Mapping[str, SamResult], phrase: str) -> list[SamInstance]:
    result = sam.get(phrase)
    return [] if result is None else result.instances


def _longer_side(inst: SamInstance) -> float:
    x0, y0, x1, y1 = box_xyxy(inst)
    return max(x1 - x0, y1 - y0)


def _area(inst: SamInstance) -> float:
    x0, y0, x1, y1 = box_xyxy(inst)
    return (x1 - x0) * (y1 - y0)


def _largest(instances: Sequence[SamInstance], limit: int) -> list[int]:
    """The indices of the `limit` largest boxes, in SAM's order.

    On equal areas the earlier instance wins, so a replay keeps the same boxes (B3).
    """
    by_size = sorted(range(len(instances)), key=lambda i: (-_area(instances[i]), i))
    return sorted(by_size[:limit])
