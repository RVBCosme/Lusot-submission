import type { Here } from "./tool";

const MAX_QUESTION_CHARS = 300; // spec §5.1, once trimmed
const MAX_ACCURACY_M = 100; // spec §4.6: "here" needs a fix of 100 m or better

// POST /ask's body (spec §5.1): the trimmed question, and `here` when the app sent one. Anything else is a detail
// for a 400 bad_request (spec §5.4), in MS1's style. The question's length counts characters, not UTF-16 units.
export function parseQuestion(raw: string | undefined): { question: string; here?: Here } | { detail: string } {
  let body: unknown;
  try {
    body = JSON.parse(raw ?? "");
  } catch {
    return { detail: "body must be JSON" };
  }
  if (typeof body !== "object" || body === null || Array.isArray(body)) return { detail: "body must be a JSON object" };
  const { question, here } = body as Record<string, unknown>;
  if (typeof question !== "string") return { detail: "question must be a string" };
  const trimmed = question.trim();
  const chars = Array.from(trimmed).length;
  if (chars < 1 || chars > MAX_QUESTION_CHARS) return { detail: `question must be 1 to ${MAX_QUESTION_CHARS} characters` };
  if (here === undefined) return { question: trimmed };

  if (typeof here !== "object" || here === null || Array.isArray(here)) return { detail: "here must be an object" };
  const { lat, lng, accuracyM } = here as Record<string, unknown>;
  // lat and lng as MS1's upload checks them.
  if (!inRange(lat, -90, 90)) return { detail: "here.lat must be a number from -90 to 90" };
  if (!inRange(lng, -180, 180)) return { detail: "here.lng must be a number from -180 to 180" };
  if (!inRange(accuracyM, 0, MAX_ACCURACY_M)) return { detail: `here.accuracyM must be a number from 0 to ${MAX_ACCURACY_M}` };
  return { question: trimmed, here: { lat, lng, accuracyM } };
}

function inRange(value: unknown, min: number, max: number): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= min && value <= max;
}
