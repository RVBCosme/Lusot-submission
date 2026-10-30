import { distanceM, type PublicPin } from "../pins";
import type { Deadline } from "./deadline";
import { type Box, cleanPlace, type Geocoder, type GeoTrace } from "./nominatim";
import { matchPlace, type Spot } from "./spots";
import { normalize } from "./text";
import { statedMinutes } from "./words";

// MS3a's nine levels, shallowest first: MMDA's seven gauge levels plus below_gutter and above_chest.
export const LEVELS: readonly string[] = [
  "below_gutter",
  "gutter",
  "half_knee",
  "half_tire",
  "knee",
  "tire",
  "waist",
  "chest",
  "above_chest",
];

// A level's place on the scale, 0 for below_gutter; -1 for a name that isn't one.
export function levelIndex(level: string): number {
  return LEVELS.indexOf(level);
}

const RADIUS_M = 300;
const MAX_WINDOW_MIN = 180;
const MAX_LIVE = 5;
const MAX_DEMO = 3;
const MAX_SUGGESTIONS = 3;

export type ToolArgs = {
  place: string;
  here: boolean;
  sinceMin: number;
  kind: "depth" | "crossing";
  vehicle: "light" | "heavy" | "on_foot" | "none";
};

const KINDS: readonly string[] = ["depth", "crossing"];
const VEHICLES: readonly string[] = ["light", "heavy", "on_foot", "none"];

// The model's call, checked. Undefined for bad JSON, a wrong type or a value outside the enums (spec §4.2, step 1).
// The window follows C732: a value under 180 counts only when the question states a time, and never goes below it.
export function parseToolArgs(json: string, question: string): ToolArgs | undefined {
  let raw: unknown;
  try {
    raw = JSON.parse(json);
  } catch {
    return undefined;
  }
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return undefined;
  const { place, here, since_minutes: since, kind, vehicle } = raw as Record<string, unknown>;
  if (typeof place !== "string" || typeof here !== "boolean" || typeof since !== "number" || !Number.isInteger(since)) {
    return undefined;
  }
  if (typeof kind !== "string" || !KINDS.includes(kind) || typeof vehicle !== "string" || !VEHICLES.includes(vehicle)) {
    return undefined;
  }
  const stated = statedMinutes(question);
  const clamped = Math.min(MAX_WINDOW_MIN, Math.max(1, since));
  return {
    place: cleanPlace(place),
    here,
    sinceMin: stated === undefined ? MAX_WINDOW_MIN : Math.min(MAX_WINDOW_MIN, Math.max(clamped, stated)),
    kind: kind as ToolArgs["kind"],
    vehicle: vehicle as ToolArgs["vehicle"],
  };
}

export type Here = { lat: number; lng: number; accuracyM: number };
export type AskPlace = { name: string; source: "spots" | "nominatim" | "here" };
export type Ranked = { ref: string; pin: PublicPin; distanceM: number; minutesAgo: number };

export type ToolResult = {
  status: "ok" | "place_not_found" | "place_too_broad" | "outside_metro_manila" | "no_location" | "lookup_unavailable";
  // Set once the place resolved to something: a listed spot, a Nominatim result (even a wide or outside one) or "here".
  place?: AskPlace;
  // Set only with `ok`: the one point inside Metro Manila that the pins were read around.
  point?: { lat: number; lng: number };
  windowMin: number;
  // At most 5 live and 3 demo pins, the ones the answer shows. `count` is every live pin kept.
  live: Ranked[];
  demo: Ranked[];
  count: number;
  suggestions: string[];
  geo: GeoTrace | null;
};

export type ToolCtx = {
  here?: Here;
  geocoder?: Geocoder;
  nearbyPins: (lat: number, lng: number, radiusM: 300) => Promise<PublicPin[]>;
  inMetroManila: (lat: number, lng: number) => boolean;
  spots: Spot[];
  nowS: number;
  deadline: Deadline;
};

// A place that resolved to a point. `wideBox` is set when it came from Nominatim as an area, not a point.
type Resolved = { place: AskPlace; point: { lat: number; lng: number }; wideBox?: Box };

// get_reports: the place to one point, the point checked, then the published pins within 300 m, ranked.
// A failed pins read throws, and the caller answers for it. Nothing here logs a place, a point or a device.
export async function runGetReports(args: ToolArgs, ctx: ToolCtx): Promise<ToolResult> {
  let geo: GeoTrace | null = null;
  const refuse = (
    status: ToolResult["status"],
    more: Partial<Pick<ToolResult, "place" | "suggestions">> = {},
  ): ToolResult => ({ status, windowMin: args.sinceMin, live: [], demo: [], count: 0, suggestions: [], geo, ...more });

  let resolved: Resolved;
  if (args.here) {
    if (ctx.here === undefined) return refuse("no_location");
    resolved = { place: { name: "here", source: "here" }, point: { lat: ctx.here.lat, lng: ctx.here.lng } };
  } else if (normalize(args.place) === "") {
    return refuse("place_not_found");
  } else {
    const match = matchPlace(args.place, ctx.spots);
    if (match !== undefined && "roadSpots" in match) return refuse("place_too_broad", { suggestions: names(match.roadSpots) });
    if (match !== undefined) {
      resolved = { place: { name: match.spot.name, source: "spots" }, point: { lat: match.spot.lat, lng: match.spot.lng } };
    } else {
      if (ctx.geocoder === undefined) return refuse("lookup_unavailable");
      const { result, trace } = await ctx.geocoder.geocode(args.place, ctx.deadline);
      geo = trace;
      if (result === undefined) return refuse("lookup_unavailable");
      if (result.status === "not_found") return refuse("place_not_found");
      resolved = {
        place: { name: result.name, source: "nominatim" },
        point: { lat: result.lat, lng: result.lng },
        ...(result.spanM > RADIUS_M && { wideBox: result.box }),
      };
    }
  }

  const { place, point, wideBox } = resolved;
  // Metro Manila comes before the breadth test: a town outside is outside, however wide (C733).
  if (!ctx.inMetroManila(point.lat, point.lng)) return refuse("outside_metro_manila", { place });
  if (wideBox !== undefined) {
    const { south, north, west, east } = wideBox;
    const inside = ctx.spots.filter((s) => s.lat >= south && s.lat <= north && s.lng >= west && s.lng <= east);
    return refuse("place_too_broad", { place, suggestions: names(inside) });
  }

  const pins = await ctx.nearbyPins(point.lat, point.lng, RADIUS_M);
  const nowMs = ctx.nowS * 1000;
  const sinceMs = nowMs - args.sinceMin * 60_000;
  const ranked = (ref: string, pin: PublicPin): Ranked => ({
    ref,
    pin,
    distanceM: Math.round(distanceM(point, pin)),
    minutesAgo: Math.max(0, Math.floor((nowMs - Date.parse(pin.capturedAt)) / 60_000)),
  });

  // Deepest first, and a tie goes to the newer photo. A floor ranks at its level.
  const kept = pins
    .filter((pin) => pin.mode === "live" && Date.parse(pin.capturedAt) >= sinceMs)
    .sort((a, b) => levelIndex(b.level) - levelIndex(a.level) || Date.parse(b.capturedAt) - Date.parse(a.capturedAt));
  // A demo pin is a past event, so it skips the window.
  const demo = pins
    .filter((pin) => pin.mode === "demo")
    .map((pin) => ({ pin, away: distanceM(point, pin) }))
    .sort((a, b) => a.away - b.away);

  return {
    status: "ok",
    place,
    point,
    windowMin: args.sinceMin,
    live: kept.slice(0, MAX_LIVE).map((pin, i) => ranked(`r${i + 1}`, pin)),
    demo: demo.slice(0, MAX_DEMO).map(({ pin }, i) => ranked(`d${i + 1}`, pin)),
    count: kept.length,
    suggestions: [],
    geo,
  };
}

const names = (spots: Spot[]): string[] => spots.slice(0, MAX_SUGGESTIONS).map((s) => s.name);

// What the model reads: summaries only, built field by field. No coordinates, report id, credit or photo place.
export function toModelOutput(result: ToolResult): string {
  return JSON.stringify({
    status: result.status,
    place: result.place?.name,
    window_minutes: result.windowMin,
    radius_m: RADIUS_M,
    count: result.count,
    reports: result.live.slice(0, MAX_LIVE).map((r) => ({
      ref: r.ref,
      level: r.pin.level,
      level_is_floor: r.pin.levelIsFloor,
      passability: r.pin.passability,
      minutes_ago: r.minutesAgo,
      distance_m: r.distanceM,
    })),
    demo_reports: result.demo.slice(0, MAX_DEMO).map((r) => ({
      ref: r.ref,
      level: r.pin.level,
      year: new Date(r.pin.capturedAt).getUTCFullYear(),
      distance_m: r.distanceM,
    })),
  });
}
