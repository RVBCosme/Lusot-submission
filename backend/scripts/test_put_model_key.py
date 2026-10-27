"""Tests for put_model_key.py: the key reaches SSM, never stdout or stderr (C16, A8).

Run: uv run --with pytest --with boto3 pytest backend/scripts/test_put_model_key.py
"""

import put_model_key
import pytest
from botocore.exceptions import ClientError

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
    monkeypatch.delenv("AWS_PROFILE", raising=False)
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
