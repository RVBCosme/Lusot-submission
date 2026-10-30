"""Tests for the export's path-free functions, lusot_analysis.export (C315, C327).

Runs are recorded with the offline runner's live() and a FakeClient, so no Meta call
is made, and replayed from their folders in tmp_path. The parsers take CSV text, as
the sealed-run entry point hands them (Task 19). The row and run.json names are MS6's,
as its loader on Window 4's branch checks them (eval/scoring/rows.py).
"""

import ast
import copy
import dataclasses
import importlib.util
import json
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from fakes import (
    REPO_PROMPTS,
    FakeClient,
    answer,
    geometry_case,
    person,
    vehicle,
    wheel,
)

from lusot_analysis import export
from lusot_analysis.pipeline import READING_PHRASES
from lusot_analysis.pipeline.evidence import Evidence, EvidenceEntry
from lusot_analysis.pipeline.references import validate_answer
from lusot_analysis.pipeline.types import Outcome
from lusot_analysis.prompts import load_prompt
from lusot_analysis.tuning import START, Tuning

ANALYSIS = Path(__file__).parents[1]
REPO = Path(__file__).parents[3]
EVAL = REPO / "eval"
RUNNER = ANALYSIS / "probes" / "run_pipeline.py"
REASON = "REASON-MARKER-31"  # the reason fakes.answer gives every answer

# The harness's `--label-words`, as printed on Window 4's branch at 1cafc88 (Oct 30):
# the patched list for the parity check that needs no harness in the tree.
WORDS = frozenset(
    {
        "above",
        "all",
        "and",
        "ankle",
        "any",
        "cars",
        "centimeter",
        "centimeters",
        "centimetre",
        "centimetres",
        "chest",
        "cm",
        "deep",
        "gutter",
        "half",
        "head",
        "in",
        "inch",
        "inches",
        "knee",
        "lagpas",
        "level",
        "light",
        "motorcycles",
        "not",
        "npatv",
        "nplv",
        "of",
        "passable",
        "patv",
        "sedan",
        "subsided",
        "tao",
        "tire",
        "to",
        "types",
        "vehicle",
        "vehicles",
        "waist",
    }
)
# Review Focus 8's table (C327; P1): each label, and whether it stays as written.
LABELS = [
    ("Knee deep.", True),
    ("9in", True),
    ("8.25 cm", True),
    ("Head+ (60+ inches)", True),
    ("10/28", True),
    ("ANKLE DEEP (9 inches)", True),
    ("Not passable to light vehicles (NPLV)", True),
    ("", True),
    ("(other words)", True),
    ("knee deep near the market", False),
    ("8:00 AM", False),
    ("1234 in", False),
    ("8.255 cm", False),
]

# A Set A and an A-neg manifest row, as MS2's manifest.csv holds them (its §5.9),
# with the columns bridge_base reads and some it must leave out.
MANIFEST = (
    "photo_id,set,split,event_id,city,spot_key,poster_kind,match,level_label_raw,"
    "passability_raw,other_alerts_raw,label_in_image,surface,duplicate,duplicate_of,"
    "decodes,metro_manila,photo_file,notes\n"
    "A001,A,dev,E01,CITY-MARKER,SPOT-MARKER,mmda,same_post,Knee deep.,NPLV,"
    "Half tire;knee deep near the market,no,,yes,A000,yes,yes,A001.jpg,NOTE-MARKER\n"
    "N001,A-neg,dev,E02,CITY-MARKER,SPOT-MARKER,other,,none,,,no,wet,no,,no,no,"
    "N001.jpg,NOTE-MARKER\n"
)
M8 = (
    "photo_id,ref_id,kind,x,y,vehicle_type,body_waterline,waterline,quality,subsets\n"
    "A001,P1,photo,,,,,,dark,reflection;splash\n"
    "A001,R1,wheel,0.5,0.45,,,hub,,\n"
    "A001,R2,vehicle,0.5,0.3,van,door_sill,,,\n"
)
# MS6's §4.3 base fields of a Set A row and an A-neg row (its rows.py).
SET_A_BASE = {
    "photo_id",
    "event_id",
    "level_label_raw",
    "passability_raw",
    "other_alerts_raw",
    "poster_kind",
    "label_in_image",
    "match",
    "duplicate",
    "metro_manila",
    "decodes",
    "quality",
    "subsets",
}
A_NEG_BASE = SET_A_BASE - {
    "level_label_raw",
    "passability_raw",
    "other_alerts_raw",
} | {"surface"}


def load_runner():
    spec = importlib.util.spec_from_file_location("run_pipeline_script", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_runner()


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture(scope="module")
def prompt():
    return load_prompt(REPO_PROMPTS)


def no_client():
    raise AssertionError("a Meta client was built")


def recorded(tmp_path, monkeypatch, case):
    """`case`'s photo, recorded live through a FakeClient with START (R128), and
    returned as (photo bytes, run folder)."""
    data, sam, given = case()
    monkeypatch.setattr(runner, "make_client", lambda: FakeClient(sam, given))
    photo = tmp_path / "A001.jpg"
    photo.write_bytes(data)
    run_dir, _ = runner.live(photo, tmp_path, run_dir=tmp_path / "run", tuning=START)
    monkeypatch.setattr(runner, "make_client", no_client)
    return data, run_dir


def places(number: float) -> int:
    """How many decimal places a number's JSON form carries."""
    return max(0, -Decimal(repr(number)).as_tuple().exponent)


def test_answer_without_reason(prompt):
    given = answer(vehicles=[vehicle(1)], wheels=[wheel(2, "hub")])
    kept = export.answer_without_reason(given, prompt.schema)
    assert kept == {key: value for key, value in given.items() if key != "reason"}
    assert "reason" in given  # the answer given is left as it was
    assert export.answer_without_reason(None, prompt.schema) is None
    # P13: an answer that fails the schema gives None, as MS6's allow-list would
    # refuse its row.
    bad = {**given, "photo_usable": "maybe"}
    assert export.answer_without_reason(bad, prompt.schema) is None
    assert export.answer_without_reason(["not", "an", "object"], prompt.schema) is None


# R152: answers that pass the schema, but whose ids MS6's loader refuses, which would
# make it refuse the whole file.
LOADER_REFUSES = {
    # Draft 2020-12 counts 2.0 as an integer; the loader wants an int.
    "float-id": {"wheels": [{"id": 2.0, "waterline": "hub"}]},
    "negative-id": {"wheels": [wheel(-1, "hub")]},
    "id-above-9999": {"vehicles": [vehicle(10000)]},
    "id-repeated-in-a-list": {"wheels": [wheel(2, "hub"), wheel(2, "rim_top")]},
}


@pytest.mark.parametrize("lists", LOADER_REFUSES.values(), ids=LOADER_REFUSES)
def test_answers_the_loader_would_refuse_are_withheld(prompt, lists):
    given = answer(**lists)
    validate_answer(given, prompt.schema)  # the schema passes each one
    kept = copy.deepcopy(given)
    assert not export.loader_takes_ids(given)
    assert export.answer_without_reason(given, prompt.schema) is None
    # photo_row withholds it too, for a caller that hands it the answer itself.
    base = export.bridge_base(export.parse_manifest(MANIFEST)[0], [], words=WORDS)
    assert export.photo_row(base, {}, given)["answer"] is None
    assert given == kept  # the model's answer is never edited


def test_ids_the_loader_takes_are_kept(prompt):
    # An id may repeat across lists, and 0 and 9999 are in range.
    given = answer(
        vehicles=[vehicle(0), vehicle(9999)],
        wheels=[wheel(0, "hub")],
        people=[person(9999, "knee")],
    )
    assert export.loader_takes_ids(given)
    assert export.answer_without_reason(given, prompt.schema)["wheels"] == [
        wheel(0, "hub")
    ]


def test_saved_row_reads_the_run_as_saved(tmp_path, monkeypatch, prompt):
    # Task 19's path: the row from spark.json's and run.json's content, path-free.
    data, run_dir = recorded(tmp_path, monkeypatch, lambda: geometry_case("van"))
    runs = export.replay_configurations(data, run_dir, prompt, tuning=START)
    spark = json.loads((run_dir / "spark.json").read_text(encoding="utf-8"))
    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    labels = export.parse_m8(M8)["A001"]
    base = export.bridge_base(export.parse_manifest(MANIFEST)[0], labels, words=WORDS)
    row = export.saved_row(base, runs, spark, record, prompt.schema, labels=labels)
    assert row["answer"] == export.answer_without_reason(spark["data"], prompt.schema)
    assert [entry["box_id"] for entry in row["m8"]] == [2, 1]  # wheel 2, vehicle 1
    assert [inches["box_id"] for inches in row["wheel_inches"]] == [2]
    # No spark.json, or a saved refusal, gives no answer.
    assert export.saved_row(base, runs, None, record, prompt.schema)["answer"] is None
    refused = export.saved_row(base, runs, {"refused": True}, record, prompt.schema)
    assert refused["answer"] is None
    # A saved answer the loader would refuse is withheld (R152).
    spark["data"]["wheels"] *= 2
    assert export.saved_row(base, runs, spark, record, prompt.schema)["answer"] is None


def test_photo_row_has_both_configurations(tmp_path, monkeypatch, prompt):
    data, run_dir = recorded(tmp_path, monkeypatch, lambda: geometry_case("van"))
    runs = export.replay_configurations(data, run_dir, prompt, tuning=START)
    assert list(runs) == ["landmark", "geometry"]
    saved = json.loads((run_dir / "spark.json").read_text(encoding="utf-8"))
    given = export.answer_without_reason(saved["data"], prompt.schema)
    (manifest_row, _) = export.parse_manifest(MANIFEST)
    m8 = export.parse_m8(M8)["A001"]
    base = export.bridge_base(manifest_row, m8, words=WORDS)
    row = export.photo_row({**manifest_row, **base}, runs, given)

    outcomes = row["outcomes"]
    assert list(outcomes) == ["landmark", "geometry"]
    # Off, a van is dropped by its type (C309); on, geometry alone reads its wheel.
    assert outcomes["landmark"] == Outcome.refused("no_usable_reference").item_fields()
    geometry = outcomes["geometry"]
    assert (geometry["level"], geometry["levelFrom"]) == ("half_knee", "geometry")
    # As the item stores them, rounded outward (C308). The van's two codes give the
    # Tamaraw's depth as the min and the Hiace's as the max (M11).
    assert (geometry["depthInMin"], geometry["depthInMax"]) == (9.4, 9.9)
    # Unrounded, to 4 decimal places (C327; finding 2), as MS6's list by box id.
    (inches,) = row["wheel_inches"]
    assert inches["box_id"] == 2
    assert inches["depthInMin"] == pytest.approx(9.464, abs=0.02)
    assert inches["depthInMax"] == pytest.approx(9.887, abs=0.02)
    assert places(inches["depthInMin"]) <= 4
    assert places(inches["depthInMax"]) <= 4

    assert "reason" not in row["answer"]
    assert row["answer"]["wheels"] == [{"id": 2, "waterline": "rim_quarter"}]
    for key in SET_A_BASE:
        assert row[key] == base[key]
    for key in ("photo_file", "notes", "city", "spot_key", "set", "split"):
        assert key not in row
    assert set(row) == SET_A_BASE | {"outcomes", "answer", "wheel_inches", "m8"}
    assert row["m8"] == []  # a Set A row always carries its m8 list
    # An A-neg row keeps A-neg's fields only, with no labels and no m8.
    a_neg = export.bridge_base(export.parse_manifest(MANIFEST)[1], [], words=WORDS)
    stray = {**a_neg, "photo_file": "N001.jpg", "notes": "NOTE-MARKER"}
    assert set(export.photo_row(stray, runs, given)) == A_NEG_BASE | {
        "outcomes",
        "answer",
        "wheel_inches",
    }
    # photo_row drops a reason it is handed, too (C62).
    assert "reason" not in export.photo_row(base, runs, saved["data"])["answer"]


def entry(id: int, kind: str, box: tuple[int, int, int, int]) -> EvidenceEntry:
    """A numbered box's evidence entry, with nothing found for it."""
    return EvidenceEntry(
        id=id,
        kind=kind,
        box=box,
        outline=(),
        landmark=None,
        level=None,
        level_from=None,
        inches=None,
        rim=None,
        waterline=None,
        used=False,
        deciding=False,
        dropped=None,
    )


def label(kind: str, x: float, y: float, **values: str) -> dict:
    """One M8 reference row, its other cells blank, as parse_m8 gives it."""
    blank = dict.fromkeys(
        ("vehicle_type", "body_waterline", "waterline", "quality", "subsets"), ""
    )
    return {
        "photo_id": "A001",
        "ref_id": "R1",
        "kind": kind,
        "x": str(x),
        "y": str(y),
        **blank,
        **values,
    }


def test_m8_points_join_boxes():
    # C327, MS6's C415, MS2's C208: a point, scaled to the sent image, goes to the
    # numbered box of its kind that holds it, edges included.
    evidence = Evidence(
        (
            entry(1, "body", (100, 100, 400, 300)),
            entry(2, "wheel", (150, 250, 200, 300)),
            entry(3, "person", (500, 100, 560, 300)),
            entry(4, "person", (520, 100, 600, 300)),
            entry(5, "wheel", (300, 250, 350, 300)),
        ),
        (),
    )
    size = (640, 480)
    labels = [
        # A wheel's hub inside wheel 2's box. Vehicle 1's box holds it too, but a
        # wheel's point goes to a wheel box only.
        label("wheel", 175 / 640, 275 / 480, waterline="hub"),
        # Inside both person boxes: person 4's centre (560, 200) is nearer than
        # person 3's (530, 200).
        label("person", 550 / 640, 200 / 480, waterline="knee"),
        # In no wheel box: null.
        label("wheel", 0.01, 0.01, waterline="rim_top"),
        # A vehicle's point goes to the vehicle's box, with its type.
        label(
            "vehicle",
            0.5,
            0.5,
            vehicle_type="sedan_hatch",
            body_waterline="door_sill",
        ),
        # On wheel 5's right edge, x = 350: edges are included.
        label("wheel", 350 / 640, 260 / 480, waterline="tire_only"),
        # A wheel M8 left unmarked keeps a null landmark.
        label("wheel", 175 / 640, 260 / 480),
    ]
    photo_row = label("photo", 0, 0, quality="ok")  # the photo row is no reference
    assert export.m8_boxes([photo_row, *labels], evidence, size) == [
        {"box_id": 2, "kind": "wheel", "landmark": "hub", "vehicle_type": None},
        {"box_id": 4, "kind": "person", "landmark": "knee", "vehicle_type": None},
        {"box_id": None, "kind": "wheel", "landmark": "rim_top", "vehicle_type": None},
        {
            "box_id": 1,
            "kind": "vehicle",
            "landmark": "door_sill",
            "vehicle_type": "sedan_hatch",
        },
        {"box_id": 5, "kind": "wheel", "landmark": "tire_only", "vehicle_type": None},
        {"box_id": 2, "kind": "wheel", "landmark": None, "vehicle_type": None},
    ]
    # With no evidence record, as on a failed run, every box id is null.
    assert [found["box_id"] for found in export.m8_boxes(labels, None, size)] == [
        None
    ] * len(labels)


def test_labels_match_a_patched_word_list():
    # Review Focus 8 (C327; P1), the half that needs no harness: the shared table
    # through label_or_marker alone, with a patched --label-words list.
    for text, stays in LABELS:
        expected = text if stays else export.OTHER_WORDS
        assert export.label_or_marker(text, WORDS) == expected, text
    # An other_alerts_raw entry is handled the same way. Its blank entry is dropped,
    # as MS2's intake drops blank list entries.
    texts = [text for text, _ in LABELS]
    row = {
        **export.parse_manifest(MANIFEST)[0],
        "level_label_raw": "",
        "other_alerts_raw": ";".join(texts),
    }
    bridged = export.bridge_base(row, [], words=WORDS)["other_alerts_raw"]
    assert bridged == [export.label_or_marker(t, WORDS) for t in texts if t.strip()]


def test_labels_match_the_harness():
    # Review Focus 8 (C327; P1): the same table through the harness's own
    # label_words_ok, in a subprocess that loads scoring.labels from eval/, so
    # backend/analysis never imports it (C321), with the words its --label-words
    # prints. Both must give the same verdict on every row.
    if not (EVAL / "scoring" / "labels.py").is_file():
        pytest.skip("eval/scoring/labels.py isn't in the tree: MS6 hasn't merged")
    texts = [text for text, _ in LABELS]
    printed = subprocess.run(
        [sys.executable, "-I", "-B", str(EVAL / "run_eval.py"), "--label-words"],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout
    words = frozenset(printed.split())
    code = (
        "import json, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from scoring.labels import label_words_ok\n"
        "labels = json.loads(sys.stdin.read())\n"
        "print(json.dumps([label_words_ok(text) for text in labels]))\n"
    )
    verdicts = json.loads(
        subprocess.run(
            [sys.executable, "-I", "-B", "-c", code, str(EVAL)],
            input=json.dumps(texts),
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        ).stdout
    )
    for text, ok in zip(texts, verdicts, strict=True):
        assert (export.label_or_marker(text, words) == text) is ok, text
    assert verdicts == [stays for _, stays in LABELS]


@pytest.mark.parametrize(
    ("row", "column"),
    [
        ("../x,C,c1.jpg", "photo_id"),
        ("C001,A/B,c1.jpg", "set"),
        ("C001,C,sub\\p.jpg", "photo_file"),
        ("C001,C,C:p.jpg", "photo_file"),
        ("C001,C,p.", "photo_file"),
        ("C001,C,a..b.jpg", "photo_file"),
    ],
)
def test_a_manifest_row_names_its_files_with_bare_names(row, column):
    # M6: no cell may lead a path out of the folder it is joined to, so the check
    # runs before any path is built, and the message names the row and the column but
    # never the cell's text.
    with pytest.raises(export.InputError) as raised:
        export.parse_manifest(f"photo_id,set,photo_file\n{row}\n")
    assert str(raised.value) == (
        f"manifest row 1: {column} must be one name, with no folder"
    )
    # A normal row still parses.
    text = "photo_id,set,photo_file\nA001,A-neg,p_01.jpg\n"
    assert export.parse_manifest(text) == [
        {"photo_id": "A001", "set": "A-neg", "photo_file": "p_01.jpg"}
    ]


def test_parsers_take_text_not_paths():
    # Task 19 reads the sealed files itself, after its own guard, and hands their
    # text to these: no path and no guard here.
    set_a, a_neg = export.parse_manifest(chr(0xFEFF) + MANIFEST)  # a BOM is dropped
    assert (set_a["photo_id"], a_neg["photo_id"]) == ("A001", "N001")
    m8 = export.parse_m8(M8)
    assert list(m8) == ["A001"]
    assert [found["ref_id"] for found in m8["A001"]] == ["P1", "R1", "R2"]

    base = export.bridge_base(set_a, m8["A001"], words=WORDS)
    assert base == {
        "photo_id": "A001",
        "event_id": "E01",
        "level_label_raw": "Knee deep.",
        "passability_raw": "NPLV",
        "other_alerts_raw": ["Half tire", export.OTHER_WORDS],
        "poster_kind": "mmda",
        "label_in_image": "no",
        "match": "same_post",
        "duplicate": True,
        "metro_manila": True,
        "decodes": True,
        "quality": "dark",
        "subsets": ["reflection", "splash"],
    }
    # A-neg: no labels, a null match, its surface, and no M8 (MS6's C423).
    assert export.bridge_base(a_neg, [], words=frozenset()) == {
        "photo_id": "N001",
        "event_id": "E02",
        "poster_kind": "other",
        "label_in_image": "no",
        "match": None,
        "duplicate": False,
        "metro_manila": False,
        "decodes": False,
        "quality": None,
        "subsets": [],
        "surface": "wet",
    }
    # A Set A photo without an M8 photo row has its marks unmade (C423).
    unmarked = export.bridge_base(set_a, [], words=WORDS)
    assert (unmarked["quality"], unmarked["subsets"]) == (None, [])
    # Tags are stripped and blanks dropped, as MS2's intake reads them.
    loose = [{**m8["A001"][0], "subsets": " reflection ; ;splash;"}]
    assert export.bridge_base(set_a, loose, words=WORDS)["subsets"] == [
        "reflection",
        "splash",
    ]

    # photo_id must be unique, and event_id is required on Set A rows only (P10).
    header, first, _ = MANIFEST.splitlines()
    with pytest.raises(export.InputError, match="photo_id repeats"):
        export.parse_manifest(f"{header}\n{first}\n{first}")
    no_event = first.replace(",E01,", ",,")
    with pytest.raises(export.InputError, match="event_id"):
        export.parse_manifest(f"{header}\n{no_event}")
    other = "photo_id,set,photo_file\nC001,C,c1.jpg\n"
    assert export.parse_manifest(other) == [
        {"photo_id": "C001", "set": "C", "photo_file": "c1.jpg"}
    ]
    with pytest.raises(export.InputError, match="photo_file"):
        export.parse_manifest("photo_id,set\nC001,C\n")
    # A cell's text never reaches an error's message.
    with pytest.raises(export.InputError) as raised:
        export.bridge_base({**set_a, "duplicate": "NOTE-MARKER"}, [], words=WORDS)
    assert "NOTE-MARKER" not in str(raised.value)

    saved_run = {
        "models": {"sam": "sam-3.1", "spark": "muse-spark-1.3"},
        "prompt_version": "muse_spark_photo_v1",
        "schema_name": "muse_spark_photo_v1",
        "blur_version": "blur-v",
        "phrases": list(READING_PHRASES),
    }
    common = {
        "date": "2026-11-03",
        "rules_version": "0.7",
        "tuning": START,
        "saved_run": saved_run,
        "geometry_default": "on",
        "dropped_reason": None,
        "datasets": {"set_a": {"version": "v1", "split_seed": "7"}},
    }
    commit = "0123456789abcdef" * 2 + "01234567"
    stops = [{"at": "A003", "cause": "key_rejected", "resumed": "2026-11-03 21:40"}]
    sealed = export.results_manifest(
        kind="sealed",
        freeze_commit=commit,
        baseline={"baseline_level": "knee", "baseline_class": "NPLV"},
        stops=stops,
        rerun_reason="fix_for_a_depth_output",
        self_check_decided="2026-10-31",
        service_retries=2,
        **common,
    )
    assert sealed["kind"] == "sealed"
    assert sealed["freeze_commit"] == commit
    assert (sealed["baseline_level"], sealed["baseline_class"]) == ("knee", "NPLV")
    assert sealed["stops"] == stops
    assert sealed["rerun_reason"] == "fix_for_a_depth_output"
    assert sealed["self_check_decided"] == "2026-10-31"
    assert sealed["service_retries"] == 2
    development = export.results_manifest(**common)
    assert development["kind"] == "development"
    for key in (
        "freeze_commit",
        "baseline_level",
        "baseline_class",
        "stops",
        "rerun_reason",
        "self_check_decided",
        "service_retries",
    ):
        assert key not in development
    assert {key: development[key] for key in ("self_check", "geometry_default")} == {
        "self_check": "off",
        "geometry_default": "on",
    }
    assert development["datasets"] == common["datasets"]
    # A sealed run.json without its freeze commit, baseline or the self-check's
    # decision would be refused by MS6's loader, so it is refused here first.
    with pytest.raises(ValueError, match="sealed"):
        export.results_manifest(kind="sealed", **common)
    with pytest.raises(ValueError, match="development"):
        export.results_manifest(freeze_commit=commit, **common)


def test_a_sealed_run_json_counts_its_service_retries():
    # MS6E-Q6: MS6's loader refuses a sealed run.json without service_retries, a
    # whole number of 0 or more, so it is refused here first; a development
    # run.json leaves it out.
    development = {
        "date": "2026-11-03",
        "rules_version": "0.6",
        "tuning": START,
        "saved_run": {
            "models": {"sam": "sam-3.1", "spark": "muse-spark-1.3"},
            "prompt_version": "muse_spark_photo_v1",
            "schema_name": "muse_spark_photo_v1",
            "blur_version": "blur-v",
            "phrases": list(READING_PHRASES),
        },
        "geometry_default": "on",
        "dropped_reason": None,
        "datasets": {"set_a": {"version": "v1", "split_seed": "7"}},
    }
    sealed = development | {
        "kind": "sealed",
        "freeze_commit": "0123456789abcdef" * 2 + "01234567",
        "baseline": {"baseline_level": "knee", "baseline_class": "NPLV"},
        "self_check_decided": "2026-10-31",
    }
    for count in (0, 1, 7):
        written = export.results_manifest(service_retries=count, **sealed)
        assert written["service_retries"] == count
        assert type(written["service_retries"]) is int
    with pytest.raises(ValueError, match="service_retries"):
        export.results_manifest(**sealed)
    for value in (None, -1, True, False, 1.0, "1"):
        with pytest.raises(ValueError, match="service_retries"):
            export.results_manifest(service_retries=value, **sealed)
    assert "service_retries" not in export.results_manifest(**development)
    with pytest.raises(ValueError, match="development"):
        export.results_manifest(service_retries=0, **development)


@pytest.mark.parametrize(
    "datasets",
    [
        ["set_a"],
        {"set_c": {"version": "v1", "split_seed": "7"}},
        {"set_a": {"version": "v1"}},
        {"set_a": {"version": "v1", "split_seed": "7", "note": "x"}},
        {"set_a": {"version": 1, "split_seed": "7"}},
        {"set_a": {"version": "see https://example.org", "split_seed": "7"}},
        {"set_a": {"version": "v" * 81, "split_seed": "7"}},
    ],
    ids=["list", "set-c", "no-seed", "extra", "number", "link", "long"],
)
def test_datasets_take_ms6s_shape(datasets):
    # MS6's rows.py: optional set_a, a_neg, set_b and set_d, each exactly version and
    # split_seed as short strings. Anything else is refused before run.json is made.
    with pytest.raises(export.InputError):
        export.check_datasets(datasets)
    export.check_datasets({})
    export.check_datasets(
        {name: {"version": "v1", "split_seed": "7"} for name in ("set_a", "set_d")}
    )


def test_frozen_records_every_numeric_cutoff():
    # R153: a `--set` candidate's run.json states its cutoffs (v0.7 item 10.1), each
    # numeric Tuning field under its own name, every name an MS6 token.
    saved_run = {
        "models": {"sam": "sam-3.1", "spark": "muse-spark-1.3"},
        "prompt_version": "muse_spark_photo_v1",
        "schema_name": "muse_spark_photo_v1",
        "blur_version": "blur-v",
        "phrases": list(READING_PHRASES),
    }
    tuning = dataclasses.replace(START, touch_tolerance_px=6.0, rim_edge_k=1.05)
    frozen = export.results_manifest(
        date="2026-10-30",
        rules_version="0.6",
        tuning=tuning,
        saved_run=saved_run,
        geometry_default="on",
        dropped_reason=None,
        datasets={},
    )["frozen"]
    numeric = [
        field.name
        for field in dataclasses.fields(Tuning)
        if field.name not in ("version", "reasoning_effort", "drawing", "untuned")
    ]
    assert len(numeric) == 13
    for name in numeric:
        assert frozen[name] == str(getattr(tuning, name))
    assert (frozen["touch_tolerance_px"], frozen["rim_edge_k"]) == ("6.0", "1.05")
    assert frozen["min_wheel_side_px"] == "40"
    for name, value in frozen.items():
        assert re.fullmatch("[a-z][a-z0-9_]{0,31}", name), name
        assert isinstance(value, str) and len(value) <= 80


def imported_modules(path: Path) -> list[str]:
    """Every module an import statement in `path` names."""
    names = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.append(node.module)
    return names


def test_no_import_crosses_into_eval():
    # C400; finding 8: backend/analysis meets MS6's harness through files and its
    # commands only. `scoring` is the harness's own package name inside eval/.
    files = [
        *(ANALYSIS / "src" / "lusot_analysis").rglob("*.py"),
        *(ANALYSIS / "probes").glob("*.py"),
    ]
    assert {"export.py", "dev_eval.py"} <= {path.name for path in files}
    for path in files:
        for name in imported_modules(path):
            assert name.split(".")[0] not in ("eval", "scoring"), path.name
