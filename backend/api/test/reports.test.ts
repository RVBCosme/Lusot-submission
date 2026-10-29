import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, QueryCommand } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { beforeEach, describe, expect, it } from "vitest";
import { getReport, type ReportDeps } from "../src/reports";

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
const ddbMock = mockClient(ddb);
const deps: ReportDeps = { ddb, tableName: "reports", indexName: "reportId-index" };
const ID = "r_0123456789abcdef0123456789abcdef";
const CAPTURED_AT = "2026-10-30T10:05:12Z";
// The item as the upload leaves it (MS1), then the claim the analysis Lambda adds (C46).
const UPLOADED = { pk: "GEO#wdw515", sk: `${CAPTURED_AT}#${ID}`, reportId: ID, mode: "live", capturedAt: CAPTURED_AT, lat: 14.6095, lng: 120.9894, gpsAccuracyM: 12 };
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

beforeEach(() => {
  ddbMock.reset();
});

describe("GET /reports/{id}", () => {
  it("a known id queries reportId-index and returns its status", async () => {
    const stored = { pk: "GEO#wdw515", sk: `${CAPTURED_AT}#${ID}`, reportId: ID, mode: "live", capturedAt: CAPTURED_AT, lat: 14.6095, lng: 120.9894 };
    ddbMock
      .on(QueryCommand)
      .resolvesOnce({ Items: [{ ...stored, status: "failed", refusalReason: "pipeline_not_built" }] })
      .resolvesOnce({ Items: [{ ...stored, status: "pending" }] });

    const failed = await getReport(ID, deps);
    const pending = await getReport(ID, deps);

    expect(failed.statusCode).toBe(200);
    expect(JSON.parse(failed.body)).toEqual({ reportId: ID, status: "failed", refusalReason: "pipeline_not_built", capturedAt: CAPTURED_AT });
    expect(JSON.parse(pending.body)).toEqual({ reportId: ID, status: "pending", capturedAt: CAPTURED_AT });
    const queries = ddbMock.commandCalls(QueryCommand);
    expect(queries).toHaveLength(2);
    expect(queries[0].args[0].input).toMatchObject({
      TableName: "reports",
      IndexName: "reportId-index",
      KeyConditionExpression: "reportId = :id",
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

    expect(res.statusCode).toBe(200);
    expect(JSON.parse(res.body)).toEqual({
      reportId: ID,
      status: "done",
      capturedAt: CAPTURED_AT,
      noFloodSeen: false,
      level: "knee",
      landmark: "rim_three_quarters",
      passability: "NPLV",
      basis: { vehicles: 1, people: 1 },
      levelIsFloor: false,
    });
  });

  it("a done report with no flood seen returns noFloodSeen and nothing else new", async () => {
    ddbMock.on(QueryCommand).resolves({ Items: [{ ...UPLOADED, ...CLAIM, status: "done", noFloodSeen: true }] });

    const res = await getReport(ID, deps);

    expect(JSON.parse(res.body)).toEqual({ reportId: ID, status: "done", capturedAt: CAPTURED_AT, noFloodSeen: true });
  });

  it.each([
    ["refused", "too_dark"],
    ["failed", "model_error"],
  ])("refused and failed reports carry only refusalReason: %s/%s", async (status, refusalReason) => {
    ddbMock.on(QueryCommand).resolves({ Items: [{ ...UPLOADED, ...CLAIM, status, refusalReason }] });

    const res = await getReport(ID, deps);

    expect(JSON.parse(res.body)).toEqual({ reportId: ID, status, refusalReason, capturedAt: CAPTURED_AT });
  });

  it("a processing report carries no result or claim fields", async () => {
    ddbMock.on(QueryCommand).resolves({ Items: [{ ...UPLOADED, ...CLAIM, status: "processing" }] });

    const res = await getReport(ID, deps);

    expect(JSON.parse(res.body)).toEqual({ reportId: ID, status: "processing", capturedAt: CAPTURED_AT });
  });

  it("never returns the location, readings, photo key or the claim", async () => {
    const allowed = ["reportId", "status", "refusalReason", "capturedAt", "noFloodSeen", "level", "landmark", "passability", "basis", "levelIsFloor"];
    const forbidden = ["lat", "lng", "gpsAccuracyM", "readings", "photoKey", "overlayKey", "claimToken", "claimedAt", "pk", "sk"];
    // readings and overlayKey arrive in MS4 (spec §3.5), and basis holds a count beyond its two.
    const stored = {
      ...UPLOADED,
      ...CLAIM,
      ...LEVEL,
      basis: { ...LEVEL.basis, wheels: 2 },
      readings: [{ kind: "wheel", boxId: 3, landmark: "rim_three_quarters" }],
      overlayKey: `overlay/${ID}.jpg`,
    };
    for (const name of forbidden) expect(stored).toHaveProperty(name);
    ddbMock.on(QueryCommand).resolves({ Items: [stored] });

    const res = await getReport(ID, deps);
    const body = JSON.parse(res.body);

    expect(Object.keys(body).filter((key) => !allowed.includes(key))).toEqual([]);
    expect(body.basis).toEqual({ vehicles: 1, people: 1 });
    // Matched as quoted JSON names, so a value that only contains one (as "plate" contains "lat") can't trip it.
    for (const name of forbidden) expect(res.body).not.toContain(`"${name}"`);
  });
});
