import { afterEach, describe, expect, it, vi } from "vitest";
import { ASK_LOG_FIELDS, logAsk } from "../../src/ask/log";

afterEach(() => {
  vi.restoreAllMocks();
});

// Every line written through console, as the arguments it got.
function capture(): unknown[][] {
  const calls: unknown[][] = [];
  for (const method of ["log", "info", "warn", "error", "debug"] as const) {
    vi.spyOn(console, method).mockImplementation((...args: unknown[]) => {
      calls.push(args);
    });
  }
  return calls;
}

describe("the ask log line (spec §4.9)", () => {
  it("names the spec's fields, and msg is the line's own", () => {
    expect([...ASK_LOG_FIELDS]).toEqual([
      "route",
      "status",
      "code",
      "source",
      "fallback",
      "kind",
      "crossing",
      "vehicle",
      "place_source",
      "nominatim",
      "reports",
      "demo",
      "cited",
      "tool_calls",
      "final",
      "meta_calls",
      "meta_status",
      "input_tokens",
      "output_tokens",
      "reasoning_tokens",
      "audio_ms",
      "transcribe_ms",
      "model_ms",
      "ms",
      "error",
    ]);
  });

  it("writes one JSON line with msg ask and the fields it was given", () => {
    const calls = capture();

    logAsk({ route: "ask", status: 200, source: "model", meta_calls: 2, meta_status: null, final: "ok" });

    expect(calls).toHaveLength(1);
    expect(calls[0]).toHaveLength(1);
    expect(JSON.parse(calls[0][0] as string)).toEqual({
      msg: "ask",
      route: "ask",
      status: 200,
      source: "model",
      meta_calls: 2,
      meta_status: null,
      final: "ok",
    });
  });

  it("drops any key the spec doesn't name, msg included", () => {
    const calls = capture();
    const fields = { route: "ask", question: "sentinel-question", lat: 14.6, device: "device-sentinel", msg: "other" };

    logAsk(fields as Parameters<typeof logAsk>[0]);

    const line = calls[0][0] as string;
    expect(JSON.parse(line)).toEqual({ msg: "ask", route: "ask" });
    for (const secret of ["sentinel-question", "14.6", "device-sentinel", "other"]) expect(line).not.toContain(secret);
  });

  it("leaves out a field given as undefined, and keeps one given as null", () => {
    const calls = capture();

    logAsk({ route: "ask", meta_status: undefined, nominatim: null });

    expect(JSON.parse(calls[0][0] as string)).toEqual({ msg: "ask", route: "ask", nominatim: null });
  });
});
