"""Tests for upload_checks.py: K1 to K4 and A1 to A4 (MS7 plan Task 3).

Fakes only: FakeStack answers the API and S3 through httpx's MockTransport, on one
fake clock, and botocore's Stubber answers CloudWatch Logs, S3 and CloudFormation
(stubs.py). Nothing reaches AWS, the API or Meta, and no folder named sealed is made.
The fake forms' credential, token and signature are built at run time. The checks get
the clock's wall time and its monotonic time apart, so one used for the other fails.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_upload_checks.py
"""

import base64
import email.policy
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from email.parser import BytesParser

import harden
import httpx
import pytest
import upload_checks
from smoke_upload import CheckFailed, Stack
from stubs import (
    Clock,
    StubSession,
    http_date,
    log_answer,
    missing_object,
    report_ids,
    stack_answers,
)

API = "https://api.test.invalid"
S3_URL = "https://bucket.s3.test.invalid/"
LAPTOP_START = datetime(
    2026, 11, 3, 2, 15, tzinfo=UTC
).timestamp()  # 10:15 AM in Manila
MAX_BYTES = 10 * 1024 * 1024
DAY = "20261103"
CREDENTIAL = f"stub/{DAY}/ap-southeast-1/s3/aws4_request"  # built here
# The form fields that carry the link itself: never printed.
SIGNED = (
    "key",
    "Policy",
    "X-Amz-Credential",
    "X-Amz-Security-Token",
    "X-Amz-Signature",
)


@pytest.fixture(autouse=True)
def consent(tmp_path, monkeypatch):
    """MS5's consent notice, as a stand-in file, and a private data folder."""
    path = tmp_path / "consent.en.md"
    path.write_bytes(b"The notice.\n")
    monkeypatch.setattr(harden, "CONSENT_PATH", path)
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "data"))


def policy_of(key: str, expires_s: float, **changes) -> dict:
    """A POST policy as MS4's SDK writes it (Task 3's names)."""
    conditions = [
        ["content-length-range", 1, MAX_BYTES],
        {"Content-Type": "image/jpeg"},
        {"bucket": "lusot-uploads"},
        {"X-Amz-Algorithm": "AWS4-HMAC-SHA256"},
        {"X-Amz-Credential": CREDENTIAL},
        {"X-Amz-Date": f"{DAY}T021500Z"},
        {"key": key},
    ]
    stamp = datetime.fromtimestamp(int(expires_s), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"expiration": stamp, "conditions": conditions} | changes


def encode(policy: dict) -> str:
    return base64.b64encode(json.dumps(policy).encode()).decode()


def form_fields(key: str, issued_s: float) -> dict[str, str]:
    """A presigned form's fields; the secret-looking ones are built here, at run time."""
    policy = encode(policy_of(key, issued_s + 300))
    return {
        "Content-Type": "image/jpeg",
        "bucket": "lusot-uploads",
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": CREDENTIAL,
        "X-Amz-Date": f"{DAY}T021500Z",
        "X-Amz-Security-Token": "-".join(("stub", "session", str(int(issued_s)))),
        "key": key,
        "Policy": policy,
        "X-Amz-Signature": hashlib.sha256(policy.encode()).hexdigest(),
    }


def form_parts(
    request: httpx.Request,
) -> tuple[dict[str, str], tuple[bytes, str] | None]:
    """A multipart form post's fields, and its file with its content type."""
    raw = b"Content-Type: " + request.headers["content-type"].encode() + b"\r\n\r\n"
    message = BytesParser(policy=email.policy.HTTP).parsebytes(raw + request.content)
    fields, file = {}, None
    for part in message.iter_parts():
        payload = part.get_payload(decode=True)
        if part.get_filename() is not None:
            file = (payload, part.get_content_type())
        else:
            fields[part.get_param("name", header="content-disposition")] = (
                payload.decode()
            )
    return fields, file


class FakeStack:
    """The API and the bucket as the checks meet them, on the laptop's fake clock.

    The server's clock is the laptop's plus `skew_s`. Report ids come from stubs'
    report_ids, in order, so a test can queue Stubber answers for them. Answers carry
    a Date header and the API's own error bodies.
    """

    def __init__(self, clock: Clock, *, skew_s: float = 0.0, seed: int = 0):
        self.clock, self.skew_s = clock, skew_s
        self.ids = iter(report_ids(40, seed=seed))
        self.made: list[str] = []
        self.issued: list[dict[str, str]] = []  # every form the API handed out
        self.reports: dict[str, dict] = {}
        self.links: dict[
            str, tuple[str, float]
        ] = {}  # Policy: (key, server time issued)
        self.counts: Counter = Counter()
        self.requests: list[httpx.Request] = []
        self.bodies: list[dict] = []  # each POST /uploads body
        # Each S3 post: its fields, its file, the status, and the server's time.
        self.posts: list[tuple[dict, tuple[bytes, str] | None, int, float]] = []
        self.honour_expiry = True
        self.honour_key = True
        self.honour_type = True
        self.after_post: dict | None = None  # a report's state to force after a post

    def server_s(self) -> float:
        return self.clock() + self.skew_s

    def answer(self, status: int, body: object = None, **headers) -> httpx.Response:
        headers = {"Date": http_date(self.server_s()), **headers}
        if body is None:
            return httpx.Response(status, headers=headers)
        return httpx.Response(status, json=body, headers=headers)

    def handle(self, request: httpx.Request) -> httpx.Response:
        request.read()
        self.requests.append(request)
        if str(request.url).startswith(S3_URL):
            return self.s3_post(request)
        path = request.url.path
        if request.method == "OPTIONS" and path == "/uploads":
            return self.answer(204)
        if request.method == "POST" and path == "/uploads":
            return self.upload(request)
        if request.method == "GET" and path.startswith("/reports/"):
            report = self.reports.get(path.removeprefix("/reports/"))
            return (
                self.answer(200, report)
                if report
                else self.answer(404, {"error": "not_found"})
            )
        return self.answer(500)

    def upload(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.bodies.append(body)
        now = self.server_s()
        if now - datetime.fromisoformat(body["capturedAt"]).timestamp() > 900:
            return self.answer(422, {"error": "capture_too_old"})
        hour = (request.headers.get("X-Lusot-Device"), int(now) // 3600)
        if self.counts[hour] >= 10:
            retry = str(3600 - int(now) % 3600)
            return self.answer(429, {"error": "device_limit"}, **{"Retry-After": retry})
        self.counts[hour] += 1
        rid = next(self.ids)
        self.made.append(rid)
        self.reports[rid] = {"status": "pending", "mode": "private", "published": False}
        fields = form_fields(f"raw/{rid}.jpg", now)
        self.issued.append(fields)
        self.links[fields["Policy"]] = (fields["key"], now)
        upload = {"url": S3_URL, "fields": fields}
        return self.answer(201, {"reportId": rid, "upload": upload, "expiresInS": 300})

    def s3_post(self, request: httpx.Request) -> httpx.Response:
        fields, file = form_parts(request)
        key, issued = self.links.get(fields.get("Policy"), (None, 0.0))
        refused = (
            key is None
            or (self.honour_key and fields.get("key") != key)
            or (self.honour_expiry and self.server_s() > issued + 300)
            or (self.honour_type and fields.get("Content-Type") != "image/jpeg")
        )
        status = 403 if refused else 204
        self.posts.append((fields, file, status, self.server_s()))
        if refused:
            text = "<Error><Code>AccessDenied</Code><Message>x</Message></Error>"
            return httpx.Response(
                403, text=text, headers={"Date": http_date(self.server_s())}
            )
        rid = fields["key"].removeprefix("raw/").removesuffix(".jpg")
        if self.after_post is not None:
            self.reports[rid] = self.after_post
        elif file[0].startswith(b"\xff\xd8\xff"):
            self.reports[rid] = {
                "status": "refused",
                "refusalReason": "too_dark",
                "mode": "private",
                "published": False,
            }
        else:
            self.reports[rid] = {
                "status": "failed",
                "refusalReason": "bad_file",
                "mode": "private",
                "published": False,
            }
        return httpx.Response(204, headers={"Date": http_date(self.server_s())})

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handle))


def line(rid: str, outcome: str, **fields) -> str:
    return json.dumps({"reportId": rid, "outcome": outcome, **fields})


def setup(*, skew_s: float = 0.0, start: float = LAPTOP_START, seed: int = 0):
    clock = Clock(start)
    fake = FakeStack(clock, skew_s=skew_s, seed=seed)
    session = StubSession("logs", "s3", "cloudformation")
    stack = Stack(
        session=session,
        api_url=API,
        bucket="lusot-uploads",
        queue="lusot-upload-queue",
        log_group="lusot-analysis-log-group",
        since_ms=int((start - 300) * 1000),
    )
    record = harden.RunRecord(
        harden.data_dir() / "ms7" / "2026-11-03", "upload_checks", "K"
    )
    return clock, fake, session, stack, record


def issued(fake, stack, record, clock, *, offset_s=0.0):
    return upload_checks.issue(
        fake.client(),
        stack.api_url,
        record,
        device_id=harden.new_device_id(),
        offset_s=offset_s,
        wall=clock,
    )


def found_object(session) -> None:
    """Queue one head_object that finds the object."""
    session.stubs["s3"].add_response("head_object", {"ContentLength": 10})


def test_policy_is_decoded_and_checked():
    rid = report_ids(1)[0]
    key, issued_s = f"raw/{rid}.jpg", 1_793_700_000.0
    fields = {"Policy": encode(policy_of(key, issued_s + 300))}
    policy = upload_checks.decode_policy(fields)
    assert upload_checks.policy_problems(policy, issued_s=issued_s, report_id=rid) == []
    late = policy_of(key, issued_s + 302)
    assert (
        len(upload_checks.policy_problems(late, issued_s=issued_s, report_id=rid)) == 1
    )
    loose = policy_of(key, issued_s + 300)
    loose["conditions"].append(["starts-with", "$key", "raw/"])
    assert (
        len(upload_checks.policy_problems(loose, issued_s=issued_s, report_id=rid)) == 1
    )
    big = policy_of(key, issued_s + 300)
    big["conditions"][0] = ["content-length-range", 1, 20 * 1024 * 1024]
    assert (
        len(upload_checks.policy_problems(big, issued_s=issued_s, report_id=rid)) == 1
    )
    other = policy_of("raw/" + report_ids(2)[1] + ".jpg", issued_s + 300)
    problems = upload_checks.policy_problems(other, issued_s=issued_s, report_id=rid)
    assert len(problems) == 1 and "r_" not in problems[0]
    png = policy_of(key, issued_s + 300)
    png["conditions"][1] = {"Content-Type": "image/png"}
    assert (
        len(upload_checks.policy_problems(png, issued_s=issued_s, report_id=rid)) == 1
    )
    # A zone-less expiration would read as the laptop's local time: a problem.
    zoneless = policy_of(key, issued_s + 300)
    zoneless["expiration"] = zoneless["expiration"].removesuffix("Z")
    assert (
        len(upload_checks.policy_problems(zoneless, issued_s=issued_s, report_id=rid))
        == 1
    )
    with pytest.raises(CheckFailed):
        upload_checks.decode_policy({"Policy": "not base64!"})
    with pytest.raises(CheckFailed):
        upload_checks.decode_policy({})


def test_server_epoch_reads_the_date_header():
    response = httpx.Response(201, headers={"Date": "Tue, 03 Nov 2026 02:15:00 GMT"})
    expected = datetime(2026, 11, 3, 2, 15, tzinfo=UTC).timestamp()
    assert upload_checks.server_epoch(response) == expected
    zoneless = httpx.Response(201, headers={"Date": "Tue, 03 Nov 2026 02:15:00 -0000"})
    assert upload_checks.server_epoch(zoneless) == expected  # read as GMT
    with pytest.raises(CheckFailed):
        upload_checks.server_epoch(httpx.Response(201))


def test_hold_uses_server_time_under_skew():
    issue_server = LAPTOP_START
    clock = Clock(issue_server + 101)  # the laptop 101 s fast
    deadline = issue_server + 330
    upload_checks.hold_until(deadline, offset_s=-101, clock=clock, sleep=clock.sleep)
    assert clock() - 101 >= deadline  # the server's time has reached it
    assert clock() - 101 < deadline + 1  # and not much more
    late = Clock(issue_server + 101)
    upload_checks.hold_until(deadline, offset_s=0, clock=late, sleep=late.sleep)
    assert late() - 101 < deadline  # by the laptop's clock it would end 101 s early


def test_not_a_jpeg_never_starts_like_one(monkeypatch):
    for seed in range(100):
        data = upload_checks.not_a_jpeg(seed=seed)
        assert len(data) == 4096
        assert data[:3] != b"\xff\xd8\xff"

    class LikeAJpeg:  # random bytes that happen to start as a JPEG does
        def __init__(self, seed):
            pass

        def randbytes(self, n):
            return (b"\xff\xd8\xff" + bytes(n))[:n]

    monkeypatch.setattr(upload_checks.random, "Random", LikeAJpeg)
    assert upload_checks.not_a_jpeg(8)[:3] == b"\x00\xd8\xff"


def test_k1_control_reads_its_result():
    clock, fake, session, stack, record = setup()
    link = issued(fake, stack, record, clock)
    log_answer(session, [line(link.report_id, "refused/too_dark", meta_calls=0)])
    result = upload_checks.k1_control(
        fake.client(), stack, link, clock=clock.mono, sleep=clock.sleep
    )
    assert result.startswith("K1 pass")
    session.done()
    # Any other outcome fails it.
    clock, fake, session, stack, record = setup()
    link = issued(fake, stack, record, clock)
    fake.after_post = {
        "status": "done",
        "noFloodSeen": True,
        "mode": "private",
        "published": False,
    }
    log_answer(session, [line(link.report_id, "done/no_flood_seen", meta_calls=8)])
    result = upload_checks.k1_control(
        fake.client(), stack, link, clock=clock.mono, sleep=clock.sleep
    )
    assert result.startswith("K1 FAIL")
    # And so does a too_dark line without meta_calls 0.
    clock, fake, session, stack, record = setup()
    link = issued(fake, stack, record, clock)
    log_answer(session, [line(link.report_id, "refused/too_dark")])
    result = upload_checks.k1_control(
        fake.client(), stack, link, clock=clock.mono, sleep=clock.sleep
    )
    assert result.startswith("K1 FAIL")


def k3(fake, stack, record, clock):
    link = issued(fake, stack, record, clock, offset_s=fake.skew_s)
    return link, lambda: upload_checks.k3_expired(
        fake.client(),
        stack,
        link,
        offset_s=fake.skew_s,
        wall=clock,
        clock=clock.mono,
        sleep=clock.sleep,
    )


def test_k3_expects_403_and_no_object():
    # Review Focus 3: with the laptop 101 s fast, the post waits for the server's time.
    clock, fake, session, stack, record = setup(skew_s=-101)
    link, run = k3(fake, stack, record, clock)
    missing_object(session)
    for _ in range(7):  # log_lines waits 30 s, every 5 s, for any line
        log_answer(session)
    result = run()
    assert result.startswith("K3 pass"), result
    fields, _, status, posted_at = fake.posts[-1]
    assert status == 403 and fields == link.form["fields"]
    assert link.issued_s + 330 <= posted_at < link.issued_s + 331
    session.done()
    # A 204 fails it.
    clock, fake, session, stack, record = setup()
    fake.honour_expiry = False
    link, run = k3(fake, stack, record, clock)
    assert run().startswith("K3 FAIL")
    # So does a raw object after the 403.
    clock, fake, session, stack, record = setup()
    link, run = k3(fake, stack, record, clock)
    found_object(session)
    for _ in range(7):
        log_answer(session)
    assert run().startswith("K3 FAIL")


def test_k3_report_stays_pending():
    clock, fake, session, stack, record = setup()
    link, run = k3(fake, stack, record, clock)
    missing_object(session)
    log_answer(session, [line(link.report_id, "failed/photo_missing")])
    assert run().startswith("K3 FAIL")  # an analysis ran
    clock, fake, session, stack, record = setup()
    link, run = k3(fake, stack, record, clock)
    fake.reports[link.report_id] = {
        "status": "failed",
        "refusalReason": "photo_missing",
    }
    missing_object(session)
    for _ in range(7):
        log_answer(session)
    assert run().startswith("K3 FAIL")  # no longer pending


def test_k4_changes_only_the_key():
    clock, fake, session, stack, record = setup()
    second, third = (
        issued(fake, stack, record, clock),
        issued(fake, stack, record, clock),
    )
    missing_object(session)
    missing_object(session)
    result = upload_checks.k4_other_key(fake.client(), stack, second, third)
    assert result.startswith("K4 pass"), result
    fields, _, status, _ = fake.posts[-1]
    assert status == 403
    assert {k: v for k, v in fields.items() if k != "key"} == {
        k: v for k, v in second.form["fields"].items() if k != "key"
    }
    assert fields["key"] == third.form["fields"]["key"] != second.form["fields"]["key"]
    session.done()
    clock, fake, session, stack, record = setup()
    fake.honour_key = False
    second, third = (
        issued(fake, stack, record, clock),
        issued(fake, stack, record, clock),
    )
    assert upload_checks.k4_other_key(fake.client(), stack, second, third).startswith(
        "K4 FAIL"
    )
    # An object at either key fails it too.
    clock, fake, session, stack, record = setup()
    second, third = (
        issued(fake, stack, record, clock),
        issued(fake, stack, record, clock),
    )
    missing_object(session)
    found_object(session)
    assert upload_checks.k4_other_key(fake.client(), stack, second, third).startswith(
        "K4 FAIL"
    )


def a1(fake, stack, record, clock):
    return upload_checks.a1_device_limit(
        fake.client(),
        stack,
        record,
        offset_s=fake.skew_s,
        wall=clock,
        sleep=clock.sleep,
    )


def test_a1_counts_to_eleven():
    clock, fake, _session, stack, record = setup()
    assert a1(fake, stack, record, clock).startswith("A1 pass")
    assert len(fake.made) == 10 and not fake.posts  # no S3 post
    assert len({r.headers["X-Lusot-Device"] for r in fake.requests}) == 1
    # An 11th 201 fails it.
    clock, fake, _session, stack, record = setup()
    fake.counts = type("NoLimit", (Counter,), {"__getitem__": lambda self, k: 0})()
    assert a1(fake, stack, record, clock).startswith("A1 FAIL")

    def refusing(error, retry_after):
        def handle(request):
            request.read()
            date = {"Date": http_date(LAPTOP_START)}
            if request.method == "POST" and handle.n < 10:
                handle.n += 1
                rid = report_ids(11)[handle.n]
                form = {
                    "url": S3_URL,
                    "fields": form_fields(f"raw/{rid}.jpg", LAPTOP_START),
                }
                body = {"reportId": rid, "upload": form, "expiresInS": 300}
                return httpx.Response(201, json=body, headers=date)
            headers = date | (
                {} if retry_after is None else {"Retry-After": retry_after}
            )
            return httpx.Response(429, json={"error": error}, headers=headers)

        handle.n = 0
        return httpx.Client(transport=httpx.MockTransport(handle))

    for error, retry_after in (
        ("global_cap", "600"),
        ("device_limit", None),
        ("device_limit", "3601"),
    ):
        clock, fake, _session, stack, record = setup()
        result = upload_checks.a1_device_limit(
            refusing(error, retry_after),
            stack,
            record,
            offset_s=0,
            wall=clock,
            sleep=clock.sleep,
        )
        assert result.startswith("A1 FAIL"), (error, retry_after)


def test_a1_waits_for_room_in_the_hour():
    next_hour = datetime(2026, 11, 3, 3, 0, tzinfo=UTC).timestamp()
    near_end = next_hour - 90  # 90 s of the hour left
    clock, fake, _session, stack, record = setup(start=near_end)
    assert a1(fake, stack, record, clock).startswith("A1 pass")
    first = datetime.fromisoformat(fake.bodies[0]["capturedAt"]).timestamp()
    assert first >= next_hour
    # Review Focus 3: the laptop, 101 s fast, reads 03:00:30 while the server's hour
    # has 71 s left, so A1 must wait by the server's clock.
    clock, fake, _session, stack, record = setup(skew_s=-101, start=next_hour + 30)
    assert a1(fake, stack, record, clock).startswith("A1 pass")
    assert clock.slept, "A1 didn't wait for the server's next hour"
    sent = [datetime.fromisoformat(b["capturedAt"]).timestamp() for b in fake.bodies]
    assert min(sent) >= next_hour and len({int(s) // 3600 for s in sent}) == 1
    # With room left, it starts at once.
    clock, fake, _session, stack, record = setup()
    assert a1(fake, stack, record, clock).startswith("A1 pass")
    assert clock.slept == []


def test_a2_uses_server_time_under_skew():
    clock, fake, _session, stack, record = setup(skew_s=-101)  # the laptop 101 s fast
    result = upload_checks.a2_old_capture(
        fake.client(), stack, record, offset_s=-101, wall=clock
    )
    assert result.startswith("A2 pass"), result
    sent = datetime.fromisoformat(fake.bodies[-1]["capturedAt"]).timestamp()
    assert sent == pytest.approx(fake.server_s() - 16 * 60, abs=0.01)
    # By the laptop's clock it would be under 15 minutes old to the server, and pass.
    clock, fake, _session, stack, record = setup(skew_s=-101)
    result = upload_checks.a2_old_capture(
        fake.client(), stack, record, offset_s=0, wall=clock
    )
    assert result.startswith("A2 FAIL")


def test_a3_and_a4():
    clock, fake, session, stack, record = setup()
    rid = report_ids(1)[0]
    log_answer(session, [line(rid, "failed/bad_file")])  # no meta_calls: C83's check
    result = upload_checks.a3_random_bytes(
        fake.client(),
        stack,
        record,
        offset_s=0,
        wall=clock,
        clock=clock.mono,
        sleep=clock.sleep,
    )
    assert result.startswith("A3 pass"), result
    _, (data, content_type), status, _ = fake.posts[-1]
    assert (
        status == 204 and content_type == "image/jpeg" and data[:3] != b"\xff\xd8\xff"
    )
    session.done()
    # A bad_file line that shows Meta calls fails it.
    clock, fake, session, stack, record = setup()
    log_answer(session, [line(rid, "failed/bad_file", meta_calls=2)])
    result = upload_checks.a3_random_bytes(
        fake.client(),
        stack,
        record,
        offset_s=0,
        wall=clock,
        clock=clock.mono,
        sleep=clock.sleep,
    )
    assert result.startswith("A3 FAIL")
    # A4: a PNG form post gets 403, and nothing is stored.
    clock, fake, session, stack, record = setup()
    missing_object(session)
    result = upload_checks.a4_png(fake.client(), stack, record, offset_s=0, wall=clock)
    assert result.startswith("A4 pass"), result
    fields, (_, content_type), status, _ = fake.posts[-1]
    assert (fields["Content-Type"], content_type, status) == (
        "image/png",
        "image/png",
        403,
    )
    clock, fake, session, stack, record = setup()
    fake.honour_type = False
    result = upload_checks.a4_png(fake.client(), stack, record, offset_s=0, wall=clock)
    assert result.startswith("A4 FAIL")


def test_without_yes_nothing_is_sent(capsys):
    for run in ("link", "abuse"):
        # 2, so a forgotten --yes never reads as a pass; no session or client is used.
        assert upload_checks.main([run], session=object(), http=object()) == 2
    assert "--yes" in capsys.readouterr().out


def test_a_sealed_data_folder_is_refused(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "sealed" / "data"))
    assert upload_checks.main(["link", "--yes"], session=object(), http=object()) == 2
    assert capsys.readouterr().out.startswith("refused:")
    assert not (tmp_path / "sealed").exists()


def outputs():
    return {
        "ApiUrl": API + "/",
        "BucketName": "lusot-uploads",
        "QueueName": "lusot-upload-queue",
    }


def run_main(argv, fake, session, clock):
    return upload_checks.main(
        argv,
        session=session,
        http=fake.client(),
        wall=clock,
        clock=clock.mono,
        sleep=clock.sleep,
    )


def test_checks_print_no_report_id(capsys):
    """Review Focus 2: both subcommands, run on fakes, print no id and no form field."""
    printed, made, issued_forms = "", [], []
    # link: the precondition, K1, K4's two, then K3 (Task 3's defaults).
    clock = Clock(LAPTOP_START)
    fake = FakeStack(clock)
    session = StubSession("logs", "s3", "cloudformation")
    stack_answers(session, outputs())
    ids = report_ids(5)
    log_answer(session, [line(ids[1], "refused/too_dark", meta_calls=0)])
    for _ in range(3):  # K4's two keys, then K3's
        missing_object(session)
    for _ in range(7):
        log_answer(session)
    code = run_main(["link", "--yes"], fake, session, clock)
    printed += capsys.readouterr().out
    assert code == 0, printed
    session.done()
    assert "K2 pass: 4 links" in printed  # every link the run was issued
    made += fake.made
    issued_forms += fake.issued
    # abuse: the precondition, A1's ten, A3, A4 (A2's upload is refused).
    clock = Clock(LAPTOP_START + 3600)
    fake = FakeStack(clock, seed=1)
    session = StubSession("logs", "s3", "cloudformation")
    stack_answers(session, outputs())
    ids = report_ids(13, seed=1)
    log_answer(session, [line(ids[11], "failed/bad_file")])
    missing_object(session)
    code = run_main(["abuse", "--yes"], fake, session, clock)
    printed += capsys.readouterr().out
    assert code == 0, printed
    session.done()
    made += fake.made
    issued_forms += fake.issued
    assert len(made) == len(issued_forms) == 5 + 13
    secrets = [
        *made,
        *(form[name] for form in issued_forms for name in SIGNED),
        S3_URL,
        API,
    ]
    for secret in secrets:
        assert secret not in printed
    # Not even an id the mask had to catch: the lines are built without one.
    assert "r_" not in printed and "<report>" not in printed
    for check in ("K1", "K2", "K3", "K4", "A1", "A2", "A3", "A4"):
        assert f"{check} pass" in printed
    # Every report made, the preconditions' included, is in a run's private record.
    ordinals, _ = harden.load_records([harden.data_dir() / "ms7" / "2026-11-03"])
    assert set(made) == set(ordinals.values())
    assert all(name[0] in "KA" for name in ordinals)


def test_the_run_stops_before_any_photo_unless_private(capsys):
    clock = Clock(LAPTOP_START)
    fake = FakeStack(clock)
    original = fake.upload

    def live_upload(request):
        response = original(request)
        for report in fake.reports.values():
            report["mode"] = "live"
        return response

    fake.upload = live_upload
    session = StubSession("logs", "s3", "cloudformation")
    stack_answers(session, outputs())
    assert run_main(["link", "--yes"], fake, session, clock) == 1
    assert fake.posts == []  # no photo went
    assert "not private" in capsys.readouterr().out
