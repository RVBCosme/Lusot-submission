import { describe, expect, it } from "vitest";
import {
  checkVerdict,
  classify,
  kindFor,
  modelAnswer,
  plainList,
  type Answer,
  type Fallback,
  type ModelVerdict,
  type Reading,
} from "../../src/ask/answer";
import type { Ranked, ToolArgs, ToolResult } from "../../src/ask/tool";
import type { PublicPin } from "../../src/pins";

const NOW_MS = Date.parse("2026-10-30T10:06:40Z");

let counter = 0;
// A live knee pin, taken `minutesAgo` before NOW_MS.
function pin(fields: Partial<PublicPin> = {}, minutesAgo = 10): PublicPin {
  return {
    id: `r_${(counter++).toString(16).padStart(32, "0")}`,
    lat: 14.6095,
    lng: 120.9894,
    gpsAccuracyM: 12,
    capturedAt: new Date(NOW_MS - minutesAgo * 60_000).toISOString(),
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

// MS4's demo pin: a past event with its credit, place and event.
function demoPin(fields: Partial<PublicPin> = {}): PublicPin {
  return pin({
    mode: "demo",
    capturedAt: "2009-09-26T02:30:00Z",
    credit: "Photo by a donor",
    place: "Rizal Avenue, Manila",
    event: "Ondoy",
    ...fields,
  });
}

const ranked = (ref: string, p: PublicPin, distanceM = 40, minutesAgo = 10): Ranked => ({ ref, pin: p, distanceM, minutesAgo });

// A tool result with `live` pins already in the tool's order (deepest first) and `demo` pins nearest first.
function result(fields: Partial<ToolResult> = {}): ToolResult {
  return {
    status: "ok",
    place: { name: "España Blvd cor. Maceda St", source: "spots" },
    point: { lat: 14.6095, lng: 120.9894 },
    windowMin: 180,
    live: [],
    demo: [],
    count: 0,
    suggestions: [],
    geo: null,
    ...fields,
  };
}

// Five live reports, r1 the deepest, and one demo pin.
function fullResult(): ToolResult {
  const live = ["waist", "tire", "knee", "knee", "gutter"].map((level, i) => ranked(`r${i + 1}`, pin({ level }), 40 + i, 5 + i));
  return result({ live, demo: [ranked("d1", demoPin(), 120, 0)], count: 7 });
}

const verdict = (fields: Partial<ModelVerdict> = {}): ModelVerdict => ({ kind: "depth", vehicle: "none", cited: ["r1"], ...fields });
const text = (fields: Record<string, unknown> = {}) => JSON.stringify({ kind: "depth", vehicle: "none", cited: ["r1"], ...fields });
const call = (fields: Partial<ToolArgs> = {}): ToolArgs => ({
  place: "España Blvd cor. Maceda St",
  here: false,
  sinceMin: 180,
  kind: "depth",
  vehicle: "none",
  ...fields,
});

describe("checkVerdict", () => {
  it("accepts a good answer and returns it", () => {
    const check = checkVerdict(text({ cited: ["r1", "d1"] }), fullResult(), "final");
    expect(check).toEqual({ ok: true, verdict: { kind: "depth", vehicle: "none", cited: ["r1", "d1"] } });
  });

  it("bad JSON, a non-object, a missing field, a wrong type or a bad enum gives invalid_answer", () => {
    const tool = fullResult();
    for (const bad of ["", "{", "null", "[]", '"depth"', "42"]) {
      expect(checkVerdict(bad, tool, "final"), bad).toEqual({ ok: false, fallback: "invalid_answer" });
    }
    for (const field of ["kind", "vehicle", "cited"]) {
      const { [field]: _, ...rest } = JSON.parse(text());
      expect(checkVerdict(JSON.stringify(rest), tool, "final"), field).toEqual({ ok: false, fallback: "invalid_answer" });
    }
    const wrong: Record<string, unknown>[] = [
      { kind: "Depth" },
      { kind: "maybe" },
      { kind: 1 },
      { vehicle: "suv" },
      { vehicle: ["light"] },
      { cited: "r1" },
      { cited: null },
      { cited: [1] },
      { cited: [["r1"]] },
      { extra: true },
    ];
    for (const fields of wrong) {
      expect(checkVerdict(text(fields), tool, "final"), JSON.stringify(fields)).toEqual({ ok: false, fallback: "invalid_answer" });
    }
  });

  it("cited without r1 fails", () => {
    expect(checkVerdict(text({ cited: ["r2"] }), fullResult(), "final")).toEqual({ ok: false, fallback: "invalid_answer" });
    expect(checkVerdict(text({ cited: [] }), fullResult(), "final")).toEqual({ ok: false, fallback: "invalid_answer" });
    expect(checkVerdict(text({ cited: ["d1"] }), fullResult(), "final")).toEqual({ ok: false, fallback: "invalid_answer" });
  });

  it("a ref the tool didn't return fails", () => {
    expect(checkVerdict(text({ cited: ["r1", "r9"] }), fullResult(), "final")).toEqual({ ok: false, fallback: "invalid_answer" });
    expect(checkVerdict(text({ cited: ["r1", "d2"] }), fullResult(), "final")).toEqual({ ok: false, fallback: "invalid_answer" });
    expect(checkVerdict(text({ cited: ["r1", "R2"] }), fullResult(), "final")).toEqual({ ok: false, fallback: "invalid_answer" });
  });

  it("duplicates collapse", () => {
    const check = checkVerdict(text({ cited: ["r1", "r2", "r1", "r2", "d1", "d1"] }), fullResult(), "final");
    expect(check).toEqual({ ok: true, verdict: { kind: "depth", vehicle: "none", cited: ["r1", "r2", "d1"] } });
  });

  it("r1 is required only while live reports exist", () => {
    const demoOnly = result({ demo: [ranked("d1", demoPin())] });
    expect(checkVerdict(text({ cited: ["d1"] }), demoOnly, "final")).toMatchObject({ ok: true });
    expect(checkVerdict(text({ cited: [] }), demoOnly, "final")).toMatchObject({ ok: true });
    const nothing = result({ status: "place_not_found", place: undefined, point: undefined });
    expect(checkVerdict(text({ cited: [] }), nothing, "final")).toMatchObject({ ok: true });
    expect(checkVerdict(text({ cited: ["r1"] }), nothing, "final")).toEqual({ ok: false, fallback: "invalid_answer" });
  });

  it("a depth verdict without a tool call gives no_tool_call", () => {
    expect(checkVerdict(text({ cited: [] }), undefined, "first")).toEqual({ ok: false, fallback: "no_tool_call" });
    expect(checkVerdict(text({ kind: "crossing", cited: [] }), undefined, "first")).toEqual({ ok: false, fallback: "no_tool_call" });
  });

  it("off_topic needs no tool call", () => {
    const check = checkVerdict(text({ kind: "off_topic", cited: [] }), undefined, "first");
    expect(check).toEqual({ ok: true, verdict: { kind: "off_topic", vehicle: "none", cited: [] } });
  });

  it("an off_topic answer that cites a ref no tool returned fails", () => {
    expect(checkVerdict(text({ kind: "off_topic", cited: ["r1"] }), undefined, "first")).toEqual({
      ok: false,
      fallback: "invalid_answer",
    });
  });

  it("a final verdict of off_topic fails", () => {
    const tool = fullResult();
    expect(checkVerdict(text({ kind: "off_topic" }), tool, "final")).toEqual({ ok: false, fallback: "invalid_answer" });
    expect(checkVerdict(text({ kind: "off_topic", cited: [] }), tool, "final")).toEqual({ ok: false, fallback: "invalid_answer" });
    expect(checkVerdict(text({ kind: "off_topic", cited: [] }), undefined, "final")).toEqual({ ok: false, fallback: "invalid_answer" });
  });
});

describe("the answer", () => {
  it("the summary is the deepest live report, with the count of all of them", () => {
    const tool = fullResult();
    const answer = modelAnswer(tool, classify({ calls: [call()], verdict: verdict(), question: "gaano kalalim" }), ["r1"], "depth");
    expect(answer).toMatchObject({
      source: "model",
      fallback: null,
      kind: "reports",
      place: { name: "España Blvd cor. Maceda St", source: "spots" },
      windowMin: 180,
      radiusM: 300,
      count: 7,
      deepestId: tool.live[0]?.pin.id,
      suggestions: [],
    });
    expect(answer.reports.map((r) => r.level)).toEqual(["waist", "tire", "knee", "knee", "gutter"]);
    expect(answer.reports[0]).toMatchObject({ id: tool.live[0]?.pin.id, distanceM: 40, level: "waist", mode: "live" });
  });

  it("a report is the pin's own fields plus distanceM, without ref or minutesAgo", () => {
    const tool = fullResult();
    const answer = modelAnswer(tool, classify({ calls: [call()], question: "q" }), null, "depth");
    expect(answer.reports[0]).toEqual({ ...tool.live[0]?.pin, distanceM: 40 });
    expect(answer.demo[0]).toEqual({ ...tool.demo[0]?.pin, distanceM: 120 });
    for (const report of [...answer.reports, ...answer.demo]) {
      expect(report).not.toHaveProperty("ref");
      expect(report).not.toHaveProperty("minutesAgo");
    }
    // A demo pin keeps its credit, place and event (MS4's C523).
    expect(answer.demo[0]).toMatchObject({ credit: "Photo by a donor", place: "Rizal Avenue, Manila", event: "Ondoy" });
  });

  it("a demo pin is never deepestId", () => {
    const tool = result({ demo: [ranked("d1", demoPin({ level: "above_chest" }), 80, 0)] });
    expect(modelAnswer(tool, classify({ calls: [call()], question: "q" }), null, "depth").deepestId).toBeNull();
    const withLive = result({ live: [ranked("r1", pin({ level: "gutter" }))], demo: [ranked("d1", demoPin({ level: "above_chest" }))], count: 1 });
    const answer = modelAnswer(withLive, classify({ calls: [call()], question: "q" }), ["r1"], "depth");
    expect(answer.deepestId).toBe(withLive.live[0]?.pin.id);
  });

  it("no live report with a demo pin gives no_reports with the demo pin", () => {
    const d = demoPin();
    const tool = result({ demo: [ranked("d1", d, 80, 0)] });
    const answer = modelAnswer(tool, classify({ calls: [call()], question: "q" }), ["d1"], "depth");
    expect(answer).toMatchObject({ kind: "no_reports", count: 0, deepestId: null, reports: [], cited: [d.id] });
    expect(answer.demo).toEqual([{ ...d, distanceM: 80 }]);
  });

  it("at most 5 live reports and 3 demo pins", () => {
    const live = Array.from({ length: 8 }, (_, i) => ranked(`r${i + 1}`, pin()));
    const demo = Array.from({ length: 6 }, (_, i) => ranked(`d${i + 1}`, demoPin()));
    const tool = result({ live, demo, count: 8 });
    const reading = classify({ calls: [call()], question: "q" });
    for (const answer of [modelAnswer(tool, reading, null, "depth"), plainList(tool, "q", "deadline")]) {
      expect(answer.reports).toHaveLength(5);
      expect(answer.demo).toHaveLength(3);
      expect(answer.count).toBe(8);
    }
  });

  it("cited refs, live or demo, map to their pins' ids", () => {
    const tool = fullResult();
    const answer = modelAnswer(tool, classify({ calls: [call()], question: "q" }), ["r1", "r3", "d1"], "depth");
    expect(answer.cited).toEqual([tool.live[0]?.pin.id, tool.live[2]?.pin.id, tool.demo[0]?.pin.id]);
  });

  it("no citations gives an answer without used marks", () => {
    const tool = fullResult();
    const reading = classify({ calls: [call({ kind: "crossing", vehicle: "light" })], question: "kaya ba sedan namin" });
    const answer = modelAnswer(tool, reading, null, "crossing");
    expect(answer).toMatchObject({ source: "model", fallback: null, kind: "reports", crossing: true, vehicle: "light", cited: [] });
    expect(answer.reports).toHaveLength(5);
  });

  it("a place with no tool result: off_topic from turn 1, otherwise no_place, with empty lists", () => {
    const reading = classify({ calls: [], verdict: verdict({ kind: "off_topic", cited: [] }), question: "ano ang oras" });
    const off = modelAnswer(undefined, reading, [], "off_topic");
    expect(off).toEqual<Answer>({
      source: "model",
      fallback: null,
      kind: "off_topic",
      crossing: false,
      vehicle: null,
      place: null,
      windowMin: 180,
      radiusM: 300,
      count: 0,
      reports: [],
      demo: [],
      deepestId: null,
      cited: [],
      suggestions: [],
    });
    expect(modelAnswer(undefined, reading, null, "depth")).toMatchObject({ kind: "no_place", place: null, windowMin: 180, radiusM: 300 });
  });

  it("each status maps to its kind, with lookup_unavailable its own", () => {
    const status = (s: ToolResult["status"]) => kindFor(result({ status: s }));
    expect(status("place_not_found")).toBe("no_place");
    expect(status("place_too_broad")).toBe("place_too_broad");
    expect(status("outside_metro_manila")).toBe("outside_metro_manila");
    expect(status("no_location")).toBe("no_location");
    expect(status("lookup_unavailable")).toBe("lookup_unavailable");
    expect(status("ok")).toBe("no_reports");
    expect(kindFor(fullResult())).toBe("reports");
    expect(kindFor(result({ demo: [ranked("d1", demoPin())] }))).toBe("no_reports");
  });

  it("off_topic comes only from turn 1's kind", () => {
    expect(kindFor(undefined, "off_topic")).toBe("off_topic");
    expect(kindFor(undefined, "depth")).toBe("no_place");
    expect(kindFor(undefined, "crossing")).toBe("no_place");
    expect(kindFor(undefined)).toBe("no_place");
    // A call already found something: turn 1's kind can't hide it.
    expect(kindFor(fullResult(), "depth")).toBe("reports");
  });

  it("every answer carries the tool's suggestions", () => {
    const tool = result({ status: "place_too_broad", place: undefined, point: undefined, suggestions: ["A", "B", "C"] });
    const reading = classify({ calls: [call()], question: "q" });
    expect(modelAnswer(tool, reading, [], "depth")).toMatchObject({ kind: "place_too_broad", suggestions: ["A", "B", "C"] });
    expect(plainList(tool, "q", "deadline")).toMatchObject({ kind: "place_too_broad", suggestions: ["A", "B", "C"] });
    expect(modelAnswer(fullResult(), reading, null, "depth").suggestions).toEqual([]);
  });

  it("a refused lookup keeps its place when it has one, and has no reports", () => {
    const tool = result({ status: "outside_metro_manila", point: undefined, place: { name: "Bacoor", source: "nominatim" } });
    const answer = modelAnswer(tool, classify({ calls: [call()], question: "q" }), [], "depth");
    expect(answer).toMatchObject({ kind: "outside_metro_manila", place: { name: "Bacoor", source: "nominatim" }, reports: [], demo: [], count: 0 });
  });
});

describe("the plain list", () => {
  it("has no vehicle and no cited ids, and keeps the crossing words' flag", () => {
    const tool = fullResult();
    const asked = plainList(tool, "tawid ba sa España cor. Maceda, truck namin", "model_calls_paused");
    expect(asked).toMatchObject({
      source: "plain_list",
      fallback: "model_calls_paused",
      kind: "reports",
      crossing: true,
      vehicle: null,
      cited: [],
      deepestId: tool.live[0]?.pin.id,
    });
    expect(asked.reports).toHaveLength(5);
    const plain = plainList(tool, "gaano kalalim sa España cor. Maceda", "deadline");
    expect(plain).toMatchObject({ crossing: false, vehicle: null, cited: [], fallback: "deadline" });
  });

  it("carries its fallback, whichever it is", () => {
    const all: Fallback[] = ["model_calls_paused", "deadline", "model_error", "key_rejected", "invalid_answer", "no_tool_call"];
    for (const fallback of all) expect(plainList(fullResult(), "q", fallback).fallback).toBe(fallback);
  });

  it("with no place found, gives no_place with empty lists", () => {
    expect(plainList(undefined, "ano ang oras", "invalid_answer")).toEqual<Answer>({
      source: "plain_list",
      fallback: "invalid_answer",
      kind: "no_place",
      crossing: false,
      vehicle: null,
      place: null,
      windowMin: 180,
      radiusM: 300,
      count: 0,
      reports: [],
      demo: [],
      deepestId: null,
      cited: [],
      suggestions: [],
    });
  });
});

describe("the guards (spec AK12)", () => {
  const read = (question: string, calls: ToolArgs[], v?: ModelVerdict): Reading => classify({ calls, verdict: v, question });

  it("an SUV labelled heavy answers light", () => {
    const reading = read("kaya ba ng SUV namin", [call({ kind: "crossing", vehicle: "heavy" })], verdict({ kind: "crossing", vehicle: "heavy" }));
    expect(reading.vehicle).toBe("light");
    expect(modelAnswer(fullResult(), reading, ["r1"], "crossing").vehicle).toBe("light");
  });

  it("a truck labelled heavy stays heavy", () => {
    expect(read("kaya ba ng truck namin", [call({ vehicle: "heavy" })], verdict({ vehicle: "heavy" })).vehicle).toBe("heavy");
    expect(read("is a bus ok here", [call({ vehicle: "heavy" })]).vehicle).toBe("heavy");
    expect(read("10-wheeler ko", [call({ vehicle: "light" }), call({ vehicle: "heavy" })]).vehicle).toBe("heavy");
  });

  it("a truck word alone doesn't make it heavy: the model has to say so", () => {
    expect(read("truck namin", [call({ vehicle: "none" })]).vehicle).toBeNull();
    expect(read("truck namin", [call({ vehicle: "light" })]).vehicle).toBe("light");
  });

  it("a walking word makes on_foot even when the model says light", () => {
    expect(read("pwede ba akong maglakad dito", [call({ vehicle: "light" })], verdict({ vehicle: "light" })).vehicle).toBe("on_foot");
    expect(read("can I walk through there", [call({ vehicle: "none" })]).vehicle).toBe("on_foot");
    expect(read("lumusong ako sa baha", [call({ vehicle: "heavy" })]).vehicle).toBe("on_foot");
  });

  it("a model-only on_foot answers none, with its class lines", () => {
    const question = "gaano kalalim sa España cor. Maceda";
    const reading = read(question, [call({ vehicle: "on_foot" })], verdict({ vehicle: "on_foot" }));
    expect(reading.vehicle).toBeNull();
    expect(modelAnswer(fullResult(), reading, ["r1"], "depth").vehicle).toBeNull();
  });

  it("a model-only on_foot doesn't hide a light or heavy reading from the other call", () => {
    expect(read("sedan namin", [call({ vehicle: "on_foot" }), call({ vehicle: "light" })]).vehicle).toBe("light");
    expect(read("sedan namin", [call({ vehicle: "light" })], verdict({ vehicle: "on_foot" })).vehicle).toBe("light");
    expect(read("truck namin", [call({ vehicle: "on_foot" }), call({ vehicle: "heavy" })]).vehicle).toBe("heavy");
    expect(read("sedan namin", [call({ vehicle: "on_foot" }), call({ vehicle: "none" })], verdict({ vehicle: "on_foot" })).vehicle).toBeNull();
  });

  it("on_foot wins over heavy", () => {
    const reading = read("maglalakad ako, hindi truck", [call({ vehicle: "heavy" })], verdict({ vehicle: "heavy" }));
    expect(reading.vehicle).toBe("on_foot");
  });

  it("any light or heavy without a truck word is light; none stays null", () => {
    expect(read("sedan", [call({ vehicle: "light" })]).vehicle).toBe("light");
    expect(read("sedan", [], verdict({ vehicle: "heavy" })).vehicle).toBe("light");
    expect(read("sedan", [call({ vehicle: "none" })], verdict({ vehicle: "none" })).vehicle).toBeNull();
    expect(read("sedan", []).vehicle).toBeNull();
  });

  it("crossing comes from either call, the answer or the words", () => {
    expect(read("gaano kalalim", [call({ kind: "crossing" })]).crossing).toBe(true);
    expect(read("gaano kalalim", [call(), call({ kind: "crossing" })]).crossing).toBe(true);
    expect(read("gaano kalalim", [call()], verdict({ kind: "crossing" })).crossing).toBe(true);
    expect(read("tawid ba sa España", [call()], verdict()).crossing).toBe(true);
    expect(read("gaano kalalim", [call()], verdict()).crossing).toBe(false);
    expect(read("gaano kalalim", []).crossing).toBe(false);
  });

  it("says where the crossing reading came from", () => {
    expect(read("gaano kalalim", [call({ kind: "crossing" })]).crossingFrom).toBe("model");
    expect(read("tawid ba sa España", [call()], verdict()).crossingFrom).toBe("words");
    expect(read("tawid ba sa España", [call({ kind: "crossing" })]).crossingFrom).toBe("both");
    expect(read("gaano kalalim", [call()], verdict()).crossingFrom).toBeNull();
  });

  it("a crossing reading in the first call survives a second call that says depth", () => {
    const reading = read("gaano kalalim", [call({ kind: "crossing" }), call({ kind: "depth" })], verdict({ kind: "depth" }));
    expect(reading.crossing).toBe(true);
    expect(modelAnswer(fullResult(), reading, ["r1"], "crossing").crossing).toBe(true);
  });

  it("a final verdict of off_topic fails, so the reports stay", () => {
    expect(checkVerdict(text({ kind: "off_topic", cited: [] }), fullResult(), "final")).toEqual({ ok: false, fallback: "invalid_answer" });
    // The answer then comes from the calls, with no citations: its reports, crossing and vehicle lines intact.
    const reading = read("kaya ba ng truck", [call({ kind: "crossing", vehicle: "heavy" })]);
    expect(modelAnswer(fullResult(), reading, null, "crossing")).toMatchObject({
      kind: "reports",
      crossing: true,
      vehicle: "heavy",
      cited: [],
    });
  });
});
