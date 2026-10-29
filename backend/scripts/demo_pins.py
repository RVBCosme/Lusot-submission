# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "boto3[crt]>=1.43.120",
#     "httpx>=0.28.1",
#     "numpy>=2.5.4",
#     "opencv-python-headless>=4.14.0.94,<5",
# ]
# ///
"""Seed, remove and check the demo pins (G1, C510, C523; MS4 spec §4.5; plan Task 8).

- `seed --until YYYY-MM-DD --ids <item_id>...`: each id is a consented item_id from
  MS2's log (F14), checked against the one allow-list (guards.py). Each photo goes
  through the real pipeline in demo mode, at its real spot and capture time (the log's
  lat, lon and taken_pht, Manila time), so a demo pin never passes as current. It is
  refused and counted, before any write, when it isn't on the allow-list, has no spot
  (an open-licensed photo has none, so it is a sample only: MS4-Q9), lies outside
  Metro Manila, or has no capture time. A pin is visible to the end of the --until day
  in Manila and kept 7 days more. Only a published level is kept: any other result
  has its item and demo/ keys deleted and is counted under not_level. A seed still
  running after 180 s is left alone, since the handler may still be writing, and
  counted under timed_out, for a `remove <id>` once it has ended. A re-seed of a
  source first deletes its pin, found by its id, which the source fixes.
- `remove [id]`: one pin and its three demo/ keys or, with no id, every demo item (a
  filtered scan of the table, run only from Rene's laptop) and every object under
  demo/, so it also deletes whatever an interrupted run left.
- `check <id>`: for a demo pin only (any other mode exits 2 before any request, so a
  live pin is never flagged), whether it is in nearby at its rounded spot and on the map,
  whether its three links answer 200, its mode, whether it stays visible past capture
  plus 3 h, and whether a flag is refused (S1, S4). The spot is never printed.

seed exits 2 before any write when /lusot/stop/publish isn't "off" (a level written
then would never pin) or when --until's end has passed or is more than 53 days ahead,
past the demo/ backstop. Each seed's Meta calls run on the credits, about $0.03 a
photo. Output: counts, outcomes and report ids, through guards.say.

Usage: uv run backend/scripts/demo_pins.py seed --until 2026-12-20 --ids S001
       uv run backend/scripts/demo_pins.py remove [id]
       uv run backend/scripts/demo_pins.py check <id>
Exit codes: 0 done (seed: at least one pin); 1 a check failed, nothing pinned, or not
found; 2 refused by a guard.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import re
import time
import uuid
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import datetime

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from eval_runs import api_client, iso_seconds, item_outcome, wait_item
from guards import (
    allowed_sources,
    approved_m9_versions,
    data_dir,
    refuse_sealed,
    say,
)
from metro_manila import geohash6, in_metro_manila
from ops_common import (
    PHT,
    REPORT_ID,
    WAIT_S,
    counts,
    guarded,
    items_by_id,
    lusot_session,
    yes,
)
from smoke_upload import CheckFailed, as_app_jpeg, load_stack

STOP_PUBLISH = "/lusot/stop/publish"
MAX_AHEAD_S = 53 * 24 * 60 * 60  # the demo/ backstop is 60 days
VISIBLE_S = 3 * 60 * 60  # a live pin's 3 h, which a demo pin must outlast (S4)
RETAIN_S = 7 * 24 * 60 * 60
DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
LINKS = ("photo", "overlay", "layers")


def demo_report_id(item_id: str) -> str:
    """The pin's id, C32's form, fixed by its source so a re-seed replaces it."""
    return "r_" + hashlib.sha256(("demo:" + item_id).encode()).hexdigest()[:32]


def demo_keys(report_id: str) -> tuple[str, str, str]:
    """A demo pin's stored photo and its overlay's image and JSON (C510)."""
    return (
        f"demo/blurred/{report_id}.jpg",
        f"demo/overlay/{report_id}.jpg",
        f"demo/overlay/{report_id}.json",
    )


def demo_times(until: str, now_s: int) -> tuple[int, int]:
    """visibleUntil, the end of the --until day in Manila, and expiresAt 7 days later.

    ValueError when the day isn't a date, has ended, or ends more than 53 days ahead.
    """
    try:
        if DAY.fullmatch(until) is None:
            raise ValueError
        day = datetime.strptime(until, "%Y-%m-%d")
    except ValueError:
        raise ValueError("--until must be a date written YYYY-MM-DD") from None
    end = int(day.replace(hour=23, minute=59, second=59, tzinfo=PHT).timestamp())
    if end <= now_s:
        raise ValueError("--until has already ended in Manila")
    if end - now_s > MAX_AHEAD_S:
        raise ValueError(
            "--until ends more than 53 days ahead, so demo/'s 60-day rule could"
            " delete a visible pin's photos"
        )
    return end, end + RETAIN_S


def spot(row: dict[str, str]) -> tuple[float, float] | None:
    """The consent log row's lat and lon, or None without a usable spot."""
    try:
        lat, lng = float(row.get("lat") or ""), float(row.get("lon") or "")
    except ValueError:
        return None
    if not (math.isfinite(lat) and math.isfinite(lng)):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng


def taken_epoch(text: str) -> int | None:
    """MS2's taken_pht, YYYY-MM-DD HH:MM in Manila, as epoch seconds, or None."""
    try:
        taken = datetime.strptime(text.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return int(taken.replace(tzinfo=PHT).timestamp())


def main(
    argv: Sequence[str] | None = None,
    *,
    session=None,
    http: httpx.Client | None = None,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser("seed", help="pin consented photos through the pipeline")
    seed.add_argument("--until", required=True, help="the last day shown, YYYY-MM-DD")
    seed.add_argument("--ids", nargs="+", required=True, help="consented item_ids")
    remove = commands.add_parser("remove", help="remove one pin, or every demo pin")
    remove.add_argument("id", nargs="?")
    check = commands.add_parser("check", help="check one pin as the app sees it")
    check.add_argument("id")

    def command() -> int:
        args = parser.parse_args(argv)
        if args.command == "seed":
            return seed_pins(args, session, clock, sleep)
        if args.command == "remove":
            return remove_pins(args, session)
        return check_pin(args, session, http)

    return guarded(
        command,
        shown=(CheckFailed,),
        errors=(BotoCoreError, ClientError, httpx.HTTPError),
    )


def seed_pins(args, session, clock, sleep) -> int:
    refuse_sealed(data_dir())
    try:
        visible_until, expires_at = demo_times(args.until, int(clock()))
    except ValueError as exc:
        say(f"refused: {exc}")
        return 2
    session = session or lusot_session()
    stack = load_stack(session)
    publish = session.client("ssm").get_parameter(Name=STOP_PUBLISH)["Parameter"]
    if publish["Value"] != "off":  # only an explicit "off" publishes (C516)
        say(f"refused: {STOP_PUBLISH} isn't off, so no demo pin would publish")
        return 2
    sources, refused = allowed_sources(args.ids, approved_m9_versions())
    ddb, s3 = session.client("dynamodb"), session.client("s3")
    table = stack.output("TableName")
    not_level: Counter = Counter()
    pinned = timed_out = 0
    for source in sources.values():
        found = spot(source.row) if source.kind == "consented" else None
        captured_s = taken_epoch(source.row.get("taken_pht") or "")
        if found is None:
            refused["no_spot"] += 1  # MS4-Q9
            continue
        if not in_metro_manila(*found):
            refused["outside_metro_manila"] += 1
            continue
        if captured_s is None:
            refused["no_capture_time"] += 1
            continue
        try:
            jpeg = as_app_jpeg(source.photo)  # before any write
        except (CheckFailed, OSError):
            refused["unreadable"] += 1
            continue
        report_id = demo_report_id(source.source_id)
        clear(ddb, s3, table, stack.bucket, report_id)
        captured = iso_seconds(captured_s)
        item = {
            "pk": {"S": "GEO#" + geohash6(*found)},
            "sk": {"S": f"{captured}#{report_id}"},
            "reportId": {"S": report_id},
            "mode": {"S": "demo"},
            "status": {"S": "pending"},
            "lat": {"N": str(found[0])},
            "lng": {"N": str(found[1])},
            "capturedAt": {"S": captured},  # in UTC, as MS1 stores it
            "receivedAt": {"S": iso_seconds(int(clock()))},
            "flags": {"N": "0"},
            "visibleUntil": {"N": str(visible_until)},
            "expiresAt": {"N": str(expires_at)},
            "credit": {"S": source.credit},
            "place": {"S": source.place},
            "demoSource": {"S": source.source_id},
        }
        if source.event:
            item["event"] = {"S": source.event}
        # The item first, so the photo's event finds it.
        ddb.put_item(TableName=table, Item=item)
        s3.put_object(
            Bucket=stack.bucket,
            Key=f"raw/{report_id}.jpg",
            Body=jpeg,
            ContentType="image/jpeg",
        )
        key = {"pk": item["pk"], "sk": item["sk"]}
        final = wait_item(ddb, table, key, bound_s=WAIT_S, clock=clock, sleep=sleep)
        outcome = item_outcome(final)
        if outcome == "done/level" and final.get("published") == {"BOOL": True}:
            pinned += 1
            say(f"{report_id}: pinned, {outcome}")
            continue
        if outcome.startswith("still "):
            # The handler may still be writing: a clear now could leave its photo
            # behind (review, Minor 3), so the pin is left for a later remove.
            timed_out += 1
            say(
                f"{report_id}: not pinned, {outcome} after {WAIT_S} s; run"
                f" `demo_pins.py remove {report_id}` once it has ended"
            )
            continue
        if outcome == "done/level":  # the publish switch changed during the run
            outcome += " unpublished"
        clear(ddb, s3, table, stack.bucket, report_id)
        not_level[outcome] += 1
        say(f"{report_id}: not pinned, {outcome}")
    if refused:
        say(f"refused: {counts(refused)}")
    if not_level:
        say(f"not_level: {counts(not_level)}")
    if timed_out:
        say(f"timed_out: {timed_out}")
    say(f"seed: {len(args.ids)} given, {pinned} pinned")
    return 0 if pinned else 1


def clear(ddb, s3, table: str, bucket: str, report_id: str) -> int:
    """Delete a pin's items and its three demo/ keys, and return how many items."""
    items = items_by_id(ddb, table, report_id)
    for item in items:
        ddb.delete_item(TableName=table, Key={"pk": item["pk"], "sk": item["sk"]})
    for key in demo_keys(report_id):
        s3.delete_object(Bucket=bucket, Key=key)
    return len(items)


def remove_pins(args, session) -> int:
    if args.id is not None and REPORT_ID.fullmatch(args.id) is None:
        say("refused: that isn't a report id")
        return 2
    session = session or lusot_session()
    stack = load_stack(session)
    ddb, s3 = session.client("dynamodb"), session.client("s3")
    table = stack.output("TableName")
    if args.id is not None:
        modes = {item["mode"]["S"] for item in items_by_id(ddb, table, args.id)}
        if modes - {"demo"}:
            say(f"refused: {args.id} isn't a demo pin")
            return 2
        removed = clear(ddb, s3, table, stack.bucket, args.id)
        say(f"removed {args.id}: {removed} items and its 3 demo/ keys")
        return 0 if removed else 1
    pages = ddb.get_paginator("scan").paginate(
        TableName=table,
        FilterExpression="#mode = :demo",
        ExpressionAttributeNames={"#mode": "mode"},
        ExpressionAttributeValues={":demo": {"S": "demo"}},
    )
    items = [item for page in pages for item in page["Items"]]
    for item in items:
        ddb.delete_item(TableName=table, Key={"pk": item["pk"], "sk": item["sk"]})
    listed = s3.get_paginator("list_objects_v2").paginate(
        Bucket=stack.bucket, Prefix="demo/"
    )
    keys = [entry["Key"] for page in listed for entry in page.get("Contents", [])]
    for key in keys:
        s3.delete_object(Bucket=stack.bucket, Key=key)
    say(f"removed {len(items)} demo items and {len(keys)} demo/ objects")
    return 0


def check_pin(args, session, http) -> int:
    if REPORT_ID.fullmatch(args.id) is None:
        say("refused: that isn't a report id")
        return 2
    session = session or lusot_session()
    stack = load_stack(session)
    items = items_by_id(session.client("dynamodb"), stack.output("TableName"), args.id)
    if not items:
        say(f"{args.id}: not found")
        return 1
    # Before any request: a live pin typed by mistake must never get a real flag.
    if {item.get("mode", {}).get("S") for item in items} != {"demo"}:
        say(f"refused: {args.id} isn't a demo pin")
        return 2
    item = items[0]
    spot_shown = rounded_spot(item)
    api = stack.api_url
    with api_client(http) as client:
        report = client.get(f"{api}/reports/{args.id}")
        if report.status_code != 200:
            say(f"{args.id}: GET /reports/{{id}} answered HTTP {report.status_code}")
            return 1
        body = report.json()
        in_nearby = False
        if spot_shown is not None:
            query = {"lat": spot_shown[0], "lng": spot_shown[1], "radius": 300}
            in_nearby = has_pin(client.get(f"{api}/reports", params=query), args.id)
        on_map = has_pin(client.get(f"{api}/map/pins"), args.id)
        links = {name: link_status(client, body.get(f"{name}Url")) for name in LINKS}
        device = {"X-Lusot-Device": str(uuid.uuid4())}  # never the shared none bucket
        flag = client.post(f"{api}/reports/{args.id}/flag", headers=device)
    captured_s = datetime.fromisoformat(item["capturedAt"]["S"]).timestamp()
    outlasts = int(item["visibleUntil"]["N"]) > captured_s + VISIBLE_S
    flag_refused = flag.status_code == 404  # C511, flags.ts: a demo pin's flag is 404
    say(f"{args.id}: mode {body.get('mode')}")
    say(f"nearby at its rounded spot: {yes(in_nearby)}")
    say(f"on the map: {yes(on_map)}")
    say("links: " + ", ".join(f"{name} {links[name]}" for name in LINKS))
    say(f"visibleUntil past capture plus 3 h: {yes(outlasts)}")
    say(f"flag refused: {yes(flag_refused)} (HTTP {flag.status_code})")
    passed = (
        body.get("mode") == "demo"
        and in_nearby
        and on_map
        and all(status == 200 for status in links.values())
        and outlasts
        and flag_refused
    )
    say(f"check: {'passed' if passed else 'failed'}")
    return 0 if passed else 1


def rounded_spot(item: dict) -> tuple[float, float] | None:
    """The item's spot as pins show it, rounded to 4 places (C514), or None."""
    try:
        return tuple(round(float(item[name]["N"]), 4) for name in ("lat", "lng"))
    except (KeyError, TypeError, ValueError):
        return None


def has_pin(response: httpx.Response, report_id: str) -> bool:
    if response.status_code != 200:
        return False
    return any(pin.get("id") == report_id for pin in response.json().get("pins", []))


def link_status(client: httpx.Client, url: str | None) -> int | str:
    """A link's HTTP status, or "missing" when the report gave none."""
    return "missing" if url is None else client.get(url).status_code


if __name__ == "__main__":
    raise SystemExit(main())
