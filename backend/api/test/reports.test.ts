import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { NoSuchKey, S3Client } from "@aws-sdk/client-s3";
import { DynamoDBDocumentClient, QueryCommand } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { beforeEach, describe, expect, it } from "vitest";
import { getReport, type ReportDeps } from "../src/reports";

const NOW = "2026-10-30T10:06:40Z";
const NOW_S = Date.parse(NOW) / 1000;
const BUCKET = "lusot-test01-uploads";

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
// A presigned GET is signed locally from the client's credentials, so these fake ones never leave the test.
const s3 = new S3Client({ region: "ap-southeast-1", credentials: { accessKeyId: "test", secretAccessKey: "test" } });
const ddbMock = mockClient(ddb);
const s3Mock = mockClient(s3);
// F10: the inches stay hidden here; only the INCHES_SHOWN test uses `shown`.
const deps: ReportDeps = {
  ddb,
  s3,
  tableName: "reports",
  indexName: "reportId-index",
  bucketName: BUCKET,
  inchesShown: false,
  now: () => Date.parse(NOW),
};
const shown: ReportDeps = { ...deps, inchesShown: true };
const ID = "r_0123456789abcdef0123456789abcdef";
const CAPTURED_AT = "2026-10-30T10:05:12Z";
// The upload's 3 h and 7 days after capture, each from an ISO string (F3).
const VISIBLE_UNTIL = Date.parse("2026-10-30T13:05:12Z") / 1000;
const EXPIRES_AT = Date.parse("2026-11-06T10:05:12Z") / 1000;
// The item as the upload leaves it (MS1), then the claim the analysis Lambda adds (C46).
const UPLOADED = {
  pk: "GEO#wdw515",
  sk: `${CAPTURED_AT}#${ID}`,
  reportId: ID,
  mode: "live",
  capturedAt: CAPTURED_AT,
  lat: 14.6095,
  lng: 120.9894,
  gpsAccuracyM: 12,
  visibleUntil: VISIBLE_UNTIL,
  expiresAt: EXPIRES_AT,
};
const CLAIM = { claimToken: "token-a", claimedAt: 1_793_354_725 };
// A knee reading from a wheel and a person, as Outcome.item_fields() writes it, plus the photo a level stores (C61).
const LEVEL = {
  status: "done",
  noFloodSeen: false,
  level: "knee",
  landmark: "rim_three_quarters",
  passability: "NPLV",
  levelIsFloor: false,
  basis: { vehicles: 1, people: 1 },
  photoKey: `blurred/${ID}.jpg`,
};
// readings as Task 14 stores them (C507): a dropped reference's level and inches are null.
const READINGS = [
  { id: 1, kind: "body", landmark: "not_visible", level: null, inches: null, used: false, dropped: null },
  { id: 2, kind: "wheel", landmark: "rim_three_quarters", level: "knee", inches: [17.3, 19.1], used: true, dropped: null },
  { id: 3, kind: "wheel", landmark: "hub", level: null, inches: null, used: false, dropped: "wheel_methods_disagree" },
];
const READINGS_HIDDEN = READINGS.map(({ inches: _inches, ...rest }) => rest);
// What MS3b and Task 14 add to a level result. Until they merge, only these fixtures hold them.
const EVIDENCE = {
  levelFrom: "geometry",
  depthInMin: 17.3,
  depthInMax: 19.1,
  readings: READINGS,
  overlayKey: `overlay/${ID}.jpg`,
  layersKey: `overlay/${ID}.json`,
};
const LINKS = [
  ["photoUrl", "photoKey"],
  ["overlayUrl", "overlayKey"],
  ["layersUrl", "layersKey"],
] as const;
const DEMO = { credit: "Photo by a donor, faces and plates blurred by Lusot", place: "Rizal Avenue, Manila", event: "Typhoon Carina" };

function without(item: Record<string, unknown>, ...names: string[]): Record<string, unknown> {
  const copy = { ...item };
  for (const name of names) delete copy[name];
  return copy;
}

// Each URL names the bucket and its key, and lasts 300 s (C503). It signs only host, so a browser's
// plain GET, which sends no other signed header, still matches the signature.
function expectLink(url: unknown, key: string): void {
  expect(typeof url).toBe("string");
  const parsed = new URL(url as string);
  expect(parsed.hostname).toBe(`${BUCKET}.s3.ap-southeast-1.amazonaws.com`);
  expect(parsed.pathname).toBe(`/${key}`);
  expect(parsed.searchParams.get("X-Amz-Expires")).toBe("300");
  expect(parsed.searchParams.get("X-Amz-SignedHeaders")).toBe("host");
}

beforeEach(() => {
  ddbMock.reset();
  s3Mock.reset();
});

describe("GET /reports/{id}", () => {
  it("a known id queries reportId-index and returns its status", async () => {
    ddbMock
      .on(QueryCommand)
      .resolvesOnce({ Items: [{ ...UPLOADED, status: "failed", refusalReason: "pipeline_not_built" }] })
      .resolvesOnce({ Items: [{ ...UPLOADED, status: "pending" }] });

    const failed = await getReport(ID, deps);
    const pending = await getReport(ID, deps);

    expect(failed.statusCode).toBe(200);
    expect(JSON.parse(failed.body)).toEqual({
      reportId: ID,
      status: "failed",
      refusalReason: "pipeline_not_built",
      capturedAt: CAPTURED_AT,
      mode: "live",
      published: false,
    });
    expect(JSON.parse(pending.body)).toEqual({ reportId: ID, status: "pending", capturedAt: CAPTURED_AT, mode: "live", published: false });
    const queries = ddbMock.commandCalls(QueryCommand);
    expect(queries).toHaveLength(2);
    // F5: the attribute name goes through a placeholder.
    expect(queries[0].args[0].input).toEqual({
      TableName: "reports",
      IndexName: "reportId-index",
      KeyConditionExpression: "#reportId = :id",
      ExpressionAttributeNames: { "#reportId": "reportId" },
      ExpressionAttributeValues: { ":id": ID },
    });
  });

  it("an unknown id gives 404", async () => {
    ddbMock.on(QueryCommand).resolves({ Items: [] });

    const res = await getReport(ID, deps);

    expect(res.statusCode).toBe(404);
    expect(JSON.parse(res.body)).toEqual({ error: "not_found" });
  });

  it.each([undefined, "", "r_123", "r_0123456789ABCDEF0123456789abcdef", `${ID}0`, `../${ID}`])(
    "a malformed id gives 404 without querying: %s",
    async (id) => {
      const res = await getReport(id, deps);

      expect(res.statusCode).toBe(404);
      expect(JSON.parse(res.body)).toEqual({ error: "not_found" });
      expect(ddbMock.calls()).toHaveLength(0);
    },
  );

  it("a done report with a level returns the level fields", async () => {
    ddbMock.on(QueryCommand).resolves({ Items: [{ ...UPLOADED, ...CLAIM, ...LEVEL }] });

    const res = await getReport(ID, deps);
    const body = JSON.parse(res.body);

    expect(res.statusCode).toBe(200);
    expect(body).toEqual({
      reportId: ID,
      status: "done",
      capturedAt: CAPTURED_AT,
      mode: "live",
      published: false,
      noFloodSeen: false,
      level: "knee",
      landmark: "rim_three_quarters",
      passability: "NPLV",
      basis: { vehicles: 1, people: 1 },
      levelIsFloor: false,
      gpsAccuracyM: 12,
      photoUrl: expect.any(String),
    });
    expectLink(body.photoUrl, LEVEL.photoKey);
  });

  it("a done report with no flood seen returns noFloodSeen and nothing else new", async () => {
    ddbMock.on(QueryCommand).resolves({ Items: [{ ...UPLOADED, ...CLAIM, status: "done", noFloodSeen: true }] });

    const res = await getReport(ID, deps);

    expect(JSON.parse(res.body)).toEqual({
      reportId: ID,
      status: "done",
      capturedAt: CAPTURED_AT,
      mode: "live",
      published: false,
      noFloodSeen: true,
    });
  });

  it.each([
    ["refused", "too_dark"],
    ["failed", "model_error"],
  ])("refused and failed reports carry only refusalReason: %s/%s", async (status, refusalReason) => {
    ddbMock.on(QueryCommand).resolves({ Items: [{ ...UPLOADED, ...CLAIM, status, refusalReason }] });

    const res = await getReport(ID, deps);

    expect(JSON.parse(res.body)).toEqual({
      reportId: ID,
      status,
      refusalReason,
      capturedAt: CAPTURED_AT,
      mode: "live",
      published: false,
    });
  });

  it("a processing report carries no result or claim fields", async () => {
    ddbMock.on(QueryCommand).resolves({ Items: [{ ...UPLOADED, ...CLAIM, status: "processing" }] });

    const res = await getReport(ID, deps);

    expect(JSON.parse(res.body)).toEqual({ reportId: ID, status: "processing", capturedAt: CAPTURED_AT, mode: "live", published: false });
  });

  it("never returns the location, a stored key, the claim or an unlisted field", async () => {
    const allowed = [
      "reportId",
      "status",
      "refusalReason",
      "capturedAt",
      "noFloodSeen",
      "level",
      "landmark",
      "passability",
      "basis",
      "levelIsFloor",
      "mode",
      "published",
      "levelFrom",
      "readings",
      "gpsAccuracyM",
      "photoUrl",
      "overlayUrl",
      "layersUrl",
      "credit",
      "place",
      "event",
    ];
    const forbidden = [
      "lat",
      "lng",
      "nudgeM",
      "consentVersion",
      "photoKey",
      "overlayKey",
      "layersKey",
      "claimToken",
      "claimedAt",
      "pk",
      "sk",
      "feedPart",
      "visibleUntil",
      "expiresAt",
      "receivedAt",
      "flags",
      "seed",
      "sampleId",
      "demoSource",
      "depthInMin",
      "depthInMax",
    ];
    // Every field an item can hold, on a demo pin so that credit, place and event come back too.
    // basis holds a count beyond its two, and each reading a field beyond its six.
    const stored = {
      ...UPLOADED,
      ...CLAIM,
      ...LEVEL,
      ...EVIDENCE,
      ...DEMO,
      mode: "demo",
      published: true,
      feedPart: "demo",
      nudgeM: 0,
      consentVersion: "0a1b2c3d",
      receivedAt: "2026-10-30T10:05:20Z",
      flags: 2,
      seed: true,
      sampleId: "s_mandaluyong_knee",
      demoSource: "consented/donor-01.jpg",
      basis: { ...LEVEL.basis, wheels: 2 },
      readings: READINGS.map((reading) => ({ ...reading, deciding: reading.used })),
    };
    for (const name of forbidden) expect(stored).toHaveProperty(name);
    ddbMock.on(QueryCommand).resolves({ Items: [stored] });

    const res = await getReport(ID, deps);
    const body = JSON.parse(res.body);

    expect(res.statusCode).toBe(200);
    expect(Object.keys(body).filter((key) => !allowed.includes(key))).toEqual([]);
    expect(body.basis).toEqual({ vehicles: 1, people: 1 });
    expect(body.readings).toHaveLength(READINGS.length);
    for (const reading of body.readings) expect(Object.keys(reading).sort()).toEqual(["dropped", "id", "kind", "landmark", "level", "used"]);
    // Matched as quoted JSON names, so a value that only contains one (as "plate" contains "lat") can't trip it.
    for (const name of [...forbidden, "inches", "deciding", "wheels"]) expect(res.body).not.toContain(`"${name}"`);
  });

  it("answers 404 past expiresAt, whatever the item holds", async () => {
    // A published live pin still inside its visibleUntil, as DynamoDB's TTL can leave it days past expiresAt.
    const pin = { ...UPLOADED, ...CLAIM, ...LEVEL, ...EVIDENCE, published: true, feedPart: "live", visibleUntil: NOW_S + 3600 };
    ddbMock
      .on(QueryCommand)
      .resolvesOnce({ Items: [{ ...pin, expiresAt: NOW_S }] })
      .resolvesOnce({ Items: [{ ...pin, expiresAt: Date.parse("2026-10-27T10:06:40Z") / 1000 }] })
      .resolvesOnce({ Items: [without(pin, "expiresAt")] })
      .resolvesOnce({ Items: [{ ...pin, expiresAt: NOW_S + 1 }] });

    const atExpiry = await getReport(ID, deps);
    const daysPast = await getReport(ID, deps);
    const noExpiry = await getReport(ID, deps);
    const justBefore = await getReport(ID, deps);

    for (const res of [atExpiry, daysPast, noExpiry]) {
      expect(res.statusCode).toBe(404);
      expect(JSON.parse(res.body)).toEqual({ error: "not_found" });
    }
    expect(justBefore.statusCode).toBe(200);
    expect(JSON.parse(justBefore.body)).toMatchObject({ reportId: ID, status: "done", published: true });
  });

  it("returns published true only for a published pin", async () => {
    const level = { ...UPLOADED, ...CLAIM, ...LEVEL };
    ddbMock
      .on(QueryCommand)
      .resolvesOnce({ Items: [{ ...level, published: true, feedPart: "live" }] })
      .resolvesOnce({ Items: [{ ...level, published: false }] })
      .resolvesOnce({ Items: [level] })
      .resolvesOnce({ Items: [{ ...level, published: "true" }] });

    const published: unknown[] = [];
    for (let i = 0; i < 4; i++) published.push(JSON.parse((await getReport(ID, deps)).body).published);

    expect(published).toEqual([true, false, false, false]);
  });

  it("gives a level result readings, its accuracy and three 300 s links on its stored keys", async () => {
    const stored = { ...UPLOADED, ...CLAIM, ...LEVEL, ...EVIDENCE };
    ddbMock.on(QueryCommand).resolves({ Items: [stored] });

    const body = JSON.parse((await getReport(ID, deps)).body);

    expect(body.readings).toEqual(READINGS_HIDDEN);
    expect(body.gpsAccuracyM).toBe(12);
    for (const [field, key] of LINKS) expectLink(body[field], stored[key]);
  });

  it("issues a live or demo report's links while visibleUntil > now, and other modes' until expiresAt", async () => {
    const level = { ...UPLOADED, ...CLAIM, ...LEVEL, ...EVIDENCE };
    const oneSecondPast = Date.parse("2026-10-30T10:06:39Z") / 1000;
    const cases: [Record<string, unknown>, boolean][] = [
      [{ ...level, visibleUntil: oneSecondPast }, false],
      [{ ...level, visibleUntil: NOW_S }, false],
      [{ ...level, visibleUntil: NOW_S + 1 }, true],
      // A pin without visibleUntil gets none, so a check written as `visibleUntil <= now` fails here.
      [without(level, "visibleUntil"), false],
      [{ ...level, ...DEMO, mode: "demo", visibleUntil: oneSecondPast }, false],
      [{ ...level, ...DEMO, mode: "demo", visibleUntil: NOW_S + 1 }, true],
      [without({ ...level, ...DEMO, mode: "demo" }, "visibleUntil"), false],
      [{ ...level, mode: "private", visibleUntil: oneSecondPast }, true],
      [without({ ...level, pk: "SAMPLE", mode: "sample" }, "visibleUntil"), true],
      [without({ ...level, pk: "EVAL", mode: "eval" }, "visibleUntil"), true],
      // An unknown mode, or none, gets no links, even while visible.
      [{ ...level, mode: "bogus" }, false],
      [without(level, "mode"), false],
    ];

    for (const [item, linked] of cases) {
      ddbMock.on(QueryCommand).resolves({ Items: [item] });

      const body = JSON.parse((await getReport(ID, deps)).body);

      expect(body.level).toBe("knee");
      for (const [field, key] of LINKS) {
        if (linked) expectLink(body[field], level[key]);
        else expect(body).not.toHaveProperty(field);
      }
    }
  });

  it("gives no links without a level", async () => {
    // Keys stored on each, so only the missing level keeps the links back.
    const keys = { photoKey: LEVEL.photoKey, overlayKey: EVIDENCE.overlayKey, layersKey: EVIDENCE.layersKey };
    ddbMock
      .on(QueryCommand)
      .resolvesOnce({ Items: [{ ...UPLOADED, ...CLAIM, ...keys, status: "done", noFloodSeen: true }] })
      .resolvesOnce({ Items: [{ ...UPLOADED, ...CLAIM, ...keys, status: "refused", refusalReason: "too_dark" }] })
      .resolvesOnce({ Items: [{ ...UPLOADED, ...CLAIM, ...keys, status: "failed", refusalReason: "model_error" }] });

    for (let i = 0; i < 3; i++) {
      const res = await getReport(ID, deps);
      const body = JSON.parse(res.body);

      expect(res.statusCode).toBe(200);
      for (const [field] of LINKS) expect(body).not.toHaveProperty(field);
      expect(body).not.toHaveProperty("readings");
    }
  });

  it("presigns from the stored keys with no S3 call, even when an object is gone", async () => {
    // S3's 7-day rule can remove a photo before TTL deletes its item, and an interrupted remove can leave
    // an item without its photos. The link is signed anyway, and S3 answers it with its own error.
    s3Mock.onAnyCommand().rejects(new NoSuchKey({ message: "The specified key does not exist.", $metadata: {} }));
    const level = { ...UPLOADED, ...CLAIM, ...LEVEL, ...EVIDENCE };
    ddbMock
      .on(QueryCommand)
      .resolvesOnce({ Items: [level] })
      .resolvesOnce({ Items: [without(level, "overlayKey", "layersKey")] })
      .resolvesOnce({ Items: [without(level, "photoKey")] });

    const all = JSON.parse((await getReport(ID, deps)).body);
    const photoOnly = JSON.parse((await getReport(ID, deps)).body);
    const noPhoto = JSON.parse((await getReport(ID, deps)).body);

    for (const [field, key] of LINKS) expectLink(all[field], level[key]);
    expectLink(photoOnly.photoUrl, LEVEL.photoKey);
    expect(photoOnly).not.toHaveProperty("overlayUrl");
    expect(photoOnly).not.toHaveProperty("layersUrl");
    expect(noPhoto).not.toHaveProperty("photoUrl");
    expectLink(noPhoto.overlayUrl, EVIDENCE.overlayKey);
    expectLink(noPhoto.layersUrl, EVIDENCE.layersKey);
    expect(s3Mock.calls()).toHaveLength(0);
  });

  it('returns levelFrom on a level result, and the inches only while INCHES_SHOWN is "true"', async () => {
    ddbMock.on(QueryCommand).resolves({ Items: [{ ...UPLOADED, ...CLAIM, ...LEVEL, ...EVIDENCE }] });

    const hiddenRes = await getReport(ID, deps);
    const shownRes = await getReport(ID, shown);
    const hidden = JSON.parse(hiddenRes.body);
    const visible = JSON.parse(shownRes.body);

    expect(hidden.levelFrom).toBe("geometry");
    expect(hidden).not.toHaveProperty("depthInMin");
    expect(hidden).not.toHaveProperty("depthInMax");
    expect(hidden.readings).toEqual(READINGS_HIDDEN);
    for (const name of ["inches", "depthInMin", "depthInMax"]) expect(hiddenRes.body).not.toContain(`"${name}"`);
    expect(visible.levelFrom).toBe("geometry");
    expect(visible.depthInMin).toBe(17.3);
    expect(visible.depthInMax).toBe(19.1);
    expect(visible.readings).toEqual(READINGS);
  });

  it("adds credit, place and event to a demo pin", async () => {
    const level = { ...UPLOADED, ...CLAIM, ...LEVEL, published: true };
    // A demo pin's photo under demo/, visible to the end of its --until day in Manila and kept 7 days more (C510).
    const demo = {
      ...level,
      ...DEMO,
      mode: "demo",
      feedPart: "demo",
      photoKey: `demo/blurred/${ID}.jpg`,
      visibleUntil: Date.parse("2026-11-08T23:59:59+08:00") / 1000,
      expiresAt: Date.parse("2026-11-15T23:59:59+08:00") / 1000,
    };
    ddbMock
      .on(QueryCommand)
      .resolvesOnce({ Items: [demo] })
      .resolvesOnce({ Items: [without(demo, "event")] })
      .resolvesOnce({ Items: [{ ...level, ...DEMO, feedPart: "live" }] });

    const withEvent = JSON.parse((await getReport(ID, deps)).body);
    const noEvent = JSON.parse((await getReport(ID, deps)).body);
    const live = JSON.parse((await getReport(ID, deps)).body);

    expect(withEvent).toMatchObject({ mode: "demo", published: true, ...DEMO });
    expectLink(withEvent.photoUrl, demo.photoKey);
    expect(noEvent).toMatchObject({ mode: "demo", credit: DEMO.credit, place: DEMO.place });
    expect(noEvent).not.toHaveProperty("event");
    expect(live.mode).toBe("live");
    for (const name of ["credit", "place", "event"]) expect(live).not.toHaveProperty(name);
  });
});
