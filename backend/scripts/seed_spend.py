# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["boto3[crt]>=1.43.120"]
# ///
"""Seed the Meta spend counter once, with the total spent before it existed (C527).

It runs right after the first deploy that carries the spend stop, with the recorded
total the tracker sends just before that deploy. One UpdateItem adds that total and
sets `seeded`, on the condition that `seeded` isn't set yet. So it adds the total once,
whether or not a run's ADD made the item between the deploy and the seed, and never
twice: a second seed changes nothing, says `already seeded` and exits 1. A missed
amount then goes in with `spend add` (docs/operations.md), never a second seed. Until
the seed, the handler reads the counter as unseeded and pauses model calls.

The counter's key, attributes and client settings come from backend/analysis's
spend.py, loaded by path through spend_loader.py, so the scripts and the Lambda share
one definition. The table is LIMITS_TABLE_NAME, or else the lusot stack's LimitsTable.
An AWS error is reported by its code and HTTP status only: its message can carry an
ARN, and an ARN carries the account ID.

boto3 comes with its CRT extra: the lusot profile signs in with `aws login`, and
botocore's provider for those credentials needs the CRT.

Usage, from the repo root: uv run backend/scripts/seed_spend.py --usd 0.42
Exit codes: 0 seeded; 1 an AWS error, or already seeded and nothing written; 2 a bad
--usd.
"""

from __future__ import annotations

import argparse
import sys

from botocore.exceptions import BotoCoreError, ClientError
from spend_loader import load_spend

spend = load_spend()


def main(argv: list[str] | None = None, *, session=None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed the Meta spend counter once (C527); it never adds twice."
    )
    parser.add_argument(
        "--usd", required=True, help="the total spent before the counter, such as 0.42"
    )
    args = parser.parse_args(argv)
    usd = spend.parse_usd(args.usd)
    if usd is None or usd < 0:
        print("--usd must be an amount in USD, such as 0.42", file=sys.stderr)
        return 2
    try:
        session = spend.operator_session() if session is None else session
        ddb = session.client("dynamodb", config=spend.SPEND_CONFIG)
        table = spend.deployed_limits_table(session)
        try:
            ddb.update_item(
                TableName=table,
                Key={"pk": {"S": spend.SPEND_PK}},
                UpdateExpression="ADD #micro :n SET #seeded = :true",
                ConditionExpression="attribute_not_exists(#seeded)",
                ExpressionAttributeNames={
                    "#micro": spend.SPEND_ATTR,
                    "#seeded": spend.SPEND_SEEDED_ATTR,
                },
                ExpressionAttributeValues={
                    ":n": {"N": str(spend.to_micro(usd))},
                    ":true": {"BOOL": True},
                },
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            print(
                "already seeded: nothing written. Add a missed amount with"
                " `spend add` (docs/operations.md), never a second seed.",
                file=sys.stderr,
            )
            return 1
        total = spend.spend_total(ddb=ddb, table=table)
    except (BotoCoreError, ClientError) as exc:
        print(spend.aws_error(exc), file=sys.stderr)
        return 1
    print(f"seeded the Meta spend counter: total ${total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
