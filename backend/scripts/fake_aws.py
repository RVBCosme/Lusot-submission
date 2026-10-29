"""AWS fakes shared by the scripts' tests (plan Task 8, F13).

FakeAws holds each call to botocore's own model of its operation, with no network and
no credentials, and FakeSession hands out one per service. test_smoke_upload.py's
FakeCloud answers them, and so does ScriptCloud below, the deployed stack in memory as
the operator scripts meet it: the reports table, the bucket, the queues, the stop
switches, the analysis log and the API, with the analysis run on each raw photo as it
lands. The rest is the tests' data: the open-licensed manifest and the consent log with
their real headers (F15), and C87's Commons folder.
"""

import copy
import csv
import io
import json
import re
import uuid
from datetime import UTC, datetime
from functools import wraps
from types import SimpleNamespace

import cv2
import httpx
import numpy as np
from botocore import xform_name
from botocore.exceptions import ClientError, ParamValidationError
from botocore.session import get_session
from botocore.validate import validate_parameters

_BOTOCORE = get_session()  # botocore's own service models; no network, no credentials


class FakeAws:
    """One AWS service's client, held to botocore's own model of each call.

    A call's parameters must pass botocore's check of its operation, and FakeCloud
    then answers it in its `<service>_<method>` method.
    """

    def __init__(self, cloud, service):
        self._cloud, self._service = cloud, service
        model = _BOTOCORE.get_service_model(service)
        self._operations = {
            xform_name(name): model.operation_model(name)
            for name in model.operation_names
        }

    def __getattr__(self, method):
        operation = self._operations[method]
        answer = getattr(self._cloud, f"{self._service}_{method}")

        def call(**params):
            try:
                validate_parameters(params, operation.input_shape)
            except ParamValidationError as exc:
                raise AssertionError(str(exc)) from None
            return answer(**params)

        return call

    def get_paginator(self, method):
        call = getattr(self, method)
        return SimpleNamespace(paginate=lambda **params: [call(**params)])


class FakeSession:
    def __init__(self, cloud, **kwargs):
        cloud.session_kwargs = kwargs
        self._cloud = cloud

    def client(self, service):
        return FakeAws(self._cloud, service)


# The stack as ScriptCloud deploys it. Every URL is under test.invalid, so a test can
# check that no output line holds one.
API = "https://api.test.invalid"
LINKS = "https://links.test.invalid/"  # a presigned link is LINKS + its object key
UPLOAD_QUEUE = "https://queue.test.invalid/lusot-upload-queue"
DEAD_LETTER_QUEUE = "https://queue.test.invalid/lusot-dead-letter-queue"
OUTPUTS = {
    "ApiUrl": API + "/",  # load_stack drops the trailing slash
    "BucketName": "lusot-uploads-test",
    "TableName": "lusot-reports-test",
    "QueueName": "lusot-upload-queue",
    "DeadLetterQueueName": "lusot-dead-letter-queue",
}
LOG_GROUP = "lusot-analysis-log-group"
PUBLISH = "/lusot/stop/publish"
MODEL_CALLS = "/lusot/stop/model-calls"
SENTINEL_IP = "203.0.113.77"  # an S3 record's uploader address, never printed
FINAL = ("done", "refused", "failed")
LEASE_S = 900  # report_store.LEASE_S
VISIBILITY_S = 1080  # the upload queue's
# The clock the tests start at: noon in Manila on Oct 29, 2026.
NOON = datetime(2026, 10, 29, 4, 0, tzinfo=UTC).timestamp()

# Analysis outcomes: the result fields and whether a stored copy is made. As the handler
# does, a copy is kept for a level, and for any outcome of a seed that reached SAM
# (Task 13's keep_photo), never for a photo that was missing.
LEVEL = (
    {
        "status": "done",
        "noFloodSeen": False,
        "level": "knee",
        "landmark": "rim_three_quarters",
        "passability": "NPLV",
        "levelIsFloor": False,
        "basis": {"vehicles": 1, "people": 0},
    },
    True,
)
NO_FLOOD = ({"status": "done", "noFloodSeen": True}, True)
REFUSED = ({"status": "refused", "refusalReason": "no_usable_reference"}, True)
PHOTO_MISSING = ({"status": "failed", "refusalReason": "photo_missing"}, False)
NO_COPY = ({"status": "done", "noFloodSeen": True}, False)


def typed(value):
    """A plain value as DynamoDB's low-level client writes it."""
    if isinstance(value, bool):
        return {"BOOL": value}
    if isinstance(value, str):
        return {"S": value}
    if isinstance(value, (int, float)):
        return {"N": str(value)}
    return {"M": {name: typed(inner) for name, inner in value.items()}}


def plain(attribute):
    """A low-level DynamoDB value as a plain one."""
    [(kind, value)] = attribute.items()
    if kind == "N":
        return float(value) if "." in value else int(value)
    if kind == "M":
        return {name: plain(inner) for name, inner in value.items()}
    return value


def log_name(fields):
    if fields["status"] != "done":
        return f"{fields['status']}/{fields['refusalReason']}"
    return "done/no_flood_seen" if fields["noFloodSeen"] else "done/level"


def iso(epoch_s):
    return datetime.fromtimestamp(epoch_s, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeClock:
    """time.time and time.sleep for a script under test.

    It moves only when the script sleeps, so every wait ends at once. A run that
    sleeps two hours has a wait with no bound, so sleeping fails then.
    """

    def __init__(self, now=NOON):
        self.now = float(now)
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds
        if sum(self.slept) > 7200:
            raise AssertionError("the run sleeps without a bound")


def _recorded(method):
    """Record a fake AWS call's name and parameters in `calls`, in order."""

    @wraps(method)
    def record(self, **params):
        self.calls.append((method.__name__, copy.deepcopy(params)))
        return method(self, **params)

    return record


class ScriptCloud:
    """The deployed stack in memory, as the operator scripts meet it.

    FakeSession(cloud) gives its AWS clients and `http()` its API and photo links.
    Each raw photo is analysed as soon as it lands, taking the next of `outcomes`: as
    the handler does, a final report only deletes the raw photo (already_finished), a
    live lease returns the message for the queue's visibility timeout (lease_held), a
    switch other than "off" pauses model calls, and a level in a pinning mode publishes
    while publish is "off". The result shows `processing_s` later. `calls` records
    every AWS call; `requests` every HTTP one.
    """

    def __init__(self, outcomes=(), *, now=NOON, processing_s=0.0):
        self.outcomes = [copy.deepcopy(outcome) for outcome in outcomes]
        self.clock = FakeClock(now)
        self.processing_s = processing_s
        self.items = {}  # (pk, sk) -> the typed item
        self.objects = {}  # the bucket: key -> bytes
        self.params = {PUBLISH: "off", MODEL_CALLS: "off", "/lusot/stop/uploads": "off"}
        self.queues = {UPLOAD_QUEUE: [], DEAD_LETTER_QUEUE: []}
        self.events = []  # the analysis log, in Lambda's text format
        self.calls = []
        self.requests = []
        self.ready_at = {}  # report id -> when its result shows
        self.returns = []  # (when, key): messages a live lease returned
        self.sent = 0

    # The tests' views.

    def called(self, name):
        return [params for called, params in self.calls if called == name]

    def by_id(self, report_id):
        found = [i for i in self.items.values() if i["reportId"]["S"] == report_id]
        return found[0] if found else None

    def keys(self, prefix=""):
        return sorted(key for key in self.objects if key.startswith(prefix))

    def http(self):
        return httpx.Client(transport=httpx.MockTransport(self.handle))

    def put(self, **fields):
        """Store an item made of plain fields, as another writer left it."""
        item = {name: typed(value) for name, value in fields.items()}
        self.items[(fields["pk"], fields["sk"])] = item
        return item

    # The analysis function.

    def deliver(self, key):
        match = re.fullmatch(r"raw/(r_[0-9a-f]{32})\.jpg", key)
        if match is None:
            return
        report_id = match.group(1)
        item = self.by_id(report_id)
        if item is None:
            self.log(report_id, outcome="error")
            return
        status = item["status"]["S"]
        if status in FINAL:
            self.objects.pop(key, None)
            self.log(report_id, outcome="already_finished")
            return
        held_s = self.clock() - int(item.get("claimedAt", {"N": "0"})["N"])
        if status == "processing" and held_s <= LEASE_S:  # another worker's live lease
            self.log(report_id, outcome="lease_held")
            self.returns.append((self.clock() + VISIBILITY_S, key))
            return
        if key not in self.objects:
            fields, keeps, calls = dict(PHOTO_MISSING[0]), False, 0
        elif self.params[MODEL_CALLS] != "off":
            fields = {"status": "failed", "refusalReason": "model_calls_paused"}
            keeps, calls = False, 0
        else:
            fields, keeps = copy.deepcopy(self.outcomes.pop(0))
            calls = 8
        level = "level" in fields
        mode = item["mode"]["S"]
        prefix = "demo/" if mode == "demo" else ""
        if keeps and (level or item.get("seed") == {"BOOL": True}):
            fields["photoKey"] = f"{prefix}blurred/{report_id}.jpg"
            self.objects[fields["photoKey"]] = b"blurred " + report_id.encode()
            if level:
                fields["overlayKey"] = f"{prefix}overlay/{report_id}.jpg"
                fields["layersKey"] = f"{prefix}overlay/{report_id}.json"
                self.objects[fields["overlayKey"]] = b"overlay"
                self.objects[fields["layersKey"]] = b"{}"
        if level and mode in ("live", "demo") and self.params[PUBLISH] == "off":
            fields |= {"published": True, "feedPart": mode}
        item.update({name: typed(value) for name, value in fields.items()})
        self.ready_at[report_id] = self.clock() + self.processing_s
        self.objects.pop(key, None)
        self.log(report_id, outcome=log_name(fields), meta_calls=calls)

    def due(self):
        """Deliver the returned messages whose visibility timeout has passed."""
        for entry in [entry for entry in self.returns if entry[0] <= self.clock()]:
            self.returns.remove(entry)
            self.deliver(entry[1])

    def log(self, report_id, **fields):
        line = json.dumps({"reportId": report_id, **fields})
        n = len(self.events)
        self.events.append(
            f"[INFO]\t2026-10-29T04:00:{n % 60:02d}.000Z\treq-{n}\t{line}\n"
        )

    def shown(self, item):
        """The item as a reader sees it: still processing until its result shows."""
        report_id = item["reportId"]["S"]
        if self.clock() < self.ready_at.get(report_id, 0.0):
            return item | {"status": {"S": "processing"}}
        return item

    # DynamoDB.

    @_recorded
    def dynamodb_put_item(self, TableName, Item):
        assert TableName == OUTPUTS["TableName"]
        self.items[(Item["pk"]["S"], Item["sk"]["S"])] = copy.deepcopy(Item)
        return {}

    @_recorded
    def dynamodb_get_item(self, TableName, Key, ConsistentRead):
        assert TableName == OUTPUTS["TableName"] and ConsistentRead is True
        self.due()
        item = self.items.get((Key["pk"]["S"], Key["sk"]["S"]))
        return {"Item": copy.deepcopy(self.shown(item))} if item else {}

    @_recorded
    def dynamodb_delete_item(self, TableName, Key):
        assert TableName == OUTPUTS["TableName"]
        self.items.pop((Key["pk"]["S"], Key["sk"]["S"]), None)
        return {}

    @_recorded
    def dynamodb_query(
        self,
        TableName,
        IndexName,
        KeyConditionExpression,
        ExpressionAttributeNames,
        ExpressionAttributeValues,
    ):
        assert TableName == OUTPUTS["TableName"]
        assert (IndexName, KeyConditionExpression, ExpressionAttributeNames) == (
            "reportId-index",
            "#reportId = :id",
            {"#reportId": "reportId"},
        )
        wanted = ExpressionAttributeValues[":id"]
        found = [i for i in self.items.values() if i["reportId"] == wanted]
        return {"Items": copy.deepcopy(found), "Count": len(found)}

    @_recorded
    def dynamodb_scan(
        self,
        TableName,
        FilterExpression,
        ExpressionAttributeNames,
        ExpressionAttributeValues,
    ):
        assert TableName == OUTPUTS["TableName"]
        assert (
            FilterExpression,
            ExpressionAttributeNames,
            ExpressionAttributeValues,
        ) == (
            "#mode = :demo",
            {"#mode": "mode"},
            {":demo": {"S": "demo"}},
        )
        found = [i for i in self.items.values() if i["mode"] == {"S": "demo"}]
        return {"Items": copy.deepcopy(found), "Count": len(found)}

    @_recorded
    def dynamodb_update_item(
        self,
        TableName,
        Key,
        UpdateExpression,
        ConditionExpression,
        ExpressionAttributeNames,
        ExpressionAttributeValues,
    ):
        assert TableName == OUTPUTS["TableName"]
        assert (UpdateExpression, ConditionExpression, ExpressionAttributeNames) == (
            "SET #visibleUntil = :now",
            "attribute_exists(#pk)",
            {"#visibleUntil": "visibleUntil", "#pk": "pk"},
        )
        self.items[(Key["pk"]["S"], Key["sk"]["S"])]["visibleUntil"] = (
            ExpressionAttributeValues[":now"]
        )
        return {}

    # S3. put_object takes no Tagging, so a tagged put fails the test.

    @_recorded
    def s3_put_object(self, Bucket, Key, Body, ContentType):
        assert Bucket == OUTPUTS["BucketName"]
        self.objects[Key] = Body
        if Key.startswith("raw/"):
            self.deliver(Key)
        return {}

    @_recorded
    def s3_get_object(self, Bucket, Key):
        assert Bucket == OUTPUTS["BucketName"]
        if Key not in self.objects:
            error = {"Code": "NoSuchKey", "Message": "The key does not exist."}
            meta = {"HTTPStatusCode": 404}
            raise ClientError({"Error": error, "ResponseMetadata": meta}, "GetObject")
        return {"Body": io.BytesIO(self.objects[Key])}

    @_recorded
    def s3_delete_object(self, Bucket, Key):
        assert Bucket == OUTPUTS["BucketName"]
        self.objects.pop(Key, None)
        return {}

    @_recorded
    def s3_copy_object(self, Bucket, CopySource, Key, TaggingDirective):
        # REPLACE with no Tagging leaves the copy untagged (Context7, S3's CopyObject).
        assert Bucket == OUTPUTS["BucketName"] and TaggingDirective == "REPLACE"
        source = CopySource.removeprefix(OUTPUTS["BucketName"] + "/")
        self.objects[Key] = self.objects[source]
        return {}

    @_recorded
    def s3_list_objects_v2(self, Bucket, Prefix):
        assert Bucket == OUTPUTS["BucketName"]
        keys = self.keys(Prefix)
        # As S3 answers, an empty listing has no Contents.
        page = {"KeyCount": len(keys)}
        if keys:
            page["Contents"] = [{"Key": key} for key in keys]
        return page

    # SSM, CloudFormation and CloudWatch Logs.

    @_recorded
    def ssm_get_parameter(self, Name):
        return {
            "Parameter": {"Name": Name, "Type": "String", "Value": self.params[Name]}
        }

    @_recorded
    def cloudformation_describe_stacks(self, StackName):
        assert StackName == "lusot"
        outputs = [{"OutputKey": k, "OutputValue": v} for k, v in OUTPUTS.items()]
        return {"Stacks": [{"StackName": StackName, "Outputs": outputs}]}

    @_recorded
    def cloudformation_describe_stack_resource(self, StackName, LogicalResourceId):
        assert (StackName, LogicalResourceId) == ("lusot", "AnalysisLogGroup")
        return {"StackResourceDetail": {"PhysicalResourceId": LOG_GROUP}}

    @_recorded
    def logs_filter_log_events(self, logGroupName, startTime, filterPattern):
        assert logGroupName == LOG_GROUP
        phrase = filterPattern.strip('"')
        return {"events": [{"message": m} for m in self.events if phrase in m]}

    # SQS. A message sent to the upload queue for a report's raw key is delivered.

    @_recorded
    def sqs_get_queue_url(self, QueueName):
        urls = {
            OUTPUTS["QueueName"]: UPLOAD_QUEUE,
            OUTPUTS["DeadLetterQueueName"]: DEAD_LETTER_QUEUE,
        }
        return {"QueueUrl": urls[QueueName]}

    @_recorded
    def sqs_send_message(self, QueueUrl, MessageBody, MessageAttributes=None):
        self.sent += 1
        message = dead_letter(MessageBody, n=1000 + self.sent, sent_s=self.clock())
        if MessageAttributes is not None:
            message["MessageAttributes"] = MessageAttributes
        self.queues[QueueUrl].append(message)
        if QueueUrl == UPLOAD_QUEUE:
            try:
                records = json.loads(MessageBody)["Records"]
            except (ValueError, KeyError, TypeError):
                records = []
            for record in records:
                self.deliver(record["s3"]["object"]["key"])
        return {"MessageId": message["MessageId"]}

    @_recorded
    def sqs_receive_message(
        self,
        QueueUrl,
        MaxNumberOfMessages,
        VisibilityTimeout,
        WaitTimeSeconds,
        MessageAttributeNames,
    ):
        out = []
        for message in self.queues[QueueUrl]:
            if (
                message["_visible_at"] <= self.clock()
                and len(out) < MaxNumberOfMessages
            ):
                message["_visible_at"] = self.clock() + VisibilityTimeout
                out.append({k: v for k, v in message.items() if not k.startswith("_")})
        return {"Messages": copy.deepcopy(out)} if out else {}

    @_recorded
    def sqs_delete_message(self, QueueUrl, ReceiptHandle):
        queue = self.queues[QueueUrl]
        queue[:] = [m for m in queue if m["ReceiptHandle"] != ReceiptHandle]
        return {}

    # The API and the presigned photo links.

    def handle(self, request):
        self.due()
        url = request.url
        self.requests.append((request.method, str(url), dict(request.headers)))
        if url.host == "links.test.invalid":
            key = url.path.lstrip("/")
            return httpx.Response(200 if key in self.objects else 403)
        assert url.host == "api.test.invalid", url
        path, method = url.path, request.method
        if method == "GET" and path.startswith("/reports/"):
            return self.report(path.removeprefix("/reports/"))
        if method == "GET" and path == "/reports":
            spot = (float(url.params["lat"]), float(url.params["lng"]))
            assert float(url.params["radius"]) <= 300
            pins = [pin for pin in self.pins() if (pin["lat"], pin["lng"]) == spot]
            return httpx.Response(200, json={"pins": pins})
        if method == "GET" and path == "/map/pins":
            return httpx.Response(200, json={"pins": self.pins()})
        if method == "POST" and path.endswith("/flag"):
            return self.flag(path.split("/")[2], request)
        if method == "GET" and path == "/samples":
            listed = [
                {k: v for k, v in entry.items() if k in SAMPLE_FIELDS}
                | {"photoUrl": f"{LINKS}samples/{entry['sampleId']}.jpg"}
                for entry in self.manifest()["samples"]
            ]
            return httpx.Response(200, json={"samples": listed})
        if method == "POST" and path.startswith("/samples/"):
            return self.run_sample(path.removeprefix("/samples/"), request)
        raise AssertionError(f"unexpected {method} {url}")

    def report(self, report_id):
        item = self.by_id(report_id)
        if item is None or int(item["expiresAt"]["N"]) <= self.clock():
            return httpx.Response(404, json={"error": "not_found"})
        item = {name: plain(value) for name, value in self.shown(item).items()}
        body = {
            name: item[name] for name in ("reportId", "status", "capturedAt", "mode")
        } | {"published": item.get("published", False)}
        if item["status"] in ("refused", "failed"):
            body["refusalReason"] = item["refusalReason"]
        if item["status"] == "done":
            body["noFloodSeen"] = item["noFloodSeen"]
            if "level" in item:
                for name in (
                    "level",
                    "landmark",
                    "passability",
                    "basis",
                    "levelIsFloor",
                ):
                    body[name] = item[name]
                for link, key in (
                    ("photoUrl", "photoKey"),
                    ("overlayUrl", "overlayKey"),
                    ("layersUrl", "layersKey"),
                ):
                    if key in item:
                        body[link] = LINKS + item[key]
        if item["mode"] == "demo":
            body |= {k: item[k] for k in ("credit", "place", "event") if k in item}
        return httpx.Response(200, json=body)

    def pins(self):
        pins = []
        for typed_item in self.items.values():
            item = {name: plain(value) for name, value in typed_item.items()}
            visible = item.get("visibleUntil", 0) > self.clock()
            if item["mode"] in ("live", "demo") and item.get("published") and visible:
                pins.append(
                    {
                        "id": item["reportId"],
                        "lat": round(item["lat"], 4),
                        "lng": round(item["lng"], 4),
                        "mode": item["mode"],
                    }
                )
        return pins

    def flag(self, report_id, request):
        assert UUID4.fullmatch(request.headers["x-lusot-device"])
        item = self.by_id(report_id)
        live = item is not None and item["mode"] == {"S": "live"}
        return httpx.Response(200 if live else 404, json={"flags": 1} if live else {})

    def manifest(self):
        stored = self.objects.get("samples/manifest.json")
        return json.loads(stored) if stored else {"version": 1, "samples": []}

    def run_sample(self, sample_id, request):
        assert UUID4.fullmatch(request.headers["x-lusot-device"])
        if not any(e["sampleId"] == sample_id for e in self.manifest()["samples"]):
            return httpx.Response(404, json={"error": "not_found"})
        report_id = "r_" + uuid.uuid4().hex
        now = int(self.clock())
        self.put(
            pk="SAMPLE",
            sk=f"{iso(now)}#{report_id}",
            reportId=report_id,
            mode="sample",
            status="pending",
            sampleId=sample_id,
            capturedAt=iso(now),
            receivedAt=iso(now),
            expiresAt=now + 7 * 86400,
        )
        self.objects[f"raw/{report_id}.jpg"] = self.objects[f"samples/{sample_id}.jpg"]
        self.deliver(f"raw/{report_id}.jpg")
        return httpx.Response(201, json={"reportId": report_id})


SAMPLE_FIELDS = ("sampleId", "credit", "license", "place", "date", "event")  # C512
UUID4 = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)


def dead_letter(body, *, n, sent_s, redriven=False):
    """A message as SQS's receive gives it, with its SentTimestamp."""
    message = {
        "MessageId": f"message-{n}",
        "ReceiptHandle": f"handle-{n}-secret",
        "Body": body,
        "Attributes": {"SentTimestamp": str(int(sent_s * 1000))},
        "_visible_at": 0.0,
    }
    if redriven:
        message["MessageAttributes"] = {
            "lusot-redriven": {"DataType": "String", "StringValue": "1"}
        }
    return message


def s3_record_body(report_id, event_s):
    """An S3 ObjectCreated notification for a report, with the uploader's address."""
    record = {
        "eventVersion": "2.1",
        "eventSource": "aws:s3",
        "awsRegion": "ap-southeast-1",
        "eventTime": datetime.fromtimestamp(event_s, UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "eventName": "ObjectCreated:Post",
        "requestParameters": {"sourceIPAddress": SENTINEL_IP},
        "s3": {
            "bucket": {"name": OUTPUTS["BucketName"]},
            "object": {"key": f"raw/{report_id}.jpg", "size": 1024},
        },
    }
    return json.dumps({"Records": [record]})


# The tests' data, outside any repo in real use (lusot-data).

# The open-licensed manifest's header, as read on Oct 30 (F15).
OPEN_HEADER = (
    "id,filename,date_taken,place,in_metro_manila,event,event_detail,subject,"
    "reference_objects,depth_estimate,passability_estimate,people_visible,"
    "children_visible,faces_identifiable,plates_readable,demo_use,demo_use_reason,"
    "label_status,notes,source,source_title,source_page,original_url,license,"
    "license_url,author,attribution_required,share_alike,credit_line,original_size,"
    "saved_as,saved_size"
)
# MS2's eval/templates/consented_log.csv (C218); no log exists yet (F15).
CONSENT_HEADER = (
    "item_id,file,kind,taken_pht,place_text,lat,lon,people,source_note,consent_file,"
    "consent_version,notes"
)
OPEN_COLUMNS, CONSENT_COLUMNS = OPEN_HEADER.split(","), CONSENT_HEADER.split(",")
MANILA = ("14.6095", "120.9894")  # inside Metro Manila (MS1's point, geohash wdw515)
BAGUIO = ("16.4023", "120.5960")  # outside it


def photo(n):
    """A bright test photo whose width, 100 + n px, tells which one was sent."""
    return cv2.imencode(".jpg", np.full((60, 100 + n, 3), 180, np.uint8))[1].tobytes()


def open_row(source_id, n=0, **fields):
    """A row of the open-licensed manifest that passes the allow-list."""
    return {
        "id": source_id,
        "filename": f"{source_id}_2023-09-23_quezon-city_rain_bus.jpg",
        "date_taken": "2023-09-23",
        "place": "Commonwealth Avenue, Quezon City",
        "event": "Habagat 2023",
        "demo_use": "ok",
        "license": "CC BY 2.0",
        "share_alike": "no",
        "credit_line": f'"Flood {source_id}" by A. Photographer, CC BY 2.0',
        "source_page": f"https://commons.test.invalid/{source_id}",
        "notes": "",
        "_photo": photo(n),
    } | fields


def consent_row(item_id, n=0, **fields):
    """A row of MS2's consent log that passes the allow-list, at a Manila spot."""
    return {
        "item_id": item_id,
        "file": f"{item_id}.jpg",
        "kind": "photo",
        "taken_pht": "2026-10-20 14:30",
        "place_text": "Espana Boulevard, Sampaloc, Manila",
        "lat": MANILA[0],
        "lon": MANILA[1],
        "people": "0",
        "source_note": f"NOTE-SENTINEL {item_id}: from a donor's message",
        "consent_file": f"{item_id}-ok.png",
        "consent_version": "M9-v4",
        "notes": "",
        "_photo": photo(n),
    } | fields


def write_csv(path, columns, rows):
    """A CSV as Windows tools write it, with a BOM; each row's photo beside it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            name = row.get("filename") or row.get("file")
            if name and "_photo" in row:
                (path.parent / name).write_bytes(row["_photo"])


def data_folder(base, *, open_rows=(), consent_rows=()):
    """LUSOT_DATA_DIR with the open-licensed manifest and the consent log."""
    write_csv(
        base / "set_c" / "open-licensed-ph" / "open_licensed_manifest.csv",
        OPEN_COLUMNS,
        open_rows,
    )
    write_csv(base / "consented" / "consented_log.csv", CONSENT_COLUMNS, consent_rows)
    return base


def formats_py(path, versions):
    """A copy of MS2's eval/data/formats.py with APPROVED_CONSENT's m9 versions."""
    path.write_text(
        "APPROVED_CONSENT = {\n"
        f'    "m9": frozenset({sorted(versions)!r}),\n'
        '    "set_b": frozenset({"SETB-v1"}),\n'
        "}\n",
        encoding="utf-8",
    )
    return path


def commons_folder(base, names, *, credited=None):
    """C87's folder under LUSOT_DATA_DIR: the list, attribution.csv and images (R116).

    Photo n has width 100 + n. Every photo has a credit line except those whose names
    are in `credited`'s complement, when `credited` is given.
    """
    folder = base / "set_c" / "commons-ph-floods"
    (folder / "images").mkdir(parents=True, exist_ok=True)
    lines = [f"C:\\photos\\{name}\tCC BY 2.0" for name in names]
    (folder / "metro_manila_41.txt").write_bytes(
        ("\r\n".join(lines) + "\r\n").encode("utf-8-sig")
    )
    for n, name in enumerate(names):
        (folder / "images" / name).write_bytes(photo(n))
    with (folder / "attribution.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, ["file_name", "credit_line"])
        writer.writeheader()
        for name in names:
            keep = credited is None or name in credited
            credit = f"{name} by A. Photographer" if keep else ""
            writer.writerow({"file_name": name, "credit_line": credit})
    return folder
