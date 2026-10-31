import { createHash } from "node:crypto";
import {
  ConditionalCheckFailedException,
  DynamoDBClient,
  ProvisionedThroughputExceededException,
} from "@aws-sdk/client-dynamodb";
import {
  DynamoDBDocumentClient,
  GetCommand,
  type GetCommandInput,
  PutCommand,
  type PutCommandInput,
} from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { afterEach, beforeEach, describe, expect, it, type MockInstance, vi } from "vitest";
import { BUDGET, Deadline } from "../../src/ask/deadline";
import { createGeocoder, type GeocoderDeps } from "../../src/ask/nominatim";
import { normalize } from "../../src/ask/text";
import { distanceM } from "../../src/pins";

const T0 = Date.parse("2026-10-30T10:00:00Z"); // a whole second
const SECOND_0 = T0 / 1000;
const BOUNDS = { west: 120.906221, south: 14.347255, east: 121.135023, north: 14.785336 };
const USER_AGENT = "Lusot/1.0 (test)";
const PLACE = "Jollibee Maginhawa";
const OTHER_PLACE = "Robinsons Place";
const PRIVATE_PLACE = "ang bahay ni Mang Kanor"; // nothing in a reply, an item or a log may repeat this

// What Nominatim's /search?format=jsonv2 answers: strings for the numbers, boundingbox as south, north, west, east.
const MAGINHAWA = {
  place_id: 1,
  lat: "14.6501",
  lon: "121.0501",
  name: "Jollibee Maginhawa",
  display_name: "Jollibee Maginhawa, Teachers Village, Quezon City, Metro Manila, Philippines",
  boundingbox: ["14.6500", "14.6502", "121.0500", "121.0502"],
};
const MAGINHAWA_FOUND = {
  status: "found",
  name: "Jollibee Maginhawa",
  lat: 14.6501,
  lng: 121.0501,
  box: { south: 14.65, north: 14.6502, west: 121.05, east: 121.0502 },
  spanM: distanceM({ lat: 14.65, lng: 121.05 }, { lat: 14.6502, lng: 121.0502 }),
};

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
const ddbMock = mockClient(ddb);

let clock: number; // the one fake clock every geocoder, sleep and Deadline reads
let tickPerCall: number; // how long each table call takes
let table: Map<string, Record<string, unknown>>;
let fetches: { url: URL; init: RequestInit; atMs: number }[];
let sleeps: number[];
let reply: (init: RequestInit) => Promise<Response>;
let errorSpy: MockInstance<typeof console.error>;
let logSpy: MockInstance<typeof console.log>;
let warnSpy: MockInstance<typeof console.warn>;

function sha256(text: string): string {
  return createHash("sha256").update(text).digest("hex");
}

const cacheKey = (place: string) => `geocode#${sha256(normalize(place))}`;

function respond(body: unknown, status = 200): () => Promise<Response> {
  return () => Promise.resolve(new Response(JSON.stringify(body), { status }));
}

const fetchFn = (async (input: string | URL | Request, init?: RequestInit) => {
  fetches.push({ url: new URL(String(input)), init: init ?? {}, atMs: clock });
  return reply(init ?? {});
}) as typeof fetch;

async function sleep(ms: number): Promise<void> {
  sleeps.push(ms);
  clock += ms;
}

// The mock never evaluates a ConditionExpression, so this does what DynamoDB would with the conditions the
// slot sends. The exact text of the current one is checked below.
function conditionHolds(input: PutCommandInput, existing: Record<string, unknown> | undefined): boolean {
  switch (input.ConditionExpression) {
    case undefined:
      return true;
    case "attribute_not_exists(#pk)":
      return existing === undefined;
    case "attribute_not_exists(#pk) OR #writtenMs <= :limit":
      return existing === undefined || (existing.writtenMs as number) <= (input.ExpressionAttributeValues?.[":limit"] as number);
    default:
      throw new Error(`the fake table doesn't know the condition ${input.ConditionExpression}`);
  }
}

// Every claim that reached the table, in the order it landed, with the write times it carried.
let claimsAttempted: number[];
let claimsApplied: number[];

// A write lands: its condition is checked against the item as it stands now.
function applyPut(input: PutCommandInput): Record<string, never> {
  const pk = input.Item?.pk as string;
  const isClaim = pk.startsWith("nominatim#");
  if (isClaim) claimsAttempted.push(input.Item?.writtenMs as number);
  if (!conditionHolds(input, table.get(pk))) {
    throw new ConditionalCheckFailedException({ message: "The conditional request failed", $metadata: {} });
  }
  if (isClaim) claimsApplied.push(input.Item?.writtenMs as number);
  table.set(pk, input.Item ?? {});
  return {};
}

function fakeTable(): void {
  ddbMock.on(GetCommand).callsFake((input: GetCommandInput) => {
    clock += tickPerCall;
    return { Item: table.get(input.Key?.pk as string) };
  });
  ddbMock.on(PutCommand).callsFake((input: PutCommandInput) => {
    clock += tickPerCall;
    return applyPut(input);
  });
}

function makeGeocoder(over: Partial<GeocoderDeps> = {}) {
  return createGeocoder({
    ddb,
    limitsTableName: "limits",
    fetchFn,
    userAgent: USER_AGENT,
    isStopped: async () => false,
    now: () => clock,
    sleep,
    bounds: BOUNDS,
    ...over,
  });
}

// A Deadline whose handler started `elapsedMs` ago, so the model's mark has 7,500 - elapsedMs left.
function deadline(elapsedMs = 0): Deadline {
  return new Deadline(clock - elapsedMs, () => clock);
}

function seed(place: string, over: Record<string, unknown> = {}): void {
  table.set(cacheKey(place), {
    pk: cacheKey(place),
    ...MAGINHAWA_FOUND,
    expiresAt: Math.floor(clock / 1000) + 3600,
    ...over,
  });
}

const gets = () => ddbMock.commandCalls(GetCommand).map((call) => call.args[0].input);
const puts = () => ddbMock.commandCalls(PutCommand).map((call) => call.args[0].input);
const slotPuts = () => puts().filter((input) => String(input.Item?.pk).startsWith("nominatim#"));
const cachePuts = () => puts().filter((input) => String(input.Item?.pk).startsWith("geocode#"));
const logged = () => JSON.stringify([...errorSpy.mock.calls, ...logSpy.mock.calls, ...warnSpy.mock.calls]);

beforeEach(() => {
  clock = T0 + 5300; // 0.3 s into second 5
  tickPerCall = 0;
  table = new Map();
  claimsAttempted = [];
  claimsApplied = [];
  fetches = [];
  sleeps = [];
  reply = respond([MAGINHAWA]);
  ddbMock.reset();
  fakeTable();
  errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
  warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("the request", () => {
  it("the request carries the User-Agent and the spec's parameters", async () => {
    const out = await makeGeocoder().geocode(PLACE, deadline());

    expect(fetches).toHaveLength(1);
    const { url, init } = fetches[0];
    expect(`${url.origin}${url.pathname}`).toBe("https://nominatim.openstreetmap.org/search");
    expect(url.searchParams.get("q")).toBe(PLACE);
    expect(url.searchParams.get("format")).toBe("jsonv2");
    expect(url.searchParams.get("limit")).toBe("1");
    expect(url.searchParams.get("countrycodes")).toBe("ph");
    expect(url.searchParams.get("bounded")).toBe("0");
    expect(url.searchParams.get("accept-language")).toBe("en");
    expect(url.searchParams.get("viewbox")).toBe("120.906221,14.785336,121.135023,14.347255"); // west,north,east,south
    expect([...url.searchParams.keys()].sort()).toEqual(
      ["accept-language", "bounded", "countrycodes", "format", "limit", "q", "viewbox"].sort(),
    );
    expect(new Headers(init.headers).get("user-agent")).toBe(USER_AGENT);
    expect(init.signal).toBeInstanceOf(AbortSignal);
    expect(out).toEqual({ result: MAGINHAWA_FOUND, trace: "called" });
    expect(sleeps).toEqual([]);
  });

  it("sends the place as the person wrote it, not the matching key", async () => {
    await makeGeocoder().geocode("  Sts.   Peter and Paul\tParish ", deadline());

    expect(normalize("Sts. Peter and Paul Parish")).toBe("sts peter cor paul parish");
    expect(fetches[0].url.searchParams.get("q")).toBe("Sts. Peter and Paul Parish");
  });

  it("the place is trimmed to 100 characters and stripped of control characters", async () => {
    const geocoder = makeGeocoder();

    await geocoder.geocode(`  Rizal\u0000 Park\n\tManila ${"z".repeat(200)}`, deadline());
    // A cut that lands on a space leaves no trailing space.
    await geocoder.geocode(`${"a".repeat(99)} ${"b".repeat(50)}`, deadline());

    const first = fetches[0].url.searchParams.get("q") ?? "";
    expect(first).toHaveLength(100);
    expect(first).toMatch(/^Rizal Park Manila z+$/);
    expect(first).not.toMatch(/\p{Cc}/u);
    expect(fetches[1].url.searchParams.get("q")).toBe("a".repeat(99));
  });

  it("with the switch on, a place with no words is off too", async () => {
    const out = await makeGeocoder({ isStopped: async () => true }).geocode("?!", deadline());

    expect(out).toEqual({ trace: "off" });
    expect(ddbMock.calls()).toHaveLength(0);
  });

  it("a place with no words in it sends nothing and touches nothing", async () => {
    const geocoder = makeGeocoder();

    expect(await geocoder.geocode("  \u0000 ", deadline())).toEqual({ result: { status: "not_found" }, trace: "not_found" });
    expect(await geocoder.geocode("?! ...", deadline())).toEqual({ result: { status: "not_found" }, trace: "not_found" });

    expect(fetches).toHaveLength(0);
    expect(ddbMock.calls()).toHaveLength(0);
  });
});

describe("the result", () => {
  it("box and spanM come from boundingbox", async () => {
    // 0.0108 degrees of latitude is about 1.2 km: a street, not a point.
    reply = respond([{ ...MAGINHAWA, boundingbox: ["14.6000", "14.6108", "121.0000", "121.0002"] }]);

    const out = await makeGeocoder().geocode(PLACE, deadline());

    expect(out.trace).toBe("called");
    if (out.result?.status !== "found") throw new Error("expected a found place");
    expect(out.result.box).toEqual({ south: 14.6, north: 14.6108, west: 121, east: 121.0002 });
    expect(out.result.spanM).toBeGreaterThan(1000);
    expect(out.result.spanM).toBeCloseTo(distanceM({ lat: 14.6, lng: 121 }, { lat: 14.6108, lng: 121.0002 }), 6);
    expect(out.result.lat).toBe(14.6501);
    expect(out.result.lng).toBe(121.0501);
  });

  it("the name is Nominatim's name, or the first part of display_name when it is empty", async () => {
    reply = respond([{ ...MAGINHAWA, name: "" }]);
    const unnamed = await makeGeocoder().geocode(PLACE, deadline());
    reply = respond([{ ...MAGINHAWA, name: "Maginhawa Street" }]);
    const named = await makeGeocoder().geocode(OTHER_PLACE, deadline());

    expect(unnamed.result).toMatchObject({ name: "Jollibee Maginhawa" }); // display_name's first part
    expect(named.result).toMatchObject({ name: "Maginhawa Street" });
    reply = respond([{ ...MAGINHAWA, name: undefined, display_name: "Maginhawa Street, Teachers Village, Quezon City" }]);
    const noName = await makeGeocoder().geocode("Maginhawa", deadline());
    expect(noName.result).toMatchObject({ name: "Maginhawa Street" });
  });

  it("an empty answer is not_found", async () => {
    reply = respond([]);

    expect(await makeGeocoder().geocode(PLACE, deadline())).toEqual({ result: { status: "not_found" }, trace: "not_found" });
  });

  it.each([
    ["a result with no point", [{ ...MAGINHAWA, lat: undefined }]],
    ["a result with no boundingbox", [{ ...MAGINHAWA, boundingbox: undefined }]],
    ["a result with a short boundingbox", [{ ...MAGINHAWA, boundingbox: ["14.65", "14.66"] }]],
    ["a result with no name at all", [{ ...MAGINHAWA, name: "", display_name: "" }]],
    ["something that is not a list", { error: "x" }],
  ])("%s gives failed and is not cached", async (_label, body) => {
    reply = respond(body);

    expect(await makeGeocoder().geocode(PLACE, deadline())).toEqual({ trace: "failed" });
    expect(cachePuts()).toHaveLength(0);
  });
});

describe("failures", () => {
  it("a 1.5 s timeout gives failed, even when the model's mark leaves far more", async () => {
    // 7,500 ms left, and a fetch that never settles until it is aborted: the timer is 1,500 ms, not the 7,500.
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const aborted: boolean[] = [];
    reply = (init) =>
      new Promise((_resolve, reject) => {
        const signal = init.signal as AbortSignal;
        signal.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })));
        vi.advanceTimersByTime(1499);
        aborted.push(signal.aborted);
        vi.advanceTimersByTime(1);
        aborted.push(signal.aborted);
      });

    const out = await makeGeocoder().geocode(PLACE, deadline());

    expect(aborted).toEqual([false, true]);
    expect(out).toEqual({ trace: "failed" });
    expect(fetches).toHaveLength(1);
    expect(cachePuts()).toHaveLength(0);
    expect(JSON.parse(errorSpy.mock.calls[0][0] as string)).toMatchObject({ msg: "nominatim_request_failed", error: "AbortError" });
  });

  it("the call's timer is cut to what the model's mark leaves", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    // 2,500 ms are left at the start, enough to ask. The claim takes 1,300 ms to land, so the call starts with 1,200.
    ddbMock.on(PutCommand).callsFake((input: PutCommandInput) => {
      clock += 1300;
      return applyPut(input);
    });
    const aborted: boolean[] = [];
    reply = (init) =>
      new Promise((_resolve, reject) => {
        const signal = init.signal as AbortSignal;
        signal.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })));
        vi.advanceTimersByTime(1199);
        aborted.push(signal.aborted);
        vi.advanceTimersByTime(1);
        aborted.push(signal.aborted);
      });

    const out = await makeGeocoder().geocode(PLACE, deadline(BUDGET.modelBy - 2500));

    expect(aborted).toEqual([false, true]);
    expect(out).toEqual({ trace: "failed" });
  });

  it.each([429, 500, 503])("a %i gives failed, with no retry and nothing cached", async (status) => {
    reply = respond({ error: "slow down" }, status);

    const out = await makeGeocoder().geocode(PLACE, deadline());

    expect(out).toEqual({ trace: "failed" });
    expect(fetches).toHaveLength(1); // the policy's rate is the limit, so no retry
    expect(sleeps).toEqual([]);
    expect(cachePuts()).toHaveLength(0);
    expect(JSON.parse(errorSpy.mock.calls[0][0] as string)).toEqual({ msg: "nominatim_http_error", status });
  });

  it("a network error gives failed", async () => {
    reply = () => Promise.reject(new TypeError(`fetch failed for ${PRIVATE_PLACE}`));

    expect(await makeGeocoder().geocode(PRIVATE_PLACE, deadline())).toEqual({ trace: "failed" });
    expect(cachePuts()).toHaveLength(0);
  });

  it("a failed cache read sends no request", async () => {
    ddbMock
      .on(GetCommand)
      .rejects(new ProvisionedThroughputExceededException({ message: `Rate exceeded for ${PRIVATE_PLACE}`, $metadata: {} }));

    const out = await makeGeocoder().geocode(PRIVATE_PLACE, deadline());

    expect(out).toEqual({ trace: "failed" });
    expect(fetches).toHaveLength(0);
    expect(puts()).toHaveLength(0);
    expect(errorSpy).toHaveBeenCalledTimes(1);
    // The error's class, and nothing from its message.
    expect(JSON.parse(errorSpy.mock.calls[0][0] as string)).toMatchObject({ error: "ProvisionedThroughputExceededException" });
    expect(logged()).not.toMatch(/Kanor|Rate exceeded/i);
  });

  it("a taken slot that can't be read sends no request", async () => {
    table.set("nominatim#last", { pk: "nominatim#last", writtenMs: clock });
    // The cache read passes and the claim is refused, then the slot can't be read.
    ddbMock.on(GetCommand).callsFake((input: GetCommandInput) => {
      if (String(input.Key?.pk).startsWith("nominatim#")) {
        throw new ProvisionedThroughputExceededException({ message: "x", $metadata: {} });
      }
      return { Item: undefined };
    });

    expect(await makeGeocoder().geocode(PLACE, deadline())).toEqual({ trace: "failed" });
    expect(fetches).toHaveLength(0);
    expect(errorSpy).toHaveBeenCalledTimes(1);
  });

  it("a claim that fails for any reason but a taken slot sends no request", async () => {
    ddbMock.on(PutCommand).rejects(new ProvisionedThroughputExceededException({ message: "x", $metadata: {} }));

    expect(await makeGeocoder().geocode(PLACE, deadline())).toEqual({ trace: "failed" });
    expect(fetches).toHaveLength(0);
    expect(errorSpy).toHaveBeenCalledTimes(1);
  });

  it("a cache write that fails still returns the place it found", async () => {
    ddbMock.on(PutCommand).callsFake((input: PutCommandInput) => {
      if (String(input.Item?.pk).startsWith("geocode#")) throw new ProvisionedThroughputExceededException({ message: "x", $metadata: {} });
      table.set(input.Item?.pk as string, input.Item ?? {});
      return {};
    });

    const out = await makeGeocoder().geocode(PLACE, deadline());

    expect(out).toEqual({ result: MAGINHAWA_FOUND, trace: "called" });
    expect(JSON.parse(errorSpy.mock.calls[0][0] as string)).toMatchObject({ error: "ProvisionedThroughputExceededException" });
  });
});

describe("the switch", () => {
  it("the switch stops it", async () => {
    const isStopped = vi.fn(async () => true);
    seed(PLACE); // even a place in the table waits for the switch

    const out = await makeGeocoder({ isStopped }).geocode(PLACE, deadline());

    expect(out).toEqual({ trace: "off" });
    expect(isStopped).toHaveBeenCalledWith("nominatim", clock);
    expect(fetches).toHaveLength(0);
    expect(ddbMock.calls()).toHaveLength(0);
  });
});

describe("the caches", () => {
  it("a memory hit makes no call", async () => {
    const geocoder = makeGeocoder();
    await geocoder.geocode(PLACE, deadline());
    const calls = ddbMock.calls().length;

    // The same place, written another way, is the same key.
    const out = await geocoder.geocode("  jollibee MAGINHAWA!", deadline());

    expect(out).toEqual({ result: MAGINHAWA_FOUND, trace: "cache" });
    expect(fetches).toHaveLength(1);
    expect(ddbMock.calls()).toHaveLength(calls);
  });

  it("a table hit makes no request", async () => {
    seed("Sts. Peter and Paul Parish");
    const geocoder = makeGeocoder();

    const out = await geocoder.geocode("STS Peter & Paul parish", deadline());

    expect(out).toEqual({ result: MAGINHAWA_FOUND, trace: "cache" });
    expect(fetches).toHaveLength(0);
    expect(puts()).toHaveLength(0); // no slot taken either
    expect(gets()).toEqual([{ TableName: "limits", Key: { pk: cacheKey("Sts. Peter and Paul Parish") } }]);

    // The hit goes into the memory, so a second ask reads nothing.
    await geocoder.geocode("sts peter and paul parish", deadline());
    expect(gets()).toHaveLength(1);
  });

  it("a cache hit needs no time", async () => {
    seed(PLACE);

    const out = await makeGeocoder().geocode(PLACE, deadline(9000));

    expect(out).toEqual({ result: MAGINHAWA_FOUND, trace: "cache" });
  });

  it("an expired cache item reads as a miss", async () => {
    // DynamoDB's TTL deletes days late, so an item past its expiresAt can still be in the table.
    seed(PLACE, { expiresAt: Math.floor(clock / 1000) - 1 });

    const out = await makeGeocoder().geocode(PLACE, deadline());

    expect(out.trace).toBe("called");
    expect(fetches).toHaveLength(1);
    expect(table.get(cacheKey(PLACE))?.expiresAt).toBe(Math.floor(clock / 1000) + 7 * 24 * 3600); // and it is replaced
  });

  it("an item that is not a place is a miss", async () => {
    seed(PLACE, { status: "found", lat: "14.6" });

    expect((await makeGeocoder().geocode(PLACE, deadline())).trace).toBe("called");
  });

  it("a miss is cached for a day, and a find for 7 days", async () => {
    const geocoder = makeGeocoder();
    const missS = Math.floor(clock / 1000);
    reply = respond([]);
    const miss = await geocoder.geocode("Atlantis", deadline());
    clock += 2000; // a later second, so the slot is free
    const findS = Math.floor(clock / 1000);
    reply = respond([MAGINHAWA]);
    const find = await geocoder.geocode(PLACE, deadline());

    expect(miss).toEqual({ result: { status: "not_found" }, trace: "not_found" });
    expect(find.trace).toBe("called");
    expect(cachePuts()).toEqual([
      { TableName: "limits", Item: { pk: cacheKey("Atlantis"), status: "not_found", expiresAt: missS + 24 * 3600 } },
      { TableName: "limits", Item: { pk: cacheKey(PLACE), ...MAGINHAWA_FOUND, expiresAt: findS + 7 * 24 * 3600 } },
    ]);

    // A miss is remembered too, in the memory and in the table.
    expect(await geocoder.geocode("Atlantis", deadline())).toEqual({ result: { status: "not_found" }, trace: "cache" });
    expect(await makeGeocoder().geocode("Atlantis", deadline())).toEqual({ result: { status: "not_found" }, trace: "cache" });
    expect(fetches).toHaveLength(2);
  });

  it("the memory keeps 500 places and lets the oldest go", async () => {
    // Every place is in the table, so no request or slot is involved.
    ddbMock.on(GetCommand).callsFake((input: GetCommandInput) => ({
      Item: { pk: input.Key?.pk, ...MAGINHAWA_FOUND, expiresAt: Math.floor(clock / 1000) + 3600 },
    }));
    const geocoder = makeGeocoder();
    for (let i = 0; i <= 500; i++) await geocoder.geocode(`Place ${i}`, deadline());
    expect(gets()).toHaveLength(501);

    await geocoder.geocode("Place 500", deadline()); // newest: still in the memory
    expect(gets()).toHaveLength(501);
    await geocoder.geocode("Place 0", deadline()); // oldest: gone
    expect(gets()).toHaveLength(502);
  });

  it("a memory entry past its day is read again", async () => {
    reply = respond([]);
    const geocoder = makeGeocoder();
    await geocoder.geocode("Atlantis", deadline());
    table.clear();
    clock += 24 * 3600 * 1000 + 1;
    reply = respond([MAGINHAWA]);

    const out = await geocoder.geocode("Atlantis", deadline());

    expect(out.trace).toBe("called");
  });

  it("no item holds the place text", async () => {
    reply = respond([{ ...MAGINHAWA, name: "Barangay Hall" }]);

    await makeGeocoder().geocode(PRIVATE_PLACE, deadline());
    reply = respond([]);
    await makeGeocoder().geocode(`${PRIVATE_PLACE} 2`, deadline());

    expect(cachePuts()).toHaveLength(2);
    expect(slotPuts().length).toBeGreaterThanOrEqual(2);
    const everything = JSON.stringify(puts()).toLowerCase();
    expect(everything).not.toContain("kanor");
    expect(everything).not.toContain("bahay");
    expect(cachePuts()[0].Item).toEqual({ pk: cacheKey(PRIVATE_PLACE), ...MAGINHAWA_FOUND, name: "Barangay Hall", expiresAt: expect.any(Number) });
  });

  it("no log line holds it", async () => {
    // Every way a request can end badly, each with the place in the error's message.
    const failures: (() => Promise<Response>)[] = [
      () => Promise.reject(new TypeError(`fetch failed for ${PRIVATE_PLACE}`)),
      respond({ error: PRIVATE_PLACE }, 503),
      respond({ error: PRIVATE_PLACE }),
    ];
    for (const failure of failures) {
      reply = failure;
      await makeGeocoder().geocode(PRIVATE_PLACE, deadline());
    }
    ddbMock.on(GetCommand).rejects(new Error(`cannot read ${PRIVATE_PLACE}`));
    await makeGeocoder().geocode(PRIVATE_PLACE, deadline());

    expect(errorSpy.mock.calls.length).toBeGreaterThanOrEqual(4);
    expect(logged().toLowerCase()).not.toContain("kanor");
  });
});

describe("the slot", () => {
  const CLAIM_CONDITION = "attribute_not_exists(#pk) OR #writtenMs <= :limit";

  it("claims the one slot item with one conditional put, and reads nothing but the cache first", async () => {
    await makeGeocoder().geocode(PLACE, deadline());

    expect(gets()).toEqual([{ TableName: "limits", Key: { pk: cacheKey(PLACE) } }]);
    expect(slotPuts()).toEqual([
      {
        TableName: "limits",
        Item: { pk: "nominatim#last", writtenMs: T0 + 5300, expiresAt: SECOND_0 + 5 + 2 * 3600 },
        ConditionExpression: CLAIM_CONDITION,
        ExpressionAttributeNames: { "#pk": "pk", "#writtenMs": "writtenMs" },
        ExpressionAttributeValues: { ":limit": T0 + 5300 - 1100 },
      },
    ]);
    expect(CLAIM_CONDITION.match(/#\w+/g)).toEqual(["#pk", "#writtenMs"]); // every name goes through a placeholder
  });

  it("two geocoders in one second make one request", async () => {
    // Two Lambdas, one table. The first asks at 5.300 s, and the second arrives in the same second.
    const first = await makeGeocoder().geocode(PLACE, deadline());
    const second = await makeGeocoder().geocode(OTHER_PLACE, deadline());

    expect(first.trace).toBe("called");
    expect(second.trace).toBe("called");
    expect(fetches).toHaveLength(2);
    // The second's claim was refused, so it read the slot (strongly consistent), slept until 1.1 s after the
    // first's write and claimed again: it asked at 6.400 s.
    expect(sleeps).toEqual([1100]);
    expect(fetches.map((f) => f.atMs)).toEqual([T0 + 5300, T0 + 6400]);
    expect(slotPuts().map((input) => input.Item?.writtenMs)).toEqual([T0 + 5300, T0 + 5300, T0 + 6400]); // the middle one was refused
    expect(claimsApplied).toEqual([T0 + 5300, T0 + 6400]);
    expect(gets().at(-1)).toEqual({ TableName: "limits", Key: { pk: "nominatim#last" }, ConsistentRead: true });
  });

  it("a taken slot with under 2,500 ms left gives busy", async () => {
    await makeGeocoder().geocode(PLACE, deadline());
    // The second Lambda has 2,650 ms left when it starts. Each table call takes 100 ms, so it finds
    // the slot taken with 2,350 ms left: too little to wait and still ask.
    tickPerCall = 100;
    const out = await makeGeocoder().geocode(OTHER_PLACE, deadline(BUDGET.modelBy - 2650));

    expect(out).toEqual({ trace: "busy" });
    expect(fetches).toHaveLength(1);
    expect(sleeps).toEqual([]);
  });

  it("with under 2,500 ms left it gives busy before it claims anything, and with 2,500 it asks", async () => {
    const short = await makeGeocoder().geocode(PLACE, deadline(BUDGET.modelBy - 2499));

    expect(short).toEqual({ trace: "busy" });
    expect(fetches).toHaveLength(0);
    expect(slotPuts()).toHaveLength(0);

    const enough = await makeGeocoder().geocode(PLACE, deadline(BUDGET.modelBy - 2500));

    expect(enough.trace).toBe("called");
  });

  it("two requests across a second's boundary stay 1.1 s apart", async () => {
    // A request's write at 0.990 s. The next geocoder arrives at 1.000 s, in the next clock second.
    table.set("nominatim#last", { pk: "nominatim#last", writtenMs: T0 + 990 });
    clock = T0 + 1000;

    const out = await makeGeocoder().geocode(PLACE, deadline());

    expect(out.trace).toBe("called");
    expect(sleeps).toEqual([1090]); // from the read's return at 1.000 s to 2.090 s
    expect(fetches[0].atMs).toBe(T0 + 2090);
    expect(table.get("nominatim#last")?.writtenMs).toBe(T0 + 2090);
  });

  it("the wait counts from when the read returned, not from when the geocoder started", async () => {
    table.set("nominatim#last", { pk: "nominatim#last", writtenMs: T0 + 5300 });
    tickPerCall = 40; // the refused claim and the read each take 40 ms

    await makeGeocoder().geocode(PLACE, deadline());

    // Started at 5.300 s (cache read 40, claim 40, slot read 40): 5.420 s. The wait ends at 6.400 s.
    expect(sleeps).toEqual([980]);
  });

  it("a slot written exactly 1.1 s ago holds nothing", async () => {
    table.set("nominatim#last", { pk: "nominatim#last", writtenMs: T0 + 1000 });
    clock = T0 + 2100;

    await makeGeocoder().geocode(PLACE, deadline());

    expect(sleeps).toEqual([]);
    expect(fetches[0].atMs).toBe(T0 + 2100);
  });

  it("a claim refused again after the wait gives busy, and never tries a third time", async () => {
    table.set("nominatim#last", { pk: "nominatim#last", writtenMs: T0 + 5300 });
    // While this Lambda sleeps, another one claims the slot.
    const out = await makeGeocoder({
      sleep: async (ms) => {
        sleeps.push(ms);
        clock += ms;
        table.set("nominatim#last", { pk: "nominatim#last", writtenMs: clock });
      },
    }).geocode(PLACE, deadline());

    expect(out).toEqual({ trace: "busy" });
    expect(slotPuts()).toHaveLength(2);
    expect(sleeps).toHaveLength(1);
    expect(fetches).toHaveLength(0);
  });

  it("a slot that is gone when it is read is claimed again at once", async () => {
    ddbMock.on(PutCommand).callsFakeOnce(() => {
      throw new ConditionalCheckFailedException({ message: "The conditional request failed", $metadata: {} });
    }).callsFake((input: PutCommandInput) => applyPut(input));

    const out = await makeGeocoder().geocode(PLACE, deadline());

    expect(out.trace).toBe("called");
    expect(sleeps).toEqual([]);
    expect(slotPuts()).toHaveLength(2);
  });
});

// Review Focus 4 for real: Lambdas whose DynamoDB calls are in flight at the same time. Each call lands at
// its send time plus a latency, and a write checks its condition when it lands. The tests below never look
// at how a claim is built, only at the write times of the claims that landed and the requests that followed.
describe("Lambdas at once", () => {
  type Event = { atMs: number; seq: number; run: () => void };
  let events: Event[];
  let seq: number;

  function at(atMs: number, run: () => void): void {
    events.push({ atMs, seq: seq++, run });
  }

  // One Lambda: its own client over the one shared table. A claim takes `claim` ms to land and any other call `other` ms.
  function lambda(latency: { claim: number; other: number }) {
    const client = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
    const stub = mockClient(client);
    const lands = <T>(ms: number, apply: () => T) =>
      new Promise<T>((resolve, reject) => {
        at(clock + ms, () => {
          try {
            resolve(apply());
          } catch (err) {
            reject(err);
          }
        });
      });
    stub.on(GetCommand).callsFake((input: GetCommandInput) => lands(latency.other, () => ({ Item: table.get(input.Key?.pk as string) })));
    stub.on(PutCommand).callsFake((input: PutCommandInput) =>
      lands(String(input.Item?.pk).startsWith("nominatim#") ? latency.claim : latency.other, () => applyPut(input)),
    );
    return makeGeocoder({
      ddb: client,
      sleep: (ms) => {
        sleeps.push(ms);
        return new Promise((resolve) => at(clock + ms, resolve));
      },
    });
  }

  // A handler starts at `startMs` and asks for `place`.
  function startAt(startMs: number, geocoder: ReturnType<typeof makeGeocoder>, place: string): void {
    at(startMs, () => {
      void geocoder.geocode(place, new Deadline(startMs, () => clock));
    });
  }

  // Runs the events in time order. Between them every Lambda runs until it waits on the table or a sleep.
  async function runAll(): Promise<void> {
    for (;;) {
      await new Promise((resolve) => setImmediate(resolve));
      events.sort((a, b) => a.atMs - b.atMs || a.seq - b.seq);
      const next = events.shift();
      if (next === undefined) return;
      clock = Math.max(clock, next.atMs);
      next.run();
    }
  }

  // The rule: claims that landed are at least 1.1 s apart, and each one sent one request.
  function expectOneRequestPerClaimAndTheGap(): void {
    const landed = [...claimsApplied].sort((a, b) => a - b);
    const gaps = landed.slice(1).map((ms, i) => ms - landed[i]);
    expect(gaps.filter((gap) => gap < 1100), `claims landed at ${landed.join(", ")}`).toEqual([]);
    expect(fetches).toHaveLength(landed.length);
  }

  beforeEach(() => {
    events = [];
    seq = 0;
    clock = T0; // the events set the time from here
  });

  it("interleaving 1: a slow claim lands after a later Lambda's claim", async () => {
    // A starts 6 ms before the next second and its claim takes 12 ms to land. B starts at the second, and
    // its claim takes 2 ms, so it lands first.
    startAt(T0 + 5994, lambda({ claim: 12, other: 1 }), PLACE);
    startAt(T0 + 6000, lambda({ claim: 2, other: 1 }), OTHER_PLACE);

    await runAll();

    expectOneRequestPerClaimAndTheGap();
    expect(fetches.length).toBeGreaterThanOrEqual(1);
  });

  it("interleaving 2: a Lambda that waited out a gap lands its claim over the boundary", async () => {
    // P asks at 5.990 s. A arrives at 6.100 s and has to wait; its claim takes 15 ms to land. B arrives at 7.000 s.
    startAt(T0 + 5989, lambda({ claim: 1, other: 1 }), "Ayala Triangle");
    startAt(T0 + 6100, lambda({ claim: 15, other: 1 }), PLACE);
    startAt(T0 + 7000, lambda({ claim: 2, other: 1 }), OTHER_PLACE);

    await runAll();

    expectOneRequestPerClaimAndTheGap();
    expect(fetches.length).toBeGreaterThanOrEqual(2);
  });

  it("two claims 1,099 ms apart: the second is refused, waits 1 ms and goes", async () => {
    startAt(T0 + 5100, lambda({ claim: 0, other: 0 }), PLACE);
    startAt(T0 + 6199, lambda({ claim: 0, other: 0 }), OTHER_PLACE);

    await runAll();

    expect(claimsAttempted).toEqual([T0 + 5100, T0 + 6199, T0 + 6200]); // 6199 was refused
    expect(claimsApplied).toEqual([T0 + 5100, T0 + 6200]);
    expect(sleeps).toEqual([1]);
    expect(fetches.map((f) => f.atMs)).toEqual([T0 + 5100, T0 + 6200]);
  });

  it("two claims 1,100 ms apart: both go, with no wait", async () => {
    startAt(T0 + 5100, lambda({ claim: 0, other: 0 }), PLACE);
    startAt(T0 + 6200, lambda({ claim: 0, other: 0 }), OTHER_PLACE);

    await runAll();

    expect(claimsAttempted).toEqual([T0 + 5100, T0 + 6200]);
    expect(claimsApplied).toEqual([T0 + 5100, T0 + 6200]);
    expect(sleeps).toEqual([]);
    expect(fetches.map((f) => f.atMs)).toEqual([T0 + 5100, T0 + 6200]);
  });
});
