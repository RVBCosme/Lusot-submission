"""Tests for ask_cloud_check.py: the typed questions Ask Lusot's Task 19 posts to the
deployed POST /ask, and what the run prints (plan Task 19, Steps 1 and 2).

Fakes only: httpx.MockTransport stands in for the API, and the stack's outputs are
monkeypatched. Nothing reaches AWS, Meta or the network.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with httpx pytest -q
        backend/scripts/test_ask_cloud_check.py
"""

import base64
import json
import re
import uuid
from pathlib import Path

import ask_cloud_check
import httpx
import pytest
from ask_cloud_check import QUESTIONS, main, run
from metro_manila import in_metro_manila

API = "https://api.test"
SPOTS = Path(__file__).resolve().parents[1] / "api" / "src" / "data" / "spots.json"

# Strings an answer holds and the run must never print.
PLACE = "Zzyzx Quarry Junction"
SUGGESTION = "Try the Zzyzx footbridge"
REPORT_ID = "r_" + "0123456789abcdef" * 2
# A made-up account number, built in two parts so the repo scan has no 12-digit run.
ACCOUNT = "123456" + "789012"


def an_answer(kind="reports", source="model"):
    """The body of a 200 from POST /ask, with text the run must not print."""
    return {
        "answer": {
            "source": source,
            "fallback": None,
            "kind": kind,
            "crossing": False,
            "vehicle": None,
            "place": {"name": PLACE, "source": "spots"},
            "windowMin": 180,
            "radiusM": 300,
            "count": 1,
            "reports": [{"id": REPORT_ID, "level": "knee"}],
            "demo": [],
            "deepestId": REPORT_ID,
            "cited": [REPORT_ID],
            "suggestions": [SUGGESTION],
        }
    }


class FakeClock:
    """A clock that moves only when the fake API answers, by that question's seconds."""

    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class Api:
    """The fake API: records every request, and answers each with `reply(request)`."""

    def __init__(self, reply=None, clock=None, seconds=()):
        self.requests = []
        self.reply = reply or (lambda request: httpx.Response(200, json=an_answer()))
        self.clock = clock
        self.seconds = list(seconds)  # what each answer takes, in order

    def __call__(self, request):
        self.requests.append(request)
        if self.clock is not None and self.seconds:
            self.clock.now += self.seconds.pop(0)
        return self.reply(request)

    @property
    def transport(self):
        return httpx.MockTransport(self)

    def bodies(self):
        return [json.loads(request.content) for request in self.requests]

    def devices(self):
        return [request.headers["x-lusot-device"] for request in self.requests]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """A test that reaches for the real transport fails instead of connecting."""

    def refuse(*args, **kwargs):
        raise AssertionError("the real transport was built")

    monkeypatch.setattr(ask_cloud_check.httpx, "HTTPTransport", refuse)


@pytest.fixture
def stack(monkeypatch):
    """The stack's outputs, as stack_outputs gives them. No session, no AWS call."""
    outputs = {"ApiUrl": f"{API}/"}
    monkeypatch.setattr(ask_cloud_check, "lusot_session", lambda: "session")
    monkeypatch.setattr(ask_cloud_check, "stack_outputs", lambda session: outputs)
    return outputs


def test_the_default_questions():
    assert [question.text for question in QUESTIONS] == [
        "Baha ba sa EDSA cor. Aurora Blvd?",
        "Baha ba malapit sa Quiapo Church?",
        "May baha ba dito?",
        "Lusot ba sedan ko sa Taft Avenue in front of PGH?",
        "Baha ba sa Bacoor?",
    ]
    names = {spot["name"] for spot in json.loads(SPOTS.read_text(encoding="utf-8"))}
    assert "EDSA cor. Aurora Blvd" in names  # the listed spot's name is in spots.json
    assert "EDSA cor. Aurora Blvd" in QUESTIONS[0].text


def test_only_dito_sends_a_point_and_it_is_a_public_one_in_manila():
    api = Api()
    run(API, QUESTIONS, transport=api.transport)
    assert [request.url for request in api.requests] == [httpx.URL(f"{API}/ask")] * 5
    assert {request.method for request in api.requests} == {"POST"}
    bodies = api.bodies()
    assert [body["question"] for body in bodies] == [q.text for q in QUESTIONS]
    assert [set(body) for body in bodies] == [
        {"question"},
        {"question"},
        {"question", "here"},
        {"question"},
        {"question"},
    ]
    here = bodies[2]["here"]
    assert in_metro_manila(here["lat"], here["lng"])
    assert here["accuracyM"] <= 100  # the route takes a fix of 100 m or better


def test_each_question_gets_its_own_device_id():
    api = Api()
    run(API, QUESTIONS, transport=api.transport)
    devices = api.devices()
    assert len(set(devices)) == len(QUESTIONS)
    for device in devices:
        assert str(uuid.UUID(device)) == device
        assert uuid.UUID(device).version == 4
    again = Api()
    run(API, QUESTIONS, transport=again.transport)
    assert not set(devices) & set(again.devices())  # nor does a second run reuse one


def test_the_output_holds_no_answer_text_and_no_report_id(capsys):
    api = Api()
    results = run(API, QUESTIONS, transport=api.transport)
    assert len(results) == 5
    out = capsys.readouterr().out
    assert out.count("HTTP 200") == 5
    secrets = [PLACE, SUGGESTION, REPORT_ID, "Zzyzx", "knee"]
    secrets += [question.text for question in QUESTIONS]
    secrets += ["Quiapo", "Bacoor", "Taft", "PGH", "Aurora", "14.58", "120.98"]
    secrets += api.devices()
    for secret in secrets:
        assert secret not in out
    assert re.search(r"[0-9]{12}", out) is None  # an account number's length


def test_a_reply_that_is_not_an_answer_prints_nothing_from_it(capsys):
    def odd(request):
        text = f"Zzyzx {REPORT_ID} {ACCOUNT}"
        return httpx.Response(200, json={"answer": {"source": text, "kind": text}})

    results = run(API, QUESTIONS[:1], transport=Api(odd).transport)
    assert (results[0]["source"], results[0]["kind"]) == (None, None)
    out = capsys.readouterr().out
    assert "source unreadable, kind unreadable" in out
    assert "Zzyzx" not in out and REPORT_ID not in out and ACCOUNT not in out


def test_run_records_status_source_kind_and_seconds(capsys):
    clock = FakeClock()
    kinds = [
        "reports",
        "no_reports",
        "place_too_broad",
        "reports",
        "outside_metro_manila",
    ]
    answers = iter(kinds)

    def reply(request):
        kind = next(answers)
        return httpx.Response(200, json=an_answer(kind, "plain_list"))

    api = Api(reply, clock, seconds=[1.5, 2.0, 3.25, 4.0, 0.5])
    results = run(API, QUESTIONS, transport=api.transport, clock=clock)
    assert results == [
        {
            "label": question.label,
            "status": 200,
            "source": "plain_list",
            "kind": kind,
            "error": None,
            "seconds": seconds,
        }
        for question, kind, seconds in zip(
            QUESTIONS, kinds, [1.5, 2.0, 3.25, 4.0, 0.5], strict=True
        )
    ]
    out = capsys.readouterr().out
    assert (
        "question 5/5 (outside Metro Manila): HTTP 200, source plain_list,"
        " kind outside_metro_manila, 0.5 s"
    ) in out


def test_a_refusal_records_its_error_code_only(capsys):
    def refused(request):
        body = {"error": "question_limit", "detail": f"Zzyzx {REPORT_ID}"}
        return httpx.Response(429, json=body)

    results = run(API, QUESTIONS[:1], transport=Api(refused).transport)
    assert results[0]["status"] == 429
    assert results[0]["error"] == "question_limit"
    assert results[0]["kind"] is None
    out = capsys.readouterr().out
    assert "HTTP 429 (question_limit)" in out
    assert "Zzyzx" not in out and REPORT_ID not in out


def test_a_lost_connection_records_its_class_name_only(capsys):
    def lost(request):
        raise httpx.ConnectError(f"refused by 203.0.113.9 for account {ACCOUNT}")

    results = run(API, QUESTIONS[:2], transport=Api(lost).transport)
    assert [result["status"] for result in results] == [None, None]
    assert [result["error"] for result in results] == ["ConnectError"] * 2
    out = capsys.readouterr().out
    assert "no reply (ConnectError)" in out
    assert "203.0.113.9" not in out and ACCOUNT not in out


def test_main_passes_when_every_question_is_answered_within_10_s(stack, capsys):
    clock = FakeClock()
    api = Api(clock=clock, seconds=[9.5, 0.5, 2.0, 10.0, 3.0])
    code = main([], transport=api.transport, clock=clock)
    out = capsys.readouterr().out
    assert code == 0
    assert out.splitlines()[-1] == (
        "ASK CHECK OK in 25.0 s: 5 questions, each HTTP 200 within 10 s,"
        " the listed spot's from the model"
    )


def test_main_fails_when_a_question_is_slow_or_not_answered(stack, capsys):
    clock = FakeClock()
    api = Api(clock=clock, seconds=[1.0, 10.25, 1.0, 1.0, 1.0])
    assert main([], transport=api.transport, clock=clock) == 1
    last = capsys.readouterr().out.splitlines()[-1]
    assert last == "ASK CHECK FAILED: 1 of 5 questions were not HTTP 200 within 10 s"

    def broken(request):
        return httpx.Response(500, json={"error": "internal"})

    assert main([], transport=Api(broken).transport) == 1
    last = capsys.readouterr().out.splitlines()[-1]
    assert last == "ASK CHECK FAILED: 5 of 5 questions were not HTTP 200 within 10 s"

    def no_answer(request):
        return httpx.Response(200, json={"answer": {}})

    assert main([], transport=Api(no_answer).transport) == 1


def in_order(*sources):
    """A fake API reply that gives the questions these sources, in order."""
    answers = iter(sources)
    return lambda request: httpx.Response(200, json=an_answer(source=next(answers)))


def test_main_fails_unless_the_listed_spot_is_answered_by_the_model(stack, capsys):
    # Task 19 M6: a listed spot needs no Nominatim, so only the model's answer there
    # proves the deployed function reads the key and calls Meta.
    rest = ["model"] * 4
    for first in ("plain_list", "Zzyzx"):
        api = Api(in_order(first, *rest))
        assert main([], transport=api.transport) == 1
        out = capsys.readouterr().out
        assert "ASK CHECK OK" not in out
        assert out.splitlines()[-1] == (
            "ASK CHECK FAILED: the listed spot's answer was not the model's"
        )
        # Each question's line names its source, as it names its kind.
        lines = [line for line in out.splitlines() if line.startswith("question ")]
        assert len(lines) == 5
        assert all(", source " in line and ", kind " in line for line in lines)
        shown = "unreadable" if first == "Zzyzx" else first
        assert lines[0].startswith(
            f"question 1/5 (listed spot): HTTP 200, source {shown}, kind reports,"
        )
        assert "Zzyzx" not in out

    # Only the listed spot must be the model's: the others may be the plain list.
    api = Api(in_order("model", *["plain_list"] * 4))
    assert main([], transport=api.transport) == 0
    assert capsys.readouterr().out.splitlines()[-1].startswith("ASK CHECK OK")


def test_the_api_url_comes_from_the_stack_output(stack):
    api = Api()
    assert main([], transport=api.transport) == 0
    # The output's trailing slash is dropped, so a path never holds two.
    assert {str(request.url) for request in api.requests} == {f"{API}/ask"}


def test_a_stack_without_the_api_url_fails_before_any_question(stack, capsys):
    stack.clear()
    api = Api()
    assert main([], transport=api.transport) == 1
    assert api.requests == []
    assert capsys.readouterr().out.splitlines() == [
        "ASK CHECK FAILED: the stack has no ApiUrl output"
    ]


def test_an_aws_failure_shows_its_class_name_only(monkeypatch, capsys):
    def broken(session):
        raise RuntimeError(f"arn:aws:iam::{ACCOUNT}:user/someone, expired")

    monkeypatch.setattr(ask_cloud_check, "lusot_session", lambda: "session")
    monkeypatch.setattr(ask_cloud_check, "stack_outputs", broken)
    api = Api()
    assert main([], transport=api.transport) == 1
    assert api.requests == []
    out = capsys.readouterr().out
    assert out == "ASK CHECK FAILED: the stack's outputs: RuntimeError\n"


def test_the_script_takes_no_path(capsys):
    # A clip comes only through --voice, so a bare path (sealed or not) is no argument.
    sealed = r"C:\Systems\Lusot\lusot-data\set_b\sealed\clip.wav"
    for argument in (sealed, "clip.wav"):
        with pytest.raises(SystemExit) as exit_:
            main([argument], transport=Api().transport)
        assert exit_.value.code == 2
    capsys.readouterr()


# --voice (plan Task 19, Step 5's synthetic WAV): the spoken questions alone, each to
# POST /ask/voice, printed without the transcript or the clip's path.
TRANSCRIPT = "Zzyzx transcript words"


def a_voice_answer(kind="no_reports", source="model"):
    return {**an_answer(kind, source), "transcript": TRANSCRIPT}


def clips(tmp_path, *names):
    paths = []
    for n, name in enumerate(names):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"RIFF" + bytes([n]) * 40)
        paths.append(path)
    return paths


def test_voice_posts_each_clip_alone_to_ask_voice(stack, tmp_path, capsys):
    one, two = clips(tmp_path, "zzyzx-one.wav", "zzyzx-two.wav")
    api = Api(lambda request: httpx.Response(200, json=a_voice_answer()))

    code = main(["--voice", str(one), "--voice", str(two)], transport=api.transport)

    assert code == 0
    assert [request.url.path for request in api.requests] == ["/ask/voice", "/ask/voice"]
    assert api.bodies() == [
        {"audio": base64.b64encode(one.read_bytes()).decode("ascii")},
        {"audio": base64.b64encode(two.read_bytes()).decode("ascii")},
    ]
    devices = api.devices()
    assert len(set(devices)) == 2
    out = capsys.readouterr().out
    assert "question 1/2 (voice 1): HTTP 200, source model, kind no_reports" in out
    assert out.splitlines()[-1].startswith(
        "ASK CHECK OK in 0.0 s: 2 spoken questions, each HTTP 200 within 10 s"
    )
    for secret in (TRANSCRIPT, PLACE, REPORT_ID, "zzyzx", str(tmp_path), *devices):
        assert secret not in out


def test_voice_fails_when_a_clip_is_not_answered_in_time(stack, tmp_path, capsys):
    (one,) = clips(tmp_path, "clip.wav")
    refused = Api(lambda request: httpx.Response(503, json={"error": "voice_failed"}))

    assert main(["--voice", str(one)], transport=refused.transport) == 1
    out = capsys.readouterr().out
    assert "question 1/1 (voice 1): HTTP 503 (voice_failed)" in out
    assert out.splitlines()[-1] == (
        "ASK CHECK FAILED: 1 of 1 questions were not HTTP 200 within 10 s"
    )


def test_voice_refuses_a_sealed_path_before_anything_is_read(stack, tmp_path, capsys):
    (inside,) = clips(tmp_path, "sealed/clip.wav")
    api = Api()

    with pytest.raises(SystemExit) as exit_:
        main(["--voice", str(inside)], transport=api.transport)

    assert exit_.value.code == 2
    assert api.requests == []
    out = capsys.readouterr().out
    assert "refused" in out and str(tmp_path) not in out


def test_voice_with_an_unreadable_clip_fails_without_naming_it(stack, tmp_path, capsys):
    missing = tmp_path / "zzyzx-missing.wav"
    api = Api()

    assert main(["--voice", str(missing)], transport=api.transport) == 1
    assert api.requests == []
    out = capsys.readouterr().out
    assert out.splitlines()[-1] == "ASK CHECK FAILED: a --voice clip can't be read (FileNotFoundError)"
    assert "zzyzx" not in out and str(tmp_path) not in out
