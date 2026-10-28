"""Synthetic results for the harness's tests (MS6, Task 2).

Each builder gives a row that passes the row contract (spec §4.3) and rules §9, so a
test changes only what it is about. No fixture holds real data.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

from scoring import RULES_VERSION
from scoring.scale import CLASSES


def level(
    level: str,
    *,
    floor: bool = False,
    landmark: str = "hub",
    level_from: str | None = None,
    inches: tuple[str, str] | None = None,
) -> dict:
    """A level result as item_fields() writes it, on one vehicle, with MS3b's
    optional levelFrom and depth pair."""
    result = {
        "status": "done",
        "noFloodSeen": False,
        "level": level,
        "landmark": landmark,
        "passability": CLASSES[level],
        "levelIsFloor": floor,
        "basis": {"vehicles": 1, "people": 0},
    }
    if level_from is not None:
        result["levelFrom"] = level_from
    if inches is not None:
        result["depthInMin"] = Decimal(inches[0])
        result["depthInMax"] = Decimal(inches[1])
    return result


def nfs() -> dict:
    """A "no flood seen" result."""
    return {"status": "done", "noFloodSeen": True}


def refused(reason: str) -> dict:
    """A refusal, with its reason."""
    return {"status": "refused", "refusalReason": reason}


def failed(reason: str) -> dict:
    """A processing failure, with its reason."""
    return {"status": "failed", "refusalReason": reason}


def set_a_row(
    photo_id: str,
    *,
    label: str = "knee deep",
    passability: str = "",
    others: tuple[str, ...] = (),
    landmark: dict | None = None,
    geometry: dict | None = None,
    **fields: object,
) -> dict:
    """A Set A photo whose facts pass rules §9, marked ok, answered and without M8
    labels. Both results default to knee; any other field is set through `fields`."""
    row = {
        "photo_id": photo_id,
        "event_id": "E01",
        "level_label_raw": label,
        "passability_raw": passability,
        "other_alerts_raw": list(others),
        "poster_kind": "mmda",
        "label_in_image": "no",
        "match": "same_post",
        "duplicate": False,
        "metro_manila": True,
        "decodes": True,
        "quality": "ok",
        "subsets": [],
        "outcomes": {
            "landmark": level("knee") if landmark is None else landmark,
            "geometry": level("knee") if geometry is None else geometry,
        },
        "answer": _answer(standing_water="yes"),
        "wheel_inches": [],
        "m8": [],
    }
    row.update(fields)
    return row


def a_neg_row(photo_id: str, **fields: object) -> dict:
    """An A-neg photo of a wet street. MS2 has no M8 for A-neg, so quality is
    unmarked and there are no subsets (C423), and match is null. Both results
    default to no flood seen."""
    row = {
        "photo_id": photo_id,
        "event_id": "E01",
        "poster_kind": "other",
        "label_in_image": "no",
        "match": None,
        "duplicate": False,
        "metro_manila": True,
        "decodes": True,
        "quality": None,
        "subsets": [],
        "surface": "wet",
        "outcomes": {"landmark": nfs(), "geometry": nfs()},
        "answer": _answer(standing_water="no"),
        "wheel_inches": [],
    }
    row.update(fields)
    return row


def set_b_row(crop_id: str, wheel: int = 1, **fields: object) -> dict:
    """A Set B (or Set D) wheel 11.25 in deep, measured by the frozen geometry."""
    row = {
        "crop_id": crop_id,
        "wheel": wheel,
        "car_id": "C01",
        "vehicle_type": "sedan_hatch",
        "tire_code": "185/65R15",
        "true_depth_in": Decimal("11.25"),
        "sam_water_found": True,
        "estimates": {
            "geometry": {
                "measured": True,
                "depthInPoint": Decimal("11.5"),
                "depthInMin": Decimal("10.75"),
                "depthInMax": Decimal("12.25"),
                "fail": None,
            }
        },
    }
    row.update(fields)
    return row


def run_json(**overrides: object) -> dict:
    """A development run's manifest. It holds every key a sealed run needs, so
    kind="sealed" alone makes a sealed one."""
    run = {
        "kind": "development",
        "date": "2026-10-30",
        "rules_version": RULES_VERSION,
        "freeze_commit": "ab" * 20,
        "frozen": {
            "model": "muse-spark-1.3",
            "prompt": "muse_spark_photo_v1",
            "k": "1.0",
        },
        "datasets": {
            name: {"version": "v1", "split_seed": "7"}
            for name in ("set_a", "a_neg", "set_b")
        },
        "self_check": "off",
        "self_check_decided": "2026-10-29",
        "geometry_default": "on",
        "baseline_level": "knee",
        "baseline_class": "NPLV",
    }
    run.update(overrides)
    return run


def write_run(
    folder: Path,
    *,
    run: dict,
    set_a: Sequence[dict] | None = None,
    a_neg: Sequence[dict] | None = None,
    set_b: Sequence[dict] | None = None,
    set_d: Sequence[dict] | None = None,
    latency: Sequence[dict] | None = None,
) -> Path:
    """Write a results folder: run.json, and a JSON Lines file with \\n endings for
    each set given. A set given as None gets no file."""
    folder.mkdir(parents=True, exist_ok=True)
    _write(folder / "run.json", _json(run))
    sets = {
        "set_a": set_a,
        "a_neg": a_neg,
        "set_b": set_b,
        "set_d": set_d,
        "latency": latency,
    }
    for name, rows in sets.items():
        if rows is not None:
            _write(folder / f"{name}.jsonl", "".join(_json(row) + "\n" for row in rows))
    return folder


def _answer(*, standing_water: str) -> dict:
    """Muse Spark's saved answer, without its reason, with nothing in view."""
    return {
        "photo_usable": "yes",
        "standing_water": standing_water,
        "vehicles": [],
        "wheels": [],
        "people": [],
    }


def _json(value: object) -> str:
    """JSON text. A Decimal is written as a number by way of float, which keeps any
    value of up to 15 significant digits exact."""
    return json.dumps(value, ensure_ascii=False, default=float)


def _write(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))
