"""The analysis Lambda: the landmark pipeline under a claim (spec §3.1).

For each uploaded photo it finds the report, loads what the run needs, and claims the
report before any paid Meta call (G2, C46). It then runs the pipeline, stores a photo
for a level result only (C61), writes the result under the claim, and deletes the raw
photo, so no raw photo outlives its report's result (W25).

An AWS error returns the message for an SQS retry, which comes after the claim's
lease has expired (C46). A fault in what the run loads, and a key or account that
Meta rejects, return it too, so they end in the dead-letter queue and its alarm, not
in failed reports (C60, C73, C79). A delivery that meets another worker's live lease
also returns its message, but its copy normally finishes on redelivery: a message is
finished only once its report is final or its own work has ended, so a copy is left
to claim the report again if that worker crashes (C89).

A report's mode, read from its item, sets where its photo is stored (C510), and a
live or demo level is published only while the publish switch reads "off" (C516).

The Meta spend stop (C527): before any Meta call, a spend counter at or over the stop
in /lusot/spend/stop-usd, or either one unreadable, sets the model-calls switch "on"
and ends the report paused. After the run, its cost goes to the counter, and a total
that reaches the stop, or a write that is lost, sets the switch too. Each flip logs
spend_stop or spend_error, which the SpendPauseAlarm counts.

The Meta client and the pipeline are imported where they are first used, not at
import: with OpenCV beside them, the Lambda's init reached its 10 s limit (the cold
start, Oct 29). The first delivery in each container pays for them inside its invoke.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import re
import threading
import time
import uuid
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote_plus

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from lusot_analysis.prompts import PromptSpec, load_prompt
from lusot_analysis.report_store import claim, write_result
from lusot_analysis.spend import (
    SPARK_TOKENS_IF_UNREPORTED,
    SPEND_CONFIG,
    SPEND_STOP_PARAM,
    cost_of,
    record_spend,
    rounded_up,
    spend_total,
)

if TYPE_CHECKING:  # annotations only: each loads where it is used
    from lusot_analysis import meta_client
    from lusot_analysis.pipeline import PipelineRun
    from lusot_analysis.pipeline.types import ModelClient, Outcome

DEADLINE_MARGIN_S = 30  # the run stops this long before Lambda's timeout (C84, C88)

_INDEX_NAME = "reportId-index"
_RAW_KEY = re.compile(r"raw/(r_[0-9a-f]{32})\.jpg")  # the key the API signs (C32)
_JPEG_MAGIC = b"\xff\xd8\xff"  # how every JPEG starts; the app sends only JPEG (C83)
# What S3 answers for a missing raw photo. With the role's raw/-limited s3:ListBucket it
# is NoSuchKey, as MS3a Task 16 recorded in the cloud (R22, R93). Any other code, such as
# AccessDenied or a 403 from clock skew, retries, so a real 403 reaches the dead-letter
# queue and its alarm.
_MISSING_PHOTO_CODES = frozenset({"NoSuchKey"})
_NOT_FOUND_VISIBILITY_S = 10  # a report not yet in the index retries this soon (R92)
# The outcomes that return the message: an error, a rejected key (C73), and another
# worker's live lease (C89).
_RETRY_OUTCOMES = frozenset({"error", "model_key_rejected", "lease_held"})
_PUBLISHED_MODES = frozenset({"live", "demo"})  # the modes that pin (C516)
# SSM after the paid run: 2 s timeouts and 2 retries (3 tries), so a hung call ends
# well inside DEADLINE_MARGIN_S and can't make a redelivery pay again.
_POST_RUN_SSM_CONFIG = Config(
    connect_timeout=2, read_timeout=2, retries={"max_attempts": 2}
)

logger = logging.getLogger("lusot.analysis")
logger.setLevel(logging.INFO)  # Lambda's text log format otherwise drops INFO

_META_CLIENT: meta_client.MetaClient | None = None  # set by _meta_client once loaded


class ReportNotFound(LookupError):
    """No report has this id yet. The index can lag the table, so this is retried."""


def _log(**fields: object) -> None:
    """One JSON line. Never a location, image data, the key or an AWS error message."""
    logger.info(json.dumps(fields))


def _error_fields(exc: Exception) -> dict:
    """The error's code and HTTP status, never its message.

    AWS error messages can carry ARNs, and an ARN carries the account ID.
    """
    if isinstance(exc, ClientError):
        return {
            "error": exc.response["Error"]["Code"],
            "http_status": exc.response["ResponseMetadata"]["HTTPStatusCode"],
        }
    return {"error": type(exc).__name__}


@functools.cache
def _client(service: str):
    """One client per service and process, made on first use."""
    return boto3.client(service)


@functools.cache
def _post_run_ssm():
    """The SSM client for every call after the paid run, made on first use.

    Its short timeouts bound the call inside the run's margin. Every flip of the
    model-calls switch uses it too, before the run or after it (C527). The reads
    before the run keep `_client("ssm")`.
    """
    return boto3.client("ssm", config=_POST_RUN_SSM_CONFIG)


@functools.cache
def _spend_ddb():
    """The spend counter's DynamoDB client, made on first use, with SPEND_CONFIG.

    Its 1 s timeouts and 5 attempts bound the write after the paid run inside the
    run's margin, and ride out a throttle on the shared 2-unit limits table (C527).
    """
    return boto3.client("dynamodb", config=SPEND_CONFIG)


class _CountedClient:
    """The Meta client, with a tally of what its calls may have cost (C527).

    A thin wrapper in the handler, so no module on the measuring path changes. Each
    SAM call that returns counts as one image, and each judge answer adds its tokens,
    or SPARK_TOKENS_IF_UNREPORTED for a count Meta didn't report. A call that raised
    is charged the same, unless Meta answered it with an HTTP error, which isn't
    billed: a timeout, an unfinished or unreadable answer, or a refusal may have
    been. Either guess sets `estimated`, so the count runs over, never under. SAM's
    phrases run in parallel threads, so the tally takes a lock.
    """

    def __init__(self, client: ModelClient) -> None:
        self._client = client
        self._lock = threading.Lock()
        self._sam_images = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self.estimated = False

    def segment(self, image: object, phrase: str, **kwargs: object):
        try:
            result = self._client.segment(image, phrase, **kwargs)
        except Exception as exc:
            if _maybe_billed(exc):
                self._add(images=1, estimated=True)
            raise
        self._add(images=1)
        return result

    def judge(self, image: object, **kwargs: object):
        try:
            answer = self._client.judge(image, **kwargs)
        except Exception as exc:
            if _maybe_billed(exc):
                self._add(tokens=SPARK_TOKENS_IF_UNREPORTED, estimated=True)
            raise
        reported = (answer.input_tokens, answer.output_tokens)
        tokens = tuple(
            fallback if count is None else count
            for count, fallback in zip(
                reported, SPARK_TOKENS_IF_UNREPORTED, strict=True
            )
        )
        self._add(tokens=tokens, estimated=None in reported)
        return answer

    def cost(self) -> Decimal:
        """What the calls so far cost, in USD, at spend.PRICES."""
        with self._lock:
            return cost_of(
                sam_images=self._sam_images,
                spark_input_tokens=self._input_tokens,
                spark_output_tokens=self._output_tokens,
            )

    def _add(
        self,
        *,
        images: int = 0,
        tokens: tuple[int, int] = (0, 0),
        estimated: bool = False,
    ) -> None:
        with self._lock:
            self._sam_images += images
            self._input_tokens += tokens[0]
            self._output_tokens += tokens[1]
            self.estimated = self.estimated or estimated


def _maybe_billed(exc: Exception) -> bool:
    """Whether a Meta call that raised `exc` may still have been billed.

    Only Meta's own HTTP error answer, a MetaApiError with a status, wasn't. The
    client's module is loaded by now: its client made the call.
    """
    from lusot_analysis.meta_client import MetaApiError

    return not (isinstance(exc, MetaApiError) and exc.status is not None)


def MetaClient(*, api_key: str) -> meta_client.MetaClient:
    """A new Meta client, its module imported on first use (the cold start).

    It keeps the class's name, so a test can put a recorder in its place.
    """
    from lusot_analysis.meta_client import MetaClient as meta_client_class

    return meta_client_class(api_key=api_key)


def _meta_client() -> meta_client.MetaClient:
    """The Meta client, made from the key in SSM once per process (spec §3.6).

    It is kept only once it is made, so a failed load is tried again by the next
    delivery (C60), and a rejected key drops it (C73). MetaClient refuses a key under
    20 characters. The load logs `model_key_loaded=true`, or `model_key_missing` with
    the error's code: never the key or its length.
    """
    global _META_CLIENT
    if _META_CLIENT is None:
        from lusot_analysis.meta_client import MissingApiKey

        try:
            value = _client("ssm").get_parameter(
                Name=os.environ["MODEL_KEY_PARAM"], WithDecryption=True
            )["Parameter"]["Value"]
            client = MetaClient(api_key=value)
        except (BotoCoreError, ClientError, MissingApiKey) as exc:
            _log(outcome="model_key_missing", **_error_fields(exc))
            raise
        _log(outcome="model_key_loaded=true")
        _META_CLIENT = client
    return _META_CLIENT


@functools.cache
def _prompt() -> PromptSpec:
    """Muse Spark's prompt and schema, read from PROMPTS_DIR once per process (C79).

    The image sets PROMPTS_DIR, as its layout isn't the repo's. A failed read isn't
    cached, so the next delivery tries again.
    """
    return load_prompt(Path(os.environ["PROMPTS_DIR"]))


def _model_calls_switch() -> str:
    """The model-calls stop switch's value, read on every delivery.

    A failed read raises, so the message retries before the claim (C60).
    """
    name = os.environ["STOP_PARAM_PREFIX"] + "model-calls"
    return _client("ssm").get_parameter(Name=name)["Parameter"]["Value"]


def _publish_switch() -> str:
    """The publish stop switch's value, read for each result that could be pinned.

    Uncached, as the model-calls switch is, so a change acts on the next result. It
    comes after the paid run, so it goes through the bounded `_post_run_ssm`.
    """
    name = os.environ["STOP_PARAM_PREFIX"] + "publish"
    return _post_run_ssm().get_parameter(Name=name)["Parameter"]["Value"]


def _spend_stop_usd() -> Decimal:
    """The spend stop in USD, read before each run. Anything but a number raises."""
    value = _client("ssm").get_parameter(Name=SPEND_STOP_PARAM)["Parameter"]["Value"]
    stop = Decimal(value)  # InvalidOperation for text that isn't a number
    if not stop.is_finite():
        raise ValueError("the spend stop isn't a finite number")
    return stop


def _spend_check(line: dict) -> Decimal | None:
    """The stop to hold the run's cost to, or None once model calls are paused.

    Read after the claim and before any Meta call (C527). A total at or over the
    stop, or either of them unreadable (fail closed, as for the switch), sets the
    model-calls switch "on" and adds `spend_stop` to `line`.
    """
    try:
        stop = _spend_stop_usd()
        total = spend_total(ddb=_spend_ddb())
    except Exception as exc:  # noqa: BLE001
        line["spend_stop"] = {"unreadable": _error_fields(exc)}
        _pause_model_calls(line["spend_stop"])
        return None
    if total >= stop:
        line["spend_stop"] = {"total_usd": str(total), "stop_usd": str(stop)}
        _pause_model_calls(line["spend_stop"])
        return None
    return stop


def _record_spend(counted: _CountedClient, stop: Decimal, line: dict) -> None:
    """Add the run's Meta cost to the counter, after the run and before its write.

    The one guard after the paid run: nothing here raises, so no fault in it can
    return the message to claim and pay again (Review Focus 3). A run with nothing
    billed records nothing. A total at or over the stop pauses model calls at once
    (`spend_stop`). A write that still fails after SPEND_CONFIG's retries logs
    `spend_error` with the amount, for docs/operations.md, and fails closed: it
    pauses model calls too, so an unseen gap can't let the stop trip late. The
    handler adds no retries of its own.
    """
    cost = counted.cost()
    if cost == 0:
        return
    if counted.estimated:
        line["spend_estimated"] = True
    try:
        total = record_spend(cost, "analysis", ddb=_spend_ddb())
    except Exception as exc:  # noqa: BLE001
        line["spend_error"] = {"usd": str(rounded_up(cost)), **_error_fields(exc)}
        _pause_model_calls(line["spend_error"])
        return
    if total >= stop:
        line["spend_stop"] = {"total_usd": str(total), "stop_usd": str(stop)}
        _pause_model_calls(line["spend_stop"])


def _pause_model_calls(fields: dict) -> None:
    """Set the model-calls switch "on", so no later run pays (C527).

    Every flip goes through the bounded `_post_run_ssm`, so one after the paid run
    ends inside the run's margin. A failed put adds its error to `fields` as
    `switch`: the line's spend_stop or spend_error still reaches the alarm.
    """
    try:
        _post_run_ssm().put_parameter(
            Name=os.environ["STOP_PARAM_PREFIX"] + "model-calls",
            Value="on",
            Type="String",
            Overwrite=True,
        )
    except Exception as exc:  # noqa: BLE001
        fields["switch"] = _error_fields(exc)


def analyse(
    data: bytes, client: ModelClient, *, deadline: float | None = None
) -> PipelineRun:
    """The handler's pipeline call, with every SAM phrase (B3).

    The face and plate phrases are what the publish blur reads, so a level result gets
    its photo to store (C61). `deadline` is the run's deadline as a time.monotonic()
    value (C84).
    """
    from lusot_analysis.meta_client import SAM_PHRASES
    from lusot_analysis.pipeline import run_pipeline

    return run_pipeline(data, client, _prompt(), phrases=SAM_PHRASES, deadline=deadline)


def handler(event: dict, context: object) -> dict:
    """Handle S3 upload notifications from SQS, reporting failed messages for retry.

    `context` is Lambda's, and its time left sets the run's deadline (C84). The
    dead-letter queue takes a message after 5 receives, and its alarm emails Rene.
    """
    failures = []
    for record in event["Records"]:
        notification = json.loads(record["body"])
        if notification.get("Event") == "s3:TestEvent":  # sent once, when S3 sets it up
            _log(outcome="s3_test_event")
            continue
        handled = [
            _handle_object(
                unquote_plus(s3_record["s3"]["object"]["key"]), record, context
            )
            for s3_record in notification["Records"]
        ]
        if not all(handled):
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}


def _handle_object(key: str, record: dict, context: object) -> bool:
    """Handle one uploaded object and log its one line. Returns False to retry.

    Nothing else from the event is logged: not the uploader's address or principal,
    and not the message's receipt handle or queue (spec §3.6).
    """
    started = time.monotonic()
    match = _RAW_KEY.fullmatch(key)
    line: dict[str, object] = {"reportId": match.group(1)} if match else {}
    try:
        if match is None:  # not a key the API hands out
            _delete(key)
            line["outcome"] = "unknown_key"
        else:
            line["outcome"] = _process(match.group(1), key, context, line)
    except ReportNotFound as exc:
        # The index can lag the table, so the message retries, in 10 s (R92).
        line.update(outcome="error", **_error_fields(exc), **_retry_soon(record))
    except Exception as exc:  # noqa: BLE001
        # Any other failure retries the message. It is logged by code and status only.
        line.update(outcome="error", **_error_fields(exc))
    _log(**line, ms=round((time.monotonic() - started) * 1000))
    return line["outcome"] not in _RETRY_OUTCOMES


def _process(report_id: str, key: str, context: object, line: dict) -> str:
    """Run spec §3.1's steps 2 to 8 for one report, and return its outcome.

    Each step adds its other log fields to `line` as it runs, so an AWS error after
    the pipeline still logs the pipeline's fields, the paid calls among them.
    """
    global _META_CLIENT
    from lusot_analysis.pipeline.types import ModelKeyRejected, Outcome

    report = _find_report(report_id)
    # Step 3, before the claim: if any load fails, the message retries and the report
    # stays untouched (C60, C79).
    client = _meta_client()
    _prompt()
    switch = _model_calls_switch()

    # Step 4: the claim, before any Meta call (G2, C46). Neither a finished report nor
    # another worker's live lease is paid for again.
    token = uuid.uuid4().hex  # new for every delivery (C82)
    state = claim(
        _client("dynamodb"),
        os.environ["TABLE_NAME"],
        _item_key(report),
        token,
        _now_s(),
    )
    if state == "finished":  # a retried delete, or a reused upload link
        _delete(key)
        return "already_finished"
    if state == "leased":
        # Another worker holds a live lease, and deletes raw/ when it's done. The
        # message returns with the queue's own visibility timeout, not R92's 10 s:
        # its copy comes back once the report is final or the lease has expired (C89).
        return "lease_held"
    # An earlier attempt may have saved its level's photo and overlay and then failed
    # its write. Every attempt starts with none, so only a written level keeps them
    # (C72).
    for stored in _photo_keys(report):
        _delete(stored)

    # Step 5: only an explicit "off" lets model calls through (C60), and only below the
    # spend stop (C527).
    if switch != "off":
        paused = Outcome.failed("model_calls_paused")
        return _finish(report, key, token, paused, line=line)
    stop = _spend_check(line)
    if stop is None:
        paused = Outcome.failed("model_calls_paused")
        return _finish(report, key, token, paused, line=line)

    # Step 6: the raw photo.
    try:
        data = (
            _client("s3")
            .get_object(Bucket=os.environ["BUCKET_NAME"], Key=key)["Body"]
            .read()
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in _MISSING_PHOTO_CODES:
            raise
        line.update(_error_fields(exc))  # a retry can't bring the photo back
        return _finish(report, key, token, Outcome.failed("photo_missing"), line=line)
    if not data.startswith(_JPEG_MAGIC):  # before any decoder sees it (C83)
        return _finish(report, key, token, Outcome.failed("bad_file"), line=line)

    # Step 7: the pipeline, its Meta calls counted (C527).
    counted = _CountedClient(client)
    try:
        run = analyse(data, counted, deadline=_deadline(context))
    except ModelKeyRejected as exc:
        # The key or the account, not the photo (C73). The report stays processing
        # until a redelivery claims it again, and that delivery reads the key again.
        _META_CLIENT = None
        line["meta_status"] = exc.status
        return "model_key_rejected"
    finally:
        # However the run ends, before its final write or its error return, so a
        # retried message's paid attempt is counted too.
        _record_spend(counted, stop, line)
    line.update(run.log)

    # Step 8: publish.
    return _finish(report, key, token, run.outcome, run.publish_jpeg, line)


def _find_report(report_id: str) -> dict:
    items = _client("dynamodb").query(
        TableName=os.environ["TABLE_NAME"],
        IndexName=_INDEX_NAME,
        KeyConditionExpression="reportId = :id",
        ExpressionAttributeValues={":id": {"S": report_id}},
    )["Items"]
    if not items:
        raise ReportNotFound
    return items[0]


def _finish(
    report: dict,
    key: str,
    token: str,
    outcome: Outcome,
    photo: bytes | None = None,
    line: dict | None = None,
) -> str:
    """Store the photo, if any, write the result, then delete the raw photo (spec §3.2).

    It returns the outcome to log. `photo` comes with a level result only (C61), and
    it is stored before the write, so a level is never written without its photo. The
    write carries the publish fields, if any, and errors join `line`, the report's
    one log line. The write is under the claim: a lost lease writes nothing and
    leaves the raw photo to the worker that holds the report. If the delete fails,
    the message returns, and the retry finds the report finished and only deletes.
    """
    fields = outcome.item_fields()
    if photo is not None:
        photo_key = _photo_keys(report)[0]
        _client("s3").put_object(
            Bucket=os.environ["BUCKET_NAME"],
            Key=photo_key,
            Body=photo,
            ContentType="image/jpeg",
        )
        fields["photoKey"] = photo_key
    fields |= _publish_fields(report, outcome, {} if line is None else line)
    written = write_result(
        _client("dynamodb"), os.environ["TABLE_NAME"], _item_key(report), token, fields
    )
    if not written:
        return "lease_lost"
    _delete(key)
    return outcome.log_name


def _publish_fields(report: dict, outcome: Outcome, line: dict) -> dict:
    """The fields that pin a live or demo level, or none (C516).

    The mode is the item's, never the event's. Only a level in a mode that pins
    reads the publish switch: once, after the pipeline and before the write. Only an
    explicit "off" lets it publish, as with the model-calls switch. The result is
    already paid for, so a failed read writes it unpublished, never retried, and adds
    the error's code and status to `line` as `publish_switch` (Review Focus 3).
    """
    mode = report["mode"]["S"]
    if outcome.level is None or mode not in _PUBLISHED_MODES:
        return {}
    try:
        switch = _publish_switch()
    except Exception as exc:  # noqa: BLE001
        line["publish_switch"] = _error_fields(exc)
        return {}
    if switch != "off":
        return {}
    return {"published": True, "feedPart": mode}


def _retry_soon(record: dict) -> dict:
    """Make the message visible again in 10 s, not the queue's 1,080 s (R92).

    A report the index doesn't show yet then retries within the app's 120 s poll. The
    queue URL is built from the record's ARN, so the role needs no sqs:GetQueueUrl,
    and neither the URL nor the receipt handle is logged. A failure returns its error
    fields to log, and the message still retries, at the queue's own timeout.
    """
    try:
        _client("sqs").change_message_visibility(
            QueueUrl=_queue_url(record["eventSourceARN"]),
            ReceiptHandle=record["receiptHandle"],
            VisibilityTimeout=_NOT_FOUND_VISIBILITY_S,
        )
    except Exception as exc:  # noqa: BLE001
        return {"visibility": _error_fields(exc)}
    return {}


def _queue_url(arn: str) -> str:
    """A queue's URL from its ARN, arn:aws:sqs:<region>:<account>:<name>."""
    _, _, _, region, account, name = arn.split(":")
    return f"https://sqs.{region}.amazonaws.com/{account}/{name}"


def _deadline(context: object) -> float | None:
    """The run's deadline on time.monotonic(): Lambda's time left less 30 s (C84).

    The margin leaves time for the publish blur and the writes (C88). None when
    `context` can't tell the time left, as when tests pass None.
    """
    remaining_ms = getattr(context, "get_remaining_time_in_millis", None)
    if remaining_ms is None:
        return None
    return time.monotonic() + remaining_ms() / 1000 - DEADLINE_MARGIN_S


def _now_s() -> int:
    """The claim's clock, in whole seconds since the epoch. Tests fix it."""
    return int(time.time())


def _item_key(report: dict) -> dict:
    return {"pk": report["pk"], "sk": report["sk"]}


def _photo_keys(report: dict) -> tuple[str, str, str]:
    """The report's stored photo and its overlay's image and JSON (C510).

    A demo report's go under demo/, which has its own 60-day backstop.
    """
    report_id = report["reportId"]["S"]
    prefix = "demo/" if report["mode"]["S"] == "demo" else ""
    return (
        f"{prefix}blurred/{report_id}.jpg",
        f"{prefix}overlay/{report_id}.jpg",
        f"{prefix}overlay/{report_id}.json",
    )


def _delete(key: str) -> None:
    _client("s3").delete_object(Bucket=os.environ["BUCKET_NAME"], Key=key)
