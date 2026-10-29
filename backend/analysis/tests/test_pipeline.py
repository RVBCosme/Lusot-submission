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
    flat_jpeg,
    instance,
    level_case,
    meta_error,
    noise_jpeg,
    person,
    sam_results,
    vehicle,
    wheel,
)

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
    run = run_pipeline(photo, client, prompt)
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
        "deciding": "wheel",
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
    # The run carries no answer, so the handler never sees the reason.
    fields = [field.name for field in dataclasses.fields(PipelineRun)]
    assert fields == ["outcome", "log", "publish_jpeg"]


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
