"""Load a run's results through the row contract (spec §4.3; C402, C403, C420).

Every field is checked against its own list, so a committed row can't hold free text:
not Muse Spark's reason, a post link, a spot name, a city or a time. A RowError names
the file, the line and the rule broken, never the value, since sealed rows pass
through here too.
"""

from __future__ import annotations

import datetime
import json
import re
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TypeVar

from scoring import RULES_VERSION
from scoring.labels import label_words_ok
from scoring.paths import refuse_sealed
from scoring.scale import CLASS_NAMES, CLASSES, LEVELS

CONFIGS = ("landmark", "geometry", "geometry_no_self_check")
# A development run's event-replay result is <configuration>_replay (C425).
REPLAY_SUFFIX = "_replay"
SET_B_VARIANTS = (
    "geometry",
    "geometry_uncalibrated",
    "known_waterline",
    "known_waterline_uncalibrated",
    "geometry_no_self_check",
)

# Schema v1's categories (backend/analysis/prompts/muse_spark_photo_v1.schema.json).
VEHICLE_TYPES = frozenset(
    {
        "sedan_hatch",
        "suv_mpv",
        "pickup",
        "van",
        "jeepney",
        "tricycle",
        "motorcycle",
        "bus_truck",
        "unknown",
    }
)
WHEEL_WATERLINES = frozenset(
    {
        "tire_only",
        "rim_quarter",
        "hub",
        "rim_three_quarters",
        "rim_top",
        "wheel_covered",
        "not_visible",
    }
)
BODY_WATERLINES = frozenset(
    {"below_bumper", "bumper", "door_sill", "mid_door", "window", "not_visible"}
)
PERSON_WATERLINES = frozenset(
    {
        "ankle",
        "mid_shin",
        "knee",
        "mid_thigh",
        "waist",
        "chest",
        "above_chest",
        "not_visible",
    }
)
YES_NO_UNSURE = frozenset({"yes", "no", "unsure"})
YES_NO = frozenset({"yes", "no"})  # photo_usable's values


@dataclass(frozen=True)
class Result:
    """One configuration's result for a photo. `reason` is a refusal's or failure's,
    and `landmark` a level's, for review.csv (C426)."""

    status: str
    reason: str | None
    no_flood_seen: bool
    level: str | None
    level_is_floor: bool
    passability: str | None
    landmark: str | None


@dataclass(frozen=True)
class Facts:
    """MS2's facts about a photo, which rules §9 reads."""

    poster_kind: str | None
    label_in_image: str | None
    match: str | None
    duplicate: bool
    metro_manila: bool
    decodes: bool


@dataclass(frozen=True)
class Reference:
    """An M8 label beside Muse Spark's reading of the same box. `kind` is wheel, body
    or person. The spark fields are None when the answer lacks the box."""

    box_id: int | None
    kind: str
    m8_landmark: str | None
    m8_type: str | None
    spark_landmark: str | None
    spark_type: str | None


@dataclass(frozen=True)
class PhotoRow:
    """A Set A or A-neg photo. An A-neg row has empty labels, no references and a
    surface. `answered` means Muse Spark's answer wasn't null."""

    photo_id: str
    event_id: str
    level_label_raw: str
    passability_raw: str
    other_alerts_raw: tuple[str, ...]
    facts: Facts
    quality: str | None
    subsets: tuple[str, ...]
    surface: str | None
    results: Mapping[str, Result]
    answered: bool
    references: tuple[Reference, ...]


@dataclass(frozen=True)
class Estimate:
    """One variant's estimate for a wheel: three numbers when measured, or else the
    check that failed."""

    measured: bool
    point: Decimal | None
    low: Decimal | None
    high: Decimal | None
    fail: str | None


@dataclass(frozen=True)
class WheelRow:
    """A Set B or Set D wheel in one crop."""

    crop_id: str
    wheel: int
    car_id: str
    vehicle_type: str
    tire_code: str
    true_depth_in: Decimal
    sam_water_found: bool | None
    bins: Mapping[str, str]
    estimates: Mapping[str, Estimate]


@dataclass(frozen=True)
class Run:
    """A loaded results folder. A set is None when its file is absent."""

    meta: Mapping[str, object]
    kind: str
    synthetic: bool
    self_check: bool
    geometry_dropped: bool
    rerun_reason: str | None
    service_retries: int
    baseline_level: str | None
    baseline_class: str | None
    set_a: tuple[PhotoRow, ...] | None
    a_neg: tuple[PhotoRow, ...] | None
    set_b: tuple[WheelRow, ...] | None
    set_d: tuple[WheelRow, ...] | None
    latency: tuple[tuple[str, Decimal], ...] | None


class RowError(ValueError):
    """A results file breaks the row contract. The message reads <file>:<line>: <what>,
    with line 0 for a file as a whole, and names the rule broken, never the value."""

    def __init__(self, file: str, line: int, what: str) -> None:
        super().__init__(f"{file}:{line}: {what}")


def load_run(folder: Path) -> Run:
    """Load a results folder through the row contract. Rows keep their file order.
    Raises SealedPath when any part of the folder's path is named sealed, before
    anything is read or listed (C411), and RowError at the first thing outside the
    contract."""
    refuse_sealed(folder)
    folder = Path(folder)
    meta = _read_manifest(folder)
    sealed = meta["kind"] == "sealed"
    self_check = meta["self_check"] == "on"
    dropped = meta.get("geometry_default") == "dropped"
    if sealed:
        for name in ("set_a.jsonl", "a_neg.jsonl"):
            if not (folder / name).is_file():
                raise RowError(name, 0, "a sealed run needs this file")
    configs = _configs(self_check, dropped)
    wheel_fields = _wheel_fields(self_check)
    return Run(
        meta=meta,
        kind=meta["kind"],
        synthetic=meta.get("synthetic", False),
        self_check=self_check,
        geometry_dropped=dropped,
        rerun_reason=meta.get("rerun_reason"),
        service_retries=meta.get("service_retries", 0),
        baseline_level=meta.get("baseline_level"),
        baseline_class=meta.get("baseline_class"),
        set_a=_photos(
            folder,
            "set_a.jsonl",
            _photo_fields(a_neg=False, configs=configs, replays=not sealed),
        ),
        a_neg=_photos(
            folder,
            "a_neg.jsonl",
            _photo_fields(a_neg=True, configs=configs, replays=not sealed),
        ),
        set_b=_wheels(folder, "set_b.jsonl", wheel_fields),
        set_d=_wheels(folder, "set_d.jsonl", wheel_fields),
        latency=_latency(folder),
    )


class _Bad(Exception):
    """A rule broken inside one line; the loader adds the file and the line number.
    It isn't a ValueError, so the JSON parser's own errors can't pass for it."""


_Check = Callable[[object, str], object]
_T = TypeVar("_T")

_ID = re.compile("[A-Z]{1,3}[0-9]{1,4}(?:-[0-9]{1,3}){0,2}")
_TOKEN = re.compile("[a-z][a-z0-9_]{0,31}")
_SHORT = re.compile("[A-Za-z0-9 ._:/,+()=-]{0,80}")
_DATE = re.compile("[0-9]{4}-[0-9]{2}-[0-9]{2}")
_COMMIT = re.compile("[0-9a-f]{40}")
_TIRE_CODE = re.compile("[0-9]{3}/[0-9]{2}R[0-9]{2}C?")


# The checks. Each takes a value and where it sits (`outcomes.landmark.basis`, say,
# or "" for a whole line), and returns the value checked.


def _at(where: str, key: str) -> str:
    return f"{where}.{key}" if where else key


def _keys(
    value: object, subject: str, fields: Collection[str], optional: Collection[str]
) -> dict:
    """An object holding only `fields`, and all of them but those in `optional`."""
    if not isinstance(value, dict):
        raise _Bad(f"{subject} must be an object")
    if any(key not in fields for key in value):
        raise _Bad(f"{subject} holds a field outside the contract")
    for key in fields:
        if key not in value and key not in optional:
            raise _Bad(f"{subject} lacks {key}")
    return value


def _object(
    value: object,
    where: str,
    fields: Mapping[str, _Check],
    optional: Collection[str] = (),
) -> dict[str, object]:
    """An object with exactly `fields` (those in `optional` may be absent), each value
    checked under its own name."""
    _keys(value, where or "the line", fields, optional)
    return {
        key: check(value[key], _at(where, key))
        for key, check in fields.items()
        if key in value
    }


def _object_of(fields: Mapping[str, _Check], optional: Collection[str] = ()) -> _Check:
    return lambda value, where: _object(value, where, fields, optional)


def _list_of(check: _Check) -> _Check:
    def checked(value: object, where: str) -> tuple[object, ...]:
        if not isinstance(value, list):
            raise _Bad(f"{where} must be a list")
        return tuple(
            check(item, f"{where}[{index}]") for index, item in enumerate(value)
        )

    return checked


def _map_of(key_check: _Check, item_check: _Check) -> _Check:
    """An object whose names aren't fixed, such as frozen's or bins'. Its names are
    checked too, and never printed."""

    def checked(value: object, where: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise _Bad(f"{where} must be an object")
        return {
            key_check(key, f"a name in {where}"): item_check(
                item, f"a value in {where}"
            )
            for key, item in value.items()
        }

    return checked


def _nullable(check: _Check) -> _Check:
    return lambda value, where: None if value is None else check(value, where)


def _among(allowed: Collection[str], what: str) -> _Check:
    def check(value: object, where: str) -> str:
        if not isinstance(value, str) or value not in allowed:
            raise _Bad(f"{where} must be {what}")
        return value

    return check


def _among_or_null(allowed: Collection[str], what: str) -> _Check:
    strict = _among(allowed, what)

    def check(value: object, where: str) -> str | None:
        return None if value is None else strict(value, where)

    return check


def _matching(pattern: re.Pattern[str], what: str) -> _Check:
    def check(value: object, where: str) -> str:
        if not isinstance(value, str) or not pattern.fullmatch(value):
            raise _Bad(f"{where} must be {what}")
        return value

    return check


_id = _matching(_ID, "an opaque id")
_token = _matching(_TOKEN, "a lowercase token")
_commit = _matching(_COMMIT, "40 lowercase hex characters")
_tire_code = _matching(_TIRE_CODE, "a tire code such as 185/65R15")


def _short(value: object, where: str) -> str:
    """A short string of plain characters, which can't hold a link or an email."""
    if not isinstance(value, str) or not _SHORT.fullmatch(value) or "://" in value:
        raise _Bad(
            f"{where} must be up to 80 plain characters (letters, digits, spaces"
            " and ._:/,+()=-), with no ://"
        )
    return value


def _reason(value: object, where: str) -> str:
    """A reason run.json records, which the report quotes: a short string that
    isn't blank."""
    if not _short(value, where).strip():
        raise _Bad(f"{where} must hold at least one character that isn't a space")
    return value


def _date(value: object, where: str) -> str:
    if isinstance(value, str) and _DATE.fullmatch(value):
        try:
            datetime.date.fromisoformat(value)
        except ValueError:
            pass
        else:
            return value
    raise _Bad(f"{where} must be a YYYY-MM-DD date")


def _rules_version(value: object, where: str) -> str:
    if value != RULES_VERSION:
        raise _Bad(f"{where} must be {RULES_VERSION}, the rules this harness scores")
    return RULES_VERSION


def _label(value: object, where: str) -> str:
    if not isinstance(value, str) or not label_words_ok(value):
        raise _Bad(f"{where} must hold only the label words (C420)")
    return value


def _bool(value: object, where: str) -> bool:
    if not isinstance(value, bool):
        raise _Bad(f"{where} must be true or false")
    return value


def _null(value: object, where: str) -> None:
    if value is not None:
        raise _Bad(f"{where} must be null")


def _any(value: object, where: str) -> object:
    """No check of its own: the caller checks this field against the others."""
    return value


def _int(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _Bad(f"{where} must be a whole number")
    return value


def _count(value: object, where: str) -> int:
    if _int(value, where) < 0:
        raise _Bad(f"{where} must be 0 or more")
    return value


def _wheel_number(value: object, where: str) -> int:
    if _int(value, where) not in (1, 2):
        raise _Bad(f"{where} must be 1 or 2")
    return value


def _box_id(value: object, where: str) -> int:
    """A box's id, in Muse Spark's answer, an M8 label or wheel_inches."""
    if not 0 <= _int(value, where) <= 9999:
        raise _Bad(f"{where} must be a whole number from 0 to 9999")
    return value


def _decimal(value: object, where: str) -> Decimal:
    """A number with at most 4 decimal places. A JSON integer becomes a Decimal."""
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise _Bad(f"{where} must be a number")
    number = Decimal(value)
    if number.as_tuple().exponent < -4:
        raise _Bad(f"{where} carries more than 4 decimal places")
    return number


def _depth(value: object, where: str) -> Decimal:
    depth = _decimal(value, where)
    if not 0 <= depth < 100:
        raise _Bad(f"{where} must be from 0 to under 100 inches")
    return depth


def _seconds(value: object, where: str) -> Decimal:
    seconds = _decimal(value, where)
    if not 0 < seconds < 3600:
        raise _Bad(f"{where} must be above 0 and under 3600")
    return seconds


# run.json


_KIND = _among(("sealed", "development"), "sealed or development")
_DATASETS = ("set_a", "a_neg", "set_b", "set_d")
_RUN_FIELDS: dict[str, _Check] = {
    "kind": _KIND,
    "date": _date,
    "rules_version": _rules_version,
    "freeze_commit": _commit,
    "frozen": _map_of(_token, _short),
    "datasets": _object_of(
        {
            name: _object_of({"version": _short, "split_seed": _short})
            for name in _DATASETS
        },
        optional=_DATASETS,
    ),
    "self_check": _among(("on", "off"), "on or off"),
    "self_check_decided": _short,
    "geometry_default": _among(("on", "off", "dropped"), "on, off or dropped"),
    "geometry_dropped_reason": _reason,
    "stops": _list_of(_object_of({"at": _short, "cause": _short, "resumed": _short})),
    "rerun_reason": _reason,
    "synthetic": _bool,
    "service_retries": _count,
    "baseline_level": _among(LEVELS, "one of the 9 levels"),
    # Null when no development label states a class: rules §2 leaves such photos out of the
    # passability metric, so there is no class baseline (Rene's option A, Nov 2).
    "baseline_class": _among_or_null(CLASS_NAMES, "PATV, NPLV, NPATV or null"),
}
# What frozen.untuned says (rules 4.3): yes when the cutoffs kept their start values
# (the tuning in force equals START), and no when they were tuned on development data and
# validated by event replay. A sealed run records it, and a development run may not.
UNTUNED = ("yes", "no")
# A sealed run needs every field but these; a development run may also leave out the
# rest, and then computes its baseline from its own rows (C424) and reads
# service_retries as 0 (MS6E-Q6).
_SEALED_OPTIONAL = ("geometry_dropped_reason", "stops", "rerun_reason", "synthetic")
_DEVELOPMENT_OPTIONAL = (
    *_SEALED_OPTIONAL,
    "service_retries",
    "rules_version",
    "freeze_commit",
    "self_check_decided",
    "geometry_default",
    "baseline_level",
    "baseline_class",
)


def _manifest(value: object, in_rerun_folder: bool) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _Bad("the manifest must be an object")
    kind = _KIND(value.get("kind"), "kind")
    optional = _SEALED_OPTIONAL if kind == "sealed" else _DEVELOPMENT_OPTIONAL
    _keys(value, "the manifest", _RUN_FIELDS, optional)
    meta = {
        key: check(value[key], key)
        for key, check in _RUN_FIELDS.items()
        if key in value
    }
    if ("baseline_level" in meta) != ("baseline_class" in meta):
        raise _Bad("baseline_level and baseline_class come as a pair (C424)")
    if (meta.get("geometry_default") == "dropped") != (
        "geometry_dropped_reason" in meta
    ):
        raise _Bad(
            "geometry_dropped_reason comes with geometry_default dropped, and only then"
        )
    if in_rerun_folder != ("rerun_reason" in meta):
        raise _Bad("rerun_reason comes with a rerun folder, and only there (C421)")
    untuned = meta["frozen"].get("untuned")
    if untuned is None and kind == "sealed":
        raise _Bad("frozen lacks untuned, which a sealed run records (rules 4.3)")
    if untuned is not None and untuned not in UNTUNED:
        raise _Bad("frozen holds untuned as yes or no only (rules 4.3)")
    return meta


def _configs(self_check: bool, dropped: bool) -> tuple[str, ...]:
    """The configurations each photo carries: landmark alone once geometry is dropped,
    or else landmark and geometry, and geometry_no_self_check with the self-check on."""
    if dropped:
        return CONFIGS[:1]
    return CONFIGS if self_check else CONFIGS[:2]


# Results


def _basis(value: object, where: str) -> dict[str, object]:
    basis = _object(value, where, {"vehicles": _count, "people": _count})
    if basis["vehicles"] + basis["people"] < 1:
        raise _Bad(f"{where} must count at least one vehicle or person")
    return basis


_STATUS = _among(("done", "refused", "failed"), "done, refused or failed")
_RESULT_LANDMARKS = (WHEEL_WATERLINES | BODY_WATERLINES | PERSON_WATERLINES) - {
    "not_visible"
}
_REFUSAL_FIELDS = {"status": _any, "refusalReason": _token}
_NO_FLOOD_FIELDS = {"status": _any, "noFloodSeen": _any}
_LEVEL_FIELDS = {
    "status": _any,
    "noFloodSeen": _any,
    "level": _among(LEVELS, "one of the 9 levels"),
    "landmark": _among(
        _RESULT_LANDMARKS, "a schema v1 waterline other than not_visible"
    ),
    "passability": _any,
    "levelIsFloor": _bool,
    "basis": _basis,
    "levelFrom": _among(("landmark", "geometry"), "landmark or geometry"),
    "depthInMin": _depth,
    "depthInMax": _depth,
}
_LEVEL_OPTIONAL = ("levelFrom", "depthInMin", "depthInMax")


def _result(value: object, where: str) -> Result:
    """One item_fields() result: a refusal or failure, "no flood seen", or a level."""
    if not isinstance(value, dict):
        raise _Bad(f"{where} must be an object")
    status = _STATUS(value.get("status"), _at(where, "status"))
    if status != "done":
        result = _object(value, where, _REFUSAL_FIELDS)
        return Result(status, result["refusalReason"], False, None, False, None, None)
    if _bool(value.get("noFloodSeen"), _at(where, "noFloodSeen")):
        _object(value, where, _NO_FLOOD_FIELDS)
        return Result("done", None, True, None, False, None, None)
    result = _object(value, where, _LEVEL_FIELDS, _LEVEL_OPTIONAL)
    if result["passability"] != CLASSES[result["level"]]:
        raise _Bad(
            f"{_at(where, 'passability')} must be the level's class, in capitals"
        )
    if ("depthInMin" in result) != ("depthInMax" in result):
        raise _Bad(f"{where} must carry depthInMin and depthInMax together")
    if "depthInMin" in result and result["depthInMin"] > result["depthInMax"]:
        raise _Bad(f"{_at(where, 'depthInMin')} must not be above depthInMax")
    return Result(
        "done",
        None,
        False,
        result["level"],
        result["levelIsFloor"],
        result["passability"],
        result["landmark"],
    )


def _outcomes(
    value: object, where: str, configs: tuple[str, ...], replays: bool
) -> dict[str, Result]:
    """A photo's results: exactly `configs`, and on a development run a replay result
    for any of them (C425)."""
    if not isinstance(value, dict):
        raise _Bad(f"{where} must be an object")
    for name in value:
        replayed = (
            name.removesuffix(REPLAY_SUFFIX) if name.endswith(REPLAY_SUFFIX) else None
        )
        if name in configs or (replays and replayed in configs):
            continue
        if replayed is not None and not replays:
            raise _Bad(
                f"{where} holds a replay, which a sealed run never carries (C425)"
            )
        if replayed is not None:
            raise _Bad(f"{where} holds a replay whose configuration is absent (C425)")
        if name in CONFIGS:
            raise _Bad(
                f"{_at(where, name)} doesn't fit self_check and geometry_default"
            )
        raise _Bad(f"{where} holds a configuration outside the contract")
    for name in configs:
        if name not in value:
            raise _Bad(f"{where} lacks {name}")
    return {name: _result(result, _at(where, name)) for name, result in value.items()}


# Set A and A-neg rows


_YES_NO_UNSURE = _among(YES_NO_UNSURE, "yes, no or unsure")
_VEHICLE_TYPE = _among(VEHICLE_TYPES, "a schema v1 vehicle type")


def _items(fields: Mapping[str, _Check]) -> _Check:
    """One of the answer's lists, whose items each carry an id found once in it."""
    items = _list_of(_object_of(fields))

    def checked(value: object, where: str) -> tuple[object, ...]:
        found = items(value, where)
        seen = set()
        for index, item in enumerate(found):
            if item["id"] in seen:
                raise _Bad(f"{where}[{index}].id repeats an earlier item's")
            seen.add(item["id"])
        return found

    return checked


_ANSWER_FIELDS = {
    "photo_usable": _among(YES_NO, "yes or no"),
    "standing_water": _YES_NO_UNSURE,
    "vehicles": _items(
        {
            "id": _box_id,
            "type": _VEHICLE_TYPE,
            "moving": _YES_NO_UNSURE,
            "wake_visible": _bool,
            "body_waterline": _among(BODY_WATERLINES, "a schema v1 body waterline"),
        }
    ),
    "wheels": _items(
        {
            "id": _box_id,
            "waterline": _among(WHEEL_WATERLINES, "a schema v1 wheel waterline"),
        }
    ),
    "people": _items(
        {
            "id": _box_id,
            "adult": _YES_NO_UNSURE,
            "standing_still": _YES_NO_UNSURE,
            "waterline": _among(PERSON_WATERLINES, "a schema v1 person waterline"),
        }
    ),
}
_WHEEL_INCHES_FIELDS = {"box_id": _box_id, "depthInMin": _depth, "depthInMax": _depth}


def _wheel_inches(value: object, where: str) -> dict[str, object]:
    """One wheel's depthInMin and depthInMax, by its box id, in order."""
    pair = _object(value, where, _WHEEL_INCHES_FIELDS)
    if pair["depthInMin"] > pair["depthInMax"]:
        raise _Bad(f"{_at(where, 'depthInMin')} must not be above depthInMax")
    return pair


# Each M8 kind: the reference it gives, the waterlines M8 may mark on it, and where
# Muse Spark's answer reads the same box (its list, and the field there).
_M8_KINDS = {
    "wheel": ("wheel", WHEEL_WATERLINES, "wheels", "waterline"),
    "vehicle": ("body", BODY_WATERLINES, "vehicles", "body_waterline"),
    "person": ("person", PERSON_WATERLINES, "people", "waterline"),
}
_M8_FIELDS = {
    "box_id": _nullable(_box_id),
    "kind": _among(_M8_KINDS, "wheel, vehicle or person"),
    "landmark": _any,
    "vehicle_type": _any,
}


def _m8_label(value: object, where: str) -> dict[str, object]:
    """One M8 label: a landmark from its kind's waterlines, or null, and a type for a
    vehicle only."""
    label = _object(value, where, _M8_FIELDS)
    reference, waterlines, _, _ = _M8_KINDS[label["kind"]]
    landmark = _among(waterlines, f"null or a schema v1 {reference} waterline")
    _nullable(landmark)(label["landmark"], _at(where, "landmark"))
    if label["kind"] == "vehicle":
        _VEHICLE_TYPE(label["vehicle_type"], _at(where, "vehicle_type"))
    else:
        _null(label["vehicle_type"], _at(where, "vehicle_type"))
    return label


def _photo_fields(
    *, a_neg: bool, configs: tuple[str, ...], replays: bool
) -> dict[str, _Check]:
    """A Set A row's fields, or an A-neg row's: no labels and no M8, a null match,
    and a surface."""
    fields: dict[str, _Check] = {
        "photo_id": _id,
        "event_id": _id,
        "poster_kind": _among(("mmda", "city", "other"), "mmda, city or other"),
        "label_in_image": _among(("no", "cropped", "yes"), "no, cropped or yes"),
        "duplicate": _bool,
        "metro_manila": _bool,
        "decodes": _bool,
        # Null when no mark was made (C423).
        "quality": _nullable(
            _among(("ok", "dark", "blurry"), "ok, dark, blurry or null")
        ),
        "subsets": _list_of(_token),
        "outcomes": lambda value, where: _outcomes(value, where, configs, replays),
        "answer": _nullable(_object_of(_ANSWER_FIELDS)),
        "wheel_inches": _list_of(_wheel_inches),
    }
    if a_neg:
        fields["match"] = _null
        fields["surface"] = _among(("wet", "dry"), "wet or dry")
    else:
        fields["match"] = _among(
            ("same_post", "separate_post", "none"), "same_post, separate_post or none"
        )
        fields["level_label_raw"] = _label
        fields["passability_raw"] = _label
        fields["other_alerts_raw"] = _list_of(_label)
        fields["m8"] = _list_of(_m8_label)
    return fields


def _photo_row(value: object, fields: Mapping[str, _Check]) -> PhotoRow:
    row = _object(value, "", fields)
    return PhotoRow(
        photo_id=row["photo_id"],
        event_id=row["event_id"],
        level_label_raw=row.get("level_label_raw", ""),
        passability_raw=row.get("passability_raw", ""),
        other_alerts_raw=row.get("other_alerts_raw", ()),
        facts=Facts(
            poster_kind=row["poster_kind"],
            label_in_image=row["label_in_image"],
            match=row["match"],
            duplicate=row["duplicate"],
            metro_manila=row["metro_manila"],
            decodes=row["decodes"],
        ),
        quality=row["quality"],
        subsets=row["subsets"],
        surface=row.get("surface"),
        results=row["outcomes"],
        answered=row["answer"] is not None,
        references=_references(row.get("m8", ()), row["answer"]),
    )


def _references(labels: Sequence[dict], answer: dict | None) -> tuple[Reference, ...]:
    """Each M8 label beside Muse Spark's reading of its box in the answer's list for
    its kind (C415). No answer, no box, or a box the answer lacks reads as None."""
    references = []
    for label in labels:
        kind, _, items, field = _M8_KINDS[label["kind"]]
        item = None
        if answer is not None and label["box_id"] is not None:
            # An id comes once in each of the answer's lists, so one item at most.
            item = next(
                (found for found in answer[items] if found["id"] == label["box_id"]),
                None,
            )
        references.append(
            Reference(
                box_id=label["box_id"],
                kind=kind,
                m8_landmark=label["landmark"],
                m8_type=label["vehicle_type"],
                spark_landmark=None if item is None else item[field],
                spark_type=None if item is None or kind != "body" else item["type"],
            )
        )
    return tuple(references)


# Set B and Set D rows


_ESTIMATE_FIELDS = {
    "measured": _bool,
    "depthInPoint": _nullable(_depth),
    "depthInMin": _nullable(_depth),
    "depthInMax": _nullable(_depth),
    "fail": _nullable(_token),
}


def _estimate(value: object, where: str) -> Estimate:
    found = _object(value, where, _ESTIMATE_FIELDS)
    numbers = (found["depthInPoint"], found["depthInMin"], found["depthInMax"])
    if found["measured"]:
        if any(number is None for number in numbers) or found["fail"] is not None:
            raise _Bad(
                f"{where} is measured, so it needs its three numbers and a null fail"
            )
        # The envelope is in order; the point may lie outside it.
        if found["depthInMin"] > found["depthInMax"]:
            raise _Bad(f"{_at(where, 'depthInMin')} must not be above depthInMax")
        return Estimate(True, *numbers, None)
    if any(number is not None for number in numbers) or found["fail"] is None:
        raise _Bad(
            f"{where} is unmeasured, so it needs three nulls and the check that failed"
        )
    return Estimate(False, None, None, None, found["fail"])


# What MS3b's export gives every variant of a wheel whose Meta call failed twice. Such
# a wheel never got an answer, so whether SAM found water is null (MS6E-Q6).
_NO_ANSWER = Estimate(False, None, None, None, "model_error")
_VARIANT_FIELDS = dict.fromkeys(SET_B_VARIANTS, _estimate)
_VARIANTS_OPTIONAL = tuple(name for name in SET_B_VARIANTS if name != "geometry")


def _estimates(value: object, where: str, self_check: bool) -> dict[str, Estimate]:
    """A wheel's estimates by variant: geometry always, and the others as run."""
    estimates = _object(value, where, _VARIANT_FIELDS, _VARIANTS_OPTIONAL)
    if "geometry_no_self_check" in estimates and not self_check:
        raise _Bad(f"{_at(where, 'geometry_no_self_check')} needs self_check on")
    return estimates


def _wheel_fields(self_check: bool) -> dict[str, _Check]:
    return {
        "crop_id": _id,
        "wheel": _wheel_number,
        "car_id": _id,
        "vehicle_type": _VEHICLE_TYPE,
        "tire_code": _tire_code,
        "true_depth_in": _depth,
        "sam_water_found": _nullable(_bool),
        "bins": _map_of(_token, _token),
        "estimates": lambda value, where: _estimates(value, where, self_check),
    }


def _wheel_row(value: object, fields: Mapping[str, _Check]) -> WheelRow:
    row = _object(value, "", fields, optional=("bins",))
    if row["sam_water_found"] is None and any(
        estimate != _NO_ANSWER for estimate in row["estimates"].values()
    ):
        raise _Bad(
            "sam_water_found may be null only when every variant failed with"
            " model_error"
        )
    return WheelRow(
        crop_id=row["crop_id"],
        wheel=row["wheel"],
        car_id=row["car_id"],
        vehicle_type=row["vehicle_type"],
        tire_code=row["tire_code"],
        true_depth_in=row["true_depth_in"],
        sam_water_found=row["sam_water_found"],
        bins=row.get("bins", {}),
        estimates=row["estimates"],
    )


# Files


def _parse(text: str) -> object:
    """One JSON value, its numbers as int or Decimal. NaN and Infinity are refused,
    and so is a repeated key, which would hide text that no check reads."""
    try:
        return json.loads(
            text,
            parse_float=Decimal,
            parse_constant=_no_constant,
            object_pairs_hook=_unique_keys,
        )
    except (ValueError, RecursionError):
        raise _Bad("the text isn't valid JSON") from None


def _no_constant(name: str) -> object:
    raise _Bad("NaN and Infinity aren't numbers here")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    found = dict(pairs)
    if len(found) < len(pairs):
        raise _Bad("an object repeats a key")
    return found


def _text(folder: Path, name: str) -> str:
    """A file's text: UTF-8 with an optional byte-order mark, its \\r\\n endings read
    as \\n."""
    try:
        return (folder / name).read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise RowError(name, 0, "the file isn't UTF-8") from None


def _read_manifest(folder: Path) -> dict[str, object]:
    if not (folder / "run.json").is_file():
        raise RowError("run.json", 0, "the folder has no run.json")
    text = _text(folder, "run.json")
    try:
        return _manifest(_parse(text), folder.resolve().name == "rerun")
    except _Bad as bad:
        raise RowError("run.json", 0, str(bad)) from None


def _read(
    folder: Path, name: str, check: Callable[[object], _T]
) -> list[tuple[int, _T]] | None:
    """A JSON Lines file's rows, each checked and kept with its line number, or None
    when the file is absent. A blank line is skipped, but still counted."""
    if not (folder / name).is_file():
        return None
    rows = []
    for number, line in enumerate(_text(folder, name).split("\n"), start=1):
        if not line.strip():
            continue
        try:
            rows.append((number, check(_parse(line))))
        except _Bad as bad:
            raise RowError(name, number, str(bad)) from None
    return rows


def _no_repeats(
    name: str, rows: list[tuple[int, _T]], key: Callable[[_T], object], what: str
) -> None:
    seen = set()
    for number, row in rows:
        if key(row) in seen:
            raise RowError(name, number, what)
        seen.add(key(row))


def _photos(
    folder: Path, name: str, fields: Mapping[str, _Check]
) -> tuple[PhotoRow, ...] | None:
    rows = _read(folder, name, lambda value: _photo_row(value, fields))
    if rows is None:
        return None
    _no_repeats(
        name, rows, lambda row: row.photo_id, "photo_id repeats an earlier row's"
    )
    # So a replay is always compared over the same photos (C425).
    for number, row in rows[1:]:
        if _replays(row) != _replays(rows[0][1]):
            raise RowError(
                name, number, "replay results must be the same on every row (C425)"
            )
    return tuple(row for _, row in rows)


def _replays(row: PhotoRow) -> set[str]:
    return {name for name in row.results if name.endswith(REPLAY_SUFFIX)}


def _wheels(
    folder: Path, name: str, fields: Mapping[str, _Check]
) -> tuple[WheelRow, ...] | None:
    rows = _read(folder, name, lambda value: _wheel_row(value, fields))
    if rows is None:
        return None
    _no_repeats(
        name,
        rows,
        lambda row: (row.crop_id, row.wheel),
        "crop_id and wheel repeat an earlier row's",
    )
    for number, row in rows[1:]:
        if set(row.estimates) != set(rows[0][1].estimates):
            raise RowError(
                name, number, "estimates must name the same variants on every row"
            )
    return tuple(row for _, row in rows)


_LATENCY_FIELDS = {"test_id": _id, "seconds": _seconds}


def _latency(folder: Path) -> tuple[tuple[str, Decimal], ...] | None:
    rows = _read(
        folder, "latency.jsonl", lambda value: _object(value, "", _LATENCY_FIELDS)
    )
    if rows is None:
        return None
    return tuple((row["test_id"], row["seconds"]) for _, row in rows)
