"""Ask Lusot's probe (plan Task 2, spec C731): Muse Spark with Ask's prompt and tool.

Typed questions only (Ask ships without voice). It settles, before the build:
- whether tools and `text.format` can sit in one request (F4), and the other forms of
  each turn if they can't: turn 1 `tools_only`, the final turn `plain_input`;
- the stateless final turn (F2), which replays turn 1's reasoning items;
- `minimal` against `low` effort, 10 timings each (the plan's step 1).

Run from the repo root, with MODEL_API_KEY set and `aws login --profile lusot` done
(the counter's credentials need the CRT, as run_probe.py's do):

    uv run --directory backend/analysis --with "botocore[crt]==1.43.120"
        python probes/ask_probe.py [--yes] [--runs 10]

Without --yes it prints the planned call count and the worst-case cost, and stops:
no key, no counter and no network. With --yes it spends Meta credits: 44 calls in the
main plan at --runs 10 (49 with step 5). --runs takes 1 to 10.

The cost guard holds the run to COST_CAP_USD ($0.50; raised from $0.30 once the estimate
became a proven upper bound, so the plan's 10 timings fit). A call's worst case is its
request body's UTF-8 byte count as input tokens (a token is never fewer than one
byte, so the text sent can't cost more tokens than bytes) plus the whole
max_output_tokens as output. That bound covers the bytes sent, not Meta's own chat
template or the reasoning behind a replayed encrypted_content, which the body doesn't
show. Real usage is far under it. Before the first paid call the main plan's worst
case must fit the cap, or the run exits 4 without a call; before each call, what has
been spent so far plus that call's worst case must fit, or the run stops and exits 4.
Each call is made once, with no retry: a 429 or a 5xx is that call's result.

The prompt, tools and schema are read from backend/api/prompts/ (ask_v1.*). Outputs go
to LUSOT_DATA_DIR/probes/<today>/ask/ as ask_summary.json and ask_calls.jsonl, never
summary.json (the MS1 probe's file, probe note section 7), and a run refuses to start
over either file. Stdout gets counts and timings only: never a question's answer, a
tool call's arguments or the key. The key is read from MODEL_API_KEY alone, sent only
in the request's Authorization header, and replaced by "[key]" in every line and file
this script writes.

Before the client is built, MS4's spend counter is read with the lusot profile, and
the run's cost is recorded once at its end however it ends, as run_probe.py does
(C527, R126). A call that raises, Ctrl+C included, or that Meta answers with a body
that can't be read, is charged at the counter's unreported rate, since it may have
been billed. ask_summary.json is written however the run ends, and says how. Exit
codes: 0 done; 2 refused (nothing was paid for); 3 the cost couldn't be recorded; 4
stopped at the cost guard, or refused because the plan's worst case passes the cap.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import statistics
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import openai
from jsonschema import Draft202012Validator

# check_before_paying is a seam: tests replace it, as they pass make_client (C527).
from lusot_analysis.laptop_spend import check_before_paying
from lusot_analysis.meta_client import BASE_URL, REASONING_EFFORTS, SPARK_MODEL
from lusot_analysis.spend import SPARK_TOKENS_IF_UNREPORTED, cost_of

REPO = Path(__file__).resolve().parents[3]  # above probes/, analysis/ and backend/
PROMPTS = REPO / "backend" / "api" / "prompts"
PROMPT_VERSION = "ask_v1"
ANSWER_NAME = "ask_answer_v1"
DATA = Path(os.environ.get("LUSOT_DATA_DIR") or r"C:\Systems\Lusot\lusot-data")
SPEND_SOURCE = "ask_probe"  # its name on MS4's spend counter
MAX_OUTPUT_TOKENS = 800  # spec 4.3
EFFORTS = ("minimal", "low")
RUNS = 10  # timings for each effort (plan Task 2, step 1)
MAX_RUNS = 10
COST_CAP_USD = Decimal("0.50")  # the tracker, Oct 30, 7:48 PM: 10 runs fit, inside C730
MIN_KEY_LENGTH = 20  # MetaClient's rule: the real key has 48 characters
# What a 400 must name to count as Meta refusing tools beside text.format (F4).
_F4_WORDS = re.compile(r"\b(text|format|tools|tool_choice)\b", re.IGNORECASE)
DEFAULT_PLACE = "Araneta Avenue cor. E. Rodriguez"
COST_GUARD_EXIT = 4
RESPONSE_TIMEOUT_S = 120.0  # a long timeout, so a slow call is a result, not an error
CANNED_REFS = ("r1", "r2", "d1")
TOOL = "get_reports"
OFF_TOPIC_TOOL = "not_about_flood_depth"


def _load_runner():
    """The offline runner, loaded from its file beside this one, as dev_eval.py does."""
    path = Path(__file__).resolve().with_name("run_pipeline.py")
    spec = importlib.util.spec_from_file_location("run_pipeline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()  # its sealed-path and data-in-repo guards, and say()


# --- the prompts and the request bodies --------------------------------------------


@dataclass(frozen=True)
class Prompts:
    """backend/api/prompts/ask_v1.*, read from disk as the API reads them."""

    instructions: str
    get_reports: dict
    not_about_flood_depth: dict
    answer_schema: dict


def load_prompts(folder: Path = PROMPTS) -> Prompts:
    def read(suffix: str) -> str:
        return (folder / f"{PROMPT_VERSION}{suffix}").read_text(encoding="utf-8")

    return Prompts(
        instructions=read(".md"),
        get_reports=json.loads(read(".tools.json")),
        not_about_flood_depth=json.loads(read(".offtopic.json")),
        answer_schema=json.loads(read(".answer.json")),
    )


def _user_message(question: str, shared: bool, *extra: str) -> dict:
    """One user message: the location line first (the prompt says so), then the
    question as the person typed it, then any `extra` text parts."""
    line = f"Location shared: {'yes' if shared else 'no'}"
    parts = [line, question, *extra]
    return {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": text} for text in parts],
    }


def _body(prompts: Prompts, effort: str, items: list[dict]) -> dict:
    """The fields every request carries: stateless, with reasoning carried as
    encrypted items (F2)."""
    if effort not in REASONING_EFFORTS:
        raise ValueError(f"reasoning effort {effort!r} isn't one Muse Spark takes")
    return {
        "model": SPARK_MODEL,
        "instructions": prompts.instructions,
        "input": items,
        "store": False,
        "include": ["reasoning.encrypted_content"],
        "reasoning": {"effort": effort},
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }


def _answer_format(prompts: Prompts) -> dict:
    """The `text` field that holds the answer schema in strict mode."""
    return {
        "text": {
            "format": {
                "type": "json_schema",
                "name": ANSWER_NAME,
                "schema": prompts.answer_schema,
                "strict": True,  # off by default at Meta
            }
        }
    }


def _with_tools(body: dict, tools: list[dict]) -> dict:
    """Meta takes only `auto` for tool_choice; one call a turn."""
    return body | {"tools": tools, "tool_choice": "auto", "parallel_tool_calls": False}


def build_turn1(
    prompts: Prompts, question: str, shared: bool, effort: str, form: str
) -> dict:
    """Turn 1's request. `schema`: get_reports and the answer schema in text.format.
    `tools_only`: get_reports and not_about_flood_depth, no text.format (spec 4.3)."""
    body = _body(prompts, effort, [_user_message(question, shared)])
    if form == "schema":
        return _with_tools(body, [prompts.get_reports]) | _answer_format(prompts)
    if form == "tools_only":
        return _with_tools(body, [prompts.get_reports, prompts.not_about_flood_depth])
    raise ValueError(f"turn 1 has no form {form!r}")


def build_turn2(
    prompts: Prompts,
    question: str,
    shared: bool,
    turn1_output: list[dict],
    tool_output: str,
    effort: str,
    form: str,
) -> dict:
    """The final turn's request. `replay` resends turn 1's reasoning items (each with
    a `summary`, [] when it came back with none), its function_call and a matching
    function_call_output (F2). `plain_input` sends no tools and the tool's output as
    input text, and keeps the schema."""
    if form == "plain_input":
        text = f"{TOOL} result:\n{tool_output}"
        body = _body(prompts, effort, [_user_message(question, shared, text)])
        return body | _answer_format(prompts)
    if form != "replay":
        raise ValueError(f"the final turn has no form {form!r}")
    items = [_user_message(question, shared)]
    for item in turn1_output:
        if item.get("type") == "reasoning":
            items.append({**item, "summary": item.get("summary") or []})
        elif item.get("type") == "function_call":
            items.append(item)
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": item["call_id"],
                    "output": tool_output,
                }
            )
    if not any(item["type"] == "function_call" for item in items):
        raise ValueError("turn 1 made no call to replay")
    body = _body(prompts, effort, items)
    return _with_tools(body, [prompts.get_reports]) | _answer_format(prompts)


def canned_tool_output(place: str = DEFAULT_PLACE) -> str:
    """Two live reports and one demo pin for `place`, the one the question names, as
    Task 8's toModelOutput shapes them: no coordinates and no report ids, only refs
    and distances."""
    return json.dumps(
        {
            "status": "ok",
            "place": place,
            "window_minutes": 180,
            "radius_m": 300,
            "count": 2,
            "reports": [
                {
                    "ref": "r1",
                    "level": "knee",
                    "level_is_floor": False,
                    "passability": "NPLV",
                    "minutes_ago": 14,
                    "distance_m": 42,
                },
                {
                    "ref": "r2",
                    "level": "half_tire",
                    "level_is_floor": False,
                    "passability": "NPLV",
                    "minutes_ago": 55,
                    "distance_m": 180,
                },
            ],
            "demo_reports": [
                {"ref": "d1", "level": "waist", "year": 2024, "distance_m": 210}
            ],
        },
        ensure_ascii=False,
    )


# --- the questions and the plan ------------------------------------------------------


@dataclass(frozen=True)
class Question:
    """A probe question (not Task 18's T1 to T10, which stay frozen), and what Meta
    should do with it. `expect` holds the arguments the get_reports call must have;
    None means the question is off-topic. `final` holds the kind and vehicle of the
    answer after the tool's output. `place` is the place the question names, which
    the canned tool output then answers for."""

    text: str
    shared: bool
    expect: dict | None
    place_word: str | None = None
    final: dict | None = None
    place: str = DEFAULT_PLACE


QUESTIONS = {
    "araneta": Question(
        "Gaano kataas ang tubig sa Araneta Avenue cor. E. Rodriguez ngayon?",
        False,
        {"here": False, "kind": "depth", "vehicle": "none"},
        "araneta",
        {"kind": "depth", "vehicle": "none"},
    ),
    "score": Question("Ano ang score ng laro kagabi?", False, None),
    "dito": Question("Baha ba malapit dito?", True, {"here": True}),
    "quezon": Question(
        "Kaya ba ng kotse ko sa Quezon Avenue?",
        False,
        {"here": False, "kind": "crossing", "vehicle": "light"},
        "quezon",
        {"kind": "crossing", "vehicle": "light"},
        "Quezon Avenue",
    ),
}


@dataclass(frozen=True)
class Job:
    """One question through one or two turns. `form2` None: turn 1 only."""

    step: str
    question: str
    effort: str
    form1: str
    form2: str | None
    run: int | None = None


def calls_of(job: Job) -> int:
    return 1 + (job.form2 is not None)


def main_jobs(runs: int) -> list[Job]:
    """Plan steps 1 to 4. Step 1 alternates the efforts, so a drifting network
    doesn't favour one."""
    jobs = [
        Job("1", "araneta", effort, "schema", "replay", n)
        for n in range(runs)
        for effort in EFFORTS
    ]
    return jobs + [
        Job("2", "score", "minimal", "schema", None),
        Job("3", "dito", "minimal", "schema", None),
        Job("4", "quezon", "minimal", "schema", "replay"),
    ]


def fallback_jobs() -> list[Job]:
    """Step 5: the other forms, once per question, when tools beside text.format
    return 400."""
    return [
        Job("5", "araneta", "minimal", "tools_only", "plain_input"),
        Job("5", "score", "minimal", "tools_only", None),
        Job("5", "quezon", "minimal", "tools_only", "plain_input"),
    ]


# What the dry run builds a final turn from, where there is no real turn 1 yet. The
# encrypted blob stands for the reasoning item, whose real size is not known.
_PLACEHOLDER_OUTPUT = [
    {"type": "reasoning", "id": "rs_0", "summary": [], "encrypted_content": "x" * 1500},
    {
        "type": "function_call",
        "id": "fc_0",
        "call_id": "call_0",
        "name": TOOL,
        "arguments": json.dumps(
            {
                "place": "Araneta Avenue cor. E. Rodriguez",
                "here": False,
                "since_minutes": 180,
                "kind": "depth",
                "vehicle": "none",
            }
        ),
        "status": "completed",
    },
]


def job_bodies(prompts: Prompts, job: Job) -> list[dict]:
    question = QUESTIONS[job.question]
    bodies = [
        build_turn1(prompts, question.text, question.shared, job.effort, job.form1)
    ]
    if job.form2 is not None:
        bodies.append(
            build_turn2(
                prompts,
                question.text,
                question.shared,
                _PLACEHOLDER_OUTPUT,
                canned_tool_output(question.place),
                job.effort,
                job.form2,
            )
        )
    return bodies


# --- the cost ------------------------------------------------------------------------


def estimate_cost(body: dict) -> Decimal:
    """A call's worst case before it is made. Input: the request body's UTF-8 byte
    count as tokens, since a token is never fewer than one byte of the text sent.
    Output: the whole max_output_tokens, which covers reasoning and the answer. The
    bound is on the bytes sent, so it leaves out Meta's own chat template and the
    reasoning behind a replayed encrypted_content."""
    sent = len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
    return cost_of(
        spark_input_tokens=sent, spark_output_tokens=body["max_output_tokens"]
    )


def estimate_plan(prompts: Prompts, jobs: Sequence[Job]) -> Decimal:
    return sum(
        (estimate_cost(body) for job in jobs for body in job_bodies(prompts, job)),
        Decimal(0),
    )


# --- the Meta client -----------------------------------------------------------------


@dataclass
class Reply:
    """One call's result. `status` is the HTTP status, or None for a lost connection
    or a timeout. `output` holds the response's output items as dicts."""

    status: int | None
    elapsed_s: float
    output: list[dict] = field(default_factory=list)
    text: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    response_status: str | None = None
    error: dict | None = None
    reconnected: bool = False  # the call opened a new connection, so its time has it


# httpcore's trace events for a new TCP connection (httpcore 1.0: "connect_tcp" in
# its connection module, under the "connection." prefix).
_CONNECT_EVENTS = frozenset(
    {"connection.connect_tcp.started", "connection.connect_unix_socket.started"}
)


class AskClient:
    """Muse Spark's Responses endpoint through one OpenAI client and one httpx
    client, so connections are kept. The SDK makes no retries of its own."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        timeout_s: float = RESPONSE_TIMEOUT_S,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._key = api_key
        self._connects = 0  # new connections opened, counted from httpcore's trace
        self._http = httpx.Client(
            transport=transport,
            timeout=timeout_s,
            limits=httpx.Limits(keepalive_expiry=120),
            event_hooks={"request": [self._watch_connections]},
        )
        self._openai = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=0,
            timeout=timeout_s,
            http_client=self._http,
        )

    def _watch_connections(self, request: httpx.Request) -> None:
        """Ask httpcore to report this request's connection events (its `trace`
        extension), and count each new TCP connection."""

        def trace(name: str, info: object) -> None:
            if name in _CONNECT_EVENTS:
                self._connects += 1

        request.extensions["trace"] = trace

    def warm_up(self) -> dict:
        """Open the connection with a request that holds no key and costs nothing, so
        the first call's time doesn't carry the connection setup (on the home Wi-Fi,
        about 21 s of IPv6 waiting). Any answer from the server will do."""
        started = time.monotonic()
        try:
            status = self._http.get(self._base_url).status_code
        except httpx.HTTPError:
            status = None
        return {
            "ok": status is not None,
            "status": status,
            "elapsed_s": round(time.monotonic() - started, 3),
        }

    def send(self, body: dict) -> Reply:
        """Make one call, once. An HTTP error, a lost connection and a 200 whose body
        can't be read are the call's result, not an exception."""
        connects = self._connects
        started = time.monotonic()
        try:
            response = self._openai.responses.create(**body)
        except openai.APIStatusError as exc:
            # A rejected key's message may echo part of the key, which no scrub of
            # the whole key would catch: keep nothing but the type and code then.
            rejected = exc.status_code in (401, 403)
            # The key is replaced before the message is cut, so a key that straddles
            # the cut can't leave its first part behind.
            message = str(exc.message).replace(self._key, "[key]")[:300]
            return Reply(
                exc.status_code,
                time.monotonic() - started,
                error={
                    "type": exc.type,
                    "code": exc.code,
                    "param": exc.param,
                    "message": "" if rejected else message,
                },
                reconnected=self._connects > connects,
            )
        except openai.APIConnectionError as exc:  # a timeout is one too
            return Reply(
                None,
                time.monotonic() - started,
                error={"type": type(exc).__name__, "message": "no answer"},
                reconnected=self._connects > connects,
            )
        elapsed = time.monotonic() - started
        reconnected = self._connects > connects
        tokens = _tokens(response)
        try:
            output = [
                item.model_dump(mode="json", exclude_none=True)
                for item in response.output
            ]
            text = response.output_text
            status = response.status
        except (AttributeError, TypeError, ValueError) as exc:
            # A 200 that isn't a Response (the SDK hands back the body's text when it
            # isn't JSON): it may have been billed, so it is a result, not a crash.
            return Reply(
                200,
                elapsed,
                input_tokens=tokens[0],
                output_tokens=tokens[1],
                reasoning_tokens=tokens[2],
                response_status="unreadable",
                error={"type": "UnreadableResponse", "message": type(exc).__name__},
                reconnected=reconnected,
            )
        return Reply(
            200,
            elapsed,
            output=output,
            text=text,
            input_tokens=tokens[0],
            output_tokens=tokens[1],
            reasoning_tokens=tokens[2],
            response_status=status,
            reconnected=reconnected,
        )


def _tokens(response: object) -> tuple[int | None, int | None, int | None]:
    """The input, output and reasoning tokens a response reports, None for any it
    doesn't (or for a body that has no usage to read)."""
    try:
        usage = response.usage
        details = usage.output_tokens_details if usage else None
        return (
            usage.input_tokens if usage else None,
            usage.output_tokens if usage else None,
            details.reasoning_tokens if details else None,
        )
    except (AttributeError, TypeError, ValueError):
        return None, None, None


# --- what a call's answer is checked against -----------------------------------------


def verdict(prompts: Prompts, question: Question, turn: int, reply: Reply) -> dict:
    """The calls and the answer in a reply, and whether they are what the plan
    expects of this question. `why` lists what was not."""
    calls = []
    for item in reply.output:
        if item.get("type") == "function_call":
            try:
                args = json.loads(item.get("arguments") or "")
            except json.JSONDecodeError:
                args = None
            calls.append({"name": item.get("name"), "args": args})
    try:
        answer = json.loads(reply.text) if reply.text else None
    except json.JSONDecodeError:
        answer = None
    why: list[str] = []
    if reply.status != 200:
        why.append(f"no answer (status {reply.status})")
    elif reply.response_status not in (None, "completed"):
        why.append(f"response {reply.response_status}")
    elif turn == 1:
        why += _turn1_problems(prompts, question, calls, answer)
    else:
        why += _final_problems(prompts, question, calls, answer)
    return {"calls": calls, "answer": answer, "right": not why, "why": why}


def _answer_problems(prompts: Prompts, answer: dict | None) -> list[str]:
    if not isinstance(answer, dict):
        return ["no JSON answer"]
    errors = Draft202012Validator(prompts.answer_schema).iter_errors(answer)
    return [f"answer: {e.message}" for e in errors]


def _turn1_problems(
    prompts: Prompts, question: Question, calls: list[dict], answer: dict | None
) -> list[str]:
    gets = [c for c in calls if c["name"] == TOOL]
    if question.expect is None:  # off-topic: an answer or the second tool, no lookup
        if gets:
            return [f"called {TOOL}"]
        if any(c["name"] == OFF_TOPIC_TOOL for c in calls):
            return []
        problems = _answer_problems(prompts, answer)
        if not problems and answer["kind"] != "off_topic":
            problems.append(f"kind {answer['kind']}, wanted off_topic")
        return problems
    if len(gets) != 1 or len(calls) != 1:
        return [f"{len(calls)} calls, {len(gets)} to {TOOL}"]
    args = gets[0]["args"]
    if not isinstance(args, dict):
        return ["arguments aren't JSON"]
    parameters = prompts.get_reports["parameters"]
    problems = [
        f"args: {e.message}" for e in Draft202012Validator(parameters).iter_errors(args)
    ]
    if problems:
        return problems
    for name, wanted in question.expect.items():
        if args[name] != wanted:
            problems.append(f"{name} {args[name]!r}, wanted {wanted!r}")
    if not 1 <= args["since_minutes"] <= 180:
        problems.append(f"since_minutes {args['since_minutes']} outside 1 to 180")
    if question.place_word and question.place_word not in args["place"].casefold():
        problems.append(f"place {args['place']!r} lacks {question.place_word!r}")
    return problems


def _final_problems(
    prompts: Prompts, question: Question, calls: list[dict], answer: dict | None
) -> list[str]:
    problems = [f"called {c['name']} again" for c in calls]
    problems += _answer_problems(prompts, answer)
    if problems or question.final is None:
        return problems
    for name, wanted in question.final.items():
        if answer[name] != wanted:
            problems.append(f"{name} {answer[name]!r}, wanted {wanted!r}")
    cited = answer["cited"]
    if "r1" not in cited:
        problems.append("r1, the deepest, isn't cited")
    if not set(cited) <= set(CANNED_REFS):
        problems.append("cites a ref the tool never gave")
    return problems


# --- the run -------------------------------------------------------------------------


class CostGuard(Exception):
    """The next call's worst case would take the estimated cost past the cap."""


class Output:
    """What the run writes, with the key replaced by "[key]" in every line."""

    def __init__(self, folder: Path, key: str) -> None:
        self.folder = folder
        self._key = key
        self.calls = folder / "ask_calls.jsonl"
        self.summary = folder / "ask_summary.json"

    def clean(self, text: str) -> str:
        return text.replace(self._key, "[key]") if self._key else text

    def say(self, line: str) -> None:
        runner.say(self.clean(line))

    def log_call(self, row: dict) -> None:
        line = self.clean(json.dumps(row, ensure_ascii=False))
        with self.calls.open("a", encoding="utf-8") as log:
            log.write(line + "\n")

    def write_summary(self, summary: dict) -> None:
        text = self.clean(json.dumps(summary, indent=2, ensure_ascii=False))
        self.summary.write_text(text, encoding="utf-8")


class Run:
    """The calls made so far, what they may have cost, and the guard on the next."""

    def __init__(self, client, prompts: Prompts, out: Output) -> None:
        self.client = client
        self.prompts = prompts
        self.out = out
        self.cold = False  # True: the connection wasn't warm, the first call carries it
        self.rows: list[dict] = []
        self.tokens = {"input": 0, "output": 0, "reasoning": 0}
        self.billed = [0, 0]  # input and output tokens that may have been billed

    @property
    def spent(self) -> Decimal:
        return cost_of(
            spark_input_tokens=self.billed[0], spark_output_tokens=self.billed[1]
        )

    def send(self, job: Job, turn: int, form: str, body: dict) -> Reply:
        """One call, once, after the guard. Whatever ends it, the call is charged
        and logged: one that raises (Ctrl+C included) may have been billed."""
        if self.spent + estimate_cost(body) > COST_CAP_USD:
            raise CostGuard
        started = time.monotonic()
        try:
            reply = self.client.send(body)
        except BaseException as exc:
            error = {"type": type(exc).__name__, "message": "the call raised"}
            self._record(
                job, turn, form, Reply(None, time.monotonic() - started, error=error)
            )
            raise
        self._record(job, turn, form, reply)
        return reply

    def _record(self, job: Job, turn: int, form: str, reply: Reply) -> None:
        # The cost first, so nothing after it can lose it.
        if reply.status is None or reply.status == 200:
            # Meta's HTTP error answers aren't billed. A timeout or a lost
            # connection may have been, and a missing count is charged at the
            # unreported rate, so the count runs over, never under.
            reported = (reply.input_tokens, reply.output_tokens)
            for n, (got, fallback) in enumerate(
                zip(reported, SPARK_TOKENS_IF_UNREPORTED, strict=True)
            ):
                self.billed[n] += fallback if got is None else got
        for name, value in (
            ("input", reply.input_tokens),
            ("output", reply.output_tokens),
            ("reasoning", reply.reasoning_tokens),
        ):
            self.tokens[name] += value or 0
        question = QUESTIONS[job.question]
        row = {
            "n": len(self.rows) + 1,
            "step": job.step,
            "question": job.question,
            "run": job.run,
            "effort": job.effort,
            "turn": turn,
            "form": form,
            "status": reply.status,
            "elapsed_s": round(reply.elapsed_s, 3),
            "includes_connect": self.cold and not self.rows,
            "reconnected": reply.reconnected,
            "response_status": reply.response_status,
            "input_tokens": reply.input_tokens,
            "output_tokens": reply.output_tokens,
            "reasoning_tokens": reply.reasoning_tokens,
            "error": reply.error,
            "verdict": verdict(self.prompts, question, turn, reply),
        }
        self.rows.append(row)
        self.out.log_call(row)
        self.out.say(_line(row))

    def do(self, job: Job) -> None:
        """One job: turn 1, then turn 2 if turn 1 called get_reports. A 400 or any
        other answer without that call ends the job."""
        question = QUESTIONS[job.question]
        first = self.send(
            job,
            1,
            job.form1,
            build_turn1(
                self.prompts, question.text, question.shared, job.effort, job.form1
            ),
        )
        called = any(
            item.get("type") == "function_call" and item.get("name") == TOOL
            for item in first.output
        )
        if job.form2 is None or not called:
            return
        body = build_turn2(
            self.prompts,
            question.text,
            question.shared,
            first.output,
            canned_tool_output(question.place),
            job.effort,
            job.form2,
        )
        self.send(job, 2, job.form2, body)

    def refusals(self) -> dict:
        """The 400s so far. Step 5 starts only on a 400 to tools beside text.format
        whose error names text, format, tools or tool_choice (F4); any other 400 is
        listed, with its param and code, and starts nothing."""
        f4, other = [], []
        for row in self.rows:
            if row["status"] != 400:
                continue
            if row["form"] in ("schema", "replay") and concerns_f4(row["error"]):
                f4.append(row)
            else:
                error = row["error"] or {}
                other.append(
                    {
                        "n": row["n"],
                        "question": row["question"],
                        "turn": row["turn"],
                        "form": row["form"],
                        "param": error.get("param"),
                        "code": error.get("code"),
                    }
                )
        return {
            "schema_400s": len(f4),
            "forms": dict(Counter(row["form"] for row in f4)),
            "other_400s": other,
        }


def concerns_f4(error: dict | None) -> bool:
    """Whether an error's param, code or message names text, format, tools or
    tool_choice, as a 400 to tools beside text.format would (F4)."""
    error = error or {}
    named = " ".join(
        str(error.get(field) or "") for field in ("param", "code", "message")
    )
    return bool(_F4_WORDS.search(named))


def _line(row: dict) -> str:
    """One call's stdout line: the step, effort, turn, status, time and tokens."""
    verdict_ = "as expected" if row["verdict"]["right"] else "NOT as expected"
    tokens = (
        f"{row['input_tokens']} in, {row['output_tokens']} out"
        if row["input_tokens"] is not None
        else "no usage"
    )
    if row["includes_connect"]:
        note = ", with the connection"
    elif row["reconnected"]:
        note = ", on a new connection"
    else:
        note = ""
    return (
        f"call {row['n']}: step {row['step']} {row['question']} {row['effort']} "
        f"turn {row['turn']} {row['form']}: status {row['status']} in "
        f"{row['elapsed_s']} s ({tokens}){note}, {verdict_}"
    )


def stats(times: list[float]) -> dict:
    """The count, median and longest of some timings."""
    if not times:
        return {"calls": 0}
    return {
        "calls": len(times),
        "p50_s": round(statistics.median(times), 3),
        "max_s": round(max(times), 3),
    }


def effort_summary(rows: list[dict], effort: str) -> dict:
    """Step 1's rows at one effort: timings per turn and per two-turn run, tokens, and
    what was right. A call that carried a connection setup (the first, if the warm-up
    failed, or one that opened a new connection) is left out of every timing, and
    `left_out` says how many were."""
    mine = [r for r in rows if r["step"] == "1" and r["effort"] == effort]
    answered = [r for r in mine if r["status"] == 200]
    marked = [r for r in answered if r["includes_connect"] or r["reconnected"]]
    timed = {
        turn: {r["run"]: r for r in answered if r["turn"] == turn and r not in marked}
        for turn in (1, 2)
    }
    both = [
        timed[1][n]["elapsed_s"] + timed[2][n]["elapsed_s"]
        for n in timed[1]
        if n in timed[2]
    ]
    turn1 = [r for r in mine if r["turn"] == 1]
    turn2 = [r for r in mine if r["turn"] == 2]
    return {
        "statuses": dict(Counter(str(r["status"]) for r in mine)),
        "turn1": stats([r["elapsed_s"] for r in timed[1].values()]),
        "turn2": stats([r["elapsed_s"] for r in timed[2].values()]),
        "two_turn": stats([round(t, 3) for t in both]),
        "left_out": len(marked),
        "tool_call_right": f"{sum(r['verdict']['right'] for r in turn1)}/{len(turn1)}",
        "final_right": f"{sum(r['verdict']['right'] for r in turn2)}/{len(turn2)}",
        "input_tokens": sum(r["input_tokens"] or 0 for r in mine),
        "output_tokens": sum(r["output_tokens"] or 0 for r in mine),
        "reasoning_tokens": sum(r["reasoning_tokens"] or 0 for r in mine),
    }


def summarize(
    run: Run,
    runs: int,
    warm: dict,
    started: datetime,
    clock: float,
    stopped: str | None,
    step5: dict,
) -> dict:
    """The summary. `stopped` says how the run ended early: "cost_guard", or the
    class name of the exception that ended it; None when every step ran."""
    return {
        "started": started.isoformat(timespec="seconds"),
        "run_s": round(time.monotonic() - clock, 1),
        "prompt_version": PROMPT_VERSION,
        "model": SPARK_MODEL,
        "runs": runs,
        "connect": warm,
        "calls": len(run.rows),
        "reconnected_calls": sum(bool(r["reconnected"]) for r in run.rows),
        "stopped": stopped,
        "cost_cap_usd": str(COST_CAP_USD),
        "estimated_cost_usd": str(run.spent),
        "tokens": run.tokens,
        "step5": step5,
        "efforts": {effort: effort_summary(run.rows, effort) for effort in EFFORTS},
        "checks": [
            {
                key: row[key]
                for key in ("n", "step", "question", "turn", "effort", "form")
            }
            | {
                "status": row["status"],
                "elapsed_s": row["elapsed_s"],
                "right": row["verdict"]["right"],
                "why": row["verdict"]["why"],
                "error": row["error"],
            }
            for row in run.rows
            if row["step"] != "1"
        ],
    }


def _run(run: Run, runs: int) -> int:
    """The paid part: steps 1 to 4, then 5 if tools beside text.format were refused.
    The summary is written however the steps end, an exception or Ctrl+C included
    (which then go on), and says how. Returns the exit code."""
    out = run.out
    out.folder.mkdir(parents=True, exist_ok=True)
    started = datetime.now().astimezone()
    clock = time.monotonic()
    warm = run.client.warm_up()
    run.cold = not warm["ok"]
    out.say(
        f"connection: {'ready' if warm['ok'] else 'not opened'} in {warm['elapsed_s']} s"
    )
    step5 = {"ran": False, "schema_400s": 0, "forms": {}, "other_400s": []}
    stopped = None
    try:
        for job in main_jobs(runs):
            run.do(job)
        if run.refusals()["schema_400s"]:
            step5["ran"] = True
            for job in fallback_jobs():
                run.do(job)
    except CostGuard:
        stopped = "cost_guard"
        out.say(f"stopped before the next call: its worst case passes ${COST_CAP_USD}")
    except BaseException as exc:
        stopped = type(exc).__name__
        raise
    finally:
        step5 |= run.refusals()
        summary = summarize(run, runs, warm, started, clock, stopped, step5)
        out.write_summary(summary)
        out.say(
            f"done in {summary['run_s']} s: {summary['calls']} calls, tokens "
            f"{json.dumps(run.tokens)}, estimated ${run.spent:.4f} of ${COST_CAP_USD}"
            + (f", ended by {stopped}" if stopped else "")
        )
    return COST_GUARD_EXIT if stopped else 0


def most_runs_that_fit(prompts: Prompts) -> int:
    """The largest --runs whose main plan's worst case fits the cap; 0 if none."""
    for runs in range(MAX_RUNS, 0, -1):
        if estimate_plan(prompts, main_jobs(runs)) <= COST_CAP_USD:
            return runs
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    make_client: Callable[[str], object] = AskClient,
) -> int:
    """The probe. `make_client` is for tests: AskClient, given MODEL_API_KEY's key."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yes", action="store_true", help="spend the credits")
    parser.add_argument(
        "--runs",
        type=int,
        choices=range(1, MAX_RUNS + 1),
        default=RUNS,
        metavar=f"1..{MAX_RUNS}",
        help="timings per effort",
    )
    args = parser.parse_args(argv)
    out_folder = DATA / "probes" / date.today().isoformat() / "ask"
    # Before anything is opened or made: a sealed path, or a data folder in the repo.
    runner.refuse_sealed(DATA, out_folder)
    runner.refuse_data_in_repo(DATA)

    key = os.environ.get("MODEL_API_KEY", "")
    out = Output(out_folder, key)
    if (
        args.yes
    ):  # a dry run makes nothing, so it needs neither the key nor a clear folder
        if len(key) < MIN_KEY_LENGTH:
            runner.say("refused: MODEL_API_KEY is missing or too short")
            raise SystemExit(2)
        if out.summary.exists() or out.calls.exists():
            runner.say(f"refused: {out.folder} already holds a run: move it aside")
            raise SystemExit(2)

    prompts = load_prompts()
    main_plan, fallback = main_jobs(args.runs), fallback_jobs()
    n_main = sum(calls_of(job) for job in main_plan)
    n_all = n_main + sum(calls_of(job) for job in fallback)
    estimate = estimate_plan(prompts, main_plan)
    estimate_all = estimate_plan(prompts, main_plan + fallback)
    print(
        f"planned: {n_main} calls to {SPARK_MODEL} ({n_all} with step 5's other forms),"
        f" worst case ${estimate:.4f} (${estimate_all:.4f} with step 5), against the"
        f" ${COST_CAP_USD} cap. The worst case counts the request's bytes as input"
        f" tokens and the full {MAX_OUTPUT_TOKENS} output tokens; real calls use far less.",
        flush=True,
    )
    over = estimate > COST_CAP_USD
    if over:
        print(
            f"the main plan's worst case passes the cap: --yes would refuse it. The most"
            f" --runs that fits is {most_runs_that_fit(prompts) or 'none'}.",
            flush=True,
        )
    if not args.yes:
        print("add --yes to run it", flush=True)
        return 0
    if over:
        runner.say("refused: the plan's worst case passes the cap; lower --runs")
        return COST_GUARD_EXIT

    spend = check_before_paying()  # MS4's counter, before any client (C527)
    run = Run(make_client(key), prompts, out)  # one client, so connections are kept
    try:
        return _run(run, args.runs)
    finally:  # the whole run's cost, once, however it ends (R126)
        spend.record_after(run.spent, SPEND_SOURCE)


if __name__ == "__main__":
    raise SystemExit(main())
