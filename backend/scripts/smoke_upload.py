# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "boto3[crt]>=1.43.120",
#     "httpx>=0.28.1",
#     "numpy>=2.5.4",
#     "opencv-python-headless>=4.14.0.94,<5",
# ]
# ///
"""Cloud smoke test of the deployed `lusot` stack (MS3a spec B1, B4, B5; plan Task 15).

In order, it checks that:
1. the API's CORS preflight for POST /uploads allows the app's origins
2. B1's photos go through end to end: the first 5 of C87's order that have a credit
   line (R102), then one synthetic dark JPEG, each through POST /uploads and its
   presigned form, as the app sends it. Each report is final (done, refused or
   failed) within 120 s of its photo's 204 (C68). The dark photo goes from the
   Capacitor origin, and both its calls answer with that allow-origin header.
3. a reused upload link pays nothing (B5). As soon as a photo's report is final and
   its log shows Meta calls, before the next upload, its form is posted again with
   the same bytes, at most 280 s after POST /uploads returned it: the form lasts
   300 s (C27), and the whole run takes longer. S3 answers 204, the raw photo is gone
   within 60 s, and the log has an already_finished line and still exactly one line
   with Meta calls.
4. the dark photo ends refused/too_dark, and its log shows no Meta call
5. every report body has C67's shape. If no photo gave a level, it prints their
   outcomes and drop causes (C75) and carries on, and the run ends with exit 3 (C71).
6. no raw photo is left for any report, and blurred/{id}.jpg exists for each level
   report and for no other (B4). It then prints the spend: the Meta calls in the log
   lines, how many ended on a 504 or a 413 from SAM or judge, and the estimated cost,
   from SAM's calls and Muse Spark's billed usage, never from a token count.
7. a report whose photo never came ends failed/photo_missing within 60 s (spec §3.6):
   the queue gets one S3-shaped notification for it, and the run prints the log
   line's S3 error code and HTTP status (R93)
8. MS1's checks:
   - S3 itself refuses a form whose Content-Type is image/png (403, Review Focus 1)
   - the analysis log shows the Meta key loaded at a cold start since the analysis
     function or the key last changed (C28)
   - the uploads stop switch: once on, POST /uploads gives 503 after the API's 30 s
     cache. The switch goes back to off whatever happens. Setting it with
     put-parameter is drift from the template, which resets it to "off" only when
     that parameter's resource changes.

With --fallback (C71), it sends the credited photos at positions 5 to 19 of C87's
order instead, one at a time up to the first level, runs checks 2, 5 and 6 on them,
and prints how many it sent.

The photos stay in C87's folder, LUSOT_DATA_DIR\\set_c\\commons-ph-floods, outside
every repo. A path inside a folder named sealed is refused before anything is read.

It prints results, counts and timings only. It never prints a photo's name, a path,
a report id, the API's, a form's or the queue's URL, the account ID, an ARN or an
image URI. An AWS error shows its code and HTTP status, any other error only its
class name, and every printed line passes through a mask that replaces any run of 12
digits with <account>. Log lines are read, never printed.

It always uses the lusot profile, never AWS_PROFILE. boto3 comes with its CRT extra:
that profile signs in with `aws login`, and botocore's provider for those credentials
needs the CRT. HTTP goes over IPv4 only, since IPv6 doesn't connect on the home Wi-Fi
(Oct 28 log).

Usage: uv run backend/scripts/smoke_upload.py [--fallback]
Exit codes: 0 every check passed, 1 a check failed, 3 every other check passed but no
photo gave a level, so C71 applies.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import time
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

import boto3
import cv2
import httpx
import numpy as np
from botocore.exceptions import BotoCoreError, ClientError

STACK = "lusot"
REGION = "ap-southeast-1"
SPOT = {"lat": 14.6095, "lng": 120.9894}  # the plan §12 example
APP_ORIGIN = "https://localhost"  # the Capacitor app
ORIGINS = (APP_ORIGIN, "http://localhost:4173")  # and the Vite preview server
STOP_UPLOADS = "/lusot/stop/uploads"
KEY_PARAM = "/lusot/meta/model-api-key"
DATA_DIR = r"C:\Systems\Lusot\lusot-data"  # when LUSOT_DATA_DIR is unset
PHOTO_LIST = "metro_manila_41.txt"  # C87's eligible photos: full path<TAB>licence
CREDITS = "attribution.csv"  # each photo's credit line (R102)
SEED = 20261028  # C87's draw, fixed in advance as R7's was
B1_POSITIONS = slice(0, 5)  # of C87's order
FALLBACK_POSITIONS = slice(5, 20)  # C71
APP_MAX_SIDE = 1600  # as app/src/lib/capture.ts sends a photo
APP_JPEG_QUALITY = 85
FINAL_STATUSES = ("done", "refused", "failed")
SWITCH_WAIT_S = 35  # the API caches the switch for 30 s
POLL_EVERY_S = 2
POLL_FOR_S = 120  # B1's bound from a photo's 204 to a final status (C68)
MISSING_PHOTO_S = 60  # spec §3.6's bound, from the notification
RAW_GONE_S = 60  # B5: the reused link's raw photo is deleted within this
FORM_FRESH_S = 280  # C27's 300 s upload form, less a margin
LOG_WAIT_S = 30  # log events can take a few seconds to become searchable
LOG_POLL_S = 5
LOG_SKEW_S = 300  # log searches start this long before the run, for clock skew
# Prices from docs/research/2026-10-26-verification-notes.md (dev.meta.ai, Oct 26).
SAM_USD_PER_IMAGE = 2.50 / 1000
SPARK_USD_PER_INPUT_TOKEN = 1.25 / 1e6
SPARK_USD_PER_OUTPUT_TOKEN = 4.25 / 1e6
_ACCOUNT_ID = re.compile(r"[0-9]{12}")


class CheckFailed(Exception):
    """A check didn't get what it expected."""


@dataclass(frozen=True)
class Stack:
    """The deployed stack, as the checks use it."""

    session: boto3.Session
    api_url: str
    bucket: str
    queue: str  # the upload queue's name: its URL holds the account ID (R20)
    since_ms: int  # where log searches start: the run's start, less LOG_SKEW_S


@dataclass
class Sent:
    """One photo sent as the app sends it, and what its report became."""

    label: str  # how the output names it: never by its file name
    report_id: str
    form: dict  # the presigned form, kept for the reused link (B5)
    data: bytes
    issued: float  # time.monotonic() once POST /uploads returned the form
    uploaded: float  # time.monotonic() once S3 answered 204
    body: dict = field(default_factory=dict)  # GET /reports/{id}, once final
    lines: list[dict] = field(default_factory=list)  # its analysis log lines


def say(line: str) -> None:
    print(_ACCOUNT_ID.sub("<account>", line), flush=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="C71: send positions 5 to 19 of C87's order, up to the first level",
    )
    args = parser.parse_args(argv)
    started = time.monotonic()
    try:
        folder = photo_folder()
        positions = FALLBACK_POSITIONS if args.fallback else B1_POSITIONS
        photos, skipped = credited(folder, seeded_photo_order(folder)[positions])
        say(
            f"photos: {len(photos)} of positions {positions.start} to"
            f" {positions.stop - 1} in C87's order, {skipped} skipped without a"
            " credit line"
        )
        if not photos:
            raise CheckFailed("no credited photo to send")
        session = boto3.Session(profile_name="lusot", region_name=REGION)
        cloudformation = session.client("cloudformation")
        [stack] = cloudformation.describe_stacks(StackName=STACK)["Stacks"]
        outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
        deployed = Stack(
            session=session,
            # Paths are joined as f"{api_url}/uploads", so no trailing slash may remain.
            api_url=outputs["ApiUrl"].rstrip("/"),
            bucket=outputs["BucketName"],
            queue=outputs["QueueName"],
            since_ms=int((time.time() - LOG_SKEW_S) * 1000),
        )
        # IPv4 only: IPv6 doesn't connect on the home Wi-Fi (Oct 28 log).
        transport = httpx.HTTPTransport(local_address="0.0.0.0")
        with httpx.Client(timeout=30, transport=transport) as http:
            run = run_fallback if args.fallback else run_b1
            level = run(http, deployed, photos)
    except CheckFailed as exc:
        say(f"SMOKE FAILED: {exc}")
        return 1
    except ClientError as exc:
        error = exc.response["Error"]["Code"]
        status = exc.response["ResponseMetadata"]["HTTPStatusCode"]
        say(f"SMOKE FAILED: AWS error in {exc.operation_name}: {error} (HTTP {status})")
        return 1
    except (BotoCoreError, httpx.HTTPError, OSError) as exc:
        # Never the message: an OSError's holds the path of the photo it was reading.
        say(f"SMOKE FAILED: {type(exc).__name__}")
        return 1
    took = time.monotonic() - started
    if not level:
        say(
            f"SMOKE NO LEVEL in {took:.1f} s: every other check passed, so C71 applies"
            " (exit 3)"
        )
        return 3
    say(f"SMOKE OK in {took:.1f} s")
    return 0


def run_b1(http: httpx.Client, stack: Stack, photos: Sequence[Path]) -> bool:
    """The B1 run's checks, in the module docstring's order.

    Returns whether a photo gave a level.
    """
    check_preflight(http, stack.api_url)
    sent = []
    reused = False
    for n, photo in enumerate(photos, 1):
        item = upload_photo(http, stack, f"photo {n}/{len(photos)}", as_app_jpeg(photo))
        sent.append(item)
        # B5 runs on the first report that paid Meta, before the next upload, while
        # its form is still good.
        if not reused and meta_calls(item.lines):
            check_reused_link(http, stack, item)
            reused = True
    if not reused:
        raise CheckFailed(
            "reused link: no photo's log shows a Meta call, so B5 can't run"
        )
    dark = upload_photo(http, stack, "the dark photo", dark_jpeg(), origin=APP_ORIGIN)
    check_dark(dark)
    level = any("level" in item.body for item in sent)
    if not level:
        say_no_level(sent)
    check_stored_photos(stack, [*sent, dark])
    say_spend([*sent, dark])
    check_missing_photo(http, stack)
    check_png_refused(http, stack.api_url)
    check_key_loaded(stack.session)
    check_stop_switch(stack.session, http, stack.api_url)
    return level


def run_fallback(http: httpx.Client, stack: Stack, photos: Sequence[Path]) -> bool:
    """C71's fallback: checks 2, 5 and 6 on the photos, sent up to the first level."""
    sent = []
    for n, photo in enumerate(photos, 1):
        label = f"fallback photo {n}/{len(photos)}"
        sent.append(upload_photo(http, stack, label, as_app_jpeg(photo)))
        if "level" in sent[-1].body:
            break
    level = "level" in sent[-1].body
    end = "up to the first level" if level else "and none gave a level"
    say(f"fallback: sent {len(sent)} of {len(photos)} photos, {end}")
    if not level:
        say_no_level(sent)
    check_stored_photos(stack, sent)
    say_spend(sent)
    return level


def photo_folder() -> Path:
    """C87's photo folder, LUSOT_DATA_DIR\\set_c\\commons-ph-floods."""
    data = Path(os.environ.get("LUSOT_DATA_DIR") or DATA_DIR)
    return data / "set_c" / "commons-ph-floods"


def refuse_sealed(path: Path) -> None:
    """Refuse a path inside a folder named sealed, in any case (CLAUDE.md, C66).

    The offline runner's rule, run before the path is opened or listed: the path is
    checked first as written, made absolute, so a path that names the folder never
    reaches the disk, then resolved, so `..` and links can't hide the folder.
    """

    def inside(checked: Path) -> bool:
        return "sealed" in (part.lower() for part in checked.parts)

    if inside(path.absolute()) or inside(path.resolve()):
        raise CheckFailed("refused: a path inside a folder named sealed")


def seeded_photo_order(folder: Path) -> list[Path]:
    """C87's full order: the listed photos' base names, sorted, then one seeded draw.

    The list has a `full path<TAB>licence` line per photo, and `#` lines are
    comments. The order is fixed in advance, whatever attribution.csv holds (R102):
    positions 0 to 4 are B1's, and 5 to 19 are C71's fallback. A listed photo
    missing from the folder raises CheckFailed.
    """
    refuse_sealed(folder)
    # utf-8-sig: Windows PowerShell 5.1 writes UTF-8 with a BOM.
    text = (folder / PHOTO_LIST).read_text(encoding="utf-8-sig")
    names = sorted(
        PureWindowsPath(line.split("\t", 1)[0].strip()).name
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    missing = sum(not (folder / name).is_file() for name in names)
    if missing:
        raise CheckFailed(
            f"{missing} of the {len(names)} listed photos are missing from the folder"
        )
    return [folder / name for name in random.Random(SEED).sample(names, len(names))]


def credited(folder: Path, photos: Sequence[Path]) -> tuple[list[Path], int]:
    """The photos with a credit line in attribution.csv, in order, and how many weren't.

    Only these are sent to Meta, so every photo sent keeps its credit (R102). A photo
    with no row, or a blank credit_line, is skipped.
    """
    refuse_sealed(folder)
    with (folder / CREDITS).open(encoding="utf-8-sig", newline="") as file:
        lines = {row["file_name"]: row["credit_line"] for row in csv.DictReader(file)}
    kept = [photo for photo in photos if (lines.get(photo.name) or "").strip()]
    return kept, len(photos) - len(kept)


def as_app_jpeg(path: Path) -> bytes:
    """The photo as the app sends it (app/src/lib/capture.ts).

    Decoded upright, shrunk with INTER_AREA so its longer side is at most 1,600 px
    (a smaller photo keeps its size), then encoded as JPEG at quality 85.
    """
    refuse_sealed(path)
    try:
        bgr = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    except cv2.error:  # an empty file raises instead of returning None
        bgr = None
    if bgr is None:
        raise CheckFailed("a photo doesn't decode")
    height, width = bgr.shape[:2]
    if max(height, width) > APP_MAX_SIDE:
        scale = APP_MAX_SIDE / max(height, width)
        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        bgr = cv2.resize(bgr, size, interpolation=cv2.INTER_AREA)
    quality = [cv2.IMWRITE_JPEG_QUALITY, APP_JPEG_QUALITY]
    return cv2.imencode(".jpg", bgr, quality)[1].tobytes()


def dark_jpeg() -> bytes:
    """A 1600 x 1200 horizontal grey gradient from 0 to 30, as the app's JPEG.

    Its mean grey of about 15 is under C44's brightness cutoff of 40, so its report
    must end refused/too_dark before any Meta call.
    """
    row = np.linspace(0, 30, 1600).astype(np.uint8)
    grey = np.tile(row, (1200, 1))
    quality = [cv2.IMWRITE_JPEG_QUALITY, APP_JPEG_QUALITY]
    return cv2.imencode(".jpg", np.dstack([grey] * 3), quality)[1].tobytes()


def upload_photo(
    http: httpx.Client,
    stack: Stack,
    label: str,
    data: bytes,
    *,
    origin: str | None = None,
) -> Sent:
    """Send one photo, wait for its report to be final, and print how it ended."""
    item = send(http, stack, label, data, origin=origin)
    item.body, item.lines, final_s = await_report(
        http, stack, label, item.report_id, since=item.uploaded
    )
    say(
        f"{label}: {result_text(item.body)} {final_s:.1f} s after its upload,"
        f" {meta_calls(item.lines)} Meta calls"
    )
    return item


def send(
    http: httpx.Client,
    stack: Stack,
    label: str,
    data: bytes,
    *,
    origin: str | None = None,
) -> Sent:
    """POST /uploads, then the photo through its presigned form, as the app does.

    With `origin`, both calls carry it and must answer with the app's allow-origin
    header (MS1's checks).
    """
    created = request_upload(http, stack.api_url, origin=origin)
    issued = time.monotonic()
    if origin is not None:
        check_allow_origin(created, "POST /uploads")
    link = created.json()
    posted = post_form(http, link["upload"], data, origin=origin)
    if posted.status_code != 204:
        raise CheckFailed(
            f"{label}: S3 form post: HTTP {posted.status_code} {s3_error(posted)},"
            " expected 204"
        )
    if origin is not None:
        check_allow_origin(posted, "the S3 form post")
    return Sent(label, link["reportId"], link["upload"], data, issued, time.monotonic())


def post_form(
    http: httpx.Client, form: dict, data: bytes, *, origin: str | None = None
) -> httpx.Response:
    # The fields go in order, and httpx sends the file after them, as S3 requires.
    return http.post(
        form["url"],
        data=form["fields"],
        files={"file": ("smoke.jpg", data, "image/jpeg")},
        headers={"Origin": origin} if origin else {},
    )


def await_report(
    http: httpx.Client,
    stack: Stack,
    label: str,
    report_id: str,
    *,
    since: float,
    bound_s: float = POLL_FOR_S,
) -> tuple[dict, list[dict], float]:
    """A report's final body (C68), its log lines, and its seconds from `since`.

    The body must have C67's shape, and the log must hold the line of how it ended.
    """
    try:
        body = wait_final(http, stack.api_url, report_id, since=since, bound_s=bound_s)
        final_s = time.monotonic() - since
        check_report_body(body)
        outcome = outcome_of(body)
        lines = log_lines(stack.session, report_id, stack.since_ms, until=outcome)
        if not any(line.get("outcome") == outcome for line in lines):
            raise CheckFailed(f"no {outcome} line in the analysis log")
    except CheckFailed as exc:
        raise CheckFailed(f"{label}: {exc}") from None
    return body, lines, final_s


def wait_final(
    http: httpx.Client,
    api_url: str,
    report_id: str,
    *,
    since: float,
    bound_s: float = POLL_FOR_S,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Poll GET /reports/{id} every 2 s until the report is final, and return its body.

    pending, processing and 404 poll on: processing isn't final (spec §3.5), and a
    404 can mean the report index hasn't caught up with a new report yet. Once
    `bound_s` has passed since `since`, a clock() value, it raises CheckFailed: B1's
    bound is 120 s from the photo's 204 (C68).
    """
    while True:
        response = http.get(f"{api_url}/reports/{report_id}")
        if response.status_code not in (200, 404):
            raise CheckFailed(f"GET /reports: {got(response)}")
        report = (
            response.json() if response.status_code == 200 else {"status": "not_found"}
        )
        if report.get("status") in FINAL_STATUSES:
            return report
        if clock() - since >= bound_s:
            raise CheckFailed(f"still {report.get('status')} after {bound_s:g} s")
        sleep(POLL_EVERY_S)


def check_report_body(body: dict) -> None:
    """GET /reports/{id}'s final body has C67's shape, and nothing more.

    Every body has reportId, status and capturedAt. A refused or failed report adds
    its refusalReason (C50). A done report adds noFloodSeen and, with a level, also
    level, landmark, passability, basis as two counts, and levelIsFloor. Any other
    key fails: the location, readings, photoKey and the claim never reach the app.
    The error names keys, never their values.
    """
    status = body.get("status")
    if status not in FINAL_STATUSES:
        raise CheckFailed(f"report body: status {status!r} isn't final")
    keys = {"reportId": str, "status": str, "capturedAt": str}
    if status != "done":
        keys["refusalReason"] = str
    else:
        keys["noFloodSeen"] = bool
        if body.get("noFloodSeen") is False:
            keys |= {
                "level": str,
                "landmark": str,
                "passability": str,
                "basis": dict,
                "levelIsFloor": bool,
            }
    extra, missing = sorted(body.keys() - keys), sorted(keys.keys() - body.keys())
    if extra or missing:
        raise CheckFailed(
            f"report body ({status}): extra keys {extra}, missing keys {missing}"
        )
    # Exact types: a count isn't a bool, and a string isn't empty.
    wrong = [
        key
        for key, kind in keys.items()
        if type(body[key]) is not kind or (kind is str and not body[key])
    ]
    basis = body.get("basis")
    if type(basis) is dict and (
        basis.keys() != {"vehicles", "people"}
        or any(type(count) is not int for count in basis.values())
    ):
        wrong.append("basis")
    if wrong:
        raise CheckFailed(f"report body ({status}): wrong {sorted(set(wrong))}")


def outcome_of(body: dict) -> str:
    """The log line's outcome for a final body, as the pipeline's Outcome.log_name.

    That is done/level, done/no_flood_seen, or status/reason.
    """
    if body["status"] != "done":
        return f"{body['status']}/{body['refusalReason']}"
    return "done/no_flood_seen" if body["noFloodSeen"] else "done/level"


def result_text(body: dict) -> str:
    """A final body as the run prints it: its outcome, and its level if it has one."""
    if "level" not in body:
        return outcome_of(body)
    floor = "at least " if body["levelIsFloor"] else ""
    return f"done/level {floor}{body['level']} ({body['passability']})"


def meta_calls(lines: Iterable[dict]) -> int:
    """The Meta calls a report's log lines record.

    A line that ends before the pipeline has no meta_calls (Task 13's review).
    """
    return sum(line.get("meta_calls", 0) for line in lines)


def log_lines(
    session: boto3.Session,
    report_id: str,
    since_ms: int,
    *,
    until: str | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict]:
    """The analysis log's JSON lines for one report. They are never printed.

    A line is an event's text from its first `{`, so Lambda's text format (level,
    time and request id, tab-separated) is dropped, and an event without JSON there
    is skipped. Events take a few seconds to become searchable, so it waits up to
    30 s for a line whose outcome is `until`, or for any line when `until` is None,
    and then returns what it found.
    """
    group = session.client("cloudformation").describe_stack_resource(
        StackName=STACK, LogicalResourceId="AnalysisLogGroup"
    )["StackResourceDetail"]["PhysicalResourceId"]
    paginator = session.client("logs").get_paginator("filter_log_events")
    began = clock()
    while True:
        lines = []
        pages = paginator.paginate(
            logGroupName=group, startTime=since_ms, filterPattern=f'"{report_id}"'
        )
        for page in pages:
            for event in page["events"]:
                line = _json_line(event["message"])
                # The search matches the id anywhere, so only the report's own lines.
                if line is not None and line.get("reportId") == report_id:
                    lines.append(line)
        if until is None:
            found = bool(lines)
        else:
            found = any(line.get("outcome") == until for line in lines)
        if found or clock() - began >= LOG_WAIT_S:
            return lines
        sleep(LOG_POLL_S)


def _json_line(message: str) -> dict | None:
    """A log event's JSON object, from its first `{` to its end, or None."""
    start = message.find("{")
    if start < 0:
        return None
    try:
        line = json.loads(message[start:])
    except ValueError:
        return None
    return line if isinstance(line, dict) else None


def check_form_fresh(issued_s: float, now_s: float) -> None:
    """The reused form must be at most 280 s old: S3 refuses it after 300 s (C27)."""
    if now_s - issued_s > FORM_FRESH_S:
        raise CheckFailed("reused link: form too old")


def check_reused_link(http: httpx.Client, stack: Stack, item: Sent) -> None:
    """B5 (G2, plan §7 step 8): the same form and bytes again, after the result.

    S3 takes them (204), and the analysis finds the report final: it deletes the new
    raw photo within 60 s and calls no model, so the log gains an already_finished
    line and still has exactly one line with Meta calls. An extra lease_held line
    from a duplicate delivery is fine (C89).
    """
    check_form_fresh(item.issued, time.monotonic())
    posted = post_form(http, item.form, item.data)
    if posted.status_code != 204:
        raise CheckFailed(
            f"reused link: HTTP {posted.status_code} {s3_error(posted)}, expected 204"
        )
    reposted = time.monotonic()
    s3 = stack.session.client("s3")
    while object_exists(s3, stack.bucket, f"raw/{item.report_id}.jpg"):
        if time.monotonic() - reposted >= RAW_GONE_S:
            raise CheckFailed(
                f"reused link: the raw photo is still there after {RAW_GONE_S} s"
            )
        time.sleep(POLL_EVERY_S)
    gone_s = time.monotonic() - reposted
    item.lines = log_lines(
        stack.session, item.report_id, stack.since_ms, until="already_finished"
    )
    if not any(line.get("outcome") == "already_finished" for line in item.lines):
        raise CheckFailed("reused link: no already_finished line in the analysis log")
    paid = sum(line.get("meta_calls", 0) > 0 for line in item.lines)
    if paid != 1:
        raise CheckFailed(f"reused link: {paid} log lines with Meta calls, expected 1")
    say(
        f"reused link: S3 took the form again (204), the raw photo was gone in"
        f" {gone_s:.1f} s, and the log has already_finished and still one line with"
        " Meta calls"
    )


def check_dark(item: Sent) -> None:
    """B1: the dark photo is refused as too dark, with no Meta call (C44)."""
    outcome = outcome_of(item.body)
    if outcome != "refused/too_dark":
        raise CheckFailed(f"the dark photo ended {outcome}, expected refused/too_dark")
    calls = meta_calls(item.lines)
    if calls:
        raise CheckFailed(f"the dark photo's log shows {calls} Meta calls, expected 0")


def say_no_level(items: Sequence[Sent]) -> None:
    """Check 5 when no photo gave a level (C71): print the outcomes.

    Each photo's drop causes from its log lines follow, for C75's diagnosis. Counts
    only.
    """
    outcomes = Counter(outcome_of(item.body) for item in items)
    counts = ", ".join(f"{n} {outcome}" for outcome, n in sorted(outcomes.items()))
    say(f"no photo gave a level (C71): {counts}")
    for item in items:
        drops = Counter()
        for line in item.lines:
            drops.update(line.get("drops") or {})
        causes = ", ".join(f"{cause} {n}" for cause, n in sorted(drops.items()))
        say(f"{item.label} drops: {causes or 'none'}")


def check_stored_photos(stack: Stack, items: Sequence[Sent]) -> None:
    """B4 (W25, C61): no raw photo is left, and only a level keeps a blurred photo."""
    s3 = stack.session.client("s3")
    for item in items:
        if object_exists(s3, stack.bucket, f"raw/{item.report_id}.jpg"):
            raise CheckFailed(f"{item.label}: its raw photo is still in the bucket")
        level = "level" in item.body
        if object_exists(s3, stack.bucket, f"blurred/{item.report_id}.jpg") != level:
            wrong = "a level but no blurred photo" if level else "a blurred photo"
            raise CheckFailed(f"{item.label}: {wrong} (B4)")
    levels = sum("level" in item.body for item in items)
    say(
        f"stored photos: no raw photo left for {len(items)} reports, and a blurred"
        f" photo only for the {levels} with a level"
    )


def object_exists(s3, bucket: str, key: str) -> bool:
    """Whether head_object finds the key. Any answer but 200 or 404 fails the check."""
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        status = exc.response["ResponseMetadata"]["HTTPStatusCode"]
        if status != 404:
            raise CheckFailed(
                f"head_object: HTTP {status}, expected 200 or 404"
            ) from None
        return False
    return True


def run_summary(lines: Iterable[dict]) -> dict:
    """The run's Meta calls, the 504s and 413s they ended on, and the estimated cost.

    It reads the run's log lines. A line's SAM calls are its sam_ms timings, or all
    its meta_calls when SAM failed before they were logged; the rest are judge's. A
    meta_status is the error that ended its pipeline: judge's when SAM's timings are
    in the line, else SAM's. The cost comes from SAM's calls at its price per image
    and from Muse Spark's billed usage, the input_tokens and output_tokens of its
    answers, never from a token count: counts aren't bills (MS1's probe note).
    """
    calls = {"sam": 0, "judge": 0}
    ended_on = {"sam": {504: 0, 413: 0}, "judge": {504: 0, 413: 0}}
    billed = {"input": 0, "output": 0}
    for line in lines:
        made = line.get("meta_calls", 0)
        sam = len(line["sam_ms"]) if "sam_ms" in line else made
        calls["sam"] += sam
        calls["judge"] += made - sam
        status = line.get("meta_status")
        if status in (504, 413):
            ended_on["judge" if "sam_ms" in line else "sam"][status] += 1
        billed["input"] += line.get("input_tokens") or 0
        billed["output"] += line.get("output_tokens") or 0
    usd = (
        calls["sam"] * SAM_USD_PER_IMAGE
        + billed["input"] * SPARK_USD_PER_INPUT_TOKEN
        + billed["output"] * SPARK_USD_PER_OUTPUT_TOKEN
    )
    return {"calls": calls, "ended_on": ended_on, "billed_tokens": billed, "usd": usd}


def say_spend(items: Sequence[Sent]) -> None:
    spend = run_summary(line for item in items for line in item.lines)
    calls, ended, billed = spend["calls"], spend["ended_on"], spend["billed_tokens"]
    say(
        f"spend: {calls['sam'] + calls['judge']} Meta calls (SAM {calls['sam']},"
        f" judge {calls['judge']}); ended on 504: SAM {ended['sam'][504]}, judge"
        f" {ended['judge'][504]}; on 413: SAM {ended['sam'][413]}, judge"
        f" {ended['judge'][413]}; billed {billed['input']:,} input and"
        f" {billed['output']:,} output tokens, estimated ${spend['usd']:.4f}"
    )


def check_missing_photo(http: httpx.Client, stack: Stack) -> None:
    """Spec §3.6: a report whose photo never came ends failed/photo_missing in 60 s.

    POST /uploads makes the report, and no photo is sent. The queue then gets one
    S3-shaped notification for its raw key, through get_queue_url on the stack's
    QueueName; the URL holds the account ID, so it is never printed. The log line's
    S3 error code and HTTP status are printed, for R93's follow-up.
    """
    report_id = request_upload(http, stack.api_url).json()["reportId"]
    sqs = stack.session.client("sqs")
    queue_url = sqs.get_queue_url(QueueName=stack.queue)["QueueUrl"]
    notification = s3_notification(stack.bucket, f"raw/{report_id}.jpg")
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(notification))
    body, lines, final_s = await_report(
        http,
        stack,
        "the missing photo",
        report_id,
        since=time.monotonic(),
        bound_s=MISSING_PHOTO_S,
    )
    outcome = outcome_of(body)
    if outcome != "failed/photo_missing":
        raise CheckFailed(
            f"the missing photo ended {outcome}, expected failed/photo_missing"
        )
    line = next(line for line in lines if line.get("outcome") == outcome)
    say(
        f"missing photo: failed/photo_missing {final_s:.1f} s after its notification,"
        f" S3 said {line.get('error')} (HTTP {line.get('http_status')})"
    )


def s3_notification(bucket: str, key: str) -> dict:
    """One ObjectCreated notification, shaped as S3 sends it to the queue.

    The handler reads only each record's object key.
    """
    record = {
        "eventVersion": "2.1",
        "eventSource": "aws:s3",
        "awsRegion": REGION,
        "eventName": "ObjectCreated:Post",
        "s3": {"bucket": {"name": bucket}, "object": {"key": key}},
    }
    return {"Records": [record]}


def check_preflight(http: httpx.Client, api_url: str) -> None:
    for origin in ORIGINS:
        response = http.options(
            f"{api_url}/uploads",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        allowed = response.headers.get("access-control-allow-origin")
        if allowed != origin:
            raise CheckFailed(
                f"preflight from {origin}: HTTP {response.status_code},"
                f" allow-origin {allowed!r}"
            )
    say(f"cors: the preflight for POST /uploads allows {' and '.join(ORIGINS)}")


def check_png_refused(http: httpx.Client, api_url: str) -> None:
    """S3 itself must refuse a non-JPEG, through the form's conditions (C27)."""
    created = request_upload(http, api_url)
    upload = created.json()["upload"]
    posted = http.post(
        upload["url"],
        data={**upload["fields"], "Content-Type": "image/png"},
        files={"file": ("smoke.png", synthetic_photo(".png"), "image/png")},
    )
    if posted.status_code != 403:
        raise CheckFailed(
            f"PNG form post: HTTP {posted.status_code}, expected 403 from S3"
        )
    say(f"png upload: refused by S3 (403 {s3_error(posted)})")


def check_key_loaded(session: boto3.Session) -> None:
    """The analysis function logs model_key_loaded=true once per cold start (C28).

    Only a cold start after the function and the key last changed proves that pair
    works, so the search starts at the later change: re-storing the key doesn't change
    the function's LastModified. The key's change time comes from describe_parameters,
    so its value is never fetched.
    """
    function = session.client("cloudformation").describe_stack_resource(
        StackName=STACK, LogicalResourceId="AnalysisFunction"
    )["StackResourceDetail"]["PhysicalResourceId"]
    lam = session.client("lambda")
    config = lam.get_function(FunctionName=function)["Configuration"]
    keys = session.client("ssm").describe_parameters(
        ParameterFilters=[{"Key": "Name", "Option": "Equals", "Values": [KEY_PARAM]}]
    )["Parameters"]
    if not keys:
        raise CheckFailed(f"the Meta key parameter {KEY_PARAM} does not exist")
    since = max(
        datetime.fromisoformat(config["LastModified"]), keys[0]["LastModifiedDate"]
    )
    paginator = session.client("logs").get_paginator("filter_log_events")
    began = time.monotonic()
    while True:
        pages = paginator.paginate(
            logGroupName=config["LoggingConfig"]["LogGroup"],
            startTime=int(since.timestamp() * 1000),
            filterPattern='"model_key_loaded=true"',
        )
        # Only whether such a line exists: no log content is printed.
        if any(page["events"] for page in pages):
            say(
                "analysis log: model_key_loaded=true"
                " since the function or key last changed"
            )
            return
        if time.monotonic() - began >= LOG_WAIT_S:
            raise CheckFailed(
                "no container has cold-started since the function or key last changed,"
                " so a redeploy or a fresh container is needed"
            )
        time.sleep(5)


def check_stop_switch(session: boto3.Session, http: httpx.Client, api_url: str) -> None:
    ssm = session.client("ssm")
    failure = None
    try:
        # In the try: a put that SSM applies but that fails on our side is reset too.
        ssm.put_parameter(Name=STOP_UPLOADS, Value="on", Type="String", Overwrite=True)
        time.sleep(SWITCH_WAIT_S)
        response = request_upload(http, api_url, expect=503)
        if response.json().get("error") != "uploads_paused":
            raise CheckFailed(
                f"POST /uploads with the switch on: {got(response)},"
                " expected uploads_paused"
            )
    except BaseException as exc:
        failure = exc
        raise
    finally:
        try:
            ssm.put_parameter(
                Name=STOP_UPLOADS, Value="off", Type="String", Overwrite=True
            )
        except (BotoCoreError, ClientError):
            say(
                "STOP SWITCH LEFT ON. Set it back by hand: aws ssm put-parameter"
                f" --name {STOP_UPLOADS} --value off --type String --overwrite"
                " --profile lusot --region ap-southeast-1 --no-cli-pager"
            )
            if failure is not None:  # so the reset's error doesn't hide the first one
                say(f"the check had already failed: {failure_name(failure)}")
            raise
    say("stop switch: 503 uploads_paused while on, then set back to off")


def failure_name(exc: BaseException) -> str:
    """An exception's class name and, for an AWS error, its code. Never its message."""
    if isinstance(exc, ClientError):
        return f"{type(exc).__name__} ({exc.response['Error']['Code']})"
    return type(exc).__name__


def request_upload(
    http: httpx.Client, api_url: str, origin: str | None = None, expect: int = 201
) -> httpx.Response:
    body = {
        **SPOT,
        "gpsAccuracyM": 10,
        "capturedAt": datetime.now(UTC).isoformat(timespec="milliseconds"),
    }
    response = http.post(
        f"{api_url}/uploads", json=body, headers={"Origin": origin} if origin else {}
    )
    if response.status_code != expect:
        raise CheckFailed(f"POST /uploads: {got(response)}, expected {expect}")
    return response


def got(response: httpx.Response) -> str:
    """An API reply's status and error fields.

    Never its body: a 201 carries the signed upload form.
    """
    try:
        body = response.json()
    except ValueError:
        body = None
    # Our API sends error and detail; API Gateway's own replies send message.
    fields = (
        [str(body[key]) for key in ("error", "detail", "message") if key in body]
        if isinstance(body, dict)
        else []
    )
    return f"HTTP {response.status_code}" + (f" ({' '.join(fields)})" if fields else "")


def check_allow_origin(response: httpx.Response, what: str) -> None:
    allowed = response.headers.get("access-control-allow-origin")
    if allowed != APP_ORIGIN:
        raise CheckFailed(f"{what}: allow-origin {allowed!r}, expected {APP_ORIGIN!r}")


def synthetic_photo(ext: str) -> bytes:
    """A 640 x 480 grey gradient with no face, encoded as ".jpg" or ".png"."""
    row = np.linspace(0, 255, 640).astype(np.uint8)
    return cv2.imencode(ext, np.dstack([np.tile(row, (480, 1))] * 3))[1].tobytes()


def s3_error(response: httpx.Response) -> str:
    """An S3 error's <Code>, never its body, which can echo the signed form."""
    match = re.search(r"<Code>([^<]+)</Code>", response.text)
    return match.group(1) if match else ""


if __name__ == "__main__":
    raise SystemExit(main())
