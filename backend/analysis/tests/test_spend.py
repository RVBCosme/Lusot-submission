"""Tests for spend.py: the Meta spend counter (C527), against moto's DynamoDB.

`spend_contract.json` is shared with Ask Lusot's spend.ts, so both count the same way.
"""

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import boto3
import pytest
from botocore.exceptions import ClientError
from fakes import create_limits_table, fail_attempts, no_backoff
from moto import mock_aws

from lusot_analysis import spend

CONTRACT = json.loads(
    (Path(__file__).parent / "fixtures" / "spend_contract.json").read_text(
        encoding="utf-8"
    )
)
TABLE = "lusot-test-limits"
KEY = {"pk": {"S": "spend#meta"}}


@pytest.fixture
def ddb(monkeypatch):
    """Moto's DynamoDB with the limits table, named by LIMITS_TABLE_NAME."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(name, "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-southeast-1")
    monkeypatch.setenv("LIMITS_TABLE_NAME", TABLE)
    with mock_aws():
        client = boto3.client("dynamodb")
        create_limits_table(client, TABLE)
        yield client


def stored(ddb) -> dict | None:
    return ddb.get_item(TableName=TABLE, Key=KEY).get("Item")


def test_contract_cases():
    assert (spend.SPEND_PK, spend.SPEND_ATTR) == (
        CONTRACT["key"],
        CONTRACT["attribute"],
    )
    assert CONTRACT["cases"]
    for usd, micro in CONTRACT["cases"]:
        assert spend.to_micro(Decimal(usd)) == micro, usd


def test_cost_of_matches_the_smoke_prices():
    # smoke_upload.py's prices (dev.meta.ai, Oct 26), and transcription's $0.18 an hour.
    assert spend.cost_of(sam_images=1) == Decimal("0.0025")
    assert spend.cost_of(spark_input_tokens=1_000_000) == Decimal("1.25")
    assert spend.cost_of(spark_output_tokens=1_000_000) == Decimal("4.25")
    assert spend.cost_of(audio_seconds=3600) == Decimal("0.18")
    assert spend.cost_of(audio_seconds=1) == Decimal("0.00005")
    assert spend.cost_of() == 0
    # The level case: 7 SAM phrases and one judge of 1,000 and 200 tokens.
    run = spend.cost_of(sam_images=7, spark_input_tokens=1000, spark_output_tokens=200)
    assert run == Decimal("0.0196")
    # About 3 times a typical judge, so an unreported count runs over, never under.
    unreported = spend.SPARK_TOKENS_IF_UNREPORTED
    assert unreported == (20_000, 4_000)
    assert spend.cost_of(
        spark_input_tokens=unreported[0], spark_output_tokens=unreported[1]
    ) == Decimal("0.042")


def test_record_spend_adds_atomically_and_returns_the_total(ddb, monkeypatch, caplog):
    updates = []
    update_item = ddb.update_item

    def update(**kwargs):
        updates.append(kwargs)
        return update_item(**kwargs)

    monkeypatch.setattr(ddb, "update_item", update)
    assert spend.record_spend(Decimal("0.0025"), "test-a", ddb=ddb) == Decimal("0.0025")
    total = spend.record_spend(Decimal("0.0025"), "test-b", ddb=ddb, table=TABLE)
    assert total == Decimal("0.005")
    # One atomic ADD each, never a read and a write, so racing runs can't lose one.
    assert (
        updates
        == [
            {
                "TableName": TABLE,
                "Key": KEY,
                "UpdateExpression": "ADD #micro :n",
                "ExpressionAttributeNames": {"#micro": "micro_usd"},
                "ExpressionAttributeValues": {":n": {"N": "2500"}},
                "ReturnValues": "UPDATED_NEW",
            }
        ]
        * 2
    )
    # No expiresAt, so the item never expires, and no source: that goes to the log.
    assert stored(ddb) == KEY | {"micro_usd": {"N": "5000"}}
    lines = [
        json.loads(r.getMessage()) for r in caplog.records if r.name == "lusot.spend"
    ]
    assert lines == [
        {"spend_source": "test-a", "spend_usd": "0.0025", "spend_total_usd": "0.0025"},
        {"spend_source": "test-b", "spend_usd": "0.0025", "spend_total_usd": "0.005"},
    ]


def test_record_spend_never_undercounts(ddb):
    # A fraction of a micro-dollar is counted as a whole one.
    assert spend.record_spend(Decimal("0.0000001"), "test", ddb=ddb) == Decimal(
        "0.000001"
    )


def test_missing_item_totals_zero(ddb, monkeypatch):
    reads = []
    get_item = ddb.get_item

    def read(**kwargs):
        reads.append(kwargs)
        return get_item(**kwargs)

    monkeypatch.setattr(ddb, "get_item", read)
    assert spend.spend_total(ddb=ddb) == Decimal(0)
    # Strongly consistent, so a check right after another run's ADD sees it.
    assert reads == [
        {
            "TableName": TABLE,
            "Key": KEY,
            "ProjectionExpression": "#micro",
            "ExpressionAttributeNames": {"#micro": "micro_usd"},
            "ConsistentRead": True,
        }
    ]
    assert stored(ddb) is None  # reading never makes the item
    spend.record_spend(Decimal("0.37"), "test", ddb=ddb)
    assert spend.spend_total(ddb=ddb, table=TABLE) == Decimal("0.37")


def test_spend_config_bounds_each_attempt(ddb, monkeypatch):
    config = spend.SPEND_CONFIG
    assert (config.connect_timeout, config.read_timeout) == (1, 1)
    # Five attempts in all, the first one included.
    assert config.retries == {"mode": "standard", "total_max_attempts": 5}
    built = []
    client = boto3.client

    def build(*args, **kwargs):
        built.append(client(*args, **kwargs))
        return built[-1]

    monkeypatch.setattr(spend.boto3, "client", build)
    spend.record_spend(Decimal("0.0025"), "test")
    assert spend.spend_total() == Decimal("0.0025")
    assert len(built) == 2  # one client each, as neither was given one
    for made in built:
        assert made.meta.service_model.service_name == "dynamodb"
        assert (made.meta.config.connect_timeout, made.meta.config.read_timeout) == (
            1,
            1,
        )
        assert made.meta.config.retries == {
            "mode": "standard",
            "total_max_attempts": 5,
        }
    # botocore's own retry handler stops after the fifth throttled attempt.
    monkeypatch.setattr(spend.boto3, "client", client)
    no_backoff(monkeypatch)
    throttled = boto3.client("dynamodb", config=config)
    attempts = fail_attempts(throttled, "UpdateItem", "ThrottlingException", 400)
    with pytest.raises(ClientError, match="ThrottlingException"):
        spend.record_spend(Decimal("0.0025"), "test", ddb=throttled)
    assert attempts == ["failed"] * 5
    assert spend.spend_total(ddb=ddb) == Decimal("0.0025")


def test_cli_add_and_total(ddb, capsys):
    session = boto3.Session(region_name="ap-southeast-1")
    add = ["add", "--usd", "0.37", "--source", "manual-test"]
    assert spend.main(add, session=session) == 0
    assert (
        spend.main(
            ["add", "--usd", "0.0025", "--source", "manual-test"], session=session
        )
        == 0
    )
    assert spend.main(["total"], session=session) == 0
    assert capsys.readouterr().out.splitlines() == [
        "added $0.37 from manual-test: total $0.37",
        "added $0.0025 from manual-test: total $0.3725",
        "total $0.3725",
    ]
    # Only a positive, finite amount is added: the counter never goes down.
    for usd in ("0", "-0.37", "NaN", "Infinity", "abc"):
        bad = ["add", "--usd", usd, "--source", "manual-test"]
        assert spend.main(bad, session=session) == 2, usd
        assert "--usd" in capsys.readouterr().err
    assert spend.spend_total(ddb=ddb) == Decimal("0.3725")


def test_cli_reports_aws_errors_by_code(ddb, monkeypatch, capsys):
    monkeypatch.setenv("LIMITS_TABLE_NAME", "lusot-no-such-table")
    session = boto3.Session(region_name="ap-southeast-1")
    assert spend.main(["total"], session=session) == 1
    out, err = capsys.readouterr()
    assert err.startswith("AWS error in GetItem: ResourceNotFoundException (HTTP 400)")
    assert "arn:" not in out + err


def test_scripts_find_the_deployed_table(monkeypatch):
    # LIMITS_TABLE_NAME when set, as in the Lambda; otherwise the lusot stack's table.
    monkeypatch.delenv("LIMITS_TABLE_NAME", raising=False)
    asked = []

    class CloudFormation:
        def describe_stack_resource(self, **kwargs):
            asked.append(kwargs)
            return {"StackResourceDetail": {"PhysicalResourceId": "lusot-Limits-X"}}

    session = SimpleNamespace(
        client=lambda name: {"cloudformation": CloudFormation()}[name]
    )
    assert spend.deployed_limits_table(session) == "lusot-Limits-X"
    assert asked == [{"StackName": "lusot", "LogicalResourceId": "LimitsTable"}]
    monkeypatch.setenv("LIMITS_TABLE_NAME", "lusot-given")
    assert spend.deployed_limits_table(session) == "lusot-given"
    assert len(asked) == 1
