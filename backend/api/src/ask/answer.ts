import type { PublicPin } from "../pins";
import type { AskPlace, Ranked, ToolArgs, ToolResult } from "./tool";
import { hasCrossingWords, hasHeavyWords, hasWalkingWords } from "./words";

const RADIUS_M = 300;
// C732's default window, used when no tool result says otherwise.
const DEFAULT_WINDOW_MIN = 180;
const MAX_LIVE = 5;
const MAX_DEMO = 3;

export type Fallback = "model_calls_paused" | "deadline" | "model_error" | "key_rejected" | "invalid_answer" | "no_tool_call";

// A report is the pin's own fields plus its distance, without the tool's ref or minutesAgo.
export type AskReport = PublicPin & { distanceM: number };

// Spec §5.3. The API returns data, never prose.
export type Answer = {
  source: "model" | "plain_list";
  fallback: Fallback | null;
  kind:
    | "reports"
    | "no_reports"
    | "place_too_broad"
    | "no_place"
    | "lookup_unavailable"
    | "outside_metro_manila"
    | "no_location"
    | "off_topic"
    | "no_speech";
  crossing: boolean;
  vehicle: "light" | "heavy" | "on_foot" | null;
  place: AskPlace | null;
  windowMin: number;
  radiusM: number;
  count: number;
  reports: AskReport[];
  demo: AskReport[];
  deepestId: string | null;
  cited: string[];
  suggestions: string[];
};

export type ModelVerdict = {
  kind: "depth" | "crossing" | "off_topic";
  vehicle: "light" | "heavy" | "on_foot" | "none";
  cited: string[];
};

const VERDICT_KINDS: readonly string[] = ["depth", "crossing", "off_topic"];
const VERDICT_VEHICLES: readonly string[] = ["light", "heavy", "on_foot", "none"];

type Invalid = { ok: false; fallback: "invalid_answer" | "no_tool_call" };

// The model's answer, checked by hand against ask_v1.answer.json (spec §4.3): exactly kind, vehicle and cited; the
// enums; `cited` deduplicated, a subset of the tool's refs, and holding r1 while live reports exist. Turn 1 must also
// have made a call unless it says off_topic, and a final turn can't say off_topic, which would hide what a call found.
export function checkVerdict(
  text: string,
  tool: ToolResult | undefined,
  turn: "first" | "final",
): { ok: true; verdict: ModelVerdict } | Invalid {
  const invalid: Invalid = { ok: false, fallback: "invalid_answer" };
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return invalid;
  }
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return invalid;
  const { kind, vehicle, cited } = raw as Record<string, unknown>;
  if (Object.keys(raw).length !== 3) return invalid;
  if (typeof kind !== "string" || !VERDICT_KINDS.includes(kind)) return invalid;
  if (typeof vehicle !== "string" || !VERDICT_VEHICLES.includes(vehicle)) return invalid;
  if (!Array.isArray(cited) || !cited.every((ref) => typeof ref === "string")) return invalid;

  if (kind === "off_topic" && turn === "final") return invalid;
  if (kind !== "off_topic" && tool === undefined) return { ok: false, fallback: "no_tool_call" };

  const refs = new Set([...(tool?.live ?? []), ...(tool?.demo ?? [])].map((r) => r.ref));
  const unique = [...new Set(cited as string[])];
  if (!unique.every((ref) => refs.has(ref))) return invalid;
  if ((tool?.live.length ?? 0) > 0 && !unique.includes("r1")) return invalid;

  return { ok: true, verdict: { kind: kind as ModelVerdict["kind"], vehicle: vehicle as ModelVerdict["vehicle"], cited: unique } };
}

export type Reading = {
  crossing: boolean;
  // Who said so: the model (a call's or the answer's kind), the question's crossing words, or both.
  crossingFrom: "model" | "words" | "both" | null;
  vehicle: "light" | "heavy" | "on_foot" | null;
};

// Code's reading of the question over both calls and the answer (spec §4.3, C711, C712). It can make the model's
// reading stricter, never looser.
export function classify(input: { calls: ToolArgs[]; verdict?: ModelVerdict; question: string }): Reading {
  const { calls, verdict, question } = input;
  const fromModel = calls.some((call) => call.kind === "crossing") || verdict?.kind === "crossing";
  const fromWords = hasCrossingWords(question);

  // A vehicle the model names (light or heavy) decides, by the heavy and light rules. Only when it names none does a
  // walking word give on_foot: "lakad" is also an errand and "wade" is how a vehicle crosses water, so a walking word
  // must not drop the class lines from a vehicle's question. A model-only on_foot is dropped: it holds only with a
  // walking word, and a wrong one would drop every class line.
  const said = [...calls.map((call) => call.vehicle), ...(verdict === undefined ? [] : [verdict.vehicle])];
  let vehicle: Reading["vehicle"] = null;
  if (said.includes("heavy") && hasHeavyWords(question)) vehicle = "heavy";
  else if (said.some((v) => v === "heavy" || v === "light")) vehicle = "light";
  else if (hasWalkingWords(question)) vehicle = "on_foot";

  return {
    crossing: fromModel || fromWords,
    crossingFrom: fromModel ? (fromWords ? "both" : "model") : fromWords ? "words" : null,
    vehicle,
  };
}

// The answer's kind. off_topic comes only from turn 1's kind, and only when no call found anything; otherwise the
// tool's status says which answer it is.
export function kindFor(tool: ToolResult | undefined, firstKind?: ModelVerdict["kind"]): Answer["kind"] {
  if (tool === undefined) return firstKind === "off_topic" ? "off_topic" : "no_place";
  switch (tool.status) {
    case "ok":
      return tool.live.length > 0 ? "reports" : "no_reports";
    case "place_not_found":
      return "no_place";
    default:
      return tool.status;
  }
}

const report = (r: Ranked): AskReport => ({ ...r.pin, distanceM: r.distanceM });

function build(
  tool: ToolResult | undefined,
  parts: Pick<Answer, "source" | "fallback" | "kind" | "crossing" | "vehicle" | "cited">,
): Answer {
  return {
    ...parts,
    place: tool?.place ?? null,
    windowMin: tool?.windowMin ?? DEFAULT_WINDOW_MIN,
    radiusM: RADIUS_M,
    count: tool?.count ?? 0,
    reports: (tool?.live ?? []).slice(0, MAX_LIVE).map(report),
    demo: (tool?.demo ?? []).slice(0, MAX_DEMO).map(report),
    // A demo pin is a past event, so it is never the report the summary is about.
    deepestId: tool?.live[0]?.pin.id ?? null,
    suggestions: tool?.suggestions ?? [],
  };
}

// The model's answer. `cited` is the final turn's checked refs, or null when that turn didn't run or failed: then the
// answer has no citations, and so no "Used" marks, but keeps its crossing and vehicle lines.
export function modelAnswer(
  tool: ToolResult | undefined,
  reading: Reading,
  cited: string[] | null,
  firstKind: ModelVerdict["kind"],
): Answer {
  const ids = new Map([...(tool?.live ?? []), ...(tool?.demo ?? [])].map((r) => [r.ref, r.pin.id]));
  const citedIds = [...new Set((cited ?? []).flatMap((ref) => ids.get(ref) ?? []))];
  return build(tool, {
    source: "model",
    fallback: null,
    kind: kindFor(tool, firstKind),
    crossing: reading.crossing,
    vehicle: reading.vehicle,
    cited: citedIds,
  });
}

// A spoken question in which the transcription heard nothing (spec §4.7): no place, no reports, nothing to read.
export function noSpeech(): Answer {
  return build(undefined, { source: "model", fallback: null, kind: "no_speech", crossing: false, vehicle: null, cited: [] });
}

// The plain list (spec §4.5): the same answer without the model's parts. No vehicle, no citations, and the crossing
// line only from the crossing words.
export function plainList(tool: ToolResult | undefined, question: string, fallback: Fallback): Answer {
  return build(tool, {
    source: "plain_list",
    fallback,
    kind: kindFor(tool),
    crossing: hasCrossingWords(question),
    vehicle: null,
    cited: [],
  });
}
