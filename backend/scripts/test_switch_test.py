"""Tests for switch_test.py: S1 to S3, the stop switches (MS7 plan Task 4).

Fakes only. FakeStack is the deployed stack in memory: botocore's Stubber answers every
AWS call (SSM, DynamoDB, CloudFormation, CloudWatch Logs and S3), each answer queued by
StubSession's hook just before its call from the fake's state, and httpx's
MockTransport answers the app's API, the feed's API and S3. The API sees a switch 30 s
after its put, as its slowest container would; the analysis handler sees model-calls
at once. Nothing reaches AWS, the API or Meta, and no folder named sealed is made.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_switch_test.py
"""

import json
import math
import re
from datetime import UTC, datetime

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
    """The stack in memory, on the laptop's fake clock (no skew)."""

    def __init__(self, clock: Clock, *, seed: int = 0):
        self.clock = clock
        self.ids = iter(report_ids(200, seed=seed))
        self.made: list[str] = []
        self.switches = {name: [(-math.inf, "off")] for name in harden.SWITCHES}
        self.table: dict[str, dict] = {}  # the synthetic items, by report id
        self.reports: dict[str, dict] = {}  # reports the API made
        self.lines: dict[str, list[dict]] = {}  # the analysis log, by report id
        self.timeline: list[tuple[float, str, object]] = []
        self.devices: list[str | None] = []  # each POST /uploads' device id
        self.files: list[bytes] = []  # each S3 post's file
        self.leak: set[str] = set()  # reads that show the synthetic pin anyway
        self.lose_demo: set[str] = (
            set()
        )  # reads that drop the demo pin while publish is on
        self.own_read_status = 200
        self.delete_fails = False
        self.off_put_fails: set[str] = set()  # switches whose "off" put fails
        self.raise_in_read: BaseException | None = None  # once publish is on
        self.session = StubSession(*SERVICES, on_call=self.on_aws)

    # The switches, as each reader sees them.
    def value(self, name: str, delay_s: float) -> str:
        seen = self.clock() - delay_s
        return [value for at, value in self.switches[name] if at <= seen][-1]

    def api_stopped(self, name: str) -> bool:
        return self.value(name, harden.SWITCH_CACHE_S) != "off"

    # AWS, answered by Stubber with what the fake holds.
    def on_aws(self, service: str, operation: str, params: dict) -> None:
        now = self.clock()
        self.timeline.append((now, f"{service}.{operation}", params))
        stub = self.session.stubs[service]
        if operation == "PutParameter":
            name = params["Name"].removeprefix(harden.SWITCH_PREFIX)
            if params["Value"] == "off" and name in self.off_put_fails:
                stub.add_client_error(
                    "put_parameter", "InternalServerError", http_status_code=500
                )
                return
            self.switches[name].append((now, params["Value"]))
            stub.add_response("put_parameter", {"Version": len(self.switches[name])})
        elif operation == "GetParameter":
            name = params["Name"].removeprefix(harden.SWITCH_PREFIX)
            stub.add_response("get_parameter", {"Parameter": self.parameter(name)})
        elif operation == "GetParameters":
            found = [
                self.parameter(n.removeprefix(harden.SWITCH_PREFIX))
                for n in params["Names"]
            ]
            stub.add_response("get_parameters", {"Parameters": found})
        elif operation == "PutItem":
            item = {
                k: TypeDeserializer().deserialize(v) for k, v in params["Item"].items()
            }
            self.table[item["reportId"]] = item
            stub.add_response("put_item", {})
        elif operation == "DeleteItem":
            if self.delete_fails:
                stub.add_client_error(
                    "delete_item", "InternalServerError", http_status_code=500
                )
                return
            self.table = {
                rid: item
                for rid, item in self.table.items()
                if (item["pk"], item["sk"])
                != (params["Key"]["pk"]["S"], params["Key"]["sk"]["S"])
            }
            stub.add_response("delete_item", {})
        elif operation == "GetItem":
            key = (params["Key"]["pk"]["S"], params["Key"]["sk"]["S"])
            found = [i for i in self.table.values() if (i["pk"], i["sk"]) == key]
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
        headers = {"Date": http_date(self.clock())}
        return (
            httpx.Response(status, json=body, headers=headers)
            if body is not None
            else httpx.Response(status, headers=headers)
        )

    def handle(self, request: httpx.Request) -> httpx.Response:
        request.read()
        url, path, method = str(request.url), request.url.path, request.method
        self.timeline.append(
            (self.clock(), f"{method} {request.url.host}{path}", request)
        )
        if url.startswith(S3_URL):
            return self.s3_post(request)
        publish_on = self.api_stopped("publish")
        if (
            publish_on
            and self.raise_in_read is not None
            and method == "GET"
            and path in ("/reports", "/map/pins", "/pins.geojson")
        ):
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
            if self.api_stopped("uploads"):
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
            if self.api_stopped("uploads"):
                return self.answer(503, {"error": "uploads_paused"})
            return self.answer(201, {"reportId": self.new_report()})
        if method == "POST" and path == "/ask":
            paused = self.api_stopped("model-calls")
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
        # The handler reads model-calls on every delivery: the value now.
        if self.value("model-calls", 0) != "off":
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
        return [
            (at, detail["Value"])
            for at, what, detail in self.timeline
            if what == "ssm.PutParameter"
            and detail["Name"] == harden.SWITCH_PREFIX + name
        ]


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


def publish(fake, clock, record):
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
    clock, fake, record = world()
    (time_, line) = publish(fake, clock, record)
    assert line.startswith("S3 pass"), line
    [(on_at, _), (_off_at, off)] = fake.puts("publish")
    [put_at] = fake.when("dynamodb.PutItem")
    [read_back] = fake.when("ssm.GetParameter", lambda p: p["Name"].endswith("publish"))
    assert on_at <= read_back <= put_at and off == "off"
    assert put_at >= on_at + harden.SWITCH_CACHE_S + 5
    assert time_.name == "publish" and time_.act_s > 0 and time_.release_s >= 0


def test_publish_item_is_deleted_before_the_switch_goes_off():
    clock, fake, record = world()
    publish(fake, clock, record)
    reads = (
        "GET api.test.invalid/reports",
        "GET api.test.invalid/map/pins",
        "GET feed.test.invalid/pins.geojson",
    )
    order = [name for _, name, _ in fake.timeline]
    on = order.index("ssm.PutParameter")
    read_back = order.index("ssm.GetParameter")
    put = order.index("dynamodb.PutItem")
    delete = order.index("dynamodb.DeleteItem")
    get = order.index("dynamodb.GetItem")
    off = len(order) - 1 - order[::-1].index("ssm.PutParameter")
    assert on < read_back < put < delete < get < off
    assert any(name in reads for name in order[put:delete])  # the reads, in between
    assert fake.table == {}


def test_s3_waits_for_both_caches():
    clock, fake, record = world()
    publish(fake, clock, record)
    [put_at] = fake.when("dynamodb.PutItem")
    reads = [
        at
        for at, name, _ in fake.timeline
        if at > put_at
        and name
        in (
            "GET api.test.invalid/reports",
            "GET api.test.invalid/map/pins",
            "GET feed.test.invalid/pins.geojson",
        )
    ]
    assert reads and min(reads) >= put_at + harden.FEED_CACHE_S


@pytest.mark.parametrize("raised", [httpx.ConnectError("dropped"), KeyboardInterrupt()])
def test_item_deleted_before_off_when_a_read_raises(raised):
    clock, fake, record = world()
    fake.raise_in_read = raised
    with pytest.raises((type(raised), CheckFailed)):
        publish(fake, clock, record)
    [delete_at] = fake.when("dynamodb.DeleteItem")
    [(_, _), (off_at, off)] = fake.puts("publish")
    assert delete_at <= off_at and off == "off"
    assert fake.table == {}


def test_failed_delete_keeps_publish_on(capsys):
    clock, fake, record = world()
    fake.delete_fails = True
    with pytest.raises(switch_test.PublishCleanupFailed):
        publish(fake, clock, record)
    assert [value for _, value in fake.puts("publish")] == ["on"]  # no "off" put
    out = capsys.readouterr().out
    [path_text] = re.findall(r"\S*hand-fix-\S*\.txt", out)
    assert "r_" not in out and "<report>" not in out
    fix = (
        harden.data_dir() / "ms7" / "2026-11-03" / path_text.rsplit("/", 1)[-1]
    ).read_text()
    [rid] = list(fake.table)
    assert "aws dynamodb delete-item" in fix and rid in fix
    assert "aws ssm put-parameter --name /lusot/stop/publish --value off" in fix
    assert fix.index("delete-item") < fix.index("put-parameter")


def test_no_paid_request_before_the_cache_expires():
    clock, fake, record = world()
    uploads(fake, clock, record)
    [(on_at, _), *_] = fake.puts("uploads")
    samples = fake.when("POST api.test.invalid/samples/" + SAMPLE_ID)
    first_503 = min(
        at
        for at, name, request in fake.timeline
        if name == "POST api.test.invalid/uploads"
        and at >= on_at + harden.SWITCH_CACHE_S
    )
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
    # A paused line that shows Meta calls fails it.
    clock, fake, record = world()
    original = fake.s3_post

    def paying(request):
        response = original(request)
        for lines in fake.lines.values():
            for entry in lines:
                if entry["outcome"] == "failed/model_calls_paused":
                    entry["meta_calls"] = 3
        return response

    fake.s3_post = paying
    _, line = model_calls(fake, clock, record)
    assert line.startswith("S2 FAIL")


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
    original = fake.api_stopped
    fake.api_stopped = lambda name: original(name) and fake.value(name, 30) != "paused"
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
    # A switch left on at the end fails the run.
    clock, fake, _ = world(seed=1)
    fake.off_put_fails = {"model-calls"}
    assert run_main(["--yes"], fake, clock) == 1
    out = capsys.readouterr().out
    assert "STOP SWITCH LEFT ON" in out and "model-calls" in out


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
    assert len(table) == 5
