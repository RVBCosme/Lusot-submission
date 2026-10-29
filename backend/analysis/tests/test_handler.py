"""Tests for the analysis Lambda's handler (spec §3.1, §3.6), against moto's AWS.

The handler's Meta client is a FakeClient on the level case, so no Meta call is made.
The key tests load the key from SSM through the handler's own loader, with MetaClient
replaced by a recorder. A guard fails any test that builds a real MetaClient by
accident.
"""

import dataclasses
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote_plus

import boto3
import cv2
import numpy as np
import pytest
from botocore.exceptions import ClientError, ReadTimeoutError
from fakes import (
    REPO_PROMPTS,
    FakeClient,
    answer,
    create_reports_table,
    flat_jpeg,
    level_case,
    meta_error,
)
from moto import mock_aws

from lusot_analysis import handler
from lusot_analysis.face_blur import blur_for_meta, decode_image
from lusot_analysis.meta_client import SAM_PHRASES, MetaClient
from lusot_analysis.pipeline.publish import publish_jpeg
from lusot_analysis.pipeline.saved import SavedOutputsClient

BUCKET = "lusot-test-uploads"
TABLE = "lusot-test-reports"
KEY_PARAM = "/lusot/meta/model-api-key"
SWITCH = "/lusot/stop/model-calls"
PUBLISH = "/lusot/stop/publish"
FAKE_KEY = "fake-model-key-" + "0" * 33  # 48 characters, like the real key (spec A8)
REPORT_ID = "r_" + "0123456789abcdef" * 2
RAW_KEY = f"raw/{REPORT_ID}.jpg"
PHOTO_KEY = f"blurred/{REPORT_ID}.jpg"
# What a level stores: its photo, and its overlay's image and JSON (C510).
STORED_KEYS = [PHOTO_KEY, f"overlay/{REPORT_ID}.jpg", f"overlay/{REPORT_ID}.json"]
PUBLISHED_FIELDS = ("published", "feedPart")
CAPTURED_AT = "2026-10-28T03:00:00.000Z"
NOW_S = 1_800_000_000  # the claim's clock, fixed in every test
# A pending live report as the API writes it (Table 14 subset), at the plan §12 spot.
ITEM = {
    "pk": {"S": "GEO#wdw515"},
    "sk": {"S": f"{CAPTURED_AT}#{REPORT_ID}"},
    "reportId": {"S": REPORT_ID},
    "mode": {"S": "live"},
    "status": {"S": "pending"},
    "lat": {"N": "14.6095"},
    "lng": {"N": "120.9894"},
    "capturedAt": {"S": CAPTURED_AT},
}
KEY = {"pk": ITEM["pk"], "sk": ITEM["sk"]}
# The level case's result as stored: knee from wheel 2, with its photo (C61), and
# published, as a live level is while the publish switch is "off".
KNEE = {
    "noFloodSeen": {"BOOL": False},
    "level": {"S": "knee"},
    "landmark": {"S": "rim_three_quarters"},
    "passability": {"S": "NPLV"},
    "levelIsFloor": {"BOOL": False},
    "basis": {"M": {"vehicles": {"N": "1"}, "people": {"N": "0"}}},
    "photoKey": {"S": PHOTO_KEY},
    "published": {"BOOL": True},
    "feedPart": {"S": "live"},
}
# The same result written unpublished.
KNEE_UNPUBLISHED = {
    name: value for name, value in KNEE.items() if name not in PUBLISHED_FIELDS
}
LEVEL_PHOTO = level_case()[0]
REASON = "REASON-MARKER-31"  # the reason fakes.answer gives every answer
# What the event carries besides the key: the uploader's address and principal from
# S3, and the receipt handle and queue from SQS. None of it may reach a log (§3.6).
SOURCE_IP = "203.0.113.7"  # TEST-NET-3 (RFC 5737)
PRINCIPAL = "AWS:AROAPRINCIPALMARKER:lusot-api"
RECEIPT = "receipt-handle-marker"
QUEUE_ARN = "arn:aws:sqs:ap-southeast-1:account-id:lusot-queue"
QUEUE_URL = "https://sqs.ap-southeast-1.amazonaws.com/account-id/lusot-queue"
RUNNER = Path(__file__).parents[1] / "probes" / "run_pipeline.py"


def load_runner():
    """The offline runner, loaded from its file: it isn't a package module."""
    spec = importlib.util.spec_from_file_location("run_pipeline_script", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def no_meta_client(**kwargs):
    raise AssertionError("a test built a real Meta client")


@pytest.fixture
def prompts(monkeypatch):
    """The repo's prompts as PROMPTS_DIR, read fresh by the test."""
    monkeypatch.setenv("PROMPTS_DIR", str(REPO_PROMPTS))
    handler._prompt.cache_clear()
    yield
    handler._prompt.cache_clear()


@pytest.fixture
def aws(monkeypatch, prompts):
    """Moto's S3, DynamoDB and SSM, set up as the template sets up the real ones.

    Each test starts cold: new AWS clients inside the mock, no Meta client, and the
    prompt not yet read. The claim's clock reads NOW_S.
    """
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(name, "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-southeast-1")
    monkeypatch.setenv("TABLE_NAME", TABLE)
    monkeypatch.setenv("BUCKET_NAME", BUCKET)
    monkeypatch.setenv("STOP_PARAM_PREFIX", "/lusot/stop/")
    monkeypatch.setenv("MODEL_KEY_PARAM", KEY_PARAM)
    monkeypatch.setattr(handler, "_META_CLIENT", None)
    monkeypatch.setattr(handler, "MetaClient", no_meta_client)
    monkeypatch.setattr(handler, "_now_s", lambda: NOW_S)
    handler._client.cache_clear()
    handler._post_run_ssm.cache_clear()
    with mock_aws():
        s3, ddb, ssm = (boto3.client(name) for name in ("s3", "dynamodb", "ssm"))
        s3.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
        )
        create_reports_table(ddb, TABLE)
        ssm.put_parameter(Name=SWITCH, Value="off", Type="String")
        ssm.put_parameter(Name=PUBLISH, Value="off", Type="String")
        ssm.put_parameter(Name=KEY_PARAM, Value=FAKE_KEY, Type="SecureString")
        yield SimpleNamespace(s3=s3, ddb=ddb, ssm=ssm)
    # Their clients belong to the mock that just ended.
    handler._client.cache_clear()
    handler._post_run_ssm.cache_clear()


@pytest.fixture
def fake(aws, monkeypatch) -> FakeClient:
    """The level case's FakeClient as the handler's Meta client.

    A test may change its answer or hooks before the delivery.
    """
    _, sam, given = level_case()
    client = FakeClient(sam, given)
    monkeypatch.setattr(handler, "_meta_client", lambda: client)
    return client


def aws_error(code: str, status: int, operation: str) -> ClientError:
    """An AWS error whose message holds an ARN, as AccessDenied messages do."""
    message = (
        "User: arn:aws:sts::account-id:assumed-role/lusot-role/session"
        " is not authorized to perform this action"
    )
    return ClientError(
        {
            "Error": {"Code": code, "Message": message},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        operation,
    )


def seed(aws, photo: bytes | None = None, **attributes: dict) -> dict:
    """Write the report with `attributes` replacing its own, and its raw photo.

    Returns the item as written.
    """
    item = ITEM | attributes
    aws.ddb.put_item(TableName=TABLE, Item=item)
    if photo is not None:
        aws.s3.put_object(Bucket=BUCKET, Key=RAW_KEY, Body=photo)
    return item


def claimed(token: str, claimed_at: int, status: str = "processing") -> dict:
    """A claim's attributes as stored, with the report's status."""
    return {
        "status": {"S": status},
        "claimToken": {"S": token},
        "claimedAt": {"N": str(claimed_at)},
    }


def report(aws) -> dict:
    return aws.ddb.get_item(TableName=TABLE, Key=KEY)["Item"]


def status(aws) -> tuple[str, str | None]:
    item = report(aws)
    return item["status"]["S"], item.get("refusalReason", {}).get("S")


def keys(aws) -> list[str]:
    return [
        obj["Key"] for obj in aws.s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])
    ]


def published(aws) -> dict:
    """The report's `published` and `feedPart`, those it has."""
    item = report(aws)
    return {name: item[name] for name in PUBLISHED_FIELDS if name in item}


def result(aws) -> tuple[str, str | None]:
    """The report's status, with its level or its reason when it has one."""
    item = report(aws)
    detail = item.get("level", item.get("refusalReason", {}))
    return item["status"]["S"], detail.get("S")


def message(key: str = RAW_KEY) -> dict:
    """An SQS batch of one S3 notification, as Lambda delivers it.

    The key is URL-encoded as S3 sends it. The S3 record carries the uploader's
    address and principal, and the SQS record its receipt handle and queue ARN, as
    real events do.
    """
    body = {
        "Records": [
            {
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Post",
                "userIdentity": {"principalId": PRINCIPAL},
                "requestParameters": {"sourceIPAddress": SOURCE_IP},
                "s3": {
                    "bucket": {"name": BUCKET},
                    "object": {"key": quote_plus(key, safe="/"), "size": 1},
                },
            }
        ]
    }
    return {
        "Records": [
            {
                "messageId": "m-1",
                "receiptHandle": RECEIPT,
                "body": json.dumps(body),
                "eventSource": "aws:sqs",
                "eventSourceARN": QUEUE_ARN,
            }
        ]
    }


def logged(caplog) -> list[dict]:
    return [
        json.loads(r.getMessage()) for r in caplog.records if r.name == "lusot.analysis"
    ]


def report_lines(caplog) -> list[dict]:
    return [line for line in logged(caplog) if line.get("reportId") == REPORT_ID]


def outcomes(caplog) -> list[str]:
    """The outcome of each line logged for the report, in order."""
    return [line["outcome"] for line in report_lines(caplog)]


def key_lines(caplog) -> list[dict]:
    """The lines the key load logs."""
    return [line for line in logged(caplog) if line["outcome"].startswith("model_key")]


def calls(client: FakeClient, method: str) -> list[str]:
    """The phrase or schema name of each `method` call the fake recorded."""
    return [name for kind, name, _ in client.calls if kind == method]


def record_meta_clients(monkeypatch, client: FakeClient) -> list[bool]:
    """Put a recorder in place of MetaClient that returns `client`.

    Returns one entry per client built: whether it got the stored key. The key itself
    isn't kept, so no failed assertion can print it.
    """
    built = []

    def build(*, api_key: str) -> FakeClient:
        built.append(api_key == FAKE_KEY)
        return client

    monkeypatch.setattr(handler, "MetaClient", build)
    return built


def spy_parameters(monkeypatch, failing: set[str]) -> list[dict]:
    """Record each SSM read the handler makes, by its keywords, in order.

    It covers both of the handler's SSM clients: the shared one, and the bounded one
    for the reads after the paid run. A read of a name in `failing` raises
    InternalServerError. The test may change `failing` between deliveries.
    """
    reads = []

    def spy_on(ssm) -> None:
        get_parameter = ssm.get_parameter

        def spy(**kwargs):
            reads.append(kwargs)
            if kwargs["Name"] in failing:
                raise aws_error("InternalServerError", 500, "GetParameter")
            return get_parameter(**kwargs)

        monkeypatch.setattr(ssm, "get_parameter", spy)

    spy_on(handler._client("ssm"))
    spy_on(handler._post_run_ssm())
    return reads


def fail_deletes(monkeypatch, key: str, times: int = 1) -> None:
    """The handler's next `times` deletes of `key` raise InternalError."""
    s3 = handler._client("s3")
    delete_object = s3.delete_object
    left = [times]

    def delete(**kwargs):
        if kwargs["Key"] == key and left[0] > 0:
            left[0] -= 1
            raise aws_error("InternalError", 500, "DeleteObject")
        return delete_object(**kwargs)

    monkeypatch.setattr(s3, "delete_object", delete)


def spy_visibility(monkeypatch, error: Exception | None = None) -> list[dict]:
    """Record each ChangeMessageVisibility the handler sends, raising `error` if set.

    No queue exists at that URL: the call is checked, not made.
    """
    changes = []

    def change_message_visibility(**kwargs):
        changes.append(kwargs)
        if error is not None:
            raise error

    sqs = handler._client("sqs")
    monkeypatch.setattr(sqs, "change_message_visibility", change_message_visibility)
    return changes


NO_FAILURES = {"batchItemFailures": []}
RETRY = {"batchItemFailures": [{"itemIdentifier": "m-1"}]}


# Kept from MS1


def test_s3_test_event_is_ignored(aws, caplog):
    before = seed(aws, photo=LEVEL_PHOTO)
    body = {
        "Service": "Amazon S3",
        "Event": "s3:TestEvent",
        "Time": CAPTURED_AT,
        "Bucket": BUCKET,
        "RequestId": "TEST",
        "HostId": "TEST",
    }
    event = {"Records": [{"messageId": "m-1", "body": json.dumps(body)}]}
    assert handler.handler(event, None) == NO_FAILURES
    assert report(aws) == before
    assert keys(aws) == [RAW_KEY]
    assert [line["outcome"] for line in logged(caplog)] == ["s3_test_event"]


@pytest.mark.parametrize("key", ["raw/whatever.png", "raw/what ever.png"])
def test_unknown_key_is_deleted_and_skipped(aws, caplog, key):
    aws.s3.put_object(Bucket=BUCKET, Key=key, Body=b"junk")
    assert handler.handler(message(key), None) == NO_FAILURES
    assert keys(aws) == []
    assert [line["outcome"] for line in logged(caplog)] == ["unknown_key"]


def test_report_not_found_is_retried(aws, fake, monkeypatch, caplog):
    # The index can lag the table, so the photo waits for the retry. The retry comes
    # 10 s later, not after the queue's 1,080 s, so the app's 120 s poll sees it (R92).
    aws.s3.put_object(Bucket=BUCKET, Key=RAW_KEY, Body=LEVEL_PHOTO)
    changes = spy_visibility(monkeypatch)
    assert handler.handler(message(), None) == RETRY
    # The queue URL is built from the record's ARN: no sqs:GetQueueUrl is needed.
    assert changes == [
        {"QueueUrl": QUEUE_URL, "ReceiptHandle": RECEIPT, "VisibilityTimeout": 10}
    ]
    assert keys(aws) == [RAW_KEY]
    assert fake.calls == []
    # A failed change is logged by its code, and the message still retries, at the
    # queue's own visibility timeout.
    error = aws_error("AccessDenied", 403, "ChangeMessageVisibility")
    failed = spy_visibility(monkeypatch, error)
    assert handler.handler(message(), None) == RETRY
    assert len(failed) == 1
    lines = report_lines(caplog)
    assert all(line.pop("ms") >= 0 for line in lines)
    not_found = {"reportId": REPORT_ID, "outcome": "error", "error": "ReportNotFound"}
    assert lines == [
        not_found,
        not_found | {"visibility": {"error": "AccessDenied", "http_status": 403}},
    ]
    for private in (QUEUE_URL, RECEIPT, "account-id", "arn:"):
        assert private not in caplog.text


def test_undecodable_file_marks_bad_file(aws, fake, caplog):
    # JPEG's first bytes, then nothing a decoder can read. C83's check passes it, and
    # the pipeline's face blur refuses it before any Meta call.
    seed(aws, photo=b"\xff\xd8\xff" + b"not a jpeg")
    assert handler.handler(message(), None) == NO_FAILURES
    assert status(aws) == ("failed", "bad_file")
    assert keys(aws) == []
    assert fake.calls == []
    (line,) = report_lines(caplog)
    assert (line["outcome"], line["meta_calls"]) == ("failed/bad_file", 0)


def test_aws_error_is_logged_by_code_and_http_status_only(
    aws, fake, monkeypatch, caplog
):
    seed(aws, photo=LEVEL_PHOTO)

    def query(**kwargs):
        raise aws_error("AccessDeniedException", 400, "Query")

    monkeypatch.setattr(handler._client("dynamodb"), "query", query)
    assert handler.handler(message(), None) == RETRY
    assert "arn:" not in caplog.text
    (line,) = report_lines(caplog)
    assert line.pop("ms") >= 0
    assert line == {
        "reportId": REPORT_ID,
        "outcome": "error",
        "error": "AccessDeniedException",
        "http_status": 400,
    }


# Results


def test_level_result_is_published(aws, fake):
    _, sam, _ = level_case()
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(message(), None) == NO_FAILURES
    item = report(aws)
    token = item["claimToken"]["S"]
    assert re.fullmatch(r"[0-9a-f]{32}", token)  # new for every delivery (C82)
    assert item == ITEM | claimed(token, NOW_S, status="done") | KNEE
    # The stored photo is the face-blurred one with SAM's faces and plates blurred
    # (C48, C61), and the raw photo is gone (W25).
    assert keys(aws) == [PHOTO_KEY]
    stored = aws.s3.get_object(Bucket=BUCKET, Key=PHOTO_KEY)
    assert stored["ContentType"] == "image/jpeg"
    data = stored["Body"].read()
    assert decode_image(data).shape[:2] == (480, 640)
    assert data == publish_jpeg(blur_for_meta(LEVEL_PHOTO), sam)
    # Every SAM phrase and one Muse Spark answer: 7 + 1 calls.
    assert sorted(calls(fake, "segment")) == sorted(SAM_PHRASES)
    assert len(calls(fake, "judge")) == 1


@pytest.mark.parametrize(
    ("photo", "judged", "result"),
    [
        pytest.param(
            LEVEL_PHOTO,
            answer(standing_water="no"),
            ("done", {"noFloodSeen": {"BOOL": True}}),
            id="no-flood-seen",
        ),
        pytest.param(
            flat_jpeg(10),
            None,
            ("refused", {"refusalReason": {"S": "too_dark"}}),
            id="too-dark",
        ),
        pytest.param(
            LEVEL_PHOTO,
            answer(photo_usable="no"),
            ("refused", {"refusalReason": {"S": "photo_unusable"}}),
            id="photo-unusable",
        ),
        pytest.param(
            LEVEL_PHOTO,
            meta_error(500),
            ("failed", {"refusalReason": {"S": "model_error"}}),
            id="model-error",
        ),
    ],
)
def test_non_level_results_store_no_photo(aws, fake, photo, judged, result):
    if judged is not None:
        fake.answer = judged
    seed(aws, photo=photo)
    assert handler.handler(message(), None) == NO_FAILURES
    item = report(aws)
    final, fields = result
    assert item == ITEM | claimed(item["claimToken"]["S"], NOW_S, final) | fields
    assert keys(aws) == []  # no blurred/ photo (C61), and no raw/ left (W25)


def test_deadline_comes_from_the_lambda_context(aws, fake):
    seed(aws, photo=LEVEL_PHOTO)
    context = SimpleNamespace(get_remaining_time_in_millis=lambda: 100_000)
    before = time.monotonic()
    assert handler.handler(message(), context) == NO_FAILURES
    after = time.monotonic()
    # The Lambda's time left less 30 s, read as the run starts (C84, C88).
    (deadline,) = {keywords["deadline"] for keywords in fake.keywords}
    assert before + 70 <= deadline <= after + 70
    # With no context, as in the other tests, the run has no deadline.
    seed(aws, photo=LEVEL_PHOTO)  # a new pending report
    fake.keywords.clear()
    assert handler.handler(message(), None) == NO_FAILURES
    assert [keywords["deadline"] for keywords in fake.keywords] == [None] * 8


def test_publish_switch_is_read_once_after_the_result(aws, fake, monkeypatch):
    # C516 replaces 3a's C64: the switch acts at write time. It is read once, after
    # the paid result and before its write, and while set it leaves the level
    # unpublished, with its photo.
    aws.ssm.put_parameter(Name=PUBLISH, Value="on", Type="String", Overwrite=True)
    reads = spy_parameters(monkeypatch, set())
    at_judge = []
    fake.on_judge = lambda: at_judge.append([read["Name"] for read in reads])
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(message(), None) == NO_FAILURES
    item = report(aws)
    token = item["claimToken"]["S"]
    assert item == ITEM | claimed(token, NOW_S, "done") | KNEE_UNPUBLISHED
    assert keys(aws) == [PHOTO_KEY]
    assert [read["Name"] for read in reads] == [SWITCH, PUBLISH]
    assert at_judge == [[SWITCH]]  # so the publish read came after the judge call


@pytest.mark.parametrize(
    ("switch", "expected"),
    [("off", ("done", None)), ("on", ("failed", "model_calls_paused"))],
    ids=["no-flood-seen", "model-calls-paused"],
)
def test_stale_photo_is_removed_after_the_claim(aws, fake, switch, expected):
    # An earlier attempt saved its level's photo and overlay and then failed its
    # write, and its lease has expired. Every attempt starts with none of them (C72).
    fake.answer = answer(standing_water="no")
    aws.ssm.put_parameter(Name=SWITCH, Value=switch, Type="String", Overwrite=True)
    seed(aws, photo=LEVEL_PHOTO, **claimed("old", NOW_S - 901))
    for key in STORED_KEYS:
        aws.s3.put_object(Bucket=BUCKET, Key=key, Body=b"a stale level object")
    assert handler.handler(message(), None) == NO_FAILURES
    assert status(aws) == expected
    assert "photoKey" not in report(aws)
    assert keys(aws) == []


@pytest.mark.parametrize("stored", STORED_KEYS)
def test_failed_photo_cleanup_retries_before_paying(aws, fake, monkeypatch, stored):
    # C72: the cleanup of each stored key runs before any Meta call, so its failure
    # costs nothing.
    seed(aws, photo=LEVEL_PHOTO)
    fail_deletes(monkeypatch, stored)
    assert handler.handler(message(), None) == RETRY
    assert status(aws) == ("processing", None)
    assert keys(aws) == [RAW_KEY]
    assert fake.calls == []


# Storage and publishing by mode (C510, C516)


@pytest.mark.parametrize(
    ("mode", "prefix"),
    [
        ("live", ""),
        ("private", ""),
        ("sample", ""),
        ("eval", ""),
        ("demo", "demo/"),
    ],
)
def test_keys_by_mode(mode, prefix):
    item = ITEM | {"mode": {"S": mode}}
    assert handler._photo_keys(item) == (
        f"{prefix}blurred/{REPORT_ID}.jpg",
        f"{prefix}overlay/{REPORT_ID}.jpg",
        f"{prefix}overlay/{REPORT_ID}.json",
    )


KNEE_RESULT = ("done", "knee")  # the level case's result, as `result` reads it


@pytest.mark.parametrize(
    ("mode", "photo", "judged", "before", "during", "final", "read", "pinned"),
    [
        pytest.param(
            "live", LEVEL_PHOTO, None, "off", None, KNEE_RESULT, True, True, id="live"
        ),
        pytest.param(
            "demo", LEVEL_PHOTO, None, "off", None, KNEE_RESULT, True, True, id="demo"
        ),
        pytest.param(
            "private",
            LEVEL_PHOTO,
            None,
            "off",
            None,
            KNEE_RESULT,
            False,
            False,
            id="private",
        ),
        pytest.param(
            "sample",
            LEVEL_PHOTO,
            None,
            "off",
            None,
            KNEE_RESULT,
            False,
            False,
            id="sample",
        ),
        pytest.param(
            "eval", LEVEL_PHOTO, None, "off", None, KNEE_RESULT, False, False, id="eval"
        ),
        pytest.param(
            "live",
            LEVEL_PHOTO,
            answer(standing_water="no"),
            "off",
            None,
            ("done", None),
            False,
            False,
            id="live-no-flood-seen",
        ),
        pytest.param(
            "live",
            flat_jpeg(10),
            None,
            "off",
            None,
            ("refused", "too_dark"),
            False,
            False,
            id="live-refusal",
        ),
        pytest.param(
            "live",
            LEVEL_PHOTO,
            meta_error(500),
            "off",
            None,
            ("failed", "model_error"),
            False,
            False,
            id="live-failure",
        ),
        pytest.param(
            "live",
            LEVEL_PHOTO,
            None,
            "on",
            None,
            KNEE_RESULT,
            True,
            False,
            id="publish-on",
        ),
        # None: the publish read raises.
        pytest.param(
            "live",
            LEVEL_PHOTO,
            None,
            None,
            None,
            KNEE_RESULT,
            True,
            False,
            id="publish-unreadable",
        ),
        pytest.param(
            "live",
            LEVEL_PHOTO,
            None,
            "off",
            "on",
            KNEE_RESULT,
            True,
            False,
            id="set-mid-run",
        ),
        pytest.param(
            "live",
            LEVEL_PHOTO,
            None,
            "on",
            "off",
            KNEE_RESULT,
            True,
            True,
            id="cleared-mid-run",
        ),
    ],
)
def test_publish_rules(
    aws, fake, monkeypatch, mode, photo, judged, before, during, final, read, pinned
):
    # Review Focus 4: only a live or demo level is published, and only while the
    # switch reads "off" when its result is written. `during` sets the switch while
    # Muse Spark answers. The switch is read only for a result that could be pinned.
    # `final` pins each case's result, so a case that expects no pin can't pass by
    # not reaching its level.
    if judged is not None:
        fake.answer = judged
    failing = set()
    if before is None:
        failing.add(PUBLISH)
    else:
        aws.ssm.put_parameter(Name=PUBLISH, Value=before, Type="String", Overwrite=True)
    reads = spy_parameters(monkeypatch, failing)
    if during is not None:
        fake.on_judge = lambda: aws.ssm.put_parameter(
            Name=PUBLISH, Value=during, Type="String", Overwrite=True
        )
    seed(aws, photo=photo, mode={"S": mode})
    assert handler.handler(message(), None) == NO_FAILURES
    assert result(aws) == final
    expected = {"published": {"BOOL": True}, "feedPart": {"S": mode}} if pinned else {}
    assert published(aws) == expected
    assert [r["Name"] for r in reads] == ([SWITCH, PUBLISH] if read else [SWITCH])


def test_mode_is_read_from_the_item(aws, fake):
    # Review Focus 4: the event names only the raw photo. The same event publishes a
    # live report and nothing for a private one: an analysed photo from outside
    # Metro Manila is shown to its sender but never pinned.
    event = message()
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(event, None) == NO_FAILURES
    assert published(aws) == {"published": {"BOOL": True}, "feedPart": {"S": "live"}}
    seed(aws, photo=LEVEL_PHOTO, mode={"S": "private"})  # pending again
    assert handler.handler(event, None) == NO_FAILURES
    item = report(aws)
    token = item["claimToken"]["S"]
    expected = ITEM | {"mode": {"S": "private"}} | claimed(token, NOW_S, "done")
    assert item == expected | KNEE_UNPUBLISHED
    assert keys(aws) == [PHOTO_KEY]


def test_failed_publish_read_never_retries(aws, fake, monkeypatch, caplog):
    # Review Focus 3: the result is paid for, so a failed publish read writes it
    # unpublished instead of returning the message to claim and pay again.
    reads = spy_parameters(monkeypatch, {PUBLISH})
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(message(), None) == NO_FAILURES
    item = report(aws)
    token = item["claimToken"]["S"]
    assert item == ITEM | claimed(token, NOW_S, "done") | KNEE_UNPUBLISHED
    assert keys(aws) == [PHOTO_KEY]
    assert len(fake.calls) == 8
    assert [read["Name"] for read in reads] == [SWITCH, PUBLISH]  # read once
    (line,) = report_lines(caplog)
    assert line["outcome"] == "done/level"
    assert line["publish_switch"] == {
        "error": "InternalServerError",
        "http_status": 500,
    }
    # The code and status only: the error's message carries an ARN.
    assert "arn:" not in caplog.text
    assert "not authorized" not in caplog.text


def test_publish_read_has_its_own_bounded_client(aws, fake, monkeypatch, caplog):
    # The publish read comes after the paid run, inside the run's 30 s margin, so a
    # hung SSM call mustn't outlast it and make a redelivery pay again. Its client
    # has 2 s timeouts and 2 retries. The model-calls read before the claim keeps
    # the shared client. A timeout is a failed read: the result is written
    # unpublished, never retried (Review Focus 3).
    config = handler._post_run_ssm().meta.config
    assert (config.connect_timeout, config.read_timeout) == (2, 2)
    # botocore stores Config's max_attempts, a count of retries, as total attempts.
    assert config.retries["total_max_attempts"] == 2 + 1
    assert handler._post_run_ssm() is handler._post_run_ssm()  # made once
    shared = handler._client("ssm")
    shared_get = shared.get_parameter
    shared_reads, post_run_reads = [], []

    def read(**kwargs):
        shared_reads.append(kwargs["Name"])
        return shared_get(**kwargs)

    def timed_out(**kwargs):
        post_run_reads.append(kwargs["Name"])
        raise ReadTimeoutError(endpoint_url="https://ssm.ap-southeast-1.amazonaws.com/")

    monkeypatch.setattr(shared, "get_parameter", read)
    monkeypatch.setattr(handler._post_run_ssm(), "get_parameter", timed_out)
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(message(), None) == NO_FAILURES
    item = report(aws)
    token = item["claimToken"]["S"]
    assert item == ITEM | claimed(token, NOW_S, "done") | KNEE_UNPUBLISHED
    assert (shared_reads, post_run_reads) == ([SWITCH], [PUBLISH])
    (line,) = report_lines(caplog)
    assert line["publish_switch"] == {"error": "ReadTimeoutError"}
    assert "Read timeout" not in caplog.text  # the class name only


def test_demo_photo_goes_under_demo(aws, fake):
    # C510: a demo pin's objects go under demo/, with its own 60-day backstop. An
    # earlier attempt's three demo/ objects are deleted at the claim (C72).
    demo_keys = [f"demo/{key}" for key in STORED_KEYS]
    seed(aws, photo=LEVEL_PHOTO, mode={"S": "demo"}, **claimed("old", NOW_S - 901))
    for key in demo_keys:
        aws.s3.put_object(Bucket=BUCKET, Key=key, Body=b"a stale demo object")
    assert handler.handler(message(), None) == NO_FAILURES
    item = report(aws)
    token = item["claimToken"]["S"]
    demo_knee = KNEE | {"photoKey": {"S": demo_keys[0]}, "feedPart": {"S": "demo"}}
    demo_item = ITEM | {"mode": {"S": "demo"}}
    assert item == demo_item | claimed(token, NOW_S, "done") | demo_knee
    assert keys(aws) == [demo_keys[0]]
    _, sam, _ = level_case()
    stored = aws.s3.get_object(Bucket=BUCKET, Key=demo_keys[0])["Body"].read()
    assert stored == publish_jpeg(blur_for_meta(LEVEL_PHOTO), sam)


# A rejected key (C73)


def test_rejected_key_drops_the_client_and_retries(aws, monkeypatch, caplog):
    _, sam, _ = level_case()
    rejecting = FakeClient(sam, meta_error(401))
    built = record_meta_clients(monkeypatch, rejecting)
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(message(), None) == RETRY
    first = report(aws)
    assert first["status"] == {"S": "processing"}
    assert keys(aws) == [RAW_KEY]
    (line,) = report_lines(caplog)
    assert (line["outcome"], line["meta_status"]) == ("model_key_rejected", 401)
    # SQS redelivers after its 1,080 s visibility, past the 900 s lease: the report is
    # claimed again, and the key is read from SSM again.
    monkeypatch.setattr(handler, "_now_s", lambda: NOW_S + 1080)
    assert handler.handler(message(), None) == RETRY
    assert built == [True, True]
    second = report(aws)
    assert second["claimToken"] != first["claimToken"]
    assert second["claimedAt"] == {"N": str(NOW_S + 1080)}
    assert outcomes(caplog) == ["model_key_rejected", "model_key_rejected"]
    assert len(calls(rejecting, "judge")) == 2


# Before the claim (C60)


def no_blur(data: bytes):
    raise AssertionError("the face blur ran")


def test_ssm_read_failure_retries_before_any_work(aws, monkeypatch, caplog):
    _, sam, given = level_case()
    client = FakeClient(sam, given)
    built = record_meta_clients(monkeypatch, client)
    reads = spy_parameters(monkeypatch, {KEY_PARAM, SWITCH})
    monkeypatch.setattr("lusot_analysis.pipeline.blur_for_meta", no_blur)
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(message(), None) == RETRY
    assert report(aws) == ITEM  # pending, and never claimed
    assert keys(aws) == [RAW_KEY]
    assert [read["Name"] for read in reads] == [KEY_PARAM]
    assert built == []
    assert client.calls == []
    assert key_lines(caplog) == [
        {
            "outcome": "model_key_missing",
            "error": "InternalServerError",
            "http_status": 500,
        }
    ]


def test_unreadable_switch_leaves_the_report_pending(aws, fake, monkeypatch):
    reads = spy_parameters(monkeypatch, {SWITCH})
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(message(), None) == RETRY
    assert report(aws) == ITEM  # still pending, with no claimToken
    assert keys(aws) == [RAW_KEY]
    assert fake.calls == []
    assert [read["Name"] for read in reads] == [SWITCH]


def test_key_load_failure_is_not_cached(aws, monkeypatch, caplog):
    _, sam, given = level_case()
    built = record_meta_clients(monkeypatch, FakeClient(sam, given))
    failing = {KEY_PARAM}
    reads = spy_parameters(monkeypatch, failing)
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(message(), None) == RETRY
    assert report(aws) == ITEM
    failing.clear()  # SSM answers again
    assert handler.handler(message(), None) == NO_FAILURES
    assert status(aws) == ("done", None)
    assert handler.handler(message(), None) == NO_FAILURES  # warm: no new key read
    key_reads = [read for read in reads if read["Name"] == KEY_PARAM]
    assert key_reads == [{"Name": KEY_PARAM, "WithDecryption": True}] * 2
    assert built == [True]
    assert key_lines(caplog) == [
        {
            "outcome": "model_key_missing",
            "error": "InternalServerError",
            "http_status": 500,
        },
        {"outcome": "model_key_loaded=true"},
    ]
    assert outcomes(caplog) == ["error", "done/level", "already_finished"]
    assert "fake-model-key" not in caplog.text


def test_short_key_is_a_key_fault(aws, monkeypatch, caplog):
    # The real MetaClient refuses a key under 20 characters, before any network use.
    monkeypatch.setattr(handler, "MetaClient", MetaClient)
    aws.ssm.put_parameter(
        Name=KEY_PARAM, Value="stale", Type="SecureString", Overwrite=True
    )
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(message(), None) == RETRY
    assert report(aws) == ITEM
    assert keys(aws) == [RAW_KEY]
    assert key_lines(caplog) == [
        {"outcome": "model_key_missing", "error": "MissingApiKey"}
    ]
    assert "stale" not in caplog.text


def test_missing_prompt_is_retried(aws, fake, monkeypatch, tmp_path, caplog):
    # A deploy fault, like a key fault: the retries end in the dead-letter queue and
    # its alarm, never in a failed report (C79).
    monkeypatch.setenv("PROMPTS_DIR", str(tmp_path))  # an empty folder
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(message(), None) == RETRY
    assert report(aws) == ITEM
    assert keys(aws) == [RAW_KEY]
    assert fake.calls == []
    (line,) = report_lines(caplog)
    assert (line["outcome"], line["error"]) == ("error", "FileNotFoundError")


# The claim and the lease (G2, B5)


@pytest.mark.parametrize("value", ["on", "ON", "Off"])
def test_switch_set_ends_model_calls_paused(aws, fake, caplog, value):
    # Only an explicit "off" lets model calls through, as with the API's uploads switch.
    aws.ssm.put_parameter(Name=SWITCH, Value=value, Type="String", Overwrite=True)
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(message(), None) == NO_FAILURES
    assert status(aws) == ("failed", "model_calls_paused")
    assert keys(aws) == []
    assert fake.calls == []
    assert outcomes(caplog) == ["failed/model_calls_paused"]


@pytest.mark.parametrize(
    ("final", "attributes"),
    [
        ("done", KNEE),
        ("refused", {"refusalReason": {"S": "too_dark"}}),
        ("failed", {"refusalReason": {"S": "model_error"}}),
    ],
)
def test_delivery_after_result_pays_nothing_and_deletes_raw(
    aws, fake, caplog, final, attributes
):
    # A retried delete or a reused upload link, long after the lease time: the status
    # decides, so nothing is claimed or paid, and only the raw photo is deleted.
    before = seed(
        aws, photo=LEVEL_PHOTO, **claimed("old", NOW_S - 3600, final), **attributes
    )
    stored = [PHOTO_KEY] if "photoKey" in attributes else []
    for key in stored:
        aws.s3.put_object(Bucket=BUCKET, Key=key, Body=b"the level's photo")
    assert handler.handler(message(), None) == NO_FAILURES
    assert report(aws) == before
    assert keys(aws) == stored  # the raw photo is gone; a level keeps its photo
    assert fake.calls == []
    assert outcomes(caplog) == ["already_finished"]


def test_live_lease_is_left_alone(aws, fake, monkeypatch, caplog):
    # Another worker holds a live lease. The delivery returns its message instead of
    # finishing it, so a copy is left if that worker crashes (C89). It sets no short
    # visibility: R92's 10 s is only for a report the index doesn't show yet.
    changes = spy_visibility(monkeypatch)
    before = seed(aws, photo=LEVEL_PHOTO, **claimed("other", NOW_S - 60))
    assert handler.handler(message(), None) == RETRY
    assert report(aws) == before
    assert keys(aws) == [RAW_KEY]  # the worker that holds the lease deletes it
    assert fake.calls == []
    assert changes == []
    # The holder crashes. The copy comes back after the queue's 1,080 s visibility
    # timeout, past the 900 s lease, and claims the report again.
    monkeypatch.setattr(handler, "_now_s", lambda: NOW_S + 1080)
    assert handler.handler(message(), None) == NO_FAILURES
    item = report(aws)
    assert item["claimToken"] != {"S": "other"}
    token = item["claimToken"]["S"]
    assert item == ITEM | claimed(token, NOW_S + 1080, "done") | KNEE
    assert len(fake.calls) == 8
    assert keys(aws) == [PHOTO_KEY]
    assert outcomes(caplog) == ["lease_held", "done/level"]


def test_expired_lease_is_reclaimed(aws, fake):
    seed(aws, photo=LEVEL_PHOTO, **claimed("old", NOW_S - 901))
    assert handler.handler(message(), None) == NO_FAILURES
    item = report(aws)
    assert item["claimToken"] != {"S": "old"}
    assert item == ITEM | claimed(item["claimToken"]["S"], NOW_S, "done") | KNEE
    assert len(fake.calls) == 8
    assert keys(aws) == [PHOTO_KEY]


def test_racing_deliveries_pay_once(aws, fake, monkeypatch, caplog):
    seed(aws, photo=LEVEL_PHOTO)
    nested = []

    def second_delivery(phrase: str) -> None:
        # The same message delivered again while the first worker calls SAM. It runs
        # once: marked first, so a second delivery that wrongly pays can't recurse.
        if phrase == "floodwater" and not nested:
            nested.append(None)
            nested[0] = handler.handler(message(), None)

    fake.on_segment = second_delivery
    assert handler.handler(message(), None) == NO_FAILURES
    # The second delivery met the first worker's lease: it paid nothing, and it
    # returned its message (C89).
    assert nested == [RETRY]
    assert len(fake.calls) == 8  # one set of calls: 7 + 1
    assert outcomes(caplog) == ["lease_held", "done/level"]
    assert status(aws) == ("done", None)
    assert keys(aws) == [PHOTO_KEY]
    # The returned copy comes back 1,080 s later, after the result, and only finishes.
    monkeypatch.setattr(handler, "_now_s", lambda: NOW_S + 1080)
    assert handler.handler(message(), None) == NO_FAILURES
    assert len(fake.calls) == 8
    assert outcomes(caplog) == ["lease_held", "done/level", "already_finished"]


def test_lease_lost_at_the_final_write(aws, fake, caplog):
    fake.answer = answer(standing_water="no")
    seed(aws, photo=LEVEL_PHOTO)

    def taken_over() -> None:  # another worker claims the report meanwhile
        aws.ddb.update_item(
            TableName=TABLE,
            Key=KEY,
            UpdateExpression="SET claimToken = :other",
            ExpressionAttributeValues={":other": {"S": "other"}},
        )

    fake.on_judge = taken_over
    assert handler.handler(message(), None) == NO_FAILURES
    assert report(aws) == ITEM | claimed("other", NOW_S)  # no result fields
    assert keys(aws) == [RAW_KEY]
    assert outcomes(caplog) == ["lease_lost"]


def test_failed_raw_delete_retries_without_reanalysis(aws, fake, monkeypatch, caplog):
    seed(aws, photo=LEVEL_PHOTO)
    fail_deletes(monkeypatch, RAW_KEY)
    assert handler.handler(message(), None) == RETRY
    assert status(aws) == ("done", None)  # written before the delete
    done = report(aws)
    assert keys(aws) == [PHOTO_KEY, RAW_KEY]
    # SQS delivers the message again: the retry only deletes.
    assert handler.handler(message(), None) == NO_FAILURES
    assert report(aws) == done
    assert keys(aws) == [PHOTO_KEY]
    assert len(fake.calls) == 8
    assert outcomes(caplog) == ["error", "already_finished"]


def test_failed_delete_redelivered_after_lease_time_only_deletes(
    aws, fake, monkeypatch, caplog
):
    # Review Focus 2: the redelivery comes 18 minutes later, after the lease time. The
    # status decides, so it doesn't claim the report again or pay.
    seed(aws, photo=LEVEL_PHOTO)
    fail_deletes(monkeypatch, RAW_KEY)
    assert handler.handler(message(), None) == RETRY
    done = report(aws)
    monkeypatch.setattr(handler, "_now_s", lambda: NOW_S + 1080)
    assert handler.handler(message(), None) == NO_FAILURES
    assert report(aws) == done
    assert keys(aws) == [PHOTO_KEY]
    assert len(fake.calls) == 8
    assert outcomes(caplog) == ["error", "already_finished"]


def test_reused_link_during_analysis_pays_once_and_leaves_no_raw(aws, fake, caplog):
    # Review Focus 4: the upload form is posted again while the first worker waits
    # for Muse Spark.
    seed(aws, photo=LEVEL_PHOTO)
    second = []

    def reuse_the_link() -> None:
        # Once, as in the racing test: a second delivery that wrongly pays reaches
        # this hook too.
        if not second:
            second.append(None)
            aws.s3.put_object(Bucket=BUCKET, Key=RAW_KEY, Body=LEVEL_PHOTO)
            second[0] = handler.handler(message(), None)

    fake.on_judge = reuse_the_link
    assert handler.handler(message(), None) == NO_FAILURES
    assert second == [RETRY]  # it met the lease, so it returned its message (C89)
    assert len(fake.calls) == 8
    assert outcomes(caplog) == ["lease_held", "done/level"]
    item = report(aws)
    assert item == ITEM | claimed(item["claimToken"]["S"], NOW_S, "done") | KNEE
    assert keys(aws) == [PHOTO_KEY]


# S3 codes (R22, narrowed)


def test_missing_photo_code(aws, fake, caplog):
    # The role's raw/-limited s3:ListBucket makes S3 answer 404 NoSuchKey for a
    # missing key, as MS3a Task 16 recorded in the cloud (R93).
    seed(aws)  # no raw object: moto answers NoSuchKey
    assert handler.handler(message(), None) == NO_FAILURES
    assert status(aws) == ("failed", "photo_missing")
    (line,) = report_lines(caplog)
    assert (line["outcome"], line["error"], line["http_status"]) == (
        "failed/photo_missing",
        "NoSuchKey",
        404,
    )
    assert fake.calls == []
    assert "arn:" not in caplog.text


PNG = cv2.imencode(".png", np.zeros((48, 64, 3), np.uint8))[1].tobytes()


@pytest.mark.parametrize(
    "data",
    [PNG, b"GIF89a" + bytes(32), b"\xff\xd8\x00" + bytes(32)],
    ids=["png", "gif", "ff-d8-only"],
)
def test_non_jpeg_bytes_end_bad_file_before_decoding(aws, fake, monkeypatch, data):
    # C83: OpenCV decodes PNG and GIF, so only JPEG's FF D8 FF reaches a decoder.
    def no_analysis(*args, **kwargs):
        raise AssertionError("a file that isn't JPEG was analysed")

    monkeypatch.setattr(handler, "analyse", no_analysis)
    seed(aws, photo=data)
    assert handler.handler(message(), None) == NO_FAILURES
    assert status(aws) == ("failed", "bad_file")
    assert keys(aws) == []
    assert fake.calls == []


@pytest.mark.parametrize(
    ("code", "http_status"),
    [
        ("SignatureDoesNotMatch", 403),
        ("RequestTimeTooSkewed", 403),
        ("AccessDenied", 403),
        ("InternalError", 500),
    ],
)
def test_other_s3_errors_retry(aws, fake, monkeypatch, caplog, code, http_status):
    # A 403 from clock skew or a bad signature can pass, so it retries (R22). With the
    # role's ListBucket a missing key reads 404 (MS3a Task 16), so AccessDenied is a
    # real permission fault: it retries into the dead-letter queue and its alarm (R93).
    seed(aws, photo=LEVEL_PHOTO)

    def get_object(**kwargs):
        raise aws_error(code, http_status, "GetObject")

    monkeypatch.setattr(handler._client("s3"), "get_object", get_object)
    assert handler.handler(message(), None) == RETRY
    assert status(aws) == ("processing", None)
    assert keys(aws) == [RAW_KEY]
    assert fake.calls == []
    assert "arn:" not in caplog.text
    (line,) = report_lines(caplog)
    assert line.pop("ms") >= 0
    # Only the code and status, and no R92 visibility change: it comes back at 1,080 s.
    assert line == {
        "reportId": REPORT_ID,
        "outcome": "error",
        "error": code,
        "http_status": http_status,
    }


def test_aws_error_after_meta_calls_retries(aws, fake, monkeypatch, caplog):
    seed(aws, photo=LEVEL_PHOTO)
    s3 = handler._client("s3")
    put_object = s3.put_object

    def put(**kwargs):
        if kwargs["Key"] == PHOTO_KEY:
            raise aws_error("InternalError", 500, "PutObject")
        return put_object(**kwargs)

    monkeypatch.setattr(s3, "put_object", put)
    assert handler.handler(message(), None) == RETRY
    assert status(aws) == ("processing", None)
    assert keys(aws) == [RAW_KEY]
    assert len(fake.calls) == 8
    # The line keeps the pipeline's fields, so the paid calls are counted.
    (line,) = report_lines(caplog)
    assert (line["outcome"], line["error"], line["http_status"]) == (
        "error",
        "InternalError",
        500,
    )
    assert line["meta_calls"] == 8


# Logs (§3.6, C62)


@pytest.mark.parametrize(
    ("photo", "judged", "key", "outcome"),
    [
        pytest.param(LEVEL_PHOTO, None, RAW_KEY, "done/level", id="level"),
        pytest.param(flat_jpeg(10), None, RAW_KEY, "refused/too_dark", id="refusal"),
        pytest.param(
            LEVEL_PHOTO, meta_error(500), RAW_KEY, "failed/model_error", id="meta-error"
        ),
        pytest.param(LEVEL_PHOTO, None, "raw/r_123.jpg", "unknown_key", id="bad-key"),
    ],
)
def test_sentinel_ip_never_reaches_a_log(
    aws, fake, caplog, photo, judged, key, outcome
):
    if judged is not None:
        fake.answer = judged
    seed(aws, photo=photo)
    aws.s3.put_object(Bucket=BUCKET, Key=key, Body=photo)
    assert handler.handler(message(key), None) == NO_FAILURES
    assert [line["outcome"] for line in logged(caplog)] == [outcome]
    assert SOURCE_IP not in caplog.text
    assert PRINCIPAL not in caplog.text


def test_one_log_line_per_report_with_its_fields(aws, fake, caplog):
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(message(), None) == NO_FAILURES
    (line,) = report_lines(caplog)
    assert line["outcome"] == "done/level"
    assert line["meta_calls"] == 8
    assert line["deciding"] == "wheel"
    assert {
        "reportId",
        "outcome",
        "ms",
        "meta_calls",
        "sam_ms",
        "spark_ms",
        "instances",
        "models",
        "prompt_version",
        "blur_version",
        "face_boxes",
        "drops",
        "deciding",
    } <= set(line)


def test_logs_never_carry_private_data(aws, monkeypatch, caplog):
    # The key goes through the handler's own loader here, so the check covers it.
    _, sam, given = level_case()
    built = record_meta_clients(monkeypatch, FakeClient(sam, given))
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(message(), None) == NO_FAILURES
    assert status(aws) == ("done", None)
    assert built == [True]
    for private in ("wdw515", "14.6095", "120.9894", FAKE_KEY, REASON, "arn:"):
        assert private not in caplog.text


def test_lambda_never_counts_tokens(aws, fake, monkeypatch):
    counted = []

    def count_input_tokens(*args, **kwargs):
        counted.append(True)
        raise AssertionError("the Lambda never counts input tokens (spec §3.6)")

    monkeypatch.setattr(fake, "count_input_tokens", count_input_tokens)
    seed(aws, photo=LEVEL_PHOTO)
    assert handler.handler(message(), None) == NO_FAILURES
    assert status(aws) == ("done", None)
    assert counted == []


# B3: the same saved outputs give the same result on the laptop and in the cloud


def test_b3_replay_through_runner_and_handler_match(tmp_path, monkeypatch, prompts):
    data, sam, given = level_case()
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr(runner, "make_client", lambda: FakeClient(sam, given))
    photo = tmp_path / "street.jpg"
    photo.write_bytes(data)
    run_dir, live = runner.live(photo, tmp_path / "data")
    replayed = runner.replay(photo, run_dir)
    # The handler's call asks for all 7 phrases. The runner saved 5, and the face and
    # plate phrases come back empty (R109), so a level still gets its photo.
    handled = handler.analyse(data, SavedOutputsClient(run_dir, data))
    assert live.outcome.level == "knee"
    assert replayed.outcome == handled.outcome == live.outcome
    assert handled.publish_jpeg is not None


@pytest.mark.skipif(
    not (os.environ.get("LUSOT_B3_RUN_DIR") and os.environ.get("LUSOT_B3_PHOTO")),
    reason="needs LUSOT_B3_RUN_DIR and LUSOT_B3_PHOTO: a real saved run (Task 16)",
)
def test_b3_on_a_real_saved_run(prompts):
    run_dir = Path(os.environ["LUSOT_B3_RUN_DIR"])
    photo = Path(os.environ["LUSOT_B3_PHOTO"])
    replayed = runner.replay(photo, run_dir)  # refuses a sealed path before reading
    data = photo.read_bytes()
    handled = handler.analyse(data, SavedOutputsClient(run_dir, data))
    saved = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert replayed.outcome == handled.outcome
    assert dataclasses.asdict(handled.outcome) == saved["outcome"]


# The cold start (Oct 29)


def test_importing_the_handler_loads_no_cv2_or_model():
    # The Lambda's init hit its 10 s limit, so the handler's import loads nothing
    # heavy: no OpenCV, no face_blur (the only module that builds YuNet), no
    # pipeline, and none of the Meta client or what it brings in. A new interpreter,
    # since this test process has loaded them already.
    heavy = {
        "cv2",
        "numpy",
        "openai",
        "httpx",
        "meta_sam_parser",
        "lusot_analysis.meta_client",
        "lusot_analysis.face_blur",
        "lusot_analysis.pipeline",
    }
    code = (
        "import sys\n"
        "import lusot_analysis.handler\n"
        f"heavy = {sorted(heavy)!r}\n"
        "loaded = sorted(set(heavy) & set(sys.modules))\n"
        "assert not loaded, loaded\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
