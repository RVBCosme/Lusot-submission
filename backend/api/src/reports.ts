import { GetObjectCommand, type S3Client } from "@aws-sdk/client-s3";
import { type DynamoDBDocumentClient, QueryCommand } from "@aws-sdk/lib-dynamodb";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { json, type JsonResponse } from "./http";
import type { ReportItem } from "./pins";

const REPORT_ID = /^r_[0-9a-f]{32}$/; // C32
const LINK_EXPIRES_S = 300; // C503: photo links last 5 minutes
// Each link and the stored key it is signed from (C503).
const LINKS = [
  ["photoUrl", "photoKey"],
  ["overlayUrl", "overlayKey"],
  ["layersUrl", "layersKey"],
] as const;
const DEMO_FIELDS = ["credit", "place", "event"] as const; // C523

export interface ReportDeps {
  ddb: DynamoDBDocumentClient;
  s3: S3Client;
  tableName: string;
  indexName: string;
  bucketName: string;
  inchesShown: boolean;
  now: () => number;
}

// The report with this id, from reportId-index, or undefined. A malformed id can't exist, so it costs no read.
export async function findReport(
  id: string | undefined,
  deps: Pick<ReportDeps, "ddb" | "tableName" | "indexName">,
): Promise<ReportItem | undefined> {
  if (id === undefined || !REPORT_ID.test(id)) return undefined;
  const { Items } = await deps.ddb.send(
    new QueryCommand({
      TableName: deps.tableName,
      IndexName: deps.indexName,
      KeyConditionExpression: "#reportId = :id",
      ExpressionAttributeNames: { "#reportId": "reportId" },
      ExpressionAttributeValues: { ":id": id },
    }),
  );
  return Items?.[0];
}

// GET /reports/{id}: the report's result, which is also the pin detail (spec §4.3).
export async function getReport(id: string | undefined, deps: ReportDeps): Promise<JsonResponse> {
  const report = await findReport(id, deps);
  const nowS = Math.floor(deps.now() / 1000);
  // C526: past expiresAt the report is gone, whatever the item holds, since DynamoDB's TTL deletes
  // it days late. An item without expiresAt gets the same 404.
  if (report === undefined || !(typeof report.expiresAt === "number" && report.expiresAt > nowS)) {
    return json(404, { error: "not_found" });
  }
  // Built field by field: never the location, a stored key, the claim, flags or anything else stored (C67).
  const body: Record<string, unknown> = {
    reportId: report.reportId,
    status: report.status,
    refusalReason: report.refusalReason,
    capturedAt: report.capturedAt,
    mode: report.mode,
    published: report.published === true,
  };
  // noFloodSeen on every done report gives the app one rule; the level fields come only with a level (C67).
  if (report.status === "done") {
    body.noFloodSeen = report.noFloodSeen;
    if (report.level !== undefined) {
      body.level = report.level;
      body.landmark = report.landmark;
      body.passability = report.passability;
      // A new map of the two counts, so nothing else stored in it reaches the app.
      body.basis = { vehicles: report.basis.vehicles, people: report.basis.people };
      body.levelIsFloor = report.levelIsFloor;
      if (report.levelFrom !== undefined) body.levelFrom = report.levelFrom;
      // C515: the inches stay hidden until the release gate shows them.
      if (deps.inchesShown) {
        body.depthInMin = report.depthInMin;
        body.depthInMax = report.depthInMax;
      }
      if (Array.isArray(report.readings)) body.readings = report.readings.map((stored) => reading(stored, deps.inchesShown));
      if (report.gpsAccuracyM !== undefined) body.gpsAccuracyM = report.gpsAccuracyM;
      Object.assign(body, await links(report, nowS, deps));
    }
  }
  // C523: a demo pin carries its credit, place and event, so a judge can tell it isn't current.
  if (report.mode === "demo") {
    for (const name of DEMO_FIELDS) if (report[name] !== undefined) body[name] = report[name];
  }
  return json(200, body);
}

// C507: one reading, field by field, so nothing else stored on it gets out. Its inches only past the gate (C515).
// levelIsFloor is the reading's own C54 floor: true, false, or null where it has no level.
function reading(stored: ReportItem, inchesShown: boolean): Record<string, unknown> {
  const { id, kind, landmark, level, levelIsFloor, used, dropped } = stored;
  return { id, kind, landmark, level, levelIsFloor, used, dropped, ...(inchesShown && { inches: stored.inches }) };
}

// C503: a pin's links are issued while it is visible (linksIssued, below), and each lasts 300 s. Each is
// signed locally from its stored key, with no S3 call, so a link to an object already gone gets S3's own
// error and the app shows the text alone. A key that isn't stored gives no link.
async function links(report: ReportItem, nowS: number, deps: ReportDeps): Promise<Record<string, string>> {
  if (!linksIssued(report, nowS)) return {};
  const signed: Record<string, string> = {};
  for (const [field, key] of LINKS) {
    const objectKey = report[key];
    if (typeof objectKey !== "string") continue;
    signed[field] = await getSignedUrl(deps.s3, new GetObjectCommand({ Bucket: deps.bucketName, Key: objectKey }), {
      expiresIn: LINK_EXPIRES_S,
    });
  }
  return signed;
}

// C503: links are issued for a live or demo pin while it is visible, and for a private, sample or eval
// report until expiresAt, which the 404 already bounds. Any other mode, or none, gets no links.
function linksIssued(report: ReportItem, nowS: number): boolean {
  switch (report.mode) {
    case "live":
    case "demo":
      return typeof report.visibleUntil === "number" && report.visibleUntil > nowS;
    case "private":
    case "sample":
    case "eval":
      return true;
    default:
      return false;
  }
}
