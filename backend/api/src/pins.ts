import { type DynamoDBDocumentClient, QueryCommand, type QueryCommandInput, type QueryCommandOutput } from "@aws-sdk/lib-dynamodb";
import ngeohash from "ngeohash";
import { SCREEN_LINE } from "./copy";
import { json, type JsonResponse } from "./http";
import type { StopSwitch } from "./stopSwitch";

const MAX_RADIUS_M = 300; // C509: nine 6-character cells cover any 300 m circle
const MAX_PINS = 200;
const MAP_MEMO_MS = 30_000; // F18, C519: at most two feed-index reads per container per 30 s
const FEED_MEMO_MS = 60_000; // matches the feed's max-age
const EARTH_RADIUS_M = 6_371_008.8; // the mean radius

export interface PinDeps {
  ddb: DynamoDBDocumentClient;
  tableName: string;
  feedIndexName: string;
  isStopped: StopSwitch;
  inchesShown: boolean;
  now: () => number;
}

export type ReportItem = NonNullable<QueryCommandOutput["Items"]>[number];

export interface Point {
  lat: number;
  lng: number;
}

// Spec §4.4: what anyone may see of a published pin. Links come only from GET /reports/{id}.
export interface PublicPin extends Point {
  id: string;
  gpsAccuracyM: number | null;
  capturedAt: string;
  mode: "live" | "demo";
  level: string;
  landmark: string;
  passability: string;
  levelIsFloor: boolean;
  basis: { vehicles: number; people: number };
  flags: number;
  credit?: string;
  place?: string;
  event?: string;
  depthInMin?: number;
  depthInMax?: number;
}

// Built field by field, so nothing else stored on the item (readings, nudgeM, the claim, a key) gets out.
export function publicPin(item: ReportItem, inchesShown: boolean): PublicPin {
  const pin: PublicPin = {
    id: item.reportId,
    // C514: about 11 m, so a pin marks a spot, not a phone.
    lat: round4(item.lat),
    lng: round4(item.lng),
    gpsAccuracyM: item.gpsAccuracyM ?? null,
    capturedAt: item.capturedAt,
    mode: item.mode,
    level: item.level,
    landmark: item.landmark,
    passability: item.passability,
    levelIsFloor: item.levelIsFloor,
    basis: { vehicles: item.basis.vehicles, people: item.basis.people },
    flags: item.flags,
  };
  // C523: a demo pin carries its credit, place and event, so a judge can tell it isn't current.
  if (item.mode === "demo") {
    pin.credit = item.credit;
    pin.place = item.place;
    if (item.event !== undefined) pin.event = item.event;
  }
  // C515: the inches stay hidden until the release gate shows them.
  if (inchesShown) {
    pin.depthInMin = item.depthInMin;
    pin.depthInMax = item.depthInMax;
  }
  return pin;
}

// GET /reports?lat=&lng=&radius=. The point is the viewer's own location, so nothing here logs it.
export async function nearby(query: Record<string, string | undefined> | undefined, deps: PinDeps): Promise<JsonResponse> {
  const lat = parseNumber(query?.lat);
  const lng = parseNumber(query?.lng);
  if (!inRange(lat, -90, 90) || !inRange(lng, -180, 180)) return json(400, { error: "bad_point" });
  const radiusM = query?.radius === undefined ? MAX_RADIUS_M : parseNumber(query.radius);
  if (!(radiusM > 0 && radiusM <= MAX_RADIUS_M)) return json(400, { error: "bad_radius" });
  return json(200, { pins: await nearbyPins({ lat, lng }, radiusM, deps) });
}

// The published pins within radiusM of the point, newest first, at most 200.
export async function nearbyPins(point: Point, radiusM: number, deps: PinDeps): Promise<PublicPin[]> {
  const nowMs = deps.now();
  const nowS = Math.floor(nowMs / 1000);
  // C516: while publish is set, live pins are hidden and demo pins stay.
  const liveHidden = await deps.isStopped("publish", nowMs);
  const cell = ngeohash.encode(point.lat, point.lng, 6);
  // C509: the partition key only. A sort-key range on capture time would cut demo pins, which keep theirs.
  const cells = await Promise.all(
    [cell, ...ngeohash.neighbors(cell)].map((geohash) =>
      queryAll(deps.ddb, {
        TableName: deps.tableName,
        KeyConditionExpression: "#pk = :pk",
        FilterExpression: "#published = :true AND #visibleUntil > :now",
        ExpressionAttributeNames: { "#pk": "pk", "#published": "published", "#visibleUntil": "visibleUntil" },
        ExpressionAttributeValues: { ":pk": `GEO#${geohash}`, ":true": true, ":now": nowS },
      }),
    ),
  );
  return (
    cells
      .flat()
      // The filter above does this in DynamoDB. It is checked again here because the tests' mock
      // never evaluates a FilterExpression, so only this line shows which items are kept (T5).
      .filter((item) => (item.mode === "live" || item.mode === "demo") && item.published === true && item.visibleUntil > nowS)
      .filter((item) => !(liveHidden && item.mode === "live"))
      .map((item) => publicPin(item, deps.inchesShown))
      // On the rounded coordinates, so the radius can't be used to find a pin more closely than C514 shows it.
      .filter((pin) => distanceM(point, pin) <= radiusM)
      .sort((a, b) => Date.parse(b.capturedAt) - Date.parse(a.capturedAt))
      .slice(0, MAX_PINS)
  );
}

// GET /map/pins (C519): every visible published pin, live and demo. Each call of the returned
// function shares one 30 s memo, so index.ts builds one per container (T9).
export function createMapPins(deps: PinDeps): () => Promise<JsonResponse> {
  return memoise(MAP_MEMO_MS, deps.now, async (nowMs) => {
    const nowS = Math.floor(nowMs / 1000);
    // C516: while publish is set, the live partition isn't read, and demo pins stay.
    const parts = (await deps.isStopped("publish", nowMs)) ? ["demo"] : ["live", "demo"];
    const pins: PublicPin[] = [];
    for (const part of parts) {
      for (const item of await feedPart(part, nowS, deps)) pins.push(publicPin(item, deps.inchesShown));
    }
    return json(200, { pins });
  });
}

// GET /pins.geojson (C517, C521): live pins only, for other flood maps, with the screen line as
// its notice. The returned function keeps a 60 s memo, so index.ts builds one per container (T9).
export function createFeed(deps: PinDeps): () => Promise<JsonResponse> {
  return memoise(FEED_MEMO_MS, deps.now, async (nowMs) => {
    const nowS = Math.floor(nowMs / 1000);
    const items = (await deps.isStopped("publish", nowMs)) ? [] : await feedPart("live", nowS, deps);
    const features = items.map((item) => {
      const { lat, lng, ...properties } = publicPin(item, deps.inchesShown);
      return { type: "Feature", geometry: { type: "Point", coordinates: [lng, lat] }, properties };
    });
    return {
      statusCode: 200,
      headers: { "content-type": "application/geo+json", "cache-control": "public, max-age=60" },
      body: JSON.stringify({ type: "FeatureCollection", notice: SCREEN_LINE, features }),
    };
  });
}

// The great-circle distance in metres (haversine).
export function distanceM(a: Point, b: Point): number {
  const rad = Math.PI / 180;
  const h =
    Math.sin(((b.lat - a.lat) * rad) / 2) ** 2 +
    Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(((b.lng - a.lng) * rad) / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

// One feed-index partition's visible pins. The index holds only published pins (spec §4.4).
function feedPart(part: string, nowS: number, deps: PinDeps): Promise<ReportItem[]> {
  return queryAll(deps.ddb, {
    TableName: deps.tableName,
    IndexName: deps.feedIndexName,
    KeyConditionExpression: "#feedPart = :part AND #visibleUntil > :now",
    ExpressionAttributeNames: { "#feedPart": "feedPart", "#visibleUntil": "visibleUntil" },
    ExpressionAttributeValues: { ":part": part, ":now": nowS },
  });
}

// Every page of a query: DynamoDB stops a page at 1 MB, and filters only after reading it.
async function queryAll(ddb: DynamoDBDocumentClient, input: QueryCommandInput): Promise<ReportItem[]> {
  const items: ReportItem[] = [];
  let start: QueryCommandInput["ExclusiveStartKey"];
  do {
    const page = await ddb.send(new QueryCommand({ ...input, ...(start !== undefined && { ExclusiveStartKey: start }) }));
    items.push(...(page.Items ?? []));
    start = page.LastEvaluatedKey;
  } while (start !== undefined);
  return items;
}

// Keeps one response for ttlMs. A failed build isn't kept, so the next call tries again.
function memoise(ttlMs: number, now: () => number, build: (nowMs: number) => Promise<JsonResponse>): () => Promise<JsonResponse> {
  let kept: { res: JsonResponse; builtAtMs: number } | undefined;
  return async () => {
    const nowMs = now();
    if (kept !== undefined && nowMs - kept.builtAtMs < ttlMs) return kept.res;
    const res = await build(nowMs);
    kept = { res, builtAtMs: nowMs };
    return res;
  };
}

// An empty or missing parameter is NaN, not Number("")'s 0.
function parseNumber(value: string | undefined): number {
  return value === undefined || value.trim() === "" ? NaN : Number(value);
}

function inRange(value: number, min: number, max: number): boolean {
  return Number.isFinite(value) && value >= min && value <= max;
}

function round4(value: number): number {
  return Math.round(value * 10_000) / 10_000;
}
