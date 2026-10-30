// Ask's one log line per question (spec §4.9, C721). Only these fields are ever written, so a question, a
// transcript, a place, a point, a device id, a report id or a key can't reach the log through it. `msg` is the
// line's own ("ask"). audio_ms and transcribe_ms are the spoken route's, which Ask doesn't serve yet (typed only).
export const ASK_LOG_FIELDS = [
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
] as const;

export type AskLogField = (typeof ASK_LOG_FIELDS)[number];

// Writes one JSON line with msg "ask" and the named fields it was given; any other key is dropped, and a field
// given as undefined is left out (null stays).
export function logAsk(fields: Partial<Record<AskLogField, unknown>>): void {
  const line: Record<string, unknown> = { msg: "ask" };
  for (const name of ASK_LOG_FIELDS) {
    if (Object.hasOwn(fields, name) && fields[name] !== undefined) line[name] = fields[name];
  }
  console.log(JSON.stringify(line));
}
