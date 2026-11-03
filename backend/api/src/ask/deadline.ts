// Ask's time budget, in ms from the handler's start (spec §4.1).
export const BUDGET = {
  // A spoken question is transcribed by here. 4000 until Nov 3, when live 6 to 7 s clips ran past it: the steps
  // before the call take about 1.2 s, which left the transcription about 2.8 s.
  transcribeBy: 7000,
  modelBy: 7500, // the model's last turn ends by here
  answerBy: 8500, // the answer is on its way by here
  // A spoken question's model and answer marks come this much later (Deadline.spoken), so its turns have about a
  // typed question's room after its transcript, which took about 3 s live. 2500 until Nov 3, when that left too little
  // for Nominatim. Its settle and pause marks stay, inside the 15 s.
  voiceExtra: 3500,
  // After the answer, inside the API function's 15 s timeout (C736): the spend write ends by here, or counts as
  // failed, and the pause that follows ends by the next mark. 12000 until Nov 3; a spoken answer's mark is now 12000.
  settleBy: 12500,
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
    private readonly extraMs = 0,
  ) {}

  // The same start, for a spoken question once it is transcribed: its model and answer marks move voiceExtra later.
  spoken(): Deadline {
    return new Deadline(this.startMs, this.now, BUDGET.voiceExtra);
  }

  // The ms left before the mark; never negative.
  remainingMs(byMs: number): number {
    const at = byMs === BUDGET.modelBy || byMs === BUDGET.answerBy ? byMs + this.extraMs : byMs;
    return Math.max(0, this.startMs + at - this.now());
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
