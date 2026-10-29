"""Tests for set_spend_stop.py: the stop rises to $140, never above it (C528).

check:py runs this file with the scripts' dependencies, moto among them. Alone, from
the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with "moto[dynamodb,ssm]==5.2.4"
        pytest -q backend/scripts/test_set_spend_stop.py
"""

import boto3
import pytest
import set_spend_stop
from moto import mock_aws

TABLE = "lusot-test-limits"
KEY = {"pk": {"S": "spend#meta"}}
STOP = "/lusot/spend/stop-usd"


@pytest.fixture
def session(monkeypatch):
    """Moto's DynamoDB and SSM: the limits table, and the template's $60 stop."""
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
        session.client("ssm").put_parameter(Name=STOP, Value="60", Type="String")
        yield session


def spent(session, micro: int) -> None:
    session.client("dynamodb").put_item(
        TableName=TABLE, Item=KEY | {"micro_usd": {"N": str(micro)}}
    )


def stop(session) -> str:
    return session.client("ssm").get_parameter(Name=STOP)["Parameter"]["Value"]


def test_raises_the_stop_to_140(session, capsys):
    spent(session, 41_500_000)
    assert set_spend_stop.main(["--usd", "140"], session=session) == 0
    assert stop(session) == "140"
    assert capsys.readouterr().out == f"{STOP}: 60 -> 140 (spent so far $41.5)\n"
    # With no counter yet, the total is 0, and a stop at the total is allowed.
    session.client("dynamodb").delete_item(TableName=TABLE, Key=KEY)
    assert set_spend_stop.main(["--usd", "60"], session=session) == 0
    assert stop(session) == "60"
    spent(session, 60_000_000)
    assert set_spend_stop.main(["--usd", "60"], session=session) == 0


@pytest.mark.parametrize(
    ("usd", "why"),
    [
        ("140.01", "above 140"),
        ("150", "above 140"),
        ("61.99", "below the $62 spent"),
        ("0", "below the $62 spent"),
        ("NaN", "--usd"),
        ("Infinity", "--usd"),
        ("abc", "--usd"),
    ],
)
def test_refuses_above_140_or_below_the_total(session, capsys, usd, why):
    spent(session, 62_000_000)
    assert set_spend_stop.main(["--usd", usd], session=session) == 2
    assert stop(session) == "60"
    out, err = capsys.readouterr()
    assert out == ""
    assert why in err


def test_reports_aws_errors_by_code(session, capsys):
    session.client("ssm").delete_parameter(Name=STOP)
    assert set_spend_stop.main(["--usd", "140"], session=session) == 1
    out, err = capsys.readouterr()
    assert err.startswith("AWS error in GetParameter: ParameterNotFound (HTTP 400)")
    assert "arn:" not in out + err
