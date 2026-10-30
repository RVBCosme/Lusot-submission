import { loadPrompts } from "./prompts";
import { normalize } from "./text";

// The word lists in the prompt folder are written for normalised text.
const hasAny = (patterns: RegExp[], text: string): boolean => {
  const normalised = normalize(text);
  return patterns.some((pattern) => pattern.test(normalised));
};

export const hasCrossingWords = (text: string): boolean => hasAny(loadPrompts().crossing, text);
export const hasHereWords = (text: string): boolean => hasAny(loadPrompts().here, text);
export const hasHeavyWords = (text: string): boolean => hasAny(loadPrompts().heavy, text);
export const hasWalkingWords = (text: string): boolean => hasAny(loadPrompts().walking, text);

type Stated = { minutes: number; inHours: boolean; start: number; end: number };

// Every `time` match in the normalised text: its number (one when it has none, as in "an hour"), in hours when it
// says hour or oras.
function timesIn(text: string): Stated[] {
  const found: Stated[] = [];
  for (const pattern of loadPrompts().time) {
    for (const match of text.matchAll(new RegExp(pattern.source, `${pattern.flags}g`))) {
      const digits = /^\d+/.exec(match[0]);
      const amount = digits ? Number(digits[0]) : 1;
      const inHours = /hour|oras/.test(match[0]);
      found.push({ minutes: inHours ? amount * 60 : amount, inHours, start: match.index, end: match.index + match[0].length });
    }
  }
  return found;
}

// The window a question states, in minutes, or undefined when it states none. An hour amount directly followed by
// a minutes amount ("1 hour 30 minutes", "2 hours and 30 minutes") or by "and a half" is one window, and their
// sum counts. Of several separate windows, the largest counts.
export function statedMinutes(text: string): number | undefined {
  const normalised = normalize(text);
  const found = timesIn(normalised);
  let largest: number | undefined;
  for (const time of found) {
    let total = time.minutes;
    if (time.inHours) {
      const next = found.find((other) => !other.inHours && /^ (?:cor )?$/.test(normalised.slice(time.end, other.start)));
      if (next) total += next.minutes;
      else if (/^ (?:cor )?(?:a half|kalahati)\b/.test(normalised.slice(time.end))) total += 30;
    }
    if (largest === undefined || total > largest) largest = total;
  }
  return largest;
}
