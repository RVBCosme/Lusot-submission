"""Tests for run_pipeline, the one pipeline function (spec §3.2, §3.4 and §3.6).

The Lambda's handler and the offline runner both call it (B3). Every test drives it
with FakeClient, so no Meta call is made.
"""

import dataclasses
import json

import pytest
from fakes import (
    REPO_PROMPTS,
    FakeClient,
    answer,
    around,
    flat_jpeg,
    geometry_case,
    instance,
    level_case,
    meta_error,
    noise_jpeg,
    person,
    sam_results,
    vehicle,
    wheel,
)

from lusot_analysis.annotate import draw_numbered_boxes
from lusot_analysis.face_blur import (
    FACE_BLUR_VERSION,
    BlurredImage,
    blur_for_meta,
    decode_image,
)
from lusot_analysis.meta_client import (
    SAM_PHRASES,
    DeadlineExceeded,
    MetaApiError,
    ModelRefused,
    SamResult,
)
from lusot_analysis.pipeline import READING_PHRASES, PipelineRun, run_pipeline
from lusot_analysis.pipeline.publish import publish_jpeg
from lusot_analysis.pipeline.quality import quality_scores
from lusot_analysis.pipeline.types import ModelKeyRejected, Outcome
from lusot_analysis.prompts import PROMPT_VERSION, load_prompt
from lusot_analysis.tuning import START, TUNING

# The level case's result: knee from wheel 2, at rim_three_quarters.
KNEE = Outcome.level_result(
    "knee", "rim_three_quarters", False, {"vehicles": 1, "people": 0}
)
REASON = "REASON-MARKER-31"  # the reason fakes.answer gives every answer


@pytest.fixture(scope="module")
def prompt():
    return load_prompt(REPO_PROMPTS)


def calls(client: FakeClient, method: str) -> list[str]:
    """The phrase or schema name of each `method` call the fake recorded."""
    return [name for kind, name, _ in client.calls if kind == method]


def failing(error: Exception, phrase: str = "floodwater"):
    """A segment hook that fails `phrase`'s call with `error`, and no other call."""

    def hook(asked: str) -> None:
        if asked == phrase:
            raise error

    return hook


def with_person(sam: dict[str, SamResult]) -> dict[str, SamResult]:
    """`sam` with one person, numbered 3 after the level case's vehicle and wheel."""
    people = [instance(0, (450, 100, 550, 400))]
    return sam | {"person": SamResult("person", people, elapsed_s=0.5, raw="")}


def test_level_result_end_to_end(prompt):
    photo, sam, given = level_case()
    client = FakeClient(sam, given)
    run = run_pipeline(photo, client, prompt, tuning=START)
    assert run.outcome == KNEE
    # The photo stored is the face-blurred one with SAM's faces and plates blurred,
    # not the one with the numbered boxes drawn on it (C48, C61).
    assert decode_image(run.publish_jpeg).shape[:2] == (480, 640)
    assert run.publish_jpeg == publish_jpeg(blur_for_meta(photo), sam)
    # One SAM call per phrase and one Muse Spark answer, each on a BlurredImage
    # itself, so the face blur ran first (C20, C37).
    assert sorted(calls(client, "segment")) == sorted(SAM_PHRASES)
    assert calls(client, "judge") == [PROMPT_VERSION]
    assert all(kind is BlurredImage for _, _, kind in client.calls)
    scores = quality_scores(photo)
    assert run.log == {
        "blur_version": FACE_BLUR_VERSION,
        "face_boxes": 0,
        "brightness": round(scores.brightness, 1),
        "sharpness": round(scores.sharpness, 1),
        "meta_calls": 8,
        "models": {"sam": "sam-3.1", "spark": "muse-spark-1.3"},
        "prompt_version": PROMPT_VERSION,
        "geometry_in_level": "off",
        "tuning_version": "tuning-v1",
        "rim_edge_k": 1.0,
        "reasoning_effort": "default",
        "drawing_version": "boxes-v1",
        "sam_ms": dict.fromkeys(SAM_PHRASES, 500),
        "instances": {
            "floodwater": 1,
            "wheel": 1,
            "wheel rim": 0,
            "person": 0,
            "vehicle": 1,
            "face": 1,
            "license plate": 1,
        },
        "drops": {},
        "numbered": {"vehicles": 1, "wheels": 1, "people": 0},
        "spark_ms": 1500,
        "input_tokens": 1000,
        "output_tokens": 200,
        "reasoning_tokens": None,
        "deciding": "wheel",
        "level_from": "landmark",
    }


@pytest.mark.parametrize(
    ("photo", "reason"),
    [(flat_jpeg(10), "too_dark"), (flat_jpeg(128), "too_blurry")],
    ids=["dark", "flat"],
)
def test_quality_refusals_make_no_meta_call(prompt, photo, reason):
    _, sam, given = level_case()
    client = FakeClient(sam, given)
    run = run_pipeline(photo, client, prompt)
    assert run.outcome == Outcome.refused(reason)
    assert run.publish_jpeg is None
    assert client.calls == []
    assert run.log["meta_calls"] == 0
    # Steps 0 and 1 ran, and nothing after them.
    assert set(run.log) == {
        "meta_calls",
        "blur_version",
        "face_boxes",
        "brightness",
        "sharpness",
    }


@pytest.mark.parametrize(
    "photo", [b"not a jpeg", noise_jpeg(32, 32)], ids=["not-an-image", "32-px"]
)
def test_bad_files(prompt, photo):
    # blur_for_meta refuses both: one doesn't decode, and the other's short side is
    # 32 px, too small to check for faces (R27).
    _, sam, given = level_case()
    client = FakeClient(sam, given)
    run = run_pipeline(photo, client, prompt)
    assert run == PipelineRun(Outcome.failed("bad_file"), {"meta_calls": 0}, None)
    assert client.calls == []


@pytest.mark.parametrize(
    ("given", "water", "expected"),
    [
        pytest.param(
            answer(photo_usable="no"),
            True,
            Outcome.refused("photo_unusable"),
            id="photo-unusable",
        ),
        pytest.param(
            answer(standing_water="unsure"),
            True,
            Outcome.refused("water_unsure"),
            id="water-unsure",
        ),
        # SAM's water never overrides a clear no (C51).
        pytest.param(
            answer(standing_water="no"), True, Outcome.no_flood(), id="no-flood-seen"
        ),
        pytest.param(
            answer(), False, Outcome.refused("no_water_found"), id="no-water-found"
        ),
        # Muse Spark refused to answer: can't tell, not processing failed (C86).
        pytest.param(
            ModelRefused("Muse Spark refused to answer"),
            True,
            Outcome.refused("model_declined"),
            id="model-declined",
        ),
    ],
)
def test_gate_outcomes_through_the_pipeline(prompt, given, water, expected):
    photo, sam, _ = level_case()
    if not water:
        sam["floodwater"] = dataclasses.replace(sam["floodwater"], instances=[])
    client = FakeClient(sam, given)
    run = run_pipeline(photo, client, prompt)
    assert run.outcome == expected
    assert run.publish_jpeg is None
    assert calls(client, "judge") == [PROMPT_VERSION]
    assert run.log["meta_calls"] == 8
    assert "deciding" not in run.log
    assert "error" not in run.log


@pytest.mark.parametrize(
    ("sam_people", "given", "reason", "drops"),
    [
        # The moving car goes, and its wheel with it (W1), so nothing is left.
        pytest.param(
            False,
            answer(
                vehicles=[vehicle(1, moving="yes")],
                wheels=[wheel(2, "rim_three_quarters")],
            ),
            "no_usable_reference",
            {"vehicle_moving": 1, "wheel_vehicle_dropped": 1},
            id="only-a-moving-vehicle",
        ),
        # Car A's tire_only reads below_gutter, far below the person's chest (C54).
        pytest.param(
            True,
            answer(
                vehicles=[vehicle(1)],
                wheels=[wheel(2, "tire_only")],
                people=[person(3, "chest")],
            ),
            "references_disagree",
            {},
            id="tire-only-beside-chest",
        ),
    ],
)
def test_refusals_after_the_drops(prompt, sam_people, given, reason, drops):
    photo, sam, _ = level_case()
    client = FakeClient(with_person(sam) if sam_people else sam, given)
    run = run_pipeline(photo, client, prompt)
    assert run.outcome == Outcome.refused(reason)
    assert run.publish_jpeg is None
    assert run.log["drops"] == drops
    assert "deciding" not in run.log


# The level case's answer, with an extra key, and with wheel 2's id as a string.
EXTRA_KEY = {
    **answer(vehicles=[vehicle(1)], wheels=[wheel(2, "rim_three_quarters")]),
    "extra": 1,
}
ID_AS_STRING = answer(vehicles=[vehicle(1)], wheels=[wheel("2", "rim_three_quarters")])


def not_json() -> json.JSONDecodeError:
    """What judge raises on an answer that isn't JSON: json.loads' own error (R62)."""
    return json.JSONDecodeError("Expecting value", f"{REASON} is not JSON", 0)


def timed_out() -> MetaApiError:
    """What the client raises on a lost connection or a timeout, after its retries."""
    return MetaApiError("connection failed or timed out")


@pytest.mark.parametrize(
    ("segment_error", "judged", "logged", "meta_calls"),
    [
        pytest.param(
            meta_error(500),
            None,
            {"error": "MetaApiError", "meta_status": 500},
            7,
            id="segment-500",
        ),
        pytest.param(
            timed_out(),
            None,
            {"error": "MetaApiError", "meta_status": None},
            7,
            id="segment-timeout",
        ),
        pytest.param(
            None,
            meta_error(400),
            {"error": "MetaApiError", "meta_status": 400},
            8,
            id="judge-400",
        ),
        pytest.param(
            None,
            timed_out(),
            {"error": "MetaApiError", "meta_status": None},
            8,
            id="judge-timeout",
        ),
        pytest.param(
            None,
            DeadlineExceeded("timed out at the deadline"),
            {"error": "DeadlineExceeded", "meta_status": None},
            8,
            id="judge-deadline",
        ),
        pytest.param(None, EXTRA_KEY, {"error": "ModelAnswerError"}, 8, id="extra-key"),
        pytest.param(
            None, ID_AS_STRING, {"error": "ModelAnswerError"}, 8, id="id-as-string"
        ),
        pytest.param(None, not_json(), {"error": "ModelAnswerError"}, 8, id="not-json"),
    ],
)
def test_model_errors_pay_once(prompt, segment_error, judged, logged, meta_calls):
    # `judged` is what judge answers or raises; None keeps the level case's answer.
    photo, sam, given = level_case()
    hook = None if segment_error is None else failing(segment_error)
    client = FakeClient(sam, given if judged is None else judged, on_segment=hook)
    run = run_pipeline(photo, client, prompt)
    assert run.outcome == Outcome.failed("model_error")
    assert run.publish_jpeg is None
    # The pipeline never asks again: no second SAM call or paid answer (C47, C59).
    segments = calls(client, "segment")
    assert len(segments) == len(set(segments))
    assert len(calls(client, "judge")) <= 1
    assert run.log["meta_calls"] == meta_calls
    # The error's class name, and a Meta error's status; never its message.
    assert {k: run.log[k] for k in ("error", "meta_status") if k in run.log} == logged
    assert "deciding" not in run.log


@pytest.mark.parametrize(
    ("segment_error", "judged", "status"),
    [
        pytest.param(meta_error(401), None, 401, id="segment-401"),
        pytest.param(meta_error(402), None, 402, id="segment-402"),
        pytest.param(None, meta_error(403), 403, id="judge-403"),
    ],
)
def test_rejected_key_raises(prompt, segment_error, judged, status):
    # C73: the key or the account was rejected, not the photo, so it isn't an outcome.
    photo, sam, given = level_case()
    hook = None if segment_error is None else failing(segment_error)
    client = FakeClient(sam, given if judged is None else judged, on_segment=hook)
    with pytest.raises(ModelKeyRejected) as exc:
        run_pipeline(photo, client, prompt)
    assert exc.value.status == status
    assert len(calls(client, "judge")) == (1 if judged is not None else 0)


def test_rejected_key_wins_over_other_sam_failures(prompt):
    # R107: a 500 on floodwater must not hide a 401 on wheel (C73).
    photo, sam, given = level_case()
    errors = {"floodwater": meta_error(500), "wheel": meta_error(401)}

    def on_segment(phrase: str) -> None:
        if phrase in errors:
            raise errors[phrase]

    client = FakeClient(sam, given, on_segment=on_segment)
    with pytest.raises(ModelKeyRejected) as exc:
        run_pipeline(photo, client, prompt)
    assert exc.value.status == 401
    assert calls(client, "judge") == []


def test_deadline_reaches_every_call(prompt):
    photo, sam, given = level_case()
    client = FakeClient(sam, given)
    run = run_pipeline(photo, client, prompt, deadline=123.0)
    assert run.outcome == KNEE
    assert len(client.keywords) == 8
    assert all(keywords["deadline"] == 123.0 for keywords in client.keywords)
    # With no deadline given, every call runs with none, as offline (C84).
    client = FakeClient(sam, given)
    run_pipeline(photo, client, prompt)
    assert [keywords["deadline"] for keywords in client.keywords] == [None] * 8


def test_deadline_exceeded_is_a_model_error(prompt):
    photo, sam, given = level_case()
    stopped = DeadlineExceeded("too little time left before the deadline")
    client = FakeClient(sam, given, on_segment=failing(stopped))
    run = run_pipeline(photo, client, prompt, deadline=123.0)
    assert run.outcome == Outcome.failed("model_error")
    assert run.log["error"] == "DeadlineExceeded"
    assert run.log["meta_status"] is None
    assert calls(client, "judge") == []


def test_other_exceptions_are_pipeline_errors(prompt):
    photo, sam, given = level_case()
    client = FakeClient(sam, given, on_segment=failing(KeyError("boom-marker")))
    run = run_pipeline(photo, client, prompt)
    assert run.outcome == Outcome.failed("pipeline_error")
    assert run.publish_jpeg is None
    assert run.log["error"] == "KeyError"
    assert "meta_status" not in run.log
    assert "boom-marker" not in json.dumps(run.log)
    assert calls(client, "judge") == []


def test_failed_publish_is_a_pipeline_error(prompt, monkeypatch):
    # A level result stores its photo (C61), so one whose photo can't be made fails,
    # with no level and no deciding reference.
    def broken(image, sam):
        raise ValueError("JPEG encoding failed")

    monkeypatch.setattr("lusot_analysis.pipeline.publish_jpeg", broken)
    photo, sam, given = level_case()
    run = run_pipeline(photo, FakeClient(sam, given), prompt)
    assert run.outcome == Outcome.failed("pipeline_error")
    assert run.publish_jpeg is None
    assert "deciding" not in run.log
    assert run.log["error"] == "ValueError"


@pytest.mark.parametrize(
    ("given", "status"),
    [
        pytest.param(None, "done", id="level"),
        pytest.param(answer(standing_water="no"), "done", id="no-flood-seen"),
        pytest.param(
            answer(vehicles=[vehicle(1, moving="unsure")]), "refused", id="refused"
        ),
        pytest.param(EXTRA_KEY, "failed", id="fails-the-schema"),
        pytest.param(not_json(), "failed", id="not-json"),
    ],
)
def test_reason_text_never_reaches_the_log(prompt, given, status):
    # C62: Muse Spark's free text can describe people or plates.
    photo, sam, level_answer = level_case()
    run = run_pipeline(photo, FakeClient(sam, given or level_answer), prompt)
    assert run.outcome.status == status
    assert REASON not in json.dumps(run.log)
    # The run carries no answer, so the handler never sees the reason. Its evidence
    # record (C328) holds none either: test_evidence_holds_no_face_plate_or_reason.
    fields = [field.name for field in dataclasses.fields(PipelineRun)]
    assert fields == ["outcome", "log", "publish_jpeg", "evidence"]


def test_reading_phrases_skip_face_and_plate(prompt):
    # C66: offline, nothing is stored, so SAM isn't asked for faces or plates.
    assert READING_PHRASES == ("floodwater", "wheel", "wheel rim", "person", "vehicle")
    photo, sam, given = level_case()
    client = FakeClient(sam, given)
    run = run_pipeline(photo, client, prompt, phrases=READING_PHRASES)
    assert sorted(calls(client, "segment")) == sorted(READING_PHRASES)
    assert run.outcome == KNEE
    assert run.publish_jpeg is None
    assert run.log["meta_calls"] == 6
    assert set(run.log["sam_ms"]) == set(READING_PHRASES)


def test_drops_from_every_step_reach_the_log(prompt):
    # Vehicles 1 and 2 each keep a wheel, 3 and 4. A third wheel lies in neither
    # vehicle's box, so it is cut before numbering and gets no number (C55, C69):
    # numbering SAM's raw results would give it one.
    sam = sam_results(
        {
            "vehicle": [(100, 100, 400, 300), (420, 100, 620, 300)],
            "wheel": [(10, 400, 60, 450), (150, 250, 200, 300), (440, 250, 490, 300)],
            "person": [(450, 320, 500, 470)],
            "floodwater": [(0, 280, 640, 480)],
        }
    )
    given = answer(
        vehicles=[vehicle(1), vehicle(2)],
        wheels=[
            wheel(3, "rim_three_quarters"),
            wheel(4, "not_visible"),  # car 2's only wheel, so it gives no reading
            wheel(99, "hub"),  # not a box's id
        ],
    )  # person 5 is left unanswered
    run = run_pipeline(noise_jpeg(), FakeClient(sam, given), prompt)
    assert run.outcome == KNEE
    assert run.log["numbered"] == {"vehicles": 2, "wheels": 2, "people": 1}
    assert run.log["drops"] == {
        "wheel_unlinked": 1,  # before numbering
        "unknown_id": 1,  # the id check
        "person_unanswered": 1,  # the drops after the gate
        "vehicle_no_reading": 1,  # measuring
    }


def test_bad_ids_are_dropped_before_the_gate(prompt):
    # Box 99 isn't numbered, so its rim_top is dropped and can't contradict the no
    # (C47, C52).
    photo, sam, _ = level_case()
    given = answer(standing_water="no", wheels=[wheel(99, "rim_top")])
    run = run_pipeline(photo, FakeClient(sam, given), prompt)
    assert run.outcome == Outcome.no_flood()
    assert run.log["drops"] == {"unknown_id": 1}
    # The same waterline on numbered wheel 2 does contradict it.
    given = answer(standing_water="no", wheels=[wheel(2, "rim_top")])
    run = run_pipeline(photo, FakeClient(sam, given), prompt)
    assert run.outcome == Outcome.refused("water_unsure")


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        pytest.param(answer(standing_water="no"), Outcome.no_flood(), id="water-no"),
        pytest.param(
            answer(standing_water="yes"),
            Outcome.refused("no_water_found"),
            id="water-yes",
        ),
        pytest.param(
            answer(photo_usable="no"), Outcome.refused("photo_unusable"), id="unusable"
        ),
    ],
)
def test_empty_scene_still_asks_muse_spark_once(prompt, given, expected):
    # Review Focus 3: a wall, a selfie or a dry lane, where SAM finds nothing at all.
    client = FakeClient(sam_results({}), given)
    run = run_pipeline(noise_jpeg(), client, prompt)
    assert run.outcome == expected
    assert run.publish_jpeg is None
    assert calls(client, "judge") == [PROMPT_VERSION]
    assert run.log["numbered"] == {"vehicles": 0, "wheels": 0, "people": 0}
    assert run.log["drops"] == {}


# MS3b: step 3 after the gate, and geometry behind geometry_in_level (C309, C317)


def with_people(
    sam: dict[str, SamResult], *boxes: tuple[float, float, float, float]
) -> dict[str, SamResult]:
    """`sam` with a person for each box, numbered after the level case's two boxes."""
    people = [instance(i, box) for i, box in enumerate(boxes)]
    return sam | {"person": SamResult("person", people, elapsed_s=0.5, raw="")}


# A person whose lowest row is 199. The level case's water starts at row 280, so none
# comes within 5 px of it (C301).
DRY_PERSON = (450, 50, 480, 200)
STEP3_CAUSES = {"no_water_contact", "ragged_waterline"}


def test_geometry_result_end_to_end(prompt):
    photo, sam, given = geometry_case()
    client = FakeClient(sam, given)
    run = run_pipeline(photo, client, prompt, geometry_in_level=True, tuning=START)
    outcome = run.outcome
    # Wheel 2's landmark and geometry both read half_knee, so the level counts as
    # geometry's, with its inches (C307). The landmark stays Muse Spark's (C320).
    assert (outcome.level, outcome.landmark, outcome.level_from) == (
        "half_knee",
        "rim_quarter",
        "geometry",
    )
    assert outcome.depth_in_min == pytest.approx(7.720, abs=0.02)
    assert outcome.depth_in_max == pytest.approx(8.184, abs=0.02)
    fields = outcome.item_fields()
    assert (fields["depthInMin"], fields["depthInMax"]) == (7.7, 8.2)  # C308
    assert {key: run.log[key] for key in MS3B_LOG_KEYS} == {
        "geometry_in_level": "on",
        "tuning_version": "tuning-v1",
        "rim_edge_k": 1.0,
        "reasoning_effort": "default",
        "drawing_version": "boxes-v1",
        "reasoning_tokens": None,
        "wheels_measured": 1,
        "geometry_checks": {},
        "level_from": "geometry",
        "depth_in": [7.7, 8.2],
    }
    assert run.log["drops"] == {}
    # Geometry reads masks SAM already sent, so it makes no new Meta call.
    assert sorted(calls(client, "segment")) == sorted(SAM_PHRASES)
    assert calls(client, "judge") == [PROMPT_VERSION]
    assert run.log["meta_calls"] == 8


def test_geometry_off_is_ms3a_plus_step3(prompt):
    # C309: off, a van is dropped by its type, as in MS3a (C45), and no geometry runs.
    photo, sam, given = geometry_case("van")
    off = run_pipeline(photo, FakeClient(sam, given), prompt, tuning=START)
    assert off.outcome == Outcome.refused("no_usable_reference")
    assert off.log["drops"]["vehicle_type"] == 1
    assert off.log["geometry_in_level"] == "off"
    assert "wheels_measured" not in off.log
    assert "geometry_checks" not in off.log
    # On, the van is kept for geometry, which alone reads its wheel (C318).
    on = run_pipeline(
        photo, FakeClient(sam, given), prompt, geometry_in_level=True, tuning=START
    )
    assert (on.outcome.level, on.outcome.level_from) == ("half_knee", "geometry")
    assert on.outcome.depth_in_min == pytest.approx(9.887, abs=0.02)
    assert on.outcome.depth_in_max == pytest.approx(9.887, abs=0.02)
    assert on.log["wheels_measured"] == 1


def test_step3_runs_after_the_gate(prompt):
    # C317: SAM found no water and Muse Spark says none stands, but wheel 2 sits at
    # rim_quarter, so the gate refuses (C52). Step 3 comes after the gate: run
    # earlier, its no_water_contact on wheel 2 would join the drops.
    photo, sam, given = geometry_case()
    sam["floodwater"] = dataclasses.replace(sam["floodwater"], instances=[])
    given = {**given, "standing_water": "no"}
    run = run_pipeline(
        photo, FakeClient(sam, given), prompt, geometry_in_level=True, tuning=START
    )
    assert run.outcome == Outcome.refused("water_unsure")
    assert run.log["drops"] == {}
    assert "wheels_measured" not in run.log


def test_a_dry_reference_refuses_rather_than_reads_shallow(prompt):
    # C317: water reaches wheel 2, at knee, but not person 3, at waist. Step 3 drops
    # the waist, and a dropped reading deeper than an exact result refuses the photo,
    # so a reading whose water SAM missed never lets a shallower one win.
    photo, sam, _ = level_case()
    given = answer(
        vehicles=[vehicle(1)],
        wheels=[wheel(2, "rim_three_quarters")],
        people=[person(3, "waist")],
    )
    sam = with_people(sam, DRY_PERSON)
    run = run_pipeline(photo, FakeClient(sam, given), prompt, tuning=START)
    assert run.outcome == Outcome.refused("references_disagree")
    assert run.log["drops"] == {"no_water_contact": 1}


def test_a_dry_standing_adult_still_blocks_wading_adults(prompt):
    # C317, C57 (finding 8): person 3, an adult standing still, blocks person 4, who
    # isn't, so person 4 drops before step 3 runs. Step 3 then drops person 3, whom no
    # water reaches, and wheel 2's knee decides.
    photo, sam, _ = level_case()
    given = answer(
        vehicles=[vehicle(1)],
        wheels=[wheel(2, "rim_three_quarters")],
        people=[person(3, "knee"), person(4, "knee", standing_still="no")],
    )
    sam = with_people(sam, DRY_PERSON, (520, 150, 560, 280))
    run = run_pipeline(photo, FakeClient(sam, given), prompt, tuning=START)
    assert run.outcome == KNEE
    assert run.log["deciding"] == "wheel"
    assert run.log["drops"] == {"person_wading": 1, "no_water_contact": 1}


def test_step3_reads_a_body_that_gives_a_reading(prompt):
    # C317, C53: wheel 2 is hidden, so vehicle 1 reads from its body, at window. Its
    # mask ends at row 249, 31 rows above the water, so step 3 drops the body, and
    # nothing is left to decide.
    photo, sam, _ = level_case()
    body = instance(0, (100, 100, 400, 300), mask_xyxy=(100, 100, 400, 250))
    sam["vehicle"] = dataclasses.replace(sam["vehicle"], instances=[body])
    given = answer(
        vehicles=[vehicle(1, body="window")], wheels=[wheel(2, "not_visible")]
    )
    run = run_pipeline(photo, FakeClient(sam, given), prompt, tuning=START)
    assert run.outcome == Outcome.refused("no_usable_reference")
    assert run.log["drops"] == {"no_water_contact": 1, "vehicle_no_reading": 1}


@pytest.mark.parametrize(
    "water",
    [None, (0, 400, 640, 480)],
    ids=["water-at-the-wheel", "water-far-below"],
)
def test_not_visible_wheel_gets_no_geometry(prompt, water):
    # Review Focus 3: a wheel answered not_visible gets no geometry (C318) and no
    # step 3 (C317), and its vehicle gives no reading from it (C76). With the water
    # far below, step 3 on it would find no contact.
    photo, sam, given = geometry_case(waterline="not_visible")
    if water is not None:
        sam["floodwater"] = sam_results({"floodwater": [water]})["floodwater"]
    run = run_pipeline(
        photo, FakeClient(sam, given), prompt, geometry_in_level=True, tuning=START
    )
    assert run.outcome == Outcome.refused("no_usable_reference")
    assert run.log["geometry_checks"] == {"waterline_not_visible": 1}
    assert run.log["wheels_measured"] == 0
    assert run.log["drops"] == {"vehicle_no_reading": 1}
    assert not STEP3_CAUSES & set(run.log["drops"])


def test_a_rim_in_a_cut_wheel_never_joins_a_kept_one(prompt):
    # P14: rims link among all of SAM's wheels, before the cuts, as C55 links wheels
    # among all of SAM's vehicles. A 30 px wheel inside wheel 2's box is cut by the
    # 40 px rule, and a second rim, centred at (355, 245), lies in both wheel boxes,
    # so it joins neither. The real rim's centre (320.5, 231) lies in wheel 2's box
    # alone. Linking among the kept wheels only would give wheel 2 both rims.
    photo, sam, given = geometry_case()
    sam["wheel"].instances.append(instance(1, (340, 228, 370, 257)))
    sam["wheel rim"].instances.append(instance(1, around(355, 245, 10, 10)))
    run = run_pipeline(
        photo, FakeClient(sam, given), prompt, geometry_in_level=True, tuning=START
    )
    assert run.log["drops"] == {"wheel_small": 1}
    assert run.log["numbered"] == {"vehicles": 1, "wheels": 1, "people": 0}
    assert run.log["wheels_measured"] == 1
    assert run.log["geometry_checks"] == {}
    assert run.outcome.level_from == "geometry"


@pytest.mark.parametrize(
    ("case", "changes", "expected", "logged"),
    [
        pytest.param(
            level_case,
            {"brightness_min": 255.0},
            Outcome.refused("too_dark"),
            {},
            id="quality-gate",
        ),
        # No reference can have more than all its columns touching (C302).
        pytest.param(
            level_case,
            {"touch_share_min": 1.01},
            Outcome.refused("no_usable_reference"),
            {"drops": {"no_water_contact": 1, "vehicle_no_reading": 1}},
            id="step-3",
        ),
        # Check 4 fails, so wheel 2 keeps its landmark reading alone (C305).
        pytest.param(
            geometry_case,
            {"daylight_brightness_min": 255.0},
            Outcome.level_result(
                "half_knee", "rim_quarter", False, {"vehicles": 1, "people": 0}
            ),
            {"geometry_checks": {"not_daylight": 1}, "wheels_measured": 0},
            id="geometry-checks",
        ),
    ],
)
def test_the_tuning_reaches_each_step(prompt, case, changes, expected, logged):
    # C310: run_pipeline's tuning, not the live one, sets each step's cutoffs, and the
    # log names its version and k from step 2 on (C316).
    tuning = dataclasses.replace(START, version="tuning-x", rim_edge_k=1.25, **changes)
    photo, sam, given = case()
    run = run_pipeline(
        photo, FakeClient(sam, given), prompt, geometry_in_level=True, tuning=tuning
    )
    assert run.outcome == expected
    assert {key: run.log[key] for key in logged} == logged
    if expected.reason != "too_dark":
        assert (run.log["tuning_version"], run.log["rim_edge_k"]) == ("tuning-x", 1.25)


# Every key MS3a's log can hold, and the keys MS3b adds (C316).
MS3A_LOG_KEYS = {
    "meta_calls",
    "blur_version",
    "face_boxes",
    "brightness",
    "sharpness",
    "models",
    "prompt_version",
    "sam_ms",
    "instances",
    "drops",
    "numbered",
    "spark_ms",
    "input_tokens",
    "output_tokens",
    "deciding",
    "error",
    "meta_status",
}
MS3B_LOG_KEYS = {
    "geometry_in_level",
    "tuning_version",
    "rim_edge_k",
    "reasoning_effort",
    "drawing_version",
    "reasoning_tokens",
    "wheels_measured",
    "geometry_checks",
    "level_from",
    "depth_in",
}


@pytest.mark.parametrize("geometry_in_level", [False, True], ids=["off", "on"])
@pytest.mark.parametrize(
    ("case", "judged"),
    [
        pytest.param(geometry_case, None, id="geometry"),
        pytest.param(lambda: geometry_case("van"), None, id="van"),
        pytest.param(level_case, None, id="level"),
        pytest.param(geometry_case, meta_error(500), id="model-error"),
    ],
)
def test_log_keys_are_the_known_set(prompt, case, judged, geometry_in_level):
    # C316: each key is one MS3a logs or one MS3b adds, so no mask, image or evidence
    # can reach the log, and every value is plain JSON.
    photo, sam, given = case()
    client = FakeClient(sam, given if judged is None else judged)
    run = run_pipeline(
        photo, client, prompt, geometry_in_level=geometry_in_level, tuning=START
    )
    assert set(run.log) <= MS3A_LOG_KEYS | MS3B_LOG_KEYS
    json.dumps(run.log)  # an array or a mask would raise TypeError


# MS3b: what Muse Spark is sent, its reasoning effort and the boxes' drawing (C312, C325)


def judged_efforts(client: FakeClient) -> list[object]:
    """The reasoning effort of each judge call the fake recorded."""
    return [
        keywords["reasoning_effort"]
        for (kind, _, _), keywords in zip(client.calls, client.keywords, strict=True)
        if kind == "judge"
    ]


def test_reasoning_effort_and_drawing_reach_judge(prompt, monkeypatch):
    # run_pipeline sends its tuning's effort, draws the boxes its tuning's way, and
    # logs both from step 2 on (C316).
    drawings = []

    def spy(image, boxes, *, drawing):
        drawings.append(drawing)
        return draw_numbered_boxes(image, boxes, drawing=drawing)

    monkeypatch.setattr("lusot_analysis.pipeline.draw_numbered_boxes", spy)
    photo, sam, given = level_case()
    tuning = dataclasses.replace(START, reasoning_effort="low", drawing="boxes-v2")
    client = FakeClient(sam, given)
    run = run_pipeline(photo, client, prompt, tuning=tuning)
    assert run.outcome == KNEE
    assert judged_efforts(client) == ["low"]
    assert drawings == ["boxes-v2"]
    logged = (run.log["reasoning_effort"], run.log["drawing_version"])
    assert logged == ("low", "boxes-v2")
    # The live TUNING, which the handler and the offline runner take by default. The
    # checks read its fields, not their start values, so a later tuning can't break
    # them (R128).
    client = FakeClient(sam, given)
    run = run_pipeline(photo, client, prompt)
    assert judged_efforts(client) == [TUNING.reasoning_effort]
    assert drawings == ["boxes-v2", TUNING.drawing]
    logged = (run.log["reasoning_effort"], run.log["drawing_version"])
    assert logged == (TUNING.reasoning_effort or "default", TUNING.drawing)


def test_reasoning_tokens_are_logged(prompt):
    # C312, C316: once Muse Spark has answered, its reasoning tokens, or None when
    # Meta doesn't report them, as its documented example doesn't.
    photo, sam, given = level_case()
    client = FakeClient(sam, given, reasoning_tokens=180)
    run = run_pipeline(photo, client, prompt, tuning=START)
    assert run.log["reasoning_tokens"] == 180
    run = run_pipeline(photo, FakeClient(sam, given), prompt, tuning=START)
    assert run.log["reasoning_tokens"] is None
    # A failed answer has no count, but the effort and the drawing are still logged.
    run = run_pipeline(photo, FakeClient(sam, meta_error(500)), prompt, tuning=START)
    assert "reasoning_tokens" not in run.log
    logged = (run.log["reasoning_effort"], run.log["drawing_version"])
    assert logged == ("default", "boxes-v1")


@pytest.mark.parametrize(
    "changes",
    [{"reasoning_effort": "extreme"}, {"drawing": "boxes-v9"}],
    ids=["effort", "drawing"],
)
def test_a_bad_tuning_fails_before_any_meta_call(prompt, changes):
    # R146: an effort Muse Spark doesn't take, or a drawing annotate doesn't know,
    # fails before the face blur. Checked later, it would cost SAM's calls first.
    def no_segment(phrase: str) -> None:
        raise AssertionError("a SAM call was made")

    photo, sam, given = level_case()
    client = FakeClient(sam, given, on_segment=no_segment)
    tuning = dataclasses.replace(START, **changes)
    run = run_pipeline(photo, client, prompt, tuning=tuning)
    assert run.outcome == Outcome.failed("pipeline_error")
    assert run.log == {"meta_calls": 0, "error": "ValueError"}
    assert client.calls == []
    assert run.evidence is None


# MS4: keep_photo, a sample seed's blurred copy whatever its outcome (C512, MS4-Q14)


@pytest.mark.parametrize(
    "judged",
    [
        pytest.param(None, id="level"),
        pytest.param(answer(standing_water="no"), id="no-flood-seen"),
        pytest.param(answer(photo_usable="no"), id="photo-unusable"),
        pytest.param(meta_error(500), id="judge-500"),
    ],
)
def test_keep_photo_never_changes_the_outcome(prompt, judged):
    # MS4-Q14: the flag adds the stored copy and nothing else, so a seed's outcome
    # and log are the ones any other report of the same photo gets.
    photo, sam, given = level_case()
    without, kept = (
        run_pipeline(
            photo,
            FakeClient(sam, given if judged is None else judged),
            prompt,
            keep_photo=keep,
        )
        for keep in (False, True)
    )
    assert kept.publish_jpeg is not None  # the flag acted on this run
    assert kept.outcome == without.outcome
    assert kept.log == without.log
    assert list(kept.log) == list(without.log)  # in the same order, too
    assert kept.evidence == without.evidence


@pytest.mark.parametrize(
    ("judged", "sam_people", "expected"),
    [
        pytest.param(None, False, KNEE, id="level"),
        pytest.param(
            answer(standing_water="no"), False, Outcome.no_flood(), id="no-flood-seen"
        ),
        pytest.param(
            answer(photo_usable="no"),
            False,
            Outcome.refused("photo_unusable"),
            id="photo-unusable",
        ),
        pytest.param(
            ModelRefused("Muse Spark refused to answer"),
            False,
            Outcome.refused("model_declined"),
            id="model-declined",
        ),
        pytest.param(
            answer(
                vehicles=[vehicle(1, moving="yes")],
                wheels=[wheel(2, "rim_three_quarters")],
            ),
            False,
            Outcome.refused("no_usable_reference"),
            id="no-usable-reference",
        ),
        pytest.param(
            answer(
                vehicles=[vehicle(1)],
                wheels=[wheel(2, "tire_only")],
                people=[person(3, "chest")],
            ),
            True,
            Outcome.refused("references_disagree"),
            id="references-disagree",
        ),
        pytest.param(
            meta_error(500), False, Outcome.failed("model_error"), id="model-error"
        ),
        pytest.param(
            KeyError("boom-marker"),
            False,
            Outcome.failed("pipeline_error"),
            id="pipeline-error",
        ),
    ],
)
def test_keep_photo_returns_a_copy_after_sam(prompt, judged, sam_people, expected):
    # C512: once SAM has sent its faces and plates, any outcome can keep step 8.1's
    # copy. Without the flag, C61 holds: a copy for a level result only.
    photo, sam, given = level_case()
    sam = with_person(sam) if sam_people else sam
    copy = publish_jpeg(blur_for_meta(photo), sam)
    answered = given if judged is None else judged
    kept = run_pipeline(photo, FakeClient(sam, answered), prompt, keep_photo=True)
    assert kept.outcome == expected
    assert kept.publish_jpeg == copy
    plain = run_pipeline(photo, FakeClient(sam, answered), prompt)
    assert plain.outcome == expected
    assert plain.publish_jpeg == (copy if expected == KNEE else None)


def test_keep_photo_needs_sam_and_both_phrases(prompt):
    # The copy blurs SAM's faces and plates, so a run that never got SAM's answer,
    # or never asked for both, has none to keep, flag or not.
    _, sam, given = level_case()
    dark = run_pipeline(flat_jpeg(10), FakeClient(sam, given), prompt, keep_photo=True)
    assert dark.outcome == Outcome.refused("too_dark")  # refused before SAM
    assert dark.publish_jpeg is None
    photo, sam, given = level_case()
    lost = FakeClient(sam, given, on_segment=failing(meta_error(500)))
    unsegmented = run_pipeline(photo, lost, prompt, keep_photo=True)
    assert unsegmented.outcome == Outcome.failed("model_error")  # SAM never returned
    assert unsegmented.publish_jpeg is None
    dry = answer(standing_water="no")
    for answered, expected in ((given, KNEE), (dry, Outcome.no_flood())):
        client = FakeClient(sam, answered)  # C66: offline, no face or plate phrase
        reading = run_pipeline(
            photo, client, prompt, phrases=READING_PHRASES, keep_photo=True
        )
        assert reading.outcome == expected
        assert reading.publish_jpeg is None
    # With both phrases, the same dry run keeps its copy, so the phrases decide.
    full = run_pipeline(photo, FakeClient(sam, dry), prompt, keep_photo=True)
    assert full.publish_jpeg == publish_jpeg(blur_for_meta(photo), sam)


def test_a_failed_kept_copy_keeps_the_outcome(prompt, monkeypatch):
    # The outcome is settled before the kept copy is made, so a copy that fails
    # leaves the outcome and the log as they were, with no copy.
    tried = []

    def broken(image, sam):
        tried.append(image)
        raise ValueError("JPEG encoding failed")

    monkeypatch.setattr("lusot_analysis.pipeline.publish_jpeg", broken)
    photo, sam, given = level_case()
    dry = answer(standing_water="no")
    plain = run_pipeline(photo, FakeClient(sam, dry), prompt)
    kept = run_pipeline(photo, FakeClient(sam, dry), prompt, keep_photo=True)
    assert len(tried) == 1  # the flagged run tried, and only it
    assert kept.outcome == Outcome.no_flood()
    assert kept.publish_jpeg is None
    assert kept.log == plain.log
    # A level run whose copy fails is still a pipeline error with the flag (C61).
    level = run_pipeline(photo, FakeClient(sam, given), prompt, keep_photo=True)
    assert level.outcome == Outcome.failed("pipeline_error")
    assert level.publish_jpeg is None
    assert level.log["error"] == "ValueError"
