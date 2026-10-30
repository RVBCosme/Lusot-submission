"""Tests for the report store: the claim before paying, and the writes under it.

G2 and C46: a worker claims a report with a 15-minute lease before any Meta call, and
writes the result only while its claim holds. Run against moto's DynamoDB.
"""

import math
from decimal import Decimal

import boto3
import pytest
from boto3.dynamodb.types import TypeDeserializer
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
# Two readings as the overlay makes them (C507): a null level, a null pair of inches,
# a bool, and a pair of floats.
READINGS = [
    {
        "id": 1,
        "kind": "body",
        "landmark": "not_visible",
        "level": None,
        "inches": None,
        "used": False,
        "dropped": None,
    },
    {
        "id": 2,
        "kind": "wheel",
        "landmark": "rim_quarter",
        "level": "half_knee",
        "inches": [7.7, 8.2],
        "used": True,
        "dropped": None,
    },
]


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
        "levelFrom": {"S": "landmark"},
        "photoKey": {"S": PHOTO_KEY},
    }


def test_writes_inches_as_numbers(ddb):
    # C308: a geometry level stores its source, and its inches as numbers.
    seed(ddb)
    assert claim(ddb, TABLE, KEY, "a", NOW_S) == "claimed"
    outcome = Outcome.level_result(
        "half_knee",
        "rim_quarter",
        False,
        {"vehicles": 1, "people": 0},
        level_from="geometry",
        depth_in=(8.2, 8.8),
    )
    fields = outcome.item_fields()
    assert (fields["depthInMin"], fields["depthInMax"]) == (8.2, 8.8)
    assert write_result(ddb, TABLE, KEY, "a", fields) is True
    assert stored(ddb) == PENDING | claimed("a", NOW_S) | {
        "status": {"S": "done"},
        "noFloodSeen": {"BOOL": False},
        "level": {"S": "half_knee"},
        "landmark": {"S": "rim_quarter"},
        "passability": {"S": "PATV"},
        "levelIsFloor": {"BOOL": False},
        "basis": {"M": {"vehicles": {"N": "1"}, "people": {"N": "0"}}},
        "levelFrom": {"S": "geometry"},
        "depthInMin": {"N": "8.2"},
        "depthInMax": {"N": "8.8"},
    }


def test_writes_lists_nulls_and_numbers(ddb):
    # C507: `readings` is a list of maps. A null is stored as NULL, a pair of floats
    # as a list of numbers, and a tuple as a list.
    seed(ddb)
    assert claim(ddb, TABLE, KEY, "a", NOW_S) == "claimed"
    fields = Outcome.no_flood().item_fields() | {
        "readings": READINGS,
        "pair": (1, 2.5),
    }
    assert write_result(ddb, TABLE, KEY, "a", fields) is True
    item = stored(ddb)
    assert item["readings"] == {
        "L": [
            {
                "M": {
                    "id": {"N": "1"},
                    "kind": {"S": "body"},
                    "landmark": {"S": "not_visible"},
                    "level": {"NULL": True},
                    "inches": {"NULL": True},
                    "used": {"BOOL": False},
                    "dropped": {"NULL": True},
                }
            },
            {
                "M": {
                    "id": {"N": "2"},
                    "kind": {"S": "wheel"},
                    "landmark": {"S": "rim_quarter"},
                    "level": {"S": "half_knee"},
                    "inches": {"L": [{"N": "7.7"}, {"N": "8.2"}]},
                    "used": {"BOOL": True},
                    "dropped": {"NULL": True},
                }
            },
        ]
    }
    assert item["pair"] == {"L": [{"N": "1"}, {"N": "2.5"}]}
    # And it reads back as it went in, numbers as decimals.
    back = TypeDeserializer().deserialize(item["readings"])
    assert back[1]["inches"] == [Decimal("7.7"), Decimal("8.2")]
    assert (back[0]["level"], back[0]["used"], back[1]["id"]) == (None, False, 2)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize(
    "shape",
    [lambda v: v, lambda v: [v], lambda v: {"a": [v]}],
    ids=["bare", "in-list", "in-map"],
)
def test_non_finite_number_raises_before_the_write(ddb, monkeypatch, bad, shape):
    # DynamoDB has no NaN or infinity. The update is built before it is sent, so a bad
    # number leaves the report as it was, still processing under the claim.
    seed(ddb)
    assert claim(ddb, TABLE, KEY, "a", NOW_S) == "claimed"
    before = stored(ddb)
    sent = []
    monkeypatch.setattr(ddb, "update_item", lambda **kwargs: sent.append(kwargs))
    fields = Outcome.no_flood().item_fields() | {"inches": shape(bad)}
    with pytest.raises(ValueError):
        write_result(ddb, TABLE, KEY, "a", fields)
    assert sent == []
    assert stored(ddb) == before
    assert stored(ddb)["status"] == {"S": "processing"}


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


def test_a_repeated_write_with_readings_is_its_own(ddb):
    # C82: a repeat of a write that carries `readings` finds this worker's token and
    # the status it wrote, so the check reads only those two, never the list.
    seed(ddb)
    assert claim(ddb, TABLE, KEY, "a", NOW_S) == "claimed"
    fields = Outcome.no_flood().item_fields() | {"readings": READINGS}
    assert write_result(ddb, TABLE, KEY, "a", fields) is True
    written = stored(ddb)
    assert write_result(ddb, TABLE, KEY, "a", fields) is True
    assert stored(ddb) == written
    # Another token never counts, with the same readings.
    assert write_result(ddb, TABLE, KEY, "b", fields) is False
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
