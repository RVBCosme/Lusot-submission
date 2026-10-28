"""The analysis pipeline, one module per step (spec §3.2).

run_pipeline is the one pipeline function. The Lambda's handler and the laptop's
offline runner both call it, so the same model outputs give the same result on both
(B3).
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from lusot_analysis.annotate import (
    check_ids_per_item,
    draw_numbered_boxes,
    number_boxes,
)
from lusot_analysis.face_blur import UndecodableImage, blur_for_meta
from lusot_analysis.meta_client import (
    SAM_MODEL,
    SAM_PHRASES,
    SPARK_MODEL,
    MetaApiError,
    ModelRefused,
)
from lusot_analysis.pipeline.combine import combine
from lusot_analysis.pipeline.measure import measure
from lusot_analysis.pipeline.publish import PUBLISH_PHRASES, publish_jpeg
from lusot_analysis.pipeline.quality import quality_refusal, quality_scores
from lusot_analysis.pipeline.references import (
    apply_drops,
    gate,
    layout,
    prepare_boxes,
    validate_answer,
    water_found,
)
from lusot_analysis.pipeline.segment import segment_all
from lusot_analysis.pipeline.types import (
    ModelAnswerError,
    ModelClient,
    ModelKeyRejected,
    Outcome,
)
from lusot_analysis.prompts import PromptSpec

# The phrases the reading uses: SAM_PHRASES without the two that only the publish
# blur reads. The offline runner sends these, since nothing it makes is stored (C66).
READING_PHRASES = tuple(p for p in SAM_PHRASES if p not in PUBLISH_PHRASES)
# Meta's statuses for a rejected key or account, which aren't the photo's fault (C73).
_KEY_REJECTED = frozenset({401, 402, 403})


@dataclass(frozen=True)
class PipelineRun:
    """How a report ends, its log fields, and the photo to store, if any.

    `publish_jpeg` is set on a level result only, with SAM's faces and plates blurred
    (C48, C61). The run holds no answer, so Muse Spark's reason never reaches the
    handler (C62).
    """

    outcome: Outcome
    log: dict[str, object]
    publish_jpeg: bytes | None


def run_pipeline(
    data: bytes,
    client: ModelClient,
    prompt: PromptSpec,
    *,
    phrases: Sequence[str] = SAM_PHRASES,
    deadline: float | None = None,
) -> PipelineRun:
    """Run spec §3.2's steps on one uploaded photo, in order.

    `phrases` are SAM's requests: SAM_PHRASES in the Lambda, READING_PHRASES offline
    (C66). A level result gets a photo to store only when both PUBLISH_PHRASES ran.
    `deadline` is the run's deadline as a time.monotonic() value, and every segment
    and judge call gets it (C84); None sets none. A file blur_for_meta refuses ends
    failed, bad_file, before any Meta call.

    Errors end as outcomes (C59), checked in this order:
    - Muse Spark refused to answer: refused, model_declined (C86).
    - A MetaApiError with status 401, 402 or 403 raises ModelKeyRejected instead: the
      key or the account was rejected, not the photo (C73).
    - Any other MetaApiError, timeouts and the deadline included, and an answer that
      isn't JSON or fails the schema: failed, model_error (C47). Nothing is retried.
    - Any other exception: failed, pipeline_error.

    The log gains each step's fields once the step runs (spec §3.6, C80).
    `meta_calls` counts the segment and judge calls made, failed ones included. A
    failure adds the error's class name and, for a MetaApiError, its status, never
    its message. Muse Spark's reason never reaches the log (C62).
    """
    log: dict[str, object] = {"meta_calls": 0}
    try:
        outcome, photo = _run_steps(data, client, prompt, phrases, deadline, log)
    except ModelRefused:
        return PipelineRun(Outcome.refused("model_declined"), log, None)
    except MetaApiError as exc:  # before Exception, as it is a RuntimeError
        if exc.status in _KEY_REJECTED:
            raise ModelKeyRejected(exc.status) from exc
        log |= {"error": type(exc).__name__, "meta_status": exc.status}
        return PipelineRun(Outcome.failed("model_error"), log, None)
    except ModelAnswerError as exc:
        log["error"] = type(exc).__name__
        return PipelineRun(Outcome.failed("model_error"), log, None)
    except Exception as exc:  # noqa: BLE001
        # Anything else is the pipeline's own fault (C59), logged by class name only.
        log["error"] = type(exc).__name__
        return PipelineRun(Outcome.failed("pipeline_error"), log, None)
    return PipelineRun(outcome, log, photo)


def _run_steps(
    data: bytes,
    client: ModelClient,
    prompt: PromptSpec,
    phrases: Sequence[str],
    deadline: float | None,
    log: dict[str, object],
) -> tuple[Outcome, bytes | None]:
    """The steps, adding each one's fields to `log` as it runs. Errors propagate."""
    # Step 0: the face blur, before any Meta call (C20).
    try:
        image = blur_for_meta(data)
    except UndecodableImage:  # undecodable, over 50 MP, or 32 px or less (R27)
        return Outcome.failed("bad_file"), None
    log |= {"blur_version": image.blur_version, "face_boxes": image.faces}

    # Step 1: the quality gate, on the photo before the face blur (C44, C58).
    scores = quality_scores(data)
    log |= {
        "brightness": round(scores.brightness, 1),
        "sharpness": round(scores.sharpness, 1),
    }
    refusal = quality_refusal(scores)
    if refusal is not None:
        return Outcome.refused(refusal), None

    # Step 2: SAM, every phrase at once. A scene with no water or no reference still
    # goes on to Muse Spark (D14, C51).
    log |= {
        "models": {"sam": SAM_MODEL, "spark": SPARK_MODEL},
        "prompt_version": prompt.version,
        "meta_calls": len(phrases),
    }
    sam = segment_all(client, image, phrases, deadline=deadline)
    log["sam_ms"] = {phrase: _ms(result.elapsed_s) for phrase, result in sam.items()}
    log["instances"] = {phrase: len(result.instances) for phrase, result in sam.items()}

    # Step 4: the references. Only the boxes the cuts keep get numbers (C69, C70).
    prepared = prepare_boxes(sam)
    drops = Counter(prepared.drops)
    log["drops"] = drops  # the later steps' drops are added to it
    boxes = number_boxes(prepared.sam)
    links = layout(prepared, boxes)
    kinds = Counter(box.kind for box in boxes)
    log["numbered"] = {
        "vehicles": kinds["vehicle"],
        "wheels": kinds["wheel"],
        "people": kinds["person"],
    }
    drawn = draw_numbered_boxes(image, boxes)
    log["meta_calls"] = len(phrases) + 1
    try:  # one paid answer, never asked for again (C47)
        spark = client.judge(
            drawn,
            prompt=prompt.text,
            schema=prompt.schema,
            schema_name=prompt.schema_name,
            deadline=deadline,
        )
    except json.JSONDecodeError as exc:  # judge's own json.loads (R62)
        raise ModelAnswerError("Muse Spark's answer isn't JSON") from exc
    log |= {
        "spark_ms": _ms(spark.elapsed_s),
        "input_tokens": spark.input_tokens,
        "output_tokens": spark.output_tokens,
    }
    validate_answer(spark.data, prompt.schema)
    answer, id_drops = check_ids_per_item(spark.data, boxes)
    drops.update(id_drops)
    settled = gate(answer, has_water=water_found(sam["floodwater"]))
    if settled is not None:
        return settled, None
    kept, kept_drops = apply_drops(answer, links)
    drops.update(kept_drops)

    # Step 5: a reading for each kept vehicle and adult. Steps 6 and 7: the level.
    references, measure_drops = measure(kept)
    drops.update(measure_drops)
    outcome, deciding = combine(references)
    if deciding is None:  # a refusal
        return outcome, None

    # Step 8.1: the photo to store, with SAM's faces and plates blurred (C48, C61).
    photo = None
    if all(phrase in phrases for phrase in PUBLISH_PHRASES):
        photo = publish_jpeg(image, sam)
    log["deciding"] = deciding.kind
    return outcome, photo


def _ms(seconds: float) -> int:
    """Seconds as whole milliseconds, as the Meta client logs its calls."""
    return round(seconds * 1000)
