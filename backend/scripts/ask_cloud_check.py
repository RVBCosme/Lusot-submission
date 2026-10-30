# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "boto3[crt]>=1.43.120",
#     "httpx>=0.28.1",
# ]
# ///
"""Cloud check of the deployed POST /ask, typed questions only (Ask Lusot plan Task 19).

It posts five typed questions to the stack's API, one at a time, in this order:
1. a listed spot, by its name in backend/api/src/data/spots.json
2. a small landmark, which the API's Nominatim step looks up
3. "dito" with a public point in Manila (Manila City Hall), never anyone's location
4. a vehicle question at a named road
5. a place outside Metro Manila

Each question goes with its own random device id (a new uuid4, the X-Lusot-Device
header), so the per-device question limit never reaches a later question. The API's URL
is the stack's ApiUrl output, as smoke_upload.py reads it. The run uses the lusot
profile, never AWS_PROFILE, and HTTP goes over IPv4 only, since IPv6 doesn't connect on
the home Wi-Fi (Oct 28 log).

For each question it prints the HTTP status, the answer's source and kind, and the
seconds from the post to the reply at the client. It never prints an answer's text, a
report id, a question, a device id, a coordinate, the API's URL or an account number:
source, kind and an error code print only when they are lowercase words, and every
printed line passes through the scripts' shared output mask (guards.py), which replaces
each run of 12 digits with <account>. A failure shows its class name, or an AWS error's
code and HTTP status, never its message. The script takes no path.

It judges three things: every question got HTTP 200 with a readable kind, each within
10 s at the client, and the listed spot's answer came from the model (source "model").
A listed spot needs no Nominatim, so that answer is the run's one proof that the
deployed function reads the key and calls Meta; a plain list there fails the run. The
kinds themselves (Bacoor outside_metro_manila, the others reports or no_reports as the
live pins allow, a landmark's place_too_broad) and the other questions' sources are for
whoever reads the output.

Usage: uv run backend/scripts/ask_cloud_check.py
Exit codes: 0 every question was answered within 10 s and the listed spot by the model,
1 a question wasn't, the listed spot's answer wasn't the model's, or the stack's API URL
couldn't be read.
"""

from __future__ import annotations

import argparse
import re
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import guards
import httpx
from ops_common import failure, lusot_session, stack_outputs

DEVICE_HEADER = "X-Lusot-Device"  # the app's random device id (C508)
WITHIN_S = 10  # Step 5: each reply within this at the client
TIMEOUT_S = 30  # longer than WITHIN_S, so a slow reply is measured, not cut off
# Manila City Hall: a public place in Manila, inside Metro Manila, and no one's location.
MANILA_POINT = {"lat": 14.5896, "lng": 120.9815, "accuracyM": 10}
# A source, kind or error code: anything else is not printed.
_WORD = re.compile(r"[a-z_]{1,40}")


class CheckFailed(Exception):
    """The run couldn't start: its message is written to be printed."""


@dataclass(frozen=True)
class Ask:
    """One typed question. `label` names it in the output, so the output never needs its
    text; `here` is the point the app would send with it, if any."""

    label: str
    text: str
    here: Mapping[str, float] | None = None


# The question whose answer must come from the model: see the module's docstring.
LISTED_SPOT = "listed spot"

QUESTIONS = (
    Ask(LISTED_SPOT, "Baha ba sa EDSA cor. Aurora Blvd?"),
    Ask("landmark", "Baha ba malapit sa Quiapo Church?"),
    Ask("dito", "May baha ba dito?", MANILA_POINT),
    Ask("sedan", "Lusot ba sedan ko sa Taft Avenue in front of PGH?"),
    Ask("outside Metro Manila", "Baha ba sa Bacoor?"),
)


def say(line: str) -> None:
    """Print `line` through the scripts' one output mask (guards.say)."""
    guards.say(line)


def main(
    argv: Sequence[str] | None = None,
    *,
    api_url: str | None = None,
    transport: httpx.BaseTransport | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Run the check. `api_url`, `transport` and `clock` are for the tests: by default
    the URL is the stack's ApiUrl output, the transport is IPv4 only and the clock is
    time.monotonic."""
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args(argv)
    began = clock()
    try:
        url = stack_api_url() if api_url is None else api_url
        results = run(url, QUESTIONS, transport=transport, clock=clock)
    except CheckFailed as exc:
        say(f"ASK CHECK FAILED: {exc}")
        return 1
    late = sum(not answered_in_time(result) for result in results)
    if late:
        say(
            f"ASK CHECK FAILED: {late} of {len(results)} questions were not HTTP 200"
            f" within {WITHIN_S} s"
        )
        return 1
    if not model_answered(results):
        say("ASK CHECK FAILED: the listed spot's answer was not the model's")
        return 1
    say(
        f"ASK CHECK OK in {clock() - began:.1f} s: {len(results)} questions, each"
        f" HTTP 200 within {WITHIN_S} s, the listed spot's from the model"
    )
    return 0


def stack_api_url() -> str:
    """The lusot stack's ApiUrl output, without a trailing slash (paths are joined as
    f"{api_url}/ask"). A failure is CheckFailed, naming only an error's class or code."""
    try:
        outputs = stack_outputs(lusot_session())
    except Exception as exc:  # noqa: BLE001
        # An AWS error, the profile or the login, shown by its code or class only.
        # botocore's classes aren't imported: the tests run without boto3.
        raise CheckFailed(f"the stack's outputs: {failure(exc)}") from None
    if "ApiUrl" not in outputs:
        raise CheckFailed("the stack has no ApiUrl output")
    return outputs["ApiUrl"].rstrip("/")


def run(
    api_url: str,
    questions: Sequence[Ask],
    *,
    transport: httpx.BaseTransport | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> list[dict]:
    """Post each question to POST /ask with its own device id, and print and return its
    label, status, source, kind, error and seconds, timed at the client.

    `source` and `kind` come from a 200's answer, `error` from another reply's error
    code or a lost connection's class name, and each is None when it is missing or not a
    lowercase word. One client carries all the questions: each new connection waits
    about 21 s per IPv6 address on the home Wi-Fi, so IPv4 only, and only one.
    """
    if transport is None:
        transport = httpx.HTTPTransport(local_address="0.0.0.0")
    results = []
    with httpx.Client(timeout=TIMEOUT_S, transport=transport) as http:
        for n, ask in enumerate(questions, 1):
            result = post_question(http, api_url, ask, clock)
            results.append(result)
            say(describe(n, len(questions), result))
    return results


def post_question(
    http: httpx.Client, api_url: str, ask: Ask, clock: Callable[[], float]
) -> dict:
    body: dict = {"question": ask.text}
    if ask.here is not None:
        body["here"] = dict(ask.here)
    headers = {DEVICE_HEADER: str(uuid.uuid4())}
    result = {
        "label": ask.label,
        "status": None,
        "source": None,
        "kind": None,
        "error": None,
    }
    began = clock()
    try:
        response = http.post(f"{api_url}/ask", json=body, headers=headers)
    except httpx.HTTPError as exc:
        # Never the message: it can hold an address.
        result |= {"error": type(exc).__name__, "seconds": clock() - began}
        return result
    result |= {"status": response.status_code, "seconds": clock() - began}
    reply = _object(response)
    answer = _object_of(reply.get("answer"))
    result |= {
        "source": _word(answer.get("source")),
        "kind": _word(answer.get("kind")),
        "error": _word(reply.get("error")),
    }
    return result


def answered_in_time(result: dict) -> bool:
    """HTTP 200 with a kind we can read, within WITHIN_S at the client."""
    return (
        result["status"] == 200
        and result["kind"] is not None
        and result["seconds"] <= WITHIN_S
    )


def model_answered(results: Sequence[dict]) -> bool:
    """The listed spot's answer came from the model (source "model")."""
    return any(r["label"] == LISTED_SPOT and r["source"] == "model" for r in results)


def describe(n: int, total: int, result: dict) -> str:
    """One question's line: its place in the run, its label, what came back, its seconds."""
    if result["status"] is None:
        what = f"no reply ({result['error']})"
    elif result["status"] == 200:
        source = result["source"] or "unreadable"
        kind = result["kind"] or "unreadable"
        what = f"HTTP 200, source {source}, kind {kind}"
    else:
        code = f" ({result['error']})" if result["error"] else ""
        what = f"HTTP {result['status']}{code}"
    seconds = result["seconds"]
    return f"question {n}/{total} ({result['label']}): {what}, {seconds:.1f} s"


def _object(response: httpx.Response) -> dict:
    """A reply's body as a JSON object, or an empty one."""
    try:
        return _object_of(response.json())
    except ValueError:
        return {}


def _object_of(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _word(value: object) -> str | None:
    """`value` when it is a short lowercase word (a source, a kind, an error code)."""
    if isinstance(value, str) and _WORD.fullmatch(value):
        return value
    return None


if __name__ == "__main__":
    raise SystemExit(main())
