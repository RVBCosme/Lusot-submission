import { createHash } from "node:crypto";
import { type DynamoDBDocumentClient, GetCommand, PutCommand } from "@aws-sdk/lib-dynamodb";
import { logError } from "../log";
import { distanceM } from "../pins";
import type { StopSwitch } from "../stopSwitch";
import { BUDGET, type Deadline } from "./deadline";
import { normalize } from "./text";

export type Box = { south: number; north: number; west: number; east: number };

// `box` is Nominatim's boundingbox and `spanM` its diagonal in metres, so the caller can tell a point from a street.
export type GeoResult =
  | { status: "found"; name: string; lat: number; lng: number; box: Box; spanM: number }
  | { status: "not_found" };

export type GeoTrace = "cache" | "called" | "not_found" | "busy" | "off" | "failed";

export type GeocoderDeps = {
  ddb: DynamoDBDocumentClient;
  limitsTableName: string;
  fetchFn: typeof fetch;
  userAgent: string;
  isStopped: StopSwitch;
  now: () => number;
  sleep: (ms: number) => Promise<void>;
  bounds: { west: number; south: number; east: number; north: number };
};

export type Geocoder = {
  geocode(place: string, deadline: Deadline): Promise<{ result?: GeoResult; trace: GeoTrace }>;
};

const SEARCH_URL = "https://nominatim.openstreetmap.org/search";
const MAX_PLACE_CHARS = 100; // C726
const MEMORY_ENTRIES = 500;
const FOUND_TTL_S = 7 * 24 * 3600;
const MISS_TTL_S = 24 * 3600;
const SLOT_TTL_S = 2 * 3600;
const SLOT_GAP_MS = 1000; // Nominatim's policy: at most 1 request a second

const NOT_FOUND: GeoResult = { status: "not_found" };

export function createGeocoder(deps: GeocoderDeps): Geocoder {
  // The newest 500 answers, by the cache key's hash. A Map keeps insertion order, so the first key is the oldest.
  const memory = new Map<string, { result: GeoResult; expiresAtMs: number }>();

  function remember(hash: string, result: GeoResult, expiresAtMs: number): void {
    memory.delete(hash);
    if (memory.size >= MEMORY_ENTRIES) {
      const oldest = memory.keys().next();
      if (!oldest.done) memory.delete(oldest.value);
    }
    memory.set(hash, { result, expiresAtMs });
  }

  function fromMemory(hash: string): GeoResult | undefined {
    const hit = memory.get(hash);
    if (hit === undefined) return undefined;
    if (hit.expiresAtMs > deps.now()) return hit.result;
    memory.delete(hash);
    return undefined;
  }

  // The cached answer, or undefined for a miss: no item, an item past its own expiresAt (DynamoDB's TTL deletes
  // days late), or one that isn't a place. A failed read throws.
  async function readTable(hash: string): Promise<{ result: GeoResult; expiresAtMs: number } | undefined> {
    const { Item } = await deps.ddb.send(new GetCommand({ TableName: deps.limitsTableName, Key: { pk: `geocode#${hash}` } }));
    if (Item === undefined || typeof Item.expiresAt !== "number" || Item.expiresAt * 1000 <= deps.now()) return undefined;
    const result = asResult(Item);
    return result && { result, expiresAtMs: Item.expiresAt * 1000 };
  }

  // Both caches. The table write may fail without losing the answer.
  async function store(hash: string, result: GeoResult): Promise<void> {
    const expiresAt = Math.floor(deps.now() / 1000) + (result.status === "found" ? FOUND_TTL_S : MISS_TTL_S);
    remember(hash, result, expiresAt * 1000);
    try {
      // The item holds the hash and what OpenStreetMap answered, never the text that was asked (AskL-Q3).
      await deps.ddb.send(new PutCommand({ TableName: deps.limitsTableName, Item: { pk: `geocode#${hash}`, ...result, expiresAt } }));
    } catch (err) {
      logError("geocode_cache_write_failed", err);
    }
  }

  // True once this Lambda holds its second's slot, with the previous request at least a second behind.
  // False when there is too little time to wait for one. The wait is at most 1 s from the moment the slot is
  // found taken, and the check leaves 1.5 s for the call after it. A failed read or write throws.
  async function takeSlot(deadline: Deadline): Promise<boolean> {
    const hasTime = () => deadline.remainingMs(BUDGET.modelBy) >= BUDGET.minNominatim;
    if (!hasTime()) return false;
    for (;;) {
      const startMs = deps.now();
      const second = Math.floor(startMs / 1000);
      // Strongly consistent, so a request another Lambda made a moment ago can't be missed.
      const { Item: previous } = await deps.ddb.send(
        new GetCommand({ TableName: deps.limitsTableName, Key: { pk: `nominatim#${second - 1}` }, ConsistentRead: true }),
      );
      if (typeof previous?.writtenMs === "number" && startMs - previous.writtenMs < SLOT_GAP_MS) {
        await deps.sleep(previous.writtenMs + SLOT_GAP_MS - startMs);
      }
      try {
        await deps.ddb.send(
          new PutCommand({
            TableName: deps.limitsTableName,
            Item: { pk: `nominatim#${second}`, writtenMs: deps.now(), expiresAt: second + SLOT_TTL_S },
            ConditionExpression: "attribute_not_exists(#pk)",
            ExpressionAttributeNames: { "#pk": "pk" },
          }),
        );
        return true;
      } catch (err) {
        if ((err as { name?: string } | undefined)?.name !== "ConditionalCheckFailedException") throw err;
      }
      // Another Lambda holds this second. Wait for the next one if the budget allows; the loop then also waits
      // out the gap since that Lambda's write.
      if (!hasTime()) return false;
      await deps.sleep(Math.max(0, (second + 1) * 1000 - deps.now()));
    }
  }

  // Asks Nominatim. Undefined when the call or its answer failed; the reason is logged without the place.
  async function search(text: string, deadline: Deadline): Promise<GeoResult | undefined> {
    const { west, north, east, south } = deps.bounds;
    const url = new URL(SEARCH_URL);
    url.search = new URLSearchParams({
      q: text,
      format: "jsonv2",
      limit: "1",
      countrycodes: "ph",
      bounded: "0", // Metro Manila is a preference only, so a place outside still resolves
      "accept-language": "en",
      viewbox: `${west},${north},${east},${south}`,
    }).toString();
    // The call's own 1.5 s, cut short by the model's mark. The timer covers reading the body too.
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), Math.min(BUDGET.nominatimCall, deadline.remainingMs(BUDGET.modelBy)));
    try {
      const res = await deps.fetchFn(url.toString(), {
        headers: { "user-agent": deps.userAgent, accept: "application/json" },
        signal: controller.signal,
      });
      if (!res.ok) {
        console.error(JSON.stringify({ msg: "nominatim_http_error", status: res.status }));
        return undefined;
      }
      const result = parseSearch(await res.json());
      if (result === undefined) console.error(JSON.stringify({ msg: "nominatim_unreadable_result" }));
      return result;
    } catch (err) {
      logError("nominatim_request_failed", err);
      return undefined;
    } finally {
      clearTimeout(timer);
    }
  }

  return {
    async geocode(place, deadline) {
      const text = cleanPlace(place);
      const key = normalize(text);
      if (key === "") return { result: NOT_FOUND, trace: "not_found" }; // nothing to ask about
      if (await deps.isStopped("nominatim", deps.now())) return { trace: "off" };

      const hash = createHash("sha256").update(key).digest("hex");
      const remembered = fromMemory(hash);
      if (remembered !== undefined) return { result: remembered, trace: "cache" };
      try {
        const stored = await readTable(hash);
        if (stored !== undefined) {
          remember(hash, stored.result, stored.expiresAtMs);
          return { result: stored.result, trace: "cache" };
        }
      } catch (err) {
        // An unreadable cache never leads to a request: a repeated query could break the policy (spec C701).
        logError("geocode_cache_unreadable", err);
        return { trace: "failed" };
      }

      try {
        if (!(await takeSlot(deadline))) return { trace: "busy" };
      } catch (err) {
        logError("nominatim_slot_failed", err);
        return { trace: "failed" };
      }
      const result = await search(text, deadline);
      if (result === undefined) return { trace: "failed" };
      await store(hash, result);
      return { result, trace: result.status === "found" ? "called" : "not_found" };
    },
  };
}

// The place as it is sent: control characters become spaces, spaces collapse, and at most 100 characters stay (C726).
function cleanPlace(place: string): string {
  const spaced = place.replace(/\p{Cc}/gu, " ").replace(/\s+/g, " ").trim();
  return Array.from(spaced).slice(0, MAX_PLACE_CHARS).join("").trimEnd();
}

function num(value: unknown): number {
  return (typeof value === "string" && value.trim() !== "") || typeof value === "number" ? Number(value) : Number.NaN;
}

// /search's answer: a list, empty when nothing matched. Undefined when the first hit isn't readable.
function parseSearch(body: unknown): GeoResult | undefined {
  if (!Array.isArray(body)) return undefined;
  if (body.length === 0) return NOT_FOUND;
  const hit = body[0] as { lat?: unknown; lon?: unknown; name?: unknown; display_name?: unknown; boundingbox?: unknown };
  const lat = num(hit.lat);
  const lng = num(hit.lon);
  // Nominatim's boundingbox is [south, north, west, east], as strings.
  const [south, north, west, east] = Array.isArray(hit.boundingbox) ? hit.boundingbox.map(num) : [];
  const name =
    typeof hit.name === "string" && hit.name.trim() !== ""
      ? hit.name.trim()
      : typeof hit.display_name === "string"
        ? (hit.display_name.split(",")[0] ?? "").trim()
        : "";
  if (![lat, lng, south, north, west, east].every(Number.isFinite) || name === "") return undefined;
  return {
    status: "found",
    name,
    lat,
    lng,
    box: { south, north, west, east },
    spanM: distanceM({ lat: south, lng: west }, { lat: north, lng: east }),
  };
}

// A cache item back into a result; undefined when it isn't one.
function asResult(item: Record<string, unknown>): GeoResult | undefined {
  if (item.status === "not_found") return NOT_FOUND;
  const box = item.box as Partial<Box> | undefined;
  if (
    item.status !== "found" ||
    typeof item.name !== "string" ||
    ![item.lat, item.lng, item.spanM, box?.south, box?.north, box?.west, box?.east].every(Number.isFinite)
  ) {
    return undefined;
  }
  return { status: "found", name: item.name, lat: item.lat as number, lng: item.lng as number, box: box as Box, spanM: item.spanM as number };
}
