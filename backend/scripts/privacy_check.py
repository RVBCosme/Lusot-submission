# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "boto3[crt]>=1.43.120",
#     "httpx>=0.28.1",
#     "numpy>=2.5.4",
#     "opencv-python-headless>=4.14.0.94,<5",
# ]
# ///
"""The privacy check on the deployed stack: P5 to P11, P14 and the log scan (MS7 plan Task 5).

Spec §4.3. Each check returns its problems, empty when it passes, and the run prints one
line per row with counts only, through harden.say:
- P5 (W27): two synthetic live items, hidden by their own times, are absent from the
  nearby read, the map read and the feed, and the one past its expiresAt reads 404
  (MS4's C526). Both are deleted afterwards, even when a check fails.
- P8: the queues keep messages 6 and 4 days (C525) and the dead-letter queue is empty;
  the bucket's lifecycle rules are raw/ 1 day, blurred/ and overlay/ 7, demo/ 60, and
  nothing else (samples/ is exempt by design); TTL is on in both tables; both log
  groups keep 14 days.
- P9: neither API's stage keeps access logs, the bucket keeps no server access logs, and
  no trail records the bucket's data events.
- P11: the feed and the map read carry only public pin fields, to 4 decimals, and the
  feed's notice is the screen line, word for word; the feed API allows any origin for
  GET only, and the app API names its origins and exposes Retry-After.
- P14 and the log scan: the analysis and API logs since --since hold no IP address, no
  test point as a pair, no device id from the runs' records, no base64 JPEG and no
  part of the Meta key (read from MODEL_API_KEY, never printed). Only counts come back.
- the raw/ photos left for the runs' reports, and the bucket's top-level prefix counts.

fetch-p3 OUT copies, for P3's look by hand, each run report's blurred/ and overlay/
photo, the demo/ photos and the samples/ copies into OUT, outside the repo, named by
ordinal (L#6-blurred.jpg), order or sample id, never by a key. It skips the samples
manifest's Set B composites, which leave out place and date (C512), since MS7 opens no
Set B photo. clear-p3 OUT deletes exactly those files.

It always uses the lusot profile. A report id, an S3 key, a queue URL, an ARN, an
address, a message's text or the key is never printed.

Usage: uv run backend/scripts/privacy_check.py [check] [--since ISO] [--ids PATH ...]
           [--inches-shown]
       uv run backend/scripts/privacy_check.py fetch-p3 OUT --ids PATH ...
       uv run backend/scripts/privacy_check.py clear-p3 OUT
Exit codes: 0 every check passed, or the copies were fetched or cleared; 1 a check
found a problem; 2 refused by a guard (a sealed or in-repo folder) or bad usage.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import time
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

import guards
import httpx
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import BotoCoreError, ClientError
from harden import (
    DEMO_EXTRA_FIELDS,
    OUTSIDE_POINT,
    PUBLIC_PIN_FIELDS,
    SMOKE_SPOT,
    api_urls,
    ipv4_client,
    load_records,
    say,
    server_now,
    server_offset,
    synthetic_item,
)
from ops_common import STACK, failure, guarded, lusot_session
from smoke_upload import CheckFailed, json_object, load_stack, object_exists
from switch_test import pin_reads

REPO = Path(__file__).resolve().parents[2]
EN_TS = REPO / "app" / "src" / "i18n" / "en.ts"
SCREEN_KEY = "layout.screenLine"
RETENTION = {"upload": "345600", "dead-letter": "518400"}  # C525
LIFECYCLE = {"raw/": 1, "blurred/": 7, "overlay/": 7, "demo/": 60}  # C510
EXEMPT = ("samples/",)  # kept while the sample button exists (MS4-Q11)
LOG_DAYS = 14
INCHES = frozenset(
    {"depthInMin", "depthInMax"}
)  # only once the release gate shows them
PHOTO_KINDS = ("blurred", "overlay")
SINCE_DEFAULT_H = 24
_IPV4 = re.compile(r"(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])")
# A whole token: an ARN's "ap-southeast-1::runtime" or a time such as 02:15:00 never counts.
_IPV6 = re.compile(
    r"(?<![0-9A-Za-z:.])[0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7}(?![0-9A-Za-z:.])"
)
_DECIMAL = re.compile(r"-?[0-9]+\.[0-9]+")
_DEMO_KEY = re.compile(r"demo/(blurred|overlay)/(r_[0-9a-f]{32})\.jpg")
_SAMPLE_ID = re.compile(r"s[0-9A-Za-z_-]{1,64}")
_FETCHED = re.compile(
    r"([A-Z]#[0-9]+-(blurred|overlay)|demo-[0-9]+-(blurred|overlay)|s[0-9A-Za-z_-]{1,64})\.jpg"
)


@dataclass(frozen=True)
class Needles:
    """What the log scan looks for, beside IP addresses and base64 JPEG data: the test
    points as pairs, the runs' device ids and the Meta key."""

    points: tuple[dict, ...] = (OUTSIDE_POINT, SMOKE_SPOT)
    devices: tuple[str, ...] = ()
    key: str = ""


def check_queues(sqs, queue_name: str, dlq_name: str) -> list[str]:
    """P8: the upload queue keeps messages 4 days and the dead-letter queue 6 (C525), so
    a message redriven in its first day is gone within 7; and the dead-letter queue is
    empty. A queue's URL holds the account ID, so it is never printed."""
    problems = []
    for label, name in (("upload", queue_name), ("dead-letter", dlq_name)):
        url = sqs.get_queue_url(QueueName=name)["QueueUrl"]
        attributes = sqs.get_queue_attributes(
            QueueUrl=url,
            AttributeNames=[
                "MessageRetentionPeriod",
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
            ],
        )["Attributes"]
        kept = attributes.get("MessageRetentionPeriod")
        if kept != RETENTION[label]:
            problems.append(
                f"the {label} queue keeps messages {kept} s, not {RETENTION[label]}"
            )
        if label == "dead-letter":
            held = sum(
                int(attributes.get(name, "0"))
                for name in (
                    "ApproximateNumberOfMessages",
                    "ApproximateNumberOfMessagesNotVisible",
                )
            )
            if held:
                problems.append(f"the dead-letter queue holds {held} messages")
    return problems


def check_lifecycle(s3, bucket: str) -> list[str]:
    """P8: raw/ 1 day, blurred/ and overlay/ 7, demo/'s 60-day backstop, and no other
    rule; samples/ is exempt by design, so a rule for it fails too."""
    try:
        rules = s3.get_bucket_lifecycle_configuration(Bucket=bucket).get("Rules", [])
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "NoSuchLifecycleConfiguration":
            raise
        rules = []
    problems, seen = [], set()
    for rule in rules:
        prefix = rule.get("Prefix", (rule.get("Filter") or {}).get("Prefix", ""))
        days = (rule.get("Expiration") or {}).get("Days")
        if prefix not in LIFECYCLE:
            exempt = " (samples/ is exempt by design)" if prefix in EXEMPT else ""
            problems.append(f"an unexpected rule for {prefix or 'every key'}{exempt}")
            continue
        seen.add(prefix)
        if rule.get("Status") != "Enabled":
            problems.append(f"the rule for {prefix} isn't enabled")
        elif days != LIFECYCLE[prefix]:
            problems.append(
                f"{prefix} expires after {days} days, not {LIFECYCLE[prefix]}"
            )
    problems += [f"no rule for {prefix}" for prefix in LIFECYCLE if prefix not in seen]
    return problems


def check_ttl(ddb, tables: dict[str, str]) -> list[str]:
    """P8: TTL is ENABLED on each table's named attribute."""
    problems = []
    for name, attribute in tables.items():
        found = ddb.describe_time_to_live(TableName=name).get(
            "TimeToLiveDescription", {}
        )
        if (found.get("TimeToLiveStatus"), found.get("AttributeName")) != (
            "ENABLED",
            attribute,
        ):
            problems.append(f"{name}'s TTL isn't enabled on {attribute}")
    return problems


def check_log_retention(logs, groups: list[str]) -> list[str]:
    """P8: each log group keeps 14 days."""
    problems = []
    for group in groups:
        found = [
            g
            for g in logs.describe_log_groups(logGroupNamePrefix=group).get(
                "logGroups", []
            )
            if g.get("logGroupName") == group
        ]
        if not found or found[0].get("retentionInDays") != LOG_DAYS:
            kept = found[0].get("retentionInDays", "forever") if found else "missing"
            problems.append(f"a log group keeps {kept}, not {LOG_DAYS} days")
    return problems


def check_access_logs(
    apigw, s3, cloudtrail, *, api_ids: tuple[str, str], bucket: str
) -> list[str]:
    """P9: no access log on either API's stage (the app's and the feed's), no server
    access logging on the bucket, and no trail with the bucket's data events."""
    problems = []
    for label, api_id in zip(("the app API", "the feed API"), api_ids, strict=True):
        for stage in apigw.get_stages(ApiId=api_id).get("Items", []):
            if (stage.get("AccessLogSettings") or {}).get("DestinationArn"):
                problems.append(
                    f"{label}'s stage {stage.get('StageName')} keeps access logs"
                )
    if "LoggingEnabled" in s3.get_bucket_logging(Bucket=bucket):
        problems.append("the bucket keeps server access logs")
    for trail in cloudtrail.describe_trails().get("trailList", []):
        selectors = cloudtrail.get_event_selectors(TrailName=trail["TrailARN"])
        if _records_bucket(selectors, bucket):
            problems.append("a trail records the bucket's data events")
    return problems


def _records_bucket(selectors: dict, bucket: str) -> bool:
    """Whether a trail's selectors take the bucket's object-level (data) events."""
    mine = f"arn:aws:s3:::{bucket}"
    for selector in selectors.get("EventSelectors") or []:
        for resource in selector.get("DataResources") or []:
            if resource.get("Type") == "AWS::S3::Object" and any(
                value in ("arn:aws:s3", "arn:aws:s3:::") or value.startswith(mine)
                for value in resource.get("Values", [])
            ):
                return True
    for selector in selectors.get("AdvancedEventSelectors") or []:
        fields = {f.get("Field"): f for f in selector.get("FieldSelectors", [])}
        if "AWS::S3::Object" not in (fields.get("resources.type") or {}).get(
            "Equals", []
        ):
            continue
        arns = fields.get("resources.ARN")
        if arns is None or any(
            value.startswith(mine) or mine.startswith(value)
            for value in arns.get("Equals", []) + arns.get("StartsWith", [])
        ):
            return True
    return False


def check_feed_cors(apigw, *, app_api_id: str, feed_api_id: str) -> list[str]:
    """P11 (MS4's C521): the feed API allows any origin for GET only, with no
    credentials, and every route is a GET; the app API names its origins and exposes
    Retry-After, which the app's poll reads (header names compared case-blind)."""
    problems = []
    feed = apigw.get_api(ApiId=feed_api_id).get("CorsConfiguration") or {}
    if feed.get("AllowOrigins") != ["*"]:
        problems.append("the feed API's AllowOrigins isn't exactly *")
    methods = {method.upper() for method in feed.get("AllowMethods", [])}
    if "GET" not in methods or methods - {"GET", "OPTIONS"}:
        problems.append("the feed API allows methods besides GET")
    if feed.get("AllowCredentials"):
        problems.append("the feed API allows credentials")
    routes = [
        route.get("RouteKey", "")
        for route in apigw.get_routes(ApiId=feed_api_id).get("Items", [])
    ]
    if not routes or any(not key.startswith("GET ") for key in routes):
        problems.append("the feed API has a route that isn't a GET")
    app = apigw.get_api(ApiId=app_api_id).get("CorsConfiguration") or {}
    if "*" in app.get("AllowOrigins", []):
        problems.append("the app API allows any origin")
    if "retry-after" not in {header.lower() for header in app.get("ExposeHeaders", [])}:
        problems.append("the app API doesn't expose Retry-After")
    return problems


def prefix_counts(s3, bucket: str) -> dict[str, int]:
    """Objects per top-level prefix, never a key."""
    counts: Counter = Counter()
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for entry in page.get("Contents", []):
            top, slash, _ = entry["Key"].partition("/")
            counts[f"{top}/" if slash else "(top level)"] += 1
    return dict(sorted(counts.items()))


def _too_precise(value: object) -> bool:
    """A coordinate with more than 4 decimals, or one that isn't a number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return True
    try:
        return Decimal(str(value)).as_tuple().exponent < -4
    except InvalidOperation:
        return True


def feed_problems(
    geojson: dict, *, screen_line: str, inches_shown: bool = False
) -> list[str]:
    """P11's feed rules: only public pin fields (less lat and lng, which sit in the
    geometry), coordinates to 4 decimals, no collection member besides type, features
    and notice, and a notice that is the screen line, word for word (MS4's S13)."""
    problems = []
    extra = sorted(set(geojson) - {"type", "features", "notice"})
    if extra:
        problems.append(f"the collection has other members: {', '.join(extra)}")
    if geojson.get("notice") != screen_line:
        problems.append("its notice isn't the screen line, word for word")
    allowed = (PUBLIC_PIN_FIELDS | (INCHES if inches_shown else frozenset())) - {
        "lat",
        "lng",
    }
    for n, feature in enumerate(geojson.get("features") or [], 1):
        outside = sorted(set((feature or {}).get("properties") or {}) - allowed)
        if outside:
            problems.append(
                f"feature {n} carries fields beyond a public pin's: {', '.join(outside)}"
            )
        coordinates = ((feature or {}).get("geometry") or {}).get("coordinates") or []
        if any(_too_precise(c) for c in coordinates):
            problems.append(f"feature {n} has a coordinate past 4 decimals")
    return problems


def map_problems(pins: list[dict], *, inches_shown: bool = False) -> list[str]:
    """P11's rules for GET /map/pins (C519): public pin fields only, where a demo pin
    may add its credit, place and event (C523), and coordinates to 4 decimals."""
    problems = []
    for n, found in enumerate(pins, 1):
        allowed = PUBLIC_PIN_FIELDS | (INCHES if inches_shown else frozenset())
        if found.get("mode") == "demo":
            allowed |= DEMO_EXTRA_FIELDS
        outside = sorted(set(found) - allowed)
        if outside:
            problems.append(
                f"pin {n} carries fields beyond a public pin's: {', '.join(outside)}"
            )
        if _too_precise(found.get("lat")) or _too_precise(found.get("lng")):
            problems.append(f"pin {n} has a coordinate past 4 decimals")
    return problems


def screen_line(path: Path = EN_TS) -> str:
    """The screen line, from MS5's English string table."""
    text = path.read_text(encoding="utf-8")
    match = re.search(
        re.escape(f"'{SCREEN_KEY}'") + r":\s*\{\s*text:\s*'([^']*)'", text
    )
    if match is None:
        raise CheckFailed(f"no {SCREEN_KEY} in the app's English strings")
    return match.group(1)


def scan_events(messages: Iterable[str], needles: Needles) -> Counter:
    """How many messages hold each needle, by name; never the text."""
    counts: Counter = Counter()
    for message in messages:
        found = set()
        if any(_is_ip(m.group(0), 4) for m in _IPV4.finditer(message)):
            found.add("ipv4")
        if any(_is_ip(m.group(0), 6) for m in _IPV6.finditer(message)):
            found.add("ipv6")
        numbers = {round(float(x), 4) for x in _DECIMAL.findall(message)}
        if any(
            round(p["lat"], 4) in numbers and round(p["lng"], 4) in numbers
            for p in needles.points
        ):
            found.add("test point")
        if any(device and device in message for device in needles.devices):
            found.add("device id")
        if "/9j/" in message:
            found.add("jpeg base64")
        if needles.key and needles.key in message:
            found.add("model key")
        counts.update(found)
    return counts


def _is_ip(candidate: str, version: int) -> bool:
    if version == 6 and (
        candidate.count(":") < 2 or not re.search(r"[0-9A-Fa-f]", candidate)
    ):
        return False
    try:
        return ipaddress.ip_address(candidate).version == version
    except ValueError:
        return False


def expired_items_check(
    ddb, http: httpx.Client, api_url: str, feed_url: str, table: str, *, now_s: int
) -> list[str]:
    """P5 (W27): a published live item past its visibleUntil is in no read, and one past
    its expiresAt reads 404 (C526). `now_s` is the server's time. Both are deleted in
    finally, even when a check fails; a failed delete is a problem, and the item stays
    hidden by its own times until its TTL."""
    items = {
        kind: synthetic_item(kind, now_s=now_s)
        for kind in ("hidden_expired", "read_expired")
    }
    problems = []
    try:
        for item in items.values():
            ddb.put_item(
                TableName=table,
                Item={k: TypeSerializer().serialize(v) for k, v in item.items()},
            )
        hidden = items["hidden_expired"]["reportId"]
        reads = pin_reads(http, api_url, feed_url)
        for where in ("nearby", "map"):
            if hidden in {rid for rid, _ in reads[where]}:
                problems.append(f"the hidden_expired item shows in the {where} read")
        if hidden in reads["feed"]:
            problems.append("the hidden_expired item shows in the feed")
        gone = http.get(f"{api_url}/reports/{items['read_expired']['reportId']}")
        if gone.status_code != 404:
            problems.append(
                f"the read_expired item reads HTTP {gone.status_code}, not 404 (C526)"
            )
    finally:
        for kind, item in items.items():
            try:
                ddb.delete_item(
                    TableName=table,
                    Key={"pk": {"S": item["pk"]}, "sk": {"S": item["sk"]}},
                )
            except (BotoCoreError, ClientError) as exc:
                problems.append(
                    f"the {kind} item's delete failed ({failure(exc)}); its times keep it hidden"
                )
    return problems


def raw_left(s3, bucket: str, report_ids: list[str]) -> int:
    """How many of the reports still have a raw/ photo."""
    return sum(object_exists(s3, bucket, f"raw/{rid}.jpg") for rid in report_ids)


def _private_folder(out: Path) -> None:
    """P3's copies are photos: never under a sealed folder, and never in the repo."""
    if guards.is_sealed(out):
        raise CheckFailed("refused: a path inside a folder named sealed")
    resolved = out.resolve()
    if resolved == REPO or REPO in resolved.parents:
        raise CheckFailed(
            "refused: P3's copies are photos, so their folder must be outside the repo"
        )


def fetch_p3(s3, bucket: str, ordinals: dict[str, str], out: Path) -> list[Path]:
    """P3's copies, named by ordinal, order or sample id (Task 5's defaults 1 to 3)."""
    _private_folder(out)
    out.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    def fetch(key: str, name: str) -> None:
        try:
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return
            raise
        path = out / name
        path.write_bytes(body)
        saved.append(path)

    for ordinal, rid in ordinals.items():
        for kind in PHOTO_KINDS:
            fetch(f"{kind}/{rid}.jpg", f"{ordinal}-{kind}.jpg")
    demo: list[str] = []
    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix="demo/"
    ):
        for entry in page.get("Contents", []):
            if (match := _DEMO_KEY.fullmatch(entry["Key"])) and match.group(
                2
            ) not in demo:
                demo.append(match.group(2))
    for n, rid in enumerate(demo, 1):
        for kind in PHOTO_KINDS:
            fetch(f"demo/{kind}/{rid}.jpg", f"demo-{n}-{kind}.jpg")
    try:
        manifest = json.loads(
            s3.get_object(Bucket=bucket, Key="samples/manifest.json")["Body"].read()
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in ("NoSuchKey", "404"):
            raise
        manifest = {"samples": []}
    for entry in manifest.get("samples", []):
        sid = entry.get("sampleId")
        # A Set B composite leaves out its place and date (C512): MS7 opens no Set B photo.
        if not (entry.get("place") and entry.get("date")):
            continue
        if isinstance(sid, str) and _SAMPLE_ID.fullmatch(sid):  # a safe file name
            fetch(f"samples/{sid}.jpg", f"{sid}.jpg")
    return saved


def clear_p3(out: Path) -> int:
    """Delete the files fetch_p3 names in `out`, and nothing else."""
    _private_folder(out)
    if not out.is_dir():
        return 0
    removed = 0
    for path in out.iterdir():
        if path.is_file() and _FETCHED.fullmatch(path.name):
            path.unlink()
            removed += 1
    return removed


def main(
    argv: Sequence[str] | None = None,
    *,
    session=None,
    http: httpx.Client | None = None,
    wall: Callable[[], float] = time.time,
    environ: dict | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "command", nargs="?", default="check", choices=("check", "fetch-p3", "clear-p3")
    )
    parser.add_argument(
        "out", nargs="?", type=Path, help="fetch-p3 and clear-p3's folder"
    )
    parser.add_argument(
        "--since", help="the log scan's start, ISO 8601 (default: a day ago)"
    )
    parser.add_argument(
        "--ids", nargs="*", type=Path, default=[], help="the runs' private records"
    )
    parser.add_argument(
        "--inches-shown", action="store_true", help="once the release gate shows inches"
    )

    def command() -> int:
        args = parser.parse_args(argv)
        env = os.environ if environ is None else environ
        if args.command in ("fetch-p3", "clear-p3") and args.out is None:
            parser.error(f"{args.command} needs an output folder")
        try:
            if args.command == "clear-p3":
                say(f"cleared {clear_p3(args.out)} P3 copies")
                return 0
            ordinals, devices = load_records(args.ids) if args.ids else ({}, [])
            if args.command == "fetch-p3":
                aws = session if session is not None else lusot_session()
                stack = load_stack(aws)
                saved = fetch_p3(aws.client("s3"), stack.bucket, ordinals, args.out)
                say(
                    f"fetched {len(saved)} P3 copies, named by ordinal, order or sample id"
                )
                return 0
        except CheckFailed as exc:
            say(str(exc))
            return 2
        return run_checks(
            args, ordinals, devices, env, session=session, http=http, wall=wall
        )

    return guarded(
        command,
        label="PRIVACY CHECK FAILED",
        shown=(CheckFailed,),
        errors=(BotoCoreError, ClientError, httpx.HTTPError),
    )


def run_checks(args, ordinals, devices, env, *, session, http, wall) -> int:
    aws = session if session is not None else lusot_session()
    stack = load_stack(aws)
    api_url, feed_url = api_urls(aws)
    api_ids = tuple(urlparse(url).hostname.split(".")[0] for url in (api_url, feed_url))
    cloudformation = aws.client("cloudformation")

    def physical(logical: str) -> str:
        return cloudformation.describe_stack_resource(
            StackName=STACK, LogicalResourceId=logical
        )["StackResourceDetail"]["PhysicalResourceId"]

    api_log_group = physical("ApiLogGroup")
    client = http if http is not None else ipv4_client()
    rows: list[tuple[str, list[str]]] = []
    try:
        offset = server_offset(client, api_url, clock=wall)
        now_s = int(server_now(offset, clock=wall).timestamp())
        rows.append(
            (
                "P5 hidden and expired items",
                expired_items_check(
                    aws.client("dynamodb"),
                    client,
                    api_url,
                    feed_url,
                    stack.output("TableName"),
                    now_s=now_s,
                ),
            )
        )
        rows.append(
            (
                "P8 queues",
                check_queues(
                    aws.client("sqs"),
                    stack.output("QueueName"),
                    stack.output("DeadLetterQueueName"),
                ),
            )
        )
        rows.append(("P8 lifecycle", check_lifecycle(aws.client("s3"), stack.bucket)))
        rows.append(
            (
                "P8 TTL",
                check_ttl(
                    aws.client("dynamodb"),
                    {
                        stack.output("TableName"): "expiresAt",
                        physical("LimitsTable"): "expiresAt",
                    },
                ),
            )
        )
        rows.append(
            (
                "P8 log retention",
                check_log_retention(
                    aws.client("logs"), [stack.log_group, api_log_group]
                ),
            )
        )
        apigw = aws.client("apigatewayv2")
        rows.append(
            (
                "P9 access logs",
                check_access_logs(
                    apigw,
                    aws.client("s3"),
                    aws.client("cloudtrail"),
                    api_ids=api_ids,
                    bucket=stack.bucket,
                ),
            )
        )
        rows.append(
            (
                "P11 CORS",
                check_feed_cors(apigw, app_api_id=api_ids[0], feed_api_id=api_ids[1]),
            )
        )
        feed = client.get(f"{feed_url}/pins.geojson")
        mapped = client.get(f"{api_url}/map/pins")
        rows.append(
            (
                "P11 feed",
                feed_problems(
                    json_object(feed, "the feed"),
                    screen_line=screen_line(),
                    inches_shown=args.inches_shown,
                ),
            )
        )
        rows.append(
            (
                "P11 map read",
                map_problems(
                    json_object(mapped, "GET /map/pins").get("pins") or [],
                    inches_shown=args.inches_shown,
                ),
            )
        )
    finally:
        if http is None:
            client.close()
    since = (
        datetime.fromisoformat(args.since)
        if args.since
        else datetime.fromtimestamp(wall(), UTC) - timedelta(hours=SINCE_DEFAULT_H)
    )
    key = env.get("MODEL_API_KEY", "")
    counts: Counter = Counter()
    logs = aws.client("logs")
    for group in (stack.log_group, api_log_group):
        pages = logs.get_paginator("filter_log_events").paginate(
            logGroupName=group, startTime=int(since.timestamp() * 1000)
        )
        counts += scan_events(
            (event["message"] for page in pages for event in page.get("events", [])),
            Needles(devices=tuple(devices), key=key),
        )
    scan = [f"{n} messages hold {name}" for name, n in sorted(counts.items())]
    if not key:
        scan.append("MODEL_API_KEY isn't set, so the key wasn't looked for")
    rows.append(("P14 log scan", scan))
    left = raw_left(aws.client("s3"), stack.bucket, list(ordinals.values()))
    rows.append(
        (
            "raw photos left",
            [f"{left} of the runs' reports still have a raw photo"] if left else [],
        )
    )
    for name, problems in rows:
        say(f"{name}: {'FAIL: ' + '; '.join(problems) if problems else 'ok'}")
    counted = prefix_counts(aws.client("s3"), stack.bucket)
    say("objects by prefix: " + ", ".join(f"{p} {n}" for p, n in counted.items()))
    failed = sum(bool(problems) for _, problems in rows)
    say(
        f"PRIVACY CHECK FAILED: {failed} of {len(rows)} rows"
        if failed
        else "PRIVACY CHECK OK"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
