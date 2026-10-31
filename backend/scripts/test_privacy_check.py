"""Tests for privacy_check.py: P5 to P11 and P14, and the log scan (MS7 plan Task 5).

Fakes only: botocore's Stubber answers every AWS call, from each test's own state where
StubSession's hook queues the answer just before its call (stubs.py), and httpx's
MockTransport answers the API and the feed. Nothing reaches AWS, the API or Meta, and
no folder named sealed is made. Addresses, device ids, the key and report ids are built
at run time.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_privacy_check.py
"""

import io
import json
from pathlib import Path

import harden
import httpx
import privacy_check
import pytest
from boto3.dynamodb.types import TypeDeserializer
from botocore.response import StreamingBody
from smoke_upload import CheckFailed
from stubs import StubSession, report_ids

API = "https://a1b2c3.execute-api.test.invalid"
FEED = "https://f4e5d6.execute-api.test.invalid"
SCREEN = "Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories."
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "data"))


def queue_session(
    dlq_retention="518400", upload_retention="345600", messages=("0", "0")
):
    session = StubSession("sqs")
    stub = session.stubs["sqs"]
    for name, retention, visible, hidden in (
        ("lusot-upload-queue", upload_retention, "0", "0"),
        ("lusot-dead-letter-queue", dlq_retention, *messages),
    ):
        stub.add_response(
            "get_queue_url",
            {"QueueUrl": f"https://sqs.test.invalid/{name}"},
            {"QueueName": name},
        )
        stub.add_response(
            "get_queue_attributes",
            {
                "Attributes": {
                    "MessageRetentionPeriod": retention,
                    "ApproximateNumberOfMessages": visible,
                    "ApproximateNumberOfMessagesNotVisible": hidden,
                }
            },
        )
    return session


def test_queues_keep_c525s_days():
    def problems(**changes):
        session = queue_session(**changes)
        found = privacy_check.check_queues(
            session.client("sqs"), "lusot-upload-queue", "lusot-dead-letter-queue"
        )
        session.done()
        return found

    assert problems() == []
    assert (
        len(problems(dlq_retention="604800")) == 1
    )  # a redriven message could outlive 7 days
    assert len(problems(upload_retention="1209600")) == 1
    assert len(problems(messages=("1", "0"))) == 1  # one message left in it
    assert len(problems(messages=("0", "1"))) == 1


def rule(prefix, days, status="Enabled", *, filtered=False):
    found = {
        "ID": f"{prefix.strip('/')}-{days}",
        "Status": status,
        "Expiration": {"Days": days},
    }
    return found | ({"Filter": {"Prefix": prefix}} if filtered else {"Prefix": prefix})


def lifecycle_problems(rules):
    session = StubSession("s3")
    session.stubs["s3"].add_response(
        "get_bucket_lifecycle_configuration", {"Rules": rules}
    )
    found = privacy_check.check_lifecycle(session.client("s3"), "lusot-uploads")
    session.done()
    return found


def test_lifecycle_rules():
    ms1 = [rule("raw/", 1), rule("blurred/", 7), rule("overlay/", 7)]
    assert lifecycle_problems([*ms1, rule("demo/", 60)]) == []
    assert lifecycle_problems([*ms1, rule("demo/", 60, filtered=True)]) == []
    assert len(lifecycle_problems([*ms1[1:], rule("demo/", 60)])) == 1  # no raw/ rule
    assert (
        len(
            lifecycle_problems(
                [ms1[0], rule("blurred/", 14), ms1[2], rule("demo/", 60)]
            )
        )
        == 1
    )
    assert len(lifecycle_problems([*ms1, rule("demo/", 7)])) == 1
    assert len(lifecycle_problems([*ms1, rule("demo/", 60), rule("samples/", 30)])) == 1
    assert len(lifecycle_problems([*ms1, rule("demo/", 60, status="Disabled")])) == 1


def live_pin(**changes):
    return {
        "id": report_ids(1)[0],
        "lat": 14.6095,
        "lng": 120.9894,
        "gpsAccuracyM": 12,
        "capturedAt": "2026-11-03T02:15:00Z",
        "mode": "live",
        "level": "knee",
        "landmark": "rim_three_quarters",
        "passability": "NPLV",
        "levelIsFloor": False,
        "basis": {"vehicles": 1, "people": 0},
        "flags": 0,
    } | changes


def feature(pin):
    properties = {k: v for k, v in pin.items() if k not in ("lat", "lng")}
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [pin["lng"], pin["lat"]]},
        "properties": properties,
    }


def collection(*pins, **changes):
    return {
        "type": "FeatureCollection",
        "notice": SCREEN,
        "features": [feature(p) for p in pins],
    } | changes


def test_feed_allows_only_public_fields_and_four_decimals():
    assert privacy_check.feed_problems(collection(live_pin()), screen_line=SCREEN) == []
    assert privacy_check.map_problems([live_pin()]) == []
    device = "device-" + "0123456789abcdef"
    for bad in (
        live_pin(deviceId=device),
        live_pin(readings=[]),
        live_pin(lat=14.60951),
    ):
        assert (
            len(privacy_check.feed_problems(collection(bad), screen_line=SCREEN)) == 1
        ), bad
        assert len(privacy_check.map_problems([bad])) == 1, bad
    demo = live_pin(
        mode="demo", credit="Photo by a donor", place="Rizal Avenue", event="Carina"
    )
    assert privacy_check.map_problems([demo]) == []
    assert len(privacy_check.map_problems([live_pin(credit="Photo by a donor")])) == 1
    # No problem names a value it found.
    [problem] = privacy_check.map_problems([live_pin(deviceId=device)])
    assert device not in problem and report_ids(1)[0] not in problem


def test_feed_notice_is_the_screen_line():
    assert privacy_check.feed_problems(collection(), screen_line=SCREEN) == []
    for bad in (
        collection(notice=SCREEN[:-1]),
        {"type": "FeatureCollection", "features": []},
        collection(extra=1),
    ):
        assert len(privacy_check.feed_problems(bad, screen_line=SCREEN)) == 1, bad


def test_screen_line_is_read_from_the_app():
    assert privacy_check.screen_line() == SCREEN


def cors_session(*, feed=None, app=None, feed_routes=("GET /pins.geojson",)):
    session = StubSession("apigatewayv2")
    stub = session.stubs["apigatewayv2"]
    feed_cors = {"AllowOrigins": ["*"], "AllowMethods": ["GET"]} | (feed or {})
    app_cors = {
        "AllowOrigins": ["https://localhost", "https://web.test.invalid"],
        "AllowMethods": ["GET", "POST"],
        "ExposeHeaders": ["retry-after"],
    } | (app or {})
    stub.add_response(
        "get_api",
        {
            "ApiId": "f4e5d6",
            "Name": "feed",
            "ProtocolType": "HTTP",
            "CorsConfiguration": feed_cors,
        },
        {"ApiId": "f4e5d6"},
    )
    stub.add_response(
        "get_routes",
        {"Items": [{"RouteKey": key} for key in feed_routes]},
        {"ApiId": "f4e5d6"},
    )
    stub.add_response(
        "get_api",
        {
            "ApiId": "a1b2c3",
            "Name": "app",
            "ProtocolType": "HTTP",
            "CorsConfiguration": app_cors,
        },
        {"ApiId": "a1b2c3"},
    )
    return session


def test_feed_api_cors():
    def problems(**changes):
        session = cors_session(**changes)
        found = privacy_check.check_feed_cors(
            session.client("apigatewayv2"), app_api_id="a1b2c3", feed_api_id="f4e5d6"
        )
        session.done()
        return found

    assert problems() == []
    for changes in (
        {"feed": {"AllowCredentials": True}},
        {"feed": {"AllowMethods": ["GET", "POST"]}},
        {"feed_routes": ("GET /pins.geojson", "POST /pins.geojson")},
        {"app": {"AllowOrigins": ["*"]}},
        {"app": {"ExposeHeaders": []}},
    ):
        assert len(problems(**changes)) == 1, changes


def access_session(*, stage_logs=(), bucket_logging=False, trail_selectors=None):
    session = StubSession("apigatewayv2", "s3", "cloudtrail")
    for api_id in ("a1b2c3", "f4e5d6"):
        stage = {"StageName": "$default"}
        if api_id in stage_logs:
            stage["AccessLogSettings"] = {
                "DestinationArn": "arn:aws:logs:x",
                "Format": "$context.identity.sourceIp",
            }
        session.stubs["apigatewayv2"].add_response(
            "get_stages", {"Items": [stage]}, {"ApiId": api_id}
        )
    logging = (
        {"LoggingEnabled": {"TargetBucket": "logs", "TargetPrefix": "x/"}}
        if bucket_logging
        else {}
    )
    session.stubs["s3"].add_response(
        "get_bucket_logging", logging, {"Bucket": "lusot-uploads"}
    )
    trails = (
        []
        if trail_selectors is None
        else [{"Name": "trail", "TrailARN": "arn:aws:cloudtrail:x:trail/trail"}]
    )
    session.stubs["cloudtrail"].add_response("describe_trails", {"trailList": trails})
    if trail_selectors is not None:
        session.stubs["cloudtrail"].add_response("get_event_selectors", trail_selectors)
    return session


def access_problems(**changes):
    session = access_session(**changes)
    found = privacy_check.check_access_logs(
        session.client("apigatewayv2"),
        session.client("s3"),
        session.client("cloudtrail"),
        api_ids=("a1b2c3", "f4e5d6"),
        bucket="lusot-uploads",
    )
    session.done()
    return found


def test_access_logs_checked_on_both_apis():
    assert access_problems() == []
    assert len(access_problems(stage_logs=("f4e5d6",))) == 1  # the feed API's stage
    assert len(access_problems(stage_logs=("a1b2c3",))) == 1  # the app API's
    assert len(access_problems(bucket_logging=True)) == 1
    data_events = {
        "EventSelectors": [
            {
                "ReadWriteType": "All",
                "DataResources": [
                    {
                        "Type": "AWS::S3::Object",
                        "Values": ["arn:aws:s3:::lusot-uploads/"],
                    }
                ],
            }
        ]
    }
    assert len(access_problems(trail_selectors=data_events)) == 1
    management = {
        "EventSelectors": [
            {
                "ReadWriteType": "All",
                "IncludeManagementEvents": True,
                "DataResources": [],
            }
        ]
    }
    assert access_problems(trail_selectors=management) == []


def needles(key="", devices=()):
    return privacy_check.Needles(
        points=(harden.OUTSIDE_POINT, harden.SMOKE_SPOT),
        devices=tuple(devices),
        key=key,
    )


def test_scan_counts_without_returning_text():
    device = harden.new_device_id()
    key = "-".join(part for part in ("stub", "model", "key", "4f1c"))
    ipv4 = ".".join(str(octet) for octet in (203, 0, 113, 9))
    ipv6 = ":".join(group for group in ("2001", "db8", "", "7"))
    messages = [
        f"[INFO]\tsource {ipv4} asked",
        f"peer {ipv6} closed",
        '{"lat": 14.35, "lng": 121.25, "outcome": "done/level"}',
        "photo data /9j/4AAQSkZJRgABAQ",
        f"device {device}",
        f"the key {key} leaked",
    ]
    counts = privacy_check.scan_events(messages, needles(key=key, devices=[device]))
    assert counts == {
        "ipv4": 1,
        "ipv6": 1,
        "test point": 1,
        "jpeg base64": 1,
        "device id": 1,
        "model key": 1,
    }
    assert all(
        isinstance(name, str) and isinstance(n, int) for name, n in counts.items()
    )
    for text in (ipv4, ipv6, device, key, "14.35"):
        assert text not in repr(counts)


def test_lambda_lines_count_zero():
    rid = "8c1f2e4a-" + "1b2c-4d5e-9f00-0a1b2c3d4e5f"
    lines = [
        f"START RequestId: {rid} Version: $LATEST",
        f"END RequestId: {rid}",
        f"REPORT RequestId: {rid}\tDuration: 102.35 ms\tBilled Duration: 103 ms\tMemory Size: 512 MB\tMax Memory Used: 98 MB\tInit Duration: 450.12 ms",
        "INIT_START Runtime Version: python:3.13.v18\tRuntime Version ARN: arn:aws:lambda:ap-southeast-1::runtime:0a1b2c3d4e5f",
        '2026-11-03T02:15:00.000Z\treq-1\t[INFO]\t{"outcome": "done/level", "score": 121.25, "at": "02:15:00"}',
    ]
    assert (
        privacy_check.scan_events(
            lines, needles(key="-".join(part for part in ("stub", "key")))
        )
        == {}
    )


class FakeTable:
    """The reports table for P5, answered through Stubber from what was written."""

    def __init__(self, *, delete_fails=False):
        self.items, self.deleted, self.delete_fails = {}, [], delete_fails
        self.session = StubSession("dynamodb", on_call=self.on_aws)

    def on_aws(self, service, operation, params):
        stub = self.session.stubs[service]
        if operation == "PutItem":
            item = {
                k: TypeDeserializer().deserialize(v) for k, v in params["Item"].items()
            }
            self.items[item["reportId"]] = item
            stub.add_response("put_item", {})
        elif operation == "DeleteItem":
            if self.delete_fails:
                stub.add_client_error(
                    "delete_item", "InternalServerError", http_status_code=500
                )
                return
            key = (params["Key"]["pk"]["S"], params["Key"]["sk"]["S"])
            self.deleted.append(key)
            self.items = {
                r: i for r, i in self.items.items() if (i["pk"], i["sk"]) != key
            }
            stub.add_response("delete_item", {})


def api_for(table, *, show_hidden=(), read_status=404, raise_on=None):
    """The API and the feed: the time hides both items unless `show_hidden` names a read."""

    def handle(request):
        path = request.url.path
        if raise_on and raise_on in path:
            raise httpx.ConnectError("dropped")
        shown = list(table.items)  # what a read that ignored the times would show
        if request.url.host.startswith("f4e5d6") and path == "/pins.geojson":
            ids = shown if "feed" in show_hidden else []
            return httpx.Response(200, json=collection(*(live_pin(id=i) for i in ids)))
        if path in ("/reports", "/map/pins"):
            where = "nearby" if path == "/reports" else "map"
            ids = shown if where in show_hidden else []
            return httpx.Response(200, json={"pins": [live_pin(id=i) for i in ids]})
        if path.startswith("/reports/"):
            return httpx.Response(
                read_status,
                json={"error": "not_found"}
                if read_status == 404
                else {"status": "done"},
            )
        return httpx.Response(500)

    return httpx.Client(transport=httpx.MockTransport(handle))


def expired(table, **api):
    return privacy_check.expired_items_check(
        table.session.client("dynamodb"),
        api_for(table, **api),
        API,
        FEED,
        "lusot-reports",
        now_s=1_793_700_000,
    )


def test_expired_items_are_hidden_then_deleted():
    table = FakeTable()
    assert expired(table) == []
    assert table.items == {} and len(table.deleted) == 2
    for where in ("nearby", "map", "feed"):
        table = FakeTable()
        problems = expired(table, show_hidden=(where,))
        assert len(problems) == 1 and "r_" not in problems[0]
        assert table.items == {}  # deleted even when a check fails
    table = FakeTable()
    assert len(expired(table, read_status=200)) == 1  # C526: past expiresAt is a 404
    assert table.items == {}
    table = FakeTable()
    with pytest.raises(httpx.ConnectError):
        expired(table, raise_on="map")
    assert table.items == {}
    table = FakeTable(delete_fails=True)
    assert any("delete" in p for p in expired(table))


class FakeBucket:
    """The upload bucket for P3, answered through Stubber from `objects`."""

    def __init__(self, objects):
        self.objects = dict(objects)
        self.session = StubSession("s3", on_call=self.on_aws)

    def on_aws(self, service, operation, params):
        stub = self.session.stubs[service]
        if operation == "GetObject":
            data = self.objects.get(params["Key"])
            if data is None:
                stub.add_client_error("get_object", "NoSuchKey", http_status_code=404)
            else:
                stub.add_response(
                    "get_object",
                    {
                        "Body": StreamingBody(io.BytesIO(data), len(data)),
                        "ContentLength": len(data),
                    },
                )
        elif operation == "ListObjectsV2":
            keys = sorted(
                k for k in self.objects if k.startswith(params.get("Prefix", ""))
            )
            stub.add_response(
                "list_objects_v2",
                {
                    "Contents": [
                        {"Key": k, "Size": len(self.objects[k])} for k in keys
                    ],
                    "KeyCount": len(keys),
                    "IsTruncated": False,
                },
            )
        elif operation == "HeadObject":
            if params["Key"] in self.objects:
                stub.add_response("head_object", {"ContentLength": 1})
            else:
                stub.add_client_error(
                    "head_object", service_error_code="404", http_status_code=404
                )


def bucket_with_runs():
    first, second, demo = report_ids(3, seed=4)
    manifest = {
        "version": 1,
        "samples": [
            {
                "sampleId": "s0123456789",
                "credit": "c",
                "license": "CC0",
                "place": "Rizal Avenue",
                "date": "2024-07-24",
            },
            {
                "sampleId": "s9876543210",
                "credit": "Synthetic",
                "license": "CC0",
                "date": "",
            },  # a Set B composite
        ],
    }
    objects = {
        f"blurred/{first}.jpg": b"\xff\xd8 blurred one",
        f"overlay/{first}.jpg": b"\xff\xd8 overlay one",
        f"demo/blurred/{demo}.jpg": b"\xff\xd8 demo",
        f"demo/overlay/{demo}.jpg": b"\xff\xd8 demo overlay",
        "samples/manifest.json": json.dumps(manifest).encode(),
        "samples/s0123456789.jpg": b"\xff\xd8 sample",
        "samples/s9876543210.jpg": b"\xff\xd8 composite",
        f"raw/{second}.jpg": b"\xff\xd8 raw",
    }
    return FakeBucket(objects), {"L#6": first, "L#7": second}, demo


def test_fetch_names_by_ordinal(tmp_path, capsys):
    bucket, ordinals, demo = bucket_with_runs()
    out = tmp_path / "data" / "ms7" / "p3"
    paths = privacy_check.fetch_p3(
        bucket.session.client("s3"), "lusot-uploads", ordinals, out
    )
    names = sorted(p.name for p in paths)
    assert names == [
        "L#6-blurred.jpg",
        "L#6-overlay.jpg",
        "demo-1-blurred.jpg",
        "demo-1-overlay.jpg",
        "s0123456789.jpg",
    ]
    assert "s9876543210.jpg" not in names  # the Set B composite isn't fetched
    assert (out / "L#6-blurred.jpg").read_bytes() == b"\xff\xd8 blurred one"
    printed = capsys.readouterr().out
    for secret in [*ordinals.values(), demo, "blurred/", "samples/"]:
        assert secret not in printed
    # clear-p3 deletes only what fetch-p3 named.
    (out / "keep.txt").write_text("mine")
    assert privacy_check.clear_p3(out) == 5
    assert sorted(p.name for p in out.iterdir()) == ["keep.txt"]


def test_fetch_refuses_a_sealed_or_repo_folder(tmp_path):
    bucket, ordinals, _ = bucket_with_runs()
    for out in (tmp_path / "sealed" / "p3", REPO / "p3-copies"):
        with pytest.raises(CheckFailed):
            privacy_check.fetch_p3(
                bucket.session.client("s3"), "lusot-uploads", ordinals, out
            )
        assert not out.exists()
    assert not (tmp_path / "sealed").exists()


def test_raw_left_and_prefix_counts():
    bucket, ordinals, _ = bucket_with_runs()
    assert (
        privacy_check.raw_left(
            bucket.session.client("s3"), "lusot-uploads", list(ordinals.values())
        )
        == 1
    )
    counts = privacy_check.prefix_counts(bucket.session.client("s3"), "lusot-uploads")
    assert counts == {
        "blurred/": 1,
        "demo/": 2,
        "overlay/": 1,
        "raw/": 1,
        "samples/": 3,
    }


def test_main_clears_and_refuses_usage(tmp_path, capsys):
    out = tmp_path / "data" / "p3"
    out.mkdir(parents=True)
    (out / "L#1-blurred.jpg").write_bytes(b"x")
    assert (
        privacy_check.main(["clear-p3", str(out)], session=object(), http=object()) == 0
    )
    assert "cleared 1 P3 copies" in capsys.readouterr().out
    assert privacy_check.main(["fetch-p3"], session=object(), http=object()) == 2
    assert (
        privacy_check.main(
            ["clear-p3", str(REPO / "p3")], session=object(), http=object()
        )
        == 2
    )
