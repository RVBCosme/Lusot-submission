import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BUDGET, Deadline } from "../../src/ask/deadline";

const START = Date.parse("2026-10-30T10:00:00Z");

describe("BUDGET", () => {
  it("holds the spec's times, counted in ms from the handler's start", () => {
    expect(BUDGET).toEqual({
      transcribeBy: 4000,
      modelBy: 7500,
      answerBy: 8500,
      settleBy: 12000,
      pauseBy: 14000,
      minTurn: 1500,
      minNominatim: 2500,
      nominatimCall: 1500,
    });
  });

  it("settles the spend, then pauses, inside the API function's 15 s", () => {
    expect(BUDGET.answerBy).toBeLessThan(BUDGET.settleBy);
    expect(BUDGET.settleBy).toBeLessThan(BUDGET.pauseBy);
    expect(BUDGET.pauseBy).toBeLessThan(15_000);
  });
});

describe("Deadline", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(START);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  const deadline = (startMs: number) => new Deadline(startMs, () => Date.now());

  it("remainingMs and signal count from the handler's start", () => {
    // The handler started 1 s before this Deadline was built, so the clock is already 1 s in.
    const d = deadline(START - 1000);
    const signal = d.signal(BUDGET.modelBy);

    expect(d.remainingMs(BUDGET.modelBy)).toBe(6500);
    expect(d.remainingMs(BUDGET.answerBy)).toBe(7500);

    vi.advanceTimersByTime(2000);
    expect(d.remainingMs(BUDGET.modelBy)).toBe(4500);
    expect(d.remainingMs(BUDGET.minNominatim)).toBe(0);

    vi.advanceTimersByTime(4499);
    expect(signal.aborted).toBe(false);
    vi.advanceTimersByTime(1);
    expect(signal.aborted).toBe(true);
    expect(d.remainingMs(BUDGET.modelBy)).toBe(0);
  });

  it("each signal ends at its own mark", () => {
    const d = deadline(START);
    const early = d.signal(BUDGET.transcribeBy);
    const late = d.signal(BUDGET.answerBy);

    vi.advanceTimersByTime(BUDGET.transcribeBy);

    expect(early.aborted).toBe(true);
    expect(late.aborted).toBe(false);
  });

  it("a mark already past gives no negative time and a signal that is already aborted", () => {
    const d = deadline(START);
    vi.advanceTimersByTime(9000);

    expect(d.remainingMs(BUDGET.answerBy)).toBe(0);
    expect(d.signal(BUDGET.answerBy).aborted).toBe(true);
  });
});
