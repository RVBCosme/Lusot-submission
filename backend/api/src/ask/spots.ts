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

// Does the normalised text hold "<road A> cor <road B>" for two different roads of the spot, with nothing else
// between them? A road's occurrence takes in the road-type word after its key ("UN Ave" in "UN Ave cor Taft").
// Two roads in one text without a corner word between them are not a corner ("EDSA north bound").
function holdsTwoRoads(text: string, spot: Spot): boolean {
  const words = text.split(" ");
  const spans: { key: string; start: number; end: number }[] = [];
  for (const key of new Set(spot.roads.map(roadKey))) {
    if (key === "") continue;
    const parts = key.split(" ");
    for (let start = 0; start + parts.length <= words.length; start++) {
      if (!parts.every((part, i) => words[start + i] === part)) continue;
      const end = start + parts.length;
      spans.push({ key, start, end: ROAD_TYPES.has(words[end]) ? end + 1 : end });
    }
  }
  return spans.some((a) => spans.some((b) => a.key !== b.key && words[a.end] === "cor" && b.start === a.end + 1));
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

// Meta's transcription refuses a keyword over 30 characters with a 400 (Oct 31), and 97 keywords is the most it has
// been shown to take (a test call on Nov 1). A keyword's length is counted in UTF-8 bytes, the strictest count, since
// Meta doesn't say which it uses: "España" is 6 characters but 7 bytes.
const MAX_KEYWORD_BYTES = 30;
const MAX_KEYWORDS = 97;

// The three spots whose names are too long for a keyword and whose landmark no road of theirs names, each with one of
// its own aliases to send instead. The other long names are corners, and their roads carry them.
export const SHORT_FORMS: ReadonlyMap<string, string> = new Map([
  ["edsa-santolan", "EDSA Santolan"],
  ["oyster-plaza", "Oyster Plaza"],
  ["sucat-sm", "SM Sucat"],
]);

// Sent to the transcription as keywords: the display names that fit Meta's limit, then the short forms, then each
// spot's roads, each once, so a corner whose name is too long still biases toward its roads' names. Names come first,
// so the count cap drops roads before names.
export function spotKeywords(spots: Spot[] = SPOTS): string[] {
  const keywords = new Set<string>();
  const names = spots.map((spot) => spot.name);
  const shortForms = spots.flatMap((spot) => SHORT_FORMS.get(spot.id) ?? []);
  for (const word of [...names, ...shortForms, ...spots.flatMap((spot) => spot.roads)]) {
    if (Buffer.byteLength(word, "utf8") <= MAX_KEYWORD_BYTES) keywords.add(word);
  }
  return [...keywords].slice(0, MAX_KEYWORDS);
}
