"""Tests for laptop_spend: laptop Meta spend reaching MS4's counter (C527, R126).

The counter is moto's DynamoDB and the stop moto's SSM, or a stub that fails as
botocore does, so no test needs credentials or reaches AWS. conftest.py fails any
test that reaches the lusot profile itself.
"""

import io
import json
import threading
import wave
from decimal import Decimal
from types import SimpleNamespace

import boto3
import pytest
from botocore.exceptions import (
    ClientError,
    MissingDependencyException,
    NoCredentialsError,
)
from fakes import FakeClient, level_case, meta_error
from moto import mock_aws

from lusot_analysis import laptop_spend
from lusot_analysis.meta_client import (
    MetaApiError,
    ModelRefused,
    SparkResult,
    TranscriptResult,
)
from lusot_analysis.spend import SPARK_TOKENS_IF_UNREPORTED, SPEND_STOP_PARAM, cost_of

TABLE = "lusot-test-limits"
KEY = {"pk": {"S": "spend#meta"}}
REGION = "ap-southeast-1"
UNSEEDED = "refused: the spend counter isn't seeded, so this run can't be counted\n"
UNREADABLE = (
    "refused: the spend counter can't be read; sign in with"
    " `aws login --profile lusot` first"
)


@pytest.fixture
def aws(monkeypatch):
    """Moto's limits table, named by LIMITS_TABLE_NAME, and the stop at $140."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(name, "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    monkeypatch.setenv("LIMITS_TABLE_NAME", TABLE)
    with mock_aws():
        session = boto3.Session(region_name=REGION)
        ddb = session.client("dynamodb")
        ddb.create_table(
            TableName=TABLE,
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            ProvisionedThroughput={"ReadCapacityUnits": 2, "WriteCapacityUnits": 2},
        )
        session.client("ssm").put_parameter(
            Name=SPEND_STOP_PARAM, Value="140", Type="String"
        )
        session.client("ssm").put_parameter(
            Name=laptop_spend.MODEL_CALLS_SWITCH, Value="off", Type="String"
        )
        yield SimpleNamespace(session=session, ddb=ddb)


def add(ddb, usd: str, *, seeded: bool = True) -> None:
    """Add `usd` to the counter, and seed it as seed_spend.py does."""
    micro = int(Decimal(usd) * 1_000_000)
    expression = "ADD #micro :n" + (" SET #seeded = :true" if seeded else "")
    names = {"#micro": "micro_usd"} | ({"#seeded": "seeded"} if seeded else {})
    values = {":n": {"N": str(micro)}} | ({":true": {"BOOL": True}} if seeded else {})
    ddb.update_item(
        TableName=TABLE,
        Key=KEY,
        UpdateExpression=expression,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def stored(ddb) -> str | None:
    item = ddb.get_item(TableName=TABLE, Key=KEY).get("Item")
    return None if item is None else item["micro_usd"]["N"]


class FailingSession:
    """A session whose every call raises `error`, as botocore does with no
    credentials, or with no CRT for the profile's `aws login`."""

    def __init__(self, error: Exception) -> None:
        self.error = error
        self.made = []

    def client(self, name, **_):
        self.made.append(name)
        return SimpleNamespace(
            get_item=self._fail,
            get_parameter=self._fail,
            describe_stack_resource=self._fail,
        )

    def _fail(self, **_):
        raise self.error


def check(session):
    """check_before_paying's exit code, or the counter it returns."""
    try:
        return laptop_spend.check_before_paying(session=session)
    except SystemExit as stop:
        return stop.code


def test_a_seeded_counter_below_its_stop_lets_the_run_go_on(aws, capsys):
    add(aws.ddb, "12.34")
    counter = check(aws.session)
    assert isinstance(counter, laptop_spend.SpendCounter)
    assert capsys.readouterr().out == ""
    counter.record_after(Decimal("0.0146"), "run_pipeline")
    assert stored(aws.ddb) == "12354600"
    # Rounded up to a whole micro-dollar, never down (spend.py's to_micro).
    counter.record_after(Decimal("0.0000001"), "run_pipeline")
    assert stored(aws.ddb) == "12354601"
    assert capsys.readouterr().out == ""


def test_without_a_session_it_reads_with_the_lusot_profile(aws, monkeypatch):
    # conftest.py fails the real lusot profile; here it stands for it.
    add(aws.ddb, "1")
    monkeypatch.setattr(laptop_spend, "operator_session", lambda: aws.session)
    assert isinstance(check(None), laptop_spend.SpendCounter)


def test_an_unseeded_counter_is_refused(aws, capsys):
    # No item yet, then an item a run's ADD made before the seed: neither reads as $0.
    assert check(aws.session) == 2
    assert capsys.readouterr().out == UNSEEDED
    add(aws.ddb, "0.37", seeded=False)
    assert check(aws.session) == 2
    assert capsys.readouterr().out == UNSEEDED
    assert stored(aws.ddb) == "370000"  # the check adds nothing


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (NoCredentialsError(), "AWS error: NoCredentialsError"),
        (
            ClientError(
                {
                    "Error": {"Code": "ExpiredTokenException", "Message": "arn"},
                    "ResponseMetadata": {"HTTPStatusCode": 400},
                },
                "GetItem",
            ),
            "AWS error in GetItem: ExpiredTokenException (HTTP 400)",
        ),
    ],
)
def test_an_unreadable_counter_is_refused(monkeypatch, capsys, error, code):
    monkeypatch.setenv("LIMITS_TABLE_NAME", TABLE)
    session = FailingSession(error)
    assert check(session) == 2
    # The error's code only: its message can hold an ARN, and so the account ID.
    assert capsys.readouterr().out == f"{UNREADABLE} ({code})\n"
    assert session.made == ["dynamodb"]


def test_a_missing_table_or_stop_is_unreadable(aws, monkeypatch, capsys):
    add(aws.ddb, "1")
    aws.session.client("ssm").delete_parameter(Name=SPEND_STOP_PARAM)
    assert check(aws.session) == 2
    assert capsys.readouterr().out.startswith(f"{UNREADABLE} (AWS error in GetParam")
    monkeypatch.setenv("LIMITS_TABLE_NAME", "lusot-no-such-table")
    assert check(aws.session) == 2
    assert capsys.readouterr().out.startswith(f"{UNREADABLE} (AWS error in GetItem")


def test_a_profile_login_without_the_crt_says_so(monkeypatch, capsys):
    monkeypatch.setenv("LIMITS_TABLE_NAME", TABLE)
    error = MissingDependencyException(msg="needs botocore[crt]")
    assert check(FailingSession(error)) == 2
    assert capsys.readouterr().out == (
        "refused: the lusot profile's `aws login` credentials need botocore's CRT:"
        ' run with uv run --with "botocore[crt]==1.43.120"\n'
    )


@pytest.mark.parametrize(
    ("total", "goes_on"),
    [("139.999999", True), ("140", False), ("140.000001", False), ("151", False)],
)
def test_a_total_at_or_over_the_stop_is_refused(aws, capsys, total, goes_on):
    add(aws.ddb, total)
    result = check(aws.session)
    if goes_on:
        assert isinstance(result, laptop_spend.SpendCounter)
        return
    assert result == 2
    assert capsys.readouterr().out == (
        f"refused: the spend counter is at its stop: ${total} of $140\n"
    )


@pytest.mark.parametrize("value", ["on", "On", "maybe"])
def test_a_model_calls_switch_not_off_is_refused(aws, capsys, value):
    # C533: once the credit guard sets the switch on at the credits' expiry, a laptop
    # tool must not pay Meta either, or the card is billed. Only "off" lets it run, as
    # in the deployed handler (C60).
    add(aws.ddb, "1")
    aws.session.client("ssm").put_parameter(
        Name=laptop_spend.MODEL_CALLS_SWITCH, Value=value, Type="String", Overwrite=True
    )
    assert check(aws.session) == 2
    assert capsys.readouterr().out == (
        "refused: the model-calls switch isn't off, so no paid call runs (C533)\n"
    )


def test_a_missing_model_calls_switch_is_refused(aws, capsys):
    add(aws.ddb, "1")
    aws.session.client("ssm").delete_parameter(Name=laptop_spend.MODEL_CALLS_SWITCH)
    assert check(aws.session) == 2
    assert capsys.readouterr().out.startswith(f"refused: {laptop_spend.UNREADABLE}")


@pytest.mark.parametrize("value", ["abc", "NaN", "Infinity"])
def test_a_stop_that_isnt_a_number_is_refused(aws, capsys, value):
    add(aws.ddb, "1")
    aws.session.client("ssm").put_parameter(
        Name=SPEND_STOP_PARAM, Value=value, Type="String", Overwrite=True
    )
    assert check(aws.session) == 2
    assert capsys.readouterr().out == (
        "refused: the spend stop isn't a number, so this run can't be held to it\n"
    )


def test_a_failed_record_prints_spend_error_and_exits_3(aws, capsys):
    add(aws.ddb, "1")
    counter = check(aws.session)
    aws.ddb.delete_table(TableName=TABLE)  # the write after the run fails
    with pytest.raises(laptop_spend.SpendNotRecorded) as raised:
        counter.record_after(Decimal("0.0146"), "run_pipeline")
    assert isinstance(raised.value, SystemExit)
    assert raised.value.code == 3
    assert capsys.readouterr().out == (
        "spend_error: $0.0146 from run_pipeline isn't on the spend counter (AWS error"
        " in UpdateItem: ResourceNotFoundException (HTTP 400)); add it by hand with"
        " spend.py add --usd 0.0146 --source manual-<who>\n"
    )


def test_nothing_billed_records_nothing(capsys):
    def no_write(**_):
        raise AssertionError("an ADD of nothing was sent")

    counter = laptop_spend.SpendCounter(SimpleNamespace(update_item=no_write), TABLE)
    counter.record_after(Decimal(0), "run_pipeline")
    assert capsys.readouterr().out == ""


def wav(seconds: float, rate: int = 16_000) -> bytes:
    """A silent mono 16-bit clip of `seconds` at `rate`."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(rate)
        clip.writeframes(b"\0\0" * round(seconds * rate))
    return buffer.getvalue()


class Voice(FakeClient):
    """A FakeClient that also transcribes and counts input tokens."""

    def __init__(self, *args, transcribe_error=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.transcribe_error = transcribe_error
        self.clips = []

    def transcribe(self, data, **_):
        self.clips.append(data)
        if self.transcribe_error is not None:
            raise self.transcribe_error
        return TranscriptResult("text", 0.5, json.dumps({"transcript": "text"}))

    def count_input_tokens(self, image, *, prompt):
        return 4321


def judge(client, image="image"):
    return client.judge(image, prompt="p", schema={}, schema_name="s")


def test_counted_calls_cost_what_the_handler_charges():
    _, sam, given = level_case()
    fake = Voice(sam, given)
    counted = laptop_spend.CountedClient(fake)
    # Each SAM call that returns is one image; its keywords pass through unchanged.
    counted.segment("image", "wheel", deadline=12.5)
    counted.segment("image", "vehicle")
    assert fake.keywords[0] == {"deadline": 12.5}
    assert counted.take() == cost_of(sam_images=2)
    assert counted.take() == 0  # each amount is taken once
    # An answer adds its tokens (FakeClient reports 1000 in and 200 out).
    assert judge(counted).input_tokens == 1000
    assert counted.take() == cost_of(spark_input_tokens=1000, spark_output_tokens=200)
    # A transcript adds the clip's whole seconds, rounded up.
    counted.transcribe(wav(2.5))
    counted.transcribe(wav(2.0, rate=24_000))
    assert counted.take() == cost_of(audio_seconds=3 + 2)
    # Token counting has no price.
    assert counted.count_input_tokens("image", prompt="p") == 4321
    assert counted.take() == 0


def test_unreported_tokens_are_charged_the_fallback():
    unreported = SparkResult({}, None, None, 1.0, "{}")
    half = SparkResult({}, 900, None, 1.0, "{}")
    fake = SimpleNamespace(judge=None)
    counted = laptop_spend.CountedClient(fake)
    for answer, tokens in (
        (unreported, SPARK_TOKENS_IF_UNREPORTED),
        (half, (900, SPARK_TOKENS_IF_UNREPORTED[1])),
    ):
        fake.judge = lambda image, answer=answer, **_: answer
        judge(counted)
        assert counted.take() == cost_of(
            spark_input_tokens=tokens[0], spark_output_tokens=tokens[1]
        )


@pytest.mark.parametrize(
    ("error", "billed"),
    [
        (meta_error(503), False),  # Meta's own HTTP error answer isn't billed
        (meta_error(401), False),
        (MetaApiError("timed out", status=None), True),
        (ModelRefused("refused"), True),
        (json.JSONDecodeError("not JSON", "x", 0), True),
        (KeyboardInterrupt(), True),
    ],
)
def test_a_call_that_raised_is_charged_unless_meta_answered_an_http_error(
    error, billed
):
    _, sam, _ = level_case()

    def fail(*_):
        raise error

    fake = Voice(sam, on_segment=fail, on_judge=fail, transcribe_error=error)
    counted = laptop_spend.CountedClient(fake)
    for call in (
        lambda: counted.segment("image", "wheel"),
        lambda: judge(counted),
        lambda: counted.transcribe(wav(1.0)),
    ):
        with pytest.raises(type(error)):
            call()
    expected = cost_of(
        sam_images=1,
        spark_input_tokens=SPARK_TOKENS_IF_UNREPORTED[0],
        spark_output_tokens=SPARK_TOKENS_IF_UNREPORTED[1],
        audio_seconds=1,
    )
    assert counted.take() == (expected if billed else 0)


def test_a_clip_it_cant_read_is_never_sent():
    _, sam, given = level_case()
    fake = Voice(sam, given)
    counted = laptop_spend.CountedClient(fake)
    with pytest.raises(wave.Error):
        counted.transcribe(b"not a wav")
    assert fake.clips == []
    assert counted.take() == 0


def test_parallel_calls_are_all_counted():
    _, sam, given = level_case()
    counted = laptop_spend.CountedClient(FakeClient(sam, given))
    threads = [
        threading.Thread(target=lambda: counted.segment("image", "wheel"))
        for _ in range(40)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert counted.take() == cost_of(sam_images=40)
