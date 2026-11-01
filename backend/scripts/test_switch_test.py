"""Tests for switch_test.py: S1 to S3, the stop switches (MS7 plan Task 4).

Fakes only. FakeStack is the deployed stack in memory: botocore's Stubber answers every
AWS call (SSM, DynamoDB, CloudFormation, CloudWatch Logs and S3), each answer queued by
StubSession's hook just before its call from the fake's state, and httpx's
MockTransport answers the app's API, the feed's API and S3. Each route sees a switch a
set delay after its put lands, 30 s by default, as the API's slowest container would;
the analysis handler sees model-calls at once. A put can take time, and lands when it
returns. Nothing reaches AWS, the API or Meta, and no folder named sealed is made.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_switch_test.py
"""

import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path

import harden
import httpx
import pytest
import switch_test
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError
from smoke_upload import CheckFailed
from stubs import Clock, StubSession, http_date, report_ids

API = "https://api.test.invalid"
FEED = "https://feed.test.invalid"
S3_URL = "https://bucket.s3.test.invalid/"
START = datetime(2026, 11, 3, 2, 15, tzinfo=UTC).timestamp()  # 10:15 AM in Manila
SERVICES = ("ssm", "dynamodb", "cloudformation", "logs", "s3")
DEMO_ID, LIVE_ID = report_ids(2, seed=9)
SAMPLE_ID = "s0123456789"
READS = (
    "GET api.test.invalid/reports",
    "GET api.test.invalid/map/pins",
    "GET feed.test.invalid/pins.geojson",
)


@pytest.fixture(autouse=True)
def consent(tmp_path, monkeypatch):
    """MS5's consent notice, as a stand-in file, and a private data folder."""
    path = tmp_path / "consent.en.md"
    path.write_bytes(b"The notice.\n")
    monkeypatch.setattr(harden, "CONSENT_PATH", path)
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "data"))


def pin(rid: str, mode: str) -> dict:
    return {"id": rid, "mode": mode, "lat": 14.6095, "lng": 120.9894, "level": "knee"}


class FakeStack:
    """The stack in memory, on the laptop's fake clock (no skew unless `skew_s`)."""

    def __init__(self, clock: Clock, *, seed: int = 0):
        self.clock = clock
        self.ids = iter(report_ids(200, seed=seed))
        self.made: list[str] = []
        self.switches = {name: [(-math.inf, "off")] for name in harden.SWITCHES}
        self.table: dict[str, dict] = {}  # the synthetic items, by report id
        self.ever: dict[str, dict] = {}  # every item written, for a stale read
        self.reports: dict[str, dict] = {}  # reports the API made
        self.lines: dict[str, list[dict]] = {}  # the analysis log, by report id
        self.timeline: list[tuple[float, str, object]] = []
        self.devices: list[str | None] = []  # each POST /uploads' device id
        self.files: list[bytes] = []  # each S3 post's file
        # How long after a put each reader sees the switch.
        self.delays = {
            "uploads": 30.0,
            "samples": 30.0,
            "ask": 30.0,
            "pins": 30.0,
            "handler": 0.0,
        }
        self.put_latency_s = (
            0.0  # each put_parameter takes this long, and lands as it returns
        )
        self.skew_s = 0.0  # the server's Date header, ahead of the laptop
        self.leak: set[str] = set()  # reads that show the synthetic pin anyway
        self.lose_demo: set[str] = (
            set()
        )  # reads that drop the demo pin while publish is on
        self.own_read_status = 200
        self.delete_fails = False
        self.put_item_raises = False  # the item is stored, and the call raises anyway
        self.raw_present = False  # head_object finds every raw photo
        self.ask_model = False  # POST /ask answers from the model whatever the switch
        self.read_back: str | None = None  # get_parameter's value for publish, if set
        self.final_on: str | None = (
            None  # the end's get_parameters reads this one as on
        )
        self.switch_reads = 0  # get_parameters calls: the first is the start's check
        self.off_put_fails: set[str] = set()  # switches whose "off" put fails
        self.raise_in_read: BaseException | None = None  # once publish is on
        self.session = StubSession(*SERVICES, on_call=self.on_aws)

    # The switches, as each reader sees them.
    def value(self, name: str, delay_s: float) -> str:
        seen = self.clock() - delay_s
        return [value for at, value in self.switches[name] if at <= seen][-1]

    def stopped(self, name: str, reader: str) -> bool:
        return self.value(name, self.delays[reader]) != "off"

    # AWS, answered by Stubber with what the fake holds.
    def on_aws(self, service: str, operation: str, params: dict) -> None:
        self.timeline.append((self.clock(), f"{service}.{operation}", params))
        stub = self.session.stubs[service]
        if operation == "PutParameter":
            name = params["Name"].removeprefix(harden.SWITCH_PREFIX)
            self.clock.now += self.put_latency_s  # it lands as it returns
            if params["Value"] == "off" and name in self.off_put_fails:
                stub.add_client_error(
                    "put_parameter", "InternalServerError", http_status_code=500
                )
                return
            self.switches[name].append((self.clock(), params["Value"]))
            stub.add_response("put_parameter", {"Version": len(self.switches[name])})
        elif operation == "GetParameter":
            name = params["Name"].removeprefix(harden.SWITCH_PREFIX)
            found = self.parameter(name)
            if name == "publish" and self.read_back is not None:
                found["Value"] = self.read_back
            stub.add_response("get_parameter", {"Parameter": found})
        elif operation == "GetParameters":
            self.switch_reads += 1
            found = [
                self.parameter(n.removeprefix(harden.SWITCH_PREFIX))
                for n in params["Names"]
            ]
            for entry in found:
                late = self.switch_reads > 1  # not the start's check (C533)
                if late and entry["Name"].endswith("/" + str(self.final_on)):
                    entry["Value"] = "on"
            stub.add_response("get_parameters", {"Parameters": found})
        elif operation == "PutItem":
            item = {
                k: TypeDeserializer().deserialize(v) for k, v in params["Item"].items()
            }
            self.table[item["reportId"]] = self.ever[item["reportId"]] = item
            if self.put_item_raises:
                stub.add_client_error(
                    "put_item", "InternalServerError", http_status_code=500
                )
            else:
                stub.add_response("put_item", {})
        elif operation == "DeleteItem":
            if self.delete_fails:
                stub.add_client_error(
                    "delete_item", "InternalServerError", http_status_code=500
                )
                return
            key = (params["Key"]["pk"]["S"], params["Key"]["sk"]["S"])
            self.table = {
                r: i for r, i in self.table.items() if (i["pk"], i["sk"]) != key
            }
            stub.add_response("delete_item", {})
        elif operation == "GetItem":
            key = (params["Key"]["pk"]["S"], params["Key"]["sk"]["S"])
            # Only a consistent read is sure to see the delete; any other may be stale.
            held = self.table if params.get("ConsistentRead") is True else self.ever
            found = [i for i in held.values() if (i["pk"], i["sk"]) == key]
            typed = (
                {k: TypeSerializer().serialize(v) for k, v in found[0].items()}
                if found
                else None
            )
            stub.add_response("get_item", {"Item": typed} if typed else {})
        elif operation == "DescribeStacks":
            outputs = {
                "ApiUrl": API + "/",
                "FeedApiUrl": FEED + "/",
                "BucketName": "lusot-uploads",
                "QueueName": "lusot-upload-queue",
                "TableName": "lusot-reports",
            }
            stack = {
                "StackName": "lusot",
                "CreationTime": "2026-10-28T00:00:00Z",
                "StackStatus": "UPDATE_COMPLETE",
                "Outputs": [
                    {"OutputKey": k, "OutputValue": v} for k, v in outputs.items()
                ],
            }
            stub.add_response("describe_stacks", {"Stacks": [stack]})
        elif operation == "DescribeStackResource":
            detail = {
                "LogicalResourceId": params["LogicalResourceId"],
                "PhysicalResourceId": "lusot-analysis-log-group",
                "ResourceType": "AWS::Logs::LogGroup",
                "LastUpdatedTimestamp": "2026-10-28T00:00:00Z",
                "ResourceStatus": "UPDATE_COMPLETE",
            }
            stub.add_response(
                "describe_stack_resource", {"StackResourceDetail": detail}
            )
        elif operation == "FilterLogEvents":
            rid = params["filterPattern"].strip('"')
            events = [
                {
                    "logStreamName": "s",
                    "timestamp": 1,
                    "ingestionTime": 1,
                    "eventId": f"e{n}",
                    "message": f"[INFO]\t2026-11-03T02:15:00.000Z\treq\t{json.dumps(line)}\n",
                }
                for n, line in enumerate(self.lines.get(rid, []))
            ]
            stub.add_response("filter_log_events", {"events": events})
        elif operation == "HeadObject":
            if self.raw_present:
                stub.add_response("head_object", {"ContentLength": 10})
            else:
                stub.add_client_error(
                    "head_object", service_error_code="404", http_status_code=404
                )
        else:
            raise AssertionError(
                f"an AWS call the fake doesn't answer: {service}.{operation}"
            )

    def parameter(self, name: str) -> dict:
        return {
            "Name": harden.SWITCH_PREFIX + name,
            "Type": "String",
            "Value": self.value(name, 0),
            "Version": len(self.switches[name]),
        }

    # HTTP: the app's API, the feed's API and S3.
    def answer(self, status: int, body: object = None) -> httpx.Response:
        headers = {"Date": http_date(self.clock() + self.skew_s)}
        if body is None:
            return httpx.Response(status, headers=headers)
        return httpx.Response(status, json=body, headers=headers)

    def handle(self, request: httpx.Request) -> httpx.Response:
        request.read()
        url, path, method = str(request.url), request.url.path, request.method
        self.timeline.append(
            (self.clock(), f"{method} {request.url.host}{path}", request)
        )
        if url.startswith(S3_URL):
            return self.s3_post(request)
        publish_on = self.stopped("publish", "pins")
        reading = method == "GET" and path in ("/reports", "/map/pins", "/pins.geojson")
        if publish_on and self.raise_in_read is not None and reading:
            raise self.raise_in_read
        if request.url.host == "feed.test.invalid" and path == "/pins.geojson":
            shown = [] if publish_on else [LIVE_ID]
            if not publish_on or "feed" in self.leak:
                shown += list(self.table)
            features = [{"type": "Feature", "properties": {"id": rid}} for rid in shown]
            return self.answer(
                200, {"type": "FeatureCollection", "notice": "x", "features": features}
            )
        if method == "OPTIONS" and path == "/uploads":
            return self.answer(204)
        if method == "POST" and path == "/uploads":
            self.devices.append(request.headers.get("X-Lusot-Device"))
            if self.stopped("uploads", "uploads"):
                return self.answer(503, {"error": "uploads_paused"})
            rid = self.new_report()
            form = {
                "url": S3_URL,
                "fields": {"key": f"raw/{rid}.jpg", "Content-Type": "image/jpeg"},
            }
            return self.answer(
                201, {"reportId": rid, "upload": form, "expiresInS": 300}
            )
        if method == "GET" and path == "/samples":
            return self.answer(
                200,
                {"samples": [{"sampleId": SAMPLE_ID, "credit": "c", "license": "CC0"}]},
            )
        if method == "POST" and path.startswith("/samples/"):
            if self.stopped("uploads", "samples"):
                return self.answer(503, {"error": "uploads_paused"})
            return self.answer(201, {"reportId": self.new_report()})
        if method == "POST" and path == "/ask":
            paused = self.stopped("model-calls", "ask") and not self.ask_model
            answer = {
                "source": "plain_list" if paused else "model",
                "fallback": "model_calls_paused" if paused else None,
                "kind": "no_reports",
            }
            return self.answer(200, {"answer": answer})
        if method == "GET" and path in ("/reports", "/map/pins"):
            where = "nearby" if path == "/reports" else "map"
            pins = (
                [] if publish_on and where in self.lose_demo else [pin(DEMO_ID, "demo")]
            )
            if not publish_on or where in self.leak:
                pins += [pin(rid, "live") for rid in self.table]
            return self.answer(200, {"pins": pins})
        if method == "GET" and path.startswith("/reports/"):
            rid = path.removeprefix("/reports/")
            if rid in self.table:
                if self.own_read_status != 200:
                    return self.answer(self.own_read_status, {"error": "not_found"})
                return self.answer(
                    200,
                    {
                        "reportId": rid,
                        "status": "done",
                        "mode": "live",
                        "published": True,
                    },
                )
            report = self.reports.get(rid)
            return (
                self.answer(200, report)
                if report
                else self.answer(404, {"error": "not_found"})
            )
        return self.answer(500)

    def new_report(self) -> str:
        rid = next(self.ids)
        self.made.append(rid)
        self.reports[rid] = {"status": "pending", "mode": "private", "published": False}
        return rid

    def s3_post(self, request: httpx.Request) -> httpx.Response:
        body = request.content
        self.files.append(body)
        rid = re.search(rb"raw/(r_[0-9a-f]{32})\.jpg", body).group(1).decode()
        if self.stopped("model-calls", "handler"):
            self.reports[rid] = {
                "status": "failed",
                "refusalReason": "model_calls_paused",
                "mode": "private",
                "published": False,
            }
            self.lines[rid] = [
                {"reportId": rid, "outcome": "failed/model_calls_paused"}
            ]
        else:
            self.reports[rid] = {
                "status": "refused",
                "refusalReason": "too_dark",
                "mode": "private",
                "published": False,
            }
            self.lines[rid] = [
                {"reportId": rid, "outcome": "refused/too_dark", "meta_calls": 0}
            ]
        return httpx.Response(204, headers={"Date": http_date(self.clock())})

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handle))

    # What the timeline holds.
    def when(self, what: str, test=lambda detail: True) -> list[float]:
        return [
            at for at, name, detail in self.timeline if name == what and test(detail)
        ]

    def puts(self, name: str) -> list[tuple[float, str]]:
        """Each put of a switch: when it returned, and its value."""
        return [(at, value) for at, value in self.switches[name][1:]]


def world(seed: int = 0):
    clock = Clock(START)
    fake = FakeStack(clock, seed=seed)
    record = harden.RunRecord(
        harden.data_dir() / "ms7" / "2026-11-03", "switch_test", "S"
    )
    return clock, fake, record


def stack_of(fake):
    from smoke_upload import load_stack

    return load_stack(fake.session)


def publish(fake, clock, record, held=None):
    return switch_test.check_publish(
        fake.client(),
        API,
        FEED,
        fake.session.client("ssm"),
        fake.session.client("dynamodb"),
        "lusot-reports",
        record,
        offset_s=0,
        wall=clock,
        clock=clock.mono,
        sleep=clock.sleep,
        held=held,
    )


def uploads(fake, clock, record):
    return switch_test.check_uploads(
        fake.client(),
        API,
        fake.session.client("ssm"),
        record,
        offset_s=0,
        wall=clock,
        clock=clock.mono,
        sleep=clock.sleep,
    )


def model_calls(fake, clock, record, *, ask=True):
    return switch_test.check_model_calls(
        fake.client(),
        stack_of(fake),
        fake.session.client("ssm"),
        record,
        ask=ask,
        offset_s=0,
        wall=clock,
        clock=clock.mono,
        sleep=clock.sleep,
    )


def test_switch_is_reset_when_the_check_raises():
    session = StubSession("ssm")
    for version in (1, 2):
        session.stubs["ssm"].add_response("put_parameter", {"Version": version})
    with (
        pytest.raises(RuntimeError),
        switch_test.switch_on(session.client("ssm"), "uploads"),
    ):
        raise RuntimeError("the check broke")
    assert [(op, p["Value"]) for _, op, p in session.calls] == [
        ("PutParameter", "on"),
        ("PutParameter", "off"),
    ]
    session.done()


def test_reset_failure_prints_the_hand_command(capsys):
    session = StubSession("ssm")
    session.stubs["ssm"].add_response("put_parameter", {"Version": 1})
    session.stubs["ssm"].add_client_error(
        "put_parameter", "InternalServerError", http_status_code=500
    )
    with (
        pytest.raises(ClientError),
        switch_test.switch_on(session.client("ssm"), "uploads"),
    ):
        pass
    out = capsys.readouterr().out
    assert "STOP SWITCH LEFT ON" in out
    assert (
        "aws ssm put-parameter --name /lusot/stop/uploads --value off --type String"
        " --overwrite --profile lusot --region ap-southeast-1 --no-cli-pager"
    ) in out
    assert re.search(r"[0-9]{12}", out) is None


def test_item_written_only_after_switch_cache():
    # Review Focus 1: a put that takes 20 s lands as it returns, so the cache counts from then.
    clock, fake, record = world()
    fake.put_latency_s = 20.0
    time_, line = publish(fake, clock, record)
    assert line.startswith("S3 pass"), line
    [(on_returned, _), (_off_returned, off)] = fake.puts("publish")
    [put_at] = fake.when("dynamodb.PutItem")
    [read_back] = fake.when("ssm.GetParameter", lambda p: p["Name"].endswith("publish"))
    assert on_returned <= read_back <= put_at and off == "off"
    assert put_at >= on_returned + harden.SWITCH_CACHE_S + 5
    assert time_.name == "publish" and time_.act_s > 0 and time_.release_s >= 0


def test_publish_item_is_deleted_before_the_switch_goes_off():
    clock, fake, record = world()
    publish(fake, clock, record)
    order = [name for _, name, _ in fake.timeline]
    on = order.index("ssm.PutParameter")
    read_back = order.index("ssm.GetParameter")
    put = order.index("dynamodb.PutItem")
    delete = order.index("dynamodb.DeleteItem")
    get = order.index("dynamodb.GetItem")
    off = len(order) - 1 - order[::-1].index("ssm.PutParameter")
    assert on < read_back < put < delete < get < off
    assert any(name in READS for name in order[put:delete])  # the reads, in between
    [(_, get_params)] = [
        (at, p) for at, name, p in fake.timeline if name == "dynamodb.GetItem"
    ]
    assert get_params["ConsistentRead"] is True
    assert fake.table == {}


def test_s3_waits_for_both_caches():
    clock, fake, record = world()
    publish(fake, clock, record)
    [put_at] = fake.when("dynamodb.PutItem")
    reads = [at for at, name, _ in fake.timeline if at > put_at and name in READS]
    assert reads and min(reads) >= put_at + harden.FEED_CACHE_S


@pytest.mark.parametrize(
    "fault",
    ["connect_error", "interrupt", "put_applied_then_raised"],
)
def test_item_deleted_before_off_when_a_read_raises(fault):
    clock, fake, record = world()
    if fault == "connect_error":
        fake.raise_in_read = httpx.ConnectError("dropped")
    elif fault == "interrupt":
        fake.raise_in_read = KeyboardInterrupt()
    else:
        fake.put_item_raises = True  # the write landed, and the call raised anyway
    with pytest.raises((httpx.ConnectError, KeyboardInterrupt, ClientError)):
        publish(fake, clock, record)
    [delete_at] = fake.when("dynamodb.DeleteItem")
    [(_, _), (off_at, off)] = fake.puts("publish")
    assert delete_at <= off_at and off == "off"
    assert fake.table == {}


def test_failed_delete_keeps_publish_on(capsys):
    clock, fake, record = world()
    fake.delete_fails = True
    held = switch_test.PublishState()
    with pytest.raises(switch_test.PublishCleanupFailed):
        publish(fake, clock, record, held=held)
    assert [value for _, value in fake.puts("publish")] == ["on"]  # no "off" put
    assert held.may_exist and held.hand_fix is not None
    out = capsys.readouterr().out
    assert str(held.hand_fix) in out
    assert "r_" not in out and "<report>" not in out
    fix = held.hand_fix.read_text()
    [rid] = list(fake.table)
    assert "aws dynamodb delete-item" in fix and "--consistent-read" in fix
    assert fix.index("delete-item") < fix.index("get-item") < fix.index("put-parameter")
    assert "aws ssm put-parameter --name /lusot/stop/publish --value off" in fix
    # The key sits in its own file, which PowerShell 5.1 can't strip of its quotes.
    # Quoted, so a data folder with a space in its path (as on the laptop) stays one argument.
    key_files = re.findall(r'"file://([^"]+)"', fix)
    assert len(key_files) == 2 and len(set(key_files)) == 1
    [key_file] = key_files[:1]
    assert rid in Path(key_file).read_text() and rid not in fix


def test_failed_delete_through_main_points_to_the_hand_fix(capsys):
    clock, fake, _ = world()
    fake.delete_fails = True
    assert run_main(["--yes"], fake, clock) == 1
    out = capsys.readouterr().out
    assert "S3 FAIL" in out
    assert "PUBLISH KEPT ON ON PURPOSE" in out and "hand-fix-" in out
    # Never the bare command to set publish off, which would show the item.
    assert "/lusot/stop/publish --value off" not in out
    assert [value for _, value in fake.puts("publish")] == ["on"]


def test_no_paid_request_before_the_cache_expires():
    # One container stops uploads at once while another still runs samples for 30 s.
    clock, fake, record = world()
    fake.delays["uploads"] = 0.0
    _, line = uploads(fake, clock, record)
    assert line.startswith("S1 pass"), line
    [(on_at, _), *_] = fake.puts("uploads")
    samples = fake.when("POST api.test.invalid/samples/" + SAMPLE_ID)
    first_503 = min(fake.when("POST api.test.invalid/uploads", lambda r: r is not None))
    assert len(samples) == 1 and samples[0] >= first_503
    assert samples[0] >= on_at + harden.SWITCH_CACHE_S
    # S2: one question, once the cache has passed; with --no-ask, none.
    clock, fake, record = world()
    model_calls(fake, clock, record)
    [(on_at, _), *_] = fake.puts("model-calls")
    asks = fake.when("POST api.test.invalid/ask")
    assert len(asks) == 1 and asks[0] >= on_at + harden.SWITCH_CACHE_S
    clock, fake, record = world()
    model_calls(fake, clock, record, ask=False)
    assert fake.when("POST api.test.invalid/ask") == []


def test_s1_uses_a_fresh_device_per_probe():
    clock, fake, record = world()
    _, line = uploads(fake, clock, record)
    assert line.startswith("S1 pass"), line
    assert len(fake.devices) >= 3 and len(set(fake.devices)) == len(fake.devices)
    assert fake.files == []  # no photo went
    # A sample that still runs fails S1.
    clock, fake, record = world()
    fake.delays["samples"] = math.inf
    _, line = uploads(fake, clock, record)
    assert line.startswith("S1 FAIL"), line


def test_s1_ends_once_every_container_serves_again():
    # The probes' container serves at once, so only the cache wait keeps S2 from
    # meeting another container that still holds the switch.
    clock, fake, record = world()
    fake.delays["uploads"] = 0.0
    uploads(fake, clock, record)
    model_calls(fake, clock, record)
    [*_, (last_off, off)] = fake.puts("uploads")
    [(s2_on, _), *_] = fake.puts("model-calls")
    s2_first = min(
        at for at in fake.when("POST api.test.invalid/uploads") if at >= s2_on
    )
    assert (
        off == "off" and s2_on >= last_off + harden.SWITCH_CACHE_S and s2_first >= s2_on
    )


def test_s2_uses_dark_jpegs():
    clock, fake, record = world()
    time_, line = model_calls(fake, clock, record)
    assert line.startswith("S2 pass"), line
    paused, released = [rid for rid in fake.made if rid in fake.lines]
    assert fake.reports[paused]["refusalReason"] == "model_calls_paused"
    assert fake.reports[released]["refusalReason"] == "too_dark"
    assert [line["outcome"] for line in fake.lines[released]] == ["refused/too_dark"]
    assert (
        all(f.find(b"\xff\xd8\xff") >= 0 for f in fake.files) and len(fake.files) == 2
    )
    assert fake.when("s3.HeadObject")  # its raw photo was looked for, and is gone
    assert time_.name == "model-calls"


@pytest.mark.parametrize(
    "fault", ["paying", "raw_left", "handler_late", "model_answers", "wrong_release"]
)
def test_s2_fails_on_each_part(fault):
    clock, fake, record = world()
    if (
        fault == "wrong_release"
    ):  # the release's photo ends otherwise, with no Meta call
        original = fake.s3_post

        def other(request):
            response = original(request)
            for rid, report in fake.reports.items():
                if report.get("refusalReason") == "too_dark":
                    report["refusalReason"] = "too_blurry"
                    fake.lines[rid] = [
                        {
                            "reportId": rid,
                            "outcome": "refused/too_blurry",
                            "meta_calls": 0,
                        }
                    ]
            return response

        fake.s3_post = other
    if fault == "paying":  # a paused line that shows Meta calls
        original = fake.s3_post

        def paying(request):
            response = original(request)
            for lines in fake.lines.values():
                for entry in lines:
                    if entry["outcome"] == "failed/model_calls_paused":
                        entry["meta_calls"] = 3
            return response

        fake.s3_post = paying
    elif fault == "raw_left":
        fake.raw_present = True
    elif fault == "handler_late":  # the release's photo is still paused
        fake.delays["handler"] = 3600.0
    elif fault == "model_answers":
        fake.ask_model = True
    _, line = model_calls(fake, clock, record)
    assert line.startswith("S2 FAIL"), (fault, line)


@pytest.mark.parametrize(
    "change",
    [
        {"leak": {"nearby"}},
        {"leak": {"map"}},
        {"leak": {"feed"}},
        {"lose_demo": {"nearby"}},
        {"lose_demo": {"map"}},
        {"own_read_status": 404},
    ],
)
def test_s3_checks_demo_pins_and_the_own_read(change):
    clock, fake, record = world()
    for name, value in change.items():
        setattr(fake, name, value)
    _, line = publish(fake, clock, record)
    assert line.startswith("S3 FAIL"), (change, line)
    assert fake.table == {}  # deleted all the same
    clock, fake, record = world()
    _, line = publish(fake, clock, record)
    assert line.startswith("S3 pass"), line
    # The feed was read at the feed API's URL.
    assert fake.when("GET feed.test.invalid/pins.geojson")


def test_s3_stops_unless_publish_reads_back_on():
    clock, fake, record = world()
    fake.read_back = "off"
    with pytest.raises(CheckFailed, match="read back"):
        publish(fake, clock, record)
    assert fake.when("dynamodb.PutItem") == []  # no item went
    assert [value for _, value in fake.puts("publish")] == ["on", "off"]


def test_mistyped_value_also_stops_uploads():
    clock, fake, record = world()
    _, line = uploads(fake, clock, record)
    values = [value for _, value in fake.puts("uploads")]
    assert values == ["on", "off", "paused", "off"]
    [(paused_at, _)] = [put for put in fake.puts("uploads") if put[1] == "paused"]
    probes = [
        at
        for at, name, _ in fake.timeline
        if name == "POST api.test.invalid/uploads"
        and paused_at + harden.SWITCH_CACHE_S <= at
    ]
    assert probes, "no probe after the paused value reached the API"
    assert "paused: 503" in line
    # A paused value the API ignored fails S1.
    clock, fake, record = world()
    original = fake.stopped
    fake.stopped = lambda name, reader: (
        original(name, reader) and fake.value(name, 30) != "paused"
    )
    _, line = uploads(fake, clock, record)
    assert line.startswith("S1 FAIL")


def test_wait_for_times_out():
    clock = Clock(START)
    with pytest.raises(CheckFailed):
        switch_test.wait_for(
            lambda: False, timeout_s=10, clock=clock.mono, sleep=clock.sleep
        )
    assert 10 <= clock() - START <= 12
    seen = iter([False, False, True])
    assert (
        switch_test.wait_for(
            lambda: next(seen), timeout_s=10, clock=clock.mono, sleep=clock.sleep
        )
        == 4
    )


def run_main(argv, fake, clock):
    return switch_test.main(
        argv,
        session=fake.session,
        http=fake.client(),
        wall=clock,
        clock=clock.mono,
        sleep=clock.sleep,
    )


def test_a_switch_already_on_refuses_the_run(capsys):
    # C533: past CreditExpiresAt the credit guard has set model-calls on, and the
    # test's finally would set it back to off and let calls bill the card. So the run
    # owns the switches only when every one reads off, and flips nothing otherwise.
    clock, fake, _ = world()
    fake.switches["model-calls"] = [(-math.inf, "on")]
    assert run_main(["--yes"], fake, clock) == 2
    out = capsys.readouterr().out
    assert "refused: a switch isn't off before the test: model-calls" in out
    assert all(fake.puts(name) == [] for name in fake.switches)


def test_run_ends_with_all_switches_off(capsys):
    clock, fake, _ = world()
    assert run_main(["--yes"], fake, clock) == 0
    printed = capsys.readouterr().out
    assert "SWITCH TEST OK" in printed
    for check in ("S1 pass", "S2 pass", "S3 pass"):
        assert check in printed
    # Review Focus 2: no report id or masked id is printed, and every report is recorded.
    assert "r_" not in printed and "<report>" not in printed
    ordinals, _ = harden.load_records([harden.data_dir() / "ms7" / "2026-11-03"])
    assert set(fake.made) <= set(ordinals.values())
    assert "| `publish` |" in printed  # the times table
    # A switch that reads on at the end fails the run, though every check passed.
    clock, fake, _ = world(seed=1)
    fake.final_on = "uploads"
    assert run_main(["--yes"], fake, clock) == 1
    out = capsys.readouterr().out
    assert "S1 pass" in out and "S2 pass" in out and "S3 pass" in out
    assert "STOP SWITCH LEFT ON: uploads" in out
    # A reset that fails leaves it on too.
    clock, fake, _ = world(seed=2)
    fake.off_put_fails = {"model-calls"}
    assert run_main(["--yes"], fake, clock) == 1
    out = capsys.readouterr().out
    assert "STOP SWITCH LEFT ON" in out and "model-calls" in out


def test_a_server_clock_far_off_stops_the_run(capsys):
    clock, fake, _ = world()
    fake.skew_s = 400.0
    assert run_main(["--yes"], fake, clock) == 1
    assert "+400 s" in capsys.readouterr().out
    assert (
        fake.puts("uploads") == [] and fake.puts("publish") == []
    )  # no switch was set


def test_without_yes_nothing_is_sent(capsys):
    assert switch_test.main([], session=object(), http=object()) == 2
    assert "--yes" in capsys.readouterr().out


def test_times_table_is_quotable():
    times = [
        switch_test.SwitchTime("uploads", 31.2, 30.4),
        switch_test.SwitchTime("model-calls", 12.0, 14.5),
        switch_test.SwitchTime("publish", 96.3, 33.0),
    ]
    table = switch_test.times_table(
        times, when="2026-11-03", run="rehearsal"
    ).splitlines()
    assert table[0] == "| Switch | On: effect after | Off: back after | Measured |"
    assert table[1] == "|---|---|---|---|"
    assert table[2] == "| `uploads` | 32 s | 31 s | 2026-11-03, rehearsal |"
    assert table[3] == "| `model-calls` | 12 s | 15 s | 2026-11-03, rehearsal |"
    assert (
        table[4]
        == "| `publish` | 97 s, the feed's 60 s cache included | 33 s | 2026-11-03, rehearsal |"
    )
    assert table[5] == "" and table[6].startswith(
        "Each time runs from the put's return."
    )
    # A release that couldn't show says so.
    none = [switch_test.SwitchTime("publish", 96.3, None)]
    row = switch_test.times_table(none, when="2026-11-03", run="record").splitlines()[2]
    assert (
        row
        == "| `publish` | 97 s, the feed's 60 s cache included | not shown (no live pin) | 2026-11-03, record |"
    )
