# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["boto3[crt]>=1.43.120"]
# ///
"""Redrive the dead-letter queue: messages under a day old, each once (C525, MS4-Q5).

It reads the queues named by the lusot stack's DeadLetterQueueName and QueueName
outputs and classes each dead letter by its S3 record's `eventTime`, the upload, which
stays the same wherever the message has been, while SQS's own timestamps start again
on a redrive:
- move: under a day old and never redriven. The body goes to the upload queue with
  the message attribute `lusot-redriven`, and the dead-letter copy is deleted.
- too_old: a day old or more. Its raw photo has gone to the 1-day rule: deleted.
- already_redriven: it failed again after a redrive: deleted, never redriven twice.
- unreadable: no S3 record with a dated eventTime: deleted.

SQS's own StartMessageMoveTask moves every message as it is, with no filter and no
attribute (botocore's model takes SourceArn, DestinationArn and a rate only), so this
receives, classes and sends each one itself. `--dry-run` receives with a 60 s
visibility timeout, changes nothing else and prints what it would do; the real run
then sees those messages once the minute has passed.

Each message holds the uploader's IP address, so it prints counts only: never a body,
a receipt handle or a queue URL, which holds the account ID. boto3 comes with its CRT
extra for the lusot profile's `aws login` credentials.

Usage: uv run backend/scripts/redrive_dlq.py [--dry-run]
Exit codes: 0 done; 1 an AWS error, or the stack lacks a queue output.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Literal

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from guards import counts, failure, say, stack_outputs

REGION = "ap-southeast-1"
REDRIVEN = "lusot-redriven"  # the mark a moved message carries
MAX_AGE_S = 24 * 60 * 60  # the raw/ prefix's 1-day rule
VISIBILITY_S = 60
Class = Literal["move", "too_old", "already_redriven", "unreadable"]


def classify(message: dict, now_s: int) -> Class:
    """A dead letter's class, by its mark and its S3 records' oldest eventTime."""
    if REDRIVEN in (message.get("MessageAttributes") or {}):
        return "already_redriven"
    try:
        records = json.loads(message["Body"])["Records"]
        uploads = [datetime.fromisoformat(record["eventTime"]) for record in records]
    except (KeyError, TypeError, ValueError):
        return "unreadable"
    # A time without a zone can't be dated.
    if not uploads or any(when.tzinfo is None for when in uploads):
        return "unreadable"
    oldest = min(when.timestamp() for when in uploads)
    return "move" if now_s - oldest < MAX_AGE_S else "too_old"


def main(
    argv: Sequence[str] | None = None,
    *,
    session=None,
    clock: Callable[[], float] = time.time,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run", action="store_true", help="print what it would do, change nothing"
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code
    try:
        session = session or boto3.Session(profile_name="lusot", region_name=REGION)
        outputs = stack_outputs(session)
        names = [outputs.get(n) for n in ("DeadLetterQueueName", "QueueName")]
        if None in names:
            say("failed: the stack lacks a queue output")
            return 1
        sqs = session.client("sqs")
        dead, upload = (sqs.get_queue_url(QueueName=n)["QueueUrl"] for n in names)
        found = drain(sqs, dead, upload, dry_run=args.dry_run, clock=clock)
    except (BotoCoreError, ClientError) as exc:
        say(f"failed: {failure(exc)}")
        return 1
    moves = found.pop("move", 0)
    deletes = sum(found.values())
    detail = f": {counts(found)}" if found else ""
    if args.dry_run:
        say(f"dry run: would move {moves}, would delete {deletes}{detail}")
    else:
        say(f"moved {moves}, deleted {deletes}{detail}")
    return 0


def drain(sqs, dead: str, upload: str, *, dry_run: bool, clock) -> Counter:
    """Receive every dead letter once, class it and, unless a dry run, act on it."""
    found: Counter = Counter()
    seen: set[str] = set()
    while True:
        messages = sqs.receive_message(
            QueueUrl=dead,
            MaxNumberOfMessages=10,
            VisibilityTimeout=VISIBILITY_S,
            WaitTimeSeconds=2,  # long polling asks every server, so empty means empty
            MessageAttributeNames=["All"],
        ).get("Messages", [])
        fresh = [m for m in messages if m["MessageId"] not in seen]
        if not fresh:
            return found
        for message in fresh:
            seen.add(message["MessageId"])
            kind = classify(message, int(clock()))
            found[kind] += 1
            if dry_run:
                continue
            if kind == "move":
                sqs.send_message(
                    QueueUrl=upload,
                    MessageBody=message["Body"],
                    MessageAttributes={
                        REDRIVEN: {"DataType": "String", "StringValue": "1"}
                    },
                )
            # After the send, so a failed send leaves the letter where it was.
            sqs.delete_message(QueueUrl=dead, ReceiptHandle=message["ReceiptHandle"])


if __name__ == "__main__":
    raise SystemExit(main())
