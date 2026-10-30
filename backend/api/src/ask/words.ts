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

// What one `time` match states: its number (one when it has none, as in "an hour"), in hours when it says hour or oras.
function minutesIn(match: string): number {
  const digits = /^\d+/.exec(match);
  const amount = digits ? Number(digits[0]) : 1;
  return /hour|oras/.test(match) ? amount * 60 : amount;
}

// The window a question states, in minutes: the largest when it states several, undefined when it states none.
export function statedMinutes(text: string): number | undefined {
  const normalised = normalize(text);
  let largest: number | undefined;
  for (const pattern of loadPrompts().time) {
    for (const match of normalised.matchAll(new RegExp(pattern.source, `${pattern.flags}g`))) {
      const minutes = minutesIn(match[0]);
      if (largest === undefined || minutes > largest) largest = minutes;
    }
  }
  return largest;
}
