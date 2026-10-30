import type {
  FunctionTool,
  Response,
  ResponseCreateParamsNonStreaming,
  ResponseFunctionToolCall,
  ResponseInputItem,
  ResponseReasoningItem,
} from "openai/resources/responses/responses";
import { sparkUsage, UNREPORTED_USAGE } from "../spend";
import { type Answer, checkVerdict, classify, type Fallback, type ModelVerdict, modelAnswer } from "./answer";
import { BUDGET, type Deadline } from "./deadline";
import { type Meta, MetaError } from "./meta";
import type { AskPrompts } from "./prompts";
import { type Here, parseToolArgs, type ToolArgs, type ToolResult, toModelOutput } from "./tool";

// Task 2's rulings (docs/research/2026-10-30-ask-probe.md): `low` was right 10 of 10 with both turns at 2.75 s at the
// median; Meta takes tools beside text.format, so turn 1 is `schema`, and the final turn replays the reasoning items.
export const EFFORT = "low";
export type Turn1Form = "schema" | "tools_only";
export type FinalForm = "replay" | "plain_input";
export const TURN1_FORM: Turn1Form = "schema";
export const FINAL_TURN: FinalForm = "replay";

// The forms runAgent uses. Only a test passes others, to cover the forms the rulings didn't pick (spec §4.3).
export type Forms = { turn1: Turn1Form; final: FinalForm };

const MODEL = "muse-spark-1.3";
const ANSWER_NAME = "ask_answer_v1";
const MAX_OUTPUT_TOKENS = 800;
const MAX_TOOL_CALLS = 2; // the model may call get_reports once more, never a third time (C703)
const KEY_REJECTED = new Set([401, 402, 403]);

export type AgentUsage = { input: number; output: number; reasoning: number };

export type AgentResult = {
  outcome:
    | { type: "answer"; answer: Answer; final: "ok" | "skipped" | "failed" | null }
    // A fallback only comes from turn 1, before any tool ran, so it never carries a tool result: once the tool has
    // run, every ending is an answer (spec §4.3). The field is the interface's, for the handler's one `fallback` type.
    | { type: "fallback"; fallback: Fallback; tool?: ToolResult };
  toolCalls: number;
  usage: AgentUsage;
};

export type AgentCtx = {
  meta: Meta;
  prompts: AskPrompts;
  tool: (args: ToolArgs) => Promise<ToolResult>;
  deadline: Deadline;
  // Forgets the cached Meta key, so the next question reads it again (Meta rejected it).
  dropKey: () => void;
};

// The tool threw (a failed pins read) after a turn was already paid for. The handler answers for the failure, and
// `usage` is what it still records on the spend counter (C736), so a paid turn is never left uncounted. The message
// is fixed; the cause stays on `cause`, and nothing here logs it.
export class AgentToolError extends Error {
  readonly usage: AgentUsage;
  readonly toolCalls: number;

  constructor(usage: AgentUsage, toolCalls: number, cause: unknown) {
    super("the tool failed", { cause });
    this.name = "AgentToolError";
    this.usage = usage;
    this.toolCalls = toolCalls;
  }
}

// What a response holds that the loop reads. `usable` is false for a response that isn't `completed` or that refused.
type Reading = { usable: boolean; reasoning: ResponseReasoningItem[]; calls: ResponseFunctionToolCall[]; text: string };

function readOutput(res: Response): Reading {
  const reading: Reading = { usable: res.status === undefined || res.status === "completed", reasoning: [], calls: [], text: "" };
  for (const item of res.output) {
    if (item.type === "reasoning") reading.reasoning.push(item);
    else if (item.type === "function_call") reading.calls.push(item);
    else if (item.type === "message") {
      for (const part of item.content) {
        if (part.type === "output_text") reading.text += part.text;
        else reading.usable = false; // a refusal
      }
    }
  }
  return reading;
}

type Turn = { ok: true; reading: Reading } | { ok: false; why: "deadline" | "model_error" | "key_rejected" };

// Spec §4.3: one question's turns, inside the model mark (BUDGET.modelBy). Turn 1 must give a valid get_reports call or
// a valid off_topic answer, else the plain list answers (a `fallback`). Once the tool has run, the question always
// ends in an answer: the final turn only adds the citations, and without them (late, failed, or not checked) the
// answer keeps its crossing and vehicle lines. Whatever happens, `usage` never counts less than Meta may have billed.
export async function runAgent(
  q: { text: string; here?: Here },
  ctx: AgentCtx,
  forms: Forms = { turn1: TURN1_FORM, final: FINAL_TURN },
): Promise<AgentResult> {
  const { meta, prompts, deadline } = ctx;
  const firstTry = meta.calls.length; // this question's tries are the ones after here
  const sum: AgentUsage = { input: 0, output: 0, reasoning: 0 };
  const asked: ToolArgs[] = []; // every call's checked arguments, for classify
  const history: ResponseInputItem[] = [userMessage(q.here !== undefined, q.text)];
  let toolCalls = 0;

  // The tally. Each response received counts at its reported usage (or Task 6's unreported amount for a count Meta left
  // out). A try that was sent and got no HTTP answer may have been billed, so it counts at the unreported amount too;
  // an HTTP error status isn't billed (C736).
  const usage = (): AgentUsage => {
    const lost = meta.calls.slice(firstTry).filter((call) => call.status === null).length;
    return {
      input: sum.input + lost * UNREPORTED_USAGE.spark_input_tokens,
      output: sum.output + lost * UNREPORTED_USAGE.spark_output_tokens,
      reasoning: sum.reasoning,
    };
  };
  const done = (outcome: AgentResult["outcome"]): AgentResult => ({ outcome, toolCalls, usage: usage() });
  const fallback = (why: Fallback) => done({ type: "fallback", fallback: why });

  const request = (items: ResponseInputItem[], tools: FunctionTool[] | null, schema: boolean): ResponseCreateParamsNonStreaming => ({
    model: MODEL,
    instructions: prompts.instructions,
    input: items,
    store: false,
    include: ["reasoning.encrypted_content"],
    reasoning: { effort: EFFORT },
    max_output_tokens: MAX_OUTPUT_TOKENS,
    ...(tools !== null && { tools, tool_choice: "auto", parallel_tool_calls: false }),
    ...(schema && { text: { format: { type: "json_schema", name: ANSWER_NAME, schema: prompts.answerSchema, strict: true } } }),
  });

  const ask = async (body: ResponseCreateParamsNonStreaming): Promise<Turn> => {
    let res: Response;
    try {
      res = await meta.respond(body, deadline, BUDGET.modelBy);
    } catch (err) {
      if (!(err instanceof MetaError)) throw err;
      if (err.status !== null && KEY_REJECTED.has(err.status)) {
        ctx.dropKey();
        return { ok: false, why: "key_rejected" };
      }
      // No HTTP answer once the mark has passed is the budget running out; with time left it is Meta failing.
      return { ok: false, why: err.status === null && deadline.remainingMs(BUDGET.modelBy) === 0 ? "deadline" : "model_error" };
    }
    const u = sparkUsage(res.usage);
    sum.input += u.spark_input_tokens ?? UNREPORTED_USAGE.spark_input_tokens;
    sum.output += u.spark_output_tokens ?? UNREPORTED_USAGE.spark_output_tokens;
    sum.reasoning += res.usage?.output_tokens_details?.reasoning_tokens ?? 0;
    const reading = readOutput(res);
    return reading.usable ? { ok: true, reading } : { ok: false, why: "model_error" };
  };

  // Runs get_reports for a call and adds what the next turn replays: the turn's reasoning items, the call, its output.
  const runTool = async (args: ToolArgs, reading: Reading, call: ResponseFunctionToolCall): Promise<ToolResult> => {
    toolCalls++;
    asked.push(args);
    let result: ToolResult;
    try {
      result = await ctx.tool(args);
    } catch (cause) {
      throw new AgentToolError(usage(), toolCalls, cause);
    }
    history.push(
      ...reading.reasoning.map((item) => ({ ...item, summary: item.summary ?? [] })), // Meta wants a summary on every replay
      call,
      { type: "function_call_output" as const, call_id: call.call_id, output: toModelOutput(result) },
    );
    return result;
  };

  // --- Turn 1 ---------------------------------------------------------------------------------------------------

  if (deadline.remainingMs(BUDGET.modelBy) < BUDGET.minTurn) return fallback("deadline");
  const first = await ask(
    forms.turn1 === "schema"
      ? request([...history], [prompts.tool], true)
      : request([...history], [prompts.tool, prompts.offTopicTool], false),
  );
  if (!first.ok) return fallback(first.why);

  const offTopic = () => done({ type: "answer", answer: modelAnswer(undefined, classify({ calls: [], question: q.text }), null, "off_topic"), final: null });
  const [firstCall] = first.reading.calls;
  if (first.reading.calls.length > 1) return fallback("invalid_answer"); // parallel_tool_calls is false
  if (firstCall === undefined) {
    // No call: only off_topic is an answer. checkVerdict names the other endings (depth or crossing: no_tool_call).
    const check = checkVerdict(first.reading.text, undefined, "first");
    return check.ok ? offTopic() : fallback(check.fallback);
  }
  if (forms.turn1 === "tools_only" && firstCall.name === prompts.offTopicTool.name) return offTopic();
  const firstArgs = firstCall.name === prompts.tool.name ? parseToolArgs(firstCall.arguments, q.text) : undefined;
  if (firstArgs === undefined) return fallback("invalid_answer");
  let tool = await runTool(firstArgs, first.reading, firstCall);

  // --- The turns after the tool: the final turn, and one more if the model calls the tool a second time ----------

  const answered = (cited: string[] | null, final: "ok" | "skipped" | "failed", verdict?: ModelVerdict): AgentResult =>
    done({
      type: "answer",
      answer: modelAnswer(tool, classify({ calls: asked, verdict, question: q.text }), cited, firstArgs.kind),
      final,
    });

  for (;;) {
    if (deadline.remainingMs(BUDGET.modelBy) < BUDGET.minTurn) return answered(null, "skipped");
    const next = await ask(
      forms.final === "replay"
        ? request([...history], [prompts.tool], true)
        : request([userMessage(q.here !== undefined, q.text, `${prompts.tool.name} result:\n${toModelOutput(tool)}`)], null, true),
    );
    if (!next.ok) return answered(null, "failed");

    const { calls, text } = next.reading;
    if (calls.length === 0) {
      const check = checkVerdict(text, tool, "final");
      return check.ok ? answered(check.verdict.cited, "ok", check.verdict) : answered(null, "failed");
    }
    // A call here is the second one, allowed once and only where tools were offered. A third isn't made.
    const [call] = calls;
    if (calls.length > 1 || forms.final !== "replay" || toolCalls >= MAX_TOOL_CALLS || call.name !== prompts.tool.name) {
      return answered(null, "failed");
    }
    const args = parseToolArgs(call.arguments, q.text);
    if (args === undefined) return answered(null, "failed");
    tool = await runTool(args, next.reading, call);
  }
}

// One user message: the location line first (the instructions say so), then the question as typed, then any `extra`.
function userMessage(shared: boolean, ...texts: string[]): ResponseInputItem {
  return {
    type: "message",
    role: "user",
    content: [`Location shared: ${shared ? "yes" : "no"}`, ...texts].map((text) => ({ type: "input_text" as const, text })),
  };
}
