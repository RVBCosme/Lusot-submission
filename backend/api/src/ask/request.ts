import type { Here } from "./tool";
import { decodeAudio } from "./wav";

const MAX_QUESTION_CHARS = 300; // spec §5.1, once trimmed
const MAX_ACCURACY_M = 100; // spec §4.6: "here" needs a fix of 100 m or better
const MAX_VOICE_BYTES = 1_100_000; // spec §5.2: the spoken question's whole body

// POST /ask's body (spec §5.1): the trimmed question, and `here` when the app sent one. Anything else is a detail
// for a 400 bad_request (spec §5.4), in MS1's style. The question's length counts characters, not UTF-16 units.
export function parseQuestion(raw: string | undefined): { question: string; here?: Here } | { detail: string } {
  const parsed = parseObject(raw);
  if (!parsed.ok) return { detail: parsed.detail };
  const { question, here } = parsed.body;
  if (typeof question !== "string") return { detail: "question must be a string" };
  const trimmed = question.trim();
  const chars = Array.from(trimmed).length;
  if (chars < 1 || chars > MAX_QUESTION_CHARS) return { detail: `question must be 1 to ${MAX_QUESTION_CHARS} characters` };
  const point = parseHere(here);
  if ("detail" in point) return point;
  return point.here === undefined ? { question: trimmed } : { question: trimmed, here: point.here };
}

// POST /ask/voice's body (spec §5.2): the audio's bytes, and `here` when the app sent one. A body over 1.1 MB, or an
// `audio` that isn't canonical base64, is bad_audio, before any WAV check (§5.4); the rest are bad_request details.
export function parseVoice(
  raw: string | undefined,
): { audio: Uint8Array; here?: Here } | { error: "bad_request" | "bad_audio"; detail?: string } {
  if (raw !== undefined && Buffer.byteLength(raw, "utf8") > MAX_VOICE_BYTES) return { error: "bad_audio" };
  const parsed = parseObject(raw);
  if (!parsed.ok) return { error: "bad_request", detail: parsed.detail };
  const audio = decodeAudio(parsed.body.audio);
  if (audio === undefined) return { error: "bad_audio" };
  const point = parseHere(parsed.body.here);
  if ("detail" in point) return { error: "bad_request", detail: point.detail };
  return point.here === undefined ? { audio } : { audio, here: point.here };
}

function parseObject(raw: string | undefined): { ok: true; body: Record<string, unknown> } | { ok: false; detail: string } {
  let body: unknown;
  try {
    body = JSON.parse(raw ?? "");
  } catch {
    return { ok: false, detail: "body must be JSON" };
  }
  if (typeof body !== "object" || body === null || Array.isArray(body)) return { ok: false, detail: "body must be a JSON object" };
  return { ok: true, body: body as Record<string, unknown> };
}

// `here`'s three fields, or none when it wasn't sent.
function parseHere(here: unknown): { here?: Here } | { detail: string } {
  if (here === undefined) return {};
  if (typeof here !== "object" || here === null || Array.isArray(here)) return { detail: "here must be an object" };
  const { lat, lng, accuracyM } = here as Record<string, unknown>;
  // lat and lng as MS1's upload checks them.
  if (!inRange(lat, -90, 90)) return { detail: "here.lat must be a number from -90 to 90" };
  if (!inRange(lng, -180, 180)) return { detail: "here.lng must be a number from -180 to 180" };
  if (!inRange(accuracyM, 0, MAX_ACCURACY_M)) return { detail: `here.accuracyM must be a number from 0 to ${MAX_ACCURACY_M}` };
  return { here: { lat, lng, accuracyM } };
}

function inRange(value: unknown, min: number, max: number): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= min && value <= max;
}
