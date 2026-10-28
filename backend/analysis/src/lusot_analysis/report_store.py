"""The claim on a report, and the result writes under it (G2, C46).

A worker claims a report before any paid Meta call. While its lease is live, no other
delivery pays for the report, and once the result is written, none does. The lease
lasts 15 minutes. It outlasts the 180 s Lambda timeout, so a live worker never loses
it. It expires before the 1,080 s visibility timeout, so a message redelivered after
a crash can claim the report again. Every write after the claim needs the report
still `processing` under this worker's token (spec §3.1).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from botocore.exceptions import ClientError

LEASE_S = 900  # 15 minutes (C46)
FINAL_STATUSES = frozenset({"done", "refused", "failed"})
ClaimState = Literal["claimed", "finished", "leased"]

_CHECK_FAILED = "ConditionalCheckFailedException"


def claim(
    ddb, table: str, key: Mapping[str, dict], token: str, now_s: int
) -> ClaimState:
    """Claim the report for `token`, from `pending` or from an expired lease.

    One conditional write moves the report to `processing` and stamps the token and
    `now_s`. A lease expires only once it is more than LEASE_S old. If the check
    fails, the old item's status says why: a final status gives "finished", and
    anything else, such as another worker's live lease, gives "leased". Other AWS
    errors propagate.
    """
    try:
        ddb.update_item(
            TableName=table,
            Key=dict(key),
            UpdateExpression=(
                "SET #status = :processing, claimToken = :token, claimedAt = :now"
            ),
            ConditionExpression=(
                "#status = :pending OR (#status = :processing AND claimedAt < :expired)"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":processing": {"S": "processing"},
                ":token": {"S": token},
                ":now": {"N": str(now_s)},
                ":pending": {"S": "pending"},
                ":expired": {"N": str(now_s - LEASE_S)},
            },
            # A failed check returns the item, so its status needs no second read.
            ReturnValuesOnConditionCheckFailure="ALL_OLD",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != _CHECK_FAILED:
            raise
        # A missing item has no status, so it reads as leased. The failed check also
        # means a claim never creates a report.
        status = exc.response.get("Item", {}).get("status", {}).get("S")
        return "finished" if status in FINAL_STATUSES else "leased"
    return "claimed"


def write_result(
    ddb,
    table: str,
    key: Mapping[str, dict],
    token: str,
    fields: Mapping[str, str | bool | int | Mapping[str, int]],
) -> bool:
    """Set every field in one conditional write, under this worker's claim.

    The write needs the report `processing` under `token`. If that check fails, the
    lease was lost: nothing is written, and it returns False. Other AWS errors
    propagate.
    """
    # Every name goes through a placeholder: `status` and `level` are reserved words.
    names = {"#status": "status"}
    values = {":processing": {"S": "processing"}, ":token": {"S": token}}
    sets = []
    for i, (name, value) in enumerate(fields.items()):
        names[f"#f{i}"] = name
        values[f":f{i}"] = _attribute_value(value)
        sets.append(f"#f{i} = :f{i}")
    try:
        ddb.update_item(
            TableName=table,
            Key=dict(key),
            UpdateExpression="SET " + ", ".join(sets),
            ConditionExpression="#status = :processing AND claimToken = :token",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != _CHECK_FAILED:
            raise
        return False
    return True


def _attribute_value(value: str | bool | int | Mapping[str, int]) -> dict:
    """The field's typed DynamoDB value. A mapping's counts are typed the same way."""
    if isinstance(value, str):
        return {"S": value}
    if isinstance(value, bool):  # before int, because a bool is an int
        return {"BOOL": value}
    if isinstance(value, int):
        return {"N": str(value)}
    return {"M": {name: _attribute_value(count) for name, count in value.items()}}
