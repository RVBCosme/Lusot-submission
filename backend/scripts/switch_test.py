# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "boto3[crt]>=1.43.120",
#     "httpx>=0.28.1",
#     "numpy>=2.5.4",
#     "opencv-python-headless>=4.14.0.94,<5",
# ]
# ///
"""The stop switches' test on the deployed stack: S1 to S3 (MS7 plan Task 4).

Spec §4.1, C810, C811 and C830. For each switch it sets the switch with put-parameter,
waits until the effect shows and checks it, sets it back to off, and waits until service
returns, timing both. A finally block always sets the switch back to off; if that
fails, it prints STOP SWITCH LEFT ON with the exact command, as the smoke script does.
- S1, uploads: POST /uploads, with no photo and a fresh device id each time, gives 503
  uploads_paused. Only after the first 503 and the API's 30 s switch cache does one
  POST /samples/{id} go, which must give 503 too. After the release, a mistyped value
  (paused) must stop uploads as well, since only "off" lets work through.
- S2, model-calls: a dark JPEG ends failed/model_calls_paused with no Meta call, and its
  raw photo is gone. After the switch cache, one POST /ask answers with its plain list
  (--no-ask leaves it out). After the release, a dark JPEG ends refused/too_dark with
  meta_calls 0.
- S3, publish: in spec §4.1's order. Set the switch and read it back as on, wait for the
  switch cache, write one synthetic live pin item at SMOKE_SPOT (C810), wait for the
  feed's cache, then check that the pin is absent from the nearby read, the app's map
  read and the public feed, that the demo pins the reads held before stay, and that
  GET /reports/{id} still answers. The item is deleted in an inner finally and
  confirmed gone before the switch goes off. From just before the item's put until its
  delete is confirmed, publish stays on whatever ends the run. If the cleanup fails, the
  hand fix (delete, confirm, then switch off) goes to a private file whose path is all
  that is printed, and the run never prints the bare command to set publish off.

Every cache wait counts from when its put returned. S1 ends once every API container has
seen uploads off again. A server clock more than 300 s from the laptop's stops the run
before any switch is set, since the synthetic item's times come from it.

None makes a Meta call: S2 uses dark JPEGs, and its question gets the plain list. It
first confirms that a new report at OUTSIDE_POINT reads private (C803). At the end all
three switches must read off, and it prints the switch times as one Markdown table for
the results note (C830).

It prints results, counts and timings only, through harden.say: reports by ordinal
(S#1), never a report id, a form field or a URL. Each run's ids, and any hand fix, go to
LUSOT_DATA_DIR\\ms7\\<date>\\. Without --yes it prints what it would do and stops.

Usage: uv run backend/scripts/switch_test.py [--yes] [--no-ask] [--run NAME]
Exit codes: 0 every check passed and every switch reads off; 1 a check failed or a
switch was left on; 2 nothing was sent, without --yes, or refused by a guard.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import BotoCoreError, ClientError
from harden import (
    FEED_CACHE_S,
    SMOKE_SPOT,
    SWITCH_CACHE_S,
    SWITCH_PREFIX,
    SWITCHES,
    RunRecord,
    api_urls,
    confirm_private,
    data_dir,
    ipv4_client,
    new_device_id,
    say,
    server_now,
    server_offset,
    synthetic_item,
)
from ops_common import PHT, guarded, lusot_session
from smoke_upload import (
    DEVICE_HEADER,
    CheckFailed,
    Stack,
    dark_jpeg,
    failure_name,
    got,
    json_object,
    load_stack,
    meta_calls,
    object_exists,
    post_form,
    s3_error,
)
from upload_checks import final_outcome, issue, made_report, result, upload_request

MARGIN_S = 5  # past a cache, for clocks and requests in flight
ACT_TIMEOUT_S = SWITCH_CACHE_S + 30
RELEASE_TIMEOUT_S = SWITCH_CACHE_S + FEED_CACHE_S + 60
INDEX_WAIT_S = 10  # feed-index follows the table eventually
MAX_OFFSET_S = 300  # a server clock further off than this stops the run
NEARBY_RADIUS_M = 300
QUESTION = "Gaano kalalim ang baha sa España Boulevard ngayon?"  # a Metro Manila place
CLI = "--profile lusot --region ap-southeast-1 --no-cli-pager"
PLAN = (
    "switch test: S1 sets uploads on, then paused, probing POST /uploads with no photo and"
    " one POST /samples once the cache has passed; S2 sets model-calls on, with two dark"
    " JPEGs and one question (none with --no-ask); S3 sets publish on, with one synthetic"
    " item for about 70 s while it is hidden; no Meta call; about 8 minutes"
)


@dataclass(frozen=True)
class SwitchTime:
    """One switch's seconds from its put's return until its effect showed, and from
    off until service was back (None when the release can't show)."""

    name: str
    act_s: float
    release_s: float | None


@dataclass
class SwitchState:
    """When the put of the switch returned, and when its reset to off returned."""

    on_at: float
    off_at: float | None = None


@dataclass
class PublishState:
    """S3's item, while it may exist: publish stays on until it is confirmed gone."""

    item_name: str | None = None
    may_exist: bool = False
    hand_fix: Path | None = None


class PublishCleanupFailed(Exception):
    """The synthetic item may remain, so publish stays on and the hand fix is written."""


def set_switch(ssm, name: str, value: str) -> None:
    ssm.put_parameter(
        Name=SWITCH_PREFIX + name, Value=value, Type="String", Overwrite=True
    )


def read_switches(ssm) -> dict[str, str]:
    """Each switch's value, or "missing"."""
    answer = ssm.get_parameters(Names=[SWITCH_PREFIX + name for name in SWITCHES])
    values = {
        found["Name"].removeprefix(SWITCH_PREFIX): found["Value"]
        for found in answer.get("Parameters", [])
    }
    return {name: values.get(name, "missing") for name in SWITCHES}


def hand_command(name: str) -> str:
    return (
        f"aws ssm put-parameter --name {SWITCH_PREFIX}{name} --value off --type String"
        f" --overwrite {CLI}"
    )


def wait_for(
    probe: Callable[[], bool],
    *,
    timeout_s: float,
    every_s: float = 2.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> float:
    """The seconds until `probe()` is True, or CheckFailed once `timeout_s` passes."""
    began = clock()
    while not probe():
        if clock() - began >= timeout_s:
            raise CheckFailed(f"not within {timeout_s:g} s")
        sleep(every_s)
    return clock() - began


def wait_until(deadline: float, *, clock, sleep) -> None:
    while (now := clock()) < deadline:
        sleep(deadline - now)


@contextmanager
def switch_on(
    ssm,
    name: str,
    value: str = "on",
    keep_on: tuple[type[BaseException], ...] = (),
    *,
    clock: Callable[[], float] = time.monotonic,
    hold: Callable[[], bool] = lambda: False,
) -> Iterator[SwitchState]:
    """Set the switch to `value`, and set it back to off in finally.

    The yielded state's `on_at` is when the put returned: an API container that read
    the switch just before the put landed holds the old value for 30 s from then, so
    every cache wait counts from it. A `keep_on` exception, or `hold()` being True
    (S3's item may still exist), leaves the switch as it is. A reset that fails prints
    STOP SWITCH LEFT ON with the command, and raises.
    """
    state = SwitchState(clock())
    failure: BaseException | None = None
    kept = False
    try:
        set_switch(
            ssm, name, value
        )  # in the try: a put SSM applies but fails here is reset
        state.on_at = clock()
        yield state
    except keep_on:
        kept = True
        raise
    except BaseException as exc:
        failure = exc
        raise
    finally:
        if not kept and not hold():
            try:
                set_switch(ssm, name, "off")
                state.off_at = clock()
            except (BotoCoreError, ClientError):
                say(f"STOP SWITCH LEFT ON. Set it back by hand: {hand_command(name)}")
                if (
                    failure is not None
                ):  # so the reset's error doesn't hide the first one
                    say(f"the check had already failed: {failure_name(failure)}")
                raise


def private_file(record: RunRecord, kind: str, suffix: str, text: str) -> Path:
    """A new file in the run's private folder, never over another."""
    record.folder.mkdir(parents=True, exist_ok=True)
    stem = f"{kind}-{record.script}-{record.started:%H%M%S}"
    for n in itertools.count(1):
        path = record.folder / (f"{stem}{suffix}" if n == 1 else f"{stem}-{n}{suffix}")
        try:
            with path.open("x", encoding="utf-8") as file:
                file.write(text)
        except FileExistsError:
            continue
        return path
    raise AssertionError("unreachable")


def write_hand_fix(record: RunRecord, steps: list[str]) -> Path:
    """The hand-fix commands, which may name a report id, in the run's private folder,
    never over another file. The returned path is all that is printed."""
    return private_file(record, "hand-fix", ".txt", "\n".join(steps) + "\n")


def is_paused(response: httpx.Response) -> bool:
    return response.status_code == 503 and (
        json_object(response, "the API").get("error") == "uploads_paused"
    )


def probe_upload(
    http: httpx.Client, api_url: str, record: RunRecord, *, offset_s: float, wall
) -> httpx.Response:
    """One POST /uploads with no photo, from a fresh device id, so the device limit
    never interferes; a report it makes is named in the record."""
    response = upload_request(
        http,
        api_url,
        device_id=record.device(new_device_id()),
        captured_at=server_now(offset_s, clock=wall),
    )
    if response.status_code == 201 and (rid := made_report(response)):
        record.name(rid)
    return response


def check_uploads(
    http: httpx.Client,
    api_url: str,
    ssm,
    record: RunRecord,
    *,
    offset_s: float,
    wall,
    clock,
    sleep,
) -> tuple[SwitchTime, str]:
    """S1, with the mistyped value after the release (Task 4's defaults 1 and 2). It
    ends once every API container has seen uploads off again, so the next check's
    uploads aren't refused."""
    timing = {"clock": clock, "sleep": sleep}

    def probe() -> httpx.Response:
        return probe_upload(http, api_url, record, offset_s=offset_s, wall=wall)

    def serving() -> bool:
        return probe().status_code == 201

    with switch_on(ssm, "uploads", clock=clock) as state:
        act_s = wait_for(lambda: is_paused(probe()), timeout_s=ACT_TIMEOUT_S, **timing)
        # The sample only after the first 503 and the cache, so no container runs it.
        wait_until(state.on_at + SWITCH_CACHE_S + MARGIN_S, **timing)
        sample = send_sample(http, api_url, record)
    release_s = wait_for(serving, timeout_s=ACT_TIMEOUT_S, **timing)
    with switch_on(ssm, "uploads", "paused", clock=clock) as typo:
        wait_until(typo.on_at + SWITCH_CACHE_S + MARGIN_S, **timing)
        mistyped = probe()
    wait_for(serving, timeout_s=ACT_TIMEOUT_S, **timing)
    wait_until(typo.off_at + SWITCH_CACHE_S + MARGIN_S, **timing)
    ok = sample in ("503", "none listed") and is_paused(mistyped)
    detail = (
        f"503 uploads_paused after {act_s:.0f} s; the sample: {sample}; paused:"
        f" {mistyped.status_code}; 201 again after {release_s:.0f} s"
    )
    return SwitchTime("uploads", act_s, release_s), result("S1", ok, detail)


def send_sample(http: httpx.Client, api_url: str, record: RunRecord) -> str:
    """One POST /samples/{id}, for the first sample GET /samples lists."""
    listed = http.get(f"{api_url}/samples")
    samples = (
        json_object(listed, "GET /samples").get("samples")
        if listed.status_code == 200
        else None
    )
    if not isinstance(samples, list):
        raise CheckFailed(f"GET /samples: {got(listed)}")
    if not samples or not isinstance(samples[0], dict) or "sampleId" not in samples[0]:
        return "none listed"
    run = http.post(
        f"{api_url}/samples/{samples[0]['sampleId']}",
        headers={DEVICE_HEADER: record.device(new_device_id())},
    )
    if run.status_code == 201 and (rid := made_report(run)):
        record.name(rid)
    return "503" if is_paused(run) else got(run)


def dark_upload(
    http: httpx.Client,
    stack: Stack,
    record: RunRecord,
    *,
    offset_s: float,
    wall,
    clock,
    sleep,
) -> tuple[str, str, list[dict], bool]:
    """A dark JPEG through the app's path: its report's ordinal, outcome and log lines,
    and whether its raw photo is gone."""
    link = issue(
        http,
        stack.api_url,
        record,
        device_id=record.device(new_device_id()),
        offset_s=offset_s,
        wall=wall,
    )
    posted = post_form(http, link.form, dark_jpeg())
    if posted.status_code != 204:
        raise CheckFailed(
            f"{link.name}: S3 answered HTTP {posted.status_code} {s3_error(posted)}"
        )
    outcome, lines = final_outcome(http, stack, link, clock=clock, sleep=sleep)
    gone = not object_exists(
        stack.session.client("s3"), stack.bucket, f"raw/{link.report_id}.jpg"
    )
    return link.name, outcome, lines, gone


def ended_free(lines: list[dict], outcome: str, *, logged: bool) -> bool:
    """One line of how it ended, and no Meta call: meta_calls 0, or, when the pipeline
    never ran (`logged` False), no meta_calls at all."""
    ended = [line for line in lines if line.get("outcome") == outcome]
    if len(ended) != 1 or meta_calls(lines) != 0:
        return False
    return (
        ended[0].get("meta_calls") == 0
        if logged
        else ended[0].get("meta_calls", 0) == 0
    )


def check_model_calls(
    http: httpx.Client,
    stack: Stack,
    ssm,
    record: RunRecord,
    *,
    ask: bool,
    offset_s: float,
    wall,
    clock,
    sleep,
) -> tuple[SwitchTime, str]:
    """S2 (Task 4's default 3). Each time is a dark upload's round trip to its final
    report, the log search included."""
    timing = {"offset_s": offset_s, "wall": wall, "clock": clock, "sleep": sleep}
    with switch_on(ssm, "model-calls", clock=clock) as state:
        paused_name, paused, paused_lines, paused_gone = dark_upload(
            http, stack, record, **timing
        )
        act_s = clock() - state.on_at
        question = "not asked (--no-ask)"
        if ask:  # the question only after the cache, so it can't pay
            wait_until(
                state.on_at + SWITCH_CACHE_S + MARGIN_S, clock=clock, sleep=sleep
            )
            question = ask_once(http, stack.api_url, record)
    name, released, lines, _ = dark_upload(http, stack, record, **timing)
    release_s = clock() - state.off_at
    ok = (
        paused == "failed/model_calls_paused"
        and ended_free(paused_lines, paused, logged=False)
        and paused_gone
        and question in ("plain list", "not asked (--no-ask)")
        and released == "refused/too_dark"
        and ended_free(lines, released, logged=True)
    )
    detail = (
        f"{paused_name}: {paused}, {meta_calls(paused_lines)} Meta calls, raw photo"
        f" {'gone' if paused_gone else 'present'}; the question: {question}; after the"
        f" release {name}: {released}, {meta_calls(lines)} Meta calls"
    )
    return SwitchTime("model-calls", act_s, release_s), result("S2", ok, detail)


def ask_once(http: httpx.Client, api_url: str, record: RunRecord) -> str:
    """One typed question, as the Ask Lusot spec words it (Task 4's names)."""
    response = http.post(
        f"{api_url}/ask",
        json={"question": QUESTION},
        headers={DEVICE_HEADER: record.device(new_device_id())},
    )
    if response.status_code != 200:
        return got(response)
    answer = json_object(response, "POST /ask").get("answer")
    if isinstance(answer, dict) and (answer.get("source"), answer.get("fallback")) == (
        "plain_list",
        "model_calls_paused",
    ):
        return "plain list"
    return "answered by the model"


def pin_reads(http: httpx.Client, api_url: str, feed_url: str) -> dict[str, list]:
    """The nearby read at SMOKE_SPOT and the map read, as (id, mode) pairs, and the
    feed's ids."""

    def pins(response: httpx.Response, what: str) -> list[tuple[str, str]]:
        if response.status_code != 200:
            raise CheckFailed(f"{what}: {got(response)}")
        found = json_object(response, what).get("pins")
        if not isinstance(found, list):
            raise CheckFailed(f"{what}: no pins list")
        return [(p.get("id"), p.get("mode")) for p in found if isinstance(p, dict)]

    near = http.get(
        f"{api_url}/reports",
        params={
            "lat": SMOKE_SPOT["lat"],
            "lng": SMOKE_SPOT["lng"],
            "radius": NEARBY_RADIUS_M,
        },
    )
    feed = http.get(f"{feed_url}/pins.geojson")
    if feed.status_code != 200:
        raise CheckFailed(f"the feed: {got(feed)}")
    features = json_object(feed, "the feed").get("features")
    if not isinstance(features, list):
        raise CheckFailed("the feed: no features list")
    return {
        "nearby": pins(near, "the nearby read"),
        "map": pins(http.get(f"{api_url}/map/pins"), "GET /map/pins"),
        "feed": sorted(
            str((f.get("properties") or {}).get("id"))
            for f in features
            if isinstance(f, dict)
        ),
    }


def check_publish(
    http: httpx.Client,
    api_url: str,
    feed_url: str,
    ssm,
    ddb,
    table: str,
    record: RunRecord,
    *,
    offset_s: float,
    wall,
    clock,
    sleep,
    held: PublishState | None = None,
) -> tuple[SwitchTime, str]:
    """S3, in spec §4.1's order, with MS7-Q3's default (a): a synthetic pin that exists
    only while the switch hides it.

    From just before its put until its delete is confirmed, `held.may_exist` is True,
    and publish stays on whatever ends the run, a second interrupt included. A failed
    cleanup writes the hand fix, delete first, and raises PublishCleanupFailed.
    """
    held = held if held is not None else PublishState()
    before = pin_reads(http, api_url, feed_url)
    demo = {
        where: {i for i, mode in before[where] if mode == "demo"}
        for where in ("nearby", "map")
    }
    with switch_on(
        ssm,
        "publish",
        keep_on=(PublishCleanupFailed,),
        clock=clock,
        hold=lambda: held.may_exist,
    ) as state:
        read_back = ssm.get_parameter(Name=SWITCH_PREFIX + "publish")["Parameter"][
            "Value"
        ]
        if read_back != "on":
            raise CheckFailed(f"publish read back as {read_back!r}, not on")
        wait_until(state.on_at + SWITCH_CACHE_S + MARGIN_S, clock=clock, sleep=sleep)
        item = synthetic_item(
            "publish", now_s=int(server_now(offset_s, clock=wall).timestamp())
        )
        held.item_name = record.name(item["reportId"])
        key = {"pk": {"S": item["pk"]}, "sk": {"S": item["sk"]}}
        record.save()  # the id is on disk before the item can exist
        held.may_exist = True
        try:
            ddb.put_item(
                TableName=table,
                Item={k: TypeSerializer().serialize(v) for k, v in item.items()},
            )
            written_at = clock()
            wait_until(written_at + FEED_CACHE_S, clock=clock, sleep=sleep)
            during = pin_reads(http, api_url, feed_url)
            own = http.get(f"{api_url}/reports/{item['reportId']}")
            act_s = clock() - state.on_at
        finally:  # a put that applied but raised is deleted too: a missing item's delete is a no-op
            remove_item(ddb, table, key, record, held=held, sleep=sleep)
    rid = item["reportId"]
    shown = [
        where for where in ("nearby", "map") if rid in {i for i, _ in during[where]}
    ]
    shown += ["the feed"] if rid in during["feed"] else []
    lost = [
        where
        for where in ("nearby", "map")
        if not demo[where] <= {i for i, _ in during[where]}
    ]
    if before["feed"]:
        release_s = wait_for(
            lambda: pin_reads(http, api_url, feed_url)["feed"] == before["feed"],
            timeout_s=RELEASE_TIMEOUT_S,
            clock=clock,
            sleep=sleep,
        )
        released = f"the feed as before after {release_s:.0f} s"
    else:
        release_s, released = (
            None,
            "the release not shown (no live pin in the feed before)",
        )
    ok = not shown and not lost and own.status_code == 200
    detail = (
        f"{held.item_name} hidden {'nowhere: shown in ' + ', '.join(shown) if shown else 'from nearby, the map and the feed'};"
        f" demo pins {'lost from ' + ', '.join(lost) if lost else 'kept'}; its own read"
        f" HTTP {own.status_code}; deleted and gone; {released}"
    )
    return SwitchTime("publish", act_s, release_s), result("S3", ok, detail)


def remove_item(
    ddb, table: str, key: dict, record: RunRecord, *, held: PublishState, sleep
) -> None:
    """Delete the synthetic item, confirm it gone with a consistent read, and give
    feed-index a moment. Any failure writes the hand fix and keeps publish on."""
    try:
        ddb.delete_item(TableName=table, Key=key)
        if "Item" in ddb.get_item(TableName=table, Key=key, ConsistentRead=True):
            raise CheckFailed("the synthetic item is still there after its delete")
        sleep(INDEX_WAIT_S)
        held.may_exist = False
    except BaseException as exc:  # noqa: BLE001 - any failure, an interrupt too, keeps publish on
        # The key in its own file: PowerShell 5.1 strips the quotes of inline JSON.
        key_file = private_file(record, "hand-fix", "-key.json", json.dumps(key))
        held.hand_fix = write_hand_fix(
            record,
            [
                "# MS7's switch test left its synthetic item, so publish is still on.",
                "# In order: delete the item, check that the read finds no Item, then set publish off.",
                # Quoted: a data folder's path can hold a space.
                f'aws dynamodb delete-item --table-name {table} --key "file://{key_file}" {CLI}',
                f'aws dynamodb get-item --table-name {table} --key "file://{key_file}" --consistent-read {CLI}',
                hand_command("publish"),
            ],
        )
        say(
            f"PUBLISH KEPT ON ON PURPOSE: the synthetic item may remain ({failure_name(exc)}). Hand fix: {held.hand_fix}"
        )
        raise PublishCleanupFailed(failure_name(exc)) from None


def times_table(times: list[SwitchTime], *, when: str, run: str) -> str:
    """Spec §4.1's switch times, one Markdown row per switch, seconds rounded up (C830),
    and a line saying what each cell measures."""
    rows = [
        "| Switch | On: effect after | Off: back after | Measured |",
        "|---|---|---|---|",
    ]
    for t in times:
        act = f"{math.ceil(t.act_s)} s"
        if t.name == "publish":
            act += ", the feed's 60 s cache included"
        back = (
            "not shown (no live pin)"
            if t.release_s is None
            else f"{math.ceil(t.release_s)} s"
        )
        rows.append(f"| `{t.name}` | {act} | {back} | {when}, {run} |")
    rows.append(
        "\nEach time runs from the put's return. uploads: until POST /uploads gives 503, and"
        " 201 again; model-calls: a dark JPEG's round trip to its final report, the log"
        " search included; publish: until the reads show the synthetic pin hidden, both"
        " caches' waits included, and until the feed shows its live pins again."
    )
    return "\n".join(rows)


def attempt(
    check: str, run: Callable[[], tuple[SwitchTime, str]]
) -> tuple[SwitchTime | None, str]:
    """One check, its line printed as it ends; a CheckFailed fails that check alone."""
    try:
        timed, line = run()
    except CheckFailed as exc:
        timed, line = None, result(check, False, str(exc))
    say(line)
    return timed, line


def main(
    argv: Sequence[str] | None = None,
    *,
    session=None,
    http: httpx.Client | None = None,
    wall: Callable[[], float] = time.time,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--yes", action="store_true", help="run; without it, nothing is sent"
    )
    parser.add_argument(
        "--no-ask", action="store_true", help="a stack without Ask Lusot"
    )
    parser.add_argument("--run", default="rehearsal", help="the times table's run name")

    def command() -> int:
        args = parser.parse_args(argv)
        if not args.yes:
            say(PLAN)
            say("nothing sent: add --yes to run it")
            return 2
        today = datetime.fromtimestamp(wall(), PHT)
        try:
            record = RunRecord(
                data_dir() / "ms7" / f"{today:%Y-%m-%d}",
                "switch_test",
                "S",
                clock=lambda: datetime.fromtimestamp(wall(), PHT),
            )
        except CheckFailed as exc:  # a sealed path, or clashing records
            say(f"refused: {exc}")
            return 2
        aws = session if session is not None else lusot_session()
        ssm = aws.client("ssm")
        client = http if http is not None else ipv4_client()
        times: list[SwitchTime] = []
        lines: list[str] = []
        held = PublishState()
        code = 0
        try:
            stack = load_stack(aws)
            api_url, feed_url = api_urls(aws)
            offset = server_offset(client, api_url, clock=wall)
            if abs(offset) > MAX_OFFSET_S:  # the synthetic item's times come from it
                raise CheckFailed(
                    f"the server's clock is {offset:+.0f} s from the laptop's"
                )
            timing = {"offset_s": offset, "wall": wall, "clock": clock, "sleep": sleep}
            record.name(
                confirm_private(
                    client,
                    api_url,
                    device_id=record.device(new_device_id()),
                    offset_s=offset,
                    clock=clock,
                    sleep=sleep,
                    wall=wall,
                )
            )
            checks = (
                ("S1", lambda: check_uploads(client, api_url, ssm, record, **timing)),
                (
                    "S2",
                    lambda: check_model_calls(
                        client, stack, ssm, record, ask=not args.no_ask, **timing
                    ),
                ),
                (
                    "S3",
                    lambda: check_publish(
                        client,
                        api_url,
                        feed_url,
                        ssm,
                        aws.client("dynamodb"),
                        stack.output("TableName"),
                        record,
                        held=held,
                        **timing,
                    ),
                ),
            )
            for check, run in checks:
                timed, line = attempt(check, run)
                lines.append(line)
                if timed is not None:
                    times.append(timed)
        except PublishCleanupFailed:
            line = result(
                "S3",
                False,
                f"{held.item_name}'s delete wasn't confirmed; publish kept on",
            )
            say(line)
            lines.append(line)
            code = 1
        except CheckFailed as exc:
            say(f"SWITCH TEST FAILED: {exc}")
            code = 1
        finally:
            say(f"run record: {record.save().name}")
            if http is None:
                client.close()
            left = {
                name: value
                for name, value in read_switches(ssm).items()
                if value != "off"
            }
            for name, value in left.items():
                if name == "publish" and held.may_exist:
                    follow = (
                        f"follow the hand fix, in order: {held.hand_fix}"
                        if held.hand_fix
                        else (
                            f"its id is in the run record {record.path.name}: delete the item,"
                            " confirm it gone with a consistent read, then set publish off"
                        )
                    )
                    say(
                        f"PUBLISH KEPT ON ON PURPOSE: the synthetic item {held.item_name} may remain; {follow}"
                    )
                else:
                    say(
                        f"STOP SWITCH LEFT ON: {name} reads {value!r}. Set it back by hand: {hand_command(name)}"
                    )
        if times:
            say(times_table(times, when=f"{today:%Y-%m-%d}", run=args.run))
        failed = sum(" FAIL: " in line for line in lines)
        if left or failed or code:
            say(
                f"SWITCH TEST FAILED: {failed} of {len(lines)} checks failed, {len(left)} switches left on"
            )
            return 1
        say("SWITCH TEST OK: every switch reads off")
        return 0

    return guarded(
        command,
        label="SWITCH TEST FAILED",
        errors=(BotoCoreError, ClientError, httpx.HTTPError),
    )


if __name__ == "__main__":
    raise SystemExit(main())
