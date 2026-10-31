"""MS7's shared helpers for its cloud checks (MS7 plan Task 1; spec §4.1, C803, C810, C812, C830).

load_test.py, upload_checks.py, switch_test.py and privacy_check.py import this, and
each keeps smoke_upload.py's header and lock. The import runs one way: this module
imports smoke_upload, and smoke_upload never imports it.

- **Names** that MS4 and MS5 committed, as Task 0 recorded them in the plan's Notes:
  the report item's fields, the fields that publish a pin, a public pin's fields, the
  feed API's stack output and the limits' 429 codes.
- **The app's rules,** which the load test's phones follow (MS5's C601 and C635): the
  poll's schedule, the wait after a 429, and which failures are retried once.
- **Private by construction** (C803, C812): every upload sits at OUTSIDE_POINT, and a
  run confirms that a new report reads `private` before it sends any photo. `say`
  prints through `scrub`, which masks report ids anywhere, file names included, then
  every 12-digit run with the scripts' shared mask (guards.mask). Reports are named by
  ordinal (`L#1`), and the ids behind the ordinals go only into each run's private
  record in lusot-data.
- **Server time:** every `capturedAt` comes from the server's clock, measured from a
  response's Date header, since the laptop's ran 101 s fast on Oct 28.
- **Readings** for MS9's runbook (C830): the $5 budget and the free plan's credits,
  and the three alarms that email Rene. The account ID is read inside a call and never
  returned or printed, and neither is a subscription's endpoint or an ARN.

Nothing here prints except `say`. AWS clients come in on a session.
"""

from __future__ import annotations

import itertools
import json
import random
import re
import time
import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from pathlib import Path

import guards
import httpx
import smoke_upload
from botocore.exceptions import ClientError
from metro_manila import geohash6
from ops_common import REGION, REPORT_ID, STACK, stack_outputs  # noqa: F401 (REGION: for the checks)
from smoke_upload import CheckFailed

PROFILE = "lusot"  # never AWS_PROFILE (ops_common.lusot_session)
SWITCH_PREFIX = "/lusot/stop/"
SWITCHES = ("uploads", "publish", "model-calls")
SWITCH_CACHE_S = 30  # the API caches each switch this long
FEED_CACHE_S = 60  # and the feed this long
# In Laguna de Bay: outside Metro Manila and nobody's spot, so every upload is private.
OUTSIDE_POINT = {"lat": 14.35, "lng": 121.25}
# MS1's old smoke spot in Manila (geohash wdw515), MS7's own: the synthetic live items
# need a Metro Manila cell, so it never follows smoke_upload.SPOT (MS4's C513).
SMOKE_SPOT = {"lat": 14.6095, "lng": 120.9894}
COST_PER_REAL_PHOTO = 0.034  # USD, C804
COST_PER_QUESTION = 0.01  # USD, C828, until MS6's tests give Ask Lusot's own
DEVICE_LIMIT_CODES = frozenset({"device_limit", "global_cap"})  # MS4's C522
# A done live landmark level as MS4 stores it (uploads.ts, the pipeline's item_fields
# and the handler's publish fields), without a photo, readings or inches (C810).
ITEM_FIELDS = (
    "pk",
    "sk",
    "reportId",
    "mode",
    "status",
    "lat",
    "lng",
    "gpsAccuracyM",
    "nudgeM",
    "capturedAt",
    "receivedAt",
    "flags",
    "visibleUntil",
    "expiresAt",
    "noFloodSeen",
    "level",
    "landmark",
    "passability",
    "levelIsFloor",
    "basis",
    "levelFrom",
    "published",
    "feedPart",
)
# What publishing adds, by mode (handler.py's _publish_fields).
PUBLISH_FIELDS: dict[str, dict[str, object]] = {
    mode: {"published": True, "feedPart": mode} for mode in ("live", "demo")
}
# pins.ts's publicPin, with the inches hidden (C515).
PUBLIC_PIN_FIELDS = frozenset(
    {
        "id",
        "lat",
        "lng",
        "gpsAccuracyM",
        "capturedAt",
        "mode",
        "level",
        "landmark",
        "passability",
        "levelIsFloor",
        "basis",
        "flags",
    }
)
DEMO_EXTRA_FIELDS = frozenset({"credit", "place", "event"})  # C523
API_URL_OUTPUT = "ApiUrl"
FEED_URL_OUTPUT = "FeedApiUrl"  # C521: the public feed's own read-only API
# MS5's consent notice: its version is a hash of this file's text (consent.tsx).
CONSENT_PATH = (
    Path(__file__).resolve().parents[2] / "app" / "src" / "content" / "consent.en.md"
)
GPS_ACCURACY_M = 10
VISIBLE_S = 3 * 60 * 60  # POST /uploads hides a pin 3 h after capture
POLL_WINDOW_S = 600  # C601
RETRY_KINDS = ("network", "503", "throttle", "device_limit", "other")
PRIVATE_EVERY_S = 1
PRIVATE_FOR_S = 30  # through the report index's 404s
FREE_TIER_REGION = "us-east-1"  # the Free Tier API answers only there
BUDGET_LIMIT_USD = 5  # C25's budget, made at sign-up, outside the template
CREDIT_FALL_FLAG_USD = 0.25  # a day: faster than cents a day goes to Rene at once
# C32's id anywhere, file names included: MS7 prints none (C812).
_ANY_REPORT_ID = re.compile(r"r_[0-9a-fA-F]{32}")
_WHOLE_SECONDS = re.compile(r"[0-9]+")
_INVOCATION_ALARMS = {
    "AnalysisInvocationsAlarm": "AnalysisFunction",
    "ApiInvocationsAlarm": "ApiFunction",
}


def api_urls(session) -> tuple[str, str]:
    """The app API's URL and the feed API's, from the stack's outputs, without a
    trailing slash. A stack without either stops the run before any upload."""
    outputs = stack_outputs(session)
    missing = [
        name for name in (API_URL_OUTPUT, FEED_URL_OUTPUT) if not outputs.get(name)
    ]
    if missing:
        raise CheckFailed(f"the stack has no {' or '.join(missing)} output")
    return outputs[API_URL_OUTPUT].rstrip("/"), outputs[FEED_URL_OUTPUT].rstrip("/")


def scrub(text: str) -> str:
    """`text` with each report id as <report>, then each 12-digit run as <account>.

    The ids go first, so an id's own digits never half-show. The digits follow the
    scripts' shared rule, guards.mask, which also masks the first 12 of a longer run.
    """
    return guards.mask(_ANY_REPORT_ID.sub("<report>", text))


def say(line: str) -> None:
    print(scrub(line), flush=True)


def new_device_id() -> str:
    return str(uuid.uuid4())


def data_dir() -> Path:
    """LUSOT_DATA_DIR, or the laptop's lusot-data. A sealed path is refused."""
    path = guards.data_dir()
    if guards.is_sealed(path):
        raise CheckFailed("refused: a path inside a folder named sealed")
    return path


class RunRecord:
    """One run's private record: its reports by ordinal, and its device ids.

    Ordinals carry the run's letter (`L#1`). They number on from the records already
    saved in `folder` with that letter, so two runs on one day never share one.
    """

    def __init__(
        self,
        folder: Path,
        script: str,
        letter: str,
        *,
        clock: Callable[[], datetime] = datetime.now,
    ):
        if guards.is_sealed(folder):
            raise CheckFailed("refused: a path inside a folder named sealed")
        self.folder, self.script, self.letter = folder, script, letter
        self.started = clock()
        self.path: Path | None = None
        self._ids: dict[str, str] = {}  # report id: ordinal
        self._devices: list[str] = []
        saved = load_records([folder])[0] if folder.is_dir() else {}
        prefix = f"{letter}#"
        self._first = 1 + max(
            (int(name[len(prefix) :]) for name in saved if name.startswith(prefix)),
            default=0,
        )

    def name(self, report_id: str) -> str:
        if report_id not in self._ids:
            self._ids[report_id] = f"{self.letter}#{self._first + len(self._ids)}"
        return self._ids[report_id]

    def device(self, device_id: str) -> str:
        if device_id not in self._devices:
            self._devices.append(device_id)
        return device_id

    def save(self) -> Path:
        """Write ids-<script>-<HHMMSS>.json, or -2, -3 and so on beside another run's.

        A later save rewrites this record's own file, never another run's.
        """
        body = json.dumps(
            {
                "ordinals": {ordinal: rid for rid, ordinal in self._ids.items()},
                "devices": self._devices,
            },
            indent=2,
        )
        if self.path is not None:
            self.path.write_text(body, encoding="utf-8")
            return self.path
        self.folder.mkdir(parents=True, exist_ok=True)
        stem = f"ids-{self.script}-{self.started:%H%M%S}"
        for n in itertools.count(1):
            path = self.folder / (f"{stem}.json" if n == 1 else f"{stem}-{n}.json")
            try:
                with path.open("x", encoding="utf-8") as file:
                    file.write(body)
            except FileExistsError:
                continue
            self.path = path
            return path
        raise AssertionError("unreachable")


def load_records(paths: Iterable[Path]) -> tuple[dict[str, str], list[str]]:
    """Every ordinal and device id in the given records, or in every ids-*.json of a
    given folder. An ordinal that two records give to different reports is refused,
    rather than one report dropped."""
    files: list[Path] = []
    for path in paths:
        if guards.is_sealed(path):
            raise CheckFailed("refused: a path inside a folder named sealed")
        files += sorted(path.glob("ids-*.json")) if path.is_dir() else [path]
    ordinals: dict[str, str] = {}
    devices: list[str] = []
    for file in files:
        try:
            record = json.loads(file.read_text(encoding="utf-8"))
            names, found = dict(record["ordinals"]), list(record["devices"])
        except (OSError, ValueError, TypeError, KeyError):
            raise CheckFailed(f"the run record {file.name} isn't readable") from None
        for ordinal, rid in names.items():
            if ordinals.setdefault(ordinal, rid) != rid:
                raise CheckFailed(
                    f"two run records name {ordinal} differently: pass one run's records"
                )
        devices += [device for device in found if device not in devices]
    return ordinals, devices


def server_offset(
    http: httpx.Client, api_url: str, *, clock: Callable[[], float] = time.time
) -> float:
    """The server's time less the laptop's, from the Date header of one CORS preflight
    to POST /uploads, against the middle of the request."""
    before = clock()
    response = http.options(
        f"{api_url}/uploads",
        headers={
            "Origin": smoke_upload.APP_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                f"content-type,{smoke_upload.DEVICE_HEADER.lower()}"
            ),
        },
    )
    after = clock()
    try:
        server = parsedate_to_datetime(response.headers["date"])
    except (KeyError, TypeError, ValueError):
        raise CheckFailed(
            f"the preflight for POST /uploads: HTTP {response.status_code}, no readable"
            " Date header"
        ) from None
    if server.tzinfo is None:  # an HTTP date is in GMT
        server = server.replace(tzinfo=UTC)
    return server.timestamp() - (before + after) / 2


def server_now(offset_s: float, *, clock: Callable[[], float] = time.time) -> datetime:
    return datetime.fromtimestamp(clock() + offset_s, UTC)


def poll_interval(elapsed_s: float) -> float | None:
    """The wait before the next poll of a report, by the seconds since its photo went
    (C601): 2 s for the first minute, 5 s to 4 minutes, then 15 s. MS5 cuts the last
    wait to the 600 s deadline and polls once more there; from 600 s, None."""
    if elapsed_s >= POLL_WINDOW_S:
        return None
    step = 2.0 if elapsed_s < 60 else 5.0 if elapsed_s < 240 else 15.0
    return min(step, POLL_WINDOW_S - elapsed_s)


def wait_after_429(
    retry_after: str | None, interval_s: float, rng: random.Random
) -> float:
    """MS5's wait after a 429: its Retry-After in whole seconds, never less than the
    interval, or else the interval plus up to 1 s. The caller cuts it to the deadline."""
    text = (retry_after or "").strip()
    if _WHOLE_SECONDS.fullmatch(text):
        return max(float(text), interval_s)
    return interval_s + rng.uniform(0, 1)


def classify_429(body: object) -> str:
    """A limit's 429 names its code; API Gateway's own throttle has none. As MS5 reads
    it (retry.ts), any code is a limit, never retried: DEVICE_LIMIT_CODES (C522) for an
    upload, and Ask Lusot's question_limit and question_cap too."""
    error = body.get("error") if isinstance(body, dict) else None
    return "device_limit" if isinstance(error, str) else "throttle"


def should_retry(kind: str, attempt: int) -> bool:
    """C635: the upload request and the S3 post each retry once, after 2 s, on a
    network error, a 503 or a throttle. A limit is never retried. The caller passes a
    503 uploads_paused as "other", since MS5 doesn't retry it."""
    if kind not in RETRY_KINDS:
        raise ValueError(f"unknown failure kind: {kind}")
    return attempt == 0 and kind in ("network", "503", "throttle")


def ipv4_client(timeout_s: float = 30.0) -> httpx.Client:
    """IPv4 only: IPv6 doesn't connect on the home Wi-Fi (Oct 28 log)."""
    transport = httpx.HTTPTransport(local_address="0.0.0.0")
    return httpx.Client(timeout=timeout_s, transport=transport)


def consent_version() -> str:
    """MS5's NOTICE_VERSION: FNV-1a, 32 bits, over the consent notice's UTF-8 bytes as
    Vite reads them (no newline translation), as 8 hex digits. A missing notice stops
    the run, so no upload goes without its version."""
    try:
        data = CONSENT_PATH.read_bytes()
        data.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        raise CheckFailed(
            "MS5's consent notice isn't readable, so its version is unknown"
        ) from None
    value = 0x811C9DC5
    for byte in data:
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return f"{value:08x}"


def upload_body(point: dict, *, captured_at: datetime) -> dict:
    """The body MS5's app sends to POST /uploads (api.ts's requestUpload)."""
    if captured_at.tzinfo is None:
        raise ValueError("captured_at needs a time zone")
    stamp = captured_at.astimezone(UTC).isoformat(timespec="milliseconds")
    return {
        "lat": point["lat"],
        "lng": point["lng"],
        "gpsAccuracyM": GPS_ACCURACY_M,
        "capturedAt": stamp.replace("+00:00", "Z"),
        "nudgeM": 0,
        "consentVersion": consent_version(),
    }


def confirm_private(
    http: httpx.Client,
    api_url: str,
    *,
    device_id: str,
    offset_s: float,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    wall: Callable[[], float] = time.time,
) -> None:
    """C803's precondition: one report at OUTSIDE_POINT, with no photo, must read
    `private` before a run sends any photo.

    GET /reports/{id} is read every 1 s through 404s, since the report index can lag a
    new report, for up to 30 s. Any other mode, any other answer, or no report by then
    raises CheckFailed. No message names the report. `wall` is the laptop's clock that
    `offset_s` corrects.
    """
    body = upload_body(OUTSIDE_POINT, captured_at=server_now(offset_s, clock=wall))
    posted = http.post(
        f"{api_url}/uploads", json=body, headers={smoke_upload.DEVICE_HEADER: device_id}
    )
    if posted.status_code != 201:
        raise CheckFailed(f"POST /uploads: {smoke_upload.got(posted)}, expected 201")
    rid = smoke_upload.json_object(posted, "POST /uploads").get("reportId")
    if not isinstance(rid, str) or REPORT_ID.fullmatch(rid) is None:
        raise CheckFailed("POST /uploads: HTTP 201 without a report id")
    began = clock()
    while True:
        response = http.get(f"{api_url}/reports/{rid}")
        if response.status_code == 200:
            if (
                smoke_upload.json_object(response, "GET /reports").get("mode")
                != "private"
            ):
                raise CheckFailed("test point is not private")
            return
        if response.status_code != 404:
            raise CheckFailed(f"GET /reports: {smoke_upload.got(response)}")
        if clock() - began >= PRIVATE_FOR_S:
            raise CheckFailed(f"the test report wasn't found in {PRIVATE_FOR_S} s")
        sleep(PRIVATE_EVERY_S)


def synthetic_item(kind: str, *, now_s: int) -> dict:
    """A done live knee pin at SMOKE_SPOT, with the fields that publish it, and no
    photo (C810). Each kind is hidden by the clock or kept hidden by the switch:

    - "publish": visible for 180 s, so only the publish switch hides it (S3)
    - "hidden_expired": an hour past its visibleUntil, so it is never visible (P5)
    - "read_expired": an hour past its expiresAt too, so GET /reports/{id} answers 404
      (P5)

    `now_s` must be the server's time, `int(server_now(offset_s).timestamp())`: the API
    compares these times with its own clock, and the laptop's ran 101 s fast on Oct 28.
    The expired kinds keep an hour's margin all the same (the plan's 60 s, widened
    after Task 1's review), so a wrong clock can't show one. Numbers are ints or
    Decimals, so boto3 serialises the item as built. Its capture time is visibleUntil
    less 3 h, as POST /uploads sets it.
    """
    times = {
        "publish": (now_s + 180, now_s + 3600),
        "hidden_expired": (now_s - 3600, now_s + 3600),
        "read_expired": (now_s - 7200, now_s - 3600),
    }
    if kind not in times:
        raise ValueError(f"unknown synthetic item: {kind}")
    visible_until, expires_at = times[kind]
    captured = datetime.fromtimestamp(visible_until - VISIBLE_S, UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    rid = "r_" + uuid.uuid4().hex
    return {
        "pk": f"GEO#{geohash6(SMOKE_SPOT['lat'], SMOKE_SPOT['lng'])}",
        "sk": f"{captured}#{rid}",
        "reportId": rid,
        "mode": "live",
        "status": "done",
        "lat": Decimal(str(SMOKE_SPOT["lat"])),
        "lng": Decimal(str(SMOKE_SPOT["lng"])),
        "gpsAccuracyM": GPS_ACCURACY_M,
        "nudgeM": 0,
        "capturedAt": captured,
        "receivedAt": captured,
        "flags": 0,
        "visibleUntil": visible_until,
        "expiresAt": expires_at,
        "noFloodSeen": False,
        "level": "knee",
        "landmark": "rim_three_quarters",
        "passability": "NPLV",
        "levelIsFloor": False,
        "basis": {"vehicles": 1, "people": 0},
        "levelFrom": "landmark",
        **PUBLISH_FIELDS["live"],
    }


def billed_cost(lines: list[dict]) -> float:
    """The USD the log lines' Meta calls cost, at spend.py's prices: SAM's calls by
    their sam_ms, and Muse Spark's billed input_tokens and output_tokens
    (smoke_upload.run_summary)."""
    return float(smoke_upload.run_summary(lines)["usd"])


def budget_status(session) -> dict[str, object]:
    """C830's reading: the $5 budget and the free plan's credits, amounts only.

    The account ID goes from sts into the budgets call and nowhere else; the Free Tier
    API's accountId is left out.
    """
    account = session.client("sts").get_caller_identity()["Account"]
    pages = (
        session.client("budgets")
        .get_paginator("describe_budgets")
        .paginate(AccountId=account)
    )
    found = [
        budget
        for page in pages
        for budget in page.get("Budgets", [])
        if budget.get("BudgetLimit", {}).get("Unit") == "USD"
        and Decimal(budget["BudgetLimit"]["Amount"]) == BUDGET_LIMIT_USD
    ]
    if len(found) != 1:
        raise CheckFailed(f"expected one budget with a $5 limit, found {len(found)}")
    [budget] = found
    spend = budget.get("CalculatedSpend", {})
    plan = session.client(
        "freetier", region_name=FREE_TIER_REGION
    ).get_account_plan_state()
    try:
        actual = float(spend["ActualSpend"]["Amount"])
        credits_left = float(plan["accountPlanRemainingCredits"]["amount"])
        plan_type, plan_status = plan["accountPlanType"], plan["accountPlanStatus"]
    except KeyError as exc:
        raise CheckFailed(f"the budget or plan reading has no {exc.args[0]}") from None
    forecast = spend.get("ForecastedSpend")
    end = plan.get("accountPlanExpirationDate")
    return {
        "limit": float(budget["BudgetLimit"]["Amount"]),
        "actual": actual,
        "forecast": float(forecast["Amount"]) if forecast else None,
        # AWS Budgets counts credits unless told not to.
        "include_credit": bool(budget.get("CostTypes", {}).get("IncludeCredit", True)),
        "plan_type": plan_type,
        "plan_status": plan_status,
        "credits_left": credits_left,
        "plan_end": end.date().isoformat() if end else None,
    }


def budget_meaning(
    status: dict, *, last_credits: float | None = None, days_since: float = 1.0
) -> list[str]:
    """One plain line for the budget and one for the free plan, saying what each
    number means. The plan's line flags PAID, EXPIRED, or credits that fell faster
    than cents a day since the last reading given (`last_credits`, `days_since` ago)."""
    forecast = status["forecast"]
    budget = (
        f"The ${status['limit']:.2f} budget: ${status['actual']:.2f} spent this month,"
        + (
            f" ${forecast:.2f} forecast."
            if forecast is not None
            else " no forecast yet."
        )
    )
    if status["include_credit"]:
        budget += (
            " It counts credits, so it nets them against usage and stays near $0 while"
            " the credits pay: it says little about burn."
        )
    else:
        budget += (
            " It leaves credits out, so it shows the usage the credits are paying."
        )
    credits = status["credits_left"]
    plan = (
        f"The free plan: {status['plan_type']}, {status['plan_status']},"
        f" ${credits:.2f} of credits left, ending {status['plan_end'] or 'on no date given'}."
        " The remaining credits are the burn signal."
    )
    if status["plan_type"] == "PAID":
        plan += " FLAG: the plan is PAID, so usage is billed to the card. Tell Rene at once."
    if status["plan_status"] == "EXPIRED":
        plan += " FLAG: the plan has EXPIRED. Tell Rene at once."
    if last_credits is not None:
        if days_since <= 0:
            raise ValueError("days_since must be more than 0")
        fall = last_credits - credits
        if fall / days_since > CREDIT_FALL_FLAG_USD:
            plan += (
                f" FLAG: the credits fell ${fall:.2f} in {days_since:g} days, faster than"
                " cents a day. Tell Rene at once."
            )
    return [budget, plan]


def alarm_problems(session) -> list[str]:
    """C830: the dead-letter alarm (with OKActions) and MS4's two invocation alarms
    (Invocations summed per hour, on the analysis and API functions) must each have
    their actions enabled and list the stack's alarm topic among them, and the topic
    needs at least one confirmed email subscription. Each problem names a logical id,
    never an ARN, an alarm's name or a subscription's endpoint."""
    cloudformation = session.client("cloudformation")

    def physical(logical: str) -> str | None:
        try:
            detail = cloudformation.describe_stack_resource(
                StackName=STACK, LogicalResourceId=logical
            )["StackResourceDetail"]
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ValidationError":
                return None  # not in the stack
            raise
        return detail["PhysicalResourceId"]

    problems: list[str] = []
    topic = physical("AlarmTopic")
    if topic is None:
        problems.append("AlarmTopic: not in the stack")
    functions = {
        logical: physical(logical) for logical in ("AnalysisFunction", "ApiFunction")
    }
    problems += [
        f"{logical}: not in the stack" for logical, n in functions.items() if not n
    ]
    names: dict[str, str] = {}
    for logical in ("DeadLetterAlarm", *_INVOCATION_ALARMS):
        name = physical(logical)
        if name is None:
            problems.append(f"{logical}: not in the stack")
        else:
            names[logical] = name
    found: dict[str, dict] = {}
    if names:
        pages = (
            session.client("cloudwatch")
            .get_paginator("describe_alarms")
            .paginate(AlarmNames=list(names.values()))
        )
        found = {
            a["AlarmName"]: a for page in pages for a in page.get("MetricAlarms", [])
        }
    for logical, name in names.items():
        alarm = found.get(name)
        if alarm is None:
            problems.append(f"{logical}: not found in CloudWatch")
            continue
        if alarm.get("ActionsEnabled") is not True:
            problems.append(f"{logical}: its actions are disabled")
        if topic is not None and topic not in alarm.get("AlarmActions", []):
            problems.append(f"{logical}: the alarm topic isn't among its AlarmActions")
        if logical == "DeadLetterAlarm":
            if topic is not None and topic not in alarm.get("OKActions", []):
                problems.append(
                    "DeadLetterAlarm: the alarm topic isn't among its OKActions"
                )
            continue
        function = functions[_INVOCATION_ALARMS[logical]]
        if function is None:
            continue  # already a problem
        if not (
            alarm.get("Namespace") == "AWS/Lambda"
            and alarm.get("MetricName") == "Invocations"
            and alarm.get("Statistic") == "Sum"
            and alarm.get("Period") == 3600
            and alarm.get("Dimensions") == [{"Name": "FunctionName", "Value": function}]
        ):
            problems.append(
                f"{logical}: not {_INVOCATION_ALARMS[logical]}'s Invocations summed per hour"
            )
    if topic is not None:
        pages = (
            session.client("sns")
            .get_paginator("list_subscriptions_by_topic")
            .paginate(TopicArn=topic)
        )
        subscriptions = [s for page in pages for s in page.get("Subscriptions", [])]
        confirmed = sum(
            s.get("Protocol") == "email"
            and s.get("SubscriptionArn", "").startswith("arn:")
            for s in subscriptions
        )
        if confirmed == 0:
            problems.append(
                f"AlarmTopic: no confirmed email subscription ({len(subscriptions)} in all)"
            )
    return problems
