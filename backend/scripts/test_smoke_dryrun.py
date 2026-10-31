"""Dry runs of the smoke flow: what it prints when AWS answers as it shouldn't (MS7 plan
Task 13; spec D-f, D-g, C812).

The whole run goes through test_smoke_upload's FakeCloud: httpx.MockTransport for the
API and S3's form posts, and fake_aws.FakeSession, which checks every AWS call against
botocore's model. Each test breaks one answer and reads everything printed. The account
ID and the key are built at run time, so the repo's scans never meet one. Nothing
reaches AWS or Meta.

check:py runs this file. Alone, from the repo root:
    uv run --with pytest --with "boto3[crt]" --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_smoke_dryrun.py
"""

import hashlib
import json
import re
from pathlib import Path

import guards
import httpx
import pytest
from botocore.exceptions import ClientError
from botocore.parsers import ResponseParserError
from test_smoke_upload import HAPPY, FakeCloud, rid, run_smoke

# A 12-digit run, an account ID's shape, built at run time.
ACCOUNT = "".join(str((7 * n + 3) % 10) for n in range(12))
ANY_ID = re.compile(r"r_[0-9a-fA-F]{32}")
TRACEBACK = "Traceback (most recent call last):"


def printed(capsys, tmp_path, cloud) -> tuple[list[str], str]:
    """The run's stdout lines, where say() prints, and all it printed, stderr too.

    As test_smoke_upload.printed checks, neither holds a path, a photo's name, the
    fake API's host, a report id, a device id or a device's hash.
    """
    out, err = capsys.readouterr()
    text = out + err
    devices = [device for device in cloud.devices if device]
    hashes = [hashlib.sha256(device.encode()).hexdigest() for device in devices]
    for private in (
        str(tmp_path),
        str(Path(__file__).parent),
        "Flood_in_Manila",
        "test.invalid",
        *cloud.reports,
        *devices,
        *hashes,
    ):
        assert private not in text
    assert not ANY_ID.search(text)
    assert ACCOUNT not in text
    return out.splitlines(), text


def denied(report_id: str) -> ClientError:
    """An AccessDenied as AWS words one: the caller's ARN, and a resource that names the
    photo's object key, with its report id after a slash."""
    message = (
        f"User: arn:aws:iam::{ACCOUNT}:user/rene-dev is not authorized to perform:"
        f" sqs:SendMessage for the notification of raw/{report_id}.jpg"
    )
    return ClientError(
        {
            "Error": {"Code": "AccessDenied", "Message": message},
            "ResponseMetadata": {"HTTPStatusCode": 403},
        },
        "SendMessage",
    )


def test_smoke_output_has_no_report_id(tmp_path, monkeypatch, capsys):
    cloud = FakeCloud(HAPPY)
    assert run_smoke(tmp_path, monkeypatch, cloud) == 0
    _, text = printed(capsys, tmp_path, cloud)
    assert cloud.reports  # the run made reports, each with an id
    assert not ANY_ID.search(text)
    assert TRACEBACK not in text


def test_unexpected_aws_reply_prints_a_traceback_without_the_account(
    tmp_path, monkeypatch, capsys
):
    cloud = FakeCloud(HAPPY)

    def send_message(QueueUrl, MessageBody):
        # The missing photo's notification, which the run doesn't catch.
        [record] = json.loads(MessageBody)["Records"]
        key = record["s3"]["object"]["key"]
        raise denied(key.removeprefix("raw/").removesuffix(".jpg"))

    monkeypatch.setattr(cloud, "sqs_send_message", send_message)
    assert run_smoke(tmp_path, monkeypatch, cloud) == 1
    lines, text = printed(capsys, tmp_path, cloud)
    # The traceback first, then the run's one line, so the verdict stays last.
    assert TRACEBACK in lines
    assert lines.index(TRACEBACK) < len(lines) - 1
    assert (
        lines[-1] == "SMOKE FAILED: AWS error in SendMessage: AccessDenied (HTTP 403)"
    )
    assert "arn:aws:iam::<account>:user/rene-dev" in text
    assert "raw/<report>.jpg" in text
    assert ACCOUNT not in text
    assert not ANY_ID.search(text)


def test_a_reply_without_a_field_prints_a_traceback(tmp_path, monkeypatch, capsys):
    """SSM's answer without the key's change time: a traceback, never Python's own."""
    cloud = FakeCloud(HAPPY)
    monkeypatch.setattr(
        cloud,
        "ssm_describe_parameters",
        lambda ParameterFilters: {"Parameters": [{"Name": "key"}]},
    )
    assert run_smoke(tmp_path, monkeypatch, cloud) == 1
    lines, text = printed(capsys, tmp_path, cloud)
    assert TRACEBACK in lines
    assert "KeyError: 'LastModifiedDate'" in lines
    assert lines[-1] == "SMOKE FAILED: unexpected KeyError"
    # Each frame names its file without its folders, which can name the user.
    assert '  File "smoke_upload.py", line ' in text


def test_an_unexpected_error_naming_an_arn_is_masked(tmp_path, monkeypatch, capsys):
    """An answer the run didn't expect ends with a masked traceback, never Python's own,
    which would show the account."""
    cloud = FakeCloud(HAPPY)

    def describe_parameters(ParameterFilters):
        arn = f"arn:aws:ssm:ap-southeast-1:{ACCOUNT}:parameter/lusot/meta/model-api-key"
        raise TypeError(f"no LastModifiedDate for {arn} ({rid(3)}, {'r_' + 'AB' * 16})")

    monkeypatch.setattr(cloud, "ssm_describe_parameters", describe_parameters)
    assert run_smoke(tmp_path, monkeypatch, cloud) == 1
    lines, text = printed(capsys, tmp_path, cloud)
    assert TRACEBACK in lines
    assert lines[-1] == "SMOKE FAILED: unexpected TypeError"
    assert "parameter/lusot/meta/model-api-key (<report>, <report>)" in text
    assert "<account>" in text
    assert ACCOUNT not in text
    assert not ANY_ID.search(text)


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("connection refused"),
        httpx.InvalidURL("Invalid URL"),
        OSError("a photo's path"),
        ResponseParserError("Unable to parse response, invalid XML received:"),
    ],
    ids=["httpx", "invalid-url", "os", "unparsed-reply"],
)
def test_errors_whose_messages_carry_urls_or_paths_print_only_their_class(
    tmp_path, monkeypatch, capsys, error
):
    """Their messages can hold a presigned URL, the API's URL or a photo's path, so
    they print no traceback (Oct 28's Task 8 review)."""
    cloud = FakeCloud(HAPPY)
    secret = f"https://example.invalid/raw/{rid(1)}.jpg?X-Amz-Signature=" + "f" * 64
    error.args = (f"{error.args[0]} for {secret}",)

    def head_object(Bucket, Key):
        raise error

    monkeypatch.setattr(cloud, "s3_head_object", head_object)
    assert run_smoke(tmp_path, monkeypatch, cloud) == 1
    lines, text = printed(capsys, tmp_path, cloud)
    assert lines[-1] == f"SMOKE FAILED: {type(error).__name__}"
    assert TRACEBACK not in text
    assert "example.invalid" not in text
    assert not ANY_ID.search(text)


def test_traceback_lines_mask_ids_anywhere_and_hide_secrets():
    secret = "Zq7" + "x9Lm" * 11 + "T"
    try:
        raise KeyError(f"blurred/{rid(2)}.jpg for {ACCOUNT}, key {secret}, {rid(4)}")
    except KeyError as exc:
        lines = guards.traceback_lines(exc, hide=(secret, ""))
    text = "\n".join(lines)
    assert lines[0] == TRACEBACK
    assert "blurred/<report>.jpg for <account>, key <hidden>, <report>" in text
    assert secret not in text and ACCOUNT not in text
    assert not ANY_ID.search(text)


@pytest.mark.parametrize("cause", [False, True], ids=["context", "from"])
def test_traceback_lines_leave_out_what_the_error_was_raised_from(cause):
    """The switch's reset can fail while an httpx error naming a URL is being handled,
    and Python would print that error too, as the reset's context or cause."""
    url = f"https://example.invalid/raw/{rid(6)}.jpg?X-Amz-Signature=" + "e" * 64
    try:
        try:
            raise httpx.ConnectError(f"connection refused for {url}")
        except httpx.ConnectError as first:
            if cause:
                raise RuntimeError("the reset failed") from first
            raise RuntimeError("the reset failed")  # noqa: B904, the implicit context
    except RuntimeError as exc:
        assert exc.__context__ is not None
        lines = guards.traceback_lines(exc)
    text = "\n".join(lines)
    assert lines[-1] == "RuntimeError: the reset failed"
    assert "example.invalid" not in text
    assert "ConnectError" not in text


def test_traceback_lines_hide_a_secret_before_its_digits_are_masked():
    """A key holding 12 digits is hidden whole, never in pieces around <account>."""
    secret = "ab" + ACCOUNT + "cd" * 8
    lines = guards.traceback_lines(RuntimeError(f"echoed {secret}"), hide=(secret,))
    assert lines[-1] == "RuntimeError: echoed <hidden>"


def test_a_failed_reset_still_says_the_switch_is_on(tmp_path, monkeypatch, capsys):
    """Whatever the reset's error, uploads stay paused for everyone, so the run says
    how to set the switch back, then fails."""
    cloud = FakeCloud(HAPPY)
    put = cloud.ssm_put_parameter

    def put_parameter(Name, Value, Type, Overwrite):
        if Value == "off":
            raise RuntimeError("the CRT failed")
        return put(Name=Name, Value=Value, Type=Type, Overwrite=Overwrite)

    monkeypatch.setattr(cloud, "ssm_put_parameter", put_parameter)
    assert run_smoke(tmp_path, monkeypatch, cloud) == 1
    lines, _ = printed(capsys, tmp_path, cloud)
    assert any(
        line.startswith("STOP SWITCH LEFT ON. Set it back by hand") for line in lines
    )
    assert lines[-1] == "SMOKE FAILED: unexpected RuntimeError"


def test_an_interrupt_passes_through_and_the_switch_goes_off(
    tmp_path, monkeypatch, capsys
):
    """Ctrl-C isn't an error to report: it stops the run, and the switch is reset."""
    cloud = FakeCloud(HAPPY)
    sleep = cloud.time.sleep

    def interrupted(seconds):
        if cloud.stopped:  # the switch's 35 s wait
            raise KeyboardInterrupt
        sleep(seconds)

    monkeypatch.setattr(cloud.time, "sleep", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run_smoke(tmp_path, monkeypatch, cloud)
    assert cloud.stopped is False
    _, text = printed(capsys, tmp_path, cloud)
    assert TRACEBACK not in text
