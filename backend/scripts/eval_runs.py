# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "boto3[crt]>=1.43.120",
#     "httpx>=0.28.1",
#     "numpy>=2.5.4",
#     "opencv-python-headless>=4.14.0.94,<5",
# ]
# ///
"""The recovery checks' cloud runs, in eval mode (MS4 spec §4.8, C513; plan Task 8).

Each run writes one `eval` item under the EVAL key, never a pin, sends the photo at
position N of C87's order as the app sends it (smoke_upload.py's `seeded_photo_order`
and `credited`, behind the sealed-path guard, so no path is typed or printed), waits for
the report to end, and reads its analysis log lines:
- duplicate: once the report is final, one more S3-shaped notification for its raw
  key. Expected: an already_finished line, and at most one line with Meta calls.
- race: that notification at once, beside the photo's own. Expected: at most one line
  with Meta calls.
- dead-holder: the item is written already `processing` under a live lease (a random
  claimToken, claimedAt now) with no worker behind it, standing in for a holder that
  died. The photo's own event meets the lease and returns its message, which comes
  back after the queue's 1,080 s visibility timeout, once the 900 s lease has expired,
  and re-claims. Expected: a lease_held line, a final report within 1,500 s, and at
  most one line with Meta calls.
- paused: with /lusot/stop/model-calls already "on" (set by hand, after telling the
  tracker). Expected: failed/model_calls_paused with no Meta call.

It prints the report id, its outcome, the seconds to it, the Meta calls in its log
lines and their outcomes, through guards.say: never a path, a URL or a log line. Every
Meta call here runs on the credits, at about $0.03 a photo.

The helpers below (`eval_item`, `wait_item`, `item_outcome`, `api_client`) are shared
with demo_pins.py and samples.py, which run reports in the cloud too.

Usage: uv run backend/scripts/eval_runs.py <duplicate|race|dead-holder|paused>
           --position N
Exit codes: 0 the case behaved as expected; 1 it didn't, a check failed or the photo
isn't there or has no credit line; 2 refused by a guard (a sealed path, or paused with
the switch not on).
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from guards import data_dir, refuse_sealed, say
from ops_common import WAIT_S, counts, guarded, lusot_session
from smoke_upload import (
    FINAL_STATUSES,
    CheckFailed,
    Stack,
    as_app_jpeg,
    credited,
    load_stack,
    log_lines,
    meta_calls,
    outcome_of,
    photo_folder,
    s3_notification,
    seeded_photo_order,
    wait_final,
)

CASES = ("duplicate", "race", "dead-holder", "paused")
# Seconds from the photo to a final report: the visibility timeout, the run and a margin
# for dead-holder; the brief's 180 s otherwise.
BOUND_S = {"duplicate": WAIT_S, "race": WAIT_S, "dead-holder": 1500, "paused": WAIT_S}
STOP_MODEL_CALLS = "/lusot/stop/model-calls"
RETAIN_S = 7 * 24 * 60 * 60  # Table 14: an item is deleted 7 days after it is made
POLL_S = 2


def iso_seconds(epoch_s: int) -> str:
    """Table 14's time form, in UTC to the second, as the API's isoSeconds writes it."""
    return datetime.fromtimestamp(epoch_s, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_report_id() -> str:
    """C32's form: 122 random bits."""
    return "r_" + uuid.uuid4().hex


def eval_item(report_id: str, now_s: int, *, seed: bool = False) -> dict:
    """An eval report's item, as put_item takes it (C513).

    The receive time stands in for a capture time, as for a sample, and the item has
    no location and no visibleUntil, so it never pins. `seed` marks a sample's seeding
    run, whose stored copy Task 13's keep_photo keeps whatever the outcome (C512).
    """
    received = iso_seconds(now_s)
    item = {
        "pk": {"S": "EVAL"},
        "sk": {"S": f"{received}#{report_id}"},
        "reportId": {"S": report_id},
        "mode": {"S": "eval"},
        "status": {"S": "pending"},
        "capturedAt": {"S": received},
        "receivedAt": {"S": received},
        "expiresAt": {"N": str(now_s + RETAIN_S)},
    }
    if seed:
        item["seed"] = {"BOOL": True}
    return item


def wait_item(
    ddb,
    table: str,
    key: dict,
    *,
    bound_s: float,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> dict:
    """The item once its status is final, polled every 2 s with a consistent read, or
    as it stands once `bound_s` has passed (an empty dict if it is gone)."""
    began = clock()
    while True:
        item = ddb.get_item(TableName=table, Key=key, ConsistentRead=True).get(
            "Item", {}
        )
        status = item.get("status", {}).get("S")
        if status in FINAL_STATUSES or clock() - began >= bound_s:
            return item
        sleep(POLL_S)


def item_outcome(item: dict) -> str:
    """A stored item's outcome as the log names it: done/level, status/reason..."""
    status = item.get("status", {}).get("S")
    if status in ("refused", "failed"):
        return f"{status}/{item.get('refusalReason', {}).get('S')}"
    if status == "done":
        return "done/level" if "level" in item else "done/no_flood_seen"
    return f"still {status or 'missing'}"


@contextmanager
def api_client(http: httpx.Client | None) -> Iterator[httpx.Client]:
    """`http`, or a client for the run over IPv4 only, since IPv6 doesn't connect on
    the home Wi-Fi (Oct 28 log)."""
    if http is not None:
        yield http
        return
    transport = httpx.HTTPTransport(local_address="0.0.0.0")
    with httpx.Client(timeout=30, transport=transport) as client:
        yield client


def main(
    argv: Sequence[str] | None = None,
    *,
    session=None,
    http: httpx.Client | None = None,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("case", choices=CASES)
    parser.add_argument(
        "--position", type=int, required=True, help="the photo's place in C87's order"
    )

    def command() -> int:
        args = parser.parse_args(argv)
        refuse_sealed(data_dir())
        return run(args, session, http, clock, sleep)

    return guarded(
        command,
        label="EVAL FAILED",
        shown=(CheckFailed,),
        errors=(BotoCoreError, ClientError, httpx.HTTPError),
    )


def run(args, session, http, clock, sleep) -> int:
    folder = photo_folder()
    refuse_sealed(folder)
    order = seeded_photo_order(folder)
    if not 0 <= args.position < len(order):
        raise CheckFailed(f"position {args.position} is outside C87's {len(order)}")
    photos, skipped = credited(folder, [order[args.position]])
    if skipped:
        raise CheckFailed(
            f"the photo at position {args.position} has no credit line (R102)"
        )
    jpeg = as_app_jpeg(photos[0])
    session = session or lusot_session()
    stack = load_stack(session)
    if args.case == "paused":
        ssm = session.client("ssm")
        if ssm.get_parameter(Name=STOP_MODEL_CALLS)["Parameter"]["Value"] != "on":
            say(f"refused: {STOP_MODEL_CALLS} isn't on, so the paused case can't run")
            return 2
    report_id = new_report_id()
    now_s = int(clock())
    item = eval_item(report_id, now_s)
    if args.case == "dead-holder":
        item |= {
            "status": {"S": "processing"},
            "claimToken": {"S": uuid.uuid4().hex},
            "claimedAt": {"N": str(now_s)},
        }
    # The item first, so the photo's event finds it.
    session.client("dynamodb").put_item(TableName=stack.output("TableName"), Item=item)
    key = f"raw/{report_id}.jpg"
    session.client("s3").put_object(
        Bucket=stack.bucket, Key=key, Body=jpeg, ContentType="image/jpeg"
    )
    started = clock()
    if args.case == "race":
        notify(stack, key)
    with api_client(http) as client:
        try:
            body = wait_final(
                client,
                stack.api_url,
                report_id,
                since=started,
                bound_s=BOUND_S[args.case],
                clock=clock,
                sleep=sleep,
            )
        except CheckFailed as exc:
            raise CheckFailed(f"{report_id}: {exc}") from None
    took = clock() - started
    outcome = outcome_of(body)
    until = outcome
    if args.case == "duplicate":
        notify(stack, key)
        until = "already_finished"
    lines = log_lines(stack, report_id, until=until, clock=clock, sleep=sleep)
    logged = Counter(str(line.get("outcome")) for line in lines)
    say(
        f"{report_id}: {args.case}, {outcome} in {took:.1f} s, {meta_calls(lines)}"
        f" Meta calls; log: {counts(logged)}"
    )
    problem = case_problem(args.case, outcome, lines, logged)
    if problem:
        say(f"EVAL FAILED: {problem}")
        return 1
    say("EVAL OK")
    return 0


def notify(stack: Stack, key: str) -> None:
    """One more S3-shaped notification for `key` on the upload queue, whose URL holds
    the account ID, so it is looked up by name and never printed."""
    sqs = stack.session.client("sqs")
    url = sqs.get_queue_url(QueueName=stack.queue)["QueueUrl"]
    sqs.send_message(
        QueueUrl=url, MessageBody=json.dumps(s3_notification(stack.bucket, key))
    )


def case_problem(
    case: str, outcome: str, lines: list[dict], logged: Counter
) -> str | None:
    """What a case's run did that §4.8 says it shouldn't, or None."""
    paid = sum(line.get("meta_calls", 0) > 0 for line in lines)
    if paid > 1:
        return f"{paid} log lines with Meta calls, expected at most 1"
    if case == "duplicate" and not logged["already_finished"]:
        return "no already_finished line in the analysis log"
    if case == "dead-holder" and not logged["lease_held"]:
        return "no lease_held line in the analysis log"
    if case == "paused" and (outcome, meta_calls(lines)) != (
        "failed/model_calls_paused",
        0,
    ):
        return f"ended {outcome}, expected failed/model_calls_paused with no Meta call"
    return None


if __name__ == "__main__":
    raise SystemExit(main())
