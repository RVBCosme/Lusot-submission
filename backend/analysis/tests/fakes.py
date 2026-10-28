"""Builders the tests share.

pytest doesn't collect this module, because its name doesn't start with `test_`.
"""

import json
import math
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import NoReturn

import cv2
import numpy as np

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
) -> SamInstance:
    """SAM's match `i`, its box `xyxy` kept as MS1's client keeps it.

    The box is (x0, y0, x1, y1), half-open, in pixels of an image of `size`, so
    box_xyxy reads it back unchanged. The mask is True inside `mask_xyxy`, rounded
    outward (floor the start, ceil the end), which defaults to the box. Both boxes
    must lie inside the image, as the client requires of SAM's.
    """
    width, height = size
    mask_box = xyxy if mask_xyxy is None else mask_xyxy
    for box in (xyxy, mask_box):
        x0, y0, x1, y1 = box
        if not (0 <= x0 <= x1 <= width and 0 <= y0 <= y1 <= height):
            raise ValueError(f"{box} isn't inside a {width} x {height} image")
    x0, y0, x1, y1 = mask_box
    mask = np.zeros((height, width), bool)
    mask[math.floor(y0) : math.ceil(y1), math.floor(x0) : math.ceil(x1)] = True
    return SamInstance(i, tuple(float(v) for v in xyxy), mask, score)


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


class FakeClient:
    """A ModelClient that answers from fixed results and records each call.

    `segment` returns `sam[phrase]`. `judge` returns `answer` as Muse Spark's answer,
    or raises it when it is an exception. Each runs its hook first, if set, as
    `on_segment(phrase)` or `on_judge()`: a hook can wait, or raise to fail the call
    before it is recorded. `calls` holds (method, phrase or schema_name, image type)
    for each call, added behind a lock, because the phrases run in parallel.
    """

    def __init__(
        self,
        sam: Mapping[str, SamResult],
        answer: dict | Exception | None = None,
        *,
        on_segment: Callable[[str], object] | None = None,
        on_judge: Callable[[], object] | None = None,
    ) -> None:
        self.sam = sam
        self.answer = answer
        self.on_segment = on_segment
        self.on_judge = on_judge
        self.calls: list[tuple[str, str, type]] = []
        self._lock = threading.Lock()

    def segment(self, image: BlurredImage, phrase: str) -> SamResult:
        if self.on_segment is not None:
            self.on_segment(phrase)
        self._record("segment", phrase, image)
        return self.sam[phrase]

    def judge(
        self, image: BlurredImage, *, prompt: str, schema: dict, schema_name: str
    ) -> SparkResult:
        if self.on_judge is not None:
            self.on_judge()
        self._record("judge", schema_name, image)
        if isinstance(self.answer, Exception):
            raise self.answer
        return SparkResult(
            data=self.answer,
            input_tokens=1000,
            output_tokens=200,
            elapsed_s=1.5,
            raw=json.dumps(self.answer),
        )

    def count_input_tokens(self, *args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("the pipeline never counts input tokens (spec §3.6)")

    def _record(self, method: str, name: str, image: object) -> None:
        with self._lock:
            self.calls.append((method, name, type(image)))


def _jpeg(bgr: np.ndarray) -> bytes:
    return cv2.imencode(".jpg", bgr)[1].tobytes()
