import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { GetParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient, QueryCommand, type QueryCommandInput } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { beforeEach, describe, expect, it } from "vitest";
import { createFeed, createMapPins, nearby, type PinDeps, publicPin } from "../src/pins";
import { createStopSwitch } from "../src/stopSwitch";

const NOW = "2026-10-30T10:06:40Z";
const CAPTURED_AT = "2026-10-30T10:05:12Z";
// Each visibleUntil is 1 s either side of NOW, built from an ISO string (F3).
const VISIBLE = Date.parse("2026-10-30T10:06:41Z") / 1000;
const HIDDEN = Date.parse("2026-10-30T10:06:39Z") / 1000;
const LINE = "Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.";
// The viewer's point, its 6-character cell and the 8 cells around it (C509).
const POINT = { lat: "14.6095", lng: "120.9894" };
const CELL = "wdw515";
const NEIGHBOURS = ["wdw51h", "wdw51k", "wdw517", "wdw516", "wdw514", "wdw50f", "wdw50g", "wdw50u"];
// At 14.6095° N, these longitudes lie 96.8 m, 107.6 m, 290.5 m and 301.3 m east of the point.
const EAST_97_M = 120.9903;
const EAST_108_M = 120.9904;
const EAST_290_M = 120.9921;
const EAST_301_M = 120.9922;
const DEMO = { credit: "Photo by a donor, faces and plates blurred by Lusot", place: "Rizal Avenue, Manila", event: "Typhoon Carina" };

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
const ssm = new SSMClient({ region: "ap-southeast-1" });
const ddbMock = mockClient(ddb);
const ssmMock = mockClient(ssm);

function deps(fields: Partial<PinDeps> = {}): PinDeps {
  return {
    ddb,
    tableName: "reports",
    feedIndexName: "feed-index",
    isStopped: createStopSwitch(ssm, "/lusot/stop/"),
    inchesShown: false,
    now: () => Date.parse(NOW),
    ...fields,
  };
}

let count = 0;
// A published live knee pin at the viewer's point, as the upload and the analysis Lambda leave it.
function item(fields: Record<string, unknown> = {}): Record<string, unknown> {
  const reportId = `r_${(count++).toString(16).padStart(32, "0")}`;
  return {
    pk: `GEO#${CELL}`,
    sk: `${CAPTURED_AT}#${reportId}`,
    reportId,
    mode: "live",
    status: "done",
    noFloodSeen: false,
    lat: 14.6095,
    lng: 120.9894,
    gpsAccuracyM: 12,
    nudgeM: 0,
    capturedAt: CAPTURED_AT,
    receivedAt: "2026-10-30T10:05:20Z",
    level: "knee",
    landmark: "rim_three_quarters",
    passability: "NPLV",
    levelIsFloor: false,
    basis: { vehicles: 1, people: 1 },
    flags: 0,
    published: true,
    feedPart: "live",
    visibleUntil: VISIBLE,
    expiresAt: Date.parse("2026-11-06T10:05:12Z") / 1000,
    ...fields,
  };
}

function demoItem(fields: Record<string, unknown> = {}): Record<string, unknown> {
  return item({ mode: "demo", feedPart: "demo", capturedAt: "2026-07-15T02:30:00Z", ...DEMO, ...fields });
}

// The mock never evaluates an expression. The viewer's cell holds every item, and each
// feed-index partition holds the items whose feedPart it names.
function store(items: Record<string, unknown>[]): void {
  ddbMock.on(QueryCommand).callsFake((input: QueryCommandInput) => {
    const values = input.ExpressionAttributeValues ?? {};
    if (":pk" in values) return { Items: values[":pk"] === `GEO#${CELL}` ? items : [] };
    return { Items: items.filter((stored) => stored.feedPart === values[":part"]) };
  });
}

function queries(): QueryCommandInput[] {
  return ddbMock.commandCalls(QueryCommand).map((call) => call.args[0].input);
}

function ids(res: { body: string }): string[] {
  return JSON.parse(res.body).pins.map((pin: { id: string }) => pin.id);
}

function features(res: { body: string }): { properties: { id: string; mode: string } }[] {
  return JSON.parse(res.body).features;
}

beforeEach(() => {
  ddbMock.reset();
  ssmMock.reset();
  ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: "off" } });
  ddbMock.on(QueryCommand).resolves({ Items: [] });
});

describe("public pins", () => {
  it("gives a public pin exactly its listed fields, rounded to 4 places", () => {
    const stored = item({
      lat: 14.609549,
      lng: 120.989351,
      flags: 2,
      basis: { vehicles: 1, people: 1, wheels: 2 },
      readings: [{ id: 1, kind: "wheel", landmark: "rim_three_quarters", level: "knee", used: true, dropped: null }],
      nudgeM: 30,
      deviceId: "device-0123456789abcdef",
      consentVersion: "a1b2c3d4",
      claimToken: "token-a",
      claimedAt: 1_793_354_725,
      photoKey: "blurred/r_x.jpg",
      overlayKey: "overlay/r_x.jpg",
      layersKey: "overlay/r_x.json",
      photoUrl: "https://example.invalid/photo",
    });

    const pin = publicPin(stored, false);

    expect(pin).toStrictEqual({
      id: stored.reportId,
      lat: 14.6095,
      lng: 120.9894,
      gpsAccuracyM: 12,
      capturedAt: CAPTURED_AT,
      mode: "live",
      level: "knee",
      landmark: "rim_three_quarters",
      passability: "NPLV",
      levelIsFloor: false,
      basis: { vehicles: 1, people: 1 },
      flags: 2,
    });
    for (const never of ["readings", "nudgeM", "deviceId", "consentVersion", "claimToken", "claimedAt", "photoKey", "overlayKey", "layersKey", "photoUrl", "pk", "sk", "reportId"]) {
      expect(pin).not.toHaveProperty(never);
    }

    const { gpsAccuracyM: _, ...noAccuracy } = stored;
    expect(publicPin(noAccuracy, false).gpsAccuracyM).toBeNull();

    const demo = demoItem();
    expect(publicPin(demo, false)).toStrictEqual({
      id: demo.reportId,
      lat: 14.6095,
      lng: 120.9894,
      gpsAccuracyM: 12,
      capturedAt: "2026-07-15T02:30:00Z",
      mode: "demo",
      level: "knee",
      landmark: "rim_three_quarters",
      passability: "NPLV",
      levelIsFloor: false,
      basis: { vehicles: 1, people: 1 },
      flags: 0,
      ...DEMO,
    });
  });

  it('shows depthInMin and depthInMax only while INCHES_SHOWN is "true"', async () => {
    const stored = item({ depthInMin: 17, depthInMax: 19 });

    const hidden = publicPin(stored, false);
    expect(hidden).not.toHaveProperty("depthInMin");
    expect(hidden).not.toHaveProperty("depthInMax");
    expect(publicPin(stored, true)).toMatchObject({ depthInMin: 17, depthInMax: 19 });

    // The routes pass the release gate's switch through (S12).
    store([stored]);
    const shown = JSON.parse((await createMapPins(deps({ inchesShown: true }))()).body).pins[0];
    expect(shown).toMatchObject({ depthInMin: 17, depthInMax: 19 });
    const off = JSON.parse((await createMapPins(deps())()).body).pins[0];
    expect(off).not.toHaveProperty("depthInMin");
  });
});

describe("GET /reports (nearby)", () => {
  it("reads the point's cell and its 8 neighbours, with no sort-key range", async () => {
    const res = await nearby(POINT, deps());

    expect(res.statusCode).toBe(200);
    const inputs = queries();
    expect(inputs).toHaveLength(9);
    expect(inputs.map((input) => input.ExpressionAttributeValues?.[":pk"]).sort()).toEqual(
      [CELL, ...NEIGHBOURS].map((cell) => `GEO#${cell}`).sort(),
    );
    for (const input of inputs) {
      expect(input).toStrictEqual({
        TableName: "reports",
        KeyConditionExpression: "#pk = :pk",
        FilterExpression: "#published = :true AND #visibleUntil > :now",
        ExpressionAttributeNames: { "#pk": "pk", "#published": "published", "#visibleUntil": "visibleUntil" },
        ExpressionAttributeValues: { ":pk": input.ExpressionAttributeValues?.[":pk"], ":true": true, ":now": Date.parse(NOW) / 1000 },
      });
    }
  });

  it("leaves out a pin past visibleUntil, an unpublished one, one 301 m away, and private, sample and eval items", async () => {
    const kept = item();
    const demo = demoItem({ visibleUntil: VISIBLE });
    const { published: _, ...unpublished } = item();
    store([
      item({ visibleUntil: HIDDEN }),
      unpublished,
      item({ lng: EAST_301_M }),
      item({ mode: "private" }),
      item({ mode: "sample", pk: "SAMPLE" }),
      item({ mode: "eval", pk: "EVAL" }),
      demo,
      kept,
    ]);

    const res = await nearby(POINT, deps());

    // The demo pin keeps its July capture time and still shows (C509).
    expect(ids(res)).toEqual([kept.reportId, demo.reportId]);
  });

  it("floors now to the second and leaves out a pin whose visibleUntil is that second", async () => {
    // 999 ms past NOW: unfloored, now would be NOW + 0.999 s (F3).
    const late = deps({ now: () => Date.parse(NOW) + 999 });
    const nowS = Date.parse(NOW) / 1000;
    const kept = item();
    store([item({ visibleUntil: nowS }), kept]);

    expect(ids(await nearby(POINT, late))).toEqual([kept.reportId]);
    await createMapPins(late)();
    await createFeed(late)();

    // Nearby's 9 cells, the map's 2 partitions and the feed's 1, each sent the whole second.
    expect(queries().map((input) => input.ExpressionAttributeValues?.[":now"])).toEqual(Array(12).fill(nowS));
  });

  it("defaults radius to 300 m and refuses 301 with 400 bad_radius", async () => {
    for (const radius of ["301", "0", "-5", "abc", "", "Infinity"]) {
      const res = await nearby({ ...POINT, radius }, deps());
      expect(res.statusCode, radius).toBe(400);
      expect(JSON.parse(res.body), radius).toEqual({ error: "bad_radius" });
    }
    expect(ddbMock.calls()).toHaveLength(0);

    const near = item({ lng: EAST_97_M });
    const past100 = item({ lng: EAST_108_M });
    const inside300 = item({ lng: EAST_290_M });
    store([near, past100, inside300, item({ lng: EAST_301_M })]);

    // The three share a capture time, so compare them as sets.
    const within300 = [near.reportId, past100.reportId, inside300.reportId].sort();
    expect(ids(await nearby(POINT, deps())).sort()).toEqual(within300);
    expect(ids(await nearby({ ...POINT, radius: "300" }, deps())).sort()).toEqual(within300);
    expect(ids(await nearby({ ...POINT, radius: "100" }, deps()))).toEqual([near.reportId]);
  });

  it("refuses a missing or bad lat or lng with 400 bad_point", async () => {
    const bad = [
      undefined,
      { lng: POINT.lng },
      { lat: POINT.lat },
      { lat: "91", lng: POINT.lng },
      { lat: "-91", lng: POINT.lng },
      { lat: POINT.lat, lng: "181" },
      { lat: "abc", lng: POINT.lng },
      { lat: "", lng: POINT.lng },
      { lat: POINT.lat, lng: "NaN" },
      { lat: "Infinity", lng: POINT.lng },
    ];
    for (const query of bad) {
      const res = await nearby(query, deps());
      expect(res.statusCode, JSON.stringify(query)).toBe(400);
      expect(JSON.parse(res.body)).toEqual({ error: "bad_point" });
    }
    expect(ddbMock.calls()).toHaveLength(0);
    expect(ssmMock.calls()).toHaveLength(0);

    expect((await nearby({ lat: "90", lng: "-180" }, deps())).statusCode).toBe(200);
  });

  it("returns at most 200 pins, newest first, as {pins}", async () => {
    const minutesAgo = (n: number) => new Date(Date.parse(NOW) - n * 60_000).toISOString().replace(".000Z", "Z");
    // 250 pins in a scrambled order: 7 and 250 share no factor, so i * 7 % 250 visits every minute once.
    store(Array.from({ length: 250 }, (_, i) => item({ capturedAt: minutesAgo((i * 7) % 250) })));

    const res = await nearby(POINT, deps());

    const body = JSON.parse(res.body);
    expect(Object.keys(body)).toEqual(["pins"]);
    expect(body.pins.map((pin: { capturedAt: string }) => pin.capturedAt)).toEqual(
      Array.from({ length: 200 }, (_, n) => minutesAgo(n)),
    );
  });
});

describe("GET /map/pins and GET /pins.geojson", () => {
  it("serves the map's live and demo pins from feed-index's two partitions", async () => {
    const live = item();
    const demo = demoItem();
    store([live, demo]);

    const res = await createMapPins(deps())();

    expect(res.statusCode).toBe(200);
    const pins = JSON.parse(res.body).pins;
    expect(pins.map((pin: { id: string; mode: string }) => [pin.id, pin.mode])).toEqual([
      [live.reportId, "live"],
      [demo.reportId, "demo"],
    ]);
    expect(pins[1]).toMatchObject(DEMO);
    expect(queries()).toStrictEqual(
      ["live", "demo"].map((part) => ({
        TableName: "reports",
        IndexName: "feed-index",
        KeyConditionExpression: "#feedPart = :part AND #visibleUntil > :now",
        ExpressionAttributeNames: { "#feedPart": "feedPart", "#visibleUntil": "visibleUntil" },
        ExpressionAttributeValues: { ":part": part, ":now": Date.parse(NOW) / 1000 },
      })),
    );
  });

  it("follows LastEvaluatedKey through every page of feed-index", async () => {
    const first = item();
    const second = item();
    const lastKey = { pk: first.pk, sk: first.sk, feedPart: "live", visibleUntil: VISIBLE };
    ddbMock
      .on(QueryCommand)
      .resolvesOnce({ Items: [first], LastEvaluatedKey: lastKey })
      .resolvesOnce({ Items: [second] })
      .resolves({ Items: [] });

    const res = await createMapPins(deps())();

    expect(ids(res)).toEqual([first.reportId, second.reportId]);
    const inputs = queries();
    expect(inputs).toHaveLength(3);
    expect(inputs[0]).not.toHaveProperty("ExclusiveStartKey");
    expect(inputs[1]).toMatchObject({ ExclusiveStartKey: lastKey, ExpressionAttributeValues: { ":part": "live" } });
    expect(inputs[2]).toMatchObject({ ExpressionAttributeValues: { ":part": "demo" } });
  });

  it("hides live pins from nearby, the map and the feed while publish is set, and keeps demo pins", async () => {
    // Only the publish switch is on, so a route that read any other switch would still show live pins.
    ssmMock.on(GetParameterCommand, { Name: "/lusot/stop/publish" }).resolves({ Parameter: { Value: "on" } });
    const demo = demoItem();
    store([item(), demo]);

    expect(ids(await nearby(POINT, deps()))).toEqual([demo.reportId]);
    expect(ids(await createMapPins(deps())())).toEqual([demo.reportId]);
    const feed = JSON.parse((await createFeed(deps())()).body);
    expect(feed.features).toEqual([]);
    expect(feed.notice).toBe(LINE);
  });

  it("serves the feed as a FeatureCollection of live pins with the screen line as its notice", async () => {
    const live = item({ lat: 14.609549, lng: 120.989351 });
    store([live, demoItem()]);

    const res = await createFeed(deps())();

    expect(res.statusCode).toBe(200);
    expect(res.headers).toEqual({ "content-type": "application/geo+json", "cache-control": "public, max-age=60" });
    expect(JSON.parse(res.body)).toStrictEqual({
      type: "FeatureCollection",
      notice: LINE,
      features: [
        {
          type: "Feature",
          geometry: { type: "Point", coordinates: [120.9894, 14.6095] },
          properties: {
            id: live.reportId,
            gpsAccuracyM: 12,
            capturedAt: CAPTURED_AT,
            mode: "live",
            level: "knee",
            landmark: "rim_three_quarters",
            passability: "NPLV",
            levelIsFloor: false,
            basis: { vehicles: 1, people: 1 },
            flags: 0,
          },
        },
      ],
    });
    // Only the live partition is read, so no demo pin can reach other maps (C517, S11).
    expect(queries().map((input) => input.ExpressionAttributeValues?.[":part"])).toEqual(["live"]);
  });

  it("reads the map's pins at most once every 30 s", async () => {
    store([item(), demoItem()]);
    const clock = { ms: Date.parse(NOW) };
    const map = createMapPins(deps({ now: () => clock.ms }));

    await map();
    clock.ms = Date.parse(NOW) + 29_000;
    await map();
    expect(queries().map((input) => input.ExpressionAttributeValues?.[":part"])).toEqual(["live", "demo"]);

    clock.ms = Date.parse(NOW) + 31_000;
    await map();
    expect(queries()).toHaveLength(4);
  });

  it("builds the feed at most once a minute", async () => {
    store([item()]);
    const clock = { ms: Date.parse(NOW) };
    const feed = createFeed(deps({ now: () => clock.ms }));

    await feed();
    clock.ms = Date.parse(NOW) + 59_000;
    await feed();
    expect(queries()).toHaveLength(1);

    clock.ms = Date.parse(NOW) + 61_000;
    await feed();
    expect(queries()).toHaveLength(2);
  });

  it("stops showing live pins within 90 s of publish being set", async () => {
    store([item()]);
    const clock = { ms: Date.parse(NOW) };
    const shared = deps({ now: () => clock.ms });
    // The worst case: another route reads the switch as off at 0 s, which caches it for 30 s,
    // and publish is set just after.
    expect(await shared.isStopped("publish", clock.ms)).toBe(false);
    ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: "on" } });

    // At 29 s the feed is built on the cached switch, and keeps that answer for 60 s.
    clock.ms = Date.parse(NOW) + 29_000;
    const feed = createFeed(shared);
    expect(features(await feed())).toHaveLength(1);

    clock.ms = Date.parse(NOW) + 91_000;
    expect(features(await feed())).toEqual([]);
  });

  it("stops showing live pins on the map within 60 s of publish being set", async () => {
    const live = item();
    const demo = demoItem();
    store([live, demo]);
    const clock = { ms: Date.parse(NOW) };
    const shared = deps({ now: () => clock.ms });
    // The same worst case: the switch is read as off at 0 s and cached for 30 s, then set.
    expect(await shared.isStopped("publish", clock.ms)).toBe(false);
    ssmMock.on(GetParameterCommand, { Name: "/lusot/stop/publish" }).resolves({ Parameter: { Value: "on" } });

    // At 29 s the map is built on the cached switch, and keeps that answer for 30 s.
    clock.ms = Date.parse(NOW) + 29_000;
    const map = createMapPins(shared);
    expect(ids(await map())).toEqual([live.reportId, demo.reportId]);

    clock.ms = Date.parse(NOW) + 61_000;
    expect(ids(await map())).toEqual([demo.reportId]);
  });
});
