"""Tests for seed_spend.py: the recorded total is added once, never twice (C527).

check:py runs this file with the scripts' dependencies, moto among them. Alone, from
the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with "moto[dynamodb,ssm]==5.2.4"
        pytest -q backend/scripts/test_seed_spend.py
"""

from decimal import Decimal

import boto3
import pytest
import seed_spend
from moto import mock_aws

TABLE = "lusot-test-limits"
KEY = {"pk": {"S": "spend#meta"}}
SEED_UPDATE = {
    "TableName": TABLE,
    "Key": KEY,
    "UpdateExpression": "ADD #micro :n SET #seeded = :true",
    "ConditionExpression": "attribute_not_exists(#seeded)",
    "ExpressionAttributeNames": {"#micro": "micro_usd", "#seeded": "seeded"},
}


@pytest.fixture
def session(monkeypatch):
    """Moto's DynamoDB with the limits table, named by LIMITS_TABLE_NAME."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(name, "testing")
    monkeypatch.setenv("LIMITS_TABLE_NAME", TABLE)
    with mock_aws():
        session = boto3.Session(region_name="ap-southeast-1")
        session.client("dynamodb").create_table(
            TableName=TABLE,
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            ProvisionedThroughput={"ReadCapacityUnits": 2, "WriteCapacityUnits": 2},
        )
        yield session


def counter(session) -> dict | None:
    return session.client("dynamodb").get_item(TableName=TABLE, Key=KEY).get("Item")


def spy_seed(session, monkeypatch) -> list[tuple[dict, dict]]:
    """Record each DynamoDB client the script makes, with its UpdateItem calls."""
    made = []
    client = session.client

    def make(name, **kwargs):
        built = client(name, **kwargs)
        if name == "dynamodb":
            updates = []
            update_item = built.update_item

            def update(**call):
                updates.append(call)
                return update_item(**call)

            monkeypatch.setattr(built, "update_item", update)
            made.append((kwargs, updates))
        return built

    monkeypatch.setattr(session, "client", make)
    return made


@pytest.mark.parametrize(
    ("runs", "total"), [(0, "1.25"), (2, "1.255")], ids=["no-runs", "two-runs"]
)
def test_seed_adds_once_after_runs(session, monkeypatch, capsys, runs, total):
    # Runs between the deploy and the seed make the item with their ADDs, unseeded.
    # The seed adds the recorded total to theirs, whether or not they came first.
    ddb = session.client("dynamodb")
    for _ in range(runs):
        seed_spend.spend.record_spend(Decimal("0.0025"), "analysis", ddb=ddb)
    made = spy_seed(session, monkeypatch)
    assert seed_spend.main(["--usd", "1.25"], session=session) == 0
    # One UpdateItem, through a client with SPEND_CONFIG, every name a placeholder.
    ((config, updates),) = made
    assert config == {"config": seed_spend.spend.SPEND_CONFIG}
    assert updates == [
        SEED_UPDATE
        | {
            "ExpressionAttributeValues": {
                ":n": {"N": "1250000"},
                ":true": {"BOOL": True},
            }
        }
    ]
    assert capsys.readouterr().out == f"seeded the Meta spend counter: total ${total}\n"
    # No expiresAt: the counter never expires.
    seeded = KEY | {
        "micro_usd": {"N": str(seed_spend.spend.to_micro(Decimal(total)))},
        "seeded": {"BOOL": True},
    }
    assert counter(session) == seeded
    # A second seed changes nothing.
    assert seed_spend.main(["--usd", "5"], session=session) == 1
    assert counter(session) == seeded
    out, err = capsys.readouterr()
    assert out == ""
    assert err.startswith("already seeded")
    assert "spend add" in err


@pytest.mark.parametrize("usd", ["-0.01", "NaN", "Infinity", "abc"])
def test_seed_refuses_a_bad_amount(session, capsys, usd):
    assert seed_spend.main(["--usd", usd], session=session) == 2
    assert counter(session) is None
    assert "--usd" in capsys.readouterr().err


def test_seed_reports_aws_errors_by_code(session, monkeypatch, capsys):
    monkeypatch.setenv("LIMITS_TABLE_NAME", "lusot-no-such-table")
    assert seed_spend.main(["--usd", "0.42"], session=session) == 1
    out, err = capsys.readouterr()
    assert err.startswith(
        "AWS error in UpdateItem: ResourceNotFoundException (HTTP 400)"
    )
    assert "arn:" not in out + err
