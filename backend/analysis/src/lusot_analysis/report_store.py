"""The claim on a report, and the result writes under it (G2, C46).

A worker claims a report before any paid Meta call. While its lease is live, no other
delivery pays for the report, and once the result is written, none does. The lease
lasts 15 minutes. It outlasts the 180 s Lambda timeout, so a live worker never loses
it. It expires before the 1,080 s visibility timeout, so a message redelivered after
a crash can claim the report again. Every write after the claim needs the report
still `processing` under this worker's token (spec §3.1).

The SDK retries a call whose answer was lost, such as after a timeout or a 5xx, and
the repeat then fails its check against the first try's own result. So a failed check
that finds this worker's own claim or result already stored counts as a success.
Tokens are new for every delivery, so a match can't be another worker's (C82).
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
    fails, the old item says why. A final status gives "finished". `processing` under
    this token gives "claimed": the SDK repeated a claim whose first try succeeded
    (C82). Anything else, such as another worker's live lease, gives "leased".
    `token` must be new for every delivery, so a match is never another worker's.
    Other AWS errors propagate.
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
        old = exc.response.get("Item", {})
        status = old.get("status", {}).get("S")
        if status in FINAL_STATUSES:
            return "finished"
        if status == "processing" and old.get("claimToken") == {"S": token}:
            return "claimed"  # this claim's own first try (C82)
        return "leased"
    return "claimed"


def write_result(
    ddb,
    table: str,
    key: Mapping[str, dict],
    token: str,
    fields: Mapping[str, str | bool | int | float | Mapping[str, int]],
) -> bool:
    """Set every field in one conditional write, under this worker's claim.

    The write needs the report `processing` under `token`. If that check fails but
    the item holds this token and the status being written, the SDK repeated a write
    whose first try succeeded, so it returns True (C82). Otherwise the lease was
    lost: nothing is written, and it returns False. Other AWS errors propagate.
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
            ReturnValuesOnConditionCheckFailure="ALL_OLD",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != _CHECK_FAILED:
            raise
        old = exc.response.get("Item", {})
        own_token = old.get("claimToken") == {"S": token}
        own_status = old.get("status") == {"S": fields.get("status")}
        return own_token and own_status  # this write's own first try (C82)
    return True


def _attribute_value(value: str | bool | float | Mapping[str, int]) -> dict:
    """The field's typed DynamoDB value. A mapping's counts are typed the same way.

    A float, such as a geometry level's inches, is a number too (C308).
    """
    if isinstance(value, str):
        return {"S": value}
    if isinstance(value, bool):  # before int, because a bool is an int
        return {"BOOL": value}
    if isinstance(value, int):
        return {"N": str(value)}
    if isinstance(value, float):
        return {"N": str(value)}
    return {"M": {name: _attribute_value(count) for name, count in value.items()}}
