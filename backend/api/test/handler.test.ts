import { createHash } from "node:crypto";
import { format } from "node:util";
import { ConditionalCheckFailedException, TransactionCanceledException } from "@aws-sdk/client-dynamodb";
import { GetParameterCommand } from "@aws-sdk/client-ssm";
import { GetCommand, PutCommand, QueryCommand, TransactWriteCommand, UpdateCommand, type UpdateCommandInput } from "@aws-sdk/lib-dynamodb";
import type { APIGatewayProxyEventV2 } from "aws-lambda";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { handler } from "../src/index";
import { awsError } from "./awsError";
import {
  BUCKET,
  coldHandler,
  DEMO_ID,
  ddbMock,
  ENV_NAMES,
  ID,
  MODEL_KEY_PARAM,
  NOW,
  PIN,
  ROUTE_KEYS,
  type RouteKey,
  request,
  resetMocks,
  s3Mock,
  serve,
  ssmMock,
  stubApiEnv,
  UPLOAD as UPLOAD_FIELDS,
} from "./routeFixtures";

const UPLOAD = JSON.stringify({ lat: 14.6095, lng: 120.9894, gpsAccuracyM: 12, capturedAt: new Date().toISOString() });

// Sentinels that must never reach a log (CLAUDE.md, spec §4.6): the caller's IP, its device id and
// the id's SHA-256, and a point that only the upload body and the nearby query hold. Ask Lusot adds a
// question's word and a "dito" point next to PIN, inside Metro Manila, so its pins are read (its spec AK7).
const SENTINEL_IP = "203.0.113.7";
const SENTINEL_DEVICE = "device-5e771ne1-0123456789";
const SENTINEL_LAT = "14.123456";
const SENTINEL_LNG = "121.123456";
const SENTINEL_WORD = "Sentinelquestionword";
const SENTINEL_HERE_LAT = "14.609517";
const SENTINEL_HERE_LNG = "120.989417";
const SENTINELS = [
  SENTINEL_IP,
  SENTINEL_DEVICE,
  createHash("sha256").update(SENTINEL_DEVICE).digest("hex"),
  SENTINEL_LAT,
  SENTINEL_LNG,
  SENTINEL_WORD,
  SENTINEL_HERE_LAT,
  SENTINEL_HERE_LNG,
];

function sentinelRequest(routeKey: RouteKey): APIGatewayProxyEventV2 {
  const fields: Partial<APIGatewayProxyEventV2> = {
    headers: { "x-lusot-device": SENTINEL_DEVICE },
    requestContext: {
      http: { method: routeKey.split(" ")[0], path: "/", protocol: "HTTP/1.1", sourceIp: SENTINEL_IP, userAgent: "lusot-test" },
    } as APIGatewayProxyEventV2["requestContext"],
  };
  if (routeKey === "POST /uploads") {
    fields.body = JSON.stringify({ ...UPLOAD_FIELDS, lat: Number(SENTINEL_LAT), lng: Number(SENTINEL_LNG) });
  }
  if (routeKey === "GET /reports") fields.queryStringParameters = { lat: SENTINEL_LAT, lng: SENTINEL_LNG };
  if (routeKey === "POST /ask") {
    const here = { lat: Number(SENTINEL_HERE_LAT), lng: Number(SENTINEL_HERE_LNG), accuracyM: 20 };
    fields.body = JSON.stringify({ question: `${SENTINEL_WORD} may baha ba dito?`, here });
  }
  return request(routeKey, fields);
}

// The status a route gives when its `failAt`-th DynamoDB or S3 call (of `calls` in its success) fails. MS4's
// routes give 500. POST /ask degrades instead (its spec §5.4, C736): its calls are the two question counters, the
// spend counter's read, the nine cells of the pins read, then the spend write. A failed counter is a 500; an
// unreadable spend counter pauses model calls and answers with the plain list; a failed pins read is a 503
// ask_unavailable; a failed spend write keeps the answer.
function failedStatus(routeKey: RouteKey, failAt: number, calls: number): number {
  if (routeKey !== "POST /ask") return 500;
  if (failAt <= 2) return 500;
  if (failAt === 3 || failAt === calls) return 200;
  return 503;
}

// Every line written through console, as console would format it.
function captureConsole(): string[] {
  const lines: string[] = [];
  for (const method of ["log", "info", "warn", "error", "debug", "trace"] as const) {
    vi.spyOn(console, method).mockImplementation((...args: unknown[]) => {
      lines.push(format(...args));
    });
  }
  return lines;
}

function awsCalls(): number {
  return ddbMock.calls().length + s3Mock.calls().length;
}

// As DynamoDB words it: the reasons come in the order of the items, and "None" marks one that passed.
function cancelled(...codes: string[]): TransactionCanceledException {
  return new TransactionCanceledException({
    message: `Transaction cancelled, please refer cancellation reasons for specific reasons [${codes.join(", ")}]`,
    $metadata: { httpStatusCode: 400 },
    CancellationReasons: codes.map((Code) => (Code === "None" ? { Code } : { Code, Message: "The conditional request failed" })),
  });
}

type Sent = { kind: string; input: Record<string, unknown> };

// Each DynamoDB command input the mock received, a transaction's items one by one. Ask Lusot's GetItem
// reads (the spend counter, the place cache, the Nominatim slot) use no ProjectionExpression, so they hold
// no placeholder; they are listed so that stays checked.
function sentInputs(): Sent[] {
  const kinds = [
    ["GetCommand", GetCommand],
    ["QueryCommand", QueryCommand],
    ["UpdateCommand", UpdateCommand],
    ["PutCommand", PutCommand],
    ["TransactWriteCommand", TransactWriteCommand],
  ] as const;
  const sent: Sent[] = [];
  for (const call of ddbMock.calls()) {
    const command = call.args[0];
    const kind = kinds.find(([, type]) => command instanceof type)?.[0] ?? "unknown";
    const input = command.input as Record<string, unknown>;
    if (kind !== "TransactWriteCommand") {
      sent.push({ kind, input });
      continue;
    }
    for (const item of input.TransactItems as Record<string, Record<string, unknown>>[]) {
      for (const [op, inner] of Object.entries(item)) sent.push({ kind: `${kind}.${op}`, input: inner });
    }
  }
  return sent;
}

const EXPRESSIONS = ["KeyConditionExpression", "FilterExpression", "UpdateExpression", "ConditionExpression"] as const;
const KEYWORDS = /\b(AND|OR|NOT|SET|ADD|REMOVE|DELETE|BETWEEN|IN)\b/g;
const FUNCTIONS = /\b(attribute_exists|attribute_not_exists|attribute_type|begins_with|contains|size|if_not_exists|list_append)\s*\(/g;
const PLACEHOLDERS = /[#:][A-Za-z0-9_]+/g;

// The words left once the placeholders, keywords and functions are taken out: each is a bare name.
function bareNames(expression: string): string[] {
  const rest = expression.replace(PLACEHOLDERS, " ").replace(FUNCTIONS, " (").replace(KEYWORDS, " ");
  return rest.match(/[A-Za-z0-9_]+/g) ?? [];
}

beforeEach(() => {
  stubApiEnv();
});

afterEach(() => {
  resetMocks();
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("handler", () => {
  it.each([
    ["POST /uploads", { routeKey: "POST /uploads", body: UPLOAD, isBase64Encoded: false }],
    ["GET /reports/{id}", { routeKey: "GET /reports/{id}", pathParameters: { id: "r_0123456789abcdef0123456789abcdef" }, isBase64Encoded: false }],
  ])("a failed AWS call on %s gives 500 and logs no ARN", async (routeKey, event) => {
    const logged = vi.spyOn(console, "error").mockImplementation(() => {});
    ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: "off" } });
    ddbMock.on(PutCommand).rejects(awsError("AccessDeniedException", 400));
    ddbMock.on(QueryCommand).rejects(awsError("AccessDeniedException", 400));

    const res = await handler(event as APIGatewayProxyEventV2);

    expect(res.statusCode).toBe(500);
    expect(JSON.parse(res.body)).toEqual({ error: "internal" });
    expect(logged).toHaveBeenCalledOnce();
    const line = logged.mock.calls[0][0] as string;
    expect(line).not.toContain("arn:");
    expect(JSON.parse(line)).toEqual({ msg: "request_failed", routeKey, error: "AccessDeniedException", status: 400 });
  });
});

// Each test gets new containers, so no switch cache or memo carries over (T9).
describe("handler, in a new container", () => {
  beforeEach(() => {
    // The presigners and the routes read the clock themselves, so pin it.
    vi.setSystemTime(Date.parse(NOW));
    serve();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("builds its clients and settings once, on the first request", async () => {
    for (const name of ENV_NAMES) vi.stubEnv(name, undefined);
    vi.resetModules();
    // Importing reads nothing from the environment, so a cold start can't fail before a request.
    const { handler: cold } = await import("../src/index");
    stubApiEnv();
    expect((await cold(request("GET /reports/{id}"))).statusCode).toBe(200);

    vi.stubEnv("TABLE_NAME", undefined);
    ddbMock.resetHistory();
    const res = await cold(request("GET /reports/{id}"));

    expect(res.statusCode).toBe(200);
    expect(ddbMock.commandCalls(QueryCommand).map((call) => call.args[0].input.TableName)).toEqual(["reports"]);
  });

  it("names a missing environment variable and builds nothing", async () => {
    for (const name of ENV_NAMES) {
      const cold = await coldHandler();
      vi.stubEnv(name, undefined);
      resetMocks();
      serve();

      await expect(cold(request("GET /reports/{id}"))).rejects.toThrow(new RegExp(`^missing environment variable ${name}$`));
      expect(awsCalls() + ssmMock.calls().length, name).toBe(0);

      // Nothing was kept, so the next request builds everything.
      stubApiEnv();
      expect((await cold(request("GET /reports/{id}"))).statusCode, name).toBe(200);
    }
  });

  it("presigns photo links on the stack's bucket in ap-southeast-1, for 300 s", async () => {
    const cold = await coldHandler();
    const report = JSON.parse((await cold(request("GET /reports/{id}"))).body);
    const listed = JSON.parse((await cold(request("GET /samples"))).body).samples;
    const { upload } = JSON.parse((await cold(request("POST /uploads"))).body);

    const links = [report.photoUrl, report.overlayUrl, report.layersUrl, ...listed.map((sample: { photoUrl: string }) => sample.photoUrl)];
    expect(links).toHaveLength(4);
    for (const link of links) {
      const url = new URL(link);
      expect(url.hostname).toBe(`${BUCKET}.s3.ap-southeast-1.amazonaws.com`);
      expect(url.searchParams.get("X-Amz-Expires")).toBe("300");
      expect(url.searchParams.get("X-Amz-Credential")).toBe("test/20261030/ap-southeast-1/s3/aws4_request");
    }
    // The upload form comes from the same client, and its policy ends 300 s from now (C27).
    expect(new URL(upload.url).hostname).toBe(`${BUCKET}.s3.ap-southeast-1.amazonaws.com`);
    expect(upload.fields["X-Amz-Credential"]).toBe("test/20261030/ap-southeast-1/s3/aws4_request");
    const policy = JSON.parse(Buffer.from(upload.fields.Policy, "base64").toString("utf8"));
    expect(Date.parse(policy.expiration)).toBe(Date.parse("2026-10-30T10:11:40Z"));
  });

  it("lets no sentinel IP, location or device id reach a log on any route", async () => {
    const lines = captureConsole();
    for (const routeKey of ROUTE_KEYS) {
      // A success.
      resetMocks();
      serve();
      const ok = await (await coldHandler())(sentinelRequest(routeKey));
      expect(ok.statusCode, routeKey).toBeLessThan(300);
      const calls = awsCalls();
      expect(calls, routeKey).toBeGreaterThan(0);

      // Every AWS call failing: the stop switch fails closed, and the rest fail where they're made.
      resetMocks();
      const failure = awsError("AccessDeniedException", 400);
      ssmMock.rejects(failure);
      ddbMock.rejects(failure);
      s3Mock.rejects(failure);
      await (await coldHandler())(sentinelRequest(routeKey));

      // SSM answers off while DynamoDB and S3 fail, at each of the success's calls in turn, so take,
      // the flag's transaction, the puts and the copy each run before they fail (T4).
      for (let failAt = 1; failAt <= calls; failAt++) {
        resetMocks();
        let seen = 0;
        serve({
          before: () => {
            seen += 1;
            if (seen === failAt) throw awsError("AccessDeniedException", 400);
          },
        });
        const res = await (await coldHandler())(sentinelRequest(routeKey));
        expect(res.statusCode, `${routeKey}, call ${failAt}`).toBe(failedStatus(routeKey, failAt, calls));
      }
    }
    // Ask's success made the thirteen calls failedStatus names, in that order.
    resetMocks();
    serve();
    await (await coldHandler())(sentinelRequest("POST /ask"));
    expect(awsCalls()).toBe(13);

    // The runs logged, so the capture works.
    expect(lines.some((line) => line.includes("request_failed"))).toBe(true);
    expect(lines.some((line) => line.includes("stop_switch_unreadable"))).toBe(true);
    for (const line of lines) for (const sentinel of SENTINELS) expect(line).not.toContain(sentinel);
  });

  it("names every attribute in every expression through a placeholder", async () => {
    const sent: Sent[] = [];
    for (const routeKey of ROUTE_KEYS) {
      resetMocks();
      serve();
      expect((await (await coldHandler())(request(routeKey))).statusCode, routeKey).toBeLessThan(300);
      sent.push(...sentInputs());
    }
    // The hour's cap refusing an upload gives the device's count back, with an expression of its own.
    resetMocks();
    serve();
    ddbMock.on(UpdateCommand).callsFake((input: UpdateCommandInput) => {
      if (String(input.Key?.pk).includes("#ALL#")) {
        throw new ConditionalCheckFailedException({ message: "The conditional request failed", $metadata: {} });
      }
      return {};
    });
    expect((await (await coldHandler())(request("POST /uploads"))).statusCode).toBe(429);
    sent.push(...sentInputs());

    const kinds = new Set(sent.map(({ kind }) => kind));
    for (const kind of ["GetCommand", "QueryCommand", "UpdateCommand", "PutCommand", "TransactWriteCommand.Put", "TransactWriteCommand.Update"]) {
      expect([...kinds], kind).toContain(kind);
    }
    const seen = new Set<string>();
    for (const { kind, input } of sent) {
      const names = (input.ExpressionAttributeNames ?? {}) as Record<string, string>;
      const values = (input.ExpressionAttributeValues ?? {}) as Record<string, unknown>;
      const used: string[] = [];
      for (const field of EXPRESSIONS) {
        const expression = input[field];
        if (expression === undefined) continue;
        seen.add(field);
        expect(typeof expression).toBe("string");
        expect(bareNames(expression as string), `${kind} ${field}: ${expression}`).toEqual([]);
        used.push(...((expression as string).match(PLACEHOLDERS) ?? []));
      }
      for (const token of used) {
        expect(Object.keys(token.startsWith("#") ? names : values), `${kind}: ${token}`).toContain(token);
      }
      // DynamoDB refuses a placeholder that no expression uses, so none is left over.
      expect([...Object.keys(names), ...Object.keys(values)].filter((token) => !used.includes(token)), kind).toEqual([]);
    }
    expect([...seen].sort()).toEqual([...EXPRESSIONS].sort());
  });

  it("routes nearby, the map and the feed to their handlers", async () => {
    const cold = await coldHandler();

    const near = await cold(request("GET /reports"));
    const map = await cold(request("GET /map/pins"));
    const feed = await cold(request("GET /pins.geojson"));

    expect(near.statusCode).toBe(200);
    expect(JSON.parse(near.body).pins.map((pin: { id: string }) => pin.id)).toEqual([ID, DEMO_ID]);
    expect(map.statusCode).toBe(200);
    expect(JSON.parse(map.body).pins.map((pin: { id: string }) => pin.id)).toEqual([ID, DEMO_ID]);
    expect(feed.statusCode).toBe(200);
    expect(feed.headers["content-type"]).toBe("application/geo+json");
    expect(JSON.parse(feed.body).features.map((feature: { properties: { id: string } }) => feature.properties.id)).toEqual([ID]);
  });

  it('shows the inches only when INCHES_SHOWN is the string "true"', async () => {
    for (const [value, shown] of [
      ["true", true],
      ["false", false],
      ["TRUE", false],
      ["1", false],
      [" true", false],
    ] as const) {
      vi.stubEnv("INCHES_SHOWN", value);
      const cold = await coldHandler();
      const report = JSON.parse((await cold(request("GET /reports/{id}"))).body);
      const pins = [
        JSON.parse((await cold(request("GET /reports"))).body).pins[0],
        JSON.parse((await cold(request("GET /map/pins"))).body).pins[0],
        JSON.parse((await cold(request("GET /pins.geojson"))).body).features[0].properties,
      ];

      for (const body of [report, ...pins]) {
        if (shown) expect(body, value).toMatchObject({ depthInMin: PIN.depthInMin, depthInMax: PIN.depthInMax });
        else expect(Object.keys(body), value).not.toContain("depthInMin");
      }
      expect("inches" in report.readings[0], value).toBe(shown);
    }
  });

  it("answers a flag whose transaction is cancelled for another reason with 500, logging the error's name only", async () => {
    // F19: the report gone between the read and the write.
    ddbMock.on(TransactWriteCommand).rejects(cancelled("None", "ConditionalCheckFailed"));
    const logged = vi.spyOn(console, "error").mockImplementation(() => {});

    const res = await (await coldHandler())(sentinelRequest("POST /reports/{id}/flag"));

    expect(res.statusCode).toBe(500);
    expect(JSON.parse(res.body)).toEqual({ error: "internal" });
    expect(logged).toHaveBeenCalledOnce();
    const line = logged.mock.calls[0][0] as string;
    expect(JSON.parse(line)).toEqual({
      msg: "request_failed",
      routeKey: "POST /reports/{id}/flag",
      error: "TransactionCanceledException",
      status: 400,
    });
    for (const absent of ["cancelled", ID, ...SENTINELS]) expect(line).not.toContain(absent);
  });

  // Ask Lusot's two variables are read on its own route only (its Task 12), so the test above keeps seven names.
  it.each(["MODEL_KEY_PARAM", "NOMINATIM_USER_AGENT"])(
    "without %s, POST /ask answers 500 internal and names it, and MS4's routes still answer",
    async (name) => {
      const lines = captureConsole();
      vi.stubEnv(name, undefined);
      const cold = await coldHandler();

      const res = await cold(request("POST /ask"));

      expect(res.statusCode).toBe(500);
      expect(JSON.parse(res.body)).toEqual({ error: "internal" });
      expect(lines.map((line) => JSON.parse(line))).toEqual([
        { msg: "ask_unconfigured", variable: name },
        { msg: "ask", route: "ask", status: 500, code: "internal", error: "MissingVariable" },
      ]);
      expect(awsCalls() + ssmMock.calls().length).toBe(0);
      expect((await cold(request("GET /reports/{id}"))).statusCode).toBe(200);
      // Set again, the next question builds Ask's deps and is answered.
      stubApiEnv();
      expect((await cold(request("POST /ask"))).statusCode).toBe(200);
    },
  );

  it("answers POST /ask through the real Meta client, and no other route reads the model key", async () => {
    vi.spyOn(console, "log").mockImplementation(() => {});
    const keyReads = () => ssmMock.commandCalls(GetParameterCommand).filter((call) => call.args[0].input.Name === MODEL_KEY_PARAM);
    for (const routeKey of ROUTE_KEYS.filter((key) => key !== "POST /ask")) await (await coldHandler())(request(routeKey));
    expect(keyReads()).toHaveLength(0);

    const res = await (await coldHandler())(request("POST /ask"));

    expect(res.statusCode).toBe(200);
    expect(JSON.parse(res.body).answer).toMatchObject({ source: "model", kind: "reports", place: { source: "here" }, cited: [ID] });
    expect(keyReads().map((call) => call.args[0].input)).toEqual([{ Name: MODEL_KEY_PARAM, WithDecryption: true }]);
  });
});
