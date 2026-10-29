"""Tests for the Meta client (C10, C37). Every HTTP call goes to httpx.MockTransport.

The fixtures in fixtures/meta/ are Meta's documented examples. Each test that uses one
names its source in its docstring.
"""

import base64
import email.policy
import email.utils
import inspect
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest
from fakes import FakeClient
from meta_sam_parser._mask_codec import _encode_raster

from lusot_analysis import face_blur
from lusot_analysis.face_blur import BlurredImage, blur_for_meta
from lusot_analysis.meta_client import (
    BASE_URL,
    REASONING_EFFORTS,
    SAM_MODEL,
    SAM_PHRASES,
    SPARK_MODEL,
    TRANSCRIBE_MODEL,
    DeadlineExceeded,
    MetaApiError,
    MetaClient,
    MissingApiKey,
    ModelRefused,
    SparkResult,
)
from lusot_analysis.pipeline.types import ModelClient

FIXTURES = Path(__file__).parent / "fixtures" / "meta"
FAKE_KEY = "fake-model-key-" + "0" * 33  # 48 characters, like the real key (spec A8)
PROMPT = "Read the address."
# The Address schema on https://dev.meta.ai/docs/structured-output, made strict.
ADDRESS_SCHEMA = {
    "type": "object",
    "properties": {
        "street": {"type": "string"},
        "city": {"type": "string"},
        "state": {"type": "string", "description": "2-letter state abbreviation"},
        "zip": {"type": "string", "description": "5-digit zip code"},
    },
    "required": ["street", "city", "state", "zip"],
    "additionalProperties": False,
}
SAM_STREAM = (FIXTURES / "sam_stream.sse").read_bytes()
# A live sam-3.1 stream, captured Oct 28 for a synthetic 640 x 480 image and the phrase
# "floodwater" (R78). No match comes as a finished empty lane.
LIVE_NO_MATCH = (FIXTURES / "sam_live_no_match.sse").read_bytes()


def sam_event(kind: str, stream: bytes = SAM_STREAM) -> dict:
    """The first event of `kind` in a captured or documented SAM stream."""
    events = (
        json.loads(line.removeprefix("data: "))
        for line in stream.decode().splitlines()
        if line.startswith("data: {")
    )
    return next(event for event in events if event["type"] == kind)


CREATED = sam_event("response.created")
DELTA = sam_event("response.output_text.delta")  # the first half of the text
PART_DONE = sam_event("response.content_part.done")
DOC_TEXT = PART_DONE["part"]["text"]  # the documented output: two matches
COMPLETED_FULL = sam_event("response.completed")  # its response carries the output
COMPLETED = COMPLETED_FULL["response"]
# The completed event with no output: the client reads the text from earlier events.
COMPLETED_EVENT = {
    "type": "response.completed",
    "response": {**COMPLETED, "output": []},
}
# A mid-stream shutdown, with the message on https://dev.meta.ai/docs/error-handling
# ("503 Service Unavailable").
SHUTDOWN = {
    "type": "error",
    "code": "server_shutting_down",
    "message": "Server is shutting down. Please retry your request.",
    "param": None,
}
# The documented records with the `c` values a request with include_confidence gets,
# in the format on https://dev.meta.ai/docs/sam/segmenting ("Request confidence"). The
# second record's box and mask values differ, which the protocol allows.
CONFIDENT_TEXT = (
    "<0f>0<|box;x1=211;y1=228;x2=270;y2=254;w=320;h=334;c=0.9609375|>"
    "<|mask;x=0;y=0;c=0.9609375;data=27,60,"
    "~!!!!M!0c[0o91w?q1!pIH4pPRVp2B3'7`e.ioeAf6-k/#Xd8%dX9x(|>"
    ",1<|box;x1=155;y1=228;x2=202;y2=254;w=320;h=334;c=0.5|>"
    "<|mask;x=0;y=0;c=0.75;data=27,48,"
    "~!!!!J!0c[q=Pj_zs=*4C4(/./x#:/`S_GnD`=o3?X{emCgO$y@|>\n"
)


@pytest.fixture(scope="module")
def photo() -> BlurredImage:
    """A face-free 320 x 334 photo, the size of the documented SAM example's frame."""
    row = np.linspace(0, 255, 320).astype(np.uint8)
    bgr = np.dstack([np.tile(row, (334, 1))] * 3)
    return blur_for_meta(cv2.imencode(".jpg", bgr)[1].tobytes())


def gradient(width: int, height: int) -> BlurredImage:
    """A face-free photo of `width` x `height`, built as the `photo` fixture is."""
    row = np.linspace(0, 255, width).astype(np.uint8)
    bgr = np.dstack([np.tile(row, (height, 1))] * 3)
    return blur_for_meta(cv2.imencode(".jpg", bgr)[1].tobytes())


@pytest.fixture(scope="module")
def wide_photo() -> BlurredImage:
    """A face-free 1600 x 1000 photo, the size of the one whose floodwater mask came
    scaled to a 1024 px side (MS3a Task 16)."""
    return gradient(1600, 1000)


@pytest.fixture(scope="module")
def square_photo() -> BlurredImage:
    """A face-free 1100 x 1100 photo, for a square box with sides over 1024 px."""
    return gradient(1100, 1100)


def mask_text(
    box: tuple[int, int, int, int], raster: np.ndarray, frame: tuple[int, int]
) -> str:
    """SAM's text for one match: `box` is (x1, y1, x2, y2), inclusive as SAM sends it,
    in a (w, h) frame, and `raster` (rows x columns of 0 and 1) is its one_bit mask.

    meta-sam-parser has no public encoder, so this uses its private one,
    _mask_codec._encode_raster, which its decoder re-runs to check each payload.
    """
    rows, cols = raster.shape
    payload = _encode_raster(raster.astype(np.uint8).ravel().tolist(), cols, rows)
    x1, y1, x2, y2 = box
    w, h = frame
    return (
        f"<0f>0<|box;x1={x1};y1={y1};x2={x2};y2={y2};w={w};h={h}|>"
        f"<|mask;x=0;y=0;data={rows},{cols},{payload}|>\n"
    )


class FakeMeta:
    """Stands in for api.meta.ai: answers each request with the next scripted one."""

    def __init__(self, *responses: httpx.Response) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self.responses:
            # Failed is a BaseException, so the SDK can't wrap it in a connection error.
            pytest.fail(f"no scripted response for {request.method} {request.url}")
        return self.responses.pop(0)


def client(meta, **kwargs) -> tuple[MetaClient, list[float]]:
    """A client on `meta`, and the list its sleeps are recorded in."""
    sleeps: list[float] = []
    transport = httpx.MockTransport(meta)
    c = MetaClient(FAKE_KEY, transport=transport, sleep=sleeps.append, **kwargs)
    return c, sleeps


class FakeClock:
    """A monotonic clock that moves only when the client sleeps, so no test waits."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def timed_client(
    meta, clock: FakeClock | None = None, **kwargs
) -> tuple[MetaClient, FakeClock]:
    """A client on `meta` that reads its deadlines on a FakeClock (C84)."""
    if clock is None:
        clock = FakeClock()
    transport = httpx.MockTransport(meta)
    c = MetaClient(
        FAKE_KEY, transport=transport, sleep=clock.sleep, clock=clock, **kwargs
    )
    return c, clock


def fixture(name: str) -> httpx.Response:
    return httpx.Response(200, json=json.loads((FIXTURES / name).read_text()))


def error(status: int, headers: dict | None = None) -> httpx.Response:
    """An error in the shape on https://dev.meta.ai/docs/error-handling."""
    body = {
        "error": {
            "message": "test",
            "type": "server_error",
            "param": None,
            "code": None,
        }
    }
    return httpx.Response(status, headers=headers, json=body)


def sse(*events: dict) -> httpx.Response:
    """A Responses stream: an `event:` and a `data:` line per event, then [DONE]."""
    body = "".join(
        f"event: {event.get('type', 'error')}\ndata: {json.dumps(event)}\n\n"
        for event in events
    )
    content = (body + "data: [DONE]\n\n").encode()
    return httpx.Response(
        200, headers={"content-type": "text/event-stream"}, content=content
    )


def raw_stream(body: bytes) -> httpx.Response:
    """A documented or captured SSE body, served as Meta serves it."""
    headers = {"content-type": "text/event-stream"}
    return httpx.Response(200, headers=headers, content=body)


def text_done(text: str) -> dict:
    """`response.output_text.done`, which Meta's live streams send (R78)."""
    lane = {"item_id": "msg_abc123", "output_index": 0, "content_index": 0}
    return {"type": "response.output_text.done", **lane, "text": text, "logprobs": []}


def part_done(text: str) -> dict:
    return {**PART_DONE, "part": {**PART_DONE["part"], "text": text}}


def sam_stream(text: str) -> httpx.Response:
    """A SAM stream shaped like Meta's live ones: `text` as one delta, finished by
    both finishing events, then completed."""
    delta = {**DELTA, "delta": text}
    return sse(CREATED, delta, text_done(text), part_done(text), COMPLETED_EVENT)


def background(status: str) -> httpx.Response:
    """The background response in `status`. Completed, it has the documented output."""
    body = {**COMPLETED, "background": True, "status": status}
    if status != "completed":
        body["output"] = []
    return httpx.Response(200, json=body)


def deleted() -> httpx.Response:
    """A delete's answer, as on https://dev.meta.ai/docs/features/responses
    ("DELETE /v1/responses/{response_id}"), for the background response's id."""
    body = {"id": "resp_abc123", "object": "response", "deleted": True}
    return httpx.Response(200, json=body)


def data_url(image: BlurredImage) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(image.jpeg).decode()


def judge(c: MetaClient, image, **kwargs) -> SparkResult:
    return c.judge(
        image, prompt=PROMPT, schema=ADDRESS_SCHEMA, schema_name="address", **kwargs
    )


def image_calls(c: MetaClient, image) -> list:
    """Every call that sends an image."""
    return [
        lambda: c.segment(image, "wheel"),
        lambda: judge(c, image),
        lambda: c.count_input_tokens(image, prompt=PROMPT),
    ]


def answered(kind: str) -> httpx.Response:
    """A good answer to `kind`: the documented Muse Spark answer, or a SAM stream."""
    return fixture("spark_response.json") if kind == "judge" else sam_stream(DOC_TEXT)


def call(c: MetaClient, kind: str, image, **kwargs):
    """`judge`, or `segment` for "wheel", on `image`, passing `kwargs` on."""
    if kind == "judge":
        return judge(c, image, **kwargs)
    return c.segment(image, "wheel", **kwargs)


def request_json(request: httpx.Request) -> dict:
    return json.loads(request.content)


def test_ids_and_phrases_are_the_ones_the_rules_name():
    assert BASE_URL == "https://api.meta.ai/v1"
    assert (SAM_MODEL, SPARK_MODEL, TRANSCRIBE_MODEL) == (
        "sam-3.1",
        "muse-spark-1.3",
        "muse-voice-transcribe-1.0",
    )
    assert SAM_PHRASES == (
        "floodwater",
        "wheel",
        "wheel rim",
        "person",
        "vehicle",
        "face",
        "license plate",
    )


def test_rejects_unblurred_input(photo):
    meta = FakeMeta()
    c, _ = client(meta)
    with pytest.raises(TypeError):
        c.segment(b"raw photo bytes", "wheel")
    with pytest.raises(TypeError):
        judge(c, np.zeros((334, 320, 3), np.uint8))
    with pytest.raises(TypeError):
        c.count_input_tokens(photo.bgr(), prompt=PROMPT)
    assert meta.requests == []


def test_rejects_blurred_image_subclass(photo):
    class Unchecked(BlurredImage):
        pass

    token = face_blur._TOKEN  # only to build the subclass; the client must still refuse
    image = Unchecked(
        photo.jpeg, photo.width, photo.height, photo.faces, photo.blur_version, token
    )
    meta = FakeMeta()
    c, _ = client(meta)
    for call in image_calls(c, image):
        with pytest.raises(TypeError):
            call()
    assert meta.requests == []


def test_missing_or_short_key_raises_without_echo(monkeypatch):
    with pytest.raises(MissingApiKey) as exc:
        MetaClient(api_key="\x16")
    assert "\x16" not in str(exc.value)
    assert "missing or too short" in str(exc.value)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with pytest.raises(MissingApiKey, match="missing or too short"):
        MetaClient()


def test_short_key_refused(monkeypatch):
    short = "k" * 19
    with pytest.raises(MissingApiKey) as exc:
        MetaClient(api_key=short)
    assert short not in str(exc.value)
    monkeypatch.setenv("MODEL_API_KEY", short)
    with pytest.raises(MissingApiKey):
        MetaClient()
    MetaClient(api_key="k" * 20)  # 20 characters is the floor
    monkeypatch.setenv("MODEL_API_KEY", FAKE_KEY)
    MetaClient()  # the key comes from the environment


@pytest.mark.parametrize(
    ("statuses", "calls", "raised"),
    [
        ([429, 200], 2, None),
        ([500, 200], 2, None),
        ([503, 200], 2, None),
        ([400], 1, 400),
        ([401], 1, 401),
        ([402], 1, 402),
        ([403], 1, 403),
        ([404], 1, 404),
        ([413], 1, 413),
        ([502], 1, 502),
        ([504], 1, 504),
    ],
)
def test_retries_only_on_429_500_503(photo, statuses, calls, raised):
    answers = [
        fixture("spark_response.json") if s == 200 else error(s) for s in statuses
    ]
    meta = FakeMeta(*answers)
    c, _ = client(meta)
    if raised is None:
        judge(c, photo)
    else:
        with pytest.raises(MetaApiError) as exc:
            judge(c, photo)
        assert exc.value.status == raised
    assert len(meta.requests) == calls


@pytest.mark.parametrize("form", ["seconds", "http-date"])
def test_honours_retry_after(photo, form):
    # The date is 5 s ahead, sent in whole seconds, so more than 4 s remain.
    ahead = datetime.now(UTC) + timedelta(seconds=5)
    value = (
        "3" if form == "seconds" else email.utils.format_datetime(ahead, usegmt=True)
    )
    meta = FakeMeta(error(429, {"Retry-After": value}), fixture("spark_response.json"))
    c, sleeps = client(meta)
    judge(c, photo)
    assert 3.0 <= sleeps[0] <= 5.0
    assert len(meta.requests) == 2


@pytest.mark.parametrize(
    ("jitter", "expected"), [(0.0, [0.5, 1.0, 2.0]), (0.5, [1.0, 1.5, 2.5])]
)
def test_backoff_doubles_with_jitter(photo, jitter, expected):
    meta = FakeMeta(error(503), error(503), error(503), fixture("spark_response.json"))
    c, sleeps = client(meta, rng=lambda: jitter)
    judge(c, photo)
    assert sleeps == expected
    assert len(meta.requests) == 4


def test_stops_after_max_attempts(photo):
    meta = FakeMeta(*(error(503) for _ in range(4)))
    c, sleeps = client(meta)
    with pytest.raises(MetaApiError) as exc:
        judge(c, photo)
    assert exc.value.status == 503
    assert len(meta.requests) == 4
    assert len(sleeps) == 3


@pytest.mark.parametrize(
    "failure", [httpx.ConnectError("refused"), httpx.ReadTimeout("too slow")]
)
def test_transport_failures_raise_without_retry(photo, failure):
    requests = []

    def meta(request):
        requests.append(request)
        raise failure

    c, sleeps = client(meta)
    with pytest.raises(MetaApiError) as exc:  # through the OpenAI SDK
        judge(c, photo)
    assert exc.value.status is None
    with pytest.raises(MetaApiError) as exc:  # through httpx alone
        c.transcribe(b"RIFF....WAVE")
    assert exc.value.status is None
    assert len(requests) == 2
    assert sleeps == []


def test_judge_sends_strict_schema(photo):
    """The answer is the example response on
    https://dev.meta.ai/docs/protocols/responses ("Basic usage"), its text replaced by
    the answer on https://dev.meta.ai/docs/structured-output."""
    meta = FakeMeta(fixture("spark_response.json"))
    c, _ = client(meta)
    result = judge(c, photo)
    [request] = meta.requests
    assert str(request.url) == BASE_URL + "/responses"
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
    body = request_json(request)
    assert body["model"] == "muse-spark-1.3"
    assert body["text"]["format"] == {
        "type": "json_schema",
        "name": "address",
        "schema": ADDRESS_SCHEMA,
        "strict": True,
    }
    assert body["store"] is False  # R76
    assert "stream" not in body and "background" not in body
    [message] = body["input"]
    assert message["role"] == "user"
    assert message["content"] == [
        {"type": "input_text", "text": PROMPT},
        {"type": "input_image", "image_url": data_url(photo)},
    ]
    assert result.data == {
        "street": "1 Hacker Way",
        "city": "Menlo Park",
        "state": "CA",
        "zip": "94025",
    }
    assert (result.input_tokens, result.output_tokens) == (69, 163)
    assert json.loads(result.raw) == result.data  # the output text it parsed (R11)
    assert result.elapsed_s >= 0


def test_judge_non_json_raises_json_decode_error(photo):
    answer = json.loads((FIXTURES / "spark_response.json").read_text())
    answer["output"][0]["content"][0]["text"] = "The street is 1 Hacker Way."
    meta = FakeMeta(httpx.Response(200, json=answer))
    c, _ = client(meta)
    with pytest.raises(json.JSONDecodeError):
        judge(c, photo)


def test_judge_sends_reasoning_effort_and_records_reasoning_tokens(photo, caplog):
    """The usage is in the shape of "Response Usage" on
    https://dev.meta.ai/docs/api-reference/responses/schemas, with 1,234 reasoning
    tokens. The documented example's usage has no breakdown."""
    caplog.set_level(logging.INFO)
    answer = json.loads((FIXTURES / "spark_response.json").read_text())
    answer["usage"] = {
        "input_tokens": 69,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens": 1397,
        "output_tokens_details": {"reasoning_tokens": 1234},
        "total_tokens": 1466,
    }
    meta = FakeMeta(httpx.Response(200, json=answer), fixture("spark_response.json"))
    c, _ = client(meta)
    result = judge(c, photo, reasoning_effort="low")
    assert request_json(meta.requests[0])["reasoning"] == {"effort": "low"}
    assert result.reasoning_tokens == 1234
    [line] = [r for r in caplog.records if r.name == "lusot.meta"]
    assert json.loads(line.getMessage())["reasoning_tokens"] == 1234
    plain = judge(c, photo)
    assert "reasoning" not in request_json(meta.requests[1])
    assert plain.reasoning_tokens is None


def test_judge_refuses_an_unknown_effort(photo):
    """The efforts listed on https://dev.meta.ai/docs/reasoning, read Oct 30, 2026
    (P15). Its "none" is "Not supported by Muse Wonder or Muse Spark" (HTTP 400), so
    it is refused before a request is sent, like a value the page doesn't list."""
    assert REASONING_EFFORTS == ("minimal", "low", "medium", "high", "xhigh", "max")
    meta = FakeMeta()  # no scripted response: a request would fail the test
    c, _ = client(meta)
    for effort in ("none", "turbo"):
        with pytest.raises(ValueError):
            judge(c, photo, reasoning_effort=effort)
    assert meta.requests == []
    # Each listed effort is sent as given.
    meta = FakeMeta(*(fixture("spark_response.json") for _ in REASONING_EFFORTS))
    c, _ = client(meta)
    for effort in REASONING_EFFORTS:
        judge(c, photo, reasoning_effort=effort)
    sent = [request_json(request)["reasoning"] for request in meta.requests]
    assert sent == [{"effort": effort} for effort in REASONING_EFFORTS]


def test_judge_raises_model_refused_on_a_refusal_part(photo, caplog):
    """The refusal is a RefusalContent part, {"type": "refusal", "refusal": ...}, on
    https://dev.meta.ai/docs/api-reference/responses/schemas, in place of the
    documented answer's output_text part (C86)."""
    caplog.set_level(logging.DEBUG)
    words = "REFUSAL-MARKER-86: I can't help with that."
    refusal = {"type": "refusal", "refusal": words}
    answer = json.loads((FIXTURES / "spark_response.json").read_text())
    answer["output"][0]["content"] = [refusal]
    meta = FakeMeta(httpx.Response(200, json=answer))
    c, _ = client(meta)
    with pytest.raises(ModelRefused) as exc:
        judge(c, photo)
    assert not isinstance(exc.value, MetaApiError)  # it ends refused, not failed
    assert words not in str(exc.value)
    assert words not in caplog.text
    # An incomplete answer stays a model error, cut-off JSON and refusal alike.
    cut_off = {"type": "output_text", "text": '{"street": "1 Hack', "annotations": []}
    for part in (cut_off, refusal):
        answer["output"][0] |= {"status": "incomplete", "content": [part]}
        incomplete = answer | {
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
        }
        meta = FakeMeta(httpx.Response(200, json=incomplete))
        c, _ = client(meta)
        with pytest.raises(MetaApiError) as exc:
            judge(c, photo)
        assert exc.value.status is None
    assert words not in caplog.text


def test_judge_reads_only_a_finished_answer(photo):
    # R104: Meta's schema makes `status` optional, so an answer without one is read,
    # but any status other than completed is a model error, before the refusal check.
    answer = json.loads((FIXTURES / "spark_response.json").read_text())
    del answer["status"]
    meta = FakeMeta(httpx.Response(200, json=answer))
    c, _ = client(meta)
    assert judge(c, photo).data["city"] == "Menlo Park"
    answer["output"][0]["content"] = [{"type": "refusal", "refusal": "No."}]
    for status in ("failed", "cancelled", "queued", "in_progress"):
        meta = FakeMeta(httpx.Response(200, json=answer | {"status": status}))
        c, _ = client(meta)
        with pytest.raises(MetaApiError) as exc:
            judge(c, photo)
        assert exc.value.status is None


def test_count_input_tokens(photo):
    """The count is the response on https://dev.meta.ai/docs/token-counting, its
    integer filled in."""
    meta = FakeMeta(fixture("input_tokens.json"))
    c, _ = client(meta)
    assert c.count_input_tokens(photo, prompt=PROMPT) == 1834
    [request] = meta.requests
    assert str(request.url) == BASE_URL + "/responses/input_tokens"
    body = request_json(request)
    assert body["model"] == "muse-spark-1.3"
    assert body["input"][0]["content"] == [
        {"type": "input_text", "text": PROMPT},
        {"type": "input_image", "image_url": data_url(photo)},
    ]


def test_segment_parses_masks_and_empty_result(photo):
    """The first stream carries the SAM output on
    https://dev.meta.ai/docs/sam/reading-segmentation ("Video output grammar", frame 0,
    a 320 x 334 frame) in the event shapes on
    https://dev.meta.ai/docs/api-reference/responses/schemas, ending in `data: [DONE]`
    as on https://dev.meta.ai/docs/api-reference/responses/retrieve-response.

    The empty one is a live sam-3.1 capture from a synthetic image on Oct 28 (R78),
    fixtures/meta/sam_live_no_match.sse: no match is a finished empty lane."""
    meta = FakeMeta(raw_stream(SAM_STREAM), raw_stream(LIVE_NO_MATCH))
    c, _ = client(meta)
    result = c.segment(photo, "wheel")
    assert result.phrase == "wheel"
    assert len(result.instances) >= 1
    for instance in result.instances:
        assert instance.mask.shape == (photo.height, photo.width)
        assert instance.mask.dtype == bool
    assert result.raw == SAM_STREAM.decode()  # the SSE text it parsed (R11)
    body = request_json(meta.requests[0])
    assert body["model"] == "sam-3.1"
    assert body["stream"] is True
    assert body["metadata"] == {"include_confidence": "true"}  # R77
    assert body["store"] is False  # C85 found that the stream accepts it (C88)
    assert body["input"][0]["content"] == [
        {"type": "input_text", "text": "wheel"},
        {"type": "input_image", "image_url": data_url(photo)},
    ]
    empty = c.segment(photo, "floodwater")
    assert empty.instances == []
    assert empty.raw == LIVE_NO_MATCH.decode()


def test_sam_store_goes_on_the_stream_only(photo):
    # C88: SAM's stream accepts store: false, so it is the default. Meta's background
    # mode refuses it with a 400, so the 504 fallback sends no store at all.
    meta = FakeMeta(
        sam_stream(DOC_TEXT),
        error(504),
        background("queued"),
        background("completed"),
        deleted(),
    )
    c, _ = client(meta)
    c.segment(photo, "wheel")
    c.segment(photo, "wheel")  # a 504, then the background path
    streamed, gateway, submitted = (request_json(r) for r in meta.requests[:3])
    assert streamed["store"] is False
    assert gateway["store"] is False
    assert "store" not in submitted
    assert submitted["background"] is True
    meta = FakeMeta(sam_stream(DOC_TEXT))
    c, _ = client(meta, sam_store=None)
    c.segment(photo, "wheel")
    assert "store" not in request_json(meta.requests[0])  # as MS1 sent it


def test_segment_box_is_half_open_in_sent_pixels(photo):
    """SAM's first record on https://dev.meta.ai/docs/sam/reading-segmentation is
    x1=211;y1=228;x2=270;y2=254 with inclusive x2 and y2, and a 27 x 60 mask (R61)."""
    meta = FakeMeta(sam_stream(DOC_TEXT))
    c, _ = client(meta)
    first, second = c.segment(photo, "wheel").instances
    assert (first.id, second.id) == (0, 1)
    assert first.box == (211.0, 228.0, 271.0, 255.0)
    assert second.box == (155.0, 228.0, 203.0, 255.0)
    x0, y0, x1, y1 = (int(v) for v in first.box)
    outside = first.mask.copy()
    outside[y0:y1, x0:x1] = False
    assert not outside.any()
    assert first.mask[y0:y1, x0:x1].sum() == 1539  # the decoded 27 x 60 mask
    assert first.score is None  # this documented record carries no `c`


def test_segment_reads_sams_confidence_as_the_score(photo):
    meta = FakeMeta(sam_stream(CONFIDENT_TEXT))
    c, _ = client(meta)
    first, second = c.segment(photo, "wheel").instances
    assert isinstance(first.score, float)
    assert first.score == 0.9609375
    assert second.score == 0.75  # the mask's `c`, not the box's 0.5


@pytest.mark.parametrize(
    "finish",
    [
        [part_done(DOC_TEXT)],  # as meta-sam-parser's README describes the live API
        [text_done(DOC_TEXT)],  # the review's first probe (R78)
        [text_done(DOC_TEXT), part_done(DOC_TEXT)],  # as the Oct 28 live streams do
    ],
)
def test_segment_reads_a_text_finished_without_deltas(photo, finish):
    meta = FakeMeta(sse(CREATED, *finish, COMPLETED_EVENT))
    c, _ = client(meta)
    assert len(c.segment(photo, "wheel").instances) == 2


@pytest.mark.parametrize(
    "events",
    [
        # The review's second probe: the output only in the completed event
        [CREATED, COMPLETED_FULL],
        [CREATED, DELTA, COMPLETED_FULL],  # deltas, but the lane never finished
        [CREATED, COMPLETED_EVENT],  # no lane at all
    ],
)
def test_segment_completed_without_a_finished_lane_raises(photo, events):
    # A completed stream must finish its text lane, as every live one does (R78).
    meta = FakeMeta(sse(*events))
    c, _ = client(meta)
    with pytest.raises(MetaApiError) as exc:
        c.segment(photo, "wheel")
    assert exc.value.status is None
    assert len(meta.requests) == 1


@pytest.mark.parametrize(
    "events",
    [
        # Deltas that hold half the text the finished part holds
        [CREATED, DELTA, part_done(DOC_TEXT), COMPLETED_EVENT],
        # Two finishing events that disagree
        [CREATED, text_done(DOC_TEXT), part_done(""), COMPLETED_EVENT],
    ],
)
def test_segment_finished_text_that_disagrees_raises(photo, events):
    meta = FakeMeta(sse(*events))
    c, _ = client(meta)
    with pytest.raises(MetaApiError) as exc:
        c.segment(photo, "wheel")
    assert exc.value.status is None
    assert len(meta.requests) == 1


def test_segment_ignores_keepalive_events(photo):
    # https://dev.meta.ai/docs/api-reference/responses/schemas lists a heartbeat
    # among a stream's wire events ("Response Keepalive Event").
    keepalive = {"type": "keepalive", "sequence_number": 1}
    finish = [text_done(DOC_TEXT), part_done(DOC_TEXT)]
    meta = FakeMeta(sse(CREATED, keepalive, *finish, keepalive, COMPLETED_EVENT))
    c, _ = client(meta)
    assert len(c.segment(photo, "wheel").instances) == 2


def test_segment_refuses_a_frame_size_other_than_the_image(photo):
    # Each box token names the frame it was found in; it must be the sent photo.
    meta = FakeMeta(sam_stream(DOC_TEXT.replace("w=320;h=334", "w=640;h=480")))
    c, _ = client(meta)
    with pytest.raises(MetaApiError) as exc:
        c.segment(photo, "wheel")
    assert exc.value.status is None
    assert len(meta.requests) == 1


@pytest.mark.parametrize(
    "ending",
    [
        {"type": "response.failed", "response": {**COMPLETED, "status": "failed"}},
        {
            "type": "response.incomplete",
            "response": {**COMPLETED, "status": "incomplete"},
        },
        {"type": "error", "code": "server_error", "message": "Something failed."},
        {"type": "response.refusal.done", "refusal": "I can't help with that."},
        {"error": {"message": "Stream failed.", "type": "server_error"}},
        None,  # the stream ends with no terminal event
    ],
)
def test_segment_stream_that_does_not_complete_raises(photo, ending):
    events = [CREATED, DELTA] + ([ending] if ending else [])
    meta = FakeMeta(sse(*events))
    c, sleeps = client(meta)
    with pytest.raises(MetaApiError) as exc:
        c.segment(photo, "wheel")
    assert exc.value.status is None
    assert len(meta.requests) == 1
    assert sleeps == []


def test_segment_retries_a_mid_stream_shutdown(photo):
    # A shutdown counts as a 503: the whole request runs again after the backoff (R77).
    meta = FakeMeta(sse(CREATED, DELTA, SHUTDOWN), raw_stream(SAM_STREAM))
    c, sleeps = client(meta, rng=lambda: 0.0)
    result = c.segment(photo, "wheel")
    assert len(result.instances) == 2
    assert len(meta.requests) == 2
    assert request_json(meta.requests[0]) == request_json(meta.requests[1])
    assert sleeps == [0.5]


def test_segment_shutdowns_on_every_try_raise_after_max_attempts(photo):
    meta = FakeMeta(*(sse(CREATED, DELTA, SHUTDOWN) for _ in range(4)))
    c, sleeps = client(meta, rng=lambda: 0.0)
    with pytest.raises(MetaApiError) as exc:
        c.segment(photo, "wheel")
    assert exc.value.status is None
    assert len(meta.requests) == 4
    assert sleeps == [0.5, 1.0, 2.0]


def test_segment_dropped_stream_raises_without_retry(photo):
    class Dropped(httpx.SyncByteStream):
        def __iter__(self):
            yield SAM_STREAM[:200]
            raise httpx.ReadError("connection dropped")

    stream = httpx.Response(
        200, headers={"content-type": "text/event-stream"}, stream=Dropped()
    )
    meta = FakeMeta(stream)
    c, sleeps = client(meta)
    with pytest.raises(MetaApiError) as exc:
        c.segment(photo, "wheel")
    assert exc.value.status is None
    assert len(meta.requests) == 1
    assert sleeps == []


@pytest.mark.parametrize(
    "text",
    [
        "No objects found.\n",
        # A mask payload that doesn't decode
        "<0f>0<|box;x1=1;y1=1;x2=2;y2=2;w=320;h=334|><|mask;x=0;y=0;data=2,2,~bad|>\n",
        # The 5 x 5 mask on https://github.com/meta-models/meta-sam (protocol/sam3.md),
        # on a 4 x 4 box, then on a 5 x 5 box one pixel past the 320 px wide photo, in
        # the photo's frame: meta-sam-parser refuses that box (invalid_box)
        (
            "<0f>0<|box;x1=10;y1=20;x2=13;y2=23;w=320;h=334|>"
            "<|mask;x=0;y=0;data=5,5,!!!!!(QO(0lu8?|>\n"
        ),
        (
            "<0f>0<|box;x1=316;y1=20;x2=320;y2=24;w=320;h=334|>"
            "<|mask;x=0;y=0;data=5,5,!!!!!(QO(0lu8?|>\n"
        ),
    ],
)
def test_segment_output_it_cannot_place_raises(photo, text):
    # A record dropped or misplaced must not read as a missing match (R63).
    meta = FakeMeta(sam_stream(text))
    c, _ = client(meta)
    with pytest.raises(MetaApiError) as exc:
        c.segment(photo, "wheel")
    assert exc.value.status is None
    assert len(meta.requests) == 1


def test_segment_places_a_mask_scaled_to_a_1024_px_side(wide_photo):
    """MS3a Task 16: on a 1600 x 1000 photo, SAM sent the box
    x1=0;y1=300;x2=1599;y2=999 (700 x 1600) with a 448 x 1024 mask, scaled by 0.64 so
    its longer side is 1024 px. The client scales it up to the box, center-aligned."""
    raster = np.zeros((448, 1024), np.uint8)
    # Edges that a row and a column of the box map to exactly
    raster[:152, :296] = 1
    text = mask_text((0, 300, 1599, 999), raster, (1600, 1000))
    meta = FakeMeta(sam_stream(text))
    c, _ = client(meta)
    (instance,) = c.segment(wide_photo, "floodwater").instances
    assert instance.box == (0.0, 300.0, 1600.0, 1000.0)
    assert instance.mask.shape == (1000, 1600)
    assert not instance.mask[:300].any()  # the rows above the box
    inside = instance.mask[300:]
    # Row i takes source row floor((i + 0.5) * 448 / 700): 236 takes 151.36 -> 151,
    # and 237 takes exactly 152. Column j takes floor((j + 0.5) * 1024 / 1600): 461
    # takes 295.36 -> 295, and 462 takes exactly 296.
    assert inside[0, 0] and inside[236, 461]
    assert not inside[237, 461] and not inside[236, 462]
    # Plain nearest, and OpenCV's INTER_NEAREST_EXACT at the exact edges, give 238 x 463
    assert instance.mask.sum() == 237 * 462


def test_segment_places_a_tall_mask_scaled_to_a_1024_px_side():
    # A 1200 x 50 box in a 1000 x 1600 portrait photo comes as 1024 rows by
    # round(50 * 1024 / 1200) = 43 columns.
    raster = np.zeros((1024, 43), np.uint8)
    raster[:303] = 1
    text = mask_text((300, 100, 349, 1299), raster, (1000, 1600))
    meta = FakeMeta(sam_stream(text))
    c, _ = client(meta)
    (instance,) = c.segment(gradient(1000, 1600), "person").instances
    assert instance.box == (300.0, 100.0, 350.0, 1300.0)
    inside = instance.mask[100:1300, 300:350]
    # Row i takes floor((i + 0.5) * 1024 / 1200): 354 takes 302, 355 takes 303.
    assert inside[354].all() and not inside[355].any()
    assert instance.mask.sum() == inside.sum() == 355 * 50


@pytest.mark.parametrize("rows", [19, 21])
def test_segment_allows_a_scaled_short_side_1_px_off(wide_photo, rows):
    # SAM's rounding is unknown: a 32 x 1600 box scales to 20.48 rows at 1024 px.
    raster = np.ones((rows, 1024), np.uint8)
    meta = FakeMeta(sam_stream(mask_text((0, 0, 1599, 31), raster, (1600, 1000))))
    c, _ = client(meta)
    (instance,) = c.segment(wide_photo, "floodwater").instances
    assert instance.mask.sum() == instance.mask[:32].sum() == 32 * 1600


@pytest.mark.parametrize(
    ("box", "size"),
    [
        # Rasters smaller than a box with no side over 1024 px: scaled by 0.64, as a
        # whole-frame scale would, and 1024 px wide but a row short of its box
        ((0, 0, 999, 24), (16, 640)),
        ((0, 0, 1023, 19), (19, 1024)),
        # A 32 x 1600 box (20.48 rows at 1024 px): a long side of 1000, a long side
        # 1 px short or over, a short side 2 px off either way, and the scaled sides
        # swapped
        ((0, 0, 1599, 31), (20, 1000)),
        ((0, 0, 1599, 31), (20, 1023)),
        ((0, 0, 1599, 31), (20, 1025)),
        ((0, 0, 1599, 31), (22, 1024)),
        ((0, 0, 1599, 31), (18, 1024)),
        ((0, 0, 1599, 31), (1024, 20)),
        # A 34 x 1600 box scales to 21.76 rows: 20 is 2 px off round's 22, though
        # only 1 px off floor's 21
        ((0, 0, 1599, 33), (20, 1024)),
        # Rasters larger than their box: 33 x 1600 on 32 x 1600, and 6 x 1024 on
        # 5 x 1100, though 6 is within 1 px of round(5 * 1024 / 1100) = 5
        ((0, 0, 1599, 31), (33, 1600)),
        ((0, 0, 1099, 4), (6, 1024)),
    ],
)
def test_segment_mask_scaled_any_other_way_raises(wide_photo, box, size):
    # Only a mask scaled to a 1024 px side is placed; any other size must not read as
    # a match or as no match (R63).
    text = mask_text(box, np.ones(size, np.uint8), (1600, 1000))
    meta = FakeMeta(sam_stream(text))
    c, _ = client(meta)
    with pytest.raises(MetaApiError) as exc:
        c.segment(wide_photo, "floodwater")
    assert exc.value.status is None
    assert len(meta.requests) == 1


@pytest.mark.parametrize("size", [(1023, 1024), (1024, 1023)])
def test_segment_square_mask_needs_both_sides_scaled_to_1024(square_photo, size):
    # Both sides of a square box are its longer side, so both must be 1024 px.
    text = mask_text((0, 0, 1099, 1099), np.ones(size, np.uint8), (1100, 1100))
    meta = FakeMeta(sam_stream(text))
    c, _ = client(meta)
    with pytest.raises(MetaApiError) as exc:
        c.segment(square_photo, "floodwater")
    assert exc.value.status is None
    assert len(meta.requests) == 1


def test_segment_504_falls_back_to_background_polling(photo):
    meta = FakeMeta(
        error(504),
        background("queued"),
        background("in_progress"),
        background("completed"),
        deleted(),
    )
    c, sleeps = client(meta)
    result = c.segment(photo, "wheel")
    assert [(r.method, str(r.url)) for r in meta.requests] == [
        ("POST", BASE_URL + "/responses"),
        ("POST", BASE_URL + "/responses"),
        ("GET", BASE_URL + "/responses/resp_abc123"),
        ("GET", BASE_URL + "/responses/resp_abc123"),
        ("DELETE", BASE_URL + "/responses/resp_abc123"),  # once read (C88)
    ]
    streamed, submitted = (request_json(r) for r in meta.requests[:2])
    assert streamed["stream"] is True
    assert submitted["background"] is True
    assert "stream" not in submitted
    assert "store" not in submitted  # stored, as Meta stores by default, to be polled
    assert submitted["metadata"] == {"include_confidence": "true"}
    assert submitted["input"] == streamed["input"]
    assert submitted["model"] == "sam-3.1"
    assert len(result.instances) == 2
    assert json.loads(result.raw) == {**COMPLETED, "background": True}  # (R11)
    assert sleeps == [1.0, 1.0]


def test_background_413_raises_after_one_call(photo):
    """A background body over 1 MiB gets 413, which isn't retried (R75):
    https://dev.meta.ai/docs/error-handling ("413 Payload Too Large")."""
    meta = FakeMeta(error(504), error(413))
    c, sleeps = client(meta)
    with pytest.raises(MetaApiError) as exc:
        c.segment(photo, "wheel")
    assert exc.value.status == 413
    assert len(meta.requests) == 2
    assert request_json(meta.requests[1])["background"] is True
    assert sleeps == []


@pytest.mark.parametrize("status", ["failed", "incomplete", "cancelled"])
def test_background_response_that_does_not_complete_raises(photo, status):
    meta = FakeMeta(error(504), background("queued"), background(status), deleted())
    c, _ = client(meta)
    with pytest.raises(MetaApiError) as exc:
        c.segment(photo, "wheel")
    assert exc.value.status is None
    assert len(meta.requests) == 4  # no further poll, then the delete (R106)
    assert meta.requests[-1].method == "DELETE"


@pytest.mark.parametrize(
    ("output", "matches"),
    [
        # The live completed response for no match: one finished empty part (R78)
        (sam_event("response.completed", LIVE_NO_MATCH)["response"]["output"], 0),
        (COMPLETED["output"], 2),
        ([], None),  # no output_text part: not a reading of "no matches"
    ],
)
def test_background_reads_only_a_finished_output_text_part(photo, output, matches):
    done = httpx.Response(200, json={**COMPLETED, "background": True, "output": output})
    meta = FakeMeta(error(504), background("queued"), done, deleted())
    c, _ = client(meta)
    if matches is None:
        with pytest.raises(MetaApiError) as exc:
            c.segment(photo, "wheel")
        assert exc.value.status is None
    else:
        assert len(c.segment(photo, "wheel").instances) == matches
    assert len(meta.requests) == 4  # the last deletes the response it read (C88)


@pytest.mark.parametrize(
    ("outcome", "status"),
    [(deleted(), 200), (error(404), 404), (httpx.ConnectError("refused"), None)],
    ids=["deleted", "not-found", "no-connection"],
)
def test_background_response_is_deleted_once_read(photo, caplog, outcome, status):
    # C88: background jobs must be stored to be polled, so the client deletes one
    # once it has read it. The delete is best effort: a failure is logged by its
    # status alone and never changes the result.
    caplog.set_level(logging.INFO)
    script = FakeMeta(error(504), background("queued"), background("completed"))
    deletes = []

    def meta(request):
        if request.method != "DELETE":
            return script(request)
        deletes.append(request)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    c, _ = client(meta)
    assert len(c.segment(photo, "wheel").instances) == 2
    [delete] = deletes
    assert str(delete.url) == BASE_URL + "/responses/resp_abc123"
    lines = [
        json.loads(r.getMessage()) for r in caplog.records if r.name == "lusot.meta"
    ]
    [line] = [line for line in lines if line.get("delete")]
    assert line.keys() == {"model", "phrase", "delete", "status", "ms"}
    assert line["status"] == status


def test_background_polling_is_bounded(photo):
    meta = FakeMeta(
        error(504),
        background("queued"),
        *(background("in_progress") for _ in range(3)),
        deleted(),
    )
    c, sleeps = client(meta, timeout_s=3.0)
    with pytest.raises(MetaApiError) as exc:
        c.segment(photo, "wheel")
    assert exc.value.status is None
    assert sum(sleeps) == 3.0
    assert len(meta.requests) == 6  # the last deletes the abandoned job (R106)
    assert meta.requests[-1].method == "DELETE"


@pytest.mark.parametrize("delete_fails", [False, True], ids=["deleted", "not-deleted"])
@pytest.mark.parametrize(
    ("ending", "raised", "message"),
    [
        ("deadline", DeadlineExceeded, "wait leaves too little time"),
        ("poll bound", MetaApiError, "timed out after 3 s"),
        ("failed", MetaApiError, "ended failed"),
    ],
)
def test_abandoned_background_job_is_still_deleted(
    photo, ending, raised, message, delete_fails
):
    # R106: once Meta has stored the job, the client tries once to delete it however
    # the polling ends, and the delete never changes or masks the error raised.
    status = "failed" if ending == "failed" else "in_progress"
    script = FakeMeta(
        error(504), background("queued"), *(background(status) for _ in range(20))
    )
    deletes = []

    def meta(request):
        if request.method != "DELETE":
            return script(request)
        deletes.append(request)
        if delete_fails:
            raise httpx.ConnectError("refused")
        return deleted()

    if ending == "deadline":
        c, clock = timed_client(meta)
        kwargs = {"deadline": clock.now + 8}
    else:
        c, _ = client(meta, timeout_s=3.0)
        kwargs = {}
    with pytest.raises(MetaApiError) as exc:
        c.segment(photo, "wheel", **kwargs)
    assert type(exc.value) is raised  # the polling's own error, not the delete's
    assert message in str(exc.value)
    assert [str(r.url) for r in deletes] == [BASE_URL + "/responses/resp_abc123"]


def test_segment_runs_in_parallel_on_one_client(photo):
    # Each phrase gets its own object ids, and earlier phrases answer later, so a
    # result that crossed threads would carry another phrase's ids.
    def meta(request):
        n = SAM_PHRASES.index(request_json(request)["input"][0]["content"][0]["text"])
        time.sleep(0.005 * (len(SAM_PHRASES) - n))
        ids = DOC_TEXT.replace("<0f>0<|", f"<0f>{2 * n}<|")
        return sam_stream(ids.replace(",1<|", f",{2 * n + 1}<|"))

    c, _ = client(meta)
    with ThreadPoolExecutor(len(SAM_PHRASES)) as pool:
        results = list(pool.map(lambda phrase: c.segment(photo, phrase), SAM_PHRASES))
    assert [result.phrase for result in results] == list(SAM_PHRASES)
    assert [[i.id for i in result.instances] for result in results] == [
        [2 * n, 2 * n + 1] for n in range(len(SAM_PHRASES))
    ]


TIMEOUT_KEYS = ("connect", "read", "write", "pool")


@pytest.mark.parametrize("kind", ["judge", "segment"])
def test_retry_after_past_the_deadline_stops(photo, kind):
    # Meta's overload replies ask for 60 s. The client never retries early, so with
    # 5 s left it stops instead of waiting (C84).
    meta = FakeMeta(error(503, {"Retry-After": "60"}))
    c, clock = timed_client(meta)
    with pytest.raises(DeadlineExceeded) as exc:
        call(c, kind, photo, deadline=clock.now + 5)
    assert isinstance(exc.value, MetaApiError)  # so it ends failed/model_error
    assert exc.value.status is None
    assert len(meta.requests) == 1
    assert clock.sleeps == []


@pytest.mark.parametrize("kind", ["judge", "segment"])
def test_retry_after_within_the_deadline_is_honoured(photo, kind):
    meta = FakeMeta(error(503, {"Retry-After": "2"}), answered(kind))
    c, clock = timed_client(meta, rng=lambda: 0.0)
    result = call(c, kind, photo, deadline=clock.now + 30)
    assert result.raw  # the parsed answer
    assert clock.sleeps == [2.0]  # Retry-After, not the 0.5 s backoff
    # Each try's timeouts are the time left when it starts (a SAM stream's read is also
    # capped at 20 s, so the connect timeout shows it for both).
    assert [r.extensions["timeout"]["connect"] for r in meta.requests] == [30.0, 28.0]


@pytest.mark.parametrize("kind", ["judge", "segment"])
@pytest.mark.parametrize(("left", "sent"), [(0.0, 0), (4.0, 0), (5.0, 1)])
def test_no_try_starts_with_under_5_s_left(photo, kind, left, sent):
    # R106 (C88): a try with under 5 s left can't finish but may still be billed, so
    # not even the first one is sent.
    meta = FakeMeta(answered(kind))
    c, clock = timed_client(meta)
    if sent:
        assert call(c, kind, photo, deadline=clock.now + left).raw
    else:
        with pytest.raises(DeadlineExceeded):
            call(c, kind, photo, deadline=clock.now + left)
    assert len(meta.requests) == sent


@pytest.mark.parametrize(("left", "retried"), [(5.4, False), (5.5, True)])
def test_no_retry_starts_with_under_5_s_left(photo, left, retried):
    # R104 (C88): a try with under 5 s left can't finish but may still be billed. The
    # 503's backoff is 0.5 s, so 4.9 s or 5.0 s would be left for the retry.
    meta = FakeMeta(error(503), fixture("spark_response.json"))
    c, clock = timed_client(meta, rng=lambda: 0.0)
    if retried:
        judge(c, photo, deadline=clock.now + left)
        assert clock.sleeps == [0.5]
    else:
        with pytest.raises(DeadlineExceeded):
            judge(c, photo, deadline=clock.now + left)
        assert clock.sleeps == []
    assert len(meta.requests) == (2 if retried else 1)


def test_background_poll_stops_at_the_deadline(photo):
    never = (background("in_progress") for _ in range(3))
    meta = FakeMeta(error(504), background("queued"), *never, deleted())
    c, clock = timed_client(meta)
    deadline = clock.now + 8
    with pytest.raises(DeadlineExceeded) as exc:
        c.segment(photo, "wheel", deadline=deadline)
    assert exc.value.status is None
    assert clock.now <= deadline  # no wait ran past it
    # Each poll is a try, so a fourth wait, which would leave 4 s, isn't started.
    assert clock.sleeps == [1.0] * 3
    # The stream, the submit, 3 polls, then the delete of the abandoned job (R106).
    assert [r.method for r in meta.requests] == ["POST"] * 2 + ["GET"] * 3 + ["DELETE"]


class Chunks(httpx.SyncByteStream):
    """A response body served in `chunks`. Before each chunk after the first, the
    clock moves `gap` seconds; a chunk that is an exception is raised instead."""

    def __init__(self, chunks: list, clock: FakeClock, gap: float = 0.0) -> None:
        self.chunks = chunks
        self.clock = clock
        self.gap = gap
        self.closed = False

    def __iter__(self):
        for n, chunk in enumerate(self.chunks):
            if n:
                self.clock.now += self.gap
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk

    def close(self) -> None:
        self.closed = True


def chunked(body: Chunks) -> httpx.Response:
    return httpx.Response(
        200, headers={"content-type": "text/event-stream"}, stream=body
    )


def stalls(clock: FakeClock, wait: float) -> Chunks:
    """A SAM stream that sends one chunk, then stalls: its next read waits `wait`
    seconds, its read timeout, and times out."""
    return Chunks(
        [SAM_STREAM[:200], httpx.ReadTimeout("no event in time")], clock, gap=wait
    )


def test_stream_read_timeout_shrinks_to_the_time_left(photo):
    # With 6 s left (R106 sends nothing under 5 s), every timeout is at most 6 s.
    clock = FakeClock()
    stalled = stalls(clock, 6.0)
    meta = FakeMeta(sam_stream(DOC_TEXT), chunked(stalled))
    c, _ = timed_client(meta, clock)
    assert len(c.segment(photo, "wheel", deadline=clock.now + 6).instances) == 2
    assert meta.requests[0].extensions["timeout"] == dict.fromkeys(TIMEOUT_KEYS, 6.0)
    # The read timeout is the time left, so a read that times out is at the deadline.
    with pytest.raises(DeadlineExceeded) as exc:
        c.segment(photo, "wheel", deadline=clock.now + 6)
    assert exc.value.status is None
    assert stalled.closed  # its connection isn't left open
    assert len(meta.requests) == 2


@pytest.mark.parametrize(
    ("left", "read", "raised"),
    [
        (None, 90.0, MetaApiError),  # no deadline: MS1's read timeout, uncapped
        (150.0, 20.0, MetaApiError),  # a stall well before the deadline
        (60.0, 20.0, MetaApiError),  # cut by the cap, yet still before the deadline
        (5.0, 5.0, DeadlineExceeded),  # the time left is shorter, so it ends at it
    ],
)
def test_stream_idle_wait_is_capped_under_a_deadline(photo, left, read, raised):
    # R103 (C88): under a deadline a SAM stream read waits at most 20 s for its next
    # event, and a timeout is DeadlineExceeded only at or after the deadline.
    clock = FakeClock()
    stalled = stalls(clock, read)
    meta = FakeMeta(chunked(stalled))
    c, _ = timed_client(meta, clock)
    deadline = None if left is None else clock.now + left
    with pytest.raises(MetaApiError) as exc:
        c.segment(photo, "wheel", deadline=deadline)
    assert type(exc.value) is raised
    assert exc.value.status is None
    timeout = meta.requests[0].extensions["timeout"]
    assert timeout["read"] == read
    assert timeout["connect"] == min(90.0, left or 90.0)  # only the read is capped
    assert stalled.closed


@pytest.mark.parametrize(("left", "stops"), [(5.0, True), (30.0, False)])
def test_stream_kept_open_past_the_deadline_stops(photo, left, stops):
    # httpx sets one read timeout per request, and keepalive events can hold a SAM
    # stream open, so the client also checks the clock as each chunk arrives (R101).
    clock = FakeClock()
    body = Chunks([SAM_STREAM[:200], SAM_STREAM[200:]], clock, gap=10.0)
    meta = FakeMeta(chunked(body))
    c, _ = timed_client(meta, clock)
    if stops:
        with pytest.raises(DeadlineExceeded) as exc:
            c.segment(photo, "wheel", deadline=clock.now + left)
        assert exc.value.status is None
    else:
        assert len(c.segment(photo, "wheel", deadline=clock.now + left).instances) == 2
    assert body.closed
    assert len(meta.requests) == 1


def test_judge_timeout_shrinks_to_the_time_left(photo):
    # With 6 s left (R106 sends nothing under 5 s), every timeout is at most 6 s.
    meta = FakeMeta(fixture("spark_response.json"))
    c, clock = timed_client(meta)
    judge(c, photo, deadline=clock.now + 6)
    assert meta.requests[0].extensions["timeout"] == dict.fromkeys(TIMEOUT_KEYS, 6.0)
    sent = []
    clock = FakeClock()

    def times_out(request):
        sent.append(request)
        clock.now += request.extensions["timeout"]["read"]  # it waits it out
        raise httpx.ReadTimeout("no answer in time")

    c, _ = timed_client(times_out, clock)
    with pytest.raises(DeadlineExceeded) as exc:  # the timeout was the time left
        judge(c, photo, deadline=clock.now + 6)
    assert exc.value.status is None
    # With more time left than timeout_s, a timeout is the client's own, as in MS1.
    with pytest.raises(MetaApiError) as exc:
        judge(c, photo, deadline=clock.now + 300)
    assert type(exc.value) is MetaApiError
    assert sent[1].extensions["timeout"]["read"] == 90.0
    assert len(sent) == 2  # neither timeout is retried


def form_parts(request: httpx.Request) -> dict[str, tuple[str, bytes]]:
    """Each multipart part's name, mapped to its content type and body."""
    head = b"Content-Type: " + request.headers["content-type"].encode() + b"\r\n\r\n"
    message = email.message_from_bytes(head + request.content, policy=email.policy.HTTP)
    return {
        part.get_param("name", header="content-disposition"): (
            part.get_content_type(),
            part.get_payload(decode=True),
        )
        for part in message.iter_parts()
    }


def test_transcribe_sends_one_wav_clip():
    """The answer is the example on https://dev.meta.ai/docs/speech-to-text ("Read the
    response"). The request follows
    https://dev.meta.ai/docs/api-reference/voice/transcribe."""
    wav = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"  # passed through untouched
    meta = FakeMeta(fixture("transcribe.json"), fixture("transcribe.json"))
    c, _ = client(meta)
    result = c.transcribe(wav, keywords=["MMDA", "baha"])
    assert result.text == "How is the weather? It is raining."
    assert json.loads(result.raw)["sessionId"] == "9f1c..."
    request = meta.requests[0]
    assert (request.method, str(request.url)) == ("POST", BASE_URL + "/asr/transcribe")
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
    assert request.headers["accept"] == "application/json"
    parts = form_parts(request)
    assert parts["audio"] == ("audio/wav", wav)
    kind, settings = parts["request"]
    assert kind == "application/json"
    assert json.loads(settings) == {
        "model": "muse-voice-transcribe-1.0",
        "audioEncoding": "WAV",
        "mode": "PUSH_TO_TALK",
        "keywords": ["MMDA", "baha"],
    }
    c.transcribe(wav)
    assert "keywords" not in json.loads(form_parts(meta.requests[1])["request"][1])


def test_contributor_model_is_refused():
    with pytest.raises(ValueError):
        MetaClient._check_model("muse-spark-1.3-contributor")
    for model in (SAM_MODEL, SPARK_MODEL, TRANSCRIBE_MODEL):
        MetaClient._check_model(model)


def test_protocol_and_fake_take_the_clients_arguments():
    # The pipeline is typed against ModelClient and tested with FakeClient, and no
    # type checker runs, so this keeps both in step with the client (C84).
    def arguments(function) -> list[tuple]:
        parameters = inspect.signature(function).parameters.values()
        return [(p.name, p.kind, p.default) for p in parameters]

    keyword_only = inspect.Parameter.KEYWORD_ONLY
    for method, added in [
        ("segment", {"deadline"}),
        ("judge", {"deadline", "reasoning_effort"}),
    ]:
        real = arguments(getattr(MetaClient, method))
        keywords = {
            name: default for name, kind, default in real if kind == keyword_only
        }
        assert all(keywords.get(name, "missing") is None for name in added)
        assert arguments(getattr(ModelClient, method)) == real
        assert arguments(getattr(FakeClient, method)) == real


@pytest.mark.parametrize(
    ("call", "fields"),
    [
        ("judge", {"model", "schema_name", "status", "ms"}),
        ("segment", {"model", "phrase", "status", "ms"}),
    ],
)
def test_key_never_logged(photo, caplog, call, fields):
    # Every logger without a level of its own logs at DEBUG here (R64).
    caplog.set_level(logging.DEBUG)
    if call == "judge":
        meta = FakeMeta(fixture("spark_response.json"))
        c, _ = client(meta)
        judge(c, photo)
    else:
        meta = FakeMeta(sam_stream(DOC_TEXT))
        c, _ = client(meta)
        c.segment(photo, "wheel")
    image = base64.b64encode(photo.jpeg).decode()
    assert caplog.records
    for record in caplog.records:
        message = record.getMessage()
        assert FAKE_KEY not in message
        assert image[:64] not in message  # no part of the photo
        assert PROMPT not in message
        assert "Hacker Way" not in message  # nor the model's answer
    assert FAKE_KEY not in caplog.text
    assert image[:64] not in caplog.text
    [line] = [r for r in caplog.records if r.name == "lusot.meta"]
    assert json.loads(line.getMessage()).keys() == fields
