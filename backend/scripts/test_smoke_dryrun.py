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

import json
import re

import guards
import httpx
import pytest
from botocore.exceptions import ClientError
from test_smoke_upload import HAPPY, FakeCloud, rid, run_smoke

# A 12-digit run, an account ID's shape, built at run time.
ACCOUNT = "".join(str((7 * n + 3) % 10) for n in range(12))
ANY_ID = re.compile(r"r_[0-9a-fA-F]{32}")
TRACEBACK = "Traceback (most recent call last):"


def printed(capsys) -> tuple[list[str], str]:
    """The run's stdout lines, where say() prints, and all it printed, stderr too."""
    out, err = capsys.readouterr()
    return out.splitlines(), out + err


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
    _, text = printed(capsys)
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
    lines, text = printed(capsys)
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


def test_a_reply_without_a_field_prints_a_masked_traceback(
    tmp_path, monkeypatch, capsys
):
    """An answer the run didn't expect ends with a masked traceback, never Python's own,
    which would show the account."""
    cloud = FakeCloud(HAPPY)

    def describe_parameters(ParameterFilters):
        arn = f"arn:aws:ssm:ap-southeast-1:{ACCOUNT}:parameter/lusot/meta/model-api-key"
        raise TypeError(f"no LastModifiedDate in the reply for {arn} ({rid(3)})")

    monkeypatch.setattr(cloud, "ssm_describe_parameters", describe_parameters)
    assert run_smoke(tmp_path, monkeypatch, cloud) == 1
    lines, text = printed(capsys)
    assert TRACEBACK in lines
    assert lines[-1] == "SMOKE FAILED: unexpected TypeError"
    assert "parameter/lusot/meta/model-api-key (<report>)" in text
    assert "<account>" in text
    assert ACCOUNT not in text
    assert not ANY_ID.search(text)


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("connection refused"),
        httpx.InvalidURL("Invalid URL"),
        OSError("a photo's path"),
    ],
    ids=["httpx", "invalid-url", "os"],
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
    lines, text = printed(capsys)
    assert lines[-1] == f"SMOKE FAILED: {type(error).__name__}"
    assert TRACEBACK not in text
    assert "example.invalid" not in text
    assert not ANY_ID.search(text)


def test_traceback_lines_mask_ids_anywhere_and_hide_secrets():
    secret = "Zq7" + "x9Lm" * 11 + "T"
    try:
        try:
            raise ValueError(f"https://example.invalid/?X-Amz-Signature={secret}")
        except ValueError:
            raise KeyError(
                f"blurred/{rid(2)}.jpg for {ACCOUNT}, key {secret}, id {rid(4)}"
            ) from None
    except KeyError as exc:
        lines = guards.traceback_lines(exc, hide=(secret, ""))
    text = "\n".join(lines)
    assert lines[0] == TRACEBACK
    assert "blurred/<report>.jpg for <account>, key <hidden>, id <report>" in text
    assert secret not in text and ACCOUNT not in text
    assert not ANY_ID.search(text)
    # Without the exception it was raised from, whose message held a URL.
    assert "example.invalid" not in text
    assert "ValueError" not in text


def test_traceback_lines_hide_a_secret_before_its_digits_are_masked():
    """A key holding 12 digits is hidden whole, never left in pieces around <account>."""
    secret = "ab" + ACCOUNT + "cd" * 8
    lines = guards.traceback_lines(RuntimeError(f"echoed {secret}"), hide=(secret,))
    assert lines[-1] == "RuntimeError: echoed <hidden>"
