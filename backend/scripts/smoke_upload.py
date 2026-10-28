# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "boto3[crt]>=1.43.120",
#     "httpx>=0.28.1",
#     "numpy>=2.5.4",
#     "opencv-python-headless>=4.14.0.94,<5",
# ]
# ///
"""Cloud smoke test of the deployed `lusot` stack (spec A5; plan Task 8).

In order, it checks that:
1. the API's CORS preflight for POST /uploads allows the app's origins
2. one upload works end to end: POST /uploads, then a synthetic 640 x 480 JPEG through
   the presigned form, then the report leaving `pending` as failed/pipeline_not_built
   (C28). Both calls answer the Capacitor origin with its allow-origin header.
3. the raw photo is gone afterwards
4. S3 itself refuses a form whose Content-Type is image/png (403, Review Focus 1)
5. the analysis log shows the Meta key loaded at a cold start since the analysis
   function or the key last changed (C28)
6. the uploads stop switch: once on, POST /uploads gives 503 after the API's 30 s
   cache. The switch goes back to off whatever happens. Setting it with put-parameter
   is drift from the template, which resets it to "off" only when that parameter's
   resource changes.

It prints results and timings only. It never prints the account ID, an ARN, a queue URL
or an image URI: an AWS error shows its code and HTTP status, any other error only its
class name, and every printed line passes through a mask that replaces any run of 12
digits with <account>.

It always uses the lusot profile, never AWS_PROFILE. boto3 comes with its CRT extra:
that profile signs in with `aws login`, and botocore's provider for those credentials
needs the CRT.

Usage: uv run backend/scripts/smoke_upload.py
Exit codes: 0 every check passed, 1 a check failed.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime

import boto3
import cv2
import httpx
import numpy as np
from botocore.exceptions import BotoCoreError, ClientError

STACK = "lusot"
REGION = "ap-southeast-1"
SPOT = {"lat": 14.6095, "lng": 120.9894}  # the plan §12 example
APP_ORIGIN = "https://localhost"  # the Capacitor app
ORIGINS = (APP_ORIGIN, "http://localhost:4173")  # and the Vite preview server
STOP_UPLOADS = "/lusot/stop/uploads"
KEY_PARAM = "/lusot/meta/model-api-key"
SWITCH_WAIT_S = 35  # the API caches the switch for 30 s
POLL_EVERY_S = 2
POLL_FOR_S = 120
LOG_WAIT_S = 30  # log events can take a few seconds to become searchable
_ACCOUNT_ID = re.compile(r"[0-9]{12}")


class CheckFailed(Exception):
    """A check didn't get what it expected."""


def say(line: str) -> None:
    print(_ACCOUNT_ID.sub("<account>", line), flush=True)


def main() -> int:
    started = time.monotonic()
    try:
        session = boto3.Session(profile_name="lusot", region_name=REGION)
        cloudformation = session.client("cloudformation")
        [stack] = cloudformation.describe_stacks(StackName=STACK)["Stacks"]
        outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
        # Paths are joined as f"{api_url}/uploads", so no trailing slash may remain.
        api_url = outputs["ApiUrl"].rstrip("/")
        with httpx.Client(timeout=30) as http:
            check_preflight(http, api_url)
            report_id = upload_and_wait(http, api_url)
            check_raw_gone(session, outputs["BucketName"], report_id)
            check_png_refused(http, api_url)
            check_key_loaded(session)
            check_stop_switch(session, http, api_url)
    except CheckFailed as exc:
        say(f"SMOKE FAILED: {exc}")
        return 1
    except ClientError as exc:
        error = exc.response["Error"]["Code"]
        status = exc.response["ResponseMetadata"]["HTTPStatusCode"]
        say(f"SMOKE FAILED: AWS error in {exc.operation_name}: {error} (HTTP {status})")
        return 1
    except (BotoCoreError, httpx.HTTPError) as exc:
        say(f"SMOKE FAILED: {type(exc).__name__}")  # never the message
        return 1
    say(f"SMOKE OK in {time.monotonic() - started:.1f} s")
    return 0


def check_preflight(http: httpx.Client, api_url: str) -> None:
    for origin in ORIGINS:
        response = http.options(
            f"{api_url}/uploads",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        allowed = response.headers.get("access-control-allow-origin")
        if allowed != origin:
            raise CheckFailed(
                f"preflight from {origin}: HTTP {response.status_code},"
                f" allow-origin {allowed!r}"
            )
    say(f"cors: the preflight for POST /uploads allows {' and '.join(ORIGINS)}")


def upload_and_wait(http: httpx.Client, api_url: str) -> str:
    """Upload one JPEG as the app would and wait for its report's MS1 end state."""
    began = time.monotonic()
    created = request_upload(http, api_url, origin=APP_ORIGIN)
    check_allow_origin(created, "POST /uploads")
    linked = time.monotonic()
    link = created.json()
    report_id, upload = link["reportId"], link["upload"]
    # The fields go in order, and httpx sends the file after them, as S3 requires.
    posted = http.post(
        upload["url"],
        data=upload["fields"],
        files={"file": ("smoke.jpg", synthetic_photo(".jpg"), "image/jpeg")},
        headers={"Origin": APP_ORIGIN},
    )
    if posted.status_code != 204:
        raise CheckFailed(
            f"S3 form post: HTTP {posted.status_code} {s3_error(posted)}, expected 204"
        )
    check_allow_origin(posted, "the S3 form post")
    uploaded = time.monotonic()
    say(
        f"upload: link in {linked - began:.1f} s (201),"
        f" photo in {uploaded - linked:.1f} s (204)"
    )

    while True:
        response = http.get(f"{api_url}/reports/{report_id}")
        # A 404 can mean the report index hasn't caught up with the new report yet.
        if response.status_code not in (200, 404):
            raise CheckFailed(f"GET /reports: {got(response)}")
        report = (
            response.json() if response.status_code == 200 else {"status": "not_found"}
        )
        if report["status"] not in ("pending", "not_found"):
            break
        if time.monotonic() - uploaded >= POLL_FOR_S:
            raise CheckFailed(
                f"report {report_id} still {report['status']} after {POLL_FOR_S} s"
            )
        time.sleep(POLL_EVERY_S)
    end_state = f"{report['status']}/{report.get('refusalReason')}"
    if end_state != "failed/pipeline_not_built":
        raise CheckFailed(
            f"report {report_id} ended {end_state}, expected failed/pipeline_not_built"
        )
    say(f"report: {end_state} {time.monotonic() - uploaded:.1f} s after the upload")
    return report_id


def check_raw_gone(session: boto3.Session, bucket: str, report_id: str) -> None:
    try:
        session.client("s3").head_object(Bucket=bucket, Key=f"raw/{report_id}.jpg")
    except ClientError as exc:
        status = exc.response["ResponseMetadata"]["HTTPStatusCode"]
        if status != 404:
            raise CheckFailed(
                f"head_object on the raw photo: HTTP {status}, expected 404"
            ) from None
        say("raw photo: deleted (head_object gives 404)")
        return
    raise CheckFailed("the raw photo is still in the bucket")


def check_png_refused(http: httpx.Client, api_url: str) -> None:
    """S3 itself must refuse a non-JPEG, through the form's conditions (C27)."""
    created = request_upload(http, api_url)
    upload = created.json()["upload"]
    posted = http.post(
        upload["url"],
        data={**upload["fields"], "Content-Type": "image/png"},
        files={"file": ("smoke.png", synthetic_photo(".png"), "image/png")},
    )
    if posted.status_code != 403:
        raise CheckFailed(
            f"PNG form post: HTTP {posted.status_code}, expected 403 from S3"
        )
    say(f"png upload: refused by S3 (403 {s3_error(posted)})")


def check_key_loaded(session: boto3.Session) -> None:
    """The analysis stub logs model_key_loaded=true once per cold start (C28).

    Only a cold start after the function and the key last changed proves that pair
    works, so the search starts at the later change: re-storing the key doesn't change
    the function's LastModified. The key's change time comes from describe_parameters,
    so its value is never fetched.
    """
    function = session.client("cloudformation").describe_stack_resource(
        StackName=STACK, LogicalResourceId="AnalysisFunction"
    )["StackResourceDetail"]["PhysicalResourceId"]
    lam = session.client("lambda")
    config = lam.get_function(FunctionName=function)["Configuration"]
    keys = session.client("ssm").describe_parameters(
        ParameterFilters=[{"Key": "Name", "Option": "Equals", "Values": [KEY_PARAM]}]
    )["Parameters"]
    if not keys:
        raise CheckFailed(f"the Meta key parameter {KEY_PARAM} does not exist")
    since = max(
        datetime.fromisoformat(config["LastModified"]), keys[0]["LastModifiedDate"]
    )
    paginator = session.client("logs").get_paginator("filter_log_events")
    began = time.monotonic()
    while True:
        pages = paginator.paginate(
            logGroupName=config["LoggingConfig"]["LogGroup"],
            startTime=int(since.timestamp() * 1000),
            filterPattern='"model_key_loaded=true"',
        )
        # Only whether such a line exists: no log content is printed.
        if any(page["events"] for page in pages):
            say(
                "analysis log: model_key_loaded=true"
                " since the function or key last changed"
            )
            return
        if time.monotonic() - began >= LOG_WAIT_S:
            raise CheckFailed(
                "no container has cold-started since the function or key last changed,"
                " so a redeploy or a fresh container is needed"
            )
        time.sleep(5)


def check_stop_switch(session: boto3.Session, http: httpx.Client, api_url: str) -> None:
    ssm = session.client("ssm")
    failure = None
    try:
        # In the try: a put that SSM applies but that fails on our side is reset too.
        ssm.put_parameter(Name=STOP_UPLOADS, Value="on", Type="String", Overwrite=True)
        time.sleep(SWITCH_WAIT_S)
        response = request_upload(http, api_url, expect=503)
        if response.json().get("error") != "uploads_paused":
            raise CheckFailed(
                f"POST /uploads with the switch on: {got(response)},"
                " expected uploads_paused"
            )
    except BaseException as exc:
        failure = exc
        raise
    finally:
        try:
            ssm.put_parameter(
                Name=STOP_UPLOADS, Value="off", Type="String", Overwrite=True
            )
        except (BotoCoreError, ClientError):
            say(
                "STOP SWITCH LEFT ON. Set it back by hand: aws ssm put-parameter"
                f" --name {STOP_UPLOADS} --value off --type String --overwrite"
                " --profile lusot --region ap-southeast-1 --no-cli-pager"
            )
            if failure is not None:  # so the reset's error doesn't hide the first one
                say(f"the check had already failed: {failure_name(failure)}")
            raise
    say("stop switch: 503 uploads_paused while on, then set back to off")


def failure_name(exc: BaseException) -> str:
    """An exception's class name and, for an AWS error, its code. Never its message."""
    if isinstance(exc, ClientError):
        return f"{type(exc).__name__} ({exc.response['Error']['Code']})"
    return type(exc).__name__


def request_upload(
    http: httpx.Client, api_url: str, origin: str | None = None, expect: int = 201
) -> httpx.Response:
    body = {
        **SPOT,
        "gpsAccuracyM": 10,
        "capturedAt": datetime.now(UTC).isoformat(timespec="milliseconds"),
    }
    response = http.post(
        f"{api_url}/uploads", json=body, headers={"Origin": origin} if origin else {}
    )
    if response.status_code != expect:
        raise CheckFailed(f"POST /uploads: {got(response)}, expected {expect}")
    return response


def got(response: httpx.Response) -> str:
    """An API reply's status and error fields.

    Never its body: a 201 carries the signed upload form.
    """
    try:
        body = response.json()
    except ValueError:
        body = None
    # Our API sends error and detail; API Gateway's own replies send message.
    fields = (
        [str(body[key]) for key in ("error", "detail", "message") if key in body]
        if isinstance(body, dict)
        else []
    )
    return f"HTTP {response.status_code}" + (f" ({' '.join(fields)})" if fields else "")


def check_allow_origin(response: httpx.Response, what: str) -> None:
    allowed = response.headers.get("access-control-allow-origin")
    if allowed != APP_ORIGIN:
        raise CheckFailed(f"{what}: allow-origin {allowed!r}, expected {APP_ORIGIN!r}")


def synthetic_photo(ext: str) -> bytes:
    """A 640 x 480 grey gradient with no face, encoded as ".jpg" or ".png"."""
    row = np.linspace(0, 255, 640).astype(np.uint8)
    return cv2.imencode(ext, np.dstack([np.tile(row, (480, 1))] * 3))[1].tobytes()


def s3_error(response: httpx.Response) -> str:
    """An S3 error's <Code>, never its body, which can echo the signed form."""
    match = re.search(r"<Code>([^<]+)</Code>", response.text)
    return match.group(1) if match else ""


if __name__ == "__main__":
    raise SystemExit(main())
