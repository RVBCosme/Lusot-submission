// Ask's time budget, in ms from the handler's start (spec §4.1).
export const BUDGET = {
  transcribeBy: 4000, // a spoken question is transcribed by here
  modelBy: 7500, // the model's last turn ends by here
  answerBy: 8500, // the answer is on its way by here
  // After the answer, inside the API function's 15 s timeout (C736): the spend write ends by here, or counts as
  // failed, and the pause that follows ends by the next mark.
  settleBy: 12000,
  pauseBy: 14000,
  minTurn: 1500, // a model turn starts only with this much left
  minNominatim: 2500, // Nominatim is asked only with this much left before modelBy: a 1 s wait and a 1.5 s call
  nominatimCall: 1500, // Nominatim's own timeout
} as const;

// Counts every mark from the handler's start, so a late-built Deadline still knows how long the handler has run.
export class Deadline {
  constructor(
    private readonly startMs: number,
    private readonly now: () => number,
  ) {}

  // The ms left before the mark; never negative.
  remainingMs(byMs: number): number {
    return Math.max(0, this.startMs + byMs - this.now());
  }

  // A signal that aborts when the mark arrives; already aborted when it has.
  signal(byMs: number): AbortSignal {
    const controller = new AbortController();
    const left = this.remainingMs(byMs);
    if (left === 0) controller.abort();
    else setTimeout(() => controller.abort(), left).unref();
    return controller.signal;
  }
}
