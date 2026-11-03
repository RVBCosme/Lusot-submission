// Samples (spec §4.5, C512, C522, C527, MS4-Q8): the list from samples/manifest.json, a run through
// the live pipeline, and, while model calls are stopped, the sample's saved seeding result.
import { createHash } from "node:crypto";
import { ConditionalCheckFailedException, DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { CopyObjectCommand, GetObjectCommand, type GetObjectCommandOutput, NoSuchKey, S3Client } from "@aws-sdk/client-s3";
import { GetParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient, PutCommand, UpdateCommand, type UpdateCommandInput } from "@aws-sdk/lib-dynamodb";
import type { APIGatewayProxyEventV2 } from "aws-lambda";
import { mockClient } from "aws-sdk-client-mock";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { handler } from "../src/index";
import { createManifest, listSamples, runSample, type SampleDeps } from "../src/samples";
import { createStopSwitch } from "../src/stopSwitch";
import { awsError } from "./awsError";

const NOW = "2026-10-30T10:06:40Z";
const BUCKET = "lusot-test01-uploads";
const DEVICE = "device-0123456789abcdef";
const REPORT_ID = /^r_[0-9a-f]{32}$/; // C32, T6
const LEVEL_SAMPLE = "s0123456789";
const SYNTHETIC_SAMPLE = "sabcdef0123";
const DRY_SAMPLE = "sfedcba9876";
const MANIFEST_KEY = "samples/manifest.json";
// The manifest as samples.py (Task 8) writes it, plus two fields that must never get out (C512). Each
// saved result holds GET /reports/{id}'s own fields, present on its rule: noFloodSeen on a done result,
// the level fields only with a level, and refusalReason only when refused.
const MANIFEST = {
  version: 1,
  samples: [
    {
      sampleId: LEVEL_SAMPLE,
      credit: "Photo by a donor, faces and plates blurred by Lusot",
      license: "used with permission",
      place: "Rizal Avenue, Manila",
      date: "2026-07-24",
      event: "Typhoon Carina",
      // The seeding run's date and final result (MS4-Q8 (b)), served only during a pause.
      savedAt: "2026-10-31",
      status: "done",
      noFloodSeen: false,
      level: "knee",
      landmark: "rim_three_quarters",
      passability: "NPLV",
      levelIsFloor: false,
      sourceNote: "SOURCE-NOTE-SENTINEL",
      notes: "NOTES-SENTINEL",
    },
    // Only a synthetic composite leaves out place and date (spec §4.5).
    {
      sampleId: SYNTHETIC_SAMPLE,
      credit: "Synthetic composite made by Lusot from open-licensed photos",
      license: "CC0 1.0",
      savedAt: "2026-10-31",
      status: "refused",
      refusalReason: "no_usable_reference",
    },
    {
      sampleId: DRY_SAMPLE,
      credit: "Photo by a contributor, CC BY 4.0, faces and plates blurred by Lusot",
      license: "CC BY 4.0",
      place: "Quezon City",
      date: "2026-08-02",
      savedAt: "2026-10-31",
      status: "done",
      noFloodSeen: true,
    },
  ],
};

const s3 = new S3Client({ region: "ap-southeast-1", credentials: { accessKeyId: "test", secretAccessKey: "test" } });
const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
const ssm = new SSMClient({ region: "ap-southeast-1" });
// Class mocks, so the clients index.ts's handler builds for itself answer from the same mocks.
const s3Mock = mockClient(S3Client);
const ddbMock = mockClient(DynamoDBDocumentClient);
const ssmMock = mockClient(SSMClient);

// Each test builds its own manifest memo and switch cache (T9).
function deps(now: () => number = () => Date.parse(NOW)): SampleDeps {
  const base = {
    ddb,
    s3,
    tableName: "reports",
    limitsTableName: "limits",
    bucketName: BUCKET,
    isStopped: createStopSwitch(ssm, "/lusot/stop/"),
    now,
  };
  return { ...base, manifest: createManifest(base) };
}

// GetObject's Body is a stream with the SDK's transformToString, the one method the code reads.
function objectBody(value: unknown): GetObjectCommandOutput["Body"] {
  const text = JSON.stringify(value);
  return { transformToString: async () => text } as unknown as GetObjectCommandOutput["Body"];
}

function serveManifest(): void {
  s3Mock.on(GetObjectCommand).callsFake(() => ({ Body: objectBody(MANIFEST) }));
}

function noSuchKey(): NoSuchKey {
  return new NoSuchKey({ message: "The specified key does not exist.", $metadata: { httpStatusCode: 404 } });
}

function sha256(text: string): string {
  return createHash("sha256").update(text).digest("hex");
}

// The mock never evaluates a ConditionExpression, so this fake does what DynamoDB would with the
// one condition take sends, and its exact text is checked below (T5).
let counts: Map<string, number>;
function fakeCounters(): void {
  counts = new Map();
  ddbMock.on(UpdateCommand).callsFake((input: UpdateCommandInput) => {
    const pk = input.Key?.pk as string;
    const values = input.ExpressionAttributeValues ?? {};
    const n = counts.get(pk);
    if (input.ConditionExpression !== undefined && n !== undefined && n >= values[":limit"]) {
      throw new ConditionalCheckFailedException({ message: "The conditional request failed", $metadata: {} });
    }
    counts.set(pk, (n ?? 0) + (values[":one"] ?? values[":minusOne"]));
    return {};
  });
}

function updates(): UpdateCommandInput[] {
  return ddbMock.commandCalls(UpdateCommand).map((call) => call.args[0].input);
}

async function run(sampleId: string | undefined, d: SampleDeps): Promise<{ statusCode: number; body: unknown }> {
  const res = await runSample(sampleId, DEVICE, d);
  return { statusCode: res.statusCode, body: JSON.parse(res.body) };
}

// Each URL names the bucket and its key, lasts 300 s and signs only host (C503, C512).
function expectLink(url: unknown, key: string): void {
  expect(typeof url).toBe("string");
  const parsed = new URL(url as string);
  expect(parsed.hostname).toBe(`${BUCKET}.s3.ap-southeast-1.amazonaws.com`);
  expect(parsed.pathname).toBe(`/${key}`);
  expect(parsed.searchParams.get("X-Amz-Expires")).toBe("300");
  expect(parsed.searchParams.get("X-Amz-SignedHeaders")).toBe("host");
}

// The environment index.ts's handler builds its own clients from.
function stubApiEnv(): void {
  vi.stubEnv("AWS_REGION", "ap-southeast-1");
  vi.stubEnv("TABLE_NAME", "reports");
  vi.stubEnv("INDEX_NAME", "reportId-index");
  vi.stubEnv("BUCKET_NAME", BUCKET);
  vi.stubEnv("STOP_PARAM_PREFIX", "/lusot/stop/");
  vi.stubEnv("LIMITS_TABLE_NAME", "limits");
  vi.stubEnv("FEED_INDEX_NAME", "feed-index");
  vi.stubEnv("INCHES_SHOWN", "false");
}

// The handler of a new container, so no manifest memo from an earlier test carries over.
async function coldHandler(): Promise<typeof handler> {
  vi.resetModules();
  return (await import("../src/index")).handler;
}

// The handler's catch answers 500, and logError's line holds the error's name and status, never its
// message, which can hold an ARN.
async function expectInternal(
  event: Partial<APIGatewayProxyEventV2>,
  error: string,
  status: number | undefined,
  entry: typeof handler = handler,
): Promise<void> {
  const logged = vi.spyOn(console, "error").mockImplementation(() => {});
  const res = await entry({ isBase64Encoded: false, ...event } as APIGatewayProxyEventV2);

  expect(res.statusCode).toBe(500);
  expect(JSON.parse(res.body)).toEqual({ error: "internal" });
  expect(logged).toHaveBeenCalledOnce();
  const line = logged.mock.calls[0][0] as string;
  expect(line).not.toContain("arn:");
  expect(JSON.parse(line)).toEqual({ msg: "request_failed", routeKey: event.routeKey, error, status });
  logged.mockRestore();
}

beforeEach(() => {
  s3Mock.reset();
  ddbMock.reset();
  ssmMock.reset();
  ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: "off" } });
  serveManifest();
  s3Mock.on(CopyObjectCommand).resolves({});
  ddbMock.on(PutCommand).resolves({});
  fakeCounters();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("GET /samples", () => {
  it("lists the manifest's fields and a 300 s photoUrl, and nothing else", async () => {
    const res = await listSamples(deps());

    expect(res.statusCode).toBe(200);
    const body = JSON.parse(res.body);
    expect(body).toStrictEqual({
      samples: [
        {
          sampleId: LEVEL_SAMPLE,
          credit: "Photo by a donor, faces and plates blurred by Lusot",
          license: "used with permission",
          place: "Rizal Avenue, Manila",
          date: "2026-07-24",
          event: "Typhoon Carina",
          photoUrl: expect.any(String),
        },
        {
          sampleId: SYNTHETIC_SAMPLE,
          credit: "Synthetic composite made by Lusot from open-licensed photos",
          license: "CC0 1.0",
          photoUrl: expect.any(String),
        },
        {
          sampleId: DRY_SAMPLE,
          credit: "Photo by a contributor, CC BY 4.0, faces and plates blurred by Lusot",
          license: "CC BY 4.0",
          place: "Quezon City",
          date: "2026-08-02",
          photoUrl: expect.any(String),
        },
      ],
    });
    expectLink(body.samples[0].photoUrl, `samples/${LEVEL_SAMPLE}.jpg`);
    expectLink(body.samples[1].photoUrl, `samples/${SYNTHETIC_SAMPLE}.jpg`);
    expectLink(body.samples[2].photoUrl, `samples/${DRY_SAMPLE}.jpg`);
    // C512: neither the source note nor any other stored field gets out.
    expect(res.body).not.toContain("SOURCE-NOTE-SENTINEL");
    expect(res.body).not.toContain("NOTES-SENTINEL");
    // One read of the manifest. Each link is signed locally, with no S3 call.
    expect(s3Mock.calls()).toHaveLength(1);
    expect(s3Mock.commandCalls(GetObjectCommand).map((call) => call.args[0].input)).toStrictEqual([{ Bucket: BUCKET, Key: MANIFEST_KEY }]);
  });

  it("lists no samples when the manifest is missing as NoSuchKey", async () => {
    s3Mock.on(GetObjectCommand).rejects(noSuchKey());

    const res = await listSamples(deps());

    expect(res.statusCode).toBe(200);
    expect(JSON.parse(res.body)).toStrictEqual({ samples: [] });
    expect(s3Mock.commandCalls(GetObjectCommand).map((call) => call.args[0].input)).toStrictEqual([{ Bucket: BUCKET, Key: MANIFEST_KEY }]);
  });

  it("reads the manifest at most once a minute", async () => {
    let nowMs = Date.parse(NOW);
    const d = deps(() => nowMs);

    // 0 s and 59 s share one read, and 61 s reads again, so a removed sample leaves the list within a minute.
    await listSamples(d);
    nowMs += 59_000;
    await runSample(LEVEL_SAMPLE, DEVICE, d);
    expect(s3Mock.commandCalls(GetObjectCommand)).toHaveLength(1);
    nowMs += 2_000;
    await listSamples(d);
    expect(s3Mock.commandCalls(GetObjectCommand)).toHaveLength(2);

    // A failed read isn't kept, so the next call reads again.
    nowMs += 61_000;
    // rejectsOnce would count from this stub's first call, so the one failure is explicit.
    let failed = false;
    s3Mock.on(GetObjectCommand).callsFake(() => {
      if (failed) return { Body: objectBody(MANIFEST) };
      failed = true;
      throw awsError("SlowDown", 503);
    });
    await expect(listSamples(d)).rejects.toMatchObject({ name: "SlowDown" });
    expect((await listSamples(d)).statusCode).toBe(200);
    expect(s3Mock.commandCalls(GetObjectCommand)).toHaveLength(4);
  });
});

describe("POST /samples/{sampleId}", () => {
  it("answers 404 when a listed sample's photo is missing as NoSuchKey", async () => {
    s3Mock.on(CopyObjectCommand).rejects(noSuchKey());

    // F1: on the copy's source, a 404 and never a 500. F11 accepts the pending item it leaves.
    expect(await run(LEVEL_SAMPLE, deps())).toEqual({ statusCode: 404, body: { error: "not_found" } });
    expect(s3Mock.commandCalls(CopyObjectCommand)).toHaveLength(1);
  });

  it("rethrows AccessDenied or any other S3 error on the manifest or the copy, so the handler answers 500", async () => {
    // F1: only NoSuchKey reads as missing, so an IAM fault never quietly empties the list.
    for (const [name, status] of [
      ["AccessDenied", 403],
      ["SlowDown", 503],
    ] as const) {
      s3Mock.on(GetObjectCommand).rejects(awsError(name, status));

      await expect(listSamples(deps())).rejects.toMatchObject({ name });
    }
    serveManifest();
    s3Mock.on(CopyObjectCommand).rejects(awsError("AccessDenied", 403));
    await expect(runSample(LEVEL_SAMPLE, DEVICE, deps())).rejects.toMatchObject({ name: "AccessDenied" });

    // Through the handler, which builds its own clients from the environment.
    stubApiEnv();
    // The two failed reads come first: a failed read isn't kept, while the run's good read stays in
    // the handler's memo for 60 s.
    for (const [name, status] of [
      ["AccessDenied", 403],
      ["SlowDown", 503],
    ] as const) {
      s3Mock.on(GetObjectCommand).rejects(awsError(name, status));
      await expectInternal({ routeKey: "GET /samples" }, name, status);
    }
    serveManifest();
    await expectInternal({ routeKey: "POST /samples/{sampleId}", pathParameters: { sampleId: LEVEL_SAMPLE } }, "AccessDenied", 403);
  });

  it("writes a pending sample report and copies its photo to raw/", async () => {
    // 999 ms past the second, so only a floored clock gives these values (F3).
    const res = await run(LEVEL_SAMPLE, deps(() => Date.parse(NOW) + 999));

    expect(res.statusCode).toBe(201);
    const puts = ddbMock.commandCalls(PutCommand);
    expect(puts).toHaveLength(1);
    const reportId = puts[0].args[0].input.Item?.reportId;
    expect(reportId).toMatch(REPORT_ID);
    // Exactly these fields: no location, no device field and no visibleUntil.
    expect(puts[0].args[0].input).toStrictEqual({
      TableName: "reports",
      Item: {
        pk: "SAMPLE",
        sk: `${NOW}#${reportId}`,
        reportId,
        mode: "sample",
        status: "pending",
        sampleId: LEVEL_SAMPLE,
        capturedAt: NOW,
        receivedAt: NOW,
        expiresAt: Date.parse(NOW) / 1000 + 604800,
      },
    });
    expect(JSON.stringify(puts[0].args[0].input)).not.toContain(sha256(DEVICE));
    const copies = s3Mock.commandCalls(CopyObjectCommand);
    expect(copies).toHaveLength(1);
    expect(copies[0].args[0].input).toStrictEqual({
      Bucket: BUCKET,
      CopySource: `${BUCKET}/samples/${LEVEL_SAMPLE}.jpg`,
      Key: `raw/${reportId}.jpg`,
    });
    // The item comes first, so the S3 event the copy raises finds it.
    expect(puts[0].calledBefore(copies[0])).toBe(true);
  });

  it("answers 201 with the reportId", async () => {
    const first = await runSample(LEVEL_SAMPLE, DEVICE, deps());
    const second = await runSample(LEVEL_SAMPLE, DEVICE, deps());

    expect(first.statusCode).toBe(201);
    const body = JSON.parse(first.body);
    expect(Object.keys(body)).toEqual(["reportId"]);
    expect(body.reportId).toMatch(REPORT_ID);
    expect(body.reportId).toBe(ddbMock.commandCalls(PutCommand)[0].args[0].input.Item?.reportId);
    // Each run is a report of its own.
    expect(JSON.parse(second.body).reportId).not.toBe(body.reportId);
  });

  it("caps runs at 5 per device and 30 in all, with C522's codes", async () => {
    const d = deps();
    for (let i = 0; i < 5; i++) expect((await runSample(LEVEL_SAMPLE, DEVICE, d)).statusCode).toBe(201);
    const sixth = await runSample(LEVEL_SAMPLE, DEVICE, d);
    expect(sixth.statusCode).toBe(429);
    expect(JSON.parse(sixth.body)).toEqual({ error: "device_limit" });
    // The seconds left in the UTC hour at 10:06:40.
    expect(sixth.headers["retry-after"]).toBe("3200");

    // Five more devices at 5 each bring the hour's runs to 30.
    for (let n = 0; n < 5; n++) {
      for (let i = 0; i < 5; i++) expect((await runSample(LEVEL_SAMPLE, `device-${n}-padding`, d)).statusCode).toBe(201);
    }
    const thirtyFirst = await runSample(LEVEL_SAMPLE, "device-another-one", d);
    expect(thirtyFirst.statusCode).toBe(429);
    expect(JSON.parse(thirtyFirst.body)).toEqual({ error: "global_cap" });
    expect(thirtyFirst.headers["retry-after"]).toBe("3200");
    expect(counts.get("sample#ALL#2026-10-30T10")).toBe(30);
    // Each of the 30 runs made one item and one copy, and the refusals neither.
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(30);
    expect(s3Mock.commandCalls(CopyObjectCommand)).toHaveLength(30);

    // T5: the exact updates, with :limit 5 for the device and 30 for the hour.
    const increment = (pk: string, limit: number) => ({
      TableName: "limits",
      Key: { pk },
      UpdateExpression: "ADD #n :one SET #expiresAt = :expiresAt",
      ConditionExpression: "attribute_not_exists(#n) OR #n < :limit",
      ExpressionAttributeNames: { "#n": "n", "#expiresAt": "expiresAt" },
      ExpressionAttributeValues: { ":one": 1, ":limit": limit, ":expiresAt": Date.parse("2026-10-30T12:00:00Z") / 1000 },
    });
    expect(updates().slice(0, 2)).toStrictEqual([
      increment(`sample#${sha256(DEVICE)}#2026-10-30T10`, 5),
      increment("sample#ALL#2026-10-30T10", 30),
    ]);
    // The day's cap in all is 150 (C534), and the day shared by every paid analysis is 300 (Codex finding 3); their
    // counters' keys have no hour.
    for (const update of updates().filter((u) => u.ConditionExpression !== undefined)) {
      const pk = String(update.Key?.pk);
      const limit =
        pk === "analysis#ALL#2026-10-30" ? 300 : pk === "sample#ALL#2026-10-30" ? 150 : pk.startsWith("sample#ALL#") ? 30 : 5;
      expect(update.ExpressionAttributeValues?.[":limit"], pk).toBe(limit);
    }
    expect(counts.get("sample#ALL#2026-10-30")).toBe(30);
    expect(counts.get("analysis#ALL#2026-10-30")).toBe(30);
  });

  it("stops runs while the uploads switch is set", async () => {
    ssmMock.on(GetParameterCommand, { Name: "/lusot/stop/uploads" }).resolves({ Parameter: { Value: "on" } });

    expect(await run(LEVEL_SAMPLE, deps())).toEqual({ statusCode: 503, body: { error: "uploads_paused" } });
    // The switch comes first: no manifest read, no count, no item and no copy.
    expect(s3Mock.calls()).toHaveLength(0);
    expect(ddbMock.calls()).toHaveLength(0);
  });

  it("answers 404 for a sample that isn't listed, before any count", async () => {
    for (const sampleId of ["s9999999999", undefined]) {
      expect(await run(sampleId, deps())).toEqual({ statusCode: 404, body: { error: "not_found" } });
    }
    expect(ddbMock.calls()).toHaveLength(0);
    expect(s3Mock.commandCalls(CopyObjectCommand)).toHaveLength(0);
  });

  it("passes X-Lusot-Device through the router to the limits", async () => {
    stubApiEnv();
    const event: Partial<APIGatewayProxyEventV2> = {
      routeKey: "POST /samples/{sampleId}",
      pathParameters: { sampleId: LEVEL_SAMPLE },
      headers: { "x-lusot-device": DEVICE },
      isBase64Encoded: false,
    };
    const res = await (await coldHandler())(event as APIGatewayProxyEventV2);

    expect(res.statusCode).toBe(201);
    // The handler's clock is the real one, so the hour is matched by its form.
    const [device, all] = updates();
    expect(device.Key?.pk).toMatch(new RegExp(`^sample#${sha256(DEVICE)}#\\d{4}-\\d{2}-\\d{2}T\\d{2}$`));
    expect(all.Key?.pk).toMatch(/^sample#ALL#\d{4}-\d{2}-\d{2}T\d{2}$/);
    // C520: only the hash is sent, never the id.
    for (const call of ddbMock.calls()) expect(JSON.stringify(call.args[0].input)).not.toContain(DEVICE);
  });

  it("answers a paused sample with its saved seeding result and starts no run", async () => {
    ssmMock.on(GetParameterCommand, { Name: "/lusot/stop/model-calls" }).resolves({ Parameter: { Value: "on" } });
    const d = deps();

    // MS4-Q8 (b), C527: marked as saved and dated, with the report's own fields from the manifest entry.
    expect(await run(LEVEL_SAMPLE, d)).toStrictEqual({
      statusCode: 200,
      body: {
        saved: true,
        savedAt: "2026-10-31",
        result: {
          status: "done",
          noFloodSeen: false,
          level: "knee",
          landmark: "rim_three_quarters",
          passability: "NPLV",
          levelIsFloor: false,
        },
      },
    });
    expect(await run(DRY_SAMPLE, d)).toStrictEqual({
      statusCode: 200,
      body: { saved: true, savedAt: "2026-10-31", result: { status: "done", noFloodSeen: true } },
    });
    expect(await run(SYNTHETIC_SAMPLE, d)).toStrictEqual({
      statusCode: 200,
      body: { saved: true, savedAt: "2026-10-31", result: { status: "refused", refusalReason: "no_usable_reference" } },
    });
    // The spec's order holds during a pause: an unknown id is still 404, and the uploads switch still wins.
    expect(await run("s9999999999", d)).toEqual({ statusCode: 404, body: { error: "not_found" } });
    ssmMock.on(GetParameterCommand, { Name: "/lusot/stop/uploads" }).resolves({ Parameter: { Value: "on" } });
    expect(await run(LEVEL_SAMPLE, deps())).toEqual({ statusCode: 503, body: { error: "uploads_paused" } });
    // No count, no item and no copy.
    expect(ddbMock.calls()).toHaveLength(0);
    expect(s3Mock.commandCalls(CopyObjectCommand)).toHaveLength(0);
  });

  it("refuses a saved result it can't serve, so the handler answers 500", async () => {
    ssmMock.on(GetParameterCommand, { Name: "/lusot/stop/model-calls" }).resolves({ Parameter: { Value: "on" } });
    const { savedAt: _savedAt, ...noDate } = MANIFEST.samples[2];
    const { status: _status, ...noStatus } = MANIFEST.samples[2];
    const drifted = [noDate, { ...noDate, savedAt: 20261031 }, noStatus, { ...noStatus, status: "failed" }];
    for (const entry of drifted) {
      s3Mock.on(GetObjectCommand).callsFake(() => ({ Body: objectBody({ version: 1, samples: [entry] }) }));

      // Never an empty "saved" answer: a 500, with no count, no item and no copy.
      await expect(runSample(DRY_SAMPLE, DEVICE, deps())).rejects.toMatchObject({ name: "SavedResultError" });
    }
    expect(ddbMock.calls()).toHaveLength(0);
    expect(s3Mock.commandCalls(CopyObjectCommand)).toHaveLength(0);

    // The handler logs the error's name, with no status since it isn't an AWS error.
    stubApiEnv();
    const event = { routeKey: "POST /samples/{sampleId}", pathParameters: { sampleId: DRY_SAMPLE } };
    await expectInternal(event, "SavedResultError", undefined, await coldHandler());
  });
});
