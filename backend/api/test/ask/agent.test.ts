// A fake Meta replays fixtures shaped from Task 2's probe (test/fixtures/meta/, placeholder ids), and a manual clock
// stands for the time: the Deadline reads it, and a scripted call or tool advances it. No network, no AWS, no key.
import { readFileSync } from "node:fs";
import type { Response } from "openai/resources/responses/responses";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { type AgentCtx, type AgentResult, AgentToolError, EFFORT, FINAL_TURN, type Forms, runAgent, TURN1_FORM } from "../../src/ask/agent";
import { BUDGET, Deadline } from "../../src/ask/deadline";
import { type Meta, type MetaCall, MetaError } from "../../src/ask/meta";
import { loadPrompts } from "../../src/ask/prompts";
import { type Ranked, type ToolArgs, type ToolResult, toModelOutput } from "../../src/ask/tool";
import type { PublicPin } from "../../src/pins";
import { UNREPORTED_USAGE } from "../../src/spend";

const START = Date.parse("2026-10-30T10:00:00Z");
const QUESTION = "Gaano kataas ang tubig sa Araneta Avenue cor. E. Rodriguez ngayon?";
const PLACE = "Araneta Avenue cor. E. Rodriguez";
const SENTINEL_HERE = { lat: 14.5871234, lng: 121.0412345, accuracyM: 25 };
const SENTINEL_ID = "sentinel-report-id";

type Fixture = Record<string, unknown> & { output: Record<string, unknown>[] };
const fixture = (name: string): Fixture =>
  JSON.parse(readFileSync(new URL(`../fixtures/meta/${name}.json`, import.meta.url), "utf8"));

// --- the replies -----------------------------------------------------------------------------------------------

const CALL_ARGS = { place: PLACE, here: false, since_minutes: 180, kind: "depth", vehicle: "none" };

// ask_call.json with its arguments replaced (an object, or a raw string to test bad JSON) and its ids made unique to `n`.
function callReply(args: Record<string, unknown> | string = {}, n = 1): Fixture {
  const reply = fixture("ask_call");
  const [reasoning, call] = reply.output;
  reply.id = `resp_call_${n}`;
  reasoning.id = `rs_fixture_${n}`;
  call.id = `fc_fixture_${n}`;
  call.call_id = `call_fixture_${n}`;
  call.arguments = typeof args === "string" ? args : JSON.stringify({ ...CALL_ARGS, ...args });
  return reply;
}

// ask_answer.json with its text replaced (an object merged over the default verdict, or a raw string).
function verdictReply(verdict: Record<string, unknown> | string = {}): Fixture {
  const reply = fixture("ask_answer");
  const message = reply.output[1] as { content: { text: string }[] };
  message.content[0].text = typeof verdict === "string" ? verdict : JSON.stringify({ kind: "depth", vehicle: "none", cited: ["r1", "r2"], ...verdict });
  return reply;
}

// --- the fake Meta ---------------------------------------------------------------------------------------------

let clock: number;

type Step = {
  reply: Fixture | MetaError;
  takes?: number; // ms the call takes on the clock
  tries?: (number | null)[]; // earlier tries inside this respond, which Meta lists on `calls` before this one
};
const step = (reply: Fixture | MetaError, over: Omit<Step, "reply"> = {}): Step => ({ reply, ...over });

function fakeMeta(steps: Step[]) {
  const calls: MetaCall[] = [];
  const bodies: Record<string, unknown>[] = [];
  const marks: number[] = [];
  const meta: Meta = {
    calls,
    async respond(body, _deadline, byMs) {
      bodies.push(JSON.parse(JSON.stringify(body))); // a copy, so a later change to the request can't alter it
      marks.push(byMs);
      const next = steps.shift();
      if (next === undefined) throw new Error("the test scripted no reply for this call");
      for (const status of next.tries ?? []) calls.push({ model: "muse-spark-1.3", status, ms: 0 });
      clock += next.takes ?? 0;
      const status = next.reply instanceof MetaError ? next.reply.status : 200;
      calls.push({ model: "muse-spark-1.3", status, ms: 0 });
      if (next.reply instanceof MetaError) throw next.reply;
      return next.reply as unknown as Response;
    },
    // The agent runs on a question's text, so it never transcribes.
    async transcribe() {
      throw new Error("the agent never transcribes");
    },
  };
  return { meta, calls, bodies, marks };
}

// --- the tool --------------------------------------------------------------------------------------------------

let counter: number;
function pin(fields: Partial<PublicPin> = {}): PublicPin {
  return {
    id: `${SENTINEL_ID}-${counter++}`,
    lat: 14.60951,
    lng: 120.98941,
    gpsAccuracyM: 12,
    capturedAt: new Date(START - 10 * 60_000).toISOString(),
    mode: "live",
    level: "knee",
    landmark: "rim_three_quarters",
    passability: "NPLV",
    levelIsFloor: false,
    basis: { vehicles: 1, people: 0 },
    flags: 0,
    ...fields,
  };
}

const ranked = (ref: string, p: PublicPin, distanceM: number, minutesAgo: number): Ranked => ({ ref, pin: p, distanceM, minutesAgo });

// Two live reports (r1 deepest) and one demo pin, as the tool returns them.
function foundResult(): ToolResult {
  return {
    status: "ok",
    place: { name: "Araneta Avenue cor. E. Rodriguez", source: "spots" },
    point: { lat: 14.60951, lng: 120.98941 },
    windowMin: 180,
    live: [ranked("r1", pin({ level: "knee" }), 42, 14), ranked("r2", pin({ level: "half_tire" }), 180, 55)],
    demo: [ranked("d1", pin({ mode: "demo", level: "waist", capturedAt: "2009-09-26T02:30:00Z" }), 210, 0)],
    count: 2,
    suggestions: [],
    geo: null,
  };
}

const notFoundResult = (): ToolResult => ({
  status: "place_not_found",
  windowMin: 180,
  live: [],
  demo: [],
  count: 0,
  suggestions: [],
  geo: null,
});

// --- the setup -------------------------------------------------------------------------------------------------

type Setup = {
  tool?: (args: ToolArgs) => Promise<ToolResult>;
  left?: number; // ms left before the model mark when the question starts
};

function setup(steps: Step[], over: Setup = {}) {
  const fake = fakeMeta(steps);
  const found = foundResult();
  const tool = vi.fn(over.tool ?? (async () => found));
  const dropKey = vi.fn();
  const left = over.left ?? BUDGET.modelBy;
  const ctx: AgentCtx = {
    meta: fake.meta,
    prompts: loadPrompts(),
    tool,
    deadline: new Deadline(clock - (BUDGET.modelBy - left), () => clock),
    dropKey,
  };
  return { ...fake, ctx, tool, dropKey, found };
}

type Answered = Extract<AgentResult["outcome"], { type: "answer" }>;
function answerOf(result: AgentResult): Answered {
  expect(result.outcome.type).toBe("answer");
  return result.outcome as Answered;
}

function fallbackOf(result: AgentResult) {
  expect(result.outcome.type).toBe("fallback");
  return result.outcome as Extract<AgentResult["outcome"], { type: "fallback" }>;
}

const run = (s: ReturnType<typeof setup>, forms?: Forms, q: Parameters<typeof runAgent>[0] = { text: QUESTION }) =>
  runAgent(q, s.ctx, forms);

beforeEach(() => {
  clock = START;
  counter = 0;
});

afterEach(() => {
  vi.restoreAllMocks();
});

// --- the tests -------------------------------------------------------------------------------------------------

describe("the rulings", () => {
  it("are Task 2's: effort low, turn 1 with the schema, the final turn replaying", () => {
    expect([EFFORT, TURN1_FORM, FINAL_TURN]).toEqual(["low", "schema", "replay"]);
  });
});

describe("a question that finds reports", () => {
  it("a depth question: one call, one tool run, an answer", async () => {
    const s = setup([step(callReply()), step(verdictReply())]);

    const result = await run(s);

    const { answer, final } = answerOf(result);
    expect(final).toBe("ok");
    expect(answer).toMatchObject({ source: "model", fallback: null, kind: "reports", crossing: false, vehicle: null });
    expect(answer.cited).toEqual([s.found.live[0].pin.id, s.found.live[1].pin.id]);
    expect(answer.reports).toHaveLength(2);
    expect(answer.demo).toHaveLength(1);
    expect(result.toolCalls).toBe(1);
    expect(s.tool).toHaveBeenCalledTimes(1);
    expect(s.tool).toHaveBeenCalledWith({ place: PLACE, here: false, sinceMin: 180, kind: "depth", vehicle: "none" });
    expect(s.calls).toHaveLength(2);
    expect(s.marks).toEqual([BUDGET.modelBy, BUDGET.modelBy]);
  });

  it("turn 1 sends the instructions, the question with the location line, the tool and the answer schema", async () => {
    const s = setup([step(callReply()), step(verdictReply())]);
    const prompts = s.ctx.prompts;

    await run(s);

    expect(s.bodies[0]).toEqual({
      model: "muse-spark-1.3",
      instructions: prompts.instructions,
      input: [
        {
          type: "message",
          role: "user",
          content: [
            { type: "input_text", text: "Location shared: no" },
            { type: "input_text", text: QUESTION },
          ],
        },
      ],
      store: false,
      include: ["reasoning.encrypted_content"],
      reasoning: { effort: "low" },
      max_output_tokens: 800,
      tools: [prompts.tool],
      tool_choice: "auto",
      parallel_tool_calls: false,
      text: { format: { type: "json_schema", name: "ask_answer_v1", schema: prompts.answerSchema, strict: true } },
    });
  });

  it("says when the location is shared", async () => {
    const s = setup([step(callReply()), step(verdictReply())]);

    await run(s, undefined, { text: QUESTION, here: SENTINEL_HERE });

    const input = s.bodies[0].input as { content: { text: string }[] }[];
    expect(input[0].content.map((part) => part.text)).toEqual(["Location shared: yes", QUESTION]);
  });

  it("turn 2 replays the reasoning items with their summaries, and the call_id matches", async () => {
    const first = callReply();
    const [reasoning] = first.output;
    reasoning.summary = [{ type: "summary_text", text: "summary-text-sentinel" }];
    // A second reasoning item that came back with no summary at all is replayed with [].
    first.output.splice(1, 0, { id: "rs_fixture_extra", type: "reasoning", encrypted_content: "enc_extra" });
    const s = setup([step(first), step(verdictReply())]);

    await run(s);

    const call = first.output[2];
    expect(s.bodies[1].input).toEqual([
      (s.bodies[0].input as unknown[])[0],
      { id: "rs_fixture_1", type: "reasoning", summary: [{ type: "summary_text", text: "summary-text-sentinel" }], encrypted_content: "enc_fixture_1" },
      { id: "rs_fixture_extra", type: "reasoning", summary: [], encrypted_content: "enc_extra" },
      call,
      { type: "function_call_output", call_id: "call_fixture_1", output: toModelOutput(s.found) },
    ]);
    expect(s.bodies[1]).toMatchObject({
      store: false,
      include: ["reasoning.encrypted_content"],
      reasoning: { effort: "low" },
      max_output_tokens: 800,
      tool_choice: "auto",
      parallel_tool_calls: false,
      text: { format: { type: "json_schema", strict: true } },
    });
    expect((s.bodies[1].tools as { name: string }[]).map((t) => t.name)).toEqual(["get_reports"]);
  });

  it("place_not_found, a second call, then an answer", async () => {
    const found = foundResult();
    const s = setup(
      [step(callReply({ place: "Araneta Ave & Rodriguez" }, 1)), step(callReply({ place: "Araneta Avenue" }, 2)), step(verdictReply())],
      { tool: vi.fn().mockResolvedValueOnce(notFoundResult()).mockResolvedValueOnce(found) },
    );

    const result = await run(s);

    const { answer, final } = answerOf(result);
    expect(final).toBe("ok");
    expect(answer.kind).toBe("reports");
    expect(answer.cited).toEqual([found.live[0].pin.id, found.live[1].pin.id]);
    expect(result.toolCalls).toBe(2);
    expect(s.tool.mock.calls.map(([args]) => args.place)).toEqual(["Araneta Ave & Rodriguez", "Araneta Avenue"]);
    expect(s.bodies).toHaveLength(3);
    // Turn 3 replays both calls with their own outputs.
    const items = s.bodies[2].input as { type: string; call_id?: string; output?: string }[];
    expect(items.filter((i) => i.type === "function_call").map((i) => i.call_id)).toEqual(["call_fixture_1", "call_fixture_2"]);
    expect(items.filter((i) => i.type === "function_call_output")).toEqual([
      { type: "function_call_output", call_id: "call_fixture_1", output: toModelOutput(notFoundResult()) },
      { type: "function_call_output", call_id: "call_fixture_2", output: toModelOutput(found) },
    ]);
    expect(s.marks).toEqual([BUDGET.modelBy, BUDGET.modelBy, BUDGET.modelBy]);
  });

  it("a third call isn't made", async () => {
    const found = foundResult();
    const s = setup(
      [
        step(callReply({ kind: "crossing", vehicle: "light" }, 1)),
        step(callReply({ kind: "depth", vehicle: "none", place: "Araneta Avenue" }, 2)),
        step(callReply({ place: "Araneta" }, 3)),
      ],
      { tool: vi.fn().mockResolvedValueOnce(notFoundResult()).mockResolvedValueOnce(found) },
    );

    const result = await run(s);

    const { answer, final } = answerOf(result);
    expect(final).toBe("failed");
    expect(answer.cited).toEqual([]);
    // The second call's result, not the first's, and the reading takes both calls: call 1 said crossing and light.
    expect(answer.kind).toBe("reports");
    expect(answer.reports.map((r) => r.id)).toEqual(found.live.map((r) => r.pin.id));
    expect(answer.crossing).toBe(true);
    expect(answer.vehicle).toBe("light");
    expect(result.toolCalls).toBe(2);
    expect(s.tool).toHaveBeenCalledTimes(2);
    expect(s.bodies).toHaveLength(3);
  });

  it("a second call with bad arguments keeps the first result and loses only the citations", async () => {
    const s = setup([step(callReply()), step(callReply('{"place":"Araneta"}', 2))]);

    const result = await run(s);

    const { answer, final } = answerOf(result);
    expect(final).toBe("failed");
    expect(answer).toMatchObject({ source: "model", kind: "reports", cited: [] });
    expect(result.toolCalls).toBe(1);
    expect(s.bodies).toHaveLength(2);
  });
});

describe("a question that isn't about flood depth", () => {
  it("off_topic without a call", async () => {
    const s = setup([step(fixture("ask_offtopic"))]);

    const result = await run(s);

    const { answer, final } = answerOf(result);
    expect(final).toBeNull();
    expect(answer).toMatchObject({ source: "model", fallback: null, kind: "off_topic", cited: [], reports: [], demo: [] });
    expect(result.toolCalls).toBe(0);
    expect(s.tool).not.toHaveBeenCalled();
    expect(s.calls).toHaveLength(1);
  });

  it("tools_only turn 1: the body holds both tools and no text.format, and a not_about_flood_depth call is the off_topic answer", async () => {
    const reply = callReply("{}");
    (reply.output[1] as { name: string }).name = "not_about_flood_depth";
    const s = setup([step(reply)]);
    const prompts = s.ctx.prompts;

    const result = await run(s, { turn1: "tools_only", final: "replay" });

    const { answer, final } = answerOf(result);
    expect(final).toBeNull();
    expect(answer).toMatchObject({ source: "model", kind: "off_topic", cited: [] });
    expect(result.toolCalls).toBe(0);
    expect(s.tool).not.toHaveBeenCalled();
    expect(s.bodies[0].tools).toEqual([prompts.tool, prompts.offTopicTool]);
    expect(s.bodies[0]).not.toHaveProperty("text");
    expect(s.bodies[0]).toMatchObject({ tool_choice: "auto", parallel_tool_calls: false, store: false });
  });

  it("tools_only turn 1 with a get_reports call goes on to the final turn", async () => {
    const s = setup([step(callReply()), step(verdictReply())]);

    const result = await run(s, { turn1: "tools_only", final: "replay" });

    expect(answerOf(result).final).toBe("ok");
    expect(s.bodies[1]).toHaveProperty("text");
  });

  it("not_about_flood_depth is accepted only where it was offered", async () => {
    const reply = callReply("{}");
    (reply.output[1] as { name: string }).name = "not_about_flood_depth";
    const s = setup([step(reply)]);

    const result = await run(s);

    expect(fallbackOf(result).fallback).toBe("invalid_answer");
  });
});

describe("the final turn", () => {
  it("less than 1,500 ms after the tool means no final turn", async () => {
    const s = setup([step(callReply({ kind: "crossing", vehicle: "light" }))], {
      tool: async () => {
        clock += BUDGET.modelBy - BUDGET.minTurn + 1; // 1,499 ms left
        return foundResult();
      },
    });

    const result = await run(s);

    const { answer, final } = answerOf(result);
    expect(final).toBe("skipped");
    // The call alone holds the crossing line and the vehicle; only the citations are lost.
    expect(answer).toMatchObject({ source: "model", kind: "reports", crossing: true, vehicle: "light", cited: [] });
    expect(answer.reports).toHaveLength(2);
    expect(s.bodies).toHaveLength(1);
    expect(result.toolCalls).toBe(1);
  });

  it("exactly 1,500 ms after the tool is enough for the final turn", async () => {
    const s = setup([step(callReply()), step(verdictReply())], {
      tool: async () => {
        clock += BUDGET.modelBy - BUDGET.minTurn; // 1,500 ms left
        return foundResult();
      },
    });

    const result = await run(s);

    expect(answerOf(result).final).toBe("ok");
    expect(s.bodies).toHaveLength(2);
  });

  it("the deadline during the final turn", async () => {
    const s = setup([step(callReply({ kind: "crossing", vehicle: "light" })), step(new MetaError(null), { takes: BUDGET.modelBy + 100 })]);

    const result = await run(s);

    const { answer, final } = answerOf(result);
    expect(final).toBe("failed");
    expect(answer).toMatchObject({ source: "model", kind: "reports", crossing: true, vehicle: "light", cited: [] });
    expect(answer.reports).toHaveLength(2);
  });

  it("a final turn that cites a ref the tool didn't return", async () => {
    const s = setup([step(callReply()), step(verdictReply({ cited: ["r1", "r9"] }))]);

    const result = await run(s);

    const { answer, final } = answerOf(result);
    expect(final).toBe("failed");
    expect(answer).toMatchObject({ kind: "reports", cited: [] });
    expect(answer.reports).toHaveLength(2);
  });

  it("a final turn that says off_topic keeps the reports", async () => {
    const s = setup([step(callReply()), step(verdictReply({ kind: "off_topic", cited: ["r1", "r2"] }))]);

    const result = await run(s);

    const { answer, final } = answerOf(result);
    expect(final).toBe("failed");
    expect(answer).toMatchObject({ source: "model", kind: "reports", cited: [] });
    expect(answer.reports).toHaveLength(2);
  });

  it.each([
    ["a verdict that leaves out r1", () => step(verdictReply({ cited: ["r2"] }))],
    ["text that isn't JSON", () => step(verdictReply("The water is knee deep."))],
    ["a verdict with an extra key", () => step(verdictReply({ extra: true }))],
    ["an incomplete response", () => step(fixture("ask_incomplete"))],
    ["a Meta error", () => step(new MetaError(500))],
    ["a rejected key", () => step(new MetaError(402))],
    ["no output at all", () => step({ ...verdictReply(), output: [] })],
    ["a refusal", () => step(refusal())],
    ["two calls in one turn", () => step(twoCalls())],
    ["a call to another tool", () => step(otherTool())],
  ])("%s gives an answer without citations, not a fallback", async (_name, make) => {
    const s = setup([step(callReply({ kind: "crossing", vehicle: "light" })), make()]);

    const result = await run(s);

    const { answer, final } = answerOf(result);
    expect(final).toBe("failed");
    expect(answer).toMatchObject({ source: "model", kind: "reports", crossing: true, vehicle: "light", cited: [] });
    expect(answer.reports).toHaveLength(2);
  });

  it("a rejected key in the final turn still drops the key", async () => {
    const s = setup([step(callReply()), step(new MetaError(401))]);

    await run(s);

    expect(s.dropKey).toHaveBeenCalledTimes(1);
  });

  it("plain_input's final turn sends no tools", async () => {
    const s = setup([step(callReply()), step(verdictReply())]);

    const result = await run(s, { turn1: "schema", final: "plain_input" });

    expect(answerOf(result).final).toBe("ok");
    expect(s.bodies[1]).not.toHaveProperty("tools");
    expect(s.bodies[1]).not.toHaveProperty("tool_choice");
    expect(s.bodies[1]).not.toHaveProperty("parallel_tool_calls");
    expect(s.bodies[1]).toMatchObject({
      store: false,
      include: ["reasoning.encrypted_content"],
      reasoning: { effort: "low" },
      max_output_tokens: 800,
      text: { format: { type: "json_schema", name: "ask_answer_v1", strict: true } },
    });
    // The question and the tool's output as plain input: no reasoning item, no call, no call output.
    expect(s.bodies[1].input).toEqual([
      {
        type: "message",
        role: "user",
        content: [
          { type: "input_text", text: "Location shared: no" },
          { type: "input_text", text: QUESTION },
          { type: "input_text", text: `get_reports result:\n${toModelOutput(s.found)}` },
        ],
      },
    ]);
  });

  it("plain_input never reaches a second call", async () => {
    const s = setup([step(callReply()), step(callReply({}, 2))]);

    const result = await run(s, { turn1: "schema", final: "plain_input" });

    expect(answerOf(result).final).toBe("failed");
    expect(result.toolCalls).toBe(1);
    expect(s.tool).toHaveBeenCalledTimes(1);
  });
});

describe("turn 1 fails", () => {
  it("the deadline during turn 1", async () => {
    const s = setup([step(new MetaError(null), { takes: BUDGET.modelBy + 1 })]);

    const result = await run(s);

    const fallback = fallbackOf(result);
    expect(fallback.fallback).toBe("deadline");
    expect(fallback).not.toHaveProperty("tool");
    expect(result.toolCalls).toBe(0);
    expect(s.tool).not.toHaveBeenCalled();
  });

  it("less than 1,500 ms left at the start sends nothing", async () => {
    const s = setup([step(callReply())], { left: BUDGET.minTurn - 1 });

    const result = await run(s);

    expect(fallbackOf(result).fallback).toBe("deadline");
    expect(s.bodies).toHaveLength(0);
    expect(result.usage).toEqual({ input: 0, output: 0, reasoning: 0 });
  });

  it("a lost connection with time left is model_error", async () => {
    const s = setup([step(new MetaError(null), { takes: 300 })]);

    expect(fallbackOf(await run(s)).fallback).toBe("model_error");
  });

  it("a depth answer without a call in turn 1", async () => {
    const s = setup([step(verdictReply())]);

    const result = await run(s);

    expect(fallbackOf(result).fallback).toBe("no_tool_call");
    expect(s.tool).not.toHaveBeenCalled();
  });

  it("a crossing answer without a call in turn 1", async () => {
    const s = setup([step(verdictReply({ kind: "crossing", cited: [] }))]);

    expect(fallbackOf(await run(s)).fallback).toBe("no_tool_call");
  });

  it.each([401, 402, 403])("a %i gives the fallback key_rejected and drops the key", async (status) => {
    const s = setup([step(new MetaError(status))]);

    const result = await run(s);

    expect(fallbackOf(result).fallback).toBe("key_rejected");
    expect(s.dropKey).toHaveBeenCalledTimes(1);
  });

  it.each([400, 429, 500, 503, 504])("a %i gives model_error and keeps the key", async (status) => {
    const s = setup([step(new MetaError(status))]);

    const result = await run(s);

    expect(fallbackOf(result).fallback).toBe("model_error");
    expect(s.dropKey).not.toHaveBeenCalled();
  });

  it("an incomplete response gives the fallback model_error", async () => {
    const s = setup([step(fixture("ask_incomplete"))]);

    const result = await run(s);

    expect(fallbackOf(result).fallback).toBe("model_error");
    expect(s.tool).not.toHaveBeenCalled();
  });

  it("a refusal gives the fallback model_error", async () => {
    const s = setup([step(refusal())]);

    expect(fallbackOf(await run(s)).fallback).toBe("model_error");
  });

  it.each([
    ["JSON that isn't JSON", "{not json"],
    ["a missing argument", '{"place":"Araneta"}'],
    ["a wrong type", JSON.stringify({ ...CALL_ARGS, here: "no" })],
    ["a value outside the enum", JSON.stringify({ ...CALL_ARGS, kind: "advice" })],
  ])("%s in the call gives invalid_answer", async (_name, args) => {
    const s = setup([step(callReply(args))]);

    const result = await run(s);

    expect(fallbackOf(result).fallback).toBe("invalid_answer");
    expect(s.tool).not.toHaveBeenCalled();
  });

  it("text that isn't a verdict, with no call, gives invalid_answer", async () => {
    const s = setup([step(verdictReply("The water is knee deep."))]);

    expect(fallbackOf(await run(s)).fallback).toBe("invalid_answer");
  });

  it("a call to another tool gives invalid_answer", async () => {
    const s = setup([step(otherTool())]);

    const result = await run(s);

    expect(fallbackOf(result).fallback).toBe("invalid_answer");
    expect(s.tool).not.toHaveBeenCalled();
  });

  it("two calls in one turn give invalid_answer", async () => {
    const s = setup([step(twoCalls())]);

    const result = await run(s);

    expect(fallbackOf(result).fallback).toBe("invalid_answer");
    expect(s.tool).not.toHaveBeenCalled();
  });
});

describe("the usage that feeds the spend counter", () => {
  it("counts each response's reported tokens, and the reasoning apart", async () => {
    const s = setup([step(callReply()), step(verdictReply())]);

    const result = await run(s);

    // ask_call.json: 1285 in, 445 out (307 reasoning). ask_answer.json: 1897 in, 320 out (287 reasoning).
    expect(result.usage).toEqual({ input: 1285 + 1897, output: 445 + 320, reasoning: 307 + 287 });
  });

  it("charges a response without usage at the unreported amount", async () => {
    const noUsage = callReply();
    delete noUsage.usage;
    const s = setup([step(noUsage), step(verdictReply())]);

    const result = await run(s);

    expect(result.usage).toEqual({
      input: UNREPORTED_USAGE.spark_input_tokens + 1897,
      output: UNREPORTED_USAGE.spark_output_tokens + 320,
      reasoning: 287,
    });
  });

  it("charges each count a response left out or gave as null at the unreported amount", async () => {
    const partial = callReply();
    partial.usage = { input_tokens: null, output_tokens: 445 };
    const s = setup([step(partial), step(verdictReply())]);

    const result = await run(s);

    expect(result.usage).toEqual({ input: UNREPORTED_USAGE.spark_input_tokens + 1897, output: 445 + 320, reasoning: 287 });
  });

  it("charges a try that ended with no status, and no HTTP error", async () => {
    // One respond: a try with no answer (may have been billed), a 503 (not billed), then the answer.
    const s = setup([step(callReply(), { tries: [null, 503] }), step(verdictReply())]);

    const result = await run(s);

    expect(result.usage).toEqual({
      input: 1285 + 1897 + UNREPORTED_USAGE.spark_input_tokens,
      output: 445 + 320 + UNREPORTED_USAGE.spark_output_tokens,
      reasoning: 307 + 287,
    });
  });

  it("counts only this question's tries on a Meta that already holds others", async () => {
    const s = setup([step(callReply()), step(verdictReply())]);
    s.calls.push({ model: "muse-spark-1.3", status: null, ms: 0 });

    const result = await run(s);

    expect(result.usage.input).toBe(1285 + 1897);
  });

  it("a fallback carries its usage: a response that was received, and a try with no answer", async () => {
    const incomplete = setup([step(fixture("ask_incomplete"))]);
    expect((await run(incomplete)).usage).toEqual({ input: 1285, output: 800, reasoning: 800 });

    const lost = setup([step(new MetaError(null), { takes: 300 })]);
    expect((await run(lost)).usage).toEqual({
      input: UNREPORTED_USAGE.spark_input_tokens,
      output: UNREPORTED_USAGE.spark_output_tokens,
      reasoning: 0,
    });

    const rejected = setup([step(new MetaError(402))]);
    expect((await run(rejected)).usage).toEqual({ input: 0, output: 0, reasoning: 0 });
  });

  it("a final turn with no answer still counts the paid turn and the lost try", async () => {
    const s = setup([step(callReply()), step(new MetaError(null), { takes: BUDGET.modelBy + 100 })]);

    const result = await run(s);

    expect(result.usage).toEqual({
      input: 1285 + UNREPORTED_USAGE.spark_input_tokens,
      output: 445 + UNREPORTED_USAGE.spark_output_tokens,
      reasoning: 307,
    });
  });

  it("a tool that throws leaves the paid turn counted on the error", async () => {
    const failure = new Error("the pins read failed");
    const s = setup([step(callReply())], {
      tool: async () => {
        throw failure;
      },
    });

    const err = await run(s).then(
      () => undefined,
      (e: unknown) => e,
    );

    expect(err).toBeInstanceOf(AgentToolError);
    const failed = err as AgentToolError;
    expect(failed.usage).toEqual({ input: 1285, output: 445, reasoning: 307 });
    expect(failed.toolCalls).toBe(1);
    expect(failed.cause).toBe(failure);
    expect(failed.message).not.toContain("pins read");
  });
});

describe("privacy", () => {
  it("no request body holds the here point's coordinates or a report id", async () => {
    const found = foundResult();
    // A tool result whose point is the person's own, as for a question about "here".
    found.point = { lat: SENTINEL_HERE.lat, lng: SENTINEL_HERE.lng };
    const s = setup(
      [step(callReply({ place: "", here: true }, 1)), step(callReply({ place: "Araneta Avenue" }, 2)), step(verdictReply())],
      { tool: vi.fn().mockResolvedValueOnce(notFoundResult()).mockResolvedValueOnce(found) },
    );

    await run(s, undefined, { text: QUESTION, here: SENTINEL_HERE });

    expect(s.bodies).toHaveLength(3);
    const sent = JSON.stringify(s.bodies);
    expect(sent).toContain("Location shared: yes");
    expect(sent).toContain('\\"ref\\":\\"r1\\"'); // the tool's output reached Meta, as refs and distances
    for (const secret of [String(SENTINEL_HERE.lat), String(SENTINEL_HERE.lng), SENTINEL_ID, "14.60951", "120.98941"]) {
      expect(sent, secret).not.toContain(secret);
    }
  });

  it("writes nothing to any log", async () => {
    const spies = (["log", "info", "warn", "error", "debug"] as const).map((name) => vi.spyOn(console, name).mockImplementation(() => {}));
    const s = setup([step(callReply()), step(verdictReply())]);

    await run(s, undefined, { text: QUESTION, here: SENTINEL_HERE });
    await run(setup([step(new MetaError(500))]));

    expect(spies.flatMap((spy) => spy.mock.calls)).toEqual([]);
  });
});

describe("who turned the crossing line on, for the log line (spec §4.9)", () => {
  const CROSSING_QUESTION = "Kaya bang tumawid sa Araneta Avenue cor. E. Rodriguez?";

  it.each([
    ["the model's call", QUESTION, { kind: "crossing" }, {}, "model"],
    ["the final answer alone", QUESTION, {}, { kind: "crossing" }, "model"],
    ["the question's words", CROSSING_QUESTION, {}, {}, "words"],
    ["both", CROSSING_QUESTION, { kind: "crossing" }, {}, "both"],
    ["neither", QUESTION, {}, {}, null],
  ] as const)("%s", async (_name, text, call, verdict, crossingFrom) => {
    const s = setup([step(callReply(call)), step(verdictReply(verdict))]);

    const outcome = answerOf(await run(s, undefined, { text }));

    expect(outcome.crossingFrom).toBe(crossingFrom);
    expect(outcome.answer.crossing).toBe(crossingFrom !== null);
  });

  it("an off_topic answer takes it from the question's words", async () => {
    const s = setup([step(fixture("ask_offtopic"))]);

    expect(answerOf(await run(s, undefined, { text: "Tumawid ba ang manok?" })).crossingFrom).toBe("words");
  });
});

// --- reply shapes ----------------------------------------------------------------------------------------------

// A completed response whose message is a refusal.
function refusal(): Fixture {
  const reply = verdictReply();
  reply.output[1] = { ...reply.output[1], content: [{ type: "refusal", refusal: "I can't help with that." }] };
  return reply;
}

// Two get_reports calls in one turn, which `parallel_tool_calls: false` should rule out.
function twoCalls(): Fixture {
  const reply = callReply();
  reply.output.push({ ...reply.output[1], id: "fc_fixture_extra", call_id: "call_fixture_extra" });
  return reply;
}

// A call to a tool that wasn't offered.
function otherTool(): Fixture {
  const reply = callReply();
  (reply.output[1] as { name: string }).name = "get_weather";
  return reply;
}
