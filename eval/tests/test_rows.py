"""The row loader and its allow-list (spec §4.3; C402, C403, C420 to C425)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from builders import (
    a_neg_row,
    failed,
    level,
    nfs,
    refused,
    run_json,
    set_a_row,
    set_b_row,
    write_run,
)
from scoring.paths import SealedPath
from scoring.rows import (
    BODY_WATERLINES,
    PERSON_WATERLINES,
    REPLAY_SUFFIX,
    SET_B_VARIANTS,
    VEHICLE_TYPES,
    WHEEL_WATERLINES,
    YES_NO,
    YES_NO_UNSURE,
    Estimate,
    Facts,
    PhotoRow,
    Reference,
    Result,
    RowError,
    Run,
    WheelRow,
    load_run,
)

KNEE = Result("done", None, False, "knee", False, "NPLV", "hub")


def load(folder: Path, run: dict | None = None, **sets: list) -> Run:
    """Write a results folder with the builders, then load it."""
    return load_run(write_run(folder, run=run_json() if run is None else run, **sets))


def message_for(folder: Path) -> str:
    """The loader's message for a folder it must refuse. It is ASCII."""
    try:
        load_run(folder)
    except RowError as error:
        assert str(error).isascii(), str(error)
        return str(error)
    pytest.fail(f"the loader accepted {folder.name}")


def refusal(
    folder: Path, file: str, line: int = 1, run: dict | None = None, **sets: list
) -> str:
    """Write a results folder the loader must refuse, and check that the message
    names the file and the line."""
    message = message_for(
        write_run(folder, run=run_json() if run is None else run, **sets)
    )
    assert message.startswith(f"{file}:{line}: "), message
    return message


def sealed(**overrides: object) -> dict:
    return run_json(kind="sealed", **overrides)


def without(obj: dict, key: str) -> dict:
    return {name: value for name, value in obj.items() if name != key}


def answer(*, vehicles: list = (), wheels: list = (), people: list = ()) -> dict:
    """Muse Spark's saved answer, without its reason."""
    return {
        "photo_usable": "yes",
        "standing_water": "yes",
        "vehicles": list(vehicles),
        "wheels": list(wheels),
        "people": list(people),
    }


def wheel(box: object, waterline: str) -> dict:
    return {"id": box, "waterline": waterline}


def vehicle(box: int, kind: str, waterline: str) -> dict:
    return {
        "id": box,
        "type": kind,
        "moving": "no",
        "wake_visible": False,
        "body_waterline": waterline,
    }


def person(box: int, waterline: str) -> dict:
    return {"id": box, "adult": "yes", "standing_still": "yes", "waterline": waterline}


def m8(
    box: object, kind: str, landmark: str | None, vehicle_type: str | None = None
) -> dict:
    return {
        "box_id": box,
        "kind": kind,
        "landmark": landmark,
        "vehicle_type": vehicle_type,
    }


def measured(point: str = "11.5", low: str = "10.75", high: str = "12.25") -> dict:
    return {
        "measured": True,
        "depthInPoint": Decimal(point),
        "depthInMin": Decimal(low),
        "depthInMax": Decimal(high),
        "fail": None,
    }


def unmeasured(fail: str = "no_waterline") -> dict:
    return {
        "measured": False,
        "depthInPoint": None,
        "depthInMin": None,
        "depthInMax": None,
        "fail": fail,
    }


def test_schema_v1_categories():
    assert len(VEHICLE_TYPES) == 9
    assert (len(WHEEL_WATERLINES), len(BODY_WATERLINES), len(PERSON_WATERLINES)) == (
        7,
        6,
        8,
    )
    assert YES_NO_UNSURE == {"yes", "no", "unsure"} and YES_NO == {"yes", "no"}


def test_loads_a_valid_run(tmp_path):
    stop = {
        "at": "2026-10-30 21:10",
        "cause": "budget alert",
        "resumed": "2026-10-30 21:40",
    }
    inches = [
        {"box_id": 2, "depthInMin": Decimal("10.5"), "depthInMax": Decimal("12.25")}
    ]
    run = load(
        tmp_path,
        run_json(stops=[stop]),
        set_a=[
            set_a_row("A001", wheel_inches=inches),
            set_a_row("A002", label="gutter deep", passability="PATV", landmark=nfs()),
            set_a_row(
                "A003", landmark=refused("too_dark"), geometry=failed("model_error")
            ),
        ],
        a_neg=[a_neg_row("N001"), a_neg_row("N002", surface="dry")],
        set_b=[
            set_b_row("B01", 1, bins={"view": "side", "size_bin": "small"}),
            set_b_row("B01", 2, true_depth_in=Decimal("11.25")),
        ],
        latency=[
            {"test_id": "L01", "seconds": Decimal("41.5")},
            {"test_id": "L02", "seconds": 38},
        ],
    )
    assert isinstance(run, Run)
    assert (run.kind, run.synthetic, run.self_check, run.geometry_dropped) == (
        "development",
        False,
        False,
        False,
    )
    assert (run.baseline_level, run.baseline_class, run.rerun_reason) == (
        "knee",
        "NPLV",
        None,
    )
    assert run.meta["stops"][0]["cause"] == "budget alert"
    # Rows keep their file order.
    assert [row.photo_id for row in run.set_a] == ["A001", "A002", "A003"]
    assert all(isinstance(row, PhotoRow) for row in (*run.set_a, *run.a_neg))
    first = run.set_a[0]
    assert first.facts == Facts("mmda", "no", "same_post", False, True, True)
    assert (first.level_label_raw, first.quality, first.subsets, first.surface) == (
        "knee deep",
        "ok",
        (),
        None,
    )
    assert first.results == {"landmark": KNEE, "geometry": KNEE}
    assert first.answered and first.references == ()
    dry = run.a_neg[1]
    assert dry.facts == Facts("other", "no", None, False, True, True)
    assert (dry.surface, dry.level_label_raw, dry.other_alerts_raw) == ("dry", "", ())
    assert all(isinstance(row, WheelRow) for row in run.set_b)
    depth = run.set_b[1].true_depth_in
    assert isinstance(depth, Decimal) and depth == Decimal("11.25")
    assert run.set_b[0].bins == {"view": "side", "size_bin": "small"}
    assert run.set_b[1].bins == {}  # a missing bins reads as {}
    assert run.set_b[0].estimates == {
        "geometry": Estimate(
            True, Decimal("11.5"), Decimal("10.75"), Decimal("12.25"), None
        )
    }
    assert run.latency == (("L01", Decimal("41.5")), ("L02", Decimal(38)))
    assert run.set_d is None


@pytest.mark.parametrize(
    "field",
    ["reason", "post_url", "spot_text", "city", "alert_time_pht", "conflicting_alerts"],
)
def test_refuses_fields_outside_the_contract(tmp_path, field):
    message = refusal(
        tmp_path, "set_a.jsonl", set_a=[set_a_row("A001", **{field: "Espana"})]
    )
    assert "outside the contract" in message and field not in message


FREE_TEXT = {
    "waterline in words": (
        "set_a",
        set_a_row("A001", answer=answer(wheels=[wheel(1, "Rim quarter")])),
    ),
    "unknown waterline": (
        "set_a",
        set_a_row("A001", answer=answer(wheels=[wheel(1, "hubcap")])),
    ),
    "reason in the answer": (
        "set_a",
        set_a_row("A001", answer={**answer(), "reason": "x"}),
    ),
    "reason in a wheel": (
        "set_a",
        set_a_row("A001", answer=answer(wheels=[{**wheel(1, "hub"), "reason": "x"}])),
    ),
    "refusal reason with a space": (
        "set_a",
        set_a_row("A001", landmark=refused("too dark")),
    ),
    "subset in capitals": ("set_a", set_a_row("A001", subsets=["Night"])),
    "bin value with a space": ("set_b", set_b_row("B01", bins={"view": "side view"})),
    "failed check with a space": (
        "set_b",
        set_b_row("B01", estimates={"geometry": unmeasured("no waterline")}),
    ),
}


@pytest.mark.parametrize(("name", "row"), list(FREE_TEXT.values()), ids=list(FREE_TEXT))
def test_refuses_free_text(tmp_path, name, row):
    refusal(tmp_path, f"{name}.jsonl", **{name: [row]})


def test_accepts_real_values(tmp_path):
    sedan = "not passable to motorcycles and cars (sedan)"
    assert len(sedan) == 44
    others = ("Knee deep", "(other words)")
    run = load(tmp_path, set_a=[set_a_row("A001", passability=sedan, others=others)])
    row = run.set_a[0]
    assert (row.passability_raw, row.other_alerts_raw) == (sedan, others)
    assert row.results["landmark"].passability == "NPLV"


PRIVATE_LABELS = {
    "spot name": ({"label": "Espana Maceda"}, "level_label_raw"),
    "time": ({"label": "knee deep 8:00 AM"}, "level_label_raw"),
    "link": ({"label": "http://x"}, "level_label_raw"),
    "spot among other alerts": (
        {"others": ("Knee deep", "Espana")},
        "other_alerts_raw[1]",
    ),
    "spot in a passability label": (
        {"passability": "not passable at Espana"},
        "passability_raw",
    ),
}


@pytest.mark.parametrize(
    ("labels", "field"), list(PRIVATE_LABELS.values()), ids=list(PRIVATE_LABELS)
)
def test_refuses_private_text_in_labels(tmp_path, labels, field):
    assert field in refusal(
        tmp_path, "set_a.jsonl", set_a=[set_a_row("A001", **labels)]
    )


def test_refuses_ids_that_arent_opaque(tmp_path):
    for index, photo_id in enumerate(["A 01", "2026-10-30", "Espana", "A0001-1-2-3"]):
        rows = [set_a_row(photo_id)]
        assert "photo_id" in refusal(
            tmp_path / f"bad{index}", "set_a.jsonl", set_a=rows
        )
    good = ["A001", "N001", "E01", "B01-1-2", "D01"]
    run = load(tmp_path / "good", set_a=[set_a_row(photo_id) for photo_id in good])
    assert [row.photo_id for row in run.set_a] == good
    other_ids = {
        "event": ("set_a", set_a_row("A001", event_id="flood 1"), "event_id"),
        "crop": ("set_b", set_b_row("b01"), "crop_id"),
        "car": ("set_b", set_b_row("B01", car_id="Car1"), "car_id"),
        "test": ("latency", {"test_id": "L-01", "seconds": 40}, "test_id"),
    }
    for case, (name, row, field) in other_ids.items():
        assert field in refusal(tmp_path / case, f"{name}.jsonl", **{name: [row]})
    twice = [set_a_row("A001"), set_a_row("A001")]
    assert "photo_id" in refusal(tmp_path / "twice", "set_a.jsonl", 2, set_a=twice)
    same_wheel = [set_b_row("B01", 1), set_b_row("B01", 1)]
    assert "crop_id" in refusal(
        tmp_path / "same_wheel", "set_b.jsonl", 2, set_b=same_wheel
    )


SHAPES = {
    "wrong class": ({**level("knee"), "passability": "PATV"}, "passability"),
    "lowercase class": ({**level("knee"), "passability": "nplv"}, "passability"),
    "level without basis": (without(level("knee"), "basis"), "basis"),
    "no flood seen with a level": ({**nfs(), "level": "knee"}, "outside the contract"),
    "refusal with a level": (
        {**refused("too_dark"), "level": "knee"},
        "outside the contract",
    ),
    "landmark not_visible": (level("knee", landmark="not_visible"), "landmark"),
    "basis of nothing": (
        {**level("knee"), "basis": {"vehicles": 0, "people": 0}},
        "basis",
    ),
    "negative basis": (
        {**level("knee"), "basis": {"vehicles": 2, "people": -1}},
        "basis.people",
    ),
    "unknown level": ({**level("knee"), "level": "ankle"}, "level"),
    "unknown status": ({"status": "pending"}, "status"),
    "unknown levelFrom": (level("knee", level_from="sam"), "levelFrom"),
    "half a depth pair": ({**level("knee"), "depthInMin": Decimal(15)}, "depthInMax"),
    "depths out of order": (level("knee", inches=("16", "15")), "depthInMin"),
    "depth of 100": (level("knee", inches=("15", "100")), "depthInMax"),
    "negative depth": (level("knee", inches=("-1", "15")), "depthInMin"),
    "level": (level("knee"), KNEE),
    "geometry's floored level": (
        level(
            "tire",
            floor=True,
            landmark="wheel_covered",
            level_from="geometry",
            inches=("19.5", "24.25"),
        ),
        Result("done", None, False, "tire", True, "NPATV", "wheel_covered"),
    ),
    "no flood seen": (nfs(), Result("done", None, True, None, False, None, None)),
    "refused": (
        refused("too_dark"),
        Result("refused", "too_dark", False, None, False, None, None),
    ),
    "failed": (
        failed("model_error"),
        Result("failed", "model_error", False, None, False, None, None),
    ),
}


@pytest.mark.parametrize(
    ("result", "expected"), list(SHAPES.values()), ids=list(SHAPES)
)
def test_result_shapes(tmp_path, result, expected):
    sets = {"set_a": [set_a_row("A001", landmark=result)]}
    if isinstance(expected, Result):
        assert load(tmp_path, **sets).set_a[0].results["landmark"] == expected
    else:
        message = refusal(tmp_path, "set_a.jsonl", **sets)
        assert "outcomes.landmark" in message and expected in message, message


def test_numbers(tmp_path):
    def depth(value: object) -> dict:
        return {"set_b": [set_b_row("B01", true_depth_in=value)]}

    five = refusal(tmp_path / "five", "set_b.jsonl", **depth(Decimal("11.12345")))
    assert "true_depth_in" in five and "decimal places" in five
    four = load(tmp_path / "four", **depth(Decimal("11.1234"))).set_b[0].true_depth_in
    assert four == Decimal("11.1234")
    ten = load(tmp_path / "integer", **depth(10)).set_b[0].true_depth_in
    assert isinstance(ten, Decimal) and ten == Decimal(10)
    for case, value in {"boolean": True, "text": "11.25", "null": None}.items():
        assert "true_depth_in" in refusal(
            tmp_path / case, "set_b.jsonl", **depth(value)
        )
    constants = {"nan": float("nan"), "infinity": float("inf"), "minus": float("-inf")}
    for case, value in constants.items():
        latency = [{"test_id": "L01", "seconds": value}]
        assert "NaN" in refusal(tmp_path / case, "latency.jsonl", latency=latency)
    for case, value in {"fraction": 1.0, "boolean_wheel": True}.items():
        rows = [set_b_row("B01", value)]
        assert "wheel" in refusal(tmp_path / case, "set_b.jsonl", set_b=rows)
    fractional = {**level("knee"), "basis": {"vehicles": 1.0, "people": 0}}
    rows = [set_a_row("A001", landmark=fractional)]
    assert "basis.vehicles" in refusal(tmp_path / "basis", "set_a.jsonl", set_a=rows)


def test_synthetic_flag(tmp_path):
    run = load(tmp_path / "flagged", run_json(synthetic=True))
    assert run.synthetic is True and run.meta["synthetic"] is True
    words = run_json(synthetic="yes")
    assert "synthetic" in refusal(tmp_path / "in_words", "run.json", 0, words)


def test_replay_and_baseline_fields(tmp_path):
    replayed = {
        "landmark": level("knee"),
        "geometry": level("knee"),
        "landmark" + REPLAY_SUFFIX: level("waist"),
    }
    run = load(tmp_path / "development", set_a=[set_a_row("A001", outcomes=replayed)])
    # A replay result carries its landmark too.
    waist = Result("done", None, False, "waist", False, "NPATV", "hub")
    assert run.set_a[0].results["landmark_replay"] == waist
    final = {
        "set_a": [set_a_row("A001", outcomes=replayed)],
        "a_neg": [a_neg_row("N001")],
    }
    assert "replay" in refusal(tmp_path / "final", "set_a.jsonl", 1, sealed(), **final)
    dropped = run_json(
        geometry_default="dropped", geometry_dropped_reason="it missed the gate"
    )
    orphan = [
        set_a_row(
            "A001", outcomes={"landmark": level("knee"), "geometry_replay": nfs()}
        )
    ]
    assert "replay" in refusal(
        tmp_path / "orphan", "set_a.jsonl", 1, dropped, set_a=orphan
    )
    # The frozen baseline (C424).
    no_level = without(sealed(), "baseline_level")
    assert "baseline_level" in refusal(tmp_path / "no_level", "run.json", 0, no_level)
    ankle = sealed(baseline_level="ankle")
    assert "baseline_level" in refusal(tmp_path / "ankle", "run.json", 0, ankle)
    lowercase = run_json(baseline_class="nplv")
    assert "baseline_class" in refusal(tmp_path / "lowercase", "run.json", 0, lowercase)
    half = without(run_json(), "baseline_class")
    assert "pair" in refusal(tmp_path / "half", "run.json", 0, half)
    run = load(
        tmp_path / "unfrozen",
        without(without(run_json(), "baseline_level"), "baseline_class"),
    )
    assert (run.baseline_level, run.baseline_class) == (None, None)


def test_unmarked_quality(tmp_path):
    run = load(
        tmp_path / "unmarked",
        set_a=[set_a_row("A001", quality=None)],
        a_neg=[a_neg_row("N001")],
    )
    assert run.set_a[0].quality is None
    assert (run.a_neg[0].quality, run.a_neg[0].subsets) == (None, ())
    rows = [set_a_row("A001", quality="unknown")]
    assert "quality" in refusal(tmp_path / "unknown", "set_a.jsonl", set_a=rows)


ECHOES = {
    "label": (
        "set_a.jsonl",
        {"set_a": [set_a_row("A001", label="Espana Maceda")]},
        "level_label_raw",
    ),
    "id": ("set_a.jsonl", {"set_a": [set_a_row("Espana")]}, "photo_id"),
    "field name": (
        "set_a.jsonl",
        {"set_a": [set_a_row("A001", Espana="x")]},
        "outside the contract",
    ),
    "refusal reason": (
        "set_a.jsonl",
        {"set_a": [set_a_row("A001", landmark=refused("Espana"))]},
        "refusalReason",
    ),
    "bin name": (
        "set_b.jsonl",
        {"set_b": [set_b_row("B01", bins={"Espana": "side"})]},
        "bins",
    ),
    "frozen value": (
        "run.json",
        {"run": run_json(frozen={"store": "Espana@x"})},
        "frozen",
    ),
}


@pytest.mark.parametrize(
    ("file", "sets", "rule"), list(ECHOES.values()), ids=list(ECHOES)
)
def test_errors_never_echo_values(tmp_path, file, sets, rule):
    message = refusal(tmp_path, file, 0 if file == "run.json" else 1, **sets)
    assert rule in message and "Espana" not in message, message


def test_self_check_controls_the_third_configuration(tmp_path):
    on = run_json(self_check="on")
    third = {
        "landmark": level("knee"),
        "geometry": level("knee"),
        "geometry_no_self_check": level("tire"),
    }
    run = load(tmp_path / "on", on, set_a=[set_a_row("A001", outcomes=third)])
    assert (
        run.self_check
        and run.set_a[0].results["geometry_no_self_check"].level == "tire"
    )
    message = refusal(
        tmp_path / "missing", "set_a.jsonl", 1, on, set_a=[set_a_row("A001")]
    )
    assert "geometry_no_self_check" in message
    off = [set_a_row("A001", outcomes=third)]
    message = refusal(
        tmp_path / "off", "set_a.jsonl", 1, run_json(self_check="off"), set_a=off
    )
    assert "geometry_no_self_check" in message
    # Set B's variant follows the same switch.
    estimates = {"geometry": measured(), "geometry_no_self_check": measured()}
    rows = [set_b_row("B01", estimates=estimates)]
    assert "geometry_no_self_check" in refusal(
        tmp_path / "set_b", "set_b.jsonl", set_b=rows
    )


def test_geometry_dropped(tmp_path):
    dropped = run_json(
        geometry_default="dropped", geometry_dropped_reason="median error over 3 in"
    )
    landmark_only = {"landmark": level("knee")}
    run = load(
        tmp_path / "dropped",
        dropped,
        set_a=[set_a_row("A001", outcomes=landmark_only)],
        a_neg=[a_neg_row("N001", outcomes={"landmark": nfs()})],
    )
    assert run.geometry_dropped and list(run.set_a[0].results) == ["landmark"]
    # With geometry dropped, its no-self-check twin goes too.
    both = {**dropped, "self_check": "on"}
    run = load(
        tmp_path / "self_check_on",
        both,
        set_a=[set_a_row("A001", outcomes=landmark_only)],
    )
    assert list(run.set_a[0].results) == ["landmark"]
    rows = [set_a_row("A001")]
    assert "geometry" in refusal(
        tmp_path / "with_geometry", "set_a.jsonl", 1, dropped, set_a=rows
    )
    no_reason = without(dropped, "geometry_dropped_reason")
    assert "geometry_dropped_reason" in refusal(
        tmp_path / "no_reason", "run.json", 0, no_reason
    )
    stray = run_json(geometry_dropped_reason="never dropped")
    assert "geometry_dropped_reason" in refusal(
        tmp_path / "stray", "run.json", 0, stray
    )


def test_rules_version(tmp_path):
    missing = without(sealed(), "rules_version")
    assert "rules_version" in refusal(tmp_path / "missing", "run.json", 0, missing)
    old = sealed(rules_version="0.5")
    assert "rules_version" in refusal(tmp_path / "old", "run.json", 0, old)
    old_development = run_json(rules_version="0.5")
    assert "rules_version" in refusal(
        tmp_path / "old_development", "run.json", 0, old_development
    )
    assert (
        load(tmp_path / "development", without(run_json(), "rules_version")).kind
        == "development"
    )


def test_sealed_run_needs_set_a_and_a_neg(tmp_path):
    rows = [set_a_row("A001")]
    message = refusal(tmp_path / "no_a_neg", "a_neg.jsonl", 0, sealed(), set_a=rows)
    assert "sealed" in message
    run = load(tmp_path / "final", sealed(), set_a=rows, a_neg=[a_neg_row("N001")])
    assert run.kind == "sealed"
    run = load(tmp_path / "development")
    assert (run.set_a, run.a_neg, run.set_b, run.set_d, run.latency) == (None,) * 5
    (tmp_path / "empty").mkdir()
    assert message_for(tmp_path / "empty").startswith("run.json:0: ")


def test_bom_and_crlf_are_tolerated(tmp_path):
    sets = {
        "set_a": [set_a_row("A001"), set_a_row("A002", label="waist deep")],
        "a_neg": [a_neg_row("N001")],
        "set_b": [set_b_row("B01")],
        "latency": [{"test_id": "L01", "seconds": 40}],
    }
    plain = load(tmp_path / "plain", **sets)
    windows = write_run(tmp_path / "windows", run=run_json(), **sets)
    for path in windows.iterdir():
        # A byte-order mark, \r\n endings, and a blank line after every line.
        text = path.read_bytes().replace(b"\n", b"\r\n\r\n")
        path.write_bytes(b"\xef\xbb\xbf" + text + b"\r\n")
    assert load_run(windows) == plain


def test_m8_join(tmp_path):
    labels = [
        m8(3, "wheel", "hub"),
        m8(4, "wheel", "rim_top"),  # a box the answer lacks
        m8(1, "wheel", "hub"),  # box 1 is a vehicle in the answer, not a wheel
        m8(None, "person", "knee"),  # its point matched no box
        m8(1, "vehicle", "door_sill", "suv_mpv"),
        m8(2, "person", "mid_thigh"),
    ]
    spark = answer(
        vehicles=[vehicle(1, "sedan_hatch", "bumper")],
        wheels=[wheel(3, "rim_quarter")],
        people=[person(2, "waist")],
    )
    run = load(
        tmp_path,
        set_a=[
            set_a_row("A001", m8=labels, answer=spark),
            set_a_row("A002", m8=labels[:1], answer=None),
        ],
    )
    assert run.set_a[0].references == (
        Reference(3, "wheel", "hub", None, "rim_quarter", None),
        Reference(4, "wheel", "rim_top", None, None, None),
        Reference(1, "wheel", "hub", None, None, None),
        Reference(None, "person", "knee", None, None, None),
        Reference(1, "body", "door_sill", "suv_mpv", "bumper", "sedan_hatch"),
        Reference(2, "person", "mid_thigh", None, "waist", None),
    )
    unanswered = run.set_a[1]
    assert not unanswered.answered
    assert unanswered.references == (Reference(3, "wheel", "hub", None, None, None),)


def test_set_b_estimates(tmp_path):
    refused_estimates = {
        "measured_without_point": {"geometry": without(measured(), "depthInPoint")},
        "measured_with_a_null": {"geometry": {**measured(), "depthInMin": None}},
        "measured_with_a_fail": {"geometry": {**measured(), "fail": "no_waterline"}},
        "unmeasured_with_numbers": {
            "geometry": {**unmeasured(), "depthInPoint": Decimal(11)}
        },
        "unmeasured_without_fail": {"geometry": {**unmeasured(), "fail": None}},
        "without_geometry": {"known_waterline": measured()},
        "unknown_variant": {"geometry": measured(), "geometry_k2": measured()},
    }
    for case, estimates in refused_estimates.items():
        rows = [set_b_row("B01", estimates=estimates)]
        assert "estimates" in refusal(tmp_path / case, "set_b.jsonl", set_b=rows)
    second = {"geometry": measured(), "known_waterline": measured()}
    differ = [set_b_row("B01", 1), set_b_row("B01", 2, estimates=second)]
    assert "variants" in refusal(tmp_path / "differ", "set_b.jsonl", 2, set_b=differ)
    every = {name: measured() for name in SET_B_VARIANTS}
    every["known_waterline_uncalibrated"] = unmeasured()
    run = load(
        tmp_path / "every",
        run_json(self_check="on"),
        set_b=[
            set_b_row("B01", 1, estimates=every),
            set_b_row("B01", 2, estimates=every),
        ],
        set_d=[set_b_row("D01", estimates=every)],
    )
    assert set(run.set_b[0].estimates) == set(SET_B_VARIANTS)
    unread = Estimate(False, None, None, None, "no_waterline")
    assert run.set_b[1].estimates["known_waterline_uncalibrated"] == unread
    assert run.set_d[0].estimates["geometry"] == run.set_b[0].estimates["geometry"]


def test_load_run_refuses_sealed_first(tmp_path):
    # C411: refused by its name, before anything is read, listed or created.
    with pytest.raises(SealedPath):
        load_run(tmp_path / "sealed")
    assert not any(tmp_path.iterdir())


RUN_JSON = {
    "not an object": ([], "object"),
    "unknown key": (run_json(notes="first try"), "outside the contract"),
    "kind": (run_json(kind="final"), "kind"),
    "date format": (run_json(date="30-10-2026"), "date"),
    "impossible date": (run_json(date="2026-02-30"), "date"),
    "freeze_commit in capitals": (run_json(freeze_commit="AB" * 20), "freeze_commit"),
    "short freeze_commit": (run_json(freeze_commit="ab" * 10), "freeze_commit"),
    "frozen link": (run_json(frozen={"prompt": "see http://x"}), "frozen"),
    "frozen at sign": (run_json(frozen={"store": "a@b"}), "frozen"),
    "frozen long value": (run_json(frozen={"prompt": "x" * 81}), "frozen"),
    "frozen name": (run_json(frozen={"SAM phrases": "flood water"}), "frozen"),
    "frozen number": (run_json(frozen={"k": Decimal("1.1")}), "frozen"),
    "unknown dataset": (
        run_json(datasets={"set_c": {"version": "v1", "split_seed": "7"}}),
        "datasets",
    ),
    "dataset field": (
        run_json(
            datasets={"set_a": {"version": "v1", "split_seed": "7", "source": "x"}}
        ),
        "datasets.set_a",
    ),
    "dataset without a seed": (
        run_json(datasets={"set_a": {"version": "v1"}}),
        "split_seed",
    ),
    "stop field": (
        run_json(
            stops=[{"at": "21:10", "cause": "alert", "resumed": "21:40", "by": "x"}]
        ),
        "stops[0]",
    ),
    "self_check": (run_json(self_check="yes"), "self_check"),
    "self_check_decided link": (
        run_json(self_check_decided="see http://x"),
        "self_check_decided",
    ),
    "geometry_default": (run_json(geometry_default="maybe"), "geometry_default"),
    "development without frozen": (without(run_json(), "frozen"), "frozen"),
    "sealed without freeze_commit": (
        without(sealed(), "freeze_commit"),
        "freeze_commit",
    ),
    "sealed without geometry_default": (
        without(sealed(), "geometry_default"),
        "geometry_default",
    ),
}


@pytest.mark.parametrize(("run", "rule"), list(RUN_JSON.values()), ids=list(RUN_JSON))
def test_run_json_contract(tmp_path, run, rule):
    assert rule in refusal(tmp_path, "run.json", 0, run)


def test_short_strings_and_the_rerun_reason(tmp_path):
    longest = run_json(
        frozen={"prompt": "x" * 80, "phrases": "flood water, puddle (backup)"}
    )
    assert load(tmp_path / "longest", longest).meta["frozen"]["prompt"] == "x" * 80
    reason = "fix 3 changed the depth output"
    sets = {"set_a": [set_a_row("A001")], "a_neg": [a_neg_row("N001")]}
    assert (
        load(tmp_path / "rerun", sealed(rerun_reason=reason), **sets).rerun_reason
        == reason
    )
    first = sealed(rerun_reason=reason)
    assert "rerun_reason" in refusal(tmp_path / "first", "run.json", 0, first, **sets)
    unexplained = tmp_path / "again" / "rerun"
    assert "rerun_reason" in refusal(unexplained, "run.json", 0, sealed(), **sets)


OWN_FIELDS = {
    "A-neg with a label": (
        "a_neg",
        a_neg_row("N001", level_label_raw="knee deep"),
        "outside",
    ),
    "A-neg with M8": ("a_neg", a_neg_row("N001", m8=[]), "outside"),
    "A-neg without surface": (
        "a_neg",
        without(a_neg_row("N001"), "surface"),
        "surface",
    ),
    "A-neg surface": ("a_neg", a_neg_row("N001", surface="damp"), "surface"),
    "A-neg match": ("a_neg", a_neg_row("N001", match="none"), "match"),
    "Set A without M8": ("set_a", without(set_a_row("A001"), "m8"), "m8"),
    "Set A with surface": ("set_a", set_a_row("A001", surface="wet"), "outside"),
    "Set A without a match": ("set_a", set_a_row("A001", match=None), "match"),
    "poster_kind": ("set_a", set_a_row("A001", poster_kind="news"), "poster_kind"),
    "label_in_image": (
        "set_a",
        set_a_row("A001", label_in_image="partly"),
        "label_in_image",
    ),
    "boolean in words": ("set_a", set_a_row("A001", duplicate="false"), "duplicate"),
    "boolean as a number": ("set_a", set_a_row("A001", decodes=1), "decodes"),
    "Set B field": ("set_b", set_b_row("B01", note="x"), "outside"),
    "wheel 3": ("set_b", set_b_row("B01", 3), "wheel"),
    "vehicle_type": ("set_b", set_b_row("B01", vehicle_type="car"), "vehicle_type"),
    "tire_code": ("set_b", set_b_row("B01", tire_code="185/65 R15"), "tire_code"),
    "true_depth_in of 100": (
        "set_b",
        set_b_row("B01", true_depth_in=100),
        "true_depth_in",
    ),
    "negative true_depth_in": (
        "set_b",
        set_b_row("B01", true_depth_in=Decimal("-0.5")),
        "true_depth_in",
    ),
    "sam_water_found": (
        "set_b",
        set_b_row("B01", sam_water_found="yes"),
        "sam_water_found",
    ),
    "Set D field": ("set_d", set_b_row("D01", ruler="x"), "outside"),
    "latency field": (
        "latency",
        {"test_id": "L01", "seconds": 40, "phone": "x"},
        "outside",
    ),
    "no seconds": ("latency", {"test_id": "L01", "seconds": 0}, "seconds"),
    "an hour": ("latency", {"test_id": "L01", "seconds": 3600}, "seconds"),
}


@pytest.mark.parametrize(
    ("name", "row", "rule"), list(OWN_FIELDS.values()), ids=list(OWN_FIELDS)
)
def test_each_file_keeps_its_own_fields(tmp_path, name, row, rule):
    assert rule in refusal(tmp_path, f"{name}.jsonl", **{name: [row]})


ANSWERS_AND_LABELS = {
    "wake_visible in words": {
        "answer": answer(
            vehicles=[{**vehicle(1, "van", "bumper"), "wake_visible": "no"}]
        )
    },
    "id as text": {"answer": answer(wheels=[wheel("1", "hub")])},
    "photo_usable unsure": {"answer": {**answer(), "photo_usable": "unsure"}},
    "answer without people": {"answer": without(answer(), "people")},
    "unknown vehicle type": {"answer": answer(vehicles=[vehicle(1, "car", "bumper")])},
    "M8 kind": {"m8": [m8(1, "car", None)]},
    "M8 wheel with a type": {"m8": [m8(1, "wheel", "hub", "van")]},
    "M8 vehicle without a type": {"m8": [m8(1, "vehicle", "bumper")]},
    "M8 wheel at a body waterline": {"m8": [m8(1, "wheel", "bumper")]},
    "M8 box id as text": {"m8": [m8("1", "wheel", "hub")]},
    "wheel_inches field": {
        "wheel_inches": [{"box_id": 1, "depthInMin": 10, "depthInMax": 12, "wheel": 1}]
    },
    "wheel_inches without a box": {
        "wheel_inches": [{"box_id": None, "depthInMin": 10, "depthInMax": 12}]
    },
}


@pytest.mark.parametrize(
    "fields", list(ANSWERS_AND_LABELS.values()), ids=list(ANSWERS_AND_LABELS)
)
def test_answer_m8_and_wheel_inches_values(tmp_path, fields):
    (field,) = fields
    assert field in refusal(
        tmp_path, "set_a.jsonl", set_a=[set_a_row("A001", **fields)]
    )


def test_each_line_is_one_json_object(tmp_path):
    good = json.dumps(set_a_row("A001"))
    lines = {
        "not_json": "{photo_id: A001}",
        "a_list": "[]",
        "repeated_key": good.replace("{", '{"event_id": "E02", ', 1),
        "two_objects": f"{good} {good}",
    }
    for case, line in lines.items():
        folder = write_run(tmp_path / case, run=run_json())
        # A blank first line still counts, so the row is line 2.
        (folder / "set_a.jsonl").write_bytes(f"\n{line}\n".encode())
        assert message_for(folder).startswith("set_a.jsonl:2: "), case
    folder = write_run(tmp_path / "utf_16", run=run_json())
    (folder / "set_a.jsonl").write_bytes(good.encode("utf-16"))
    assert message_for(folder).startswith("set_a.jsonl:0: ")
