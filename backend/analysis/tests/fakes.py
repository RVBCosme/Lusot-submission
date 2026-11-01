"""Builders the tests share.

pytest doesn't collect this module, because its name doesn't start with `test_`.
"""

import dataclasses
import io
import json
import math
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import NoReturn

import cv2
import numpy as np
from botocore.awsrequest import AWSResponse
from botocore.retries.standard import ExponentialBackoff

from lusot_analysis.face_blur import BlurredImage
from lusot_analysis.meta_client import (
    SAM_PHRASES,
    MetaApiError,
    SamInstance,
    SamResult,
    SparkResult,
)

SIZE = (640, 480)  # width, height
REPO_PROMPTS = Path(__file__).parents[1] / "prompts"  # the repo's prompt files


def create_reports_table(ddb, name: str) -> None:
    """The reports table with its keys and `reportId-index`, as in the template."""
    ddb.create_table(
        TableName=name,
        AttributeDefinitions=[
            {"AttributeName": attribute, "AttributeType": "S"}
            for attribute in ("pk", "sk", "reportId")
        ],
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "reportId-index",
                "KeySchema": [{"AttributeName": "reportId", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            }
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 10, "WriteCapacityUnits": 5},
    )


def create_limits_table(ddb, name: str) -> None:
    """The limits table, as in the template: one key, `pk`."""
    ddb.create_table(
        TableName=name,
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
        ProvisionedThroughput={"ReadCapacityUnits": 2, "WriteCapacityUnits": 2},
    )


class _Body(io.BytesIO):
    """A response body as botocore reads one: `stream()` yields its bytes."""

    def stream(self, **kwargs: object):
        chunk = self.read()
        while chunk:
            yield chunk
            chunk = self.read()


def fail_attempts(
    client, operation: str, code: str, status: int, times: int | None = None
) -> list[str]:
    """Answer the client's next `times` attempts at `operation` with AWS error `code`.

    Every attempt fails when `times` is None. The answer comes at botocore's
    before-send event, registered first, ahead of moto's own hook, so botocore's own
    retry handler reads it as the service's answer. botocore still calls every
    before-send handler, moto's too, so a failed attempt's request is also pointed at
    a host moto serves nothing at: moto never applies it, as the service never applies
    a throttled or refused write. botocore makes a new request for each retry, so the
    next attempt goes to moto unchanged. An attempt past `times` goes on to moto.
    Returns a list that gains each attempt's fate, "failed" or "sent", in order. The
    error's message holds an ARN, as AccessDenied messages do. The body is AWS's JSON
    protocol, as DynamoDB uses.
    """
    attempts: list[str] = []
    service = client.meta.service_model.service_id.hyphenize()

    def answer(request, **kwargs):
        if times is not None and len(attempts) >= times:
            attempts.append("sent")
            return None
        attempts.append("failed")
        url, request.url = request.url, "https://never-applied.invalid/"
        body = {
            "__type": code,
            "message": "User: arn:aws:sts::account-id:assumed-role/lusot-role/s"
            " is not authorized to perform this action",
        }
        headers = {
            "x-amzn-ErrorType": code,
            "Content-Type": "application/x-amz-json-1.0",
        }
        return AWSResponse(url, status, headers, _Body(json.dumps(body).encode()))

    client.meta.events.register_first(f"before-send.{service}.{operation}", answer)
    return attempts


def no_backoff(monkeypatch) -> None:
    """botocore's standard-mode retries wait 0 s, not their backoff, in this test."""
    monkeypatch.setattr(ExponentialBackoff, "delay_amount", lambda self, context: 0)


def noise_jpeg(width: int = 640, height: int = 480, seed: int = 0) -> bytes:
    """Colour noise as a JPEG: bright and sharp, with no face in it."""
    bgr = np.random.default_rng(seed).integers(0, 256, (height, width, 3), np.uint8)
    return _jpeg(bgr)


def flat_jpeg(value: int, width: int = 640, height: int = 480) -> bytes:
    """One grey `value` everywhere, as a JPEG: no detail at all."""
    return _jpeg(np.full((height, width, 3), value, np.uint8))


def around(
    cx: float, cy: float, width: float = 40.0, height: float = 40.0
) -> tuple[float, float, float, float]:
    """The (x0, y0, x1, y1) box of `width` x `height` centred on (cx, cy)."""
    return cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2


def instance(
    i: int,
    xyxy: tuple[float, float, float, float],
    *,
    size: tuple[int, int] = SIZE,
    mask_xyxy: tuple[float, float, float, float] | None = None,
    score: float | None = 0.9,
    mask: np.ndarray | None = None,
) -> SamInstance:
    """SAM's match `i`, its box `xyxy` kept as MS1's client keeps it.

    The box is (x0, y0, x1, y1), half-open, in pixels of an image of `size`, so
    box_xyxy reads it back unchanged. The mask is True inside `mask_xyxy`, rounded
    outward (floor the start, ceil the end), which defaults to the box. Both boxes
    must lie inside the image, as the client requires of SAM's. A `mask` given is the
    match's mask itself, and overrides `mask_xyxy`.
    """
    width, height = size
    mask_box = xyxy if mask_xyxy is None else mask_xyxy
    for box in (xyxy, mask_box):
        x0, y0, x1, y1 = box
        if not (0 <= x0 <= x1 <= width and 0 <= y0 <= y1 <= height):
            raise ValueError(f"{box} isn't inside a {width} x {height} image")
    if mask is None:
        x0, y0, x1, y1 = mask_box
        mask = np.zeros((height, width), bool)
        mask[math.floor(y0) : math.ceil(y1), math.floor(x0) : math.ceil(x1)] = True
    return SamInstance(i, tuple(float(v) for v in xyxy), mask, score)


def wheel_scene(
    *,
    centre: tuple[int, int] = (320, 240),
    tire_r: int = 57,
    rim_r: int = 35,
    y_true: int = 257,
    seam: int = 0,
    reflection: str = "none",
    ripple: float = 0,
    squash: float = 1.0,
    size: tuple[int, int] = SIZE,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The (wheel, rim, water) bool masks of a wheel standing in water at `y_true`.

    The wheel and the rim are filled ellipses with vertical semi-axis r and
    horizontal semi-axis `squash` x r, centred on pixel `centre`. A pixel is in one
    when its centre lies on or within the ellipse: pixel (x, y) when
    ((x - cx) / (squash x r))^2 + ((y - cy) / r)^2 <= 1. `squash` below 1 is a wheel
    seen at an angle. The masks hold the wheel's face only, so a test that needs the
    tread in the box sets the box itself. Both are kept on rows < `y_true`.

    `reflection` is "none", "overlap" or "hole". With "overlap" or "hole", both masks
    also hold their mirror image in the water: row y maps to 2 x y_true - 1 - y. In
    column x, the water starts at row y_true + seam + round(ripple x sin(x / 7)) and
    runs to the image's bottom. For "none" and "hole", the wheel's pixels are removed
    from it; for "overlap", it keeps them.
    """
    if reflection not in ("none", "overlap", "hole"):
        raise ValueError(f"not a reflection: {reflection!r}")
    width, height = size
    ys, xs = np.mgrid[0:height, 0:width]
    cx, cy = centre

    def face(r: int) -> np.ndarray:
        inside = ((xs - cx) / (squash * r)) ** 2 + ((ys - cy) / r) ** 2 <= 1
        inside &= ys < y_true
        if reflection != "none":
            rows = np.arange(y_true, min(height, 2 * y_true))
            inside[rows] |= inside[2 * y_true - 1 - rows]
        return inside

    wheel, rim = face(tire_r), face(rim_r)
    tops = y_true + seam + np.round(ripple * np.sin(np.arange(width) / 7)).astype(int)
    water = ys >= tops
    if reflection != "overlap":
        water &= ~wheel
    return wheel, rim, water


def sam_results(
    boxes: Mapping[str, Sequence[tuple]], *, size: tuple[int, int] = SIZE
) -> dict[str, SamResult]:
    """SAM's results for all 7 phrases: an instance for each box listed, else none.

    Each phrase's ids count from 0 in the order given, as each SAM request's do.
    """
    unknown = set(boxes) - set(SAM_PHRASES)
    if unknown:
        raise ValueError(f"not SAM phrases: {sorted(unknown)}")
    return {
        phrase: SamResult(
            phrase,
            [
                instance(i, xyxy, size=size)
                for i, xyxy in enumerate(boxes.get(phrase, ()))
            ],
            elapsed_s=0.5,
            raw="",
        )
        for phrase in SAM_PHRASES
    }


def vehicle(
    id: int,
    type: str = "sedan_hatch",
    moving: str = "no",
    body: str = "not_visible",
    wake: bool = False,
) -> dict:
    """One `vehicles` entry of Muse Spark's answer, in the schema's field names."""
    return {
        "id": id,
        "type": type,
        "moving": moving,
        "wake_visible": wake,
        "body_waterline": body,
    }


def wheel(id: int, waterline: str) -> dict:
    """One `wheels` entry of Muse Spark's answer."""
    return {"id": id, "waterline": waterline}


def person(
    id: int, waterline: str, adult: str = "yes", standing_still: str = "yes"
) -> dict:
    """One `people` entry of Muse Spark's answer."""
    return {
        "id": id,
        "adult": adult,
        "standing_still": standing_still,
        "waterline": waterline,
    }


def answer(
    *,
    photo_usable: str = "yes",
    standing_water: str = "yes",
    vehicles: Sequence[dict] = (),
    wheels: Sequence[dict] = (),
    people: Sequence[dict] = (),
    reason: str = "REASON-MARKER-31",
) -> dict:
    """Muse Spark's whole answer, with its lists as lists, as JSON parses them.

    The reason is a marker, so a test can show it never reaches a log (C62).
    """
    return {
        "photo_usable": photo_usable,
        "standing_water": standing_water,
        "vehicles": list(vehicles),
        "wheels": list(wheels),
        "people": list(people),
        "reason": reason,
    }


def meta_error(status: int) -> MetaApiError:
    """The MetaApiError the client raises for test_meta_client.py's `error(status)`.

    Those responses carry no error code, so the message is the status alone.
    """
    return MetaApiError(f"HTTP {status}", status=status)


def dry_street(sam: dict[str, SamResult]) -> dict[str, SamResult]:
    """SAM's results with no floodwater: a dry street (D14).

    A "no" on standing water then stays no flood seen under the live tuning, whose
    no-flood share (C93) refuses a "no" over the level case's wide water.
    """
    return {**sam, "floodwater": dataclasses.replace(sam["floodwater"], instances=[])}


def street_for(given: object, sam: dict[str, SamResult]) -> dict[str, SamResult]:
    """The SAM results a test's answer needs: a dry street for a "no" on standing
    water (D14), so it stays no flood seen under the live tuning (C93); else `sam`."""
    if isinstance(given, dict) and given.get("standing_water") == "no":
        return dry_street(sam)
    return sam


def level_case() -> tuple[bytes, dict[str, SamResult], dict]:
    """The level case: a photo, SAM's results and Muse Spark's answer, read as knee.

    The photo is 640 x 480 noise. SAM finds one vehicle, numbered 1, and its wheel,
    numbered 2, which the 40 px rule keeps; water below them; a face and a plate.
    Muse Spark answers a parked sedan_hatch with its body not_visible and the wheel at
    rim_three_quarters. run_pipeline reads that as knee from the wheel, and stores a
    photo. The pipeline's, the offline runner's and the handler's tests share it.
    """
    sam = sam_results(
        {
            "vehicle": [(100, 100, 400, 300)],
            "wheel": [(150, 250, 200, 300)],
            "floodwater": [(0, 280, 640, 480)],
            "face": [(300, 120, 330, 150)],
            "license plate": [(220, 270, 280, 290)],
        }
    )
    given = answer(vehicles=[vehicle(1)], wheels=[wheel(2, "rim_three_quarters")])
    return noise_jpeg(), sam, given


def geometry_case(
    vehicle_type: str = "sedan_hatch", waterline: str = "rim_quarter"
) -> tuple[bytes, dict[str, SamResult], dict]:
    """The geometry case: a photo, SAM's results and Muse Spark's answer.

    The photo is 640 x 480 noise. SAM's wheel, rim and water are wheel_scene's masks at
    y_true 257, with the boxes (263, 183, 378, 257), (285, 205, 356, 257) and (0, 257,
    640, 480). Its vehicle is (150, 100, 500, 300), and the other phrases find nothing.
    Muse Spark answers vehicle 1, a parked `vehicle_type` with its body not_visible,
    and wheel 2 at `waterline`. With geometry on, run_pipeline measures a sedan_hatch's
    wheel at 7.720 to 8.184 in, which is half_knee. Tasks 7 to 10 and 12 reuse it.
    """
    wheel_mask, rim_mask, water = wheel_scene(y_true=257)
    sam = sam_results({"vehicle": [(150, 100, 500, 300)]})
    for phrase, xyxy, mask in (
        ("wheel", (263, 183, 378, 257), wheel_mask),
        ("wheel rim", (285, 205, 356, 257), rim_mask),
        ("floodwater", (0, 257, 640, 480), water),
    ):
        found = [instance(0, xyxy, mask=mask)]
        sam[phrase] = SamResult(phrase, found, elapsed_s=0.5, raw="")
    given = answer(vehicles=[vehicle(1, vehicle_type)], wheels=[wheel(2, waterline)])
    return noise_jpeg(), sam, given


class FakeClient:
    """A ModelClient that answers from fixed results and records each call.

    `segment` returns `sam[phrase]`. `judge` returns `answer` as Muse Spark's answer,
    or raises it when it is an exception. The answer's reasoning token count is
    `reasoning_tokens` (C312). Each runs its hook first, if set, as
    `on_segment(phrase)` or `on_judge()`: a hook can wait, or raise to fail the call
    before it is recorded. `calls` holds (method, phrase or schema_name, image type)
    for each call, added behind a lock, because the phrases run in parallel.
    `keywords` holds each call's keyword arguments in the same order: `deadline`,
    and `reasoning_effort` for `judge` (C84, R101).
    """

    def __init__(
        self,
        sam: Mapping[str, SamResult],
        answer: dict | Exception | None = None,
        *,
        on_segment: Callable[[str], object] | None = None,
        on_judge: Callable[[], object] | None = None,
        reasoning_tokens: int | None = None,
    ) -> None:
        self.sam = sam
        self.answer = answer
        self.on_segment = on_segment
        self.on_judge = on_judge
        self.reasoning_tokens = reasoning_tokens
        self.calls: list[tuple[str, str, type]] = []
        self.keywords: list[dict[str, object]] = []
        self._lock = threading.Lock()

    def segment(
        self, image: BlurredImage, phrase: str, *, deadline: float | None = None
    ) -> SamResult:
        if self.on_segment is not None:
            self.on_segment(phrase)
        self._record("segment", phrase, image, deadline=deadline)
        return self.sam[phrase]

    def judge(
        self,
        image: BlurredImage,
        *,
        prompt: str,
        schema: dict,
        schema_name: str,
        deadline: float | None = None,
        reasoning_effort: str | None = None,
    ) -> SparkResult:
        if self.on_judge is not None:
            self.on_judge()
        self._record(
            "judge",
            schema_name,
            image,
            deadline=deadline,
            reasoning_effort=reasoning_effort,
        )
        if isinstance(self.answer, Exception):
            raise self.answer
        return SparkResult(
            data=self.answer,
            input_tokens=1000,
            output_tokens=200,
            elapsed_s=1.5,
            raw=json.dumps(self.answer),
            reasoning_tokens=self.reasoning_tokens,
        )

    def count_input_tokens(self, *args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("the pipeline never counts input tokens (spec §3.6)")

    def _record(
        self, method: str, name: str, image: object, **keywords: object
    ) -> None:
        with self._lock:
            self.calls.append((method, name, type(image)))
            self.keywords.append(keywords)


def _jpeg(bgr: np.ndarray) -> bytes:
    return cv2.imencode(".jpg", bgr)[1].tobytes()


class FakeSpend:
    """Stands in for laptop_spend.SpendCounter, with no AWS (C527).

    `records` holds each amount recorded and its source, in order. As the real one
    does, it does nothing for nothing billed. Each record runs `on_record` first, if
    set, as `on_record()`: a test can note what is saved by then. A tool's tests make
    it their check_before_paying, so a run checks and records without the lusot
    profile.
    """

    def __init__(self, on_record: Callable[[], object] | None = None) -> None:
        self.records: list[tuple[object, str]] = []
        self.on_record = on_record

    def record_after(self, usd, source: str) -> None:
        if usd <= 0:
            return
        if self.on_record is not None:
            self.on_record()
        self.records.append((usd, source))

    @property
    def total(self):
        """Everything recorded, in USD."""
        return sum(usd for usd, _ in self.records)
