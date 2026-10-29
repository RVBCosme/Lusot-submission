"""Tests for smoke_upload.py's cloud checks (MS3a spec B1, B4, B5; MS4 Task 9).

Fakes only: httpx.MockTransport stands in for the API and S3's form posts, tmp_path
folders for the photos, and FakeCloud for the AWS clients, each of whose calls must
first pass botocore's own check of that operation (fake_aws.py's FakeSession, shared
with the other scripts' tests). The main() tests run on FakeTime,
a clock that moves only when the run sleeps or the fake cloud takes time. Nothing
reaches AWS or Meta.

check:py runs this file with the script's own dependencies (R115). Alone, from the
repo root (R5's pattern):
    uv run --with pytest --with "boto3[crt]" --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_smoke_upload.py
"""

import csv
import json
import random
import re
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from itertools import groupby
from pathlib import Path

import cv2
import guards
import httpx
import metro_manila
import numpy as np
import pytest
import smoke_upload
from botocore.exceptions import ClientError
from fake_aws import FakeSession
from smoke_upload import CheckFailed
from spend_loader import load_spend

SEED = 20261028
RID = "r_" + "0123456789abcdef" * 2
OTHER = "r_" + "fedcba9876543210" * 2
CAPTURED = "2026-10-29T01:02:03Z"
API = "https://api.test.invalid"
FORMS = "https://forms.test.invalid/"  # a report's form posts to FORMS + its id
QUEUE_URL = "https://queue.test.invalid/lusot-upload-queue"
OUTPUTS = {
    "ApiUrl": API + "/",  # the run must drop the trailing slash
    "BucketName": "lusot-uploads-test",
    "QueueName": "lusot-upload-queue",
}
FUNCTION = "lusot-analysis-function"
LOG_GROUP = "lusot-analysis-log-group"
APP = "https://localhost"  # the Capacitor app's origin
KEY_LOADED = '"model_key_loaded=true"'  # MS1's key-loaded check searches for this
# The line the analysis function logs at a cold start once the Meta key loads (C28).
KEY_LOADED_EVENT = (
    '[INFO]\t2026-10-29T01:00:00.000Z\treq-0\t{"outcome": "model_key_loaded=true"}\n'
)
PHRASES = ("floodwater", "wheel", "wheel rim", "person", "vehicle", "face")
SAM_MS = {phrase: 900 for phrase in (*PHRASES, "license plate")}  # 7 SAM calls
SPOT = {"lat": 14.35, "lng": 121.25}  # MS7's OUTSIDE_POINT, in Laguna de Bay
MANILA = {"lat": 14.6095, "lng": 120.9894}  # MS1's old spot, inside Metro Manila
DEVICE_HEADERS = "content-type,x-lusot-device"  # what the preflight asks for
LIMITS_TABLE = "lusot-limits-test"
LINKS = "https://links.test.invalid/"  # a presigned link is LINKS + its object key

# A reading as GET /reports/{id} gives it while INCHES_SHOWN is "false" (C507, C515).
READING = {
    "id": 2,
    "kind": "wheel",
    "landmark": "rim_three_quarters",
    "level": "knee",
    "used": True,
    "dropped": None,
}
# A level body's fields that only Task 14 and MS3b add: --phase-a waives them.
PHASE_B = ("readings", "overlayUrl", "layersUrl", "levelFrom")

# Final report bodies (C67, as MS4 extends it) and the log lines the handler writes.
LEVEL_BODY = {
    "reportId": RID,
    "status": "done",
    "capturedAt": CAPTURED,
    "mode": "private",
    "published": False,
    "noFloodSeen": False,
    "level": "knee",
    "landmark": "rim_three_quarters",
    "passability": "NPLV",
    "basis": {"vehicles": 1, "people": 0},
    "levelIsFloor": False,
    "levelFrom": "geometry",
    "readings": [READING],
    "gpsAccuracyM": 10,
    "photoUrl": f"{LINKS}blurred/{RID}.jpg",
    "overlayUrl": f"{LINKS}overlay/{RID}.jpg",
    "layersUrl": f"{LINKS}overlay/{RID}.json",
}
NO_FLOOD_BODY = {
    "reportId": RID,
    "status": "done",
    "capturedAt": CAPTURED,
    "mode": "private",
    "published": False,
    "noFloodSeen": True,
}
REFUSED_BODY = {
    "reportId": RID,
    "status": "refused",
    "capturedAt": CAPTURED,
    "mode": "private",
    "published": False,
    "refusalReason": "too_dark",
}


def without(body, *keys):
    return {k: v for k, v in body.items() if k not in keys}


def rid(n):
    return f"r_{n:032x}"


def paid(outcome, **fields):
    """The log line of a photo that went through SAM's 7 phrases and Muse Spark."""
    return {
        "outcome": outcome,
        "meta_calls": 8,
        "sam_ms": SAM_MS,
        "input_tokens": 2000,
        "output_tokens": 4000,
        "drops": {},
        **fields,
    }


def result(body):
    """A body's result fields, without the id, time, mode and published every body
    has, which FakeCloud adds."""
    return without(body, "reportId", "capturedAt", "mode", "published")


LEVEL = (result(LEVEL_BODY), paid("done/level", deciding="wheel"))
FLOOR = (
    {
        **result(LEVEL_BODY),
        "level": "tire",
        "landmark": "wheel_covered",
        "passability": "NPATV",
        "levelIsFloor": True,
    },
    paid("done/level", deciding="wheel"),
)
NO_FLOOD = (result(NO_FLOOD_BODY), paid("done/no_flood_seen"))
NO_REFERENCE = (
    {"status": "refused", "refusalReason": "no_usable_reference"},
    paid("refused/no_usable_reference", drops={"vehicle_moving": 2}),
)
TOO_DARK = (result(REFUSED_BODY), {"outcome": "refused/too_dark", "meta_calls": 0})
HAPPY = [LEVEL, NO_REFERENCE, NO_FLOOD, FLOOR, NO_REFERENCE]  # B1's five outcomes


def event(report_id, n=1, **fields):
    """An analysis log event in Lambda's text format: level, time, request id, JSON."""
    line = json.dumps({"reportId": report_id, **fields})
    return f"[INFO]\t2026-10-29T01:02:{n:02d}.000Z\treq-{n}\t{line}\n"


class FakeTime:
    """The time module as main() sees it in these tests.

    Its monotonic clock moves only when the run sleeps or the fake cloud takes time,
    so every wait ends at once. The wall clock stays real. A run that sleeps an hour
    has a wait with no bound, so sleeping fails then instead of hanging the test.
    """

    def __init__(self):
        self.now = 1000.0
        self.slept = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds
        if sum(self.slept) > 3600:
            raise AssertionError("the run sleeps without a bound")

    def time(self):
        return time.time()


class FakeCloud:
    """The deployed stack in memory, as the smoke run meets it.

    `handle` answers the API and S3's form posts, and FakeSession its AWS clients.
    POST /uploads makes a report `private` outside Metro Manila and `live` inside it,
    on the shared polygon, as uploads.ts does. Each photo is analysed as soon as it
    lands: a dark one is refused too_dark with no Meta call, as the quality gate would,
    and any other takes the next of `outcomes`. Each logs its line, stores a blurred
    photo, an overlay and its layers for a level, and deletes its raw photo. A form
    posted again after the result logs already_finished. A photo takes `upload_s` to
    reach S3, and its report shows processing for `processing_s` more. With `phase_a`,
    it is a stack without Task 14 and MS3b: no level holds PHASE_B's fields, and no
    overlay is stored. Nearby and the map list `nearby` and `on_map`, by report id.
    The spend counter starts at a seeded $1. Each name in `faults` breaks one step, as
    its method says. `trail` records what happened, in order.
    """

    def __init__(
        self, outcomes=(), *, faults=(), upload_s=0.0, processing_s=0.0, phase_a=False
    ):
        self.outcomes = list(outcomes)
        self.faults = set(faults)
        self.upload_s, self.processing_s = upload_s, processing_s
        self.phase_a = phase_a
        self.time = FakeTime()
        self.reports = {}  # report id -> its item's result fields
        self.modes = {}  # report id -> its mode, set by POST /uploads
        self.reads = Counter()  # report id -> GET /reports/{id} calls
        self.ready_at = {}  # report id -> when GET first shows its result
        self.objects = set()  # the bucket's keys
        self.events = [KEY_LOADED_EVENT]
        self.searches = []  # each log search's parameters
        self.lookups = []  # each describe_stack_resource's logical id
        self.trail = []
        self.transports = []  # each HTTPTransport's arguments
        self.devices = []  # each POST /uploads' X-Lusot-Device
        self.asked_headers = []  # each preflight's Access-Control-Request-Headers
        self.nearby = [OTHER]  # the pins near the spot, by report id
        self.on_map = [OTHER]  # the map's pins, by report id
        self.spent = []  # each ADD to the spend counter, in micro-dollars
        self.micro_total = 1_000_000  # the counter, seeded at $1
        self.stopped = False

    def transport(self, **kwargs):
        self.transports.append(kwargs)
        return httpx.MockTransport(self.handle)

    def handle(self, request):
        """The API and S3's form posts. Faults: no_cors_link and no_cors_form drop
        the allow-origin header, no_device_cors drops x-lusot-device from the
        preflight's allow-headers, repost_403 refuses a form posted after its report
        is final, not_private makes every report live, published shows every report
        published, index_lag answers a report's first 2 reads with 404 and
        never_indexed all of them, pin_found puts the run's first report on the map,
        and map_down answers the map with 503."""
        origin = request.headers.get("origin")
        cors = {"access-control-allow-origin": origin} if origin else {}
        url = str(request.url)
        if request.method == "OPTIONS" and url == f"{API}/uploads":
            self.trail.append(("preflight", origin))
            self.asked_headers.append(
                request.headers.get("access-control-request-headers")
            )
            allowed = (
                "content-type" if "no_device_cors" in self.faults else DEVICE_HEADERS
            )
            headers = cors | {"access-control-allow-headers": allowed}
            return httpx.Response(204, headers=headers)
        if request.method == "POST" and url == f"{API}/uploads":
            self.devices.append(request.headers.get("x-lusot-device"))
            if self.stopped:
                self.trail.append(("paused",))
                return httpx.Response(503, json={"error": "uploads_paused"})
            spot = json.loads(request.content)
            report_id = f"r_{len(self.reports):032x}"
            self.reports[report_id] = {"status": "pending"}
            inside = metro_manila.in_metro_manila(spot["lat"], spot["lng"])
            live = inside or "not_private" in self.faults
            self.modes[report_id] = "live" if live else "private"
            self.trail.append(("link", report_id, origin))
            form = {
                "url": FORMS + report_id,
                "fields": {
                    "key": f"raw/{report_id}.jpg",
                    "Content-Type": "image/jpeg",
                    "Policy": "policy",
                    "X-Amz-Signature": "signature",
                },
            }
            body = {"reportId": report_id, "upload": form, "expiresInS": 300}
            headers = {} if "no_cors_link" in self.faults else cors
            return httpx.Response(201, json=body, headers=headers)
        if request.method == "POST" and url.startswith(FORMS):
            report_id = url.removeprefix(FORMS)
            final = self.reports[report_id]["status"] != "pending"
            if b"image/png" in request.content or (
                final and "repost_403" in self.faults
            ):
                self.trail.append(("refused", report_id))
                text = "<Error><Code>AccessDenied</Code></Error>"
                return httpx.Response(403, text=text)
            content = request.content
            jpeg = content[
                content.find(b"\xff\xd8\xff") : content.rfind(b"\xff\xd9") + 2
            ]
            grey = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_GRAYSCALE)
            self.trail.append(("photo", report_id, grey.shape[1], origin))
            self.time.now += self.upload_s
            self.objects.add(f"raw/{report_id}.jpg")
            self.deliver(f"raw/{report_id}.jpg", grey)
            headers = {} if "no_cors_form" in self.faults else cors
            return httpx.Response(204, headers=headers)
        if request.method == "GET" and url.startswith(f"{API}/reports/"):
            report_id = url.removeprefix(f"{API}/reports/")
            self.reads[report_id] += 1
            lagging = "index_lag" in self.faults and self.reads[report_id] <= 2
            if (
                report_id not in self.reports
                or lagging
                or "never_indexed" in self.faults
            ):
                return httpx.Response(404, json={"error": "not_found"})
            report = self.reports[report_id]
            if self.time.now < self.ready_at.get(report_id, 0.0):
                report = {"status": "processing"}
            if report["status"] == "pending":
                self.trail.append(("pending", report_id))
            body = {
                "reportId": report_id,
                "capturedAt": CAPTURED,
                "mode": self.modes[report_id],
                "published": "published" in self.faults,
            }
            return httpx.Response(200, json=body | report)
        if request.method == "GET" and request.url.path == "/reports":
            assert dict(request.url.params) == {
                "lat": "14.35",
                "lng": "121.25",
                "radius": "300",
            }
            self.trail.append(("nearby",))
            return httpx.Response(200, json=self.pins(self.nearby))
        if request.method == "GET" and url == f"{API}/map/pins":
            self.trail.append(("map",))
            if "map_down" in self.faults:
                return httpx.Response(503, json={"message": "Service Unavailable"})
            first = [rid(0)] if "pin_found" in self.faults else []
            return httpx.Response(200, json=self.pins(self.on_map + first))
        raise AssertionError(f"unexpected {request.method} {url}")

    @staticmethod
    def pins(ids):
        """A pins answer as pins.ts gives it, in part: each report id at the spot."""
        return {"pins": [{"id": i, **SPOT, "mode": "live"} for i in ids]}

    def deliver(self, key, grey=None):
        """The analysis function on one notification for a raw photo.

        Faults: reuse_pays, no_already_finished and repost_keeps_raw change a
        delivery after the result; missing_bad_file the missing photo's end;
        keep_raw, blurred_always, no_blurred, overlay_always, no_overlay and silent a
        photo's first delivery.
        """
        report_id = key.removeprefix("raw/").removesuffix(".jpg")
        report = self.reports[report_id]
        if report["status"] != "pending":  # already final: a reused link (B5)
            if "reuse_pays" in self.faults:
                self.log(report_id, **paid("done/level"))
            if "no_already_finished" not in self.faults:
                self.log(report_id, outcome="already_finished")
            if "repost_keeps_raw" not in self.faults:
                self.objects.discard(key)
            return
        if key not in self.objects:  # the missing photo's notification
            if "missing_bad_file" in self.faults:
                report.update(status="failed", refusalReason="bad_file")
                self.log(report_id, outcome="failed/bad_file")
            else:
                report.update(status="failed", refusalReason="photo_missing")
                self.log(
                    report_id,
                    outcome="failed/photo_missing",
                    error="NoSuchKey",
                    http_status=404,
                )
            return
        self.ready_at[report_id] = self.time.now + self.processing_s
        fields, line = self.dark() if grey.mean() < 40 else self.outcomes.pop(0)
        if self.phase_a:  # neither Task 14 nor MS3b is deployed
            fields = without(fields, *PHASE_B)
        report.update(fields)
        level = "level" in fields and "no_blurred" not in self.faults
        if level or "blurred_always" in self.faults:
            self.objects.add(f"blurred/{report_id}.jpg")
        # Task 14's overlay and its layers, beside a level's blurred photo.
        overlay = "level" in fields and not self.phase_a
        if (overlay and "no_overlay" not in self.faults) or (
            "overlay_always" in self.faults
        ):
            self.objects |= {f"overlay/{report_id}.jpg", f"overlay/{report_id}.json"}
        if "silent" not in self.faults:
            self.log(report_id, **line)
        if "keep_raw" not in self.faults:
            self.objects.discard(key)

    def dark(self):
        """The dark photo's end: refused too_dark with meta_calls 0. Faults:
        dark_too_blurry, dark_pays and dark_line_without_meta_calls."""
        if "dark_too_blurry" in self.faults:
            fields = {"status": "refused", "refusalReason": "too_blurry"}
            return fields, {"outcome": "refused/too_blurry", "meta_calls": 0}
        fields, line = TOO_DARK[0], dict(TOO_DARK[1])
        if "dark_pays" in self.faults:
            line["meta_calls"] = 8
        if "dark_line_without_meta_calls" in self.faults:
            del line["meta_calls"]
        return fields, line

    def log(self, report_id, **fields):
        self.events.append(event(report_id, len(self.events), **fields, ms=1200))

    def cloudformation_describe_stacks(self, StackName):
        assert StackName == "lusot"
        outputs = [{"OutputKey": k, "OutputValue": v} for k, v in OUTPUTS.items()]
        return {"Stacks": [{"StackName": StackName, "Outputs": outputs}]}

    def cloudformation_describe_stack_resource(self, StackName, LogicalResourceId):
        assert StackName == "lusot"
        self.lookups.append(LogicalResourceId)
        ids = {
            "AnalysisFunction": FUNCTION,
            "AnalysisLogGroup": LOG_GROUP,
            "LimitsTable": LIMITS_TABLE,
        }
        return {"StackResourceDetail": {"PhysicalResourceId": ids[LogicalResourceId]}}

    def dynamodb_update_item(
        self,
        TableName,
        Key,
        UpdateExpression,
        ExpressionAttributeNames,
        ExpressionAttributeValues,
        ReturnValues,
    ):
        """spend.py's record_spend: one atomic ADD to the Meta spend counter (C527).

        Fault: spend_write_fails refuses it as IAM would, with an ARN in the message.
        """
        assert (TableName, Key, UpdateExpression) == (
            LIMITS_TABLE,
            {"pk": {"S": "spend#meta"}},
            "ADD #micro :n",
        )
        assert (ExpressionAttributeNames, ReturnValues) == (
            {"#micro": "micro_usd"},
            "UPDATED_NEW",
        )
        if "spend_write_fails" in self.faults:
            arn = f"arn:aws:iam::{'9' * 12}:user/rene-dev"
            error = {"Code": "AccessDeniedException", "Message": f"{arn} is denied"}
            meta = {"HTTPStatusCode": 400}
            raise ClientError({"Error": error, "ResponseMetadata": meta}, "UpdateItem")
        micro = int(ExpressionAttributeValues[":n"]["N"])
        self.spent.append(micro)
        self.micro_total += micro
        return {"Attributes": {"micro_usd": {"N": str(self.micro_total)}}}

    def lambda_get_function(self, FunctionName):
        assert FunctionName == FUNCTION
        config = {
            "LastModified": "2026-10-29T00:00:00.000+0000",  # Lambda's own format
            "LoggingConfig": {"LogGroup": LOG_GROUP},
        }
        return {"Configuration": config}

    def ssm_describe_parameters(self, ParameterFilters):
        changed = datetime(2026, 10, 28, tzinfo=UTC)
        return {"Parameters": [{"Name": "key", "LastModifiedDate": changed}]}

    def ssm_put_parameter(self, Name, Value, Type, Overwrite):
        assert (Name, Type, Overwrite) == ("/lusot/stop/uploads", "String", True)
        self.stopped = Value == "on"
        return {"Version": 2}

    def s3_head_object(self, Bucket, Key):
        assert Bucket == OUTPUTS["BucketName"]
        if Key not in self.objects:
            error = {"Code": "404", "Message": "Not Found"}
            meta = {"HTTPStatusCode": 404}
            raise ClientError({"Error": error, "ResponseMetadata": meta}, "HeadObject")
        return {"ContentLength": 1}

    def sqs_get_queue_url(self, QueueName):
        assert QueueName == OUTPUTS["QueueName"]
        return {"QueueUrl": QUEUE_URL}

    def sqs_send_message(self, QueueUrl, MessageBody):
        """One S3-shaped notification. Fault: queue_ignored never delivers it."""
        assert QueueUrl == QUEUE_URL
        # As S3 shapes it, and as the handler reads it: each record's object key.
        [record] = json.loads(MessageBody)["Records"]
        assert (record["eventSource"], record["eventName"]) == (
            "aws:s3",
            "ObjectCreated:Post",
        )
        assert record["s3"]["bucket"]["name"] == OUTPUTS["BucketName"]
        key = record["s3"]["object"]["key"]
        self.trail.append(("queue", key.removeprefix("raw/").removesuffix(".jpg")))
        if "queue_ignored" not in self.faults:
            self.deliver(key)
        return {"MessageId": "message-1"}

    def logs_filter_log_events(self, logGroupName, startTime, filterPattern):
        self.searches.append(
            {
                "logGroupName": logGroupName,
                "startTime": startTime,
                "filterPattern": filterPattern,
            }
        )
        phrase = filterPattern.strip('"')
        return {"events": [{"message": m} for m in self.events if phrase in m]}


def a_stack(cloud, since_ms=1_000, *, phase_a=False):
    """A Stack on FakeCloud's clients, as main() builds it from the stack."""
    return smoke_upload.Stack(
        FakeSession(cloud),
        API,
        OUTPUTS["BucketName"],
        OUTPUTS["QueueName"],
        LOG_GROUP,
        since_ms,
        phase_a=phase_a,
    )


def a_client(cloud):
    return httpx.Client(transport=httpx.MockTransport(cloud.handle))


def sent_item(label, report_id):
    """A photo as sent, for the checks that read only its label and report id."""
    return smoke_upload.Sent(label, report_id, {}, b"", 0.0, 0.0)


def listed_folder(folder, names, photos=None):
    """C87's folder: metro_manila_41.txt lists `names`, which sit in images (R116).

    The list is written as Windows tools write it: a BOM, CRLF line ends, full Windows
    paths, and a comment line first. A photo holds its `photos` bytes, or nothing.
    """
    (folder / "images").mkdir(parents=True, exist_ok=True)
    root = r"C:\Systems\Lusot\lusot-data\set_c\commons-ph-floods\images"
    lines = ["# file<TAB>licence: the Metro Manila photos, checked by hand"]
    lines += [f"{root}\\{name}\tCC BY 2.0" for name in names]
    (folder / "metro_manila_41.txt").write_bytes(
        ("\r\n".join(lines) + "\r\n").encode("utf-8-sig")
    )
    for n, name in enumerate(names):
        (folder / "images" / name).write_bytes(photos[n] if photos else b"")
    return folder


def write_credits(folder, credit_lines):
    """attribution.csv with C87's columns and a BOM: a row per photo in the mapping."""
    columns = [
        "file_name",
        "title",
        "commons_page_url",
        "author",
        "licence",
        "licence_url",
        "credit_line",
        "fetch_mode",
        "flags",
    ]
    with (folder / "attribution.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, columns)
        writer.writeheader()
        for name, credit in credit_lines.items():
            writer.writerow(
                {
                    "file_name": name,
                    "title": f"File:{name}",
                    "author": "A. Photographer",
                    "licence": "CC BY 2.0",
                    "credit_line": credit,
                    "fetch_mode": "original",
                    "flags": "metro_manila_or_ondoy_2009",
                }
            )


def test_seeded_order_follows_c87(tmp_path):
    names = [f"Flood_in_Manila_{n:02d}.jpg" for n in range(30)]
    # Listed out of order, so the order must come from sorting the names.
    folder = listed_folder(tmp_path / "commons", names[::-1])
    order = smoke_upload.seeded_photo_order(folder)
    draw = random.Random(SEED).sample(sorted(names), 30)
    # Each photo is opened in images by its listed name (R116).
    assert order == [folder / "images" / name for name in draw]
    # The prefix property R102 relies on: a shorter draw is the full order's start.
    assert [p.name for p in order[:20]] == random.Random(SEED).sample(sorted(names), 20)
    (folder / "images" / names[7]).unlink()
    missing = "1 of the 30 listed photos are missing from images"
    with pytest.raises(CheckFailed, match=missing):
        smoke_upload.seeded_photo_order(folder)
    # A photo directly in the folder, not in images, is missing too.
    (folder / names[7]).write_bytes(b"")
    with pytest.raises(CheckFailed, match=missing):
        smoke_upload.seeded_photo_order(folder)


def test_only_credited_photos_are_sent(tmp_path):
    names = ["a.jpg", "b.jpg", "c.jpg", "d.jpg", "e.jpg"]
    folder = listed_folder(tmp_path / "commons", names)
    credits = {
        "a.jpg": '"Flood, Manila" by A. Photographer, CC BY 2.0',
        "b.jpg": "",  # an empty credit line
        "d.jpg": "Flood by D. Photographer, public domain",
        "e.jpg": "Street by E. Photographer, CC BY 2.0",
    }  # and no row for c.jpg
    write_credits(folder, credits)
    photos = [folder / name for name in ("e.jpg", "b.jpg", "a.jpg", "c.jpg", "d.jpg")]
    kept, skipped = smoke_upload.credited(folder, photos)
    assert kept == [folder / "e.jpg", folder / "a.jpg", folder / "d.jpg"]
    assert skipped == 2
    # A credit line of spaces is no credit either.
    write_credits(folder, {"a.jpg": "   "})
    assert smoke_upload.credited(folder, [folder / "a.jpg"]) == ([], 1)


def test_photos_are_sent_as_the_app_sends_them(tmp_path):
    # 1 px stripes: INTER_AREA averages them, where other filters alias.
    stripes = np.zeros((3000, 4000), np.uint8)
    stripes[:, ::2] = 255
    big = tmp_path / "big.png"
    big.write_bytes(cv2.imencode(".png", stripes)[1].tobytes())
    sent = smoke_upload.as_app_jpeg(big)
    assert sent[:2] == b"\xff\xd8"
    decoded = cv2.imdecode(np.frombuffer(sent, np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape == (1200, 1600, 3)
    # Exactly the app's steps: INTER_AREA to 1,600 px, then JPEG at quality 85.
    bgr = cv2.cvtColor(stripes, cv2.COLOR_GRAY2BGR)
    shrunk = cv2.resize(bgr, (1600, 1200), interpolation=cv2.INTER_AREA)
    assert (
        sent
        == cv2.imencode(".jpg", shrunk, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes()
    )
    # A photo already within 1,600 px keeps its size, as in the app.
    small = tmp_path / "small.png"
    small.write_bytes(cv2.imencode(".png", stripes[:600, :800])[1].tobytes())
    shape = cv2.imdecode(
        np.frombuffer(smoke_upload.as_app_jpeg(small), np.uint8), 1
    ).shape
    assert shape == (600, 800, 3)


def test_dark_jpeg_is_below_the_brightness_cutoff():
    data = smoke_upload.dark_jpeg()
    assert data[:3] == b"\xff\xd8\xff"  # the handler reads only JPEG (C83)
    grey = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    assert grey.shape == (1200, 1600)
    assert grey.mean() < 40  # C44's brightness cutoff
    # A horizontal gradient from 0 to 30.
    assert grey[:, :10].mean() < 5 and grey[:, -10:].mean() > 25


def api_replies(*replies):
    """An API whose GET /reports answers each reply in turn: a status, or 404."""
    queue, asked = list(replies), []

    def handle(request):
        asked.append(str(request.url))
        reply = queue.pop(0)
        if reply == 404:
            return httpx.Response(404, json={"error": "not_found"})
        body = {
            "reportId": RID,
            "status": reply,
            "capturedAt": CAPTURED,
            "mode": "private",
            "published": False,
        }
        if reply == "done":
            body["noFloodSeen"] = True
        return httpx.Response(200, json=body)

    return httpx.Client(transport=httpx.MockTransport(handle)), asked


def still_processing_at(seconds):
    """wait_final on a report still processing `seconds` after its 204.

    The poll after that one finds it done.
    """
    http, _ = api_replies("processing", "processing", "done")
    times = iter([1000.0, 1000.0 + seconds])  # the 204 came at 1,000 s
    return smoke_upload.wait_final(
        http, API, RID, since=1000.0, clock=lambda: next(times), sleep=lambda _: None
    )


def test_wait_final_polls_through_processing():
    http, asked = api_replies("pending", "processing", 404, "done")
    sleeps = []
    body = smoke_upload.wait_final(
        http, API, RID, since=1000.0, clock=lambda: 1000.0, sleep=sleeps.append
    )
    assert body == NO_FLOOD_BODY
    assert sleeps == [2, 2, 2]
    assert asked == [f"{API}/reports/{RID}"] * 4
    # B1's bound is 120 s from the photo's 204 (C68). Still processing at 119.9 s
    # can end in time...
    assert still_processing_at(119.9)["status"] == "done"
    # ...but at 120 s it can't, since the next poll is later still, and the clock
    # passing 121 s while processing fails too.
    for seconds in (120.0, 121.0):
        with pytest.raises(CheckFailed, match="still processing after 120 s"):
            still_processing_at(seconds)


def test_report_body_shapes():
    # C67 as MS4 extends it: a level, no flood seen and a refusal pass, each with its
    # mode and published, and the level with its readings, accuracy and links.
    for body in (LEVEL_BODY, NO_FLOOD_BODY, REFUSED_BODY):
        smoke_upload.check_report_body(body)
    smoke_upload.check_report_body(LEVEL_BODY | {"gpsAccuracyM": 12.5})
    # The location, a stored key, the claim, the inches and a demo pin's fields never
    # reach a smoke report.
    for key, value in (
        ("photoKey", f"blurred/{RID}.jpg"),
        ("overlayKey", f"overlay/{RID}.jpg"),
        ("lat", 14.35),
        ("claimToken", "claim-token-value"),
        ("depthInMin", 17.3),
        ("depthInMax", 19.1),
        ("credit", "Photo by A. Donor"),
        ("place", "Rizal Avenue, Manila"),
        ("event", "Typhoon Carina"),
    ):
        with pytest.raises(CheckFailed, match=f"extra keys \\['{key}'\\]") as exc:
            smoke_upload.check_report_body(LEVEL_BODY | {key: value})
        assert str(value) not in str(exc.value)  # keys only, never their values
    # A reading's inches stay hidden too, while the deployed INCHES_SHOWN is "false".
    inches = LEVEL_BODY | {"readings": [READING, READING | {"inches": [17.3, 19.1]}]}
    with pytest.raises(CheckFailed, match="extra reading keys \\['inches'\\]") as exc:
        smoke_upload.check_report_body(inches)
    assert "17.3" not in str(exc.value)
    # A level needs every level field, links and all.
    for key in (
        "levelIsFloor",
        "levelFrom",
        "readings",
        "gpsAccuracyM",
        "photoUrl",
        "overlayUrl",
        "layersUrl",
    ):
        with pytest.raises(CheckFailed, match=f"missing keys \\['{key}'\\]"):
            smoke_upload.check_report_body(without(LEVEL_BODY, key))
    # Every body has its mode and published.
    for body in (LEVEL_BODY, NO_FLOOD_BODY, REFUSED_BODY):
        for key in ("mode", "published"):
            with pytest.raises(CheckFailed, match=f"missing keys \\['{key}'\\]"):
                smoke_upload.check_report_body(without(body, key))
    # No flood seen and a refusal take none of a level's fields.
    with pytest.raises(CheckFailed, match="extra keys \\['level'\\]"):
        smoke_upload.check_report_body(NO_FLOOD_BODY | {"level": "knee"})
    with pytest.raises(CheckFailed, match="extra keys \\['photoUrl'\\]"):
        smoke_upload.check_report_body(NO_FLOOD_BODY | {"photoUrl": LINKS})
    with pytest.raises(CheckFailed, match="extra keys \\['noFloodSeen'\\]"):
        smoke_upload.check_report_body(REFUSED_BODY | {"noFloodSeen": False})
    # Shapes: basis is exactly two counts, a flag is a boolean, the accuracy a number,
    # readings a list of objects, and a string isn't empty.
    for wrong, key in (
        (LEVEL_BODY | {"basis": {"vehicles": 1}}, "basis"),
        (LEVEL_BODY | {"basis": {"vehicles": 1, "people": True}}, "basis"),
        (LEVEL_BODY | {"levelIsFloor": "false"}, "levelIsFloor"),
        (LEVEL_BODY | {"gpsAccuracyM": True}, "gpsAccuracyM"),
        (LEVEL_BODY | {"gpsAccuracyM": "10"}, "gpsAccuracyM"),
        (LEVEL_BODY | {"readings": READING}, "readings"),
        (LEVEL_BODY | {"readings": ["wheel"]}, "readings"),
        (LEVEL_BODY | {"overlayUrl": ""}, "overlayUrl"),
        (REFUSED_BODY | {"refusalReason": ""}, "refusalReason"),
        (REFUSED_BODY | {"published": "false"}, "published"),
        (NO_FLOOD_BODY | {"mode": ""}, "mode"),
    ):
        with pytest.raises(CheckFailed, match=f"wrong \\['{key}'\\]"):
            smoke_upload.check_report_body(wrong)
    # Only a final status passes.
    with pytest.raises(CheckFailed, match="isn't final"):
        smoke_upload.check_report_body({"reportId": RID, "status": "processing"})


def test_reused_link_needs_a_fresh_form():
    smoke_upload.check_form_fresh(1000.0, 1280.0)
    with pytest.raises(CheckFailed, match="^reused link: form too old$"):
        smoke_upload.check_form_fresh(1000.0, 1280.1)
    # The B5 check tests the form's age before it posts the form again.
    cloud = FakeCloud()
    form = {"url": FORMS + RID, "fields": {"key": f"raw/{RID}.jpg"}}
    now = time.monotonic()
    # The form came 281 s ago; the photo went 81 s after it.
    item = smoke_upload.Sent("photo 1/5", RID, form, photo(0), now - 281, now - 200)
    http = httpx.Client(transport=httpx.MockTransport(cloud.handle))
    with pytest.raises(CheckFailed, match="^reused link: form too old$"):
        smoke_upload.check_reused_link(http, a_stack(cloud), item)
    assert cloud.trail == []  # nothing was posted


def test_log_lines_parse_the_lambda_text_format(capsys):
    cloud = FakeCloud()
    cloud.events = [
        # The brief's event, as Lambda's text format writes the handler's line.
        (
            "[INFO]\t2026-10-29T01:02:03.000Z\treq-1\t"
            f'{{"reportId": "{RID}", "meta_calls": 0}}\n'
        ),
        # Not JSON from the first {: skipped.
        f"[ERROR]\t2026-10-29T01:02:04.000Z\treq-2\tTraceback near {RID}: {{oops\n",
        # Another report's line that mentions this id: not this report's line.
        event(OTHER, 3, note=RID),
        # A line with nested objects, as the pipeline's fields are, parses whole.
        event(RID, 4, outcome="done/level", sam_ms={"wheel": 900}, drops={}),
    ]
    lines = smoke_upload.log_lines(a_stack(cloud), RID)
    assert lines == [
        {"reportId": RID, "meta_calls": 0},
        {
            "reportId": RID,
            "outcome": "done/level",
            "sam_ms": {"wheel": 900},
            "drops": {},
        },
    ]
    # The search is the stack's log group from the run's start, found once by main().
    assert cloud.searches == [
        {"logGroupName": LOG_GROUP, "startTime": 1_000, "filterPattern": f'"{RID}"'}
    ]
    assert cloud.lookups == []
    assert capsys.readouterr().out == ""  # log lines are never printed


def test_log_lines_wait_for_the_line_they_need():
    cloud = FakeCloud()
    cloud.events = [event(RID, 1, outcome="done/level", meta_calls=8)]
    now = [0.0]

    def sleep(seconds):
        now[0] += seconds
        cloud.events.append(event(RID, 2, outcome="already_finished"))

    lines = smoke_upload.log_lines(
        a_stack(cloud),
        RID,
        until="already_finished",
        clock=lambda: now[0],
        sleep=sleep,
    )
    assert [line["outcome"] for line in lines] == ["done/level", "already_finished"]
    assert now == [5.0]
    # A line that never comes: after 30 s it returns what it found.
    cloud.events = [event(RID, 1, outcome="error")]
    now[0], slept = 0.0, []

    def wait(seconds):
        now[0] += seconds
        slept.append(seconds)

    lines = smoke_upload.log_lines(
        a_stack(cloud),
        RID,
        until="failed/photo_missing",
        clock=lambda: now[0],
        sleep=wait,
    )
    assert lines == [{"reportId": RID, "outcome": "error"}]
    assert slept == [5] * 6


class LinkedPath:
    """Stands in for a link: as written it names no sealed folder, but it resolves
    into one. Nothing is made on disk, so no symlink and no sealed folder is needed.
    """

    def __init__(self, written, resolved):
        self.written, self.resolved = written, resolved

    def absolute(self):
        return self.written

    def resolve(self):
        return self.resolved


def test_sealed_paths_are_refused(tmp_path):
    # The offline runner's rule (C66): a part equal to "sealed", in any case, as
    # written or resolved, before anything is opened or listed. None of these exists.
    for parts in (
        ("sealed", "x.jpg"),
        ("set_b", "Sealed", "x.jpg"),
        ("sealed", "..", "x.jpg"),
    ):
        with pytest.raises(CheckFailed, match="inside a folder named sealed"):
            smoke_upload.refuse_sealed(tmp_path.joinpath(*parts))
    link = LinkedPath(tmp_path / "a" / "x.jpg", tmp_path / "SEALED" / "x.jpg")
    with pytest.raises(CheckFailed, match="inside a folder named sealed"):
        smoke_upload.refuse_sealed(link)
    # These pass: a part must equal "sealed".
    smoke_upload.refuse_sealed(LinkedPath(tmp_path / "a", tmp_path / "b"))
    smoke_upload.refuse_sealed(tmp_path / "unsealed" / "sealed.jpg")
    # Each step that reads the disk refuses first: these would raise OSError otherwise.
    sealed = tmp_path / "set_c" / "sealed"
    for read in (
        lambda: smoke_upload.seeded_photo_order(sealed),
        lambda: smoke_upload.credited(sealed, [sealed / "x.jpg"]),
        lambda: smoke_upload.as_app_jpeg(sealed / "x.jpg"),
    ):
        with pytest.raises(CheckFailed, match="inside a folder named sealed"):
            read()
    assert list(tmp_path.iterdir()) == []


def test_run_summary_counts_504_and_413_and_bills_from_usage():
    lines = [
        paid("done/level"),  # SAM's 7 calls and judge's, with its billed usage
        # judge ended on a 504: SAM's timings are in, and its usage never came.
        {
            "outcome": "failed/model_error",
            "meta_calls": 8,
            "sam_ms": SAM_MS,
            "meta_status": 504,
        },
        # SAM ended on a 413, before any timing was logged.
        {"outcome": "failed/model_error", "meta_calls": 7, "meta_status": 413},
        {"outcome": "failed/model_error", "meta_calls": 7, "meta_status": 504},
        # A Meta failure with no status, a non-Meta failure between SAM and judge,
        # and a usage the answer didn't report.
        {
            "outcome": "failed/model_error",
            "meta_calls": 8,
            "sam_ms": SAM_MS,
            "meta_status": None,
        },
        {"outcome": "failed/pipeline_error", "meta_calls": 7, "sam_ms": SAM_MS},
        paid("refused/no_usable_reference", input_tokens=None, output_tokens=None),
        # A token count isn't a bill, so it never adds to the cost.
        paid("done/no_flood_seen", counted_input_tokens=999_999),
        # Lines that end before the pipeline carry no meta_calls (Task 13's review).
        {"outcome": "refused/too_dark", "meta_calls": 0},
        {"outcome": "already_finished"},
        {"outcome": "model_key_rejected", "meta_status": 401},
    ]
    summary = smoke_upload.run_summary(lines)
    assert summary["calls"] == {"sam": 56, "judge": 5}
    assert summary["ended_on"] == {"sam": {504: 1, 413: 1}, "judge": {504: 1, 413: 0}}
    assert summary["billed_tokens"] == {"input": 4000, "output": 8000}
    # $2.50 per 1,000 SAM images; Muse Spark $1.25 and $4.25 per million tokens in, out:
    # 56 * 0.0025 + 4000 * 0.00000125 + 8000 * 0.00000425, exactly, as spend.py adds.
    assert summary["usd"] == Decimal("0.179")


def photo(n):
    """A bright test photo whose width, 100 + n px, tells which one was sent."""
    return cv2.imencode(".jpg", np.full((60, 100 + n, 3), 180, np.uint8))[1].tobytes()


NAMES = [f"Flood_in_Manila_{n:02d}.jpg" for n in range(20)]
ORDER = random.Random(SEED).sample(sorted(NAMES), 20)


def run_smoke(tmp_path, monkeypatch, cloud, *argv, credited=True):
    """main() against `cloud`, with 20 photos in a tmp_path C87 folder.

    Every photo has a credit line unless `credited` is False. The run's time module is
    the cloud's FakeTime.
    """
    folder = tmp_path / "data" / "set_c" / "commons-ph-floods"
    listed_folder(folder, NAMES, [photo(n) for n in range(20)])
    credit = "{} by A. Photographer, CC BY 2.0" if credited else ""
    write_credits(folder, {name: credit.format(name) for name in NAMES})
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "data"))
    # spend.py takes LIMITS_TABLE_NAME over the stack's LimitsTable.
    monkeypatch.delenv("LIMITS_TABLE_NAME", raising=False)
    monkeypatch.setattr(
        smoke_upload.boto3, "Session", lambda **kw: FakeSession(cloud, **kw)
    )
    monkeypatch.setattr(smoke_upload.httpx, "HTTPTransport", cloud.transport)
    monkeypatch.setattr(smoke_upload, "time", cloud.time)
    return smoke_upload.main(list(argv))


def sent_names(cloud):
    """The listed photos the run sent, in order, told apart by their widths."""
    return [
        NAMES[step[2] - 100]
        for step in cloud.trail
        if step[0] == "photo" and step[2] < 1600
    ]


def printed(capsys, tmp_path, cloud, *, timings=False):
    """The run's printed lines, with each timing as N unless `timings` is True.

    It never prints a photo's name, a path, a report id, or a URL of the API, the
    forms or the queue.
    """
    out = capsys.readouterr().out
    for private in (str(tmp_path), "Flood_in_Manila", "test.invalid", *cloud.reports):
        assert private not in out
    return (out if timings else re.sub(r"\b\d+\.\d s\b", "N s", out)).splitlines()


def test_b1_run_checks_in_order(tmp_path, monkeypatch, capsys):
    cloud = FakeCloud(HAPPY)
    before = time.time()
    assert run_smoke(tmp_path, monkeypatch, cloud) == 0
    after = time.time()
    assert cloud.session_kwargs == {
        "profile_name": "lusot",
        "region_name": "ap-southeast-1",
    }
    assert cloud.transports[0] == {"local_address": "0.0.0.0"}  # IPv4 only
    # B1's photos are positions 0 to 4 of C87's order; photo 1's form goes twice.
    assert sent_names(cloud) == [ORDER[0], *ORDER[:5]]
    width = {n: 100 + NAMES.index(ORDER[n]) for n in range(5)}
    assert cloud.trail == [
        ("preflight", APP),
        ("preflight", "http://localhost:4173"),
        ("link", rid(0), None),
        ("pending", rid(0)),  # S1: the report reads private before its photo goes
        ("photo", rid(0), width[0], None),
        # B5: as soon as the first paid report is final, before the next upload.
        ("photo", rid(0), width[0], None),
        *[
            step
            for n in range(1, 5)
            for step in (
                ("link", rid(n), None),
                ("pending", rid(n)),
                ("photo", rid(n), width[n], None),
            )
        ],
        # The dark photo comes from the app's origin.
        ("link", rid(5), APP),
        ("pending", rid(5)),
        ("photo", rid(5), 1600, APP),
        # No pin: nearby at the spot, then the map.
        ("nearby",),
        ("map",),
        # The missing photo: a report, then its notification, with no photo.
        ("link", rid(6), None),
        ("queue", rid(6)),
        ("link", rid(7), None),
        ("refused", rid(7)),  # the PNG
        ("paused",),
    ]
    assert cloud.time.slept == [35]  # only the stop switch waits here
    # The preflights ask for the device header, and the run's 9 POST /uploads all
    # carry one device id, a uuid4.
    assert cloud.asked_headers == [DEVICE_HEADERS] * 2
    [device] = set(cloud.devices)
    assert len(cloud.devices) == 9 and uuid.UUID(device).version == 4
    assert cloud.spent == [185_000]  # the run's $0.185, in micro-dollars
    assert printed(capsys, tmp_path, cloud) == [
        "photos: 5 of positions 0 to 4 in C87's order, 0 skipped without a credit line",
        (
            "cors: the preflight for POST /uploads allows https://localhost and"
            " http://localhost:4173, with the x-lusot-device header"
        ),
        "photo 1/5: done/level knee (NPLV) N s after its upload, 8 Meta calls",
        (
            "reused link: S3 took the form again (204), the raw photo was gone in N s,"
            " and the log has already_finished and still one line with Meta calls"
        ),
        "photo 2/5: refused/no_usable_reference N s after its upload, 8 Meta calls",
        "photo 3/5: done/no_flood_seen N s after its upload, 8 Meta calls",
        (
            "photo 4/5: done/level at least tire (NPATV) N s after its upload,"
            " 8 Meta calls"
        ),
        "photo 5/5: refused/no_usable_reference N s after its upload, 8 Meta calls",
        "the dark photo: refused/too_dark N s after its upload, 0 Meta calls",
        "no pin: none of the 6 reports is in nearby or on the map",
        (
            "stored photos: no raw photo left for 6 reports, and a blurred photo, an"
            " overlay and its layers only for the 2 with a level"
        ),
        (
            "spend: 40 Meta calls (SAM 35, judge 5); ended on 504: SAM 0, judge 0;"
            " on 413: SAM 0, judge 0; billed 10,000 input and 20,000 output tokens,"
            " estimated $0.1850"
        ),
        "spend recorded: $0.185 as smoke, counter total $1.185",
        (
            "missing photo: failed/photo_missing N s after its notification, S3 said"
            " NoSuchKey (HTTP 404)"
        ),
        "png upload: refused by S3 (403 AccessDenied)",
        "analysis log: model_key_loaded=true since the function or key last changed",
        "stop switch: 503 uploads_paused while on, then set back to off",
        "SMOKE OK in N s",
    ]
    # Every report's log search starts 5 minutes before the run did, for clock skew,
    # in the log group main() looked up once.
    starts = {
        s["startTime"] for s in cloud.searches if s["filterPattern"] != KEY_LOADED
    }
    [start] = starts
    assert (before - 300) * 1000 - 1 <= start <= (after - 300) * 1000
    assert {search["logGroupName"] for search in cloud.searches} == {LOG_GROUP}
    assert cloud.lookups.count("AnalysisLogGroup") == 1


def test_b1_bound_counts_from_the_photos_204(tmp_path, monkeypatch, capsys):
    # Each photo takes 50 s to reach S3 and its report 100 s more: 150 s after
    # POST /uploads but 100 s after the 204, inside C68's 120 s.
    cloud = FakeCloud(HAPPY, upload_s=50.0, processing_s=100.0)
    assert run_smoke(tmp_path, monkeypatch, cloud) == 0
    lines = printed(capsys, tmp_path, cloud, timings=True)
    assert lines[2] == (
        "photo 1/5: done/level knee (NPLV) 100.0 s after its upload, 8 Meta calls"
    )
    assert (
        "the dark photo: refused/too_dark 100.0 s after its upload, 0 Meta calls"
        in (lines)
    )


def test_b1_run_without_a_level_ends_with_exit_3(tmp_path, monkeypatch, capsys):
    cloud = FakeCloud([NO_REFERENCE, NO_FLOOD, NO_REFERENCE, NO_REFERENCE, NO_FLOOD])
    assert run_smoke(tmp_path, monkeypatch, cloud) == 3
    lines = printed(capsys, tmp_path, cloud)
    # C71: the outcomes and, for C75's diagnosis, each photo's drop causes; then the
    # B4 and B5 checks and the rest still run.
    at = lines.index(
        "the dark photo: refused/too_dark N s after its upload, 0 Meta calls"
    )
    assert lines[at + 1 : at + 9] == [
        (
            "no photo gave a level (C71): 2 done/no_flood_seen,"
            " 3 refused/no_usable_reference"
        ),
        "photo 1/5 drops: vehicle_moving 2",
        "photo 2/5 drops: none",
        "photo 3/5 drops: vehicle_moving 2",
        "photo 4/5 drops: vehicle_moving 2",
        "photo 5/5 drops: none",
        "no pin: none of the 6 reports is in nearby or on the map",
        (
            "stored photos: no raw photo left for 6 reports, and a blurred photo, an"
            " overlay and its layers only for the 0 with a level"
        ),
    ]
    assert any(line.startswith("reused link: S3 took the form again") for line in lines)
    assert lines[-2:] == [
        "stop switch: 503 uploads_paused while on, then set back to off",
        "SMOKE NO LEVEL in N s: every other check passed, so C71 applies (exit 3)",
    ]


# How each failing check ends the run: the fake cloud's set-up, then the reason
# after "SMOKE FAILED: ", then the run's sleeps when a bound or a wait decides.
FAILURES = {
    "raw photo kept": (
        {"faults": {"keep_raw"}},
        "photo 2/5: its raw photo is still in the bucket",
        None,
    ),
    "blurred photo without a level": (
        {"faults": {"blurred_always"}},
        "photo 2/5: a blurred photo but no level (B4)",
        None,
    ),
    "level without a blurred photo": (
        {"faults": {"no_blurred"}},
        "photo 1/5: a level but no blurred photo (B4)",
        None,
    ),
    "dark photo too blurry": (
        {"faults": {"dark_too_blurry"}},
        "the dark photo ended refused/too_blurry, expected refused/too_dark",
        None,
    ),
    "dark photo pays": (
        {"faults": {"dark_pays"}},
        "the dark photo's log shows 8 Meta calls, expected 0",
        None,
    ),
    "dark line without meta_calls": (
        {"faults": {"dark_line_without_meta_calls"}},
        "the dark photo's refused/too_dark line has meta_calls None, expected 0",
        None,
    ),
    "missing photo ends bad_file": (
        {"faults": {"missing_bad_file"}},
        "the missing photo ended failed/bad_file, expected failed/photo_missing",
        None,
    ),
    "missing photo never ends": (
        {"faults": {"queue_ignored"}},
        "the missing photo: still pending after 60 s",
        [2] * 30,
    ),
    "re-post refused": (
        {"faults": {"repost_403"}},
        "reused link: HTTP 403 AccessDenied, expected 204",
        None,
    ),
    "re-post's raw photo kept": (
        {"faults": {"repost_keeps_raw"}},
        "reused link: the raw photo is still there after 60 s",
        [2] * 30,
    ),
    "no already_finished line": (
        {"faults": {"no_already_finished"}},
        "reused link: no already_finished line in the analysis log",
        [5] * 6,
    ),
    "re-post pays": (
        {"faults": {"reuse_pays"}},
        "reused link: 2 log lines with Meta calls, expected 1",
        None,
    ),
    "no photo paid": (
        {"outcomes": [TOO_DARK] * 5},
        "reused link: no photo's log shows a Meta call, so B5 can't run",
        None,
    ),
    "no allow-origin on the link": (
        {"faults": {"no_cors_link"}},
        "POST /uploads: allow-origin None, expected 'https://localhost'",
        None,
    ),
    "no allow-origin on the form post": (
        {"faults": {"no_cors_form"}},
        "the S3 form post: allow-origin None, expected 'https://localhost'",
        None,
    ),
    "no credited photo": (
        {"credited": False},
        "no credited photo to send",
        None,
    ),
    "no outcome line": (
        {"faults": {"silent"}},
        "photo 1/5: no done/level line in the analysis log",
        [5] * 6,
    ),
    "report past 120 s": (
        {"processing_s": 121.0},
        "photo 1/5: still processing after 120 s",
        [2] * 60,
    ),
    # S1 (C513): no photo goes until its report reads private, and none pins.
    "not private": (
        {"faults": {"not_private"}},
        "photo 1/5: the report reads mode 'live', not private, so its photo wasn't"
        " sent",
        None,
    ),
    "report never found": (
        {"faults": {"never_indexed"}},
        "photo 1/5: the report wasn't found in 10 s, so its photo wasn't sent",
        [1] * 10,
    ),
    "published": (
        {"faults": {"published"}},
        "photo 1/5: published is true, expected false",
        None,
    ),
    "pin found": (
        {"faults": {"pin_found"}},
        "no pin: photo 1/5 found on the map (S1)",
        None,
    ),
    "level without an overlay": (
        {"faults": {"no_overlay"}},
        "photo 1/5: a level but no stored overlay (B4)",
        None,
    ),
    "overlay without a level": (
        {"faults": {"overlay_always"}},
        "photo 2/5: a stored overlay but no level (B4)",
        None,
    ),
    "preflight without the device header": (
        {"faults": {"no_device_cors"}},
        "preflight from https://localhost: allow-headers 'content-type', expected"
        " x-lusot-device",
        None,
    ),
}


@pytest.mark.parametrize(("setup", "reason", "slept"), FAILURES.values(), ids=FAILURES)
def test_failed_checks_end_the_run_with_their_reason(
    tmp_path, monkeypatch, capsys, setup, reason, slept
):
    setup = dict(setup)
    credited = setup.pop("credited", True)
    cloud = FakeCloud(setup.pop("outcomes", HAPPY), **setup)
    assert run_smoke(tmp_path, monkeypatch, cloud, credited=credited) == 1
    assert printed(capsys, tmp_path, cloud)[-1] == f"SMOKE FAILED: {reason}"
    if slept is not None:
        assert cloud.time.slept == slept


@pytest.mark.parametrize(
    ("argv", "calls", "reason"),
    [
        ((), 40, "photo 2/5: its raw photo is still in the bucket"),
        (
            ("--fallback",),
            16,
            "fallback photo 1/15: its raw photo is still in the bucket",
        ),
    ],
    ids=["b1", "fallback"],
)
def test_a_run_that_fails_after_paying_still_prints_the_spend(
    tmp_path, monkeypatch, capsys, argv, calls, reason
):
    # B4 fails once the photos are paid for, and the spend is printed and recorded
    # before the end.
    cloud = FakeCloud([NO_REFERENCE, LEVEL, *HAPPY], faults={"keep_raw"})
    assert run_smoke(tmp_path, monkeypatch, cloud, *argv) == 1
    lines = printed(capsys, tmp_path, cloud)
    assert lines[-3].startswith(f"spend: {calls} Meta calls")
    assert lines[-2].startswith("spend recorded: $")
    assert lines[-1] == f"SMOKE FAILED: {reason}"
    assert len(cloud.spent) == 1


def test_an_unreadable_photo_stops_the_run_before_any_upload(
    tmp_path, monkeypatch, capsys
):
    # B1's third photo can't be read, and the error's text holds its path.
    read_bytes = Path.read_bytes

    def refuse_one(path):
        if path.name == ORDER[2]:
            raise PermissionError(13, "Permission denied", str(path))
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", refuse_one)
    cloud = FakeCloud(HAPPY)
    assert run_smoke(tmp_path, monkeypatch, cloud) == 1
    # Only the error's class: printed() checks that no path or photo name is shown.
    assert printed(capsys, tmp_path, cloud)[-1] == "SMOKE FAILED: PermissionError"
    assert cloud.trail == []  # every photo is read before the first upload


@pytest.mark.parametrize(
    ("outcomes", "sent", "code", "last"),
    [
        ([NO_REFERENCE, NO_FLOOD, LEVEL], 3, 0, "SMOKE OK in N s"),
        (
            [NO_REFERENCE] * 15,
            15,
            3,
            (
                "SMOKE NO LEVEL in N s: no fallback photo gave a level either, so B1"
                " is partly met, with the drop causes above as its reason (C71,"
                " exit 3)"
            ),
        ),
    ],
    ids=["level", "none"],
)
def test_fallback_stops_at_the_first_level(
    tmp_path, monkeypatch, capsys, outcomes, sent, code, last
):
    cloud = FakeCloud(outcomes)
    assert run_smoke(tmp_path, monkeypatch, cloud, "--fallback") == code
    # C71: positions 5 to 19 of C87's order, one at a time, with checks 2, 5 and 6.
    assert sent_names(cloud) == ORDER[5 : 5 + sent]
    assert {step[0] for step in cloud.trail} == {
        "link",
        "pending",
        "photo",
        "nearby",
        "map",
    }
    # A device id carries at most 10 uploads, and none comes back.
    runs = [len(list(group)) for _, group in groupby(cloud.devices)]
    assert runs == ([10, sent - 10] if sent > 10 else [sent])
    assert len(set(cloud.devices)) == len(runs)
    lines = printed(capsys, tmp_path, cloud)
    assert lines[0] == (
        "photos: 15 of positions 5 to 19 in C87's order, 0 skipped without a credit"
        " line"
    )
    first = outcomes[0][1]["outcome"]
    assert (
        lines[1] == f"fallback photo 1/15: {first} N s after its upload, 8 Meta calls"
    )
    end = "up to the first level" if code == 0 else "and none gave a level"
    assert f"fallback: sent {sent} of 15 photos, {end}" in lines
    assert any(
        line.startswith("stored photos: no raw photo left for") for line in lines
    )
    assert any(line.startswith(f"spend: {8 * sent} Meta calls") for line in lines)
    assert any(line.startswith("spend recorded: $") for line in lines)
    assert lines[-1] == last


# MS4 Task 9: the smoke run stays private and off the map (S1, C513).


def test_smoke_spot_is_outside_metro_manila():
    # The shared polygon loads, so "outside" is its answer, not a missing file's.
    assert metro_manila.ncr_boundary() is not None
    assert metro_manila.in_metro_manila(**smoke_upload.SPOT) is False
    assert smoke_upload.SPOT == SPOT  # MS7's OUTSIDE_POINT, in Laguna de Bay
    assert metro_manila.in_metro_manila(**MANILA) is True  # the old spot pinned


def test_send_stops_unless_the_report_is_private(monkeypatch):
    # Review Focus 4: from a Manila spot the report reads live, so no form is posted.
    monkeypatch.setattr(smoke_upload, "SPOT", MANILA)
    cloud = FakeCloud([LEVEL])
    reason = (
        "^photo 1/5: the report reads mode 'live', not private, so its photo wasn't"
        " sent$"
    )
    with pytest.raises(CheckFailed, match=reason):
        smoke_upload.send(a_client(cloud), a_stack(cloud), "photo 1/5", photo(0))
    assert cloud.trail == [("link", rid(0), None), ("pending", rid(0))]
    assert cloud.objects == set()
    # From the spot it reads private, so the photo goes, after that read.
    monkeypatch.undo()
    cloud = FakeCloud([LEVEL])
    item = smoke_upload.send(a_client(cloud), a_stack(cloud), "photo 1/5", photo(0))
    assert item.report_id == rid(0)
    assert [step[0] for step in cloud.trail] == ["link", "pending", "photo"]
    # The report index can lag a new report, so the read polls every 1 s through 404s.
    cloud = FakeCloud([LEVEL], faults={"index_lag"})
    monkeypatch.setattr(smoke_upload, "time", cloud.time)
    smoke_upload.send(a_client(cloud), a_stack(cloud), "photo 1/5", photo(0))
    assert cloud.time.slept == [1, 1]
    assert [step[0] for step in cloud.trail] == ["link", "pending", "photo"]


def test_device_id_rotates_every_10_uploads(tmp_path, monkeypatch):
    smoke_upload.new_device()  # as main() does first
    cloud = FakeCloud()
    http = a_client(cloud)
    for _ in range(25):
        smoke_upload.request_upload(http, API)
    ids = list(dict.fromkeys(cloud.devices))
    assert cloud.devices == [ids[0]] * 10 + [ids[1]] * 10 + [ids[2]] * 5
    for device in ids:
        assert uuid.UUID(device).version == 4 and str(uuid.UUID(device)) == device
    # A new run starts a new id, though the last one had 5 uploads left.
    run = FakeCloud(HAPPY)
    assert run_smoke(tmp_path, monkeypatch, run) == 0
    [device] = set(run.devices)
    assert device not in ids


def test_no_pin_check(capsys):
    items = [
        sent_item("photo 1/5", rid(0)),
        sent_item("photo 2/5", rid(1)),
        sent_item("the dark photo", rid(2)),
    ]
    cloud = FakeCloud()  # nearby and the map list another report only
    smoke_upload.check_no_pin(a_client(cloud), a_stack(cloud), items)
    assert capsys.readouterr().out == (
        "no pin: none of the 3 reports is in nearby or on the map\n"
    )
    # Nearby at the spot with radius 300 (the fake checks the query), then the map.
    assert cloud.trail == [("nearby",), ("map",)]
    # A run report found fails, naming where and which, by label, never by id.
    for where, pins, reason in (
        ("nearby", [OTHER, rid(1)], "photo 2/5 found in nearby"),
        (
            "on_map",
            [rid(2), OTHER, rid(0)],
            "photo 1/5 and the dark photo found on the map",
        ),
    ):
        cloud = FakeCloud()
        setattr(cloud, where, pins)
        with pytest.raises(CheckFailed, match=f"^no pin: {reason} \\(S1\\)$") as exc:
            smoke_upload.check_no_pin(a_client(cloud), a_stack(cloud), items)
        assert not any(rid(n) in str(exc.value) for n in range(3))
    # An answer that can't be read fails too: it never passes for "no pin".
    cloud = FakeCloud(faults={"map_down"})
    with pytest.raises(
        CheckFailed, match="^no pin: GET /map/pins: HTTP 503 \\(Service Unavailable\\)$"
    ):
        smoke_upload.check_no_pin(a_client(cloud), a_stack(cloud), items)
    for answer in ({}, {"pins": {"id": rid(0)}}, {"pins": [rid(0)]}):
        http = httpx.Client(
            transport=httpx.MockTransport(
                lambda _, a=answer: httpx.Response(200, json=a)
            )
        )
        with pytest.raises(
            CheckFailed, match="^no pin: GET /reports: not a pins list$"
        ):
            smoke_upload.check_no_pin(http, a_stack(cloud), items)


def test_phase_a_waives_only_the_later_fields(tmp_path, monkeypatch, capsys):
    # On a Phase A stack a level body need not hold Task 14's and MS3b's fields...
    phase_a_level = without(LEVEL_BODY, *PHASE_B)
    smoke_upload.check_report_body(phase_a_level, phase_a=True)
    smoke_upload.check_report_body(LEVEL_BODY, phase_a=True)
    # ...which the full check still needs.
    missing = "missing keys \\['layersUrl', 'levelFrom', 'overlayUrl', 'readings'\\]"
    with pytest.raises(CheckFailed, match=missing):
        smoke_upload.check_report_body(phase_a_level)
    # Every other rule stands.
    for body, reason in (
        (phase_a_level | {"depthInMin": 17.3}, "extra keys \\['depthInMin'\\]"),
        (phase_a_level | {"credit": "Photo by A. Donor"}, "extra keys \\['credit'\\]"),
        (
            phase_a_level | {"readings": [READING | {"inches": [17.3, 19.1]}]},
            "extra reading keys \\['inches'\\]",
        ),
        (without(phase_a_level, "photoUrl"), "missing keys \\['photoUrl'\\]"),
        (without(phase_a_level, "gpsAccuracyM"), "missing keys \\['gpsAccuracyM'\\]"),
        (phase_a_level | {"overlayUrl": ""}, "wrong \\['overlayUrl'\\]"),
    ):
        with pytest.raises(CheckFailed, match=reason):
            smoke_upload.check_report_body(body, phase_a=True)
    # A live mode still fails: a final body must read private.
    cloud = FakeCloud(phase_a=True)
    cloud.reports[RID], cloud.modes[RID] = result(phase_a_level), "live"
    cloud.events.append(event(RID, 1, outcome="done/level", meta_calls=8))
    stack = a_stack(cloud, phase_a=True)
    with pytest.raises(CheckFailed, match="^photo 1/5: mode 'live', expected private$"):
        smoke_upload.await_report(
            a_client(cloud), stack, "photo 1/5", RID, since=time.monotonic()
        )
    # A run on a Phase A stack, whose levels have none of the later fields and no
    # overlay: check 6 doesn't look for one.
    cloud = FakeCloud(HAPPY, phase_a=True)
    assert run_smoke(tmp_path, monkeypatch, cloud, "--phase-a") == 0
    assert not any(key.startswith("overlay/") for key in cloud.objects)
    lines = printed(capsys, tmp_path, cloud)
    assert (
        "stored photos: no raw photo left for 6 reports, and a blurred photo only for"
        " the 2 with a level (Phase A: no overlay checked)"
    ) in lines
    assert lines[-1] == "SMOKE OK in N s"
    # Without --phase-a, the same stack fails.
    cloud = FakeCloud(HAPPY, phase_a=True)
    assert run_smoke(tmp_path, monkeypatch, cloud) == 1
    assert printed(capsys, tmp_path, cloud)[-1] == (
        "SMOKE FAILED: photo 1/5: report body (done): extra keys [], missing keys"
        " ['layersUrl', 'levelFrom', 'overlayUrl', 'readings']"
    )
    # With it, a live report still stops the run before its photo goes.
    cloud = FakeCloud(HAPPY, phase_a=True, faults={"not_private"})
    assert run_smoke(tmp_path, monkeypatch, cloud, "--phase-a") == 1
    assert printed(capsys, tmp_path, cloud)[-1] == (
        "SMOKE FAILED: photo 1/5: the report reads mode 'live', not private, so its"
        " photo wasn't sent"
    )
    assert "photo" not in {step[0] for step in cloud.trail}


def test_smoke_guards_are_the_shared_ones(tmp_path, monkeypatch, capsys):
    # T1: one sealed-path rule. refuse_sealed asks guards.is_sealed, and CheckFailed
    # stays this run's refusal...
    asked = []
    monkeypatch.setattr(guards, "is_sealed", lambda path: asked.append(path) or True)
    plain = tmp_path / "photos" / "x.jpg"
    refused = "^refused: a path inside a folder named sealed$"
    with pytest.raises(CheckFailed, match=refused):
        smoke_upload.refuse_sealed(plain)
    assert asked == [plain]
    # ...and has no rule of its own: what guards allows, it allows.
    monkeypatch.setattr(guards, "is_sealed", lambda path: False)
    smoke_upload.refuse_sealed(tmp_path / "sealed" / "x.jpg")
    # One output mask: say prints what guards.mask makes of a line, and masks nothing
    # itself.
    digits = "4" * 12
    monkeypatch.setattr(guards, "mask", lambda line: f"masked({line})")
    smoke_upload.say(f"account {digits}")
    monkeypatch.setattr(guards, "mask", lambda line: line)
    smoke_upload.say(f"account {digits}")
    assert capsys.readouterr().out == (f"masked(account {digits})\naccount {digits}\n")
    monkeypatch.undo()
    smoke_upload.say(f"account {digits}")
    assert capsys.readouterr().out == "account <account>\n"
    # No pattern of its own is left for either.
    patterns = [n for n, v in vars(smoke_upload).items() if isinstance(v, re.Pattern)]
    assert patterns == []


def test_smoke_records_its_spend(tmp_path, monkeypatch, capsys):
    spend = load_spend()
    # The prices are spend.py's, the Lambda's own (C527), and none of its own.
    assert smoke_upload.spend is spend
    for name in (
        "SAM_USD_PER_IMAGE",
        "SPARK_USD_PER_INPUT_TOKEN",
        "SPARK_USD_PER_OUTPUT_TOKEN",
    ):
        assert not hasattr(smoke_upload, name)
    with monkeypatch.context() as patched:
        patched.setitem(spend.PRICES, "sam_image", Decimal("1"))
        # 7 SAM images at $1, and Muse Spark's 2,000 and 4,000 billed tokens.
        summary = smoke_upload.run_summary([paid("done/level")])
        assert summary["usd"] == Decimal("7.0195")
    # After the run, its billed cost goes on the Meta spend counter, once, as smoke,
    # through a client with spend.py's settings.
    cloud = FakeCloud(HAPPY)
    assert run_smoke(tmp_path, monkeypatch, cloud) == 0
    assert cloud.spent == [185_000]  # $0.185: SAM's 35 images and the billed tokens
    assert cloud.client_settings["dynamodb"] == {"config": spend.SPEND_CONFIG}
    assert "LimitsTable" in cloud.lookups
    assert "spend recorded: $0.185 as smoke, counter total $1.185" in printed(
        capsys, tmp_path, cloud
    )
    # A failed write prints spend_error with the amount, for the tracker to add by
    # hand, and the run ends nonzero once its other checks have run.
    error = (
        "spend_error: usd 0.185 from this run isn't on the spend counter (AWS error in"
        " UpdateItem: AccessDeniedException (HTTP 400)); add it once by hand"
        " (docs/operations.md)"
    )
    cloud = FakeCloud(HAPPY, faults={"spend_write_fails"})
    assert run_smoke(tmp_path, monkeypatch, cloud) == 1
    lines = printed(capsys, tmp_path, cloud)
    assert error in lines
    assert not any("arn:" in line for line in lines)
    assert lines[-2:] == [
        "stop switch: 503 uploads_paused while on, then set back to off",
        "SMOKE FAILED: spend_error: this run's spend isn't on the counter (see above)",
    ]
    # So does a fallback run.
    cloud = FakeCloud([LEVEL], faults={"spend_write_fails"})
    assert run_smoke(tmp_path, monkeypatch, cloud, "--fallback") == 1
    lines = printed(capsys, tmp_path, cloud)
    assert any(line.startswith("spend_error: usd 0.") for line in lines)
    assert lines[-1] == (
        "SMOKE FAILED: spend_error: this run's spend isn't on the counter (see above)"
    )
    # A check that fails after paying keeps its own reason, and still prints the
    # spend_error line.
    cloud = FakeCloud(HAPPY, faults={"spend_write_fails", "keep_raw"})
    assert run_smoke(tmp_path, monkeypatch, cloud) == 1
    lines = printed(capsys, tmp_path, cloud)
    assert error in lines
    assert lines[-1] == "SMOKE FAILED: photo 2/5: its raw photo is still in the bucket"
    # Nothing billed, nothing recorded, as the handler does.
    cloud = FakeCloud([TOO_DARK] * 5)
    assert run_smoke(tmp_path, monkeypatch, cloud) == 1
    lines = printed(capsys, tmp_path, cloud)
    assert cloud.spent == []
    assert not any(line.startswith(("spend recorded", "spend_error")) for line in lines)
