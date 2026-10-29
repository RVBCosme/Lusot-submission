"""The Meta spend counter and its stop (C527, C528).

Every paid Meta call adds its cost to one counter in the limits table, as whole
micro-dollars rounded up, so the count runs over, never under. The analysis handler
reads it before any Meta call and pauses model calls once it reaches the stop in
/lusot/spend/stop-usd. The item has no expiresAt, so it never expires.

Only a seeded counter is read. seed_spend.py adds the total spent before the counter
existed and sets `seeded`, once. Until then spend_total raises SpendUnseeded, so a new
or re-created table reads as unreadable, never as $0. A run's ADD before the seed may
make the item, still unseeded.

Standard library and boto3 only, so backend/scripts can load this file by path. Ask
Lusot's spend.ts counts the same way, and both test against spend_contract.json.

A small CLI adds an amount a run couldn't write, or prints the total, with the lusot
profile's credentials. The stop never moves to cover a missed amount: the amount is
added to the counter instead. From the repo root (PowerShell; the CRT is for the
profile's `aws login` credentials):
    uv run --directory backend/analysis --with "botocore[crt]==1.43.120"
        python -m lusot_analysis.spend add --usd 0.37 --source manual-<who>
    uv run ... python -m lusot_analysis.spend total
Exit codes: 0 done; 1 an AWS error, or `total` on an unseeded counter; 2 a bad --usd.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from decimal import ROUND_CEILING, Decimal, InvalidOperation

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

SPEND_PK = "spend#meta"  # the counter's key in the limits table
SPEND_ATTR = "micro_usd"  # its total, in whole micro-dollars
SPEND_SEEDED_ATTR = "seeded"  # set once by seed_spend.py; only a seeded total is read
SPEND_STOP_PARAM = "/lusot/spend/stop-usd"  # the stop, in USD (the template's)
STACK = "lusot"  # samconfig's stack_name
REGION = "ap-southeast-1"

# USD per unit, from docs/research/2026-10-26-verification-notes.md (dev.meta.ai,
# Oct 26), as smoke_upload.py had them. Transcription is charged by whole seconds.
PRICES = {
    "sam_image": Decimal("2.50") / 1000,
    "spark_input_token": Decimal("1.25") / 1_000_000,
    "spark_output_token": Decimal("4.25") / 1_000_000,
    "audio_second": Decimal("0.18") / 3600,
}
# Charged for a judge whose usage Meta didn't report: about $0.042, about 3 times a
# typical judge, so the count runs over, never under (the tracker's ruling, Oct 30).
SPARK_TOKENS_IF_UNREPORTED = (20_000, 4_000)  # input, output

# Each attempt is bounded at 1 s to connect and 1 s to read, and standard mode makes 5
# attempts in all, retrying a throttle (which DynamoDB never applied) and a 5xx or a
# dropped connection (where the ADD may have landed, so the count can run over by a
# run's cost, never under). Worst case about 25 s, inside the handler's 30 s margin.
# total_max_attempts counts the first attempt; Config's max_attempts counts retries
# only, so max_attempts=5 would make 6 attempts.
SPEND_CONFIG = Config(
    connect_timeout=1,
    read_timeout=1,
    retries={"mode": "standard", "total_max_attempts": 5},
)

logger = logging.getLogger("lusot.spend")
logger.setLevel(logging.INFO)  # Lambda's text log format otherwise drops INFO


class SpendUnseeded(RuntimeError):
    """The counter's item is missing or has no `seeded`: seed_spend.py hasn't run."""


def cost_of(
    *,
    sam_images: int = 0,
    spark_input_tokens: int = 0,
    spark_output_tokens: int = 0,
    audio_seconds: int = 0,
) -> Decimal:
    """What these units cost at PRICES, in USD."""
    return (
        PRICES["sam_image"] * sam_images
        + PRICES["spark_input_token"] * spark_input_tokens
        + PRICES["spark_output_token"] * spark_output_tokens
        + PRICES["audio_second"] * audio_seconds
    )


def to_micro(usd: Decimal) -> int:
    """`usd` in whole micro-dollars, rounded up, so a cost is never undercounted."""
    return int((usd * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


def rounded_up(usd: Decimal) -> Decimal:
    """`usd` as the counter records it: rounded up to a whole micro-dollar."""
    return _usd(to_micro(usd))


def _usd(micro: int | str) -> Decimal:
    return Decimal(micro) / 1_000_000


def _table(table: str | None) -> str:
    return os.environ["LIMITS_TABLE_NAME"] if table is None else table


def record_spend(
    usd: Decimal, source: str, *, ddb=None, table: str | None = None
) -> Decimal:
    """Add `usd` to the counter in one atomic ADD, and return the new total in USD.

    `source` says who spent it, and goes to the log line only. Without `ddb`, a new
    client with SPEND_CONFIG is made.
    """
    client = boto3.client("dynamodb", config=SPEND_CONFIG) if ddb is None else ddb
    micro = to_micro(usd)
    response = client.update_item(
        TableName=_table(table),
        Key={"pk": {"S": SPEND_PK}},
        UpdateExpression="ADD #micro :n",
        ExpressionAttributeNames={"#micro": SPEND_ATTR},
        ExpressionAttributeValues={":n": {"N": str(micro)}},
        ReturnValues="UPDATED_NEW",
    )
    total = _usd(response["Attributes"][SPEND_ATTR]["N"])
    line = {
        "spend_source": source,
        "spend_usd": str(_usd(micro)),
        "spend_total_usd": str(total),
    }
    logger.info(json.dumps(line))
    return total


def spend_total(*, ddb=None, table: str | None = None) -> Decimal:
    """The counter's total in USD, read strongly consistent.

    A missing item, or one with no `seeded`, raises SpendUnseeded: never $0.
    """
    client = boto3.client("dynamodb", config=SPEND_CONFIG) if ddb is None else ddb
    item = client.get_item(
        TableName=_table(table),
        Key={"pk": {"S": SPEND_PK}},
        ProjectionExpression="#micro, #seeded",
        ExpressionAttributeNames={"#micro": SPEND_ATTR, "#seeded": SPEND_SEEDED_ATTR},
        ConsistentRead=True,
    ).get("Item")
    if item is None or SPEND_SEEDED_ATTR not in item:
        raise SpendUnseeded(
            "unseeded: the Meta spend counter has no seed yet; run seed_spend.py"
            " (docs/operations.md)"
        )
    return _usd(item[SPEND_ATTR]["N"])


# For the CLI and the operator scripts in backend/scripts.


def operator_session() -> boto3.Session:
    """Always the lusot profile: a stray AWS_PROFILE could reach another account."""
    return boto3.Session(profile_name="lusot", region_name=REGION)


def deployed_limits_table(session) -> str:
    """LIMITS_TABLE_NAME when set, or else the deployed stack's limits table."""
    name = os.environ.get("LIMITS_TABLE_NAME")
    if name:
        return name
    return session.client("cloudformation").describe_stack_resource(
        StackName=STACK, LogicalResourceId="LimitsTable"
    )["StackResourceDetail"]["PhysicalResourceId"]


def parse_usd(text: str) -> Decimal | None:
    """`text` as a finite amount in USD, or None when it isn't one."""
    try:
        usd = Decimal(text)
    except InvalidOperation:
        return None
    return usd if usd.is_finite() else None


def aws_error(exc: Exception) -> str:
    """An AWS error by its code and HTTP status, never its message.

    The message can carry an ARN, and an ARN carries the account ID.
    """
    if isinstance(exc, ClientError):
        code = exc.response["Error"]["Code"]
        status = exc.response["ResponseMetadata"]["HTTPStatusCode"]
        return f"AWS error in {exc.operation_name}: {code} (HTTP {status})"
    return f"AWS error: {type(exc).__name__}"


def main(argv: list[str] | None = None, *, session=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m lusot_analysis.spend",
        description="Add to the Meta spend counter, or print its total (C527).",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser(
        "add", help="add an amount a run couldn't write, and print the new total"
    )
    add.add_argument("--usd", required=True, help="the amount in USD, such as 0.37")
    add.add_argument("--source", required=True, help="who adds it, such as manual-rene")
    commands.add_parser("total", help="print the counter's total")
    args = parser.parse_args(argv)
    if args.command == "add":
        usd = parse_usd(args.usd)
        if usd is None or usd <= 0:
            print(
                "--usd must be a positive amount in USD, such as 0.37", file=sys.stderr
            )
            return 2
    try:
        session = operator_session() if session is None else session
        ddb = session.client("dynamodb", config=SPEND_CONFIG)
        table = deployed_limits_table(session)
        if args.command == "add":
            total = record_spend(usd, args.source, ddb=ddb, table=table)
            print(f"added ${usd} from {args.source}: total ${total}")
        else:
            print(f"total ${spend_total(ddb=ddb, table=table)}")
    except (BotoCoreError, ClientError) as exc:
        print(aws_error(exc), file=sys.stderr)
        return 1
    except SpendUnseeded as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
