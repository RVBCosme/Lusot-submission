"""The Meta Model API client: SAM 3.1, Muse Spark 1.3 and Muse Voice Transcribe (C10).

It sends only BlurredImages, so the face blur always runs first (C37). SAM and Muse
Spark go through the OpenAI SDK at Meta's base URL (plan Table 17), and transcription is
a plain HTTPS multipart call. One httpx client carries both, so connections are kept.
Only 429, 500 and 503 are retried. A call can run under a deadline (C84, C88): it then
starts no try or wait that the deadline rules out, and cuts its timeouts to the time
left, but a read already under way can end after it (MetaClient._send says by how much).
"""

from __future__ import annotations

import base64
import contextlib
import email.utils
import json
import logging
import os
import random
import re
import time
from collections.abc import Callable, Iterable, Iterator
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
# SAM's longest mask side (MS3a Task 16: a 700 x 1600 box's mask came as 448 x 1024).
SAM_MASK_SIDE = 1024

_MODELS = frozenset({SAM_MODEL, SPARK_MODEL, TRANSCRIBE_MODEL})
_MIN_KEY_LENGTH = 20  # the real key has 48 characters (spec A8), the stale shell copy 1
_RETRY_STATUSES = frozenset({429, 500, 503})
_POLL_S = 1.0  # between polls of a background SAM response
# Under a deadline (C88): no retry starts with less time than this left, because it
# couldn't finish but might still be billed, and a SAM stream waits at most this long
# for its next event, 2.4 times the slowest call C85 saw at the app's size (R103).
_MIN_TRY_S = 5.0
_STREAM_GAP_S = 20.0
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
    timeout, or a response that came with HTTP 200 but didn't complete or couldn't
    be read.
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class DeadlineExceeded(MetaApiError):
    """A Meta call stopped at the run's deadline (C84). `status` is None.

    The client raises it instead of starting a try, first or retry, with under 5 s
    left, or a retry or poll wait that would leave under 5 s (C88, R104, R106). It
    also raises it at a SAM stream's first chunk at or after the deadline, and when
    a timeout fires at or after it. It is a MetaApiError, so the report ends
    failed/model_error like any other Meta failure.
    """


class ModelRefused(Exception):
    """Muse Spark refused to answer: its message held a refusal part (C86).

    It carries none of the refusal's text, so nothing that logs it can show the
    model's words. It isn't a MetaApiError: the report ends refused, not failed.
    """


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
    """Muse Spark's answer. `raw` is the output text that `data` was parsed from.

    `reasoning_tokens` is usage.output_tokens_details.reasoning_tokens, or None when
    the response doesn't report it (Meta's documented example doesn't).
    """

    data: dict
    input_tokens: int | None
    output_tokens: int | None
    elapsed_s: float
    raw: str
    reasoning_tokens: int | None = None


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
        sam_store: bool | None = False,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        rng: Callable[[], float] = random.random,
    ) -> None:
        """Read the key from `api_key`, or else from MODEL_API_KEY.

        A missing key, or one shorter than 20 characters, raises MissingApiKey. The
        OpenAI SDK makes no retries of its own (max_retries=0), and it shares this
        client's one httpx client. `sam_store` is the `store` value sent with every
        streamed SAM request: False by default, which C85 found Meta accepts (C88), or
        None to send none, as MS1 did. `clock` is the monotonic clock that deadlines
        are read on; tests pass a fake with `sleep`.
        """
        key = os.environ.get("MODEL_API_KEY") if api_key is None else api_key
        if not key or len(key) < _MIN_KEY_LENGTH:
            raise MissingApiKey("MODEL_API_KEY is missing or too short")
        self._transcribe_url = base_url.rstrip("/") + "/asr/transcribe"
        self._timeout_s = timeout_s
        self._max_attempts = max_attempts
        self._sam_store = sam_store
        self._sleep = sleep
        self._clock = clock
        self._rng = rng
        self._http = httpx.Client(transport=transport, timeout=timeout_s)
        self._openai = openai.OpenAI(
            api_key=key,
            base_url=base_url,
            max_retries=0,
            timeout=timeout_s,
            http_client=self._http,
        )

    def segment(
        self, image: BlurredImage, phrase: str, *, deadline: float | None = None
    ) -> SamResult:
        """Find every match of `phrase` in `image` with SAM 3.1 (plan §7 step 2).

        The request is streamed. On a 504 it is sent again in the background and
        polled (C10), with no `store`, and the stored job is deleted however the
        polling ends (C88, R106). A result comes only from a completed response: any
        other end raises MetaApiError, so a failure never reads as "no matches"
        (R63). `deadline` is a time.monotonic() value that bounds the call as `_send`
        describes (C84, C88); None sets no deadline.
        """
        _check_image(image)
        request = {
            "model": SAM_MODEL,
            "input": _message(phrase, image),
            # SAM adds its confidence `c` to each box and mask only when asked (R77).
            "metadata": {"include_confidence": "true"},
        }
        # Meta's background mode refuses store: false, and a background job must be
        # stored to be polled, so only the stream sends it (C85, C88).
        streamed = request
        if self._sam_store is not None:
            streamed = request | {"store": self._sam_store}
        started = time.monotonic()
        try:
            raw, text = self._sam_streamed(streamed, phrase, deadline)
        except MetaApiError as exc:
            if exc.status != 504:
                raise
            # A background body over 1 MiB gets 413 (R75). Base64 makes the photo a
            # third larger, so that is about 768 KiB of JPEG. A 413 isn't retried: it
            # raises from here.
            raw, text = self._sam_background(request, phrase, deadline)
        elapsed = time.monotonic() - started
        return SamResult(phrase, _instances(text, image), elapsed, raw)

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
        """Ask Muse Spark about `image`, its answer held to `schema` in strict mode.

        `schema_name` names the schema and is logged as the prompt version. The
        response isn't stored at Meta (store: false, R76). `deadline` bounds the call
        as in `segment` (C84). `reasoning_effort` is sent as reasoning.effort when
        set; otherwise Meta's default applies.

        Before any parsing, an answer with a status other than completed raises
        MetaApiError (C86, R104), and one that holds a refusal part raises
        ModelRefused (C86). Meta's schema makes `status` optional, so an answer
        without one is read. The answer is then parsed with json.loads, so one that
        isn't JSON raises json.JSONDecodeError (R62).
        """
        _check_image(image)
        message = _message(prompt, image)
        text_format = {
            "type": "json_schema",
            "name": schema_name,
            "schema": schema,
            "strict": True,
        }
        options = {}
        if reasoning_effort is not None:
            options["reasoning"] = {"effort": reasoning_effort}
        started = time.monotonic()
        response = self._send(
            lambda timeout: self._openai.responses.with_raw_response.create(
                model=SPARK_MODEL,
                input=message,
                text={"format": text_format},
                store=False,
                timeout=timeout,
                **options,
            ),
            SPARK_MODEL,
            deadline,
            log_extra=_reasoning_logged,
            schema_name=schema_name,
        ).parse()
        elapsed = time.monotonic() - started
        if response.status not in (None, "completed"):
            raise MetaApiError(f"Muse Spark's answer ended {response.status}")
        if _refused(response):
            raise ModelRefused("Muse Spark refused to answer")
        text = response.output_text
        usage = response.usage
        return SparkResult(
            data=json.loads(text),
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            elapsed_s=elapsed,
            raw=text,
            reasoning_tokens=_reasoning_tokens(usage),
        )

    def count_input_tokens(self, image: BlurredImage, *, prompt: str) -> int:
        """Muse Spark's input tokens for `prompt` and `image`, counted without a run."""
        _check_image(image)
        message = _message(prompt, image)
        response = self._send(
            lambda timeout: self._openai.responses.input_tokens.with_raw_response.count(
                model=SPARK_MODEL, input=message, timeout=timeout
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
            lambda timeout: self._http.post(
                self._transcribe_url, headers=headers, files=files, timeout=timeout
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

    def _sam_streamed(
        self, request: dict, phrase: str, deadline: float | None
    ) -> tuple[str, str]:
        """Stream a SAM request. Return the SSE text and SAM's output text.

        The stream is read inside the retry loop, so a shutdown in it is retried.
        Under a deadline, each read waits at most 20 s for the next event (C88, R103),
        and each chunk is checked against the deadline as it arrives, because
        keepalive events can hold a stream open (R101). So a stalled stream ends
        within 20 s, and one still running at the deadline ends at its next chunk.
        """
        text = ""

        def call(timeout: float) -> Any:
            nonlocal text
            limits: float | httpx.Timeout = timeout
            if deadline is not None:
                limits = httpx.Timeout(timeout, read=min(timeout, _STREAM_GAP_S))
            response = self._openai.responses.with_raw_response.create(
                **request, stream=True, timeout=limits
            )
            body = response.http_response
            if deadline is not None:
                body.stream = _UntilDeadline(body.stream, deadline, self._clock)
            try:
                body.read()  # the whole stream, kept as the raw text
            finally:
                body.close()  # a read that failed would leave the connection open
            text = _stream_text(response.parse())
            return response

        response = self._send(call, SAM_MODEL, deadline, phrase=phrase)
        return response.text, text

    def _sam_background(
        self, request: dict, phrase: str, deadline: float | None
    ) -> tuple[str, str]:
        """Run a SAM request in the background, then poll it after each 1 s wait.

        It gives up once those waits add up to timeout_s. The polls' own time and any
        retry waits inside them aren't counted, so the fallback can run longer than
        timeout_s, unless the deadline stops a wait first (C84). Each poll is a try,
        so no poll wait starts that would leave under 5 s (R106). Meta stores a
        background job so it can be polled, so once the submit has returned an id,
        the job is deleted however the polling ends (C88, R106). Return the final
        response JSON and SAM's output text.
        """
        submitted = self._send(
            lambda timeout: self._openai.responses.with_raw_response.create(
                **request, background=True, timeout=timeout
            ),
            SAM_MODEL,
            deadline,
            phrase=phrase,
        ).parse()
        try:
            waited = 0.0
            while True:
                self._wait(_POLL_S, deadline, then_left=_MIN_TRY_S)
                waited += _POLL_S
                raw = self._send(
                    lambda timeout: self._openai.responses.with_raw_response.retrieve(
                        submitted.id, timeout=timeout
                    ),
                    SAM_MODEL,
                    deadline,
                    phrase=phrase,
                )
                response = raw.parse()
                if response.status == "completed":
                    return raw.text, _output_text(response)
                if response.status not in ("queued", "in_progress"):
                    raise MetaApiError(
                        f"SAM's background response ended {response.status}"
                    )
                if waited >= self._timeout_s:
                    raise MetaApiError(
                        f"SAM's background response timed out after {waited:g} s"
                    )
        finally:
            if submitted.id:
                self._delete(submitted.id, phrase, deadline)

    def _delete(self, response_id: str, phrase: str, deadline: float | None) -> None:
        """Delete a stored background job, best effort (C88, R106).

        It needs only some time left before the deadline, not the 5 s floor of a
        billed try, so it still runs when polling stopped at that floor. A failure
        never fails the call or masks the error that ended the polling. Each try's
        log line carries `delete` and the status alone.
        """
        with contextlib.suppress(MetaApiError):
            self._send(
                lambda timeout: self._openai.responses.with_raw_response.delete(
                    response_id, timeout=timeout
                ),
                SAM_MODEL,
                deadline,
                floor=0.0,
                phrase=phrase,
                delete=True,
            )

    def _send(
        self,
        request: Callable[[float], _R],
        model: str,
        deadline: float | None = None,
        *,
        floor: float = _MIN_TRY_S,
        log_extra: Callable[[_R], dict[str, object]] | None = None,
        **fields: object,
    ) -> _R:
        """Make one Meta call, retrying only 429, 500 and 503 (C10); log each try.

        `request` takes the try's timeout and returns the raw HTTP response. Before
        try n + 1 the wait is 0.5 s x 2^(n - 1) plus up to 1 s of jitter, or the
        server's Retry-After if longer, for at most max_attempts tries. A shutdown in
        a SAM stream counts as a 503 (R77). Any other HTTP error, and a lost
        connection or a timeout, raises MetaApiError at once (R65). `log_extra` adds
        fields read from a response to its try's log line.

        With a deadline (C84, C88), each try's timeouts are cut to the time left, and
        DeadlineExceeded is raised instead of starting a try, first or retry, with
        less than `floor` seconds left (R104, R106): 5 s, except for the best-effort
        delete, which needs only some time left. A timeout that fires at or after the
        deadline raises it too; one that fires before it is a MetaApiError. A wait is
        never shortened, so a retry never comes early. A read under way at the
        deadline can still run to its timeout: at most 20 s for a SAM stream, and at
        most the time left when the try began for the other calls.
        """
        self._check_model(model)
        attempt = 1
        while True:
            timeout = self._timeout(deadline, floor)
            started = time.monotonic()
            status = retry_after = None
            try:
                response = request(timeout)
                status = response.status_code
                if log_extra is not None:
                    fields.update(log_extra(response))
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
                timeouts = (openai.APITimeoutError, httpx.TimeoutException)
                late = deadline is not None and self._clock() >= deadline
                if late and isinstance(exc, timeouts):
                    raise DeadlineExceeded("timed out at the deadline") from exc
                raise MetaApiError("connection failed or timed out") from exc
            finally:
                _log(model, fields, status, started)
            delay = self._delay(attempt, retry_after)
            self._wait(delay, deadline, then_left=floor)
            attempt += 1

    def _delay(self, attempt: int, retry_after: str | None) -> float:
        backoff = 0.5 * 2 ** (attempt - 1) + self._rng()
        return max(backoff, _retry_after(retry_after))

    def _timeout(self, deadline: float | None, floor: float) -> float:
        """A try's timeout: timeout_s, or the time left if that is less (C84).

        With no time left, or less than `floor` seconds (C88, R106), it raises
        DeadlineExceeded, so nothing is sent.
        """
        if deadline is None:
            return self._timeout_s
        left = deadline - self._clock()
        if left <= 0 or left < floor:
            raise DeadlineExceeded("too little time left before the deadline")
        return min(self._timeout_s, left)

    def _wait(
        self, seconds: float, deadline: float | None, *, then_left: float
    ) -> None:
        """Sleep, unless the deadline rules the wait out: then raise DeadlineExceeded.

        A wait is ruled out when it would reach the deadline, or leave less than
        `then_left` seconds after it (C88). It is never shortened, so a retry or a
        poll never comes early (C84).
        """
        if deadline is not None:
            left = deadline - (self._clock() + seconds)
            if left <= 0 or left < then_left:
                raise DeadlineExceeded(f"a {seconds:g} s wait leaves too little time")
        self._sleep(seconds)


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


class _UntilDeadline(httpx.SyncByteStream):
    """A response body that raises DeadlineExceeded at a chunk arriving at or after
    the deadline (C84), so keepalive events can't hold a stream open past it."""

    def __init__(
        self, stream: httpx.SyncByteStream, deadline: float, clock: Callable[[], float]
    ) -> None:
        self._stream = stream
        self._deadline = deadline
        self._clock = clock

    def __iter__(self) -> Iterator[bytes]:
        for chunk in self._stream:
            if self._clock() >= self._deadline:
                raise DeadlineExceeded("SAM's stream ran to the deadline")
            yield chunk

    def close(self) -> None:
        self._stream.close()


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


def _refused(response: Any) -> bool:
    """True when the answer's message holds a refusal part (RefusalContent, C86)."""
    return any(
        part.type == "refusal"
        for item in response.output
        if item.type == "message"
        for part in item.content
    )


def _reasoning_tokens(usage: Any) -> int | None:
    """usage.output_tokens_details.reasoning_tokens, or None when it isn't reported."""
    details = usage.output_tokens_details if usage else None
    return details.reasoning_tokens if details else None


def _reasoning_logged(raw: Any) -> dict[str, object]:
    """The reasoning token count for a Muse Spark try's log line, when reported."""
    tokens = _reasoning_tokens(raw.parse().usage)
    return {} if tokens is None else {"reasoning_tokens": tokens}


def _instances(text: str, image: BlurredImage) -> list[SamInstance]:
    """Read SAM's output text (meta-sam-parser) into instances on `image` (R61).

    Text the parser drops or keeps as plain text, a box whose frame (its `w` and `h`)
    isn't the image's size, and a mask that doesn't fill its box inside the image
    raise MetaApiError: a lost or misplaced record must not read as no match. A mask
    whose box has a side over SAM_MASK_SIDE may come scaled down so its longer side is
    SAM_MASK_SIDE, and is scaled back up to fill its box (_scaled_down has the rule).
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
        size, box_size = (record.mask.height, record.mask.width), (y1 - y0, x1 - x0)
        fits = size == box_size or _scaled_down(size, box_size)
        if not fits or x1 > image.width or y1 > image.height:
            raise MetaApiError("a SAM mask doesn't fill its box inside the image")
        crop = np.frombuffer(decode_mask_to_raster(record.mask), np.uint8)
        crop = crop.reshape(size).astype(bool)
        mask = np.zeros((image.height, image.width), bool)
        mask[y0:y1, x0:x1] = crop if size == box_size else _upscaled(crop, box_size)
        box = (float(x0), float(y0), float(x1), float(y1))
        instances.append(
            SamInstance(int(record.object_id), box, mask, record.confidence)
        )
    return instances


def _scaled_down(size: tuple[int, int], box: tuple[int, int]) -> bool:
    """True when a mask of `size` is its `box` (both rows, columns) scaled down to a
    longer side of SAM_MASK_SIDE, as SAM sends it when the box has a side over
    SAM_MASK_SIDE.

    The box needs a side over SAM_MASK_SIDE (MS3a Task 16). The mask's side along the
    box's longer axis (both, for a square box) must be SAM_MASK_SIDE. Its other side
    must be within 1 px of the box's, rounded at the same scale, as SAM's rounding is
    unknown, and no longer than the box's.
    """
    longest = max(box)
    if longest <= SAM_MASK_SIDE:
        return False
    for side, box_side in zip(size, box, strict=True):
        # On the longer axis `scaled` is SAM_MASK_SIDE, and the side must match it.
        scaled = round(box_side * SAM_MASK_SIDE / longest)
        slack = 0 if box_side == longest else 1
        if side > box_side or abs(side - scaled) > slack:
            return False
    return True


def _upscaled(crop: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """`crop` scaled up to `size` (rows, columns) by center-aligned nearest neighbour.

    Index i on each axis takes source index floor((i + 0.5) * src / dst), worked in
    integers so a whole-number result stays whole. OpenCV's INTER_NEAREST_EXACT, in
    16-bit fixed point, can be one index off either way within about 0.01 of a whole
    number, and plain INTER_NEAREST is half a pixel off throughout.
    """
    rows, cols = (
        (2 * np.arange(dst) + 1) * src // (2 * dst)
        for src, dst in zip(crop.shape, size, strict=True)
    )
    return crop[np.ix_(rows, cols)]


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

    A Muse Spark answer's line also has its reasoning token count, when reported.
    Never the key, an image, a prompt or a model's output (R64).
    """
    ms = round((time.monotonic() - started) * 1000)
    logger.info(json.dumps({"model": model, **fields, "status": status, "ms": ms}))
