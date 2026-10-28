"""Tests for the Meta client (C10, C37). Every HTTP call goes to httpx.MockTransport.

The fixtures in fixtures/meta/ are Meta's documented examples. Each test that uses one
names its source in its docstring.
"""

import base64
import email.policy
import email.utils
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest

from lusot_analysis import face_blur
from lusot_analysis.face_blur import BlurredImage, blur_for_meta
from lusot_analysis.meta_client import (
    BASE_URL,
    SAM_MODEL,
    SAM_PHRASES,
    SPARK_MODEL,
    TRANSCRIBE_MODEL,
    MetaApiError,
    MetaClient,
    MissingApiKey,
    SparkResult,
)

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
SAM_EVENTS = [
    json.loads(line.removeprefix("data: "))
    for line in SAM_STREAM.decode().splitlines()
    if line.startswith("data: {")
]


def sam_event(kind: str) -> dict:
    """The first event of `kind` in the documented SAM stream."""
    return next(event for event in SAM_EVENTS if event["type"] == kind)


CREATED = sam_event("response.created")
DELTA = sam_event("response.output_text.delta")
PART_DONE = sam_event("response.content_part.done")
COMPLETED = sam_event("response.completed")["response"]  # SAM's output included
# The completed event with no output: the client reads the text from earlier events.
COMPLETED_EVENT = {
    "type": "response.completed",
    "response": {**COMPLETED, "output": []},
}


@pytest.fixture(scope="module")
def photo() -> BlurredImage:
    """A face-free 320 x 334 photo, the size of the documented SAM example's frame."""
    row = np.linspace(0, 255, 320).astype(np.uint8)
    bgr = np.dstack([np.tile(row, (334, 1))] * 3)
    return blur_for_meta(cv2.imencode(".jpg", bgr)[1].tobytes())


class FakeMeta:
    """Stands in for api.meta.ai: answers each request with the next scripted one."""

    def __init__(self, *responses: httpx.Response) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0)


def client(meta, **kwargs) -> tuple[MetaClient, list[float]]:
    """A client on `meta`, and the list its sleeps are recorded in."""
    sleeps: list[float] = []
    transport = httpx.MockTransport(meta)
    c = MetaClient(FAKE_KEY, transport=transport, sleep=sleeps.append, **kwargs)
    return c, sleeps


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


def documented_stream() -> httpx.Response:
    """The SAM stream in fixtures/meta/sam_stream.sse, as Meta would send it."""
    headers = {"content-type": "text/event-stream"}
    return httpx.Response(200, headers=headers, content=SAM_STREAM)


def sam_stream(text: str) -> httpx.Response:
    """A SAM stream that sends `text` as its output, then completes."""
    return sse(CREATED, {**DELTA, "delta": text}, COMPLETED_EVENT)


def background(status: str) -> httpx.Response:
    """The background response in `status`. Completed, it has the documented output."""
    body = {**COMPLETED, "background": True, "status": status}
    if status != "completed":
        body["output"] = []
    return httpx.Response(200, json=body)


def data_url(image: BlurredImage) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(image.jpeg).decode()


def judge(c: MetaClient, image) -> SparkResult:
    return c.judge(image, prompt=PROMPT, schema=ADDRESS_SCHEMA, schema_name="address")


def image_calls(c: MetaClient, image) -> list:
    """Every call that sends an image."""
    return [
        lambda: c.segment(image, "wheel"),
        lambda: judge(c, image),
        lambda: c.count_input_tokens(image, prompt=PROMPT),
    ]


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
    """The stream carries the SAM output on
    https://dev.meta.ai/docs/sam/reading-segmentation ("Video output grammar", frame 0,
    a 320 x 334 frame) in the event shapes on
    https://dev.meta.ai/docs/api-reference/responses/schemas, ending in `data: [DONE]`
    as on https://dev.meta.ai/docs/api-reference/responses/retrieve-response."""
    meta = FakeMeta(documented_stream(), sse(CREATED, COMPLETED_EVENT))
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
    assert "store" not in body  # Meta's SAM pages never show `store` (R76)
    assert body["input"][0]["content"] == [
        {"type": "input_text", "text": "wheel"},
        {"type": "input_image", "image_url": data_url(photo)},
    ]
    assert c.segment(photo, "wheel").instances == []


def test_segment_box_is_half_open_in_sent_pixels(photo):
    """SAM's first record on https://dev.meta.ai/docs/sam/reading-segmentation is
    x1=211;y1=228;x2=270;y2=254 with inclusive x2 and y2, and a 27 x 60 mask (R61)."""
    meta = FakeMeta(sam_stream(PART_DONE["part"]["text"]))
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
    assert first.score is None  # the request doesn't ask for SAM's confidence


def test_segment_reads_a_finished_part_without_deltas(photo):
    # Meta's protocol lets a stream send its text only in the finished content part.
    meta = FakeMeta(sse(CREATED, PART_DONE, COMPLETED_EVENT))
    c, _ = client(meta)
    assert len(c.segment(photo, "wheel").instances) == 2


@pytest.mark.parametrize(
    "ending",
    [
        {"type": "response.failed", "response": {**COMPLETED, "status": "failed"}},
        {
            "type": "response.incomplete",
            "response": {**COMPLETED, "status": "incomplete"},
        },
        {"type": "error", "code": "server_shutting_down", "message": "Shutting down."},
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
        # on a 4 x 4 box, then on a box past the 320 px wide photo
        (
            "<0f>0<|box;x1=10;y1=20;x2=13;y2=23;w=320;h=334|>"
            "<|mask;x=0;y=0;data=5,5,!!!!!(QO(0lu8?|>\n"
        ),
        (
            "<0f>0<|box;x1=316;y1=20;x2=320;y2=24;w=400;h=334|>"
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


def test_segment_504_falls_back_to_background_polling(photo):
    meta = FakeMeta(
        error(504),
        background("queued"),
        background("in_progress"),
        background("completed"),
    )
    c, sleeps = client(meta)
    result = c.segment(photo, "wheel")
    assert [(r.method, str(r.url)) for r in meta.requests] == [
        ("POST", BASE_URL + "/responses"),
        ("POST", BASE_URL + "/responses"),
        ("GET", BASE_URL + "/responses/resp_abc123"),
        ("GET", BASE_URL + "/responses/resp_abc123"),
    ]
    streamed, submitted = (request_json(r) for r in meta.requests[:2])
    assert streamed["stream"] is True
    assert submitted["background"] is True
    assert "stream" not in submitted
    assert "store" not in submitted  # stored, as Meta stores by default, to be polled
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
    meta = FakeMeta(error(504), background("queued"), background(status))
    c, _ = client(meta)
    with pytest.raises(MetaApiError) as exc:
        c.segment(photo, "wheel")
    assert exc.value.status is None


def test_background_polling_is_bounded(photo):
    meta = FakeMeta(
        error(504), background("queued"), *(background("in_progress") for _ in range(3))
    )
    c, sleeps = client(meta, timeout_s=3.0)
    with pytest.raises(MetaApiError) as exc:
        c.segment(photo, "wheel")
    assert exc.value.status is None
    assert sum(sleeps) == 3.0
    assert len(meta.requests) == 5


def test_segment_runs_in_parallel_on_one_client(photo):
    def meta(request):
        return documented_stream()

    c, _ = client(meta)
    with ThreadPoolExecutor(len(SAM_PHRASES)) as pool:
        results = list(pool.map(lambda phrase: c.segment(photo, phrase), SAM_PHRASES))
    assert [result.phrase for result in results] == list(SAM_PHRASES)
    assert all(len(result.instances) == 2 for result in results)


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
        meta = FakeMeta(sam_stream(PART_DONE["part"]["text"]))
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
