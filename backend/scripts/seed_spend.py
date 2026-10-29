# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["boto3[crt]>=1.43.120"]
# ///
"""Seed the Meta spend counter once, with the total spent before it existed (C527).

It runs right after the first deploy that carries the spend stop, with the recorded
total the tracker sends just before that deploy. The put is conditional on the item not
existing, so it seeds once and never resets the total: a counter that already exists,
even one a run started between the deploy and the seed, is left as it is, and the
script says so and exits 3. A missed amount then goes in with `spend add`
(docs/operations.md), never a second seed.

The counter's key, attribute and client settings come from backend/analysis's
spend.py, loaded by path through spend_loader.py, so the scripts and the Lambda share
one definition. The table is LIMITS_TABLE_NAME, or else the lusot stack's LimitsTable.
An AWS error is reported by its code and HTTP status only: its message can carry an
ARN, and an ARN carries the account ID.

boto3 comes with its CRT extra: the lusot profile signs in with `aws login`, and
botocore's provider for those credentials needs the CRT.

Usage, from the repo root: uv run backend/scripts/seed_spend.py --usd 0.42
Exit codes: 0 seeded; 1 an AWS error; 2 a bad --usd; 3 already seeded, nothing written.
"""

from __future__ import annotations

import argparse
import sys

from botocore.exceptions import BotoCoreError, ClientError
from spend_loader import load_spend

spend = load_spend()


def main(argv: list[str] | None = None, *, session=None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed the Meta spend counter once (C527); it never resets it."
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
            ddb.put_item(
                TableName=table,
                Item={
                    "pk": {"S": spend.SPEND_PK},
                    spend.SPEND_ATTR: {"N": str(spend.to_micro(usd))},
                },
                ConditionExpression="attribute_not_exists(#pk)",
                ExpressionAttributeNames={"#pk": "pk"},
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            total = spend.spend_total(ddb=ddb, table=table)
            print(
                f"the Meta spend counter already holds ${total}: nothing written."
                " Add a missed amount with `spend add` (docs/operations.md), never"
                " a second seed.",
                file=sys.stderr,
            )
            return 3
        total = spend.spend_total(ddb=ddb, table=table)
    except (BotoCoreError, ClientError) as exc:
        print(spend.aws_error(exc), file=sys.stderr)
        return 1
    print(f"seeded the Meta spend counter: total ${total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
