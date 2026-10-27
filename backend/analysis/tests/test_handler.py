"""Tests for the MS1 analysis Lambda stub (C28), against moto's AWS."""

import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote_plus

import boto3
import cv2
import numpy as np
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from lusot_analysis import face_blur, handler

BUCKET = "lusot-test-uploads"
TABLE = "lusot-test-reports"
KEY_PARAM = "/lusot/meta/model-api-key"
FAKE_KEY = "fake-model-key-" + "0" * 33  # 48 characters, like the real key (spec A8)
REPORT_ID = "r_" + "0123456789abcdef" * 2
RAW_KEY = f"raw/{REPORT_ID}.jpg"
CAPTURED_AT = "2026-10-28T03:00:00.000Z"
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
PORTRAIT = Path(__file__).parent / "fixtures" / "faces" / "portrait.jpg"


def gradient_jpeg() -> bytes:
    """A synthetic 640 x 480 photo with no face.

    Not smaller: YuNet can return garbage boxes for detection passes under 32 px.
    """
    row = np.linspace(0, 255, 640).astype(np.uint8)
    return cv2.imencode(".jpg", np.dstack([np.tile(row, (480, 1))] * 3))[1].tobytes()


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


@pytest.fixture
def aws(monkeypatch):
    """Moto's S3, DynamoDB and SSM, set up as the template sets up the real ones."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(name, "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-southeast-1")
    monkeypatch.setenv("TABLE_NAME", TABLE)
    monkeypatch.setenv("BUCKET_NAME", BUCKET)
    monkeypatch.setenv("STOP_PARAM_PREFIX", "/lusot/stop/")
    monkeypatch.setenv("MODEL_KEY_PARAM", KEY_PARAM)
    # Each test starts cold: new clients inside the mock, and the key check not yet run.
    handler._client.cache_clear()
    handler._check_model_key.cache_clear()
    with mock_aws():
        s3, ddb, ssm = (boto3.client(name) for name in ("s3", "dynamodb", "ssm"))
        s3.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
        )
        ddb.create_table(
            TableName=TABLE,
            AttributeDefinitions=[
                {"AttributeName": name, "AttributeType": "S"}
                for name in ("pk", "sk", "reportId")
            ],
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "reportId-index",
                    "KeySchema": [{"AttributeName": "reportId", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5,
                    },
                }
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 10, "WriteCapacityUnits": 5},
        )
        ssm.put_parameter(Name="/lusot/stop/model-calls", Value="off", Type="String")
        ssm.put_parameter(Name=KEY_PARAM, Value=FAKE_KEY, Type="SecureString")
        yield SimpleNamespace(s3=s3, ddb=ddb, ssm=ssm)


@pytest.fixture
def blur_calls(monkeypatch):
    """Records each face-blur run, so a test can tell whether a photo was analysed."""
    calls = []

    def spy(data):
        calls.append(len(data))
        return face_blur.blur_for_meta(data)

    monkeypatch.setattr(handler, "blur_for_meta", spy)
    return calls


def seed(aws, photo: bytes | None = None, **fields: str) -> None:
    """Write the report, with `fields` replacing its strings, and its raw photo."""
    item = ITEM | {name: {"S": value} for name, value in fields.items()}
    aws.ddb.put_item(TableName=TABLE, Item=item)
    if photo is not None:
        aws.s3.put_object(Bucket=BUCKET, Key=RAW_KEY, Body=photo)


def report(aws) -> dict:
    return aws.ddb.get_item(TableName=TABLE, Key={"pk": ITEM["pk"], "sk": ITEM["sk"]})[
        "Item"
    ]


def status(aws) -> tuple[str, str | None]:
    item = report(aws)
    return item["status"]["S"], item.get("refusalReason", {}).get("S")


def keys(aws) -> list[str]:
    return [
        obj["Key"] for obj in aws.s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])
    ]


def message(key: str = RAW_KEY) -> dict:
    """An SQS batch of one S3 notification, with the key URL-encoded as S3 sends it."""
    body = {
        "Records": [
            {
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Post",
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
                "body": json.dumps(body),
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:ap-southeast-1:account-id:lusot-queue",
            }
        ]
    }


def logged(caplog) -> list[dict]:
    return [
        json.loads(r.getMessage()) for r in caplog.records if r.name == "lusot.analysis"
    ]


def report_lines(caplog) -> list[dict]:
    return [line for line in logged(caplog) if line.get("reportId") == REPORT_ID]


NO_FAILURES = {"batchItemFailures": []}
RETRY = {"batchItemFailures": [{"itemIdentifier": "m-1"}]}


def test_stub_marks_failed_pipeline_not_built_and_deletes_raw(aws, caplog):
    seed(aws, photo=PORTRAIT.read_bytes())
    assert handler.handler(message(), None) == NO_FAILURES
    assert status(aws) == ("failed", "pipeline_not_built")
    # The raw photo is gone, and nothing is under blurred/ or overlay/.
    assert keys(aws) == []
    (line,) = report_lines(caplog)
    assert line["outcome"] == "pipeline_not_built"
    assert line["face_boxes"] >= 1  # the face blur ran on the portrait
    assert line["ms"] >= 0
    for location in ("wdw515", "14.6095", "120.9894"):
        assert location not in caplog.text


def test_s3_test_event_is_ignored(aws):
    seed(aws, photo=gradient_jpeg())
    before = report(aws)
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


def test_undecodable_file_marks_bad_file(aws):
    seed(aws, photo=b"not a jpeg")
    assert handler.handler(message(), None) == NO_FAILURES
    assert status(aws) == ("failed", "bad_file")
    assert keys(aws) == []


def test_duplicate_event_does_not_reprocess(aws, blur_calls):
    seed(
        aws, photo=gradient_jpeg(), status="failed", refusalReason="pipeline_not_built"
    )
    before = report(aws)
    assert handler.handler(message(), None) == NO_FAILURES
    assert report(aws) == before
    assert keys(aws) == []
    assert blur_calls == []


@pytest.mark.parametrize("value", ["on", "ON"])
def test_model_calls_stop_switch_marks_paused(aws, blur_calls, value):
    # Only an explicit "off" lets model calls through, as with the API's uploads switch.
    aws.ssm.put_parameter(
        Name="/lusot/stop/model-calls", Value=value, Type="String", Overwrite=True
    )
    seed(aws, photo=gradient_jpeg())
    assert handler.handler(message(), None) == NO_FAILURES
    assert status(aws) == ("failed", "model_calls_paused")
    assert keys(aws) == []
    assert blur_calls == []


def test_failed_delete_is_reported_for_retry(aws, monkeypatch, blur_calls):
    seed(aws, photo=gradient_jpeg())
    s3 = handler._client("s3")
    delete = s3.delete_object
    deletes = []

    def fails_once(**kwargs):
        deletes.append(kwargs["Key"])
        if len(deletes) == 1:
            raise aws_error("InternalError", 500, "DeleteObject")
        return delete(**kwargs)

    monkeypatch.setattr(s3, "delete_object", fails_once)
    assert handler.handler(message(), None) == RETRY
    assert status(aws) == ("failed", "pipeline_not_built")  # set before the delete
    assert keys(aws) == [RAW_KEY]
    # SQS delivers the message again: the retry only deletes.
    assert handler.handler(message(), None) == NO_FAILURES
    assert keys(aws) == []
    assert status(aws) == ("failed", "pipeline_not_built")
    assert len(blur_calls) == 1


@pytest.mark.parametrize("key", ["raw/whatever.png", "raw/what ever.png"])
def test_unknown_key_is_deleted_and_skipped(aws, key):
    aws.s3.put_object(Bucket=BUCKET, Key=key, Body=b"junk")
    assert handler.handler(message(key), None) == NO_FAILURES
    assert keys(aws) == []


@pytest.mark.parametrize(
    ("value", "outcome"),
    [
        (FAKE_KEY, "model_key_loaded=true"),
        ("stale", "model_key_missing"),  # too short, like the stale shell copy
        (None, "model_key_missing"),  # no parameter at all
    ],
    ids=["present", "too-short", "absent"],
)
def test_cold_start_checks_key_length_only(aws, caplog, value, outcome):
    if value is None:
        aws.ssm.delete_parameter(Name=KEY_PARAM)
    else:
        aws.ssm.put_parameter(
            Name=KEY_PARAM, Value=value, Type="SecureString", Overwrite=True
        )
    seed(aws, photo=gradient_jpeg())
    assert handler.handler(message(), None) == NO_FAILURES
    assert handler.handler(message(), None) == NO_FAILURES  # warm: no second check
    checks = [
        line for line in logged(caplog) if line["outcome"].startswith("model_key")
    ]
    assert [line["outcome"] for line in checks] == [outcome]
    assert set(checks[0]) <= {"outcome", "error", "status"}  # never the value or length
    assert "fake-model-key" not in caplog.text
    assert "stale" not in caplog.text
    assert status(aws) == ("failed", "pipeline_not_built")  # processing still proceeds


@pytest.mark.parametrize("http_status", [404, 403])
def test_missing_photo_marks_photo_missing(aws, monkeypatch, http_status):
    seed(aws)  # no raw object
    if http_status == 403:
        # Without s3:ListBucket, the real role gets 403, not 404, for a missing key.
        def get_object(**kwargs):
            raise aws_error("AccessDenied", 403, "GetObject")

        monkeypatch.setattr(handler._client("s3"), "get_object", get_object)
    assert handler.handler(message(), None) == NO_FAILURES
    assert status(aws) == ("failed", "photo_missing")


def test_report_not_found_is_retried(aws):
    # The index can lag the table, so the photo waits for the retry.
    aws.s3.put_object(Bucket=BUCKET, Key=RAW_KEY, Body=gradient_jpeg())
    assert handler.handler(message(), None) == RETRY
    assert keys(aws) == [RAW_KEY]


def test_finished_report_is_not_overwritten(aws, monkeypatch):
    # Another delivery of the event finished the report after this one read it.
    seed(aws, photo=gradient_jpeg(), status="failed", refusalReason="bad_file")
    pending = ITEM  # what the index showed before the other delivery finished
    monkeypatch.setattr(
        handler._client("dynamodb"), "query", lambda **kwargs: {"Items": [pending]}
    )
    assert handler.handler(message(), None) == NO_FAILURES
    assert status(aws) == ("failed", "bad_file")
    assert keys(aws) == []


def test_aws_error_is_logged_by_code_and_status_only(aws, monkeypatch, caplog):
    seed(aws, photo=gradient_jpeg())

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
        "status": 400,
    }
