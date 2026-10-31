"""Tests for harden.py, MS7's shared helpers for its cloud checks (MS7 plan Task 1).

Fakes only: botocore's Stubber answers every AWS call and httpx's MockTransport every
HTTP call, so nothing reaches AWS, the API or Meta. Every 12-digit run, report id,
email address and ARN is built at run time, so no file holds one for the account-ID
scan or gitleaks, and no folder named sealed is ever made.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_harden.py
"""

import json
import random
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import boto3
import harden
import httpx
import metro_manila
import ops_common
import pytest
import smoke_upload
from boto3.dynamodb.types import TypeSerializer
from botocore.stub import Stubber
from smoke_upload import CheckFailed

SCRIPTS = Path(__file__).resolve().parent
API_SRC = SCRIPTS.parent / "api"
TWELVE = "1234567890" + "12"
ACCOUNT = "4" + "0" * 5 + "731" + "986"  # 12 digits, built here
EMAIL = "someone" + chr(64) + "example.test"  # an address, built here
TOPIC = f"arn:aws:sns:{ops_common.REGION}:{ACCOUNT}:lusot-AlarmTopic-T1"
NOW = datetime(2026, 11, 3, 10, 15, 0)  # a run's start, on the laptop's clock
NOW_S = 1_793_700_000


def report_id(fill: str = "ab") -> str:
    """C32's form, built at run time: r_ and 32 hex, with a 12-digit run inside."""
    return "r_" + fill + TWELVE + "cd" * 9


@pytest.fixture
def consent(tmp_path, monkeypatch):
    """MS5's consent notice, as a stand-in file: main doesn't hold it until MS5 merges."""
    path = tmp_path / "consent.en.md"
    path.write_bytes(b"Ang paunawa.\nThe notice.\n")
    monkeypatch.setattr(harden, "CONSENT_PATH", path)
    return path


class FakeSession:
    """A boto3 session whose clients are stubbed. It records the region each asks for."""

    def __init__(self, *services):
        real = boto3.Session(
            aws_access_key_id="stub",
            aws_secret_access_key="stub",
            region_name="ap-southeast-1",
        )
        self.clients = {
            name: real.client(name, region_name="us-east-1") for name in services
        }
        self.stubs = {name: Stubber(client) for name, client in self.clients.items()}
        self.regions = {}

    def client(self, service, region_name=None):
        self.regions[service] = region_name
        return self.clients[service]

    def __enter__(self):
        for stub in self.stubs.values():
            stub.activate()
        return self

    def __exit__(self, *exc):
        for stub in self.stubs.values():
            stub.deactivate()

    def check(self):
        for stub in self.stubs.values():
            stub.assert_no_pending_responses()


def test_scrub_masks_report_ids_and_account_ids(capsys):
    rid = report_id()
    line = f"report {rid} in raw/{rid}.jpg, account {TWELVE}, file ids-{TWELVE}.json"
    expected = "report <report> in raw/<report>.jpg, account <account>, file ids-<account>.json"
    assert harden.scrub(line) == expected
    # guards.mask is the committed rule for longer runs: their first 12 digits are
    # masked (test_guards.py), the cautious side (plan Notes, Task 1's names, item 2).
    assert harden.scrub(f"{TWELVE}3") == "<account>3"
    assert (
        harden.scrub("an 11-digit run " + TWELVE[:11])
        == "an 11-digit run " + TWELVE[:11]
    )
    harden.say(line)
    assert capsys.readouterr().out == expected + "\n"
    # smoke_upload keeps MS4's one mask (test_smoke_upload.py): a standalone id passes.
    smoke_upload.say(f"{rid}: account {TWELVE}")
    assert capsys.readouterr().out == f"{rid}: account <account>\n"


def test_smoke_upload_never_imports_harden():
    source = (SCRIPTS / "smoke_upload.py").read_text(encoding="utf-8")
    assert re.search(r"^\s*(import harden|from harden)\b", source, re.MULTILINE) is None


def test_captured_at_uses_server_time(consent):
    t = float(NOW_S)
    now = harden.server_now(-101, clock=lambda: t)  # the laptop 101 s fast (Oct 28)
    body = harden.upload_body(harden.OUTSIDE_POINT, captured_at=now)
    expected = datetime.fromtimestamp(t - 101, UTC)
    assert datetime.fromisoformat(body["capturedAt"]) == expected
    with pytest.raises(ValueError):
        harden.upload_body(harden.OUTSIDE_POINT, captured_at=datetime(2026, 11, 3))


def test_server_offset_reads_the_date_header():
    asked = []

    def handle(request):
        asked.append(request)
        return httpx.Response(204, headers={"Date": "Tue, 03 Nov 2026 02:15:00 GMT"})

    http = httpx.Client(transport=httpx.MockTransport(handle))
    server = datetime(2026, 11, 3, 2, 15, tzinfo=UTC).timestamp()
    offset = harden.server_offset(
        http, "https://api.test.invalid", clock=lambda: server + 101
    )
    assert offset == -101
    [preflight] = asked
    assert preflight.method == "OPTIONS"
    assert preflight.url.path == "/uploads"
    assert preflight.headers["access-control-request-method"] == "POST"

    def no_date(request):
        return httpx.Response(204)

    http = httpx.Client(transport=httpx.MockTransport(no_date))
    with pytest.raises(CheckFailed, match="Date"):
        harden.server_offset(http, "https://api.test.invalid")


def test_run_records_never_overwrite(tmp_path):
    first, second = report_id("01"), report_id("02")
    one = harden.RunRecord(tmp_path, "load_test", "L", clock=lambda: NOW)
    assert one.name(first) == "L#1"
    path_one = one.save()
    # A second run in the same second numbers on from the folder's saved records.
    two = harden.RunRecord(tmp_path, "load_test", "L", clock=lambda: NOW)
    assert two.name(second) == "L#2"
    path_two = two.save()
    assert path_one.name == "ids-load_test-101500.json"
    assert path_two.name == "ids-load_test-101500-2.json"
    assert one.save() == path_one  # a record rewrites only its own file
    assert {p.name for p in tmp_path.iterdir()} == {path_one.name, path_two.name}
    expected = {"L#1": first, "L#2": second}
    assert harden.load_records([path_one, path_two])[0] == expected
    assert harden.load_records([tmp_path])[0] == expected
    assert (
        harden.load_records([tmp_path, path_one])[0] == expected
    )  # read twice is fine


def test_load_records_refuses_an_ordinal_named_twice(tmp_path):
    for n, rid in enumerate((report_id("01"), report_id("02"))):
        record = {"ordinals": {"S#1": rid}, "devices": []}
        (tmp_path / f"ids-switch_test-10150{n}.json").write_text(json.dumps(record))
    with pytest.raises(CheckFailed) as caught:
        harden.load_records([tmp_path])
    assert "S#1" in str(caught.value)
    assert "r_" not in str(caught.value)
    (tmp_path / "ids-x-000000.json").write_text("{not json")
    with pytest.raises(CheckFailed):
        harden.load_records([tmp_path / "ids-x-000000.json"])


def test_poll_interval_follows_c601():
    assert harden.poll_interval(0) == 2.0
    assert harden.poll_interval(59.9) == 2.0
    assert harden.poll_interval(60) == 5.0
    assert harden.poll_interval(239.9) == 5.0
    assert harden.poll_interval(240) == 15.0
    assert harden.poll_interval(585) == 15.0
    # MS5's last wait is cut to the deadline, so one last poll comes at 600 s
    # (poll.ts; plan Notes, Task 1's names, item 3).
    assert harden.poll_interval(590) == 10.0
    assert harden.poll_interval(599.9) == pytest.approx(0.1)
    assert harden.poll_interval(600) is None
    assert harden.poll_interval(700) is None


def test_wait_after_429_prefers_retry_after():
    rng = random.Random(1)
    assert harden.wait_after_429("7", 5.0, rng) == 7.0
    assert harden.wait_after_429(" 7 ", 5.0, rng) == 7.0
    # Never less than the interval (MS5's poll.ts).
    assert harden.wait_after_429("7", 15.0, rng) == 15.0
    wait = harden.wait_after_429(None, 5.0, random.Random(1))
    assert 5.0 <= wait <= 6.0
    # Whole seconds only, as MS5 reads it: a date or a fraction is the interval plus jitter.
    for unread in ("Tue, 03 Nov 2026 02:15:00 GMT", "1.5", "", "-3"):
        assert 5.0 <= harden.wait_after_429(unread, 5.0, random.Random(1)) <= 6.0


def test_device_limit_429_not_retried():
    assert harden.classify_429({"error": "device_limit"}) == "device_limit"
    assert harden.classify_429({"error": "global_cap"}) == "device_limit"
    assert harden.classify_429({"message": "Too Many Requests"}) == "throttle"
    assert harden.classify_429(None) == "throttle"
    assert harden.classify_429({"error": ["device_limit"]}) == "throttle"
    # Any code is a limit, as MS5's retry.ts reads it: Ask Lusot's and unknown ones too.
    assert harden.classify_429({"error": "question_limit"}) == "device_limit"
    assert harden.classify_429({"error": "a_new_limit"}) == "device_limit"
    assert harden.should_retry("device_limit", 0) is False
    assert harden.should_retry("throttle", 0) is True
    assert harden.should_retry("throttle", 1) is False
    assert harden.should_retry("network", 0) is True
    assert harden.should_retry("503", 0) is True
    assert harden.should_retry("other", 0) is False
    with pytest.raises(ValueError):
        harden.should_retry("timeout", 0)


def test_ordinals_never_repeat_and_save_privately(tmp_path):
    first, second = report_id("0a"), report_id("0b")
    devices = [harden.new_device_id(), harden.new_device_id()]
    record = harden.RunRecord(
        tmp_path / "ms7" / "2026-11-03", "load_test", "L", clock=lambda: NOW
    )
    assert record.name(first) == "L#1"
    assert record.name(second) == "L#2"
    assert record.name(first) == "L#1"
    assert [record.device(d) for d in devices] == devices
    record.device(devices[0])
    saved = json.loads(record.save().read_text(encoding="utf-8"))
    assert saved == {"ordinals": {"L#1": first, "L#2": second}, "devices": devices}
    assert harden.load_records([tmp_path / "ms7" / "2026-11-03"]) == (
        saved["ordinals"],
        devices,
    )
    # A record never goes under a folder named sealed, which is never made.
    with pytest.raises(CheckFailed):
        harden.RunRecord(tmp_path / "sealed" / "day", "load_test", "L")
    with pytest.raises(CheckFailed):
        harden.load_records([tmp_path / "sealed"])
    assert not (tmp_path / "sealed").exists()


def test_data_dir_refuses_sealed(tmp_path, monkeypatch):
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "sealed" / "x"))
    with pytest.raises(CheckFailed):
        harden.data_dir()
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "data"))
    assert harden.data_dir() == tmp_path / "data"
    monkeypatch.delenv("LUSOT_DATA_DIR")
    assert harden.data_dir() == Path(r"C:\Systems\Lusot\lusot-data")
    assert not (tmp_path / "sealed").exists()


def budget(amount, *, include_credit=True, actual="0.02", forecast="0.05"):
    spend = {"ActualSpend": {"Amount": actual, "Unit": "USD"}}
    if forecast is not None:
        spend["ForecastedSpend"] = {"Amount": forecast, "Unit": "USD"}
    return {
        "BudgetName": f"budget-{amount}",
        "BudgetLimit": {"Amount": amount, "Unit": "USD"},
        "CostTypes": {"IncludeCredit": include_credit},
        "TimeUnit": "MONTHLY",
        "BudgetType": "COST",
        "CalculatedSpend": spend,
    }


def stub_budget(session, budgets):
    session.stubs["sts"].add_response(
        "get_caller_identity",
        {
            "Account": ACCOUNT,
            "Arn": f"arn:aws:iam::{ACCOUNT}:user/rene-dev",
            "UserId": "AIDSTUB",
        },
        {},
    )
    session.stubs["budgets"].add_response(
        "describe_budgets", {"Budgets": budgets}, {"AccountId": ACCOUNT}
    )


def test_budget_status_prints_no_account(capsys):
    session = FakeSession("sts", "budgets", "freetier")
    stub_budget(session, [budget("150.0", include_credit=False), budget("5.0")])
    session.stubs["freetier"].add_response(
        "get_account_plan_state",
        {
            "accountId": ACCOUNT,
            "accountPlanType": "FREE",
            "accountPlanStatus": "ACTIVE",
            "accountPlanRemainingCredits": {"amount": 199.4, "unit": "USD"},
            "accountPlanExpirationDate": datetime(2027, 4, 27, tzinfo=UTC),
        },
        {},
    )
    with session:
        status = harden.budget_status(session)
        session.check()
    assert status == {
        "limit": 5.0,
        "actual": 0.02,
        "forecast": 0.05,
        "include_credit": True,
        "plan_type": "FREE",
        "plan_status": "ACTIVE",
        "credits_left": 199.4,
        "plan_end": "2027-04-27",
    }
    assert session.regions["freetier"] == "us-east-1"  # it answers only there
    lines = harden.budget_meaning(status)
    for line in lines:
        harden.say(line)
    # The raw lines and the result, before say's mask could hide a leak.
    unmasked = "\n".join(lines) + repr(status) + capsys.readouterr().out
    assert ACCOUNT not in unmasked
    assert re.search(r"[0-9]{12}", unmasked) is None


def test_budget_status_needs_one_five_dollar_budget():
    session = FakeSession("sts", "budgets", "freetier")
    stub_budget(session, [budget("150.0")])
    with session, pytest.raises(CheckFailed) as caught:
        harden.budget_status(session)
    assert ACCOUNT not in str(caught.value)


def plan_status(**fields):
    return {
        "limit": 5.0,
        "actual": 0.02,
        "forecast": 0.05,
        "include_credit": True,
        "plan_type": "FREE",
        "plan_status": "ACTIVE",
        "credits_left": 199.40,
        "plan_end": "2027-04-27",
    } | fields


def test_budget_meaning_reads_credits_right():
    budget_line, plan_line = harden.budget_meaning(plan_status(), last_credits=199.60)
    assert "$5.00" in budget_line and "$0.02" in budget_line
    assert "nets" in budget_line and "credits" in budget_line
    assert "burn" in plan_line and "$199.40" in plan_line
    assert "FLAG" not in budget_line + plan_line
    gross, _ = harden.budget_meaning(plan_status(include_credit=False))
    assert "nets" not in gross and "leaves credits out" in gross
    for flagged in (
        harden.budget_meaning(plan_status(plan_status="EXPIRED")),
        harden.budget_meaning(plan_status(plan_type="PAID")),
        harden.budget_meaning(plan_status(), last_credits=202.40),
        harden.budget_meaning(
            plan_status(credits_left=196.40), last_credits=199.40, days_since=1
        ),
        harden.budget_meaning(plan_status(), last_credits=200.30),  # $0.90 in a day
    ):
        assert " ".join(flagged).count("FLAG") == 1
    # A slow fall over several days is still cents a day.
    _, slow = harden.budget_meaning(plan_status(), last_credits=200.20, days_since=4)
    assert "FLAG" not in slow
    _, unforecast = harden.budget_meaning(plan_status(forecast=None, plan_end=None))
    assert "FLAG" not in unforecast


RESOURCES = {
    "AlarmTopic": TOPIC,
    "AnalysisFunction": "stub-analysis-function",
    "ApiFunction": "stub-api-function",
    "DeadLetterAlarm": "stub-dead-letter-alarm",
    "AnalysisInvocationsAlarm": "stub-analysis-alarm",
    "ApiInvocationsAlarm": "stub-api-alarm",
}


def alarm(logical, **changes):
    name = RESOURCES[logical]
    found = {
        "AlarmName": name,
        "ActionsEnabled": True,
        "AlarmActions": [TOPIC],
        "OKActions": [],
        "Namespace": "AWS/Lambda",
        "MetricName": "Invocations",
        "Statistic": "Sum",
        "Period": 3600,
        "Dimensions": [],
    }
    if logical == "DeadLetterAlarm":
        found |= {
            "Namespace": "AWS/SQS",
            "MetricName": "ApproximateNumberOfMessagesVisible",
            "Statistic": "Maximum",
            "Period": 300,
            "OKActions": [TOPIC],
        }
    else:
        function = RESOURCES[
            "AnalysisFunction" if logical.startswith("Analysis") else "ApiFunction"
        ]
        found["Dimensions"] = [{"Name": "FunctionName", "Value": function}]
    return found | changes


def subscription(arn):
    return {
        "SubscriptionArn": arn,
        "Owner": ACCOUNT,
        "Protocol": "email",
        "Endpoint": EMAIL,
        "TopicArn": TOPIC,
    }


def stub_alarms(*, missing=None, alarms=None, subscriptions=None):
    """Stubber answers for alarm_problems, in its call order: a resource left out of
    the stack, the alarms CloudWatch returns, and the topic's subscriptions."""
    session = FakeSession("cloudformation", "cloudwatch", "sns")
    for logical, physical in RESOURCES.items():
        expected = {"StackName": "lusot", "LogicalResourceId": logical}
        if logical == missing:
            session.stubs["cloudformation"].add_client_error(
                "describe_stack_resource",
                "ValidationError",
                http_status_code=400,
                expected_params=expected,
            )
            continue
        detail = {
            "LogicalResourceId": logical,
            "PhysicalResourceId": physical,
            "ResourceType": "AWS::CloudFormation::Stub",
            "LastUpdatedTimestamp": NOW,
            "ResourceStatus": "UPDATE_COMPLETE",
        }
        session.stubs["cloudformation"].add_response(
            "describe_stack_resource", {"StackResourceDetail": detail}, expected
        )
    names = [
        RESOURCES[n]
        for n in ("DeadLetterAlarm", "AnalysisInvocationsAlarm", "ApiInvocationsAlarm")
        if n != missing
    ]
    if alarms is None:
        alarms = [alarm(n) for n in RESOURCES if n.endswith("Alarm") and n != missing]
    session.stubs["cloudwatch"].add_response(
        "describe_alarms", {"MetricAlarms": alarms}, {"AlarmNames": names}
    )
    if missing != "AlarmTopic":
        confirmed = f"{TOPIC}:0a1b2c3d"
        subs = [subscription(confirmed)] if subscriptions is None else subscriptions
        session.stubs["sns"].add_response(
            "list_subscriptions_by_topic", {"Subscriptions": subs}, {"TopicArn": TOPIC}
        )
    return session


def problems_of(session, capsys):
    with session:
        problems = harden.alarm_problems(session)
        session.check()
    for problem in problems:
        harden.say(problem)
    printed = capsys.readouterr().out
    for leak in (EMAIL, "@", ACCOUNT, "arn:"):
        assert leak not in printed and leak not in repr(problems)
    return problems


def test_alarm_problems(capsys):
    assert problems_of(stub_alarms(), capsys) == []
    [missing] = problems_of(stub_alarms(missing="ApiInvocationsAlarm"), capsys)
    assert "ApiInvocationsAlarm" in missing
    no_topic = [alarm(n) for n in RESOURCES if n.endswith("Alarm")]
    no_topic[1] = alarm("AnalysisInvocationsAlarm", AlarmActions=[])
    [unsent] = problems_of(stub_alarms(alarms=no_topic), capsys)
    assert "AnalysisInvocationsAlarm" in unsent
    no_ok = [alarm(n) for n in RESOURCES if n.endswith("Alarm")]
    no_ok[0] = alarm("DeadLetterAlarm", OKActions=[])
    [unok] = problems_of(stub_alarms(alarms=no_ok), capsys)
    assert "DeadLetterAlarm" in unok and "OKActions" in unok
    pending = [subscription("PendingConfirmation"), subscription("PendingConfirmation")]
    [unconfirmed] = problems_of(stub_alarms(subscriptions=pending), capsys)
    assert "confirmed" in unconfirmed
    wrong_function = [alarm(n) for n in RESOURCES if n.endswith("Alarm")]
    wrong_function[2] = alarm(
        "ApiInvocationsAlarm", Dimensions=[{"Name": "FunctionName", "Value": "other"}]
    )
    [elsewhere] = problems_of(stub_alarms(alarms=wrong_function), capsys)
    assert "ApiInvocationsAlarm" in elsewhere
    # Actions that are off send no email, whatever they list (review, Minor 6).
    silent = [alarm(n) for n in RESOURCES if n.endswith("Alarm")]
    silent[1] = alarm("AnalysisInvocationsAlarm", ActionsEnabled=False)
    [disabled] = problems_of(stub_alarms(alarms=silent), capsys)
    assert "AnalysisInvocationsAlarm" in disabled and "disabled" in disabled
    [gone] = problems_of(stub_alarms(missing="AnalysisFunction"), capsys)
    assert gone == "AnalysisFunction: not in the stack"


class FakeApi:
    """POST /uploads, then GET /reports/{id} answering from a script of replies."""

    def __init__(self, replies):
        self.rid = report_id("5e")
        self.replies = list(replies)
        self.requests = []

    def handle(self, request):
        self.requests.append(request)
        if request.method == "POST" and request.url.path == "/uploads":
            form = {
                "url": "https://bucket.s3.test.invalid/",
                "fields": {"key": f"raw/{self.rid}.jpg"},
            }
            return httpx.Response(
                201, json={"reportId": self.rid, "upload": form, "expiresInS": 300}
            )
        if request.method == "GET" and request.url.path == f"/reports/{self.rid}":
            status, body = self.replies.pop(0)
            return httpx.Response(status, json=body)
        return httpx.Response(500)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self.handle))


class Clock:
    def __init__(self):
        self.now, self.slept = 0.0, []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def test_confirm_private_waits_through_404(consent):
    api = FakeApi(
        [(404, {"message": "Not Found"}), (404, {}), (200, {"mode": "private"})]
    )
    clock, device = Clock(), harden.new_device_id()
    harden.confirm_private(
        api.client(),
        "https://api.test.invalid",
        device_id=device,
        offset_s=-101,
        clock=clock,
        sleep=clock.sleep,
    )
    post, *gets = api.requests
    assert [r.method for r in gets] == ["GET", "GET", "GET"]
    assert all(r.url.host == "api.test.invalid" for r in api.requests)  # nothing to S3
    assert post.headers["X-Lusot-Device"] == device
    body = json.loads(post.content)
    assert {"lat": body["lat"], "lng": body["lng"]} == harden.OUTSIDE_POINT
    sent = datetime.fromisoformat(body["capturedAt"])
    assert abs(sent - (datetime.now(UTC) - timedelta(seconds=101))) < timedelta(
        seconds=5
    )
    assert clock.slept == [1, 1]


def test_confirm_private_refuses_live(consent):
    api = FakeApi([(200, {"mode": "live"})])
    with pytest.raises(CheckFailed, match="^test point is not private$"):
        harden.confirm_private(
            api.client(),
            "https://api.test.invalid",
            device_id=harden.new_device_id(),
            offset_s=0,
            clock=Clock(),
            sleep=lambda s: None,
        )
    clock = Clock()
    api = FakeApi([(404, {})] * 40)
    with pytest.raises(CheckFailed) as caught:
        harden.confirm_private(
            api.client(),
            "https://api.test.invalid",
            device_id=harden.new_device_id(),
            offset_s=0,
            clock=clock,
            sleep=clock.sleep,
        )
    assert clock.now == 30
    assert "r_" not in str(caught.value)
    assert not any(r.url.host.endswith("s3.test.invalid") for r in api.requests)


def test_upload_body_matches_the_app(consent):
    body = harden.upload_body(harden.OUTSIDE_POINT, captured_at=datetime.now(UTC))
    assert list(body) == [
        "lat",
        "lng",
        "gpsAccuracyM",
        "capturedAt",
        "nudgeM",
        "consentVersion",
    ]
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", body["capturedAt"])
    assert body["nudgeM"] == 0
    assert body["gpsAccuracyM"] == 10
    assert body["consentVersion"] == harden.consent_version()
    assert re.fullmatch(r"[0-9a-f]{8}", body["consentVersion"])


@pytest.mark.parametrize(
    ("text", "version"),
    [("", "811c9dc5"), ("a", "e40c292c"), ("foobar", "bf9cf968"), ("ñ\r\n", None)],
)
def test_consent_version_is_ms5s_fnv1a(consent, text, version):
    consent.write_bytes(text.encode())
    if version is None:  # the bytes as they are: no newline translation
        value = 0x811C9DC5
        for byte in text.encode():
            value = ((value ^ byte) * 0x01000193) % 2**32
        version = f"{value:08x}"
    assert harden.consent_version() == version


def test_consent_version_needs_ms5s_notice(tmp_path, monkeypatch):
    monkeypatch.setattr(harden, "CONSENT_PATH", tmp_path / "missing.md")
    with pytest.raises(CheckFailed):
        harden.upload_body(harden.OUTSIDE_POINT, captured_at=datetime.now(UTC))


def test_geohash_matches_the_api():
    assert harden.geohash6(14.6095, 120.9894) == "wdw515"
    assert harden.geohash6(57.64911, 10.40744) == "u4pruy"  # the standard example
    assert metro_manila.in_metro_manila(**harden.SMOKE_SPOT)
    assert not metro_manila.in_metro_manila(**harden.OUTSIDE_POINT)


def test_publish_fields_follow_the_mode():
    assert set(harden.PUBLISH_FIELDS) == {"live", "demo"}
    for mode, fields in harden.PUBLISH_FIELDS.items():
        assert fields == {"published": True, "feedPart": mode}


def test_api_urls_reads_both_apis():
    outputs = [
        {"OutputKey": "ApiUrl", "OutputValue": "https://a1.execute-api.test.invalid/"},
        {
            "OutputKey": "FeedApiUrl",
            "OutputValue": "https://f1.execute-api.test.invalid/",
        },
        {"OutputKey": "BucketName", "OutputValue": "lusot-uploads"},
    ]
    session = FakeSession("cloudformation")
    for answer in (outputs, outputs[:1] + outputs[2:]):
        stack = {
            "StackName": "lusot",
            "CreationTime": NOW,
            "StackStatus": "UPDATE_COMPLETE",
            "Outputs": answer,
        }
        session.stubs["cloudformation"].add_response(
            "describe_stacks", {"Stacks": [stack]}, {"StackName": "lusot"}
        )
    with session:
        assert harden.api_urls(session) == (
            "https://a1.execute-api.test.invalid",
            "https://f1.execute-api.test.invalid",
        )
        with pytest.raises(CheckFailed, match="FeedApiUrl"):
            harden.api_urls(session)
        session.check()


def test_synthetic_items_have_ms4s_shape_and_are_hidden():
    times = {
        "publish": (NOW_S + 180, NOW_S + 3600),
        "hidden_expired": (NOW_S - 3600, NOW_S + 3600),
        "read_expired": (NOW_S - 7200, NOW_S - 3600),
    }
    serializer, ids = TypeSerializer(), set()
    for kind, (visible_until, expires_at) in times.items():
        item = harden.synthetic_item(kind, now_s=NOW_S)
        assert list(item) == list(harden.ITEM_FIELDS)
        assert item["mode"] == "live" and item["status"] == "done"
        assert item["pk"] == "GEO#wdw515"
        assert item.items() >= harden.PUBLISH_FIELDS["live"].items()
        assert re.fullmatch(r"r_[0-9a-f]{32}", item["reportId"])
        assert item["sk"] == f"{item['capturedAt']}#{item['reportId']}"
        assert (item["visibleUntil"], item["expiresAt"]) == (visible_until, expires_at)
        assert (item["level"], item["landmark"], item["passability"]) == (
            "knee",
            "rim_three_quarters",
            "NPLV",
        )
        assert item["levelIsFloor"] is False and item["noFloodSeen"] is False
        assert item["basis"] == {"vehicles": 1, "people": 0}
        assert (item["lat"], item["lng"]) == (Decimal("14.6095"), Decimal("120.9894"))
        captured = datetime.fromisoformat(item["capturedAt"]).timestamp()
        assert captured == visible_until - 3 * 3600  # as POST /uploads sets it
        for value in item.values():
            serializer.serialize(value)  # put_item takes it as built
        ids.add(item["reportId"])
    assert len(ids) == 3
    with pytest.raises(ValueError):
        harden.synthetic_item("visible", now_s=NOW_S)


def test_synthetic_items_hold_under_skew():
    """Review Focus 3: built from the server's time with the laptop 101 s fast, each
    item is hidden, or visible only for the switch to hide, even by a clock 101 s off
    either way (Task 1's review, Important 1)."""
    laptop = float(NOW_S)
    server = laptop - 101
    now_s = int(harden.server_now(-101, clock=lambda: laptop).timestamp())
    assert now_s == server
    for seen_at in (server - 101, server, server + 101):
        hidden = harden.synthetic_item("hidden_expired", now_s=now_s)
        assert hidden["visibleUntil"] < seen_at
        gone = harden.synthetic_item("read_expired", now_s=now_s)
        assert gone["visibleUntil"] < seen_at and gone["expiresAt"] < seen_at
        shown = harden.synthetic_item("publish", now_s=now_s)
        assert shown["visibleUntil"] > seen_at  # so only the switch can hide it


def test_names_follow_ms4s_code():
    """Task 0's record, pinned to MS4's committed code, so a change there fails here."""
    fixtures = (API_SRC / "test" / "routeFixtures.ts").read_text(encoding="utf-8")
    pin = re.search(
        r"export const PIN: Record<string, unknown> = \{\n(.*?)\n\};",
        fixtures,
        re.DOTALL,
    )
    pin_fields = set(re.findall(r"^  (\w+):", pin.group(1), re.MULTILINE))
    # The API tests' published live pin, less what a synthetic item has no use for:
    # no photo, no evidence and no geometry (C810; plan Notes, Task 1's names).
    left_out = {
        "photoKey",
        "overlayKey",
        "layersKey",
        "readings",
        "depthInMin",
        "depthInMax",
    }
    assert set(harden.ITEM_FIELDS) == pin_fields - left_out
    assert len(set(harden.ITEM_FIELDS)) == len(harden.ITEM_FIELDS)
    pins = (API_SRC / "src" / "pins.ts").read_text(encoding="utf-8")
    built = re.search(r"const pin: PublicPin = \{\n(.*?)\n  \};", pins, re.DOTALL)
    assert (
        set(re.findall(r"^    (\w+):", built.group(1), re.MULTILINE))
        == harden.PUBLIC_PIN_FIELDS
    )
    demo = re.search(r'if \(item\.mode === "demo"\) \{\n(.*?)\n  \}', pins, re.DOTALL)
    assert set(re.findall(r"pin\.(\w+) =", demo.group(1))) == harden.DEMO_EXTRA_FIELDS
    limits = (API_SRC / "src" / "limits.ts").read_text(encoding="utf-8")
    # C522's codes, which uploads and samples share; Ask Lusot's question codes aren't MS7's.
    table = re.search(r"const LIMIT_CODES\b.*? = \{\n(.*?)\n\};", limits, re.DOTALL).group(1)
    for bucket in ("upload", "sample"):
        codes = re.search(rf"^  {bucket}: \{{(.*?)\}},$", table, re.MULTILINE).group(1)
        assert set(re.findall(r'"(\w+)"', codes)) == harden.DEVICE_LIMIT_CODES
    template = (SCRIPTS.parent / "template.yaml").read_text(encoding="utf-8")
    outputs = template.split("\nOutputs:\n", 1)[1]
    assert re.search(rf"^  {harden.FEED_URL_OUTPUT}:$", outputs, re.MULTILINE)
    assert re.search(r"^  ApiUrl:$", outputs, re.MULTILINE)


def test_billed_cost():
    sam = {f"phrase {n}": 900 + n for n in range(7)}
    lines = [
        {"outcome": "refused/too_dark", "meta_calls": 0},
        {"meta_calls": 8, "sam_ms": sam, "input_tokens": 2000, "output_tokens": 300},
    ]
    # 7 x $0.0025, plus Muse Spark's $1.25 and $4.25 per million tokens (plan Table 16).
    assert harden.billed_cost(lines) == pytest.approx(0.021275)
    assert harden.billed_cost([]) == 0.0


def test_ipv4_client_and_device_ids(monkeypatch):
    made = []

    class Recorder(httpx.MockTransport):
        def __init__(self, **kwargs):
            made.append(kwargs)
            super().__init__(lambda request: httpx.Response(200))

    monkeypatch.setattr(harden.httpx, "HTTPTransport", Recorder)
    with harden.ipv4_client(15.0) as http:
        assert http.timeout.read == 15.0
    assert made == [{"local_address": "0.0.0.0"}]
    device = harden.new_device_id()
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", device
    )
    assert device != harden.new_device_id()


def test_constants_are_the_shared_ones():
    assert harden.STACK is ops_common.STACK and harden.REGION is ops_common.REGION
    assert harden.PROFILE == "lusot"
    assert [harden.SWITCH_PREFIX + s for s in harden.SWITCHES] == [
        "/lusot/stop/uploads",
        "/lusot/stop/publish",
        "/lusot/stop/model-calls",
    ]
    assert (harden.SWITCH_CACHE_S, harden.FEED_CACHE_S) == (30, 60)
