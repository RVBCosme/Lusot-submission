"""Tests for the report store: the claim before paying, and the writes under it.

G2 and C46: a worker claims a report with a 15-minute lease before any Meta call, and
writes the result only while its claim holds. Run against moto's DynamoDB.
"""

import boto3
import pytest
from botocore.exceptions import ClientError
from fakes import create_reports_table
from moto import mock_aws

from lusot_analysis.pipeline.types import Outcome
from lusot_analysis.report_store import claim, write_result

TABLE = "lusot-test-reports"
NOW_S = 1_800_000_000
REPORT_ID = "r_" + "0123456789abcdef" * 2
CAPTURED_AT = "2026-10-28T03:00:00.000Z"
KEY = {"pk": {"S": "GEO#wdw515"}, "sk": {"S": f"{CAPTURED_AT}#{REPORT_ID}"}}
# A pending report as the API writes it (Table 14 subset).
PENDING = KEY | {
    "reportId": {"S": REPORT_ID},
    "mode": {"S": "live"},
    "status": {"S": "pending"},
    "capturedAt": {"S": CAPTURED_AT},
}
PHOTO_KEY = f"blurred/{REPORT_ID}.jpg"


@pytest.fixture
def ddb(monkeypatch):
    """Moto's DynamoDB, with the reports table."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(name, "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-southeast-1")
    with mock_aws():
        client = boto3.client("dynamodb")
        create_reports_table(client, TABLE)
        yield client


def claimed(token: str, claimed_at: int, status: str = "processing") -> dict:
    """A claim's attributes as stored, with the report's status."""
    return {
        "status": {"S": status},
        "claimToken": {"S": token},
        "claimedAt": {"N": str(claimed_at)},
    }


def seed(ddb, **attributes: dict) -> dict:
    """Write the pending report with `attributes` replacing its own, and return it."""
    item = PENDING | attributes
    ddb.put_item(TableName=TABLE, Item=item)
    return item


def stored(ddb) -> dict:
    return ddb.get_item(TableName=TABLE, Key=KEY)["Item"]


def test_claims_a_pending_report(ddb):
    seed(ddb)
    assert claim(ddb, TABLE, KEY, "a", NOW_S) == "claimed"
    assert stored(ddb) == PENDING | claimed("a", NOW_S)


@pytest.mark.parametrize("status", ["done", "refused", "failed"])
def test_finished_reports_are_not_claimed(ddb, status):
    before = seed(ddb, status={"S": status})
    assert claim(ddb, TABLE, KEY, "a", NOW_S) == "finished"
    assert stored(ddb) == before


def test_live_lease_is_respected(ddb):
    # A lease exactly 15 minutes old is still live. Only an older one expires.
    before = seed(ddb, **claimed("old", NOW_S - 900))
    assert claim(ddb, TABLE, KEY, "new", NOW_S) == "leased"
    assert stored(ddb) == before


def test_expired_lease_is_reclaimed(ddb):
    seed(ddb, **claimed("old", NOW_S - 901))
    assert claim(ddb, TABLE, KEY, "new", NOW_S) == "claimed"
    assert stored(ddb) == PENDING | claimed("new", NOW_S)


def test_finished_report_with_old_claim_is_never_reclaimed(ddb):
    # Review Focus 2: a failed raw delete comes back 18 minutes later, after the lease
    # time. The status decides, so that delivery only deletes and pays nothing.
    before = seed(ddb, **claimed("old", NOW_S - 3600, status="done"))
    assert claim(ddb, TABLE, KEY, "new", NOW_S) == "finished"
    assert stored(ddb) == before


def test_missing_report_is_never_created(ddb):
    # With no item there is no status, so the claim reads as leased. It mustn't create
    # the item, or the handler would pay for a report that doesn't exist. Nor may a
    # result write create one.
    assert claim(ddb, TABLE, KEY, "a", NOW_S) == "leased"
    fields = Outcome.no_flood().item_fields()
    assert write_result(ddb, TABLE, KEY, "a", fields) is False
    assert "Item" not in ddb.get_item(TableName=TABLE, Key=KEY)


def test_a_repeated_claim_is_its_own(ddb):
    # C82: the SDK repeats a claim whose answer was lost, and the repeat fails against
    # the first try's own result. Tokens are new for every delivery, so it's this one.
    seed(ddb)
    assert claim(ddb, TABLE, KEY, "a", NOW_S) == "claimed"
    first = stored(ddb)
    assert claim(ddb, TABLE, KEY, "a", NOW_S) == "claimed"
    assert stored(ddb) == first
    # The same state under another token is a live lease.
    assert claim(ddb, TABLE, KEY, "b", NOW_S) == "leased"
    assert stored(ddb) == first


def test_writes_a_level_result_under_the_claim(ddb):
    seed(ddb)
    assert claim(ddb, TABLE, KEY, "a", NOW_S) == "claimed"
    outcome = Outcome.level_result(
        "knee", "rim_three_quarters", False, {"vehicles": 1, "people": 0}
    )
    fields = outcome.item_fields() | {"photoKey": PHOTO_KEY}
    assert write_result(ddb, TABLE, KEY, "a", fields) is True
    # The claim's token and time stay with the result.
    assert stored(ddb) == PENDING | claimed("a", NOW_S) | {
        "status": {"S": "done"},
        "noFloodSeen": {"BOOL": False},
        "level": {"S": "knee"},
        "landmark": {"S": "rim_three_quarters"},
        "passability": {"S": "NPLV"},
        "levelIsFloor": {"BOOL": False},
        "basis": {"M": {"vehicles": {"N": "1"}, "people": {"N": "0"}}},
        "photoKey": {"S": PHOTO_KEY},
    }


@pytest.mark.parametrize(
    ("status", "reason"), [("refused", "too_dark"), ("failed", "model_error")]
)
def test_writes_refusals_and_failures(ddb, status, reason):
    seed(ddb)
    assert claim(ddb, TABLE, KEY, "a", NOW_S) == "claimed"
    fields = Outcome(status, reason).item_fields()
    assert write_result(ddb, TABLE, KEY, "a", fields) is True
    # Exactly the status and its reason: no level field and no photo (C42, C61).
    assert stored(ddb) == PENDING | claimed("a", NOW_S, status=status) | {
        "refusalReason": {"S": reason}
    }


def test_lost_lease_drops_the_write(ddb):
    seed(ddb)
    assert claim(ddb, TABLE, KEY, "a", NOW_S) == "claimed"
    # Another worker re-claimed the report after this worker's lease expired.
    ddb.update_item(
        TableName=TABLE,
        Key=KEY,
        UpdateExpression="SET claimToken = :b",
        ExpressionAttributeValues={":b": {"S": "b"}},
    )
    fields = Outcome.no_flood().item_fields()
    assert write_result(ddb, TABLE, KEY, "a", fields) is False
    assert stored(ddb) == PENDING | claimed("b", NOW_S)


def test_write_requires_processing(ddb):
    before = seed(ddb, **claimed("a", NOW_S, status="done"))
    fields = Outcome.failed("model_error").item_fields()
    assert write_result(ddb, TABLE, KEY, "a", fields) is False
    assert stored(ddb) == before


def test_a_repeated_write_is_its_own(ddb):
    # C82: a repeated write finds this worker's token and the status it writes.
    seed(ddb)
    assert claim(ddb, TABLE, KEY, "a", NOW_S) == "claimed"
    fields = Outcome.no_flood().item_fields()
    assert write_result(ddb, TABLE, KEY, "a", fields) is True
    written = stored(ddb)
    assert write_result(ddb, TABLE, KEY, "a", fields) is True
    assert stored(ddb) == written
    # Another token never counts, and neither does another status under this one.
    assert write_result(ddb, TABLE, KEY, "b", fields) is False
    failed = Outcome.failed("model_error").item_fields()
    assert write_result(ddb, TABLE, KEY, "a", failed) is False
    assert stored(ddb) == written


def test_other_aws_errors_propagate(ddb, monkeypatch):
    def throttled(**kwargs):
        raise ClientError(
            {
                "Error": {
                    "Code": "ProvisionedThroughputExceededException",
                    "Message": "throttled",
                },
                "ResponseMetadata": {"HTTPStatusCode": 400},
            },
            "UpdateItem",
        )

    seed(ddb)
    monkeypatch.setattr(ddb, "update_item", throttled)
    with pytest.raises(ClientError, match="ProvisionedThroughputExceededException"):
        claim(ddb, TABLE, KEY, "a", NOW_S)
    fields = Outcome.no_flood().item_fields()
    with pytest.raises(ClientError, match="ProvisionedThroughputExceededException"):
        write_result(ddb, TABLE, KEY, "a", fields)
