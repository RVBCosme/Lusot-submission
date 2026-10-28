"""The MS1 analysis Lambda: a stub until the pipeline exists (C28).

It proves the wiring: the queue, the model-calls stop switch, OpenCV and YuNet in the
container, and the Meta key in SSM. It calls no model, and it stores no photo, because
plates can't be blurred until SAM runs (MS3). Every report ends `failed` with a reason,
and the raw photo is deleted.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import re
import time
from urllib.parse import unquote_plus

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from lusot_analysis.face_blur import UndecodableImage, blur_for_meta

_INDEX_NAME = "reportId-index"
_RAW_KEY = re.compile(r"raw/(r_[0-9a-f]{32})\.jpg")  # the key the API signs (C32)
_MIN_KEY_LENGTH = 20  # the real key has 48 characters (spec A8), the stale shell copy 1

logger = logging.getLogger("lusot.analysis")
logger.setLevel(logging.INFO)  # Lambda's text log format otherwise drops INFO


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
            "status": exc.response["ResponseMetadata"]["HTTPStatusCode"],
        }
    return {"error": type(exc).__name__}


@functools.cache
def _client(service: str):
    """One client per service and process, made on first use."""
    return boto3.client(service)


@functools.cache
def _check_model_key() -> None:
    """Read the Meta key once per cold start and check only its length (C28).

    It proves the SSM and KMS wiring. Neither the key nor its length is logged, and a
    missing key doesn't stop processing, since the stub calls no model.
    """
    try:
        value = _client("ssm").get_parameter(
            Name=os.environ["MODEL_KEY_PARAM"], WithDecryption=True
        )["Parameter"]["Value"]
    except (BotoCoreError, ClientError) as exc:
        _log(outcome="model_key_missing", **_error_fields(exc))
        return
    loaded = len(value) >= _MIN_KEY_LENGTH
    _log(outcome="model_key_loaded=true" if loaded else "model_key_missing")


def handler(event: dict, context: object) -> dict:
    """Handle S3 upload notifications from SQS, reporting failed messages for retry.

    The dead-letter queue takes a message after 5 receives, and its alarm emails Rene.
    """
    _check_model_key()
    failures = []
    for record in event["Records"]:
        notification = json.loads(record["body"])
        if notification.get("Event") == "s3:TestEvent":  # sent once, when S3 sets it up
            _log(outcome="s3_test_event")
            continue
        handled = [
            _handle_object(unquote_plus(s3_record["s3"]["object"]["key"]))
            for s3_record in notification["Records"]
        ]
        if not all(handled):
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}


def _handle_object(key: str) -> bool:
    """Handle one uploaded object and log its outcome. Returns False to retry."""
    started = time.monotonic()
    match = _RAW_KEY.fullmatch(key)
    line = {"reportId": match.group(1)} if match else {}
    try:
        if match is None:  # not a key the API hands out
            _delete(key)
            line["outcome"] = "unknown_key"
        else:
            line.update(_process(match.group(1), key))
    except Exception as exc:  # noqa: BLE001
        # Any failure retries the message. It is logged by code and status only.
        line.update(outcome="error", **_error_fields(exc))
    _log(**line, ms=round((time.monotonic() - started) * 1000))
    return line["outcome"] != "error"


def _process(report_id: str, key: str) -> dict:
    """Run the stub for one report and return its log fields."""
    report = _find_report(report_id)
    if report["status"]["S"] != "pending":  # a duplicate event, or a retried delete
        _delete(key)
        return {"outcome": "already_finished"}
    if _model_calls_stopped():
        return _finish(report, key, "model_calls_paused")
    try:
        data = (
            _client("s3")
            .get_object(Bucket=os.environ["BUCKET_NAME"], Key=key)["Body"]
            .read()
        )
    except ClientError as exc:
        # The role can't list the bucket, so a missing photo reads as 403, not 404.
        # A retry can't bring it back.
        if exc.response["ResponseMetadata"]["HTTPStatusCode"] not in (403, 404):
            raise
        return {"outcome": _mark_failed(report, "photo_missing"), **_error_fields(exc)}
    try:
        # Downscales before detection (R16). Only the face-box count is kept.
        faces = blur_for_meta(data).faces
    except UndecodableImage:
        return _finish(report, key, "bad_file")
    return {**_finish(report, key, "pipeline_not_built"), "face_boxes": faces}


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


def _model_calls_stopped() -> bool:
    # Only an explicit "off" lets model calls through, as with the API's uploads switch.
    # A failed read raises, so the message is retried rather than processed.
    name = os.environ["STOP_PARAM_PREFIX"] + "model-calls"
    return _client("ssm").get_parameter(Name=name)["Parameter"]["Value"] != "off"


def _finish(report: dict, key: str, reason: str) -> dict:
    """Mark the report failed, then delete the raw photo.

    If the delete fails, the retry finds the report finished and only deletes.
    """
    outcome = _mark_failed(report, reason)
    _delete(key)
    return {"outcome": outcome}


def _mark_failed(report: dict, reason: str) -> str:
    """Mark the report failed if it is still pending, and return the outcome."""
    try:
        _client("dynamodb").update_item(
            TableName=os.environ["TABLE_NAME"],
            Key={"pk": report["pk"], "sk": report["sk"]},
            UpdateExpression="SET #status = :failed, refusalReason = :reason",
            ConditionExpression="#status = :pending",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":failed": {"S": "failed"},
                ":reason": {"S": reason},
                ":pending": {"S": "pending"},
            },
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        return "already_finished"  # another delivery of the event finished it first
    return reason


def _delete(key: str) -> None:
    _client("s3").delete_object(Bucket=os.environ["BUCKET_NAME"], Key=key)
