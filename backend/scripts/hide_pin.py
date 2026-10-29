# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["boto3[crt]>=1.43.120"]
# ///
"""Hide one pin from the map, without deleting it (MS9's N9; MS4 spec §4.6; Task 8).

Flags never hide a pin on their own (MS4-Q3); this is Rene's tool. It sets
`visibleUntil` to now on the live or demo pin with this report id, so the map, nearby
and the feed stop showing it, and the item, its photos and its flags stay until
expiresAt. Any other mode isn't a pin, so it is refused. The id is found through the
lusot stack's reportId-index, and nothing from lusot-data is read.

boto3 comes with its CRT extra: the lusot profile signs in with `aws login`, and
botocore's provider for those credentials needs the CRT. Output: the report id and
its outcome, through guards.say.

Usage: uv run backend/scripts/hide_pin.py <report id>
Exit codes: 0 hidden; 1 not found, or an AWS error; 2 refused (not a report id, or
not a live or demo pin).
"""

from __future__ import annotations

import argparse
import re
import time
from collections.abc import Callable, Sequence

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from guards import failure, items_by_id, say, stack_outputs

REGION = "ap-southeast-1"
REPORT_ID = re.compile(r"r_[0-9a-f]{32}")  # C32
PIN_MODES = ("live", "demo")


def main(
    argv: Sequence[str] | None = None,
    *,
    session=None,
    clock: Callable[[], float] = time.time,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("id", help="the pin's report id")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code
    if REPORT_ID.fullmatch(args.id) is None:
        say("refused: that isn't a report id")
        return 2
    try:
        session = session or boto3.Session(profile_name="lusot", region_name=REGION)
        table = stack_outputs(session).get("TableName")
        if table is None:
            say("failed: the stack has no TableName output")
            return 1
        ddb = session.client("dynamodb")
        items = items_by_id(ddb, table, args.id)
        if not items:
            say(f"{args.id}: not found")
            return 1
        modes = sorted({item["mode"]["S"] for item in items})
        if any(mode not in PIN_MODES for mode in modes):
            say(f"refused: {args.id} is a {modes[0]} report, not a live or demo pin")
            return 2
        now = int(clock())
        for item in items:
            ddb.update_item(
                TableName=table,
                Key={"pk": item["pk"], "sk": item["sk"]},
                UpdateExpression="SET #visibleUntil = :now",
                # Never a new item from a key that has gone meanwhile.
                ConditionExpression="attribute_exists(#pk)",
                ExpressionAttributeNames={"#visibleUntil": "visibleUntil", "#pk": "pk"},
                ExpressionAttributeValues={":now": {"N": str(now)}},
            )
    except (BotoCoreError, ClientError) as exc:
        say(f"failed: {failure(exc)}")
        return 1
    say(f"{args.id}: hidden ({modes[0]}), visibleUntil set to now; nothing deleted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
