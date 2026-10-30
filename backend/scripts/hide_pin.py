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
import time
from collections.abc import Callable, Sequence

from botocore.exceptions import BotoCoreError, ClientError
from guards import say
from ops_common import REPORT_ID, guarded, items_by_id, lusot_session, stack_outputs

PIN_MODES = ("live", "demo")


def main(
    argv: Sequence[str] | None = None,
    *,
    session=None,
    clock: Callable[[], float] = time.time,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("id", help="the pin's report id")

    def command() -> int:
        args = parser.parse_args(argv)
        return hide(args.id, session, clock)

    return guarded(command, errors=(BotoCoreError, ClientError))


def hide(report_id: str, session, clock) -> int:
    if REPORT_ID.fullmatch(report_id) is None:
        say("refused: that isn't a report id")
        return 2
    session = session or lusot_session()
    table = stack_outputs(session).get("TableName")
    if table is None:
        say("failed: the stack has no TableName output")
        return 1
    ddb = session.client("dynamodb")
    items = items_by_id(ddb, table, report_id)
    if not items:
        say(f"{report_id}: not found")
        return 1
    modes = {item["mode"]["S"] for item in items}
    others = sorted(modes - set(PIN_MODES))
    if others:  # named, so a demo id with a private item reads as private
        say(f"refused: {report_id} is a {others[0]} report, not a live or demo pin")
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
    shown = "/".join(sorted(modes))
    say(f"{report_id}: hidden ({shown}), visibleUntil set to now; nothing deleted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
