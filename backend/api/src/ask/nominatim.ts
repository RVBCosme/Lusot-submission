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
const SLOT_PK = "nominatim#last";
const SLOT_TTL_S = 2 * 3600;
// Nominatim's policy is at most 1 request a second. Each Lambda compares write times against its own clock, so the
// gap is 1,100 ms: the extra 100 ms covers small skew between the Lambdas' clocks.
const SLOT_GAP_MS = 1100;

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

  // Both caches. The table write may fail without losing the answer. The caches are read before the slot wait and
  // written only after an answer, so two Lambdas that miss on the same uncached place a moment apart each send it
  // once. The requests stay 1.1 s apart, so the policy holds, and the cache prevents repeats once an answer is stored.
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

  // One conditional write to the one slot item, `nominatim#last`, claims the right to make a request. It succeeds
  // only when no item exists or the item's writtenMs is at least SLOT_GAP_MS older than this write. A single-item
  // conditional write is atomic: DynamoDB checks the condition against the item as it stands when the write lands.
  // So every claim that succeeds saw the previous successful claim's writtenMs and needed it to be 1.1 s older, and
  // across all Lambdas the stored write times rise by at least SLOT_GAP_MS per request, whatever the order the
  // writes were sent or landed in. The gap is measured between write times; a request leaves one round trip after its write.
  // True when the claim succeeded. False when another Lambda holds the slot. Any other failure throws.
  async function claim(): Promise<boolean> {
    const writtenMs = deps.now(); // taken just before the put
    try {
      await deps.ddb.send(
        new PutCommand({
          TableName: deps.limitsTableName,
          Item: { pk: SLOT_PK, writtenMs, expiresAt: Math.floor(writtenMs / 1000) + SLOT_TTL_S },
          ConditionExpression: "attribute_not_exists(#pk) OR #writtenMs <= :limit",
          ExpressionAttributeNames: { "#pk": "pk", "#writtenMs": "writtenMs" },
          ExpressionAttributeValues: { ":limit": writtenMs - SLOT_GAP_MS },
        }),
      );
      return true;
    } catch (err) {
      if ((err as { name?: string } | undefined)?.name === "ConditionalCheckFailedException") return false;
      throw err;
    }
  }

  // True once this Lambda holds the slot. False (busy) when there is too little time to ask: under 2,500 ms at the
  // start, or at the moment the slot is found taken, or when the claim is refused again after one wait. A taken
  // slot is waited out once: read the slot's writtenMs, sleep until 1,100 ms after it, claim again, never loop.
  // The wait is at most 1,100 ms, so the call that follows has about 1,400 ms; its timer is cut to what remains.
  // A failed read or write throws.
  async function takeSlot(deadline: Deadline): Promise<boolean> {
    const hasTime = () => deadline.remainingMs(BUDGET.modelBy) >= BUDGET.minNominatim;
    if (!hasTime()) return false;
    if (await claim()) return true;
    if (!hasTime()) return false;
    // Strongly consistent, so a claim another Lambda made a moment ago can't be missed.
    const { Item: last } = await deps.ddb.send(
      new GetCommand({ TableName: deps.limitsTableName, Key: { pk: SLOT_PK }, ConsistentRead: true }),
    );
    // The wait counts from the moment the read returned.
    if (typeof last?.writtenMs === "number") await deps.sleep(Math.max(0, last.writtenMs + SLOT_GAP_MS - deps.now()));
    return claim();
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
      if (await deps.isStopped("nominatim", deps.now())) return { trace: "off" };
      if (key === "") return { result: NOT_FOUND, trace: "not_found" }; // nothing to ask about

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
