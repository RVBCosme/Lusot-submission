"""Tests for put_model_key.py: the key reaches SSM, never stdout or stderr (C16, A8).

Run: uv run --with pytest --with boto3 pytest backend/scripts/test_put_model_key.py
"""

import json

import put_model_key
import pytest
from botocore.exceptions import ClientError
from botocore.parsers import ResponseParserError

NAME = "/lusot/meta/model-api-key"
KEY = "Zq7" + "x9Lm" * 11 + "T"  # 48 characters, like the real key (spec A8)
# Built at run time, so the repo's 12-digit scan never meets a literal account ID.
ACCOUNT = "1" * 12


class FakeSSM:
    """Holds parameters in memory and answers as SSM does.

    Like the real service, it returns a SecureString's ciphertext unless the
    read asks for decryption.
    """

    def __init__(self, read_back=None, error=None):
        self.puts = []
        self.params = {}
        self._read_back = read_back
        self._error = error

    def put_parameter(self, **kwargs):
        if self._error:
            raise self._error
        self.puts.append(kwargs)
        self.params[kwargs["Name"]] = {
            "Name": kwargs["Name"],
            "Type": kwargs["Type"],
            "Value": kwargs["Value"],
            "Version": 1,
            "DataType": "text",
            "ARN": f"arn:aws:ssm:ap-southeast-1:{ACCOUNT}:parameter{kwargs['Name']}",
        }
        return {"Version": 1, "Tier": kwargs.get("Tier", "Standard")}

    def get_parameter(self, Name, WithDecryption=False):
        param = dict(self.params[Name])
        if param["Type"] == "SecureString" and not WithDecryption:
            param["Value"] = "AQICAHhciphertextnotthekey=="
        if self._read_back is not None:
            param["Value"] = self._read_back
        return {"Parameter": param}


def fragments(text, size=6):
    """Every run of `size` characters in text, so no piece of the key can slip out."""
    return {text[i : i + size] for i in range(len(text) - size + 1)}


def test_put_model_key_never_prints_value(monkeypatch, capsys):
    monkeypatch.setenv("MODEL_API_KEY", KEY)
    ssm = FakeSSM()

    assert put_model_key.main(ssm) == 0

    out, err = capsys.readouterr()
    assert f"stored {NAME} (SecureString), length 48, read-back matches: True" in out
    assert not any(piece in out + err for piece in fragments(KEY))
    assert ssm.puts == [
        {
            "Name": NAME,
            "Value": KEY,
            "Type": "SecureString",
            "KeyId": "alias/aws/ssm",
            "Overwrite": True,
            "Tier": "Standard",
        }
    ]


def test_twenty_character_key_is_stored(monkeypatch, capsys):
    monkeypatch.setenv("MODEL_API_KEY", KEY[:20])

    assert put_model_key.main(FakeSSM()) == 0
    assert "length 20, read-back matches: True" in capsys.readouterr().out


@pytest.mark.parametrize("value", [None, "", "~", KEY[:19]])
def test_missing_or_short_key_exits_2_without_storing(monkeypatch, capsys, value):
    if value is None:
        monkeypatch.delenv("MODEL_API_KEY", raising=False)
    else:
        monkeypatch.setenv("MODEL_API_KEY", value)
    ssm = FakeSSM()

    assert put_model_key.main(ssm) == 2

    out, err = capsys.readouterr()
    assert "missing or too short" in err
    assert f"length {len(value or '')}" in err
    if value:
        assert value not in out + err
    assert ssm.puts == []


def test_read_back_mismatch_exits_1(monkeypatch, capsys):
    monkeypatch.setenv("MODEL_API_KEY", KEY)

    assert put_model_key.main(FakeSSM(read_back=KEY[::-1])) == 1
    assert "read-back matches: False" in capsys.readouterr().out


def test_missing_profile_is_one_line_not_a_traceback(monkeypatch, capsys, tmp_path):
    # An empty AWS config: boto3 fails on the profile before any network call.
    (tmp_path / "config").write_text("")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "config"))
    monkeypatch.setenv("MODEL_API_KEY", KEY)

    assert put_model_key.main() == 1
    assert capsys.readouterr().err == "AWS error: ProfileNotFound\n"


def test_a_stray_aws_profile_is_ignored(monkeypatch, capsys, tmp_path):
    # Only another profile exists. Following AWS_PROFILE would send the key with that
    # profile's keys (to a dead local endpoint here); the script must insist on lusot.
    (tmp_path / "config").write_text(
        "[profile other]\nregion = ap-southeast-1\n"
        "aws_access_key_id = testing\naws_secret_access_key = testing\n"
    )
    (tmp_path / "credentials").write_text("")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "credentials"))
    monkeypatch.setenv("AWS_PROFILE", "other")
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("AWS_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("MODEL_API_KEY", KEY)

    assert put_model_key.main() == 1
    assert capsys.readouterr().err == "AWS error: ProfileNotFound\n"


def test_aws_error_prints_code_not_message(monkeypatch, capsys):
    monkeypatch.setenv("MODEL_API_KEY", KEY)
    message = f"User: arn:aws:iam::{ACCOUNT}:user/rene-dev is not authorized"
    denied = ClientError(
        {
            "Error": {"Code": "AccessDeniedException", "Message": message},
            "ResponseMetadata": {"HTTPStatusCode": 400},
        },
        "PutParameter",
    )

    assert put_model_key.main(FakeSSM(error=denied)) == 1

    out, err = capsys.readouterr()
    assert "AccessDeniedException" in err
    assert ACCOUNT not in out + err
    assert "arn:" not in out + err


class OddSSM(FakeSSM):
    """Stores the key, then answers the read with a reply the script doesn't expect."""

    def __init__(self, reply):
        super().__init__()
        self._reply = reply

    def get_parameter(self, Name, WithDecryption=False):
        if isinstance(self._reply, Exception):
            raise self._reply
        return self._reply


@pytest.mark.parametrize(
    "reply",
    [
        {"Parameter": {"Name": NAME, "Type": "SecureString"}},  # no Value
        RuntimeError(
            f"reply for arn:aws:ssm:ap-southeast-1:{ACCOUNT}:parameter{NAME}: {KEY}"
        ),
    ],
    ids=["no-value", "echoes-the-key"],
)
def test_an_unexpected_reply_prints_a_traceback_without_the_key(
    monkeypatch, capsys, reply
):
    """D-f: a reply it doesn't expect prints its traceback, through the scripts' mask,
    with the key itself hidden, so no piece of the key or the account shows."""
    monkeypatch.setenv("MODEL_API_KEY", KEY)

    assert put_model_key.main(OddSSM(reply)) == 1

    out, err = capsys.readouterr()
    assert out == ""
    lines = err.splitlines()
    assert lines[0] == "Traceback (most recent call last):"
    kind = type(reply).__name__ if isinstance(reply, Exception) else "KeyError"
    # What failed, and what to do.
    assert lines[-1] == (
        f"AWS answered as put_model_key.py doesn't expect ({kind}): the key may be"
        " stored, but it isn't checked, so run the script again"
    )
    if isinstance(reply, Exception):
        assert f"arn:aws:ssm:ap-southeast-1:<account>:parameter{NAME}: <hidden>" in err
    assert not any(piece in out + err for piece in fragments(KEY))
    assert ACCOUNT not in out + err


def test_a_reply_botocore_cannot_parse_prints_one_line(monkeypatch, capsys):
    """Its message holds the reply's whole body, the decrypted key included."""
    monkeypatch.setenv("MODEL_API_KEY", KEY)
    unparsed = ResponseParserError(f'invalid JSON received: b\'{{"Value": "{KEY}"\'')

    assert put_model_key.main(OddSSM(unparsed)) == 1

    out, err = capsys.readouterr()
    assert err == "AWS error: ResponseParserError\n"
    assert not any(piece in out + err for piece in fragments(KEY))


@pytest.mark.parametrize("form", ["repr", "json"])
def test_an_escaped_key_is_hidden_too(monkeypatch, capsys, form):
    """A key with a control character, as one pasted with Ctrl+V once held, echoed as
    repr or JSON writes it."""
    key = KEY[:24] + "\x16" + KEY[24:]
    written = repr(key)[1:-1] if form == "repr" else json.dumps(key)[1:-1]
    assert written != key
    monkeypatch.setenv("MODEL_API_KEY", key)

    assert put_model_key.main(OddSSM(RuntimeError(f"reply: {written}"))) == 1

    out, err = capsys.readouterr()
    assert "RuntimeError: reply: <hidden>" in err
    assert not any(piece in out + err for piece in fragments(KEY))
