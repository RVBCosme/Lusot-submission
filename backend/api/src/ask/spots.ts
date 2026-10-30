import spotsJson from "../data/spots.json";
import { normalize } from "./text";

export type Spot = { id: string; name: string; city: string; lat: number; lng: number; roads: string[]; aliases: string[] };

export const SPOTS: Spot[] = spotsJson;

type Form = { text: string; spot: Spot };

// Each spot's display name and aliases, normalised.
function formsOf(spots: Spot[]): Form[] {
  return spots
    .flatMap((spot) => [spot.name, ...spot.aliases].map((form) => ({ text: normalize(form), spot })))
    .filter((form) => form.text !== "");
}

// The spot whose longest form sits in the text on word boundaries (normalised text has single spaces only).
// A form equal to the whole text is the longest one a text can hold, so an exact match wins here too.
function longestFormIn(text: string, forms: Form[]): Spot | undefined {
  const padded = ` ${text} `;
  let best: Form | undefined;
  for (const form of forms) {
    if (padded.includes(` ${form.text} `) && (best === undefined || form.text.length > best.text.length)) best = form;
  }
  return best?.spot;
}

const ROAD_TYPES = new Set(["avenue", "ave", "boulevard", "blvd", "street", "st", "road", "rd", "highway", "hwy"]);

// A road's normalised name without a trailing road-type word, so "Aurora Blvd" and "Aurora Boulevard" are one road.
// Only the corner step compares roads this way; a whole-road place compares the full normalised name.
export function roadKey(road: string): string {
  const words = normalize(road).split(" ");
  if (words.length > 1 && ROAD_TYPES.has(words[words.length - 1])) words.pop();
  return words.join(" ");
}

// Does the normalised text name two different roads of the spot, one after the other without overlapping?
function holdsTwoRoads(text: string, spot: Spot): boolean {
  const words = text.split(" ");
  const spans: { key: string; start: number; end: number }[] = [];
  for (const key of new Set(spot.roads.map(roadKey))) {
    if (key === "") continue;
    const parts = key.split(" ");
    for (let start = 0; start + parts.length <= words.length; start++) {
      if (parts.every((part, i) => words[start + i] === part)) spans.push({ key, start, end: start + parts.length });
    }
  }
  return spans.some((a) => spans.some((b) => a.key !== b.key && a.end <= b.start));
}

// A corner by its roads: the spot that is the only one holding two different roads of the text.
function cornerIn(text: string, spots: Spot[]): Spot | undefined {
  const holders = spots.filter((spot) => holdsTwoRoads(text, spot));
  return holders.length === 1 ? holders[0] : undefined;
}

// The tool's place against the list: the longest name or alias the place holds, else the one spot that holds two
// of the place's roads, else a place that is only a road's name, which finds the road's one spot or, when the
// list has several, all of them (C733).
export function matchPlace(place: string, spots: Spot[] = SPOTS): { spot: Spot } | { roadSpots: Spot[] } | undefined {
  const text = normalize(place);
  if (text === "") return undefined;
  const spot = longestFormIn(text, formsOf(spots)) ?? cornerIn(text, spots);
  if (spot) return { spot };
  const onRoad = spots.filter((candidate) => candidate.roads.some((road) => normalize(road) === text));
  if (onRoad.length === 1) return { spot: onRoad[0] };
  if (onRoad.length > 1) return { roadSpots: onRoad };
  return undefined;
}

// For the plain list: a question names a spot by a name or an alias, or by two of its roads, never by one road alone.
export function findSpotIn(question: string, spots: Spot[] = SPOTS): Spot | undefined {
  const text = normalize(question);
  return longestFormIn(text, formsOf(spots)) ?? cornerIn(text, spots);
}

// The display names, sent to the transcription as keywords.
export function spotKeywords(spots: Spot[] = SPOTS): string[] {
  return spots.map((spot) => spot.name);
}
