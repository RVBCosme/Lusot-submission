# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "boto3[crt]>=1.43.120",
#     "httpx>=0.28.1",
#     "numpy>=2.5.4",
#     "opencv-python-headless>=4.14.0.94,<5",
# ]
# ///
"""The upload link's and the upload path's checks on the deployed stack (MS7 plan Task 3).

Spec §4.1, C809 and C822. `link` runs K1 to K4, with the letter K:
- K1, the control: a link used at once with a dark JPEG gives 204, and its report ends
  refused/too_dark with one log line whose meta_calls is 0.
- K2: every link the run is issued has a policy, decoded from base64, that expires at
  most 300 s after the answer's Date header (plus that header's 1 s), names exactly its
  own report's key raw/<id>.jpg, and allows only image/jpeg from 1 byte to 10 MB.
- K4: a link's form posted with its key changed to another report's: 403, and no object
  at either key.
- K3: a link held until 330 s after its Date header by the server's clock, then posted
  with a dark JPEG: 403, no raw object, the report still pending, and no log line.

`abuse` runs A1 to A4, W21's abuse test, with the letter A, each with its own device id:
- A1: 11 POST /uploads from one device in one clock hour, with no photo: ten 201s, then
  429 {"error": "device_limit"} with a Retry-After of at most 3,600 s (MS4's C522). With
  under 2 minutes of the server's hour left, it first waits for the next hour.
- A2: a capturedAt 16 minutes old by the server's clock: 422 capture_too_old (W20).
- A3: random bytes posted as image/jpeg: failed/bad_file, with no Meta call (C83).
- A4: a PNG form post: 403 from S3.

None makes a Meta call. Every upload sits at OUTSIDE_POINT, outside Metro Manila, and
each run first confirms that a new report there reads private, before any file goes
(C803). Every capturedAt comes from the server's clock, measured once per run.

It prints one line per check and counts only, through harden.say: reports by ordinal
(K#1, A#1), never a report id, a form field or a URL. The ids go into the run's private
record in LUSOT_DATA_DIR\\ms7\\<date>\\. Without --yes it prints what it would send and
stops, with no network call.

Usage: uv run backend/scripts/upload_checks.py <link|abuse> [--yes]
Exit codes: 0 every check passed, or nothing was sent; 1 a check failed; 2 refused by
a guard (a sealed data folder).
"""

from __future__ import annotations

import argparse
import base64
import json
import random
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from harden import (
    OUTSIDE_POINT,
    RunRecord,
    confirm_private,
    data_dir,
    ipv4_client,
    new_device_id,
    say,
    server_now,
    server_offset,
    upload_body,
)
from ops_common import PHT, REPORT_ID, guarded, lusot_session
from smoke_upload import (
    DEVICE_HEADER,
    CheckFailed,
    Stack,
    dark_jpeg,
    got,
    json_object,
    load_stack,
    log_lines,
    meta_calls,
    object_exists,
    outcome_of,
    post_form,
    s3_error,
    synthetic_photo,
    wait_final,
)

LINK_S = 300  # C27: the upload link lasts 5 minutes
DATE_SLACK_S = 1  # the Date header's resolution
HOLD_S = 330  # K3 posts this long after its link's Date header (C809)
MAX_BYTES = 10 * 1024 * 1024  # C27, plan §12
DEVICE_LIMIT = 10  # uploads per device per UTC clock hour (C508)
LIMITS_PER_CLOCK_HOUR = True  # limits.ts counts per UTC clock hour (Task 3's names)
HOUR_S = 3600
HOUR_ROOM_S = 120  # A1 waits for the next hour with less than this left
HOUR_MARGIN_S = 5  # and starts this long after it
STALE_S = 16 * 60  # A2: a minute past W20's 15
JPEG_MAGIC = b"\xff\xd8\xff"
LETTERS = {"link": "K", "abuse": "A"}
PLANS = {
    "link": (
        "link: 5 POST /uploads at OUTSIDE_POINT from one device, 3 dark JPEG form posts"
        " (K1 at once, K4 with another report's key, K3 after a 330 s hold), no Meta call;"
        " about 7 minutes"
    ),
    "abuse": (
        "abuse: 14 POST /uploads at OUTSIDE_POINT from 5 devices (the precondition, A1's"
        " 11, A2's stale one, A3 and A4), random bytes posted as a JPEG and one PNG form"
        " post, no Meta call; about 3 minutes"
    ),
}
_WHOLE_SECONDS = re.compile(r"[0-9]+")


@dataclass(frozen=True)
class Link:
    """One issued upload link: its report's ordinal and id, its form, and the server's
    time it was issued at, from the answer's Date header."""

    name: str
    report_id: str
    form: dict
    issued_s: float


def decode_policy(fields: dict[str, str]) -> dict:
    """The POST policy: the base64 JSON in the form's Policy field."""
    try:
        policy = json.loads(base64.b64decode(fields["Policy"], validate=True))
    except (KeyError, TypeError, ValueError):
        raise CheckFailed("the form has no readable Policy") from None
    if not isinstance(policy, dict):
        raise CheckFailed("the form's Policy isn't a JSON object")
    return policy


def policy_problems(policy: dict, *, issued_s: float, report_id: str) -> list[str]:
    """What is wrong with a link's policy (K2), or [] when it expires at most 301 s
    after `issued_s`, names only this report's key, exactly, and allows only image/jpeg
    from 1 byte to 10 MB. No problem names the key."""
    problems = []
    try:
        expires_s = datetime.fromisoformat(policy["expiration"]).timestamp()
    except (KeyError, TypeError, ValueError):
        problems.append("it has no readable expiration")
    else:
        if expires_s > issued_s + LINK_S + DATE_SLACK_S:
            problems.append(
                f"it expires {expires_s - issued_s:.0f} s after it was issued"
            )
    keys, types, ranges = [], [], []
    for condition in policy.get("conditions") or []:
        if isinstance(condition, dict):  # {"name": value}: an exact match
            for name, value in condition.items():
                field = name.lower()
                if field == "key":
                    keys.append(("eq", value))
                elif field == "content-type":
                    types.append(("eq", value))
        elif isinstance(condition, list) and condition:
            operator = str(condition[0]).lower()
            if operator == "content-length-range":
                ranges.append(condition[1:])
            elif len(condition) == 3 and isinstance(condition[1], str):
                field = condition[1].lower().lstrip("$")
                if field == "key":
                    keys.append((operator, condition[2]))
                elif field == "content-type":
                    types.append((operator, condition[2]))
    if keys != [("eq", f"raw/{report_id}.jpg")]:
        problems.append("its key condition isn't exactly this report's raw key")
    if ranges != [[1, MAX_BYTES]]:
        problems.append("its size range isn't 1 byte to 10 MB")
    if not types or any(t != ("eq", "image/jpeg") for t in types):
        problems.append("its Content-Type isn't exactly image/jpeg")
    return problems


def server_epoch(response: httpx.Response) -> float:
    """The server's time, from the answer's Date header."""
    try:
        when = parsedate_to_datetime(response.headers["date"])
    except (KeyError, TypeError, ValueError):
        raise CheckFailed(
            f"HTTP {response.status_code} without a readable Date header"
        ) from None
    return when.timestamp()


def hold_until(
    server_deadline_s: float,
    *,
    offset_s: float,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Return once the server's time, the laptop's plus `offset_s`, reaches the deadline."""
    while (now := clock() + offset_s) < server_deadline_s:
        sleep(server_deadline_s - now)


def not_a_jpeg(n: int = 4096, seed: int = 7) -> bytes:
    """`n` random bytes that never start with a JPEG's FF D8 FF."""
    data = bytearray(random.Random(seed).randbytes(n))
    if data[:3] == JPEG_MAGIC:
        data[0] = 0
    return bytes(data)


def upload_request(
    http: httpx.Client, api_url: str, *, device_id: str, captured_at: datetime
) -> httpx.Response:
    """POST /uploads at OUTSIDE_POINT, with the app's body and this device's id."""
    body = upload_body(OUTSIDE_POINT, captured_at=captured_at)
    return http.post(
        f"{api_url}/uploads", json=body, headers={DEVICE_HEADER: device_id}
    )


def made_report(response: httpx.Response) -> str | None:
    """The report id a 201 carries, or None."""
    rid = json_object(response, "POST /uploads").get("reportId")
    return rid if isinstance(rid, str) and REPORT_ID.fullmatch(rid) else None


def issue(
    http: httpx.Client,
    api_url: str,
    record: RunRecord,
    *,
    device_id: str,
    offset_s: float,
    wall: Callable[[], float] = time.time,
) -> Link:
    """A new upload link, its report named in the run's record."""
    captured = server_now(offset_s, clock=wall)
    response = upload_request(http, api_url, device_id=device_id, captured_at=captured)
    if response.status_code != 201:
        raise CheckFailed(f"POST /uploads: {got(response)}, expected 201")
    rid = made_report(response)
    form = json_object(response, "POST /uploads").get("upload")
    if rid is None or not (
        isinstance(form, dict)
        and isinstance(form.get("url"), str)
        and isinstance(form.get("fields"), dict)
    ):
        raise CheckFailed("POST /uploads: HTTP 201 without a report id and a form")
    return Link(record.name(rid), rid, form, server_epoch(response))


def result(check: str, ok: bool, detail: str) -> str:
    return f"{check} {'pass' if ok else 'FAIL'}: {detail}"


def checked(check: str, run: Callable[[], str]) -> str:
    """One check's line; a CheckFailed inside it fails that check alone."""
    try:
        return run()
    except CheckFailed as exc:
        return result(check, False, str(exc))


def final_outcome(
    http: httpx.Client, stack: Stack, link: Link, *, clock, sleep
) -> tuple[str, list[dict]]:
    """The report's outcome once final (B1's 120 s), and its log lines."""
    body = wait_final(
        http, stack.api_url, link.report_id, since=clock(), clock=clock, sleep=sleep
    )
    try:
        outcome = outcome_of(body)
    except KeyError:
        raise CheckFailed(
            f"{link.name}: the final report has no outcome fields"
        ) from None
    return outcome, log_lines(
        stack, link.report_id, until=outcome, clock=clock, sleep=sleep
    )


def k1_control(http: httpx.Client, stack: Stack, link: Link, *, clock, sleep) -> str:
    posted = post_form(http, link.form, dark_jpeg())
    if posted.status_code != 204:
        return result(
            "K1",
            False,
            f"{link.name}: S3 answered HTTP {posted.status_code} {s3_error(posted)}, expected 204",
        )
    outcome, lines = final_outcome(http, stack, link, clock=clock, sleep=sleep)
    ended = [line for line in lines if line.get("outcome") == outcome]
    ok = (
        outcome == "refused/too_dark"
        and len(ended) == 1
        and ended[0].get("meta_calls") == 0
        and meta_calls(lines) == 0
    )
    calls = ended[0].get("meta_calls") if len(ended) == 1 else f"in {len(ended)} lines"
    return result("K1", ok, f"{link.name}: 204, {outcome}, meta_calls {calls}")


def k2_policies(links: Sequence[Link]) -> str:
    found = [
        f"{link.name}: {problem}"
        for link in links
        for problem in policy_problems(
            decode_policy(link.form["fields"]),
            issued_s=link.issued_s,
            report_id=link.report_id,
        )
    ]
    if found:
        return result("K2", False, "; ".join(found))
    return result(
        "K2",
        True,
        f"{len(links)} links: each expires within 300 s, names only its own raw key,"
        " and allows image/jpeg from 1 byte to 10 MB",
    )


def k3_expired(
    http: httpx.Client, stack: Stack, link: Link, *, offset_s: float, wall, clock, sleep
) -> str:
    hold_until(link.issued_s + HOLD_S, offset_s=offset_s, clock=wall, sleep=sleep)
    posted = post_form(http, link.form, dark_jpeg())
    if posted.status_code != 403:
        return result(
            "K3",
            False,
            f"{link.name}: S3 answered HTTP {posted.status_code} after {HOLD_S} s, expected 403",
        )
    stored = object_exists(
        stack.session.client("s3"), stack.bucket, f"raw/{link.report_id}.jpg"
    )
    read = http.get(f"{stack.api_url}/reports/{link.report_id}")
    status = (
        json_object(read, "GET /reports").get("status")
        if read.status_code == 200
        else got(read)
    )
    lines = log_lines(
        stack, link.report_id, clock=clock, sleep=sleep
    )  # waits 30 s for any
    ok = not stored and status == "pending" and not lines
    return result(
        "K3",
        ok,
        f"{link.name}: 403 {s3_error(posted)} after {HOLD_S} s; raw object"
        f" {'present' if stored else 'absent'}; report {status}; {len(lines)} log lines",
    )


def k4_other_key(http: httpx.Client, stack: Stack, link: Link, other: Link) -> str:
    fields = {**link.form["fields"], "key": other.form["fields"]["key"]}
    posted = http.post(
        link.form["url"],
        data=fields,
        files={"file": ("k4.jpg", dark_jpeg(), "image/jpeg")},
    )
    if posted.status_code != 403:
        return result(
            "K4",
            False,
            f"{link.name}'s form with {other.name}'s key: HTTP {posted.status_code}, expected 403",
        )
    s3 = stack.session.client("s3")
    stored = [
        n.name
        for n in (link, other)
        if object_exists(s3, stack.bucket, f"raw/{n.report_id}.jpg")
    ]
    return result(
        "K4",
        not stored,
        f"{link.name}'s form with {other.name}'s key: 403 {s3_error(posted)};"
        f" objects at {', '.join(stored) if stored else 'neither key'}",
    )


def a1_device_limit(
    http: httpx.Client, stack: Stack, record: RunRecord, *, offset_s: float, wall, sleep
) -> str:
    server_s = wall() + offset_s
    if LIMITS_PER_CLOCK_HOUR and HOUR_S - server_s % HOUR_S < HOUR_ROOM_S:
        next_hour = server_s - server_s % HOUR_S + HOUR_S
        hold_until(
            next_hour + HOUR_MARGIN_S, offset_s=offset_s, clock=wall, sleep=sleep
        )
    device = record.device(new_device_id())
    for n in range(1, DEVICE_LIMIT + 2):
        captured = server_now(offset_s, clock=wall)
        response = upload_request(
            http, stack.api_url, device_id=device, captured_at=captured
        )
        if response.status_code == 201 and (rid := made_report(response)):
            record.name(rid)
        if n <= DEVICE_LIMIT and response.status_code != 201:
            return result(
                "A1",
                False,
                f"upload {n} of {DEVICE_LIMIT}: {got(response)}, expected 201",
            )
    error = (
        json_object(response, "POST /uploads").get("error")
        if response.status_code == 429
        else None
    )
    retry = (response.headers.get("retry-after") or "").strip()
    retry_ok = _WHOLE_SECONDS.fullmatch(retry) is not None and 1 <= int(retry) <= HOUR_S
    ok = response.status_code == 429 and error == "device_limit" and retry_ok
    return result(
        "A1",
        ok,
        f"10 x 201, then the 11th: {got(response)}, Retry-After {retry or 'missing'};"
        " no file sent",
    )


def a2_old_capture(
    http: httpx.Client, stack: Stack, record: RunRecord, *, offset_s: float, wall
) -> str:
    device = record.device(new_device_id())
    captured = server_now(offset_s, clock=wall) - timedelta(seconds=STALE_S)
    response = upload_request(
        http, stack.api_url, device_id=device, captured_at=captured
    )
    if response.status_code == 201 and (rid := made_report(response)):
        record.name(rid)
    error = (
        json_object(response, "POST /uploads").get("error")
        if response.status_code == 422
        else None
    )
    ok = response.status_code == 422 and error == "capture_too_old"
    return result(
        "A2", ok, f"capturedAt 16 minutes old by the server's clock: {got(response)}"
    )


def a3_random_bytes(
    http: httpx.Client,
    stack: Stack,
    record: RunRecord,
    *,
    offset_s: float,
    wall,
    clock,
    sleep,
) -> str:
    link = issue(
        http,
        stack.api_url,
        record,
        device_id=record.device(new_device_id()),
        offset_s=offset_s,
        wall=wall,
    )
    posted = post_form(http, link.form, not_a_jpeg())
    if posted.status_code != 204:
        return result(
            "A3",
            False,
            f"{link.name}: S3 answered HTTP {posted.status_code} {s3_error(posted)}, expected 204",
        )
    outcome, lines = final_outcome(http, stack, link, clock=clock, sleep=sleep)
    ended = [line for line in lines if line.get("outcome") == outcome]
    # C83's check ends it before the pipeline, which alone logs meta_calls (Task 3's names).
    ok = (
        outcome == "failed/bad_file"
        and len(ended) == 1
        and ended[0].get("meta_calls", 0) == 0
        and meta_calls(lines) == 0
    )
    return result(
        "A3", ok, f"{link.name}: 204, {outcome}, {meta_calls(lines)} Meta calls"
    )


def a4_png(
    http: httpx.Client, stack: Stack, record: RunRecord, *, offset_s: float, wall
) -> str:
    link = issue(
        http,
        stack.api_url,
        record,
        device_id=record.device(new_device_id()),
        offset_s=offset_s,
        wall=wall,
    )
    posted = http.post(
        link.form["url"],
        data={**link.form["fields"], "Content-Type": "image/png"},
        files={"file": ("a4.png", synthetic_photo(".png"), "image/png")},
    )
    if posted.status_code != 403:
        return result(
            "A4",
            False,
            f"{link.name}: the PNG form post got HTTP {posted.status_code}, expected 403",
        )
    stored = object_exists(
        stack.session.client("s3"), stack.bucket, f"raw/{link.report_id}.jpg"
    )
    return result(
        "A4",
        not stored,
        f"{link.name}: 403 {s3_error(posted)}; raw object {'present' if stored else 'absent'}",
    )


def run_link(
    http: httpx.Client,
    stack: Stack,
    record: RunRecord,
    *,
    offset_s: float,
    wall,
    clock,
    sleep,
) -> list[str]:
    """K1 to K4, in the order K1, K4, K3, with one device for the run's five uploads."""
    device = record.device(new_device_id())
    confirm_private(
        http,
        stack.api_url,
        device_id=device,
        offset_s=offset_s,
        clock=clock,
        sleep=sleep,
        wall=wall,
    )

    def link() -> Link:
        return issue(
            http, stack.api_url, record, device_id=device, offset_s=offset_s, wall=wall
        )

    first = link()
    k1 = checked("K1", lambda: k1_control(http, stack, first, clock=clock, sleep=sleep))
    third, fourth = link(), link()
    k4 = checked("K4", lambda: k4_other_key(http, stack, third, fourth))
    second = link()
    k3 = checked(
        "K3",
        lambda: k3_expired(
            http, stack, second, offset_s=offset_s, wall=wall, clock=clock, sleep=sleep
        ),
    )
    k2 = checked("K2", lambda: k2_policies([first, second, third, fourth]))
    return [k1, k2, k3, k4]


def run_abuse(
    http: httpx.Client,
    stack: Stack,
    record: RunRecord,
    *,
    offset_s: float,
    wall,
    clock,
    sleep,
) -> list[str]:
    """A1 to A4, each with its own device id, after the precondition with its own."""
    confirm_private(
        http,
        stack.api_url,
        device_id=record.device(new_device_id()),
        offset_s=offset_s,
        clock=clock,
        sleep=sleep,
        wall=wall,
    )
    timing = {"offset_s": offset_s, "wall": wall}
    return [
        checked(
            "A1", lambda: a1_device_limit(http, stack, record, sleep=sleep, **timing)
        ),
        checked("A2", lambda: a2_old_capture(http, stack, record, **timing)),
        checked(
            "A3",
            lambda: a3_random_bytes(
                http, stack, record, clock=clock, sleep=sleep, **timing
            ),
        ),
        checked("A4", lambda: a4_png(http, stack, record, **timing)),
    ]


def main(
    argv: Sequence[str] | None = None,
    *,
    session=None,
    http: httpx.Client | None = None,
    wall: Callable[[], float] = time.time,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run", choices=tuple(LETTERS))
    parser.add_argument(
        "--yes", action="store_true", help="upload; without it, nothing is sent"
    )

    def command() -> int:
        args = parser.parse_args(argv)
        if not args.yes:
            say(PLANS[args.run])
            say("nothing sent: add --yes to run it")
            return 0
        today = datetime.fromtimestamp(wall(), PHT)
        record = RunRecord(
            data_dir() / "ms7" / f"{today:%Y-%m-%d}",
            "upload_checks",
            LETTERS[args.run],
            clock=lambda: datetime.fromtimestamp(wall(), PHT),
        )
        client = http if http is not None else ipv4_client()
        try:
            stack = load_stack(session if session is not None else lusot_session())
            offset = server_offset(client, stack.api_url, clock=wall)
            run = run_link if args.run == "link" else run_abuse
            lines = run(
                client,
                stack,
                record,
                offset_s=offset,
                wall=wall,
                clock=clock,
                sleep=sleep,
            )
        except CheckFailed as exc:
            say(f"UPLOAD CHECKS FAILED: {exc}")
            return 1
        finally:
            say(f"run record: {record.save().name}")
            if http is None:
                client.close()
        for line in lines:
            say(line)
        failed = sum(" FAIL: " in line for line in lines)
        say(
            f"UPLOAD CHECKS FAILED: {failed} of {len(lines)}"
            if failed
            else "UPLOAD CHECKS OK"
        )
        return 1 if failed else 0

    return guarded(
        command,
        label="UPLOAD CHECKS FAILED",
        errors=(BotoCoreError, ClientError, httpx.HTTPError),
    )


if __name__ == "__main__":
    raise SystemExit(main())
