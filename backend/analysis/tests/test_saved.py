"""Tests for the saved model outputs the offline runner keeps (spec §3.7, B3).

RecordingClient keeps what a live run's client returns, and SavedOutputsClient gives
it back, so the same outputs give the same result. Every test records through
FakeClient, so no Meta call is made.
"""

import dataclasses
import hashlib
import json

import numpy as np
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
)

from lusot_analysis.face_blur import FACE_BLUR_VERSION, blur_for_meta
from lusot_analysis.meta_client import (
    SAM_PHRASES,
    MetaApiError,
    ModelRefused,
    SamResult,
    SparkResult,
)
from lusot_analysis.pipeline import READING_PHRASES, run_pipeline
from lusot_analysis.pipeline.saved import (
    RecordingClient,
    SavedOutputsClient,
    load_sam_results,
    rebuild_outcome,
    save_sam_results,
)
from lusot_analysis.pipeline.types import ModelAnswerError, Outcome
from lusot_analysis.prompts import PROMPT_VERSION, load_prompt

# The level case's result: knee from wheel 2, at rim_three_quarters.
KNEE = Outcome.level_result(
    "knee", "rim_three_quarters", False, {"vehicles": 1, "people": 0}
)
REASON = "REASON-MARKER-31"  # the reason fakes.answer gives every answer


@pytest.fixture(scope="module")
def prompt():
    return load_prompt(REPO_PROMPTS)


def record(
    tmp_path, client, prompt, *, photo=None, phrases=READING_PHRASES, **keywords
):
    """A live run of `photo` through RecordingClient(client), saved.

    The photo, by default the level case's, is written to tmp_path/street.jpg and the
    run to tmp_path/run. `keywords` go to run_pipeline. Returns the photo's bytes,
    the run and its folder.
    """
    photo = level_case()[0] if photo is None else photo
    path = tmp_path / "street.jpg"
    path.write_bytes(photo)
    recorder = RecordingClient(client)
    run = run_pipeline(photo, recorder, prompt, phrases=phrases, **keywords)
    run_dir = tmp_path / "run"
    recorder.save(run_dir, photo=path, prompt=prompt, run=run)
    return photo, run, run_dir


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fields(result: SamResult) -> tuple:
    """A SAM result's fields, with each instance's id, box and score but no mask."""
    instances = [(inst.id, inst.box, inst.score) for inst in result.instances]
    return result.phrase, result.elapsed_s, result.raw, instances


def judge_saved(client, prompt, image, **keywords):
    """The saved answer, asked for as the pipeline asks for it."""
    return client.judge(
        image,
        prompt=prompt.text,
        schema=prompt.schema,
        schema_name=prompt.schema_name,
        **keywords,
    )


def failing(error: Exception, phrase: str):
    """A segment hook that fails `phrase`'s call with `error`, and no other call."""

    def hook(asked: str) -> None:
        if asked == phrase:
            raise error

    return hook


def test_record_then_replay_gives_the_same_outcome(tmp_path, prompt):
    _, sam, given = level_case()
    photo, live, run_dir = record(tmp_path, FakeClient(sam, given), prompt)
    assert live.outcome == KNEE
    client = SavedOutputsClient(run_dir, photo)
    replayed = run_pipeline(photo, client, prompt, phrases=READING_PHRASES)
    assert replayed.outcome == live.outcome
    assert replayed.log["drops"] == live.log["drops"]
    assert replayed.log["instances"] == live.log["instances"]
    # The times and token counts come back too, so the whole log matches (B3).
    assert replayed.log == live.log


@pytest.mark.parametrize(
    ("photo", "given", "outcome", "image", "phrases", "blur_version"),
    [
        # Step 1 stops it before SAM: no image size and no phrase.
        pytest.param(
            flat_jpeg(10),
            None,
            Outcome.refused("too_dark"),
            None,
            [],
            FACE_BLUR_VERSION,
            id="too-dark",
        ),
        # Step 0 refuses the file, so not even the blur version is known.
        pytest.param(
            b"not a jpeg",
            None,
            Outcome.failed("bad_file"),
            None,
            [],
            None,
            id="bad-file",
        ),
        # The gate settles it after SAM and Muse Spark.
        pytest.param(
            None,
            answer(standing_water="no"),
            Outcome.no_flood(),
            {"width": 640, "height": 480},
            list(READING_PHRASES),
            FACE_BLUR_VERSION,
            id="no-flood-seen",
        ),
    ],
)
def test_runs_that_end_early_replay_as_saved(
    tmp_path, prompt, photo, given, outcome, image, phrases, blur_version
):
    _, sam, level_answer = level_case()
    client = FakeClient(sam, level_answer if given is None else given)
    data, live, run_dir = record(tmp_path, client, prompt, photo=photo)
    assert live.outcome == outcome
    saved = read_json(run_dir / "run.json")
    assert saved["image"] == image
    assert saved["phrases"] == phrases
    assert saved["blur_version"] == blur_version
    replayed = run_pipeline(
        data, SavedOutputsClient(run_dir, data), prompt, phrases=READING_PHRASES
    )
    assert replayed.outcome == live.outcome
    assert replayed.log == live.log


def test_saved_layout(tmp_path, prompt):
    _, sam, given = level_case()
    photo, live, run_dir = record(tmp_path, FakeClient(sam, given), prompt)
    names = sorted(
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file()
    )
    stems = ("floodwater", "wheel", "wheel_rim", "person", "vehicle")
    assert names == sorted(
        [
            "run.json",
            "spark.json",
            "spark.raw",
            *(f"sam/{stem}.{ext}" for stem in stems for ext in ("json", "raw")),
            # masks only where SAM found something: no wheel rim and no person
            "sam/floodwater.npz",
            "sam/wheel.npz",
            "sam/vehicle.npz",
        ]
    )
    # The runner never asks for faces or plates (C66).
    assert not any("face" in name or "license_plate" in name for name in names)

    assert read_json(run_dir / "run.json") == {
        "photo": "street.jpg",
        "photo_sha256": hashlib.sha256(photo).hexdigest(),
        "phrases": list(READING_PHRASES),
        "prompt_version": PROMPT_VERSION,
        "schema_name": PROMPT_VERSION,
        "models": {"sam": "sam-3.1", "spark": "muse-spark-1.3"},
        "blur_version": FACE_BLUR_VERSION,
        "image": {"width": 640, "height": 480},
        "outcome": dataclasses.asdict(KNEE),
        "log": json.loads(json.dumps(live.log)),
    }
    assert read_json(run_dir / "sam" / "wheel.json") == {
        "phrase": "wheel",
        "elapsed_s": 0.5,
        "instances": [{"id": 0, "box": [150.0, 250.0, 200.0, 300.0], "score": 0.9}],
    }
    assert read_json(run_dir / "sam" / "wheel_rim.json")["instances"] == []
    spark = read_json(run_dir / "spark.json")
    assert spark == {
        "data": given,
        "input_tokens": 1000,
        "output_tokens": 200,
        "reasoning_tokens": None,
        "elapsed_s": 1.5,
    }
    # Only the offline runner keeps Muse Spark's reason, and only with the answer
    # (C62): run.json's log never has it.
    assert spark["data"]["reason"] == REASON
    assert (run_dir / "spark.raw").read_bytes() == json.dumps(given).encode()
    assert REASON not in (run_dir / "run.json").read_text(encoding="utf-8")


def test_saved_masks_round_trip(tmp_path, prompt):
    # A mask that doesn't fill its box, a match with no score, and raw text with
    # CRLF line ends all come back exactly as SAM gave them.
    _, sam, given = level_case()
    vehicles = [
        instance(0, (100, 100, 400, 300), mask_xyxy=(120, 110, 380, 290)),
        instance(1, (420, 100, 620, 300), score=None),
    ]
    sam["vehicle"] = SamResult("vehicle", vehicles, 0.25, "data: SAM-RAW\r\n\r\n")
    photo, _, run_dir = record(tmp_path, FakeClient(sam, given), prompt)
    with np.load(run_dir / "sam" / "vehicle.npz") as saved:
        assert saved["masks"].shape == (2, 480, 640)
        assert saved["masks"].dtype == bool
    client = SavedOutputsClient(run_dir, photo)
    image = blur_for_meta(photo)
    for phrase in READING_PHRASES:
        got, want = client.segment(image, phrase), sam[phrase]
        assert fields(got) == fields(want)
        for mine, theirs in zip(got.instances, want.instances, strict=True):
            assert mine.mask.dtype == bool
            assert np.array_equal(mine.mask, theirs.mask)


def test_sam_results_round_trip(tmp_path):
    # The sam/ layout on its own, for tools that keep SAM's outputs without a run:
    # every phrase, one with a space and empty ones included, comes back exactly, as
    # from a run folder.
    _, sam, _ = level_case()
    vehicles = [
        instance(0, (100, 100, 400, 300), mask_xyxy=(120, 110, 380, 290)),
        instance(1, (420, 100, 620, 300), score=None),
    ]
    sam["vehicle"] = SamResult("vehicle", vehicles, 0.25, "data: SAM-RAW\r\n\r\n")
    run_dir = tmp_path / "saved"
    save_sam_results(run_dir, sam)
    loaded = load_sam_results(run_dir)
    assert set(loaded) == set(sam)
    for phrase, want in sam.items():
        assert fields(loaded[phrase]) == fields(want)
        for mine, theirs in zip(loaded[phrase].instances, want.instances, strict=True):
            assert mine.mask.dtype == bool
            assert np.array_equal(mine.mask, theirs.mask)
    # The files RecordingClient.save writes: masks only where SAM found something.
    found = ("floodwater", "wheel", "vehicle", "face", "license_plate")
    stems = (*found, "wheel_rim", "person")
    assert sorted(path.name for path in (run_dir / "sam").iterdir()) == sorted(
        [
            *(f"{stem}.{ext}" for stem in stems for ext in ("json", "raw")),
            *(f"{stem}.npz" for stem in found),
        ]
    )
    # A second save would mix two sets of results.
    with pytest.raises(FileExistsError):
        save_sam_results(run_dir, sam)


def test_rebuild_outcome_round_trips():
    # R141: a saved outcome, through JSON as run.json keeps it, rebuilds to the one
    # it was saved from.
    geometry = Outcome.level_result(
        "half_knee",
        "rim_quarter",
        False,
        {"vehicles": 1, "people": 0},
        level_from="geometry",
        depth_in=(7.72, 8.184),
    )
    outcomes = (KNEE, geometry, Outcome.no_flood(), Outcome.refused("too_dark"))
    for outcome in outcomes:
        assert rebuild_outcome(dataclasses.asdict(outcome)) == outcome
        saved = json.loads(json.dumps(dataclasses.asdict(outcome)))
        assert rebuild_outcome(saved) == outcome
    # MS3a saved its outcomes before Task 4's three fields existed. Such a level
    # rebuilds with their defaults, so it counts as a landmark's, as it was.
    ms3a = dataclasses.asdict(KNEE)
    for key in ("level_from", "depth_in_min", "depth_in_max"):
        del ms3a[key]
    rebuilt = rebuild_outcome(ms3a)
    assert (rebuilt.level, rebuilt.level_from) == ("knee", "landmark")
    assert rebuilt == KNEE


def test_a_run_folder_is_written_once(tmp_path, prompt):
    # A second save would mix two runs: an answer left from the first one would
    # answer for a run that got none.
    _, sam, given = level_case()
    photo, _, run_dir = record(tmp_path, FakeClient(sam, given), prompt)
    recorder = RecordingClient(FakeClient(sam, meta_error(500)))
    run = run_pipeline(photo, recorder, prompt, phrases=READING_PHRASES)
    with pytest.raises(FileExistsError):
        recorder.save(run_dir, photo=tmp_path / "street.jpg", prompt=prompt, run=run)
    assert read_json(run_dir / "run.json")["outcome"] == dataclasses.asdict(KNEE)


def test_replay_refuses_another_photo(tmp_path, prompt):
    _, sam, given = level_case()
    _, _, run_dir = record(tmp_path, FakeClient(sam, given), prompt)
    with pytest.raises(ValueError, match="^saved outputs belong to another photo$"):
        SavedOutputsClient(run_dir, noise_jpeg(seed=1))


def test_replay_of_a_model_error(tmp_path, prompt):
    # The live judge failed, so no answer was saved, and the replay fails too.
    _, sam, _ = level_case()
    photo, live, run_dir = record(tmp_path, FakeClient(sam, meta_error(500)), prompt)
    assert live.outcome == Outcome.failed("model_error")
    assert not (run_dir / "spark.json").exists()
    assert not (run_dir / "spark.raw").exists()
    client = SavedOutputsClient(run_dir, photo)
    replayed = run_pipeline(photo, client, prompt, phrases=READING_PHRASES)
    assert replayed.outcome == live.outcome
    assert replayed.log["error"] == "ModelAnswerError"
    with pytest.raises(ModelAnswerError):
        judge_saved(client, prompt, blur_for_meta(photo))


def test_replay_of_a_refusal(tmp_path, prompt):
    # R109: Muse Spark refused (C86). The refusal is kept with no text, as
    # ModelRefused carries none, and the replay refuses the same way.
    _, sam, _ = level_case()
    refusal = ModelRefused("Muse Spark refused to answer")
    photo, live, run_dir = record(tmp_path, FakeClient(sam, refusal), prompt)
    assert live.outcome == Outcome.refused("model_declined")
    assert read_json(run_dir / "spark.json") == {"refused": True}
    assert not (run_dir / "spark.raw").exists()
    client = SavedOutputsClient(run_dir, photo)
    replayed = run_pipeline(photo, client, prompt, phrases=READING_PHRASES)
    assert replayed.outcome == live.outcome
    assert replayed.log == live.log
    # The schema name is still checked first.
    image = blur_for_meta(photo)
    other = dataclasses.replace(prompt, schema_name="muse_spark_photo_v2")
    with pytest.raises(ValueError, match="another schema"):
        judge_saved(client, other, image)
    with pytest.raises(ModelRefused):
        judge_saved(client, prompt, image)
    # The recording raises the live refusal itself, unchanged.
    with pytest.raises(ModelRefused) as exc:
        judge_saved(RecordingClient(FakeClient(sam, refusal)), prompt, image)
    assert exc.value is refusal


@pytest.mark.parametrize(
    ("phrase", "error", "phrases", "reason", "status"),
    [
        pytest.param(
            "wheel", meta_error(500), READING_PHRASES, "model_error", 500, id="500"
        ),
        pytest.param(
            "wheel",
            MetaApiError("connection failed or timed out"),
            READING_PHRASES,
            "model_error",
            None,
            id="timeout",
        ),
        # Asked for, a face is replayed like any other phrase, never as empty.
        pytest.param(
            "face", meta_error(503), SAM_PHRASES, "model_error", 503, id="face-503"
        ),
        # Not Meta's failure: the log has no meta_status.
        pytest.param(
            "wheel",
            AttributeError("boom"),
            READING_PHRASES,
            "pipeline_error",
            "absent",
            id="not-meta",
        ),
        pytest.param(
            "face",
            AttributeError("boom"),
            SAM_PHRASES,
            "pipeline_error",
            "absent",
            id="face-not-meta",
        ),
    ],
)
def test_replay_of_a_failed_sam_call(
    tmp_path, prompt, phrase, error, phrases, reason, status
):
    # R109: the failed call saved no result, and the replay fails the same way.
    _, sam, given = level_case()
    fake = FakeClient(sam, given, on_segment=failing(error, phrase))
    photo, live, run_dir = record(tmp_path, fake, prompt, phrases=phrases)
    assert live.outcome == Outcome.failed(reason)
    assert not (run_dir / "sam" / f"{phrase.replace(' ', '_')}.json").exists()
    assert phrase in read_json(run_dir / "run.json")["phrases"]
    client = SavedOutputsClient(run_dir, photo)
    replayed = run_pipeline(photo, client, prompt, phrases=phrases)
    assert replayed.outcome == live.outcome
    if status == "absent":
        assert "meta_status" not in live.log
        assert "meta_status" not in replayed.log
    else:
        assert live.log["meta_status"] == replayed.log["meta_status"] == status


def test_faces_and_plates_come_back_empty_when_not_saved(tmp_path, prompt):
    # The runner never asks for them (C66), but the handler's pipeline call asks for
    # all 7 phrases. Replayed through it, they come back empty, and the level result
    # stands, with a photo to store (B3).
    _, sam, given = level_case()
    photo, live, run_dir = record(tmp_path, FakeClient(sam, given), prompt)
    client = SavedOutputsClient(run_dir, photo)
    replayed = run_pipeline(photo, client, prompt)
    assert replayed.outcome == live.outcome == KNEE
    assert replayed.log["instances"]["face"] == 0
    assert replayed.log["instances"]["license plate"] == 0
    assert replayed.publish_jpeg is not None
    image = blur_for_meta(photo)
    for phrase in ("face", "license plate"):
        assert client.segment(image, phrase) == SamResult(phrase, [], 0.0, "")


def test_other_phrases_must_have_been_saved(tmp_path, prompt):
    # Any other phrase the live run didn't save has no stand-in.
    _, sam, given = level_case()
    phrases = ("floodwater", "vehicle")
    photo, _, run_dir = record(
        tmp_path, FakeClient(sam, given), prompt, phrases=phrases
    )
    assert read_json(run_dir / "run.json")["phrases"] == list(phrases)
    client = SavedOutputsClient(run_dir, photo)
    image = blur_for_meta(photo)
    assert len(client.segment(image, "vehicle").instances) == 1
    with pytest.raises(KeyError):
        client.segment(image, "wheel")


def test_replay_checks_the_image_size(tmp_path, prompt):
    _, sam, given = level_case()
    photo, _, run_dir = record(tmp_path, FakeClient(sam, given), prompt)
    client = SavedOutputsClient(run_dir, photo)
    with pytest.raises(ValueError, match="another size"):
        client.segment(blur_for_meta(noise_jpeg(320, 240)), "wheel")


def test_replay_checks_the_schema_name(tmp_path, prompt):
    _, sam, given = level_case()
    photo, _, run_dir = record(tmp_path, FakeClient(sam, given), prompt)
    client = SavedOutputsClient(run_dir, photo)
    image = blur_for_meta(photo)
    assert judge_saved(client, prompt, image).data == given
    other = dataclasses.replace(
        prompt, version="muse_spark_photo_v2", schema_name="muse_spark_photo_v2"
    )
    with pytest.raises(ValueError, match="another schema"):
        judge_saved(client, other, image)
    # So another prompt version can't reuse the saved answer through the pipeline.
    replayed = run_pipeline(photo, client, other, phrases=READING_PHRASES)
    assert replayed.outcome == Outcome.failed("pipeline_error")


def test_keywords_pass_through_the_recording_and_replays_ignore_them(tmp_path, prompt):
    # R108: the deadline and the reasoning effort reach the real client unchanged.
    _, sam, given = level_case()
    fake = FakeClient(sam, given)
    photo, live, run_dir = record(tmp_path, fake, prompt, deadline=123.0)
    assert [keywords["deadline"] for keywords in fake.keywords] == [123.0] * 6
    image = blur_for_meta(photo)
    recorder = RecordingClient(fake)
    recorder.segment(image, "wheel", deadline=7.0)
    judge_saved(recorder, prompt, image, deadline=7.0, reasoning_effort="low")
    assert fake.keywords[-2:] == [
        {"deadline": 7.0},
        {"deadline": 7.0, "reasoning_effort": "low"},
    ]
    # A replay makes no Meta call, so a deadline long past changes nothing.
    client = SavedOutputsClient(run_dir, photo)
    replayed = run_pipeline(
        photo, client, prompt, phrases=READING_PHRASES, deadline=0.0
    )
    assert replayed.outcome == live.outcome
    assert client.segment(image, "wheel", deadline=0.0).instances
    spark = judge_saved(client, prompt, image, deadline=0.0, reasoning_effort="high")
    assert spark.data == given


class ReasoningClient(FakeClient):
    """A FakeClient whose answers report 321 reasoning tokens, as Meta's may."""

    def judge(self, image, **keywords):
        return dataclasses.replace(
            super().judge(image, **keywords), reasoning_tokens=321
        )


@pytest.mark.parametrize(
    ("client_class", "reasoning"),
    [(FakeClient, None), (ReasoningClient, 321)],
    ids=["not-reported", "reported"],
)
def test_the_answer_comes_back_whole(tmp_path, prompt, client_class, reasoning):
    # R108: reasoning_tokens is kept, as None when Meta didn't report it.
    _, sam, given = level_case()
    photo, _, run_dir = record(tmp_path, client_class(sam, given), prompt)
    assert read_json(run_dir / "spark.json")["reasoning_tokens"] == reasoning
    client = SavedOutputsClient(run_dir, photo)
    assert judge_saved(client, prompt, blur_for_meta(photo)) == SparkResult(
        data=given,
        input_tokens=1000,
        output_tokens=200,
        elapsed_s=1.5,
        raw=json.dumps(given),
        reasoning_tokens=reasoning,
    )
