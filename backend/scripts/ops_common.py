"""The operator scripts' shared helpers, in one copy (plan Task 8, review Minor 4).

The stack's name and region, C32's report id, Manila's fixed offset, the 180 s wait
for a seed, the lusot profile's session, the stack's outputs, the reports by id, and
how a script's main() ends on an error. guards.py keeps the sealed-path guard, the
output mask and the allow-lists.

Standard library only at import, and boto3 is imported only when a session is made,
so a script that imports this keeps its own header and lock. AWS clients come in as
arguments.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from datetime import timedelta, timezone

STACK = "lusot"  # samconfig's stack_name
REGION = "ap-southeast-1"
INDEX_NAME = "reportId-index"  # the reports table's, in the template
# C32's id, standalone: not inside a word and not run into more letters or digits, as
# scripts/check_account_ids.mjs anchors its hex runs. The output mask exempts only
# this token, so a 12-digit run around or inside other text is still masked.
REPORT_ID = re.compile(r"(?<![0-9A-Za-z_])r_[0-9a-f]{32}(?![0-9A-Za-z])")
# Manila's fixed offset: Windows has no tzdata, and the scripts don't install it (F15).
PHT = timezone(timedelta(hours=8))
WAIT_S = 180  # for a seeded report's final status


def lusot_session():
    """The lusot profile's session, always: a stray AWS_PROFILE could reach another
    account. boto3 is imported here, so importing this module doesn't need it."""
    import boto3

    return boto3.Session(profile_name="lusot", region_name=REGION)


def stack_outputs(session) -> dict[str, str]:
    """The lusot stack's outputs, by key: names and the API's URL, never a queue URL."""
    cloudformation = session.client("cloudformation")
    [stack] = cloudformation.describe_stacks(StackName=STACK)["Stacks"]
    return {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}


def items_by_id(ddb, table: str, report_id: str) -> list[dict]:
    """Every item with this report id, from reportId-index, every page.

    A global secondary index is eventually consistent only (Context7, DynamoDB's
    developer guide), so it can lag a write by a moment.
    """
    pages = ddb.get_paginator("query").paginate(
        TableName=table,
        IndexName=INDEX_NAME,
        KeyConditionExpression="#reportId = :id",
        ExpressionAttributeNames={"#reportId": "reportId"},
        ExpressionAttributeValues={":id": {"S": report_id}},
    )
    return [item for page in pages for item in page["Items"]]


def failure(exc: BaseException) -> str:
    """An error as the scripts print it: an AWS error's code and HTTP status, or the
    class name. Never a message, which can hold an ARN, a path or a URL."""
    response = getattr(exc, "response", None)
    if isinstance(response, dict) and "Error" in response:
        code = response["Error"].get("Code")
        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        return f"AWS error in {exc.operation_name}: {code} (HTTP {status})"
    return type(exc).__name__


def guarded(
    command: Callable[[], int],
    *,
    label: str = "failed",
    shown: tuple[type[BaseException], ...] = (),
    errors: tuple[type[BaseException], ...] = (),
) -> int:
    """Run a script's command as its main() does, and return its exit code.

    A guard's or argparse's SystemExit returns its code. An exception in `shown`,
    whose message the script wrote to be printed, ends in `label: <message>`. Any of
    `errors`, a ValueError, a KeyError or an OSError ends in `label: <failure(exc)>`,
    with no traceback. Anything else is a bug, and propagates.
    """
    from guards import say  # not at import: guards imports REPORT_ID from here

    try:
        return command()
    except SystemExit as exc:
        return exc.code
    except shown as exc:
        say(f"{label}: {exc}")
    except (ValueError, KeyError, OSError, *errors) as exc:
        say(f"{label}: {failure(exc)}")
    return 1


def counts(counter: Counter) -> str:
    """A counter as the scripts print it: "1 a, 2 b", by name."""
    return ", ".join(f"{n} {name}" for name, n in sorted(counter.items()))


def yes(flag: bool) -> str:
    return "yes" if flag else "no"
