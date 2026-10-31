"""Test-only fakes for MS7's scripts' tests, on botocore's Stubber (MS7 plan Tasks 2 to 5).

No network and no credentials: each client is a real botocore client whose every call is
answered by its Stubber, in the order the test queued it, so an unqueued call fails the
test instead of reaching AWS. HTTP fakes are the tests' own httpx.MockTransport
handlers. Every 12-digit run, report id, key-like value and address is built at run
time, so no file holds one for the account-ID scan or gitleaks.
"""

import random
from email.utils import formatdate

import boto3
from botocore.stub import Stubber


class StubSession:
    """A boto3 session whose clients are stubbed, active from the start. It records the
    region each client asks for, and every call in order, across clients, in `calls`
    as (service, operation, params). `on_call(service, operation, params)` sees each
    call before its Stubber answers it, so a fake API can follow what the call did."""

    def __init__(self, *services: str, region: str = "ap-southeast-1", on_call=None):
        base = boto3.Session(
            aws_access_key_id="stub", aws_secret_access_key="stub", region_name=region
        )
        self.clients = {name: base.client(name) for name in services}
        self.stubs = {name: Stubber(client) for name, client in self.clients.items()}
        self.regions: dict[str, str | None] = {}
        self.calls: list[tuple[str, str, dict]] = []
        self.on_call = on_call
        for name, client in self.clients.items():
            client.meta.events.register_first(
                "before-parameter-build.*.*",
                lambda params, model, service=name, **_: self._record(
                    service, model, params
                ),
            )
        for stub in self.stubs.values():
            stub.activate()

    def _record(self, service: str, model, params: dict) -> None:
        self.calls.append((service, model.name, dict(params)))
        if self.on_call is not None:
            self.on_call(service, model.name, dict(params))

    def client(self, service: str, region_name: str | None = None):
        self.regions[service] = region_name
        return self.clients[service]

    def done(self) -> None:
        """Every queued answer was used."""
        for stub in self.stubs.values():
            stub.assert_no_pending_responses()


class Clock:
    """A fake clock: calling it gives wall time, `mono` a monotonic time that starts at
    1,000 s, so code that mixes the two is caught; sleep moves both on."""

    def __init__(self, now: float = 0.0):
        self.now = now
        self.start = now
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def mono(self) -> float:
        return self.now - self.start + 1000.0

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += max(seconds, 0.0)


def report_ids(count: int, *, seed: int = 0) -> list[str]:
    """`count` report ids in C32's form, the same on every run for one seed."""
    return [
        f"r_{random.Random(seed * 1000 + n).getrandbits(128):032x}"
        for n in range(count)
    ]


def http_date(epoch_s: float) -> str:
    """An HTTP Date header for `epoch_s`, to the second, as API Gateway sends it."""
    return formatdate(epoch_s, usegmt=True)


def stack_answers(session: StubSession, outputs: dict[str, str]) -> None:
    """Queue smoke_upload.load_stack's two CloudFormation calls."""
    stack = {
        "StackName": "lusot",
        "CreationTime": "2026-10-28T00:00:00Z",
        "StackStatus": "UPDATE_COMPLETE",
        "Outputs": [{"OutputKey": k, "OutputValue": v} for k, v in outputs.items()],
    }
    cloudformation = session.stubs["cloudformation"]
    cloudformation.add_response(
        "describe_stacks", {"Stacks": [stack]}, {"StackName": "lusot"}
    )
    detail = {
        "LogicalResourceId": "AnalysisLogGroup",
        "PhysicalResourceId": "lusot-analysis-log-group",
        "ResourceType": "AWS::Logs::LogGroup",
        "LastUpdatedTimestamp": "2026-10-28T00:00:00Z",
        "ResourceStatus": "UPDATE_COMPLETE",
    }
    cloudformation.add_response(
        "describe_stack_resource",
        {"StackResourceDetail": detail},
        {"StackName": "lusot", "LogicalResourceId": "AnalysisLogGroup"},
    )


def log_answer(session: StubSession, lines: list[str] = ()) -> None:
    """Queue one filter_log_events page holding these JSON lines, in Lambda's text
    format (level, time and request id before each)."""
    events = [
        {
            "logStreamName": "stream",
            "timestamp": 1,
            "ingestionTime": 1,
            "eventId": f"event-{n}",
            "message": f"[INFO]\t2026-11-03T02:15:00.000Z\treq-{n}\t{line}\n",
        }
        for n, line in enumerate(lines)
    ]
    session.stubs["logs"].add_response("filter_log_events", {"events": events})


def missing_object(session: StubSession) -> None:
    """Queue one head_object that finds nothing (404)."""
    session.stubs["s3"].add_client_error(
        "head_object", service_error_code="404", http_status_code=404
    )
