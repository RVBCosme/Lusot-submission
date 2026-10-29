"""Tests for seed_spend.py: the Meta spend counter is seeded once, never reset (C527).

check:py runs this file with the scripts' dependencies, moto among them. Alone, from
the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with "moto[dynamodb,ssm]==5.2.4"
        pytest -q backend/scripts/test_seed_spend.py
"""

import boto3
import pytest
import seed_spend
from moto import mock_aws

TABLE = "lusot-test-limits"
KEY = {"pk": {"S": "spend#meta"}}


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


def test_seed_writes_once(session, capsys):
    assert seed_spend.main(["--usd", "0.42"], session=session) == 0
    # No expiresAt: the counter never expires.
    assert counter(session) == KEY | {"micro_usd": {"N": "420000"}}
    assert capsys.readouterr().out == "seeded the Meta spend counter: total $0.42\n"
    # A second seed changes nothing.
    assert seed_spend.main(["--usd", "5"], session=session) == 3
    assert counter(session) == KEY | {"micro_usd": {"N": "420000"}}
    out, err = capsys.readouterr()
    assert out == ""
    assert "already holds $0.42" in err
    assert "spend add" in err


def test_seed_never_resets_a_started_counter(session, capsys):
    # A run recorded between the deploy and the seed: its ADD made the item, so the
    # seed leaves it, and the missed total goes in with `spend add` instead.
    session.client("dynamodb").put_item(
        TableName=TABLE, Item=KEY | {"micro_usd": {"N": "19600"}}
    )
    assert seed_spend.main(["--usd", "0.42"], session=session) == 3
    assert counter(session) == KEY | {"micro_usd": {"N": "19600"}}
    assert "already holds $0.0196" in capsys.readouterr().err


@pytest.mark.parametrize("usd", ["-0.01", "NaN", "Infinity", "abc"])
def test_seed_refuses_a_bad_amount(session, capsys, usd):
    assert seed_spend.main(["--usd", usd], session=session) == 2
    assert counter(session) is None
    assert "--usd" in capsys.readouterr().err


def test_seed_reports_aws_errors_by_code(session, monkeypatch, capsys):
    monkeypatch.setenv("LIMITS_TABLE_NAME", "lusot-no-such-table")
    assert seed_spend.main(["--usd", "0.42"], session=session) == 1
    out, err = capsys.readouterr()
    assert err.startswith("AWS error in PutItem: ResourceNotFoundException (HTTP 400)")
    assert "arn:" not in out + err
