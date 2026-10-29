"""Step 4: the references in a photo (spec §3.2).

Before numbering (step 4.1; C69, C70), a wheel no rule could read loses its box, and
the caps keep a crowded street's labels few. A box cut there gets no number, so Muse
Spark never answers about it.

After numbering, `layout` names the kept boxes' links by box id. Muse Spark's answer
must pass the schema (step 4.3, C47). annotate's check_ids_per_item then drops the
entries with bad ids (step 4.4), and the gate decides whether the answer's top level
settles the outcome (step 4.5; C51, C52). If it doesn't, apply_drops keeps the
vehicles and people that may give readings (step 4.6, spec §3.3).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from lusot_analysis import rules
from lusot_analysis.annotate import NumberedBox
from lusot_analysis.meta_client import SamInstance, SamResult
from lusot_analysis.pipeline.segment import box_xyxy, link_wheels
from lusot_analysis.pipeline.types import ModelAnswerError, Outcome
from lusot_analysis.prompts import validator_class
from lusot_analysis.tuning import TUNING

# From the tuning module, checked on Manila photos and never swept (C310).
MIN_WHEEL_SIDE_PX = TUNING.min_wheel_side_px  # a wheel SAM box's longer side (C56, P2)
MAX_VEHICLES = TUNING.max_vehicles  # both caps are provisional (C70, P6)
MAX_PEOPLE = TUNING.max_people


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


@dataclass(frozen=True)
class Layout:
    """The numbered boxes, and Prepared's links named by box id, not position.

    - `wheel_vehicle`: each numbered wheel's vehicle.
    - `small_wheel_vehicles`: the vehicles that lost a linked wheel to the 40 px rule.
      Such a wheel still counts as visible (C53, C69).
    """

    boxes: tuple[NumberedBox, ...]
    wheel_vehicle: Mapping[int, int]
    small_wheel_vehicles: frozenset[int]


def layout(prepared: Prepared, boxes: Sequence[NumberedBox]) -> Layout:
    """Prepared's links by box id. `boxes` is number_boxes(prepared.sam).

    number_boxes keeps each kind in SAM's order, so the k-th vehicle box is the k-th
    kept vehicle, and likewise for wheels and people.
    """
    vehicles = [box.id for box in boxes if box.kind == "vehicle"]
    wheels = [box.id for box in boxes if box.kind == "wheel"]
    return Layout(
        boxes=tuple(boxes),
        wheel_vehicle={
            wheel: vehicles[k]
            for wheel, k in zip(wheels, prepared.wheel_vehicle, strict=True)
        },
        small_wheel_vehicles=frozenset(
            vehicles[k] for k in prepared.small_wheel_vehicles
        ),
    )


def instances_by_id(prepared: Prepared, layout: Layout) -> dict[int, SamInstance]:
    """Each numbered box's SAM instance, by box id.

    number_boxes keeps each kind in SAM's order, so the k-th numbered box of a kind is
    the k-th kept instance of its phrase, which the kind names.
    """
    instances: dict[int, SamInstance] = {}
    for kind in ("vehicle", "wheel", "person"):
        ids = [box.id for box in layout.boxes if box.kind == kind]
        instances |= dict(zip(ids, _instances(prepared.sam, kind), strict=True))
    return instances


def validate_answer(data: object, schema: dict) -> None:
    """Raise ModelAnswerError unless `data` is an object that passes `schema` (C47).

    The validator is load_prompt's. The error never quotes the answer, whose text can
    hold Muse Spark's reason (C62).
    """
    validator = validator_class(schema)(schema)
    if not isinstance(data, dict) or not validator.is_valid(data):
        raise ModelAnswerError("Muse Spark's answer fails the schema")


def water_found(result: SamResult) -> bool:
    """True when any instance's mask has a pixel. No instance means no water (C51)."""
    return any(inst.mask.any() for inst in result.instances)


def gate(answer: dict, *, has_water: bool) -> Outcome | None:
    """The outcome the answer's top level settles, or None to go on (step 4.5).

    `answer` has passed the schema and check_ids_per_item. In this order:
    1. `photo_usable` no: refused, photo_unusable.
    2. `standing_water` unsure: refused, water_unsure.
    3. `standing_water` no: no flood seen, unless an answered item puts the water
       above its lowest mark, which contradicts the no: refused, water_unsure (C52).
       Every answered item counts, even one a later drop removes. Water in SAM's mask
       never overrides a clear no (C51).
    4. `standing_water` yes, with no water in SAM's mask: refused, no_water_found
       (C51, Rene's Q1).
    """
    if answer["photo_usable"] == "no":
        return Outcome.refused("photo_unusable")
    standing = answer["standing_water"]
    if standing == "unsure":
        return Outcome.refused("water_unsure")
    if standing == "no":
        if _water_above_lowest_mark(answer):
            return Outcome.refused("water_unsure")
        return Outcome.no_flood()
    if not has_water:  # standing_water is yes
        return Outcome.refused("no_water_found")
    return None


@dataclass(frozen=True)
class KeptVehicle:
    """A vehicle the drops keep, with what step 5 reads from it.

    - `wheels`: (wheel id, waterline) for each answered wheel linked to it, in id
      order.
    - `wheels_hidden`: whether its body may give a reading (C53). Every numbered wheel
      linked to it is answered as hidden, and it lost no linked wheel to the 40 px
      rule (C69). An unanswered wheel counts as visible (C76). It holds when no wheel
      is linked.
    - `vehicle_type`: Muse Spark's type. Only rules.READING_TYPES read Table 8's
      wheel rows and the body (C45, C53); a type kept for geometry reads from geometry
      alone (C318).
    """

    id: int
    body_waterline: str
    wheels: tuple[tuple[int, str], ...]
    wheels_hidden: bool
    vehicle_type: str = "sedan_hatch"


@dataclass(frozen=True)
class KeptPerson:
    """An adult the drops keep. The waterline can be not_visible."""

    id: int
    waterline: str


@dataclass(frozen=True)
class Kept:
    """The vehicles and people left after the drops, each in id order (step 4.6).

    `causes` names each dropped box's first cause by box id, for the evidence record
    (C328). Kept compares without it.
    """

    vehicles: tuple[KeptVehicle, ...]
    people: tuple[KeptPerson, ...]
    causes: Mapping[int, str] = field(default_factory=dict, compare=False)


def apply_drops(
    answer: dict, layout: Layout, *, geometry_types: frozenset[str] = frozenset()
) -> tuple[Kept, Counter[str]]:
    """The vehicles and people that may give readings, and the drops (step 4.6).

    `answer` has passed check_ids_per_item, so each entry names a numbered box of its
    own kind, once. A numbered box with no entry is unanswered (C76). Each drop counts
    once, under the first cause that applies:
    - A vehicle: `vehicle_unanswered`; `vehicle_moving` when `moving` is yes or unsure
      (W1); `vehicle_type` when its type is in neither rules.READING_TYPES (C45) nor
      `geometry_types`, which the pipeline sets to rules.GEOMETRY_ONLY_TYPES when
      geometry is on (C318). Each of its numbered wheels goes with it, as
      `wheel_vehicle_dropped`.
    - A numbered wheel of a kept vehicle: `wheel_unanswered`.
    - A person: `person_unanswered`; `person_not_adult` when `adult` is no or unsure;
      `person_wading` when `standing_still` is no or unsure while someone answered as
      an adult standing still is in the photo, whatever that person's waterline (C57,
      Rene's Q3). No one else blocks: not an unanswered person, nor one answered
      `adult: unsure` (C76).

    `wake_visible` changes nothing (C63). Kept's `causes` holds each drop by box id,
    and the Counter counts them.
    """
    vehicles, wheels, people = (
        {item["id"]: item for item in answer[name]}
        for name in ("vehicles", "wheels", "people")
    )
    read_types = rules.READING_TYPES | geometry_types
    causes: dict[int, str] = {}  # box ids are unique, so each box has one cause
    kept_vehicles = []
    for vehicle_id in [box.id for box in layout.boxes if box.kind == "vehicle"]:
        entry = vehicles.get(vehicle_id)
        # Its numbered wheels. wheel_vehicle is a mapping, so they're sorted by id.
        own = sorted(w for w, v in layout.wheel_vehicle.items() if v == vehicle_id)
        if entry is None:
            cause = "vehicle_unanswered"
        elif entry["moving"] != "no":  # yes or unsure (W1)
            cause = "vehicle_moving"
        elif entry["type"] not in read_types:  # C45, narrowed by C318
            cause = "vehicle_type"
        else:
            cause = None
        if cause is not None:
            causes[vehicle_id] = cause
            causes |= dict.fromkeys(own, "wheel_vehicle_dropped")
            continue
        answered = tuple((w, wheels[w]["waterline"]) for w in own if w in wheels)
        unanswered = [w for w in own if w not in wheels]
        causes |= dict.fromkeys(unanswered, "wheel_unanswered")
        hidden = vehicle_id not in layout.small_wheel_vehicles and all(
            w in wheels and wheels[w]["waterline"] in rules.HIDDEN_WHEEL for w in own
        )
        kept_vehicles.append(
            KeptVehicle(
                vehicle_id, entry["body_waterline"], answered, hidden, entry["type"]
            )
        )

    blocked = any(
        p["adult"] == "yes" and p["standing_still"] == "yes" for p in people.values()
    )
    kept_people = []
    for person_id in [box.id for box in layout.boxes if box.kind == "person"]:
        entry = people.get(person_id)
        if entry is None:
            causes[person_id] = "person_unanswered"
        elif entry["adult"] != "yes":  # no or unsure
            causes[person_id] = "person_not_adult"
        elif blocked and entry["standing_still"] != "yes":  # wading: no or unsure
            causes[person_id] = "person_wading"
        else:
            kept_people.append(KeptPerson(person_id, entry["waterline"]))
    kept = Kept(tuple(kept_vehicles), tuple(kept_people), causes)
    return kept, Counter(kept.causes.values())


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


def _water_above_lowest_mark(answer: dict) -> bool:
    """True when an answered item puts the water above its lowest mark (C52).

    That is a wheel above tire_only, a person above ankle, or a body above
    below_bumper. not_visible marks nothing.
    """
    marks = rules.ABOVE_LOWEST_MARK
    return (
        any(item["waterline"] in marks["wheel"] for item in answer["wheels"])
        or any(item["waterline"] in marks["person"] for item in answer["people"])
        or any(item["body_waterline"] in marks["body"] for item in answer["vehicles"])
    )
