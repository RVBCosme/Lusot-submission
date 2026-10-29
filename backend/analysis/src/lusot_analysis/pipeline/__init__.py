"""The analysis pipeline, one module per step (spec §3.2).

run_pipeline is the one pipeline function. The Lambda's handler and the laptop's
offline runner both call it, so the same model outputs give the same result on both
(B3).
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from lusot_analysis import rules
from lusot_analysis.annotate import (
    DRAWINGS,
    NumberedBox,
    check_ids_per_item,
    draw_numbered_boxes,
    number_boxes,
)
from lusot_analysis.face_blur import UndecodableImage, blur_for_meta
from lusot_analysis.meta_client import (
    REASONING_EFFORTS,
    SAM_MODEL,
    SAM_PHRASES,
    SPARK_MODEL,
    MetaApiError,
    ModelRefused,
    SamInstance,
    SamResult,
)
from lusot_analysis.pipeline.combine import combine
from lusot_analysis.pipeline.evidence import Evidence, build_evidence
from lusot_analysis.pipeline.geometry import (
    GeometryReading,
    link_rims,
    wheel_geometry,
)
from lusot_analysis.pipeline.measure import measure_boxes
from lusot_analysis.pipeline.publish import PUBLISH_PHRASES, publish_jpeg
from lusot_analysis.pipeline.quality import quality_refusal, quality_scores
from lusot_analysis.pipeline.references import (
    Kept,
    apply_drops,
    gate,
    instances_by_id,
    layout,
    prepare_boxes,
    validate_answer,
    water_found,
)
from lusot_analysis.pipeline.segment import box_xyxy, segment_all
from lusot_analysis.pipeline.types import (
    KEY_REJECTED_STATUSES,
    ModelAnswerError,
    ModelClient,
    ModelKeyRejected,
    Outcome,
)
from lusot_analysis.pipeline.waterline import Waterline, find_waterline, water_mask
from lusot_analysis.prompts import PromptSpec
from lusot_analysis.tuning import TUNING, Tuning

# The phrases the reading uses: SAM_PHRASES without the two that only the publish
# blur reads. The offline runner sends these, since nothing it makes is stored (C66).
READING_PHRASES = tuple(p for p in SAM_PHRASES if p not in PUBLISH_PHRASES)


@dataclass(frozen=True)
class PipelineRun:
    """How a report ends, its log fields, the photo to store, and the evidence record.

    `publish_jpeg` is set on a level result only, with SAM's faces and plates blurred
    (C48, C61). The run holds no answer, so Muse Spark's reason never reaches the
    handler (C62).

    `evidence` is the record MS4 draws from (C328). It is set once Muse Spark's
    answer has passed the schema and the id check, on a gate result too, and is None
    before that and on every error path. It holds no reason either, and never joins
    the log.
    """

    outcome: Outcome
    log: dict[str, object]
    publish_jpeg: bytes | None
    evidence: Evidence | None = None


def run_pipeline(
    data: bytes,
    client: ModelClient,
    prompt: PromptSpec,
    *,
    phrases: Sequence[str] = SAM_PHRASES,
    deadline: float | None = None,
    geometry_in_level: bool = False,
    tuning: Tuning = TUNING,
) -> PipelineRun:
    """Run spec §3.2's steps on one uploaded photo, in order, with MS3b's (its §4).

    `phrases` are SAM's requests: SAM_PHRASES in the Lambda, READING_PHRASES offline
    (C66). A level result gets a photo to store only when both PUBLISH_PHRASES ran.
    `deadline` is the run's deadline as a time.monotonic() value, and every segment
    and judge call gets it (C84); None sets none. A file blur_for_meta refuses ends
    failed, bad_file, before any Meta call.

    `geometry_in_level` puts rim geometry in the level path (C309). Off is MS3a's
    rules plus step 3, so vans and `unknown` are dropped by type and no geometry is
    computed. `tuning` gives the cutoffs: the quality gate's, step 3's and the
    geometry checks' (C310). Step 3 runs either way, after the gate (C317). It also
    gives what Muse Spark is sent: its reasoning effort and the boxes' drawing (C312,
    C325). The handler and the offline runner take the default, TUNING. An effort
    Muse Spark doesn't take, or a drawing annotate doesn't know, raises ValueError
    before the face blur, so it ends failed, pipeline_error, with no Meta call (R146).

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
    its message. Muse Spark's reason never reaches the log (C62). C316's fields:
    - from step 2 on: `geometry_in_level` ("on" or "off"), `tuning_version`,
      `rim_edge_k`, k, `reasoning_effort` (the tuning's, or "default" when none is
      sent) and `drawing_version`
    - once Muse Spark has answered: `reasoning_tokens`, or None when Meta doesn't
      report it
    - with geometry on, once its checks run: `wheels_measured` and `geometry_checks`,
      each failed check counted by cause
    - on a level result: `level_from`, and `depth_in` when it is "geometry": the
      inches as the item stores them, [min, max] rounded outward (C308)
    """
    log: dict[str, object] = {"meta_calls": 0}
    try:
        outcome, photo, evidence = _run_steps(
            data,
            client,
            prompt,
            phrases,
            deadline,
            log,
            geometry_in_level=geometry_in_level,
            tuning=tuning,
        )
    except ModelRefused:
        return PipelineRun(Outcome.refused("model_declined"), log, None)
    except MetaApiError as exc:  # before Exception, as it is a RuntimeError
        if exc.status in KEY_REJECTED_STATUSES:
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
    return PipelineRun(outcome, log, photo, evidence)


def _run_steps(
    data: bytes,
    client: ModelClient,
    prompt: PromptSpec,
    phrases: Sequence[str],
    deadline: float | None,
    log: dict[str, object],
    *,
    geometry_in_level: bool,
    tuning: Tuning,
) -> tuple[Outcome, bytes | None, Evidence | None]:
    """The steps, adding each one's fields to `log` as it runs. Errors propagate.

    It returns the outcome, the photo to store, and the evidence record, which is
    None until the answer passes the id check (C328).
    """
    # What Muse Spark is to be sent, checked before anything is paid for (R146).
    effort = tuning.reasoning_effort
    if effort is not None and effort not in REASONING_EFFORTS:
        raise ValueError(
            f"reasoning effort {effort!r} isn't one of {REASONING_EFFORTS}"
        )
    if tuning.drawing not in DRAWINGS:
        raise ValueError(f"drawing {tuning.drawing!r} isn't one of {DRAWINGS}")

    # Step 0: the face blur, before any Meta call (C20).
    try:
        image = blur_for_meta(data)
    except UndecodableImage:  # undecodable, over 50 MP, or 32 px or less (R27)
        return Outcome.failed("bad_file"), None, None
    log |= {"blur_version": image.blur_version, "face_boxes": image.faces}

    # Step 1: the quality gate, on the photo before the face blur (C44, C58).
    scores = quality_scores(data)
    log |= {
        "brightness": round(scores.brightness, 1),
        "sharpness": round(scores.sharpness, 1),
    }
    refusal = quality_refusal(scores, tuning)
    if refusal is not None:
        return Outcome.refused(refusal), None, None

    # Step 2: SAM, every phrase at once. A scene with no water or no reference still
    # goes on to Muse Spark (D14, C51).
    log |= {
        "models": {"sam": SAM_MODEL, "spark": SPARK_MODEL},
        "prompt_version": prompt.version,
        "geometry_in_level": "on" if geometry_in_level else "off",  # C309, C316
        "tuning_version": tuning.version,
        "rim_edge_k": tuning.rim_edge_k,
        "reasoning_effort": tuning.reasoning_effort or "default",  # C312
        "drawing_version": tuning.drawing,  # C325
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
    instances = instances_by_id(prepared, links)
    # Step 2's rim links (C300), with geometry on or off: they are box logic only.
    # `rims` keeps each wheel's one linked rim for the evidence record, which draws
    # it either way (C328, R127). A wheel with none, or with several, is left out.
    linked = _rim_links(sam, boxes, instances)
    rims = {w: found[0] for w, found in linked.items() if len(found) == 1}
    kinds = Counter(box.kind for box in boxes)
    log["numbered"] = {
        "vehicles": kinds["vehicle"],
        "wheels": kinds["wheel"],
        "people": kinds["person"],
    }
    drawn = draw_numbered_boxes(image, boxes, drawing=tuning.drawing)
    log["meta_calls"] = len(phrases) + 1
    try:  # one paid answer, never asked for again (C47)
        spark = client.judge(
            drawn,
            prompt=prompt.text,
            schema=prompt.schema,
            schema_name=prompt.schema_name,
            deadline=deadline,
            reasoning_effort=tuning.reasoning_effort,
        )
    except json.JSONDecodeError as exc:  # judge's own json.loads (R62)
        raise ModelAnswerError("Muse Spark's answer isn't JSON") from exc
    log |= {
        "spark_ms": _ms(spark.elapsed_s),
        "input_tokens": spark.input_tokens,
        "output_tokens": spark.output_tokens,
        "reasoning_tokens": spark.reasoning_tokens,
    }
    validate_answer(spark.data, prompt.schema)
    answer, id_drops = check_ids_per_item(spark.data, boxes)
    drops.update(id_drops)
    # SAM's water as one mask: step 3 reads it, and the evidence record outlines it,
    # on a gate result too (C328).
    water = water_mask(sam["floodwater"], (image.height, image.width))
    settled = gate(answer, has_water=water_found(sam["floodwater"]))
    if settled is not None:  # no box has a reading yet, and step 3 hasn't run
        evidence = build_evidence(
            boxes,
            instances,
            answer,
            water,
            rims=rims,
            causes={},
            readings={},
            waterlines={},
            geometry={},
            used=frozenset(),
            deciding=None,
        )
        return settled, None, evidence
    # With geometry on, vans and `unknown` are kept for geometry alone (C318).
    geometry_types = rules.GEOMETRY_ONLY_TYPES if geometry_in_level else frozenset()
    kept, kept_drops = apply_drops(answer, links, geometry_types=geometry_types)
    drops.update(kept_drops)

    # Step 3, after the gate, beside the drops above (C317): the waterline under each
    # kept reference that gives a reading. A reference it drops never decides.
    waterlines = _waterlines(kept, instances, water, tuning)
    step3_drops = {i: w.cause for i, w in waterlines.items() if w.cause is not None}

    # Steps 4 and 5 of spec §4, with geometry on: each kept vehicle's wheels.
    geometry: dict[int, GeometryReading] = {}
    if geometry_in_level:
        geometry, checks = _wheel_geometry(
            kept, instances, linked, waterlines, scores.brightness, tuning
        )
        log |= {"wheels_measured": len(geometry), "geometry_checks": checks}

    # Step 5: a reading for each kept vehicle and adult. Steps 6 and 7: the level.
    # Step 3's causes and wheel_methods_disagree join the drops here.
    measured = measure_boxes(kept, step3_drops=step3_drops, geometry=geometry)
    drops.update(measured.drops)
    outcome, deciding = combine(measured.references)
    # The evidence record, from what the steps above hold (C328). Only a reading that
    # can decide is used (C317, R147). A box apply_drops dropped never reaches
    # measure_boxes, so the two maps of causes never share a box.
    evidence = build_evidence(
        boxes,
        instances,
        answer,
        water,
        rims=rims,
        causes={**kept.causes, **measured.causes},
        readings=measured.readings,
        waterlines=waterlines,
        geometry=geometry,
        used=frozenset(r.box_id for r in measured.references if r.decides),
        deciding=None if deciding is None else deciding.box_id,
    )
    if deciding is None:  # a refusal
        return outcome, None, evidence

    # Step 8.1: the photo to store, with SAM's faces and plates blurred (C48, C61).
    photo = None
    if all(phrase in phrases for phrase in PUBLISH_PHRASES):
        photo = publish_jpeg(image, sam)
    log |= {"deciding": deciding.kind, "level_from": outcome.level_from}
    if outcome.level_from == "geometry":  # as the item stores them (C308)
        low, high = rules.round_out(outcome.depth_in_min, outcome.depth_in_max)
        log["depth_in"] = [low, high]
    return outcome, photo, evidence


def _rim_links(
    sam: Mapping[str, SamResult],
    boxes: Sequence[NumberedBox],
    instances: Mapping[int, SamInstance],
) -> dict[int, tuple[SamInstance, ...]]:
    """Each numbered wheel's linked rims, by its box id (C300).

    The links are made among all of SAM's wheels, before the cuts, as C55 links
    wheels among all of SAM's vehicles. So a rim inside a cut wheel's box joins no
    kept wheel, and each kept wheel takes only its own rims (P14). A kept wheel is
    SAM's own instance, so it is found by identity.
    """
    wheels = sam["wheel"].instances
    links = link_rims(wheels, sam["wheel rim"].instances)
    by_wheel = {id(wheel): found for wheel, found in zip(wheels, links, strict=True)}
    return {
        box.id: by_wheel[id(instances[box.id])] for box in boxes if box.kind == "wheel"
    }


def _waterlines(
    kept: Kept,
    instances: Mapping[int, SamInstance],
    water: np.ndarray,
    tuning: Tuning,
) -> dict[int, Waterline]:
    """Step 3's waterline for each kept reference that gives a reading, by box id.

    Those are each kept vehicle's wheels answered other than not_visible, its body
    when it gives C53's reading (a sedan or SUV whose wheels are hidden, at a body row
    that reads), and each kept adult whose waterline reads (C317).
    """
    ids: list[int] = []
    for vehicle in kept.vehicles:
        ids += [w for w, line in vehicle.wheels if line != "not_visible"]
        body_reads = (
            vehicle.vehicle_type in rules.READING_TYPES
            and vehicle.wheels_hidden
            and rules.BODY_ROWS[vehicle.body_waterline] is not None
        )
        if body_reads:  # C53
            ids.append(vehicle.id)
    ids += [p.id for p in kept.people if rules.PEOPLE_ROWS[p.waterline] is not None]
    return {i: find_waterline(instances[i].mask, water, tuning) for i in ids}


def _wheel_geometry(
    kept: Kept,
    instances: Mapping[int, SamInstance],
    linked: Mapping[int, Sequence[SamInstance]],
    waterlines: Mapping[int, Waterline],
    brightness: float,
    tuning: Tuning,
) -> tuple[dict[int, GeometryReading], Counter[str]]:
    """Spec §4's steps 4 and 5 for each answered wheel of a kept vehicle.

    It returns the geometry readings by wheel id, and how many wheels failed each
    check. `brightness` is the quality gate's score (check 4), and a wheel's box is
    SAM's (checks 6 and 9).
    """
    readings: dict[int, GeometryReading] = {}
    checks: Counter[str] = Counter()
    for vehicle in kept.vehicles:
        codes = rules.tire_codes(vehicle.vehicle_type)
        for wheel_id, line in vehicle.wheels:
            reading = wheel_geometry(
                answer_waterline=line,
                codes=codes,
                rims=linked[wheel_id],
                waterline=waterlines.get(wheel_id),
                wheel_box=box_xyxy(instances[wheel_id]),
                brightness=brightness,
                tuning=tuning,
            )
            if isinstance(reading, str):
                checks[reading] += 1
            else:
                readings[wheel_id] = reading
    return readings, checks


def _ms(seconds: float) -> int:
    """Seconds as whole milliseconds, as the Meta client logs its calls."""
    return round(seconds * 1000)
