"""The Meta Model API client: SAM 3.1, Muse Spark 1.3 and Muse Voice Transcribe (C10).

It sends only BlurredImages, so the face blur always runs first (C37). SAM and Muse
Spark go through the OpenAI SDK at Meta's base URL (plan Table 17), and transcription is
a plain HTTPS multipart call. One httpx client carries both, so connections are kept.
Only 429, 500 and 503 are retried.
"""

from __future__ import annotations

import base64
import email.utils
import json
import logging
import os
import random
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar

import httpx
import numpy as np
import openai
from meta_sam_parser import (
    CompletedOutcome,
    decode_mask_to_raster,
    image_segmentation_format,
)

from lusot_analysis.face_blur import BlurredImage

BASE_URL = "https://api.meta.ai/v1"
SAM_MODEL = "sam-3.1"
SPARK_MODEL = "muse-spark-1.3"
TRANSCRIBE_MODEL = "muse-voice-transcribe-1.0"
# What SAM is asked to find, one request per phrase (plan §7 step 2).
SAM_PHRASES = (
    "floodwater",
    "wheel",
    "wheel rim",
    "person",
    "vehicle",
    "face",
    "license plate",
)

_MODELS = frozenset({SAM_MODEL, SPARK_MODEL, TRANSCRIBE_MODEL})
_MIN_KEY_LENGTH = 20  # the real key has 48 characters (spec A8), the stale shell copy 1
_RETRY_STATUSES = frozenset({429, 500, 503})
_POLL_S = 1.0  # between polls of a background SAM response
# Stream events that end a SAM response without a result (R63).
_STREAM_FAILURES = frozenset(
    {"response.failed", "response.incomplete", "response.refusal.done", "error"}
)
_BOX_TOKEN = re.compile(r"<\|box;([^|]*)\|>")  # a box token's fields hold no `|`

_R = TypeVar("_R")

logger = logging.getLogger("lusot.meta")
logger.setLevel(logging.INFO)  # Lambda's text log format otherwise drops INFO
# At DEBUG the OpenAI SDK logs each request's options, its JSON body included: the
# photo and the prompt (R64). Photos are never logged, so its logger stays at INFO.
logging.getLogger("openai").setLevel(logging.INFO)


class MissingApiKey(RuntimeError):
    """MODEL_API_KEY is missing or too short. The message never holds the value."""


class MetaApiError(RuntimeError):
    """A Meta call failed, or its response didn't complete.

    `status` is the HTTP status, or None when there was none: a lost connection, a
    timeout, or a SAM response that came with HTTP 200 but didn't complete or
    couldn't be read.
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


# Meta's error page (https://dev.meta.ai/docs/error-handling, "503 Service
# Unavailable"): "When a shutdown happens mid-stream, it arrives as a terminal `error`
# SSE event with `code: server_shutting_down` before the stream closes; detect it and
# retry the full request (see Streaming errors)." So _send retries it as a 503 (R77).
class _ShuttingDown(Exception):
    """A SAM stream ended with an `error` event whose code is server_shutting_down."""


@dataclass
class SamInstance:
    """One SAM match, in pixels of the image that was sent (R61).

    `box` is (x0, y0, x1, y1), half-open: x0 and y0 are the first column and row, x1
    and y1 are one past the last, so `mask[y0:y1, x0:x1]` holds the whole match. SAM
    sends inclusive x2 and y2, which become x1 = x2 + 1 and y1 = y2 + 1. `mask` is a
    bool array of the image's height x width. `score` is SAM's confidence for the
    mask (its `c`, which the client asks for), or None when a record has none.
    """

    id: int
    box: tuple[float, float, float, float]
    mask: np.ndarray
    score: float | None


@dataclass
class SamResult:
    """SAM's matches for one phrase.

    `raw` is the text the client parsed, kept for a replay (R11): the SSE stream, or
    the final response JSON when the request ran in the background.
    """

    phrase: str
    instances: list[SamInstance]
    elapsed_s: float
    raw: str


@dataclass
class SparkResult:
    """Muse Spark's answer. `raw` is the output text that `data` was parsed from."""

    data: dict
    input_tokens: int | None
    output_tokens: int | None
    elapsed_s: float
    raw: str


@dataclass
class TranscriptResult:
    """A clip's transcript. `raw` is the response body."""

    text: str
    elapsed_s: float
    raw: str


class MetaClient:
    """Calls Meta's models. Make one per process; threads can share it (R61)."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = BASE_URL,
        timeout_s: float = 90.0,
        max_attempts: int = 4,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        rng: Callable[[], float] = random.random,
    ) -> None:
        """Read the key from `api_key`, or else from MODEL_API_KEY.

        A missing key, or one shorter than 20 characters, raises MissingApiKey. The
        OpenAI SDK makes no retries of its own (max_retries=0), and it shares this
        client's one httpx client.
        """
        key = os.environ.get("MODEL_API_KEY") if api_key is None else api_key
        if not key or len(key) < _MIN_KEY_LENGTH:
            raise MissingApiKey("MODEL_API_KEY is missing or too short")
        self._transcribe_url = base_url.rstrip("/") + "/asr/transcribe"
        self._timeout_s = timeout_s
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._rng = rng
        self._http = httpx.Client(transport=transport, timeout=timeout_s)
        self._openai = openai.OpenAI(
            api_key=key,
            base_url=base_url,
            max_retries=0,
            timeout=timeout_s,
            http_client=self._http,
        )

    def segment(self, image: BlurredImage, phrase: str) -> SamResult:
        """Find every match of `phrase` in `image` with SAM 3.1 (plan §7 step 2).

        The request is streamed. On a 504 it is sent again in the background and
        polled (C10). A result comes only from a completed response: any other end
        raises MetaApiError, so a failure never reads as "no matches" (R63).
        """
        _check_image(image)
        request = {
            "model": SAM_MODEL,
            "input": _message(phrase, image),
            # SAM adds its confidence `c` to each box and mask only when asked (R77).
            "metadata": {"include_confidence": "true"},
        }
        started = time.monotonic()
        try:
            raw, text = self._sam_streamed(request, phrase)
        except MetaApiError as exc:
            if exc.status != 504:
                raise
            # A background body over 1 MiB gets 413, and a 1,600 px photo inlined as
            # base64 can come close (R75). A 413 isn't retried: it raises from here.
            raw, text = self._sam_background(request, phrase)
        elapsed = time.monotonic() - started
        return SamResult(phrase, _instances(text, image), elapsed, raw)

    def judge(
        self, image: BlurredImage, *, prompt: str, schema: dict, schema_name: str
    ) -> SparkResult:
        """Ask Muse Spark about `image`, its answer held to `schema` in strict mode.

        `schema_name` names the schema and is logged as the prompt version. The
        response isn't stored at Meta (store: false, R76). The answer is parsed with
        json.loads, so one that isn't JSON raises json.JSONDecodeError (R62).
        """
        _check_image(image)
        message = _message(prompt, image)
        text_format = {
            "type": "json_schema",
            "name": schema_name,
            "schema": schema,
            "strict": True,
        }
        started = time.monotonic()
        response = self._send(
            lambda: self._openai.responses.with_raw_response.create(
                model=SPARK_MODEL,
                input=message,
                text={"format": text_format},
                store=False,
            ),
            SPARK_MODEL,
            schema_name=schema_name,
        ).parse()
        elapsed = time.monotonic() - started
        text = response.output_text
        usage = response.usage
        return SparkResult(
            data=json.loads(text),
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            elapsed_s=elapsed,
            raw=text,
        )

    def count_input_tokens(self, image: BlurredImage, *, prompt: str) -> int:
        """Muse Spark's input tokens for `prompt` and `image`, counted without a run."""
        _check_image(image)
        message = _message(prompt, image)
        response = self._send(
            lambda: self._openai.responses.input_tokens.with_raw_response.count(
                model=SPARK_MODEL, input=message
            ),
            SPARK_MODEL,
        )
        return response.parse().input_tokens

    def transcribe(
        self, wav: bytes, *, keywords: list[str] | None = None
    ) -> TranscriptResult:
        """Transcribe one WAV clip (mono, 16-bit PCM, 16 kHz) as a single turn.

        A multipart POST to /asr/transcribe. `keywords` bias recognition toward
        those words.
        """
        settings = {
            "model": TRANSCRIBE_MODEL,
            "audioEncoding": "WAV",
            "mode": "PUSH_TO_TALK",
        }
        if keywords:
            settings["keywords"] = list(keywords)
        files = {
            "request": (None, json.dumps(settings), "application/json"),
            "audio": ("clip.wav", wav, "audio/wav"),
        }
        headers = {
            "Authorization": f"Bearer {self._openai.api_key}",
            "Accept": "application/json",
        }
        started = time.monotonic()
        response = self._send(
            lambda: self._http.post(
                self._transcribe_url, headers=headers, files=files
            ).raise_for_status(),
            TRANSCRIBE_MODEL,
        )
        elapsed = time.monotonic() - started
        return TranscriptResult(response.json()["transcript"], elapsed, response.text)

    @staticmethod
    def _check_model(model: str) -> None:
        """Refuse any model but the three the rules name: never the contributor one."""
        if model not in _MODELS:
            raise ValueError(f"model {model!r} isn't one of the allowed ids")

    def _sam_streamed(self, request: dict, phrase: str) -> tuple[str, str]:
        """Stream a SAM request. Return the SSE text and SAM's output text.

        The stream is read inside the retry loop, so a shutdown in it is retried.
        """
        text = ""

        def call() -> Any:
            nonlocal text
            response = self._openai.responses.with_raw_response.create(
                **request, stream=True
            )
            response.http_response.read()  # the whole stream, kept as the raw text
            text = _stream_text(response.parse())
            return response

        response = self._send(call, SAM_MODEL, phrase=phrase)
        return response.text, text

    def _sam_background(self, request: dict, phrase: str) -> tuple[str, str]:
        """Run a SAM request in the background, then poll it after each 1 s wait.

        It gives up once those waits add up to timeout_s. The polls' own time and any
        retry waits inside them aren't counted, so the fallback can run longer than
        timeout_s. Return the final response JSON and SAM's output text.
        """
        submitted = self._send(
            lambda: self._openai.responses.with_raw_response.create(
                **request, background=True
            ),
            SAM_MODEL,
            phrase=phrase,
        ).parse()
        waited = 0.0
        while True:
            self._sleep(_POLL_S)
            waited += _POLL_S
            raw = self._send(
                lambda: self._openai.responses.with_raw_response.retrieve(submitted.id),
                SAM_MODEL,
                phrase=phrase,
            )
            response = raw.parse()
            if response.status == "completed":
                return raw.text, _output_text(response)
            if response.status not in ("queued", "in_progress"):
                raise MetaApiError(f"SAM's background response ended {response.status}")
            if waited >= self._timeout_s:
                raise MetaApiError(
                    f"SAM's background response timed out after {waited:g} s"
                )

    def _send(self, request: Callable[[], _R], model: str, **fields: str) -> _R:
        """Make one Meta call, retrying only 429, 500 and 503 (C10); log each try.

        `request` returns the raw HTTP response. Before try n + 1 the wait is 0.5 s x
        2^(n - 1) plus up to 1 s of jitter, or the server's Retry-After if longer, for
        at most max_attempts tries. A shutdown in a SAM stream counts as a 503 (R77).
        Any other HTTP error, and a lost connection or a timeout, raises MetaApiError
        at once (R65).
        """
        self._check_model(model)
        attempt = 1
        while True:
            started = time.monotonic()
            status = retry_after = None
            try:
                response = request()
                status = response.status_code
                return response
            except (openai.APIStatusError, httpx.HTTPStatusError) as exc:
                status = exc.response.status_code
                if status not in _RETRY_STATUSES or attempt >= self._max_attempts:
                    code = getattr(exc, "code", None)  # Meta's error code, when sent
                    message = f"HTTP {status}" + (f" ({code})" if code else "")
                    raise MetaApiError(message, status=status) from exc
                retry_after = exc.response.headers.get("retry-after")
            except _ShuttingDown as exc:  # an event, not a response: no Retry-After
                if attempt >= self._max_attempts:
                    raise MetaApiError("SAM's stream shut down; no tries left") from exc
            except (openai.APIConnectionError, httpx.TransportError) as exc:
                raise MetaApiError("connection failed or timed out") from exc
            finally:
                _log(model, fields, status, started)
            self._sleep(self._delay(attempt, retry_after))
            attempt += 1

    def _delay(self, attempt: int, retry_after: str | None) -> float:
        backoff = 0.5 * 2 ** (attempt - 1) + self._rng()
        return max(backoff, _retry_after(retry_after))


def _check_image(image: object) -> None:
    """Only a BlurredImage itself, not a subclass, so the face blur ran first (C37)."""
    if type(image) is not BlurredImage:
        raise TypeError("the Meta client sends only a BlurredImage from blur_for_meta")


def _message(text: str, image: BlurredImage) -> list[dict]:
    """One user message: the text, then the image as a JPEG data URL."""
    url = "data:image/jpeg;base64," + base64.b64encode(image.jpeg).decode("ascii")
    content = [
        {"type": "input_text", "text": text},
        {"type": "input_image", "image_url": url},
    ]
    return [{"type": "message", "role": "user", "content": content}]


def _stream_text(events: Iterable[Any]) -> str:
    """SAM's output text from a stream that completed (R63, R78).

    The text lane must be finished, by `response.output_text.done` or by an
    `output_text` part in `response.content_part.done`. Meta's live streams send both
    after the deltas (two captures, Oct 28). Only one of the captures had no match,
    and it came as a finished empty lane (tests/fixtures/meta/sam_live_no_match.sse).
    As in meta-sam-parser's own stream adapter, a completed stream whose lane never
    finished, finishing events that disagree, or deltas that don't add up to the
    finished text raise MetaApiError. A shutdown raises _ShuttingDown, which _send
    retries. A stream that fails, stops short, refuses or reports any other error
    raises MetaApiError.
    """
    deltas: list[str] = []
    finished = None
    try:
        for event in events:
            kind = getattr(event, "type", None)
            if kind == "response.output_text.delta":
                deltas.append(event.delta)
            elif kind == "response.output_text.done":
                finished = _finish(finished, event.text)
            elif kind == "response.content_part.done":
                if event.part.type == "output_text":  # not a refusal part
                    finished = _finish(finished, event.part.text)
            elif kind == "response.completed":
                if finished is None:
                    raise MetaApiError("SAM's text lane never finished")
                if deltas and "".join(deltas) != finished:
                    raise MetaApiError("SAM's finished text differs from its deltas")
                return finished
            elif kind == "error" and event.code == "server_shutting_down":
                raise _ShuttingDown
            elif kind in _STREAM_FAILURES:
                raise MetaApiError(f"SAM's stream ended with {kind}")
    except (openai.APIError, json.JSONDecodeError) as exc:
        # The SDK raises APIError for an `error` object; JSONDecodeError is bad data.
        raise MetaApiError("SAM's stream sent an error") from exc
    raise MetaApiError("SAM's stream ended without completing")


def _finish(finished: str | None, text: str) -> str:
    """The lane's finished text. A second finishing event must carry the same text."""
    if finished is not None and text != finished:
        raise MetaApiError("SAM's stream finished its text twice, differently")
    return text


def _output_text(response: Any) -> str:
    """The one output_text part of a completed background response (R78).

    No match comes as one empty part, as in the live capture, so a completed response
    with no such part, or with more than one, raises MetaApiError.
    """
    parts = [
        part.text
        for item in response.output
        if item.type == "message"
        for part in item.content
        if part.type == "output_text"
    ]
    if len(parts) != 1:
        raise MetaApiError(f"SAM's completed response has {len(parts)} text parts")
    return parts[0]


def _instances(text: str, image: BlurredImage) -> list[SamInstance]:
    """Read SAM's output text (meta-sam-parser) into instances on `image` (R61).

    Text the parser drops or keeps as plain text, a box whose frame (its `w` and `h`)
    isn't the image's size, and a mask that doesn't fill its box inside the image
    raise MetaApiError: a lost or misplaced record must not read as no match.
    """
    parser = image_segmentation_format().create_parser()
    parser.push(text)
    result = parser.finish(CompletedOutcome()).result
    errors = [d.code for d in result.diagnostics if d.severity == "error"]
    if errors or any(record.kind == "text" for record in result.records):
        raise MetaApiError(f"SAM's output couldn't be read: {errors or 'plain text'}")
    # The parser checks each box against its frame but doesn't keep the frame's size.
    for body in _BOX_TOKEN.findall(text):
        fields = _token_fields(body)
        frame = [int(fields[key]) for key in ("w", "h") if key in fields]
        if len(frame) == 2 and frame != [image.width, image.height]:
            raise MetaApiError("a SAM box is in a frame of another size than the image")
    instances = []
    for record in result.records:
        if record.kind != "mask":
            continue
        bounds = record.bounds
        x0, y0, x1, y1 = (
            int(v) for v in (bounds.left, bounds.top, bounds.right, bounds.bottom)
        )
        size = (record.mask.height, record.mask.width)
        if size != (y1 - y0, x1 - x0) or x1 > image.width or y1 > image.height:
            raise MetaApiError("a SAM mask doesn't fill its box inside the image")
        crop = np.frombuffer(decode_mask_to_raster(record.mask), np.uint8)
        mask = np.zeros((image.height, image.width), bool)
        mask[y0:y1, x0:x1] = crop.reshape(size).astype(bool)
        box = (float(x0), float(y0), float(x1), float(y1))
        instances.append(
            SamInstance(int(record.object_id), box, mask, record.confidence)
        )
    return instances


def _token_fields(body: str) -> dict[str, str]:
    """A token's `key=value` fields by name, trimmed, as SAM's protocol reads them."""
    fields = {}
    for field in body.split(";"):
        key, sep, value = field.partition("=")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def _retry_after(value: str | None) -> float:
    """The wait a Retry-After header asks for, given in seconds or as an HTTP date."""
    if value is None:
        return 0.0
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = email.utils.parsedate_to_datetime(value)
            seconds = (when - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError):  # not a date, or a date with no time zone
            return 0.0
    return max(0.0, seconds)


def _log(model: str, fields: dict, status: int | None, started: float) -> None:
    """One JSON line: the model, the phrase or schema_name, the status and the time.

    Never the key, an image, a prompt or a model's output (R64).
    """
    ms = round((time.monotonic() - started) * 1000)
    logger.info(json.dumps({"model": model, **fields, "status": status, "ms": ms}))
