import { randomUUID } from "node:crypto";
import type { S3Client } from "@aws-sdk/client-s3";
import { type DynamoDBDocumentClient, PutCommand } from "@aws-sdk/lib-dynamodb";
import { createPresignedPost } from "@aws-sdk/s3-presigned-post";
import ngeohash from "ngeohash";
import { json, type JsonResponse } from "./http";
import { take } from "./limits";
import { inMetroManila } from "./metroManila";
import type { StopSwitch } from "./stopSwitch";

const MAX_AGE_MS = 15 * 60_000; // W20: the photo was taken at most 15 minutes ago
const MAX_AHEAD_MS = 2 * 60_000; // slack for a phone clock that runs fast
const MAX_GPS_ACCURACY_M = 50; // plan Table 4
const MAX_NUDGE_M = 100; // plan Table 4
// MS5 sends an 8-hex-digit NOTICE_VERSION; this allows any short version tag.
const CONSENT_VERSION = /^[A-Za-z0-9._-]{1,32}$/;
const VISIBLE_S = 3 * 60 * 60; // Table 14: the map hides the pin 3 h after capture
const RETAIN_S = 7 * 24 * 60 * 60; // Table 14: the item is deleted 7 days after capture
const UPLOAD_EXPIRES_S = 300; // C27: the upload link lasts 5 minutes
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // C27, plan §12: 10 MB
// An ISO 8601 time with an explicit zone. Without one, Date.parse would assume the server's local time.
const ISO_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;

export interface UploadDeps {
  ddb: DynamoDBDocumentClient;
  s3: S3Client;
  isStopped: StopSwitch;
  tableName: string;
  limitsTableName: string;
  bucketName: string;
  now: () => number;
}

interface UploadRequest {
  lat: number;
  lng: number;
  gpsAccuracyM: number;
  nudgeM: number;
  consentVersion?: string;
  capturedMs: number;
}

// C32: 122 random bits, so a report can only be fetched by someone who was given its id.
export function newReportId(): string {
  return `r_${randomUUID().replaceAll("-", "")}`;
}

// The checks run in the spec's order: the switch, the body, the device's limit, the hour's cap.
export async function createUpload(
  rawBody: string | undefined,
  deviceHeader: string | undefined,
  deps: UploadDeps,
): Promise<JsonResponse> {
  const nowMs = deps.now();
  const nowS = Math.floor(nowMs / 1000);
  if (await deps.isStopped("uploads", nowMs)) return json(503, { error: "uploads_paused" });

  const req = parseRequest(rawBody);
  if (typeof req === "string") return json(400, { error: "bad_request", detail: req });
  if (nowMs - req.capturedMs > MAX_AGE_MS) return json(422, { error: "capture_too_old" });
  if (req.capturedMs - nowMs > MAX_AHEAD_MS) return json(422, { error: "capture_in_future" });
  if (req.gpsAccuracyM > MAX_GPS_ACCURACY_M) return json(422, { error: "gps_too_coarse" });
  if (req.nudgeM > MAX_NUDGE_M) return json(422, { error: "nudge_too_far" });

  const refused = await take("upload", deviceHeader, nowS, deps);
  if (refused !== null) return refused;

  const reportId = newReportId();
  const capturedS = Math.floor(req.capturedMs / 1000);
  const capturedAt = isoSeconds(capturedS);
  await deps.ddb.send(
    new PutCommand({
      TableName: deps.tableName,
      Item: {
        pk: `GEO#${ngeohash.encode(req.lat, req.lng, 6)}`,
        sk: `${capturedAt}#${reportId}`,
        reportId,
        // C502: the point the app sends is final, after the nudge. Outside the NCR, nothing pins.
        mode: inMetroManila(req.lat, req.lng) ? "live" : "private",
        status: "pending",
        lat: req.lat,
        lng: req.lng,
        gpsAccuracyM: req.gpsAccuracyM,
        nudgeM: req.nudgeM,
        // Left out when absent: the document client refuses an undefined attribute.
        ...(req.consentVersion !== undefined && { consentVersion: req.consentVersion }),
        capturedAt,
        receivedAt: isoSeconds(nowS),
        flags: 0,
        visibleUntil: capturedS + VISIBLE_S,
        expiresAt: capturedS + RETAIN_S,
      },
    }),
  );

  const upload = await createPresignedPost(deps.s3, {
    Bucket: deps.bucketName,
    Key: `raw/${reportId}.jpg`,
    Conditions: [["content-length-range", 1, MAX_UPLOAD_BYTES], { "Content-Type": "image/jpeg" }],
    Fields: { "Content-Type": "image/jpeg" },
    Expires: UPLOAD_EXPIRES_S,
  });
  return json(201, { reportId, upload, expiresInS: UPLOAD_EXPIRES_S });
}

// Returns the request, or a detail string for a 400.
function parseRequest(rawBody: string | undefined): UploadRequest | string {
  let body: unknown;
  try {
    body = JSON.parse(rawBody ?? "");
  } catch {
    return "body must be JSON";
  }
  if (typeof body !== "object" || body === null) return "body must be a JSON object";
  const { lat, lng, gpsAccuracyM, nudgeM = 0, consentVersion, capturedAt } = body as Record<string, unknown>;
  if (!inRange(lat, -90, 90)) return "lat must be a number from -90 to 90";
  if (!inRange(lng, -180, 180)) return "lng must be a number from -180 to 180";
  // MS1's range stays a 400; above 50 m is the 422 gps_too_coarse.
  if (!inRange(gpsAccuracyM, 0, 10_000)) return "gpsAccuracyM must be a number from 0 to 10000";
  if (!inRange(nudgeM, 0, Infinity)) return "nudgeM must be a number of at least 0";
  if (consentVersion !== undefined && (typeof consentVersion !== "string" || !CONSENT_VERSION.test(consentVersion))) {
    return "consentVersion must be 1 to 32 letters, digits, dots, dashes or underscores";
  }
  const capturedMs = typeof capturedAt === "string" && ISO_TIME.test(capturedAt) ? Date.parse(capturedAt) : NaN;
  if (Number.isNaN(capturedMs)) return "capturedAt must be an ISO 8601 time with a time zone";
  return { lat, lng, gpsAccuracyM, nudgeM, consentVersion, capturedMs };
}

function inRange(value: unknown, min: number, max: number): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= min && value <= max;
}

// Table 14's form, in UTC to the second (2026-10-30T10:05:12Z), so sort keys order by time.
// samples.ts writes a sample report's receivedAt and sk with it too.
export function isoSeconds(epochS: number): string {
  return new Date(epochS * 1000).toISOString().replace(".000Z", "Z");
}
