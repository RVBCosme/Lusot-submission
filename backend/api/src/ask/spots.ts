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

// The tool's place against the list: the longest name or alias the place holds, else a place that is only a
// road's name, which finds the road's one spot or, when the list has several, all of them (C733).
export function matchPlace(place: string, spots: Spot[] = SPOTS): { spot: Spot } | { roadSpots: Spot[] } | undefined {
  const text = normalize(place);
  if (text === "") return undefined;
  const spot = longestFormIn(text, formsOf(spots));
  if (spot) return { spot };
  const onRoad = spots.filter((candidate) => candidate.roads.some((road) => normalize(road) === text));
  if (onRoad.length === 1) return { spot: onRoad[0] };
  if (onRoad.length > 1) return { roadSpots: onRoad };
  return undefined;
}

// For the plain list: a question names a spot only by a name or an alias, never by a road alone.
export function findSpotIn(question: string, spots: Spot[] = SPOTS): Spot | undefined {
  return longestFormIn(normalize(question), formsOf(spots));
}

// The display names, sent to the transcription as keywords.
export function spotKeywords(spots: Spot[] = SPOTS): string[] {
  return spots.map((spot) => spot.name);
}
