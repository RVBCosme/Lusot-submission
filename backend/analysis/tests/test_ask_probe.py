"""Tests for Ask Lusot's probe, probes/ask_probe.py (plan Task 2, spec C731).

The probe isn't a package module, so it is loaded from its file. The data folder is a
synthetic one under tmp_path, a scripted fake stands in for Meta, and a FakeSpend for
MS4's counter, so no test reaches Meta, AWS or lusot-data. AskClient's own tests use
an httpx mock transport, which never leaves the process.
"""

import importlib.util
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fakes import FakeSpend

from lusot_analysis.meta_client import BASE_URL, SPARK_MODEL
from lusot_analysis.spend import SPARK_TOKENS_IF_UNREPORTED, cost_of

PROBE = Path(__file__).parents[1] / "probes" / "ask_probe.py"
PROMPT_DIR = Path(__file__).parents[3] / "backend" / "api" / "prompts"
KEY = "sentinel-" * 4  # low entropy on purpose: gitleaks would flag a random one


def load_probe():
    spec = importlib.util.spec_from_file_location("ask_probe_script", PROBE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ask_probe_script"] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


probe = load_probe()
PROMPTS = probe.load_prompts()
QUESTION = "Gaano kataas ang tubig sa Araneta Avenue cor. E. Rodriguez ngayon?"


def reasoning_item(n=1, summary=None):
    item = {"type": "reasoning", "id": f"rs_{n}", "encrypted_content": f"ENC{n}"}
    if summary is not None:
        item["summary"] = summary
    return item


def call_item(name="get_reports", args=None, n=1):
    return {
        "type": "function_call",
        "id": f"fc_{n}",
        "call_id": f"call_{n}",
        "name": name,
        "arguments": json.dumps(args or {}),
        "status": "completed",
    }


def message_items(text):
    part = {"type": "output_text", "text": text, "annotations": []}
    return [
        {
            "type": "message",
            "id": "msg_1",
            "role": "assistant",
            "status": "completed",
            "content": [part],
        }
    ]


TURN1_OUTPUT = [
    reasoning_item(1, [{"type": "summary_text", "text": "thinking"}]),
    reasoning_item(2),  # a reasoning item that came back with no summary
    call_item(args={"place": "x"}),
]


# --- the request bodies ---------------------------------------------------------


def all_bodies(question=QUESTION, shared=False, effort="minimal"):
    tool_output = probe.canned_tool_output()
    return [
        probe.build_turn1(PROMPTS, question, shared, effort, "schema"),
        probe.build_turn1(PROMPTS, question, shared, effort, "tools_only"),
        probe.build_turn2(
            PROMPTS, question, shared, TURN1_OUTPUT, tool_output, effort, "replay"
        ),
        probe.build_turn2(
            PROMPTS, question, shared, TURN1_OUTPUT, tool_output, effort, "plain_input"
        ),
    ]


def test_every_body_sends_store_false_and_the_reasoning_include():
    for body in all_bodies():
        assert body["store"] is False
        assert body["include"] == ["reasoning.encrypted_content"]


def test_every_body_names_the_model_the_effort_and_the_spec_limits():
    for effort in ("minimal", "low"):
        for body in all_bodies(effort=effort):
            assert body["model"] == SPARK_MODEL == "muse-spark-1.3"
            assert body["reasoning"] == {"effort": effort}
            assert body["max_output_tokens"] == 800
            assert body["instructions"] == PROMPTS.instructions


def test_the_prompts_are_the_files_on_disk():
    on_disk = PROMPT_DIR / "ask_v1.md"
    assert PROMPTS.instructions == on_disk.read_text(encoding="utf-8")
    tools = json.loads((PROMPT_DIR / "ask_v1.tools.json").read_text(encoding="utf-8"))
    assert PROMPTS.get_reports == tools
    off = json.loads((PROMPT_DIR / "ask_v1.offtopic.json").read_text(encoding="utf-8"))
    assert PROMPTS.not_about_flood_depth == off
    answer = (PROMPT_DIR / "ask_v1.answer.json").read_text(encoding="utf-8")
    assert PROMPTS.answer_schema == json.loads(answer)
    assert probe.PROMPTS == PROMPT_DIR


def test_turn_1_input_is_one_message_with_the_location_line_first():
    for shared, line in (
        (True, "Location shared: yes"),
        (False, "Location shared: no"),
    ):
        body = probe.build_turn1(PROMPTS, QUESTION, shared, "minimal", "schema")
        (message,) = body["input"]
        assert message["role"] == "user"
        texts = [part["text"] for part in message["content"]]
        assert texts == [line, QUESTION]
        assert {part["type"] for part in message["content"]} == {"input_text"}


def test_the_replay_turns_function_call_output_matches_the_calls_call_id():
    tool_output = probe.canned_tool_output()
    body = probe.build_turn2(
        PROMPTS, QUESTION, False, TURN1_OUTPUT, tool_output, "minimal", "replay"
    )
    items = body["input"]
    (call,) = [i for i in items if i["type"] == "function_call"]
    (result,) = [i for i in items if i["type"] == "function_call_output"]
    assert result["call_id"] == call["call_id"] == "call_1"
    assert result["output"] == tool_output
    # The result follows the call it answers, and the question comes first.
    assert items.index(result) == items.index(call) + 1
    assert items[0]["type"] == "message"


def test_each_replayed_reasoning_item_keeps_its_summary():
    body = probe.build_turn2(
        PROMPTS, QUESTION, False, TURN1_OUTPUT, "{}", "minimal", "replay"
    )
    replayed = [i for i in body["input"] if i["type"] == "reasoning"]
    assert [i["id"] for i in replayed] == ["rs_1", "rs_2"]
    assert replayed[0]["summary"] == [{"type": "summary_text", "text": "thinking"}]
    assert replayed[1]["summary"] == []  # Meta needs the field on every replay
    assert [i["encrypted_content"] for i in replayed] == ["ENC1", "ENC2"]
    # Replaying must not change the turn 1 output it was built from.
    assert "summary" not in TURN1_OUTPUT[1]


def test_a_replay_with_no_call_in_turn_1_is_refused():
    with pytest.raises(ValueError):
        probe.build_turn2(
            PROMPTS, QUESTION, False, [reasoning_item()], "{}", "minimal", "replay"
        )


def test_plain_input_sends_no_tools():
    tool_output = probe.canned_tool_output()
    body = probe.build_turn2(
        PROMPTS, QUESTION, False, TURN1_OUTPUT, tool_output, "minimal", "plain_input"
    )
    for field in ("tools", "tool_choice", "parallel_tool_calls"):
        assert field not in body
    texts = [part["text"] for item in body["input"] for part in item.get("content", [])]
    assert tool_output in "\n".join(texts)
    assert QUESTION in texts
    assert not any(i.get("type", "").startswith("function") for i in body["input"])
    assert body["text"]["format"]["schema"] == PROMPTS.answer_schema  # F4 keeps it


def test_tools_only_sends_both_tools_and_no_text_format():
    body = probe.build_turn1(PROMPTS, QUESTION, False, "minimal", "tools_only")
    names = [tool["name"] for tool in body["tools"]]
    assert names == ["get_reports", "not_about_flood_depth"]
    assert "text" not in body
    assert body["tool_choice"] == "auto"
    assert body["parallel_tool_calls"] is False


def test_schema_sends_one_tool_and_the_strict_schema():
    body = probe.build_turn1(PROMPTS, QUESTION, False, "minimal", "schema")
    assert [tool["name"] for tool in body["tools"]] == ["get_reports"]
    assert body["text"] == {
        "format": {
            "type": "json_schema",
            "name": "ask_answer_v1",
            "schema": PROMPTS.answer_schema,
            "strict": True,
        }
    }
    assert body["tool_choice"] == "auto"
    assert body["parallel_tool_calls"] is False


def test_the_replay_turn_keeps_the_one_tool_and_the_schema():
    body = probe.build_turn2(
        PROMPTS, QUESTION, False, TURN1_OUTPUT, "{}", "minimal", "replay"
    )
    assert [tool["name"] for tool in body["tools"]] == ["get_reports"]
    assert body["text"]["format"]["strict"] is True


def test_a_bad_effort_or_form_is_refused_before_any_body():
    with pytest.raises(ValueError):
        probe.build_turn1(PROMPTS, QUESTION, False, "none", "schema")
    with pytest.raises(ValueError):
        probe.build_turn1(PROMPTS, QUESTION, False, "minimal", "replay")
    with pytest.raises(ValueError):
        probe.build_turn2(PROMPTS, QUESTION, False, TURN1_OUTPUT, "{}", "low", "schema")


def test_the_canned_tool_output_has_two_live_reports_and_a_demo_pin():
    output = json.loads(probe.canned_tool_output())
    assert set(output) == {
        "status",
        "place",
        "window_minutes",
        "radius_m",
        "count",
        "reports",
        "demo_reports",
    }
    assert output["status"] == "ok"
    assert output["radius_m"] == 300
    assert [r["ref"] for r in output["reports"]] == ["r1", "r2"]
    assert [r["ref"] for r in output["demo_reports"]] == ["d1"]
    assert output["count"] == 2
    assert set(output["reports"][0]) == {
        "ref",
        "level",
        "level_is_floor",
        "passability",
        "minutes_ago",
        "distance_m",
    }
    assert set(output["demo_reports"][0]) == {"ref", "level", "year", "distance_m"}
    text = probe.canned_tool_output()
    for forbidden in ("lat", "lng", '"id"', "reportId"):
        assert forbidden not in text


def test_the_estimate_prices_the_input_and_the_full_output_cap():
    body = probe.build_turn1(PROMPTS, QUESTION, False, "minimal", "schema")
    chars = len(json.dumps(body, ensure_ascii=False))
    expected = cost_of(
        spark_input_tokens=-(-chars // probe.CHARS_PER_TOKEN),
        spark_output_tokens=800,
    )
    assert probe.estimate_cost(body) == expected


# --- AskClient: one call, once -------------------------------------------------


def responses_json(output, usage=True, status="completed"):
    body = {
        "id": "resp_1",
        "object": "response",
        "created_at": 1,
        "model": SPARK_MODEL,
        "status": status,
        "output": output,
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
    }
    if usage:
        body["usage"] = {
            "input_tokens": 910,
            "output_tokens": 46,
            "total_tokens": 956,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 12},
        }
    return body


def client_with(handler):
    return probe.AskClient(KEY, transport=httpx.MockTransport(handler), timeout_s=5)


def test_a_completed_call_gives_its_items_text_and_usage():
    seen = []

    def handler(request):
        seen.append(request)
        output = [reasoning_item(1, []), call_item(args={"place": "x"})]
        return httpx.Response(200, json=responses_json(output))

    client = client_with(handler)
    body = probe.build_turn1(PROMPTS, QUESTION, False, "minimal", "schema")
    reply = client.send(body)
    assert reply.status == 200
    assert reply.response_status == "completed"
    assert [i["type"] for i in reply.output] == ["reasoning", "function_call"]
    assert reply.output[0]["summary"] == []
    assert reply.output[1]["call_id"] == "call_1"
    assert (reply.input_tokens, reply.output_tokens) == (910, 46)
    assert reply.reasoning_tokens == 12
    assert reply.elapsed_s >= 0
    (request,) = seen
    assert request.url.path.endswith("/responses")
    sent = json.loads(request.content)
    assert sent["store"] is False
    assert sent["include"] == ["reasoning.encrypted_content"]
    assert request.headers["authorization"] == f"Bearer {KEY}"


def test_the_output_text_comes_from_the_message_item():
    def handler(request):
        text = '{"kind":"off_topic","vehicle":"none","cited":[]}'
        return httpx.Response(200, json=responses_json(message_items(text)))

    reply = client_with(handler).send(
        probe.build_turn1(PROMPTS, QUESTION, False, "minimal", "schema")
    )
    assert json.loads(reply.text)["kind"] == "off_topic"
    assert reply.output[0]["type"] == "message"


@pytest.mark.parametrize("status", [400, 429, 500, 503, 504])
def test_an_error_status_is_recorded_as_the_calls_result_and_never_retried(status):
    seen = []

    def handler(request):
        seen.append(request)
        error = {"message": f"nope {KEY}", "type": "bad", "param": "text", "code": "c"}
        return httpx.Response(
            status, json={"error": error}, headers={"retry-after": "0"}
        )

    reply = client_with(handler).send(
        probe.build_turn1(PROMPTS, QUESTION, False, "minimal", "schema")
    )
    assert len(seen) == 1  # the SDK's own retries are off
    assert reply.status == status
    assert reply.output == []
    assert reply.error["param"] == "text"
    assert reply.error["code"] == "c"


@pytest.mark.parametrize("status", [401, 403])
def test_a_rejected_keys_message_is_not_kept(status):
    def handler(request):
        message = f"Invalid key {KEY[:12]}...{KEY[-4:]}"
        return httpx.Response(
            status, json={"error": {"message": message, "type": "auth"}}
        )

    reply = client_with(handler).send(
        probe.build_turn1(PROMPTS, QUESTION, False, "minimal", "schema")
    )
    assert reply.status == status
    assert reply.error["message"] == ""
    assert KEY[:12] not in json.dumps(reply.error)


def test_a_lost_connection_is_a_call_with_no_status():
    def handler(request):
        raise httpx.ConnectError("no route", request=request)

    reply = client_with(handler).send(
        probe.build_turn1(PROMPTS, QUESTION, False, "minimal", "schema")
    )
    assert reply.status is None
    assert reply.error["type"] == "APIConnectionError"


def test_warm_up_sends_no_key_and_reports_the_connection_time():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(404, text="not found")

    warm = client_with(handler).warm_up()
    assert warm["ok"] is True
    assert warm["status"] == 404
    assert warm["elapsed_s"] >= 0
    assert "authorization" not in seen[0].headers
    assert str(seen[0].url).rstrip("/") == BASE_URL


def test_warm_up_that_fails_is_reported_not_raised():
    def handler(request):
        raise httpx.ConnectError("no route", request=request)

    warm = client_with(handler).warm_up()
    assert warm == {"ok": False, "status": None, "elapsed_s": warm["elapsed_s"]}


# --- main: the run ---------------------------------------------------------------


class ScriptedMeta:
    """Stands in for AskClient: answers each body as Meta might, and keeps them all."""

    def __init__(self, handler=None, warm_ok=True):
        self.bodies = []
        self.handler = handler or self.default
        self.warm_ok = warm_ok
        self.warmed = 0

    def warm_up(self):
        self.warmed += 1
        return {"ok": self.warm_ok, "status": 404, "elapsed_s": 0.05}

    def send(self, body):
        self.bodies.append(body)
        return self.handler(body)

    @staticmethod
    def question(body):
        return body["input"][0]["content"][1]["text"]

    @staticmethod
    def final(body):
        outputs = [i for i in body["input"] if i.get("type") == "function_call_output"]
        return bool(outputs) or "tools" not in body

    @staticmethod
    def reply(output=(), text="", **fields):
        values = {
            "status": 200,
            "elapsed_s": 0.5,
            "output": list(output),
            "text": text,
            "input_tokens": 900,
            "output_tokens": 60,
            "reasoning_tokens": 10,
            "response_status": "completed",
        }
        return probe.Reply(**(values | fields))

    @classmethod
    def answer(cls, kind, vehicle, cited=("r1", "r2")):
        answer = {"kind": kind, "vehicle": vehicle, "cited": list(cited)}
        return cls.reply(message_items(json.dumps(answer)), json.dumps(answer))

    def default(self, body):
        text = self.question(body)
        if "laro" in text:  # the off-topic question
            if "text" in body:
                return self.answer("off_topic", "none", [])
            return self.reply([reasoning_item(), call_item("not_about_flood_depth")])
        crossing = "Quezon" in text
        if self.final(body):
            return self.answer(
                "crossing" if crossing else "depth", "light" if crossing else "none"
            )
        args = {
            "place": "Quezon Avenue"
            if crossing
            else "Araneta Avenue cor. E. Rodriguez",
            "here": False,
            "since_minutes": 180,
            "kind": "crossing" if crossing else "depth",
            "vehicle": "light" if crossing else "none",
        }
        if "dito" in text:
            args |= {"place": "", "here": True}
        return self.reply([reasoning_item(1, []), call_item(args=args)])


@pytest.fixture
def data(tmp_path, monkeypatch):
    """The data folder under tmp_path, today's ask folder in it, and a key."""
    folder = tmp_path / "data"
    monkeypatch.setattr(probe, "DATA", folder)
    monkeypatch.setenv("MODEL_API_KEY", KEY)
    return folder / "probes" / date.today().isoformat() / "ask"


@pytest.fixture
def go(monkeypatch):
    """probe.main with a fake as the client and the counter. It returns the exit
    code, the fake, the FakeSpend and the order of check, client and record."""

    def run(argv, meta=None, spend=None):
        events = []
        meta = meta or ScriptedMeta()
        spend = spend or FakeSpend(on_record=lambda: events.append("record"))

        def check():
            events.append("check")
            return spend

        def make(key):
            events.append("client")
            assert key == KEY
            return meta

        monkeypatch.setattr(probe, "check_before_paying", check)
        code = probe.main(argv, make_client=make)
        return code, meta, spend, events

    return run


def calls_log(folder):
    lines = (folder / "ask_calls.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def summary_of(folder):
    return json.loads((folder / "ask_summary.json").read_text(encoding="utf-8"))


def test_without_yes_it_prints_the_plan_and_makes_no_call(
    data, go, capsys, monkeypatch
):
    monkeypatch.delenv("MODEL_API_KEY")  # a dry run needs no key
    code, _meta, _spend, events = go([])
    out = capsys.readouterr().out
    assert code == 0
    assert events == []  # no counter read, no client built
    assert not data.exists()  # nothing written
    assert "44 calls" in out
    assert "49 with" in out  # with step 5's fallback
    assert "$0.30" in out
    assert "--yes" in out


def test_the_plan_is_44_calls_and_5_more_and_its_worst_case_fits_the_cap():
    prompts = probe.load_prompts()
    main, fallback = probe.main_jobs(10), probe.fallback_jobs()
    assert sum(probe.calls_of(job) for job in main) == 44
    assert sum(probe.calls_of(job) for job in fallback) == 5
    assert probe.estimate_plan(prompts, main + fallback) < probe.COST_CAP_USD


def test_a_missing_or_short_key_refuses_and_prints_only_that(
    data, go, capsys, monkeypatch
):
    for value in (None, "tiny"):
        if value is None:
            monkeypatch.delenv("MODEL_API_KEY")
        else:
            monkeypatch.setenv("MODEL_API_KEY", value)
        with pytest.raises(SystemExit) as exit_:
            go(["--yes"])
        assert exit_.value.code == 2
        seen = capsys.readouterr()
        assert seen.out.strip() == "refused: MODEL_API_KEY is missing or too short"
        assert seen.err == ""
        assert not data.exists()


def test_a_refusal_reads_no_counter_and_builds_no_client(data, monkeypatch):
    def reached(*_, **__):
        raise AssertionError("the counter was read or a client was built")

    monkeypatch.setattr(probe, "check_before_paying", reached)
    data.mkdir(parents=True)
    (data / "ask_summary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit):
        probe.main(["--yes"], make_client=reached)
    monkeypatch.delenv("MODEL_API_KEY")
    with pytest.raises(SystemExit):
        probe.main(["--yes"], make_client=reached)


def test_a_full_run_writes_ask_summary_and_ask_calls_and_never_summary_json(
    data, go, capsys
):
    code, meta, _spend, _events = go(["--yes", "--runs", "2"])
    assert code == 0
    assert not (data / "summary.json").exists()
    assert not (data.parent / "summary.json").exists()
    assert sorted(path.name for path in data.iterdir()) == [
        "ask_calls.jsonl",
        "ask_summary.json",
    ]
    # 2 runs x 2 efforts x 2 turns, then the off-topic, the "dito" and the car (2).
    assert sum(probe.calls_of(job) for job in probe.main_jobs(2)) == 12
    assert len(meta.bodies) == 12 == len(calls_log(data))
    summary = summary_of(data)
    assert summary["calls"] == 12
    assert summary["stopped"] is None
    assert summary["model"] == "muse-spark-1.3"
    assert summary["prompt_version"] == "ask_v1"
    assert summary["step5"]["ran"] is False
    for effort in ("minimal", "low"):
        block = summary["efforts"][effort]
        assert block["turn1"]["calls"] == 2
        assert block["turn2"]["calls"] == 2
        assert block["two_turn"]["calls"] == 2
        assert block["two_turn"]["max_s"] == 1.0  # 0.5 s + 0.5 s
        assert block["tool_call_right"] == "2/2"
        assert block["final_right"] == "2/2"
    checks = {(c["question"], c["turn"]): c for c in summary["checks"]}
    assert checks[("score", 1)]["right"] is True
    assert checks[("dito", 1)]["right"] is True
    assert checks[("quezon", 1)]["right"] is True
    assert checks[("quezon", 2)]["right"] is True
    assert capsys.readouterr().out


def test_the_run_reads_the_counter_before_the_client_and_records_once_after(data, go):
    _code, meta, spend, events = go(["--yes", "--runs", "1"])
    assert events == ["check", "client", "record"]
    calls = len(meta.bodies)
    usd = cost_of(spark_input_tokens=900 * calls, spark_output_tokens=60 * calls)
    assert spend.records == [(usd, "ask_probe")]
    summary = summary_of(data)
    assert Decimal(str(summary["estimated_cost_usd"])) == usd
    assert summary["tokens"] == {
        "input": 900 * calls,
        "output": 60 * calls,
        "reasoning": 10 * calls,
    }


def test_one_client_is_built_and_warmed_once(data, go):
    _, meta, _, events = go(["--yes", "--runs", "1"])
    assert events.count("client") == 1
    assert meta.warmed == 1


def test_stdout_has_counts_and_timings_only(data, go, capsys):
    go(["--yes", "--runs", "1"])
    out = capsys.readouterr().out
    for question in probe.QUESTIONS.values():
        assert question.text not in out
    for text in ("Araneta Avenue", "Quezon Avenue", "off_topic", "thinking", "cited"):
        assert text not in out
    assert " s" in out  # timings


def test_a_sealed_part_in_the_data_path_is_refused_before_anything_is_made(
    tmp_path, go, monkeypatch, capsys
):
    monkeypatch.setenv("MODEL_API_KEY", KEY)
    for name in ("sealed", "Sealed", "sealed.", "sealed::$INDEX_ALLOCATION"):
        monkeypatch.setattr(probe, "DATA", tmp_path / name / "data")
        with pytest.raises(SystemExit) as exit_:
            go(["--yes"])
        assert exit_.value.code == 2
        assert "sealed" in capsys.readouterr().out
        assert not (tmp_path / name).exists()


def test_a_sealed_part_is_refused_even_for_the_dry_run(tmp_path, go, monkeypatch):
    monkeypatch.setattr(probe, "DATA", tmp_path / "sealed" / "data")
    with pytest.raises(SystemExit) as exit_:
        go([])
    assert exit_.value.code == 2


def test_a_data_folder_inside_the_repo_is_refused(go, monkeypatch, capsys):
    monkeypatch.setenv("MODEL_API_KEY", KEY)
    inside = probe.REPO / "not-a-real-data-folder"
    monkeypatch.setattr(probe, "DATA", inside)
    with pytest.raises(SystemExit) as exit_:
        go(["--yes"])
    assert exit_.value.code == 2
    assert "inside the repo" in capsys.readouterr().out
    assert not inside.exists()


def test_an_earlier_summary_or_calls_file_is_never_overwritten(data, go):
    data.mkdir(parents=True)
    for name in ("ask_summary.json", "ask_calls.jsonl"):
        for other in ("ask_summary.json", "ask_calls.jsonl"):
            (data / other).unlink(missing_ok=True)
        (data / name).write_text("{}", encoding="utf-8")
        with pytest.raises(SystemExit) as exit_:
            go(["--yes"])
        assert exit_.value.code == 2
        assert (data / name).read_text(encoding="utf-8") == "{}"


def test_no_output_file_or_line_holds_the_key(data, go, capsys):
    def leaky(body):
        if ScriptedMeta.question(body).startswith("Kaya"):
            return ScriptedMeta.reply(
                status=429,
                error={
                    "type": "rate_limit",
                    "code": "slow_down",
                    "param": None,
                    "message": f"key {KEY} is over its limit",
                },
            )
        return ScriptedMeta().default(body)

    go(["--yes", "--runs", "1"], meta=ScriptedMeta(leaky))
    seen = capsys.readouterr()
    assert KEY not in seen.out and KEY not in seen.err
    files = [path for path in data.parent.rglob("*") if path.is_file()]
    assert len(files) == 2
    texts = [path.read_text(encoding="utf-8") for path in files]
    assert all(KEY not in text for text in texts)
    assert any("[key]" in text for text in texts)  # the message stays, scrubbed


def test_the_cost_guard_stops_before_a_call_that_would_pass_the_cap(
    data, go, monkeypatch
):
    first = probe.build_turn1(PROMPTS, QUESTION, False, "minimal", "schema")
    # Room for the first call's worst case and not for the second's.
    cap = probe.estimate_cost(first) + Decimal("0.0001")
    monkeypatch.setattr(probe, "COST_CAP_USD", cap)
    code, meta, spend, _ = go(["--yes"])
    assert code == probe.COST_GUARD_EXIT == 4
    assert len(meta.bodies) == 1
    summary = summary_of(data)
    assert summary["stopped"] == "cost_guard"
    assert summary["calls"] == 1
    spent = cost_of(spark_input_tokens=900, spark_output_tokens=60)
    assert spend.records == [(spent, "ask_probe")]  # what was paid is recorded


def test_a_cap_below_the_first_calls_worst_case_makes_no_call(data, go, monkeypatch):
    monkeypatch.setattr(probe, "COST_CAP_USD", Decimal("0.001"))
    code, meta, spend, _events = go(["--yes"])
    assert code == 4
    assert meta.bodies == []
    assert spend.records == []
    assert summary_of(data)["stopped"] == "cost_guard"


def test_calls_that_cost_nothing_are_not_recorded(data, go):
    def refused(body):
        return ScriptedMeta.reply(status=400, error={"type": "bad", "message": "no"})

    code, _meta, spend, _ = go(["--yes", "--runs", "1"], meta=ScriptedMeta(refused))
    assert code == 0
    assert spend.records == []  # an HTTP error isn't billed


def test_a_call_that_may_have_been_billed_is_charged_at_the_unreported_rate(data, go):
    def lost(body):
        return ScriptedMeta.reply(
            status=None,
            input_tokens=None,
            output_tokens=None,
            reasoning_tokens=None,
            error={"type": "APITimeoutError"},
        )

    _, meta, spend, _ = go(["--yes", "--runs", "1"], meta=ScriptedMeta(lost))
    tokens_in, tokens_out = SPARK_TOKENS_IF_UNREPORTED
    one = cost_of(spark_input_tokens=tokens_in, spark_output_tokens=tokens_out)
    assert spend.records == [(one * len(meta.bodies), "ask_probe")]


def test_a_400_beside_text_format_runs_step_5s_other_forms(data, go):
    def schema_refused(body):
        if "tools" in body and "text" in body:
            return ScriptedMeta.reply(
                status=400,
                error={"type": "invalid_request", "param": "text", "message": "no"},
            )
        return ScriptedMeta().default(body)

    meta = ScriptedMeta(schema_refused)
    code, meta, _spend, _ = go(["--yes", "--runs", "1"], meta=meta)
    assert code == 0
    # Steps 1 to 4 were refused at turn 1, so no turn 2: 2 + 1 + 1 + 1 calls.
    # Step 5: tools_only turn 1 for 3 questions, plain_input turn 2 for 2 of them.
    tools_only = [b for b in meta.bodies if "tools" in b and "text" not in b]
    plain = [b for b in meta.bodies if "tools" not in b and "text" in b]
    assert [len(b["tools"]) for b in tools_only] == [2, 2, 2]
    assert len(plain) == 2
    assert len(meta.bodies) == 5 + 5
    summary = summary_of(data)
    assert summary["step5"]["ran"] is True
    assert summary["step5"]["schema_400s"] == 5
    rows = calls_log(data)
    assert rows[0]["status"] == 400 and rows[0]["error"]["param"] == "text"
    fallback = {r["step"] for r in rows if r["form"] in ("tools_only", "plain_input")}
    assert fallback == {"5"}
    off_topic = [r for r in rows if r["question"] == "score" and r["step"] == "5"]
    assert off_topic[0]["verdict"]["right"] is True  # not_about_flood_depth counts


def test_no_400_means_no_step_5(data, go):
    _, meta, _, _ = go(["--yes", "--runs", "1"])
    assert not [b for b in meta.bodies if "tools" in b and "text" not in b]


def test_an_error_that_is_not_a_400_does_not_start_step_5(data, go):
    def limited(body):
        if "text" in body and "tools" in body:
            return ScriptedMeta.reply(status=429, error={"type": "rate_limit"})
        return ScriptedMeta().default(body)

    go(["--yes", "--runs", "1"], meta=ScriptedMeta(limited))
    assert summary_of(data)["step5"]["ran"] is False


def test_a_400_about_the_reasoning_effort_does_not_start_step_5(data, go):
    def no_minimal(body):
        if body["reasoning"]["effort"] == "minimal":
            error = {"type": "bad", "param": "reasoning.effort", "message": "no"}
            return ScriptedMeta.reply(status=400, error=error)
        return ScriptedMeta().default(body)

    go(["--yes", "--runs", "1"], meta=ScriptedMeta(no_minimal))
    step5 = summary_of(data)["step5"]
    assert step5["ran"] is False
    assert step5["schema_400s"] == 0


def test_turn_2_is_skipped_when_turn_1_made_no_call(data, go):
    def never_calls(body):
        return ScriptedMeta.answer("depth", "none", [])

    code, meta, _, _ = go(["--yes", "--runs", "1"], meta=ScriptedMeta(never_calls))
    assert code == 0
    assert len(meta.bodies) == 2 + 1 + 1 + 1  # turn 1 only, everywhere
    assert not [b for b in meta.bodies if ScriptedMeta.final(b)]
    assert summary_of(data)["efforts"]["minimal"]["tool_call_right"] == "0/1"


def test_a_wrong_call_is_marked_wrong_with_its_reasons(data, go):
    def wrong(body):
        args = {
            "place": "Elsewhere",
            "here": True,
            "since_minutes": 500,
            "kind": "crossing",
            "vehicle": "heavy",
        }
        if ScriptedMeta.final(body):
            return ScriptedMeta().default(body)
        return ScriptedMeta.reply([call_item(args=args)])

    go(["--yes", "--runs", "1"], meta=ScriptedMeta(wrong))
    first = calls_log(data)[0]
    assert first["question"] == "araneta" and first["turn"] == 1
    assert first["verdict"]["right"] is False
    why = " ".join(first["verdict"]["why"])
    for word in ("here", "kind", "vehicle", "place", "since_minutes"):
        assert word in why


def test_a_final_answer_that_cites_a_ref_the_tool_never_gave_is_wrong(data, go):
    def invents(body):
        if ScriptedMeta.final(body):
            return ScriptedMeta.answer("depth", "none", ["r1", "r9"])
        return ScriptedMeta().default(body)

    go(["--yes", "--runs", "1"], meta=ScriptedMeta(invents))
    summary = summary_of(data)
    assert summary["efforts"]["minimal"]["final_right"] == "0/1"


def test_a_cold_first_connection_is_left_out_of_the_timings(data, go):
    go(["--yes", "--runs", "2"], meta=ScriptedMeta(warm_ok=False))
    rows = calls_log(data)
    assert [r["includes_connect"] for r in rows[:3]] == [True, False, False]
    summary = summary_of(data)
    assert summary["connect"]["ok"] is False
    assert summary["efforts"]["minimal"]["turn1"]["calls"] == 1  # run 0 left out
    assert summary["efforts"]["minimal"]["two_turn"]["calls"] == 1


def test_a_warm_connection_leaves_every_call_in_the_timings(data, go):
    go(["--yes", "--runs", "2"])
    summary = summary_of(data)
    assert summary["connect"]["ok"] is True
    assert summary["efforts"]["minimal"]["turn1"]["calls"] == 2
