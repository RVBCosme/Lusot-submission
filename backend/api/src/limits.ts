import { createHash } from "node:crypto";
import { type DynamoDBDocumentClient, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { json, type JsonResponse } from "./http";

export type Bucket = "upload" | "sample" | "question";

// Per UTC clock hour (C508, MS4-Q13): each device's count, then the count in all.
export const LIMITS: Record<Bucket, { device: number; all: number }> = {
  upload: { device: 10, all: 300 },
  sample: { device: 5, all: 30 },
  question: { device: 20, all: 300 },
};

// The refusal codes, in one place: C522's for uploads and samples, Ask Lusot's for questions.
export const LIMIT_CODES: Record<Bucket, { device: string; all: string }> = {
  upload: { device: "device_limit", all: "global_cap" },
  sample: { device: "device_limit", all: "global_cap" },
  question: { device: "question_limit", all: "question_cap" },
};

const DEVICE_ID = /^[A-Za-z0-9_-]{8,64}$/;
const HOUR_S = 3600;
const TTL_S = 2 * HOUR_S; // the counter outlives its hour by an hour

export interface LimitDeps {
  ddb: DynamoDBDocumentClient;
  limitsTableName: string;
}

// A missing or malformed X-Lusot-Device counts in one shared bucket (C508).
export function deviceKey(header: string | undefined): string {
  return header !== undefined && DEVICE_ID.test(header) ? header : "none";
}

// Only the hash is stored, never the id (C520).
export function hashDevice(key: string): string {
  return createHash("sha256").update(key).digest("hex");
}

// The UTC clock hour, as 2026-10-30T10.
export function utcHour(nowS: number): string {
  return new Date(nowS * 1000).toISOString().slice(0, 13);
}

export function retryAfterS(nowS: number): number {
  return HOUR_S - (nowS % HOUR_S);
}

// Counts one against the device's hour and then against the hour in all. Null when both
// allow it, else the 429 that refuses it. The device goes first, so one device can't use up
// the hour's cap (spec §4.6).
export async function take(
  bucket: Bucket,
  deviceHeader: string | undefined,
  nowS: number,
  deps: LimitDeps,
): Promise<JsonResponse | null> {
  const hour = utcHour(nowS);
  const expiresAt = nowS - (nowS % HOUR_S) + TTL_S;
  const device = `${bucket}#${hashDevice(deviceKey(deviceHeader))}#${hour}`;
  if (!(await increment(device, LIMITS[bucket].device, expiresAt, deps))) return refuse(LIMIT_CODES[bucket].device, nowS);
  if (!(await increment(`${bucket}#ALL#${hour}`, LIMITS[bucket].all, expiresAt, deps))) {
    // The hour refused it, so the device's count goes back.
    await deps.ddb.send(
      new UpdateCommand({
        TableName: deps.limitsTableName,
        Key: { pk: device },
        UpdateExpression: "ADD #n :minusOne",
        ExpressionAttributeNames: { "#n": "n" },
        ExpressionAttributeValues: { ":minusOne": -1 },
      }),
    );
    return refuse(LIMIT_CODES[bucket].all, nowS);
  }
  return null;
}

// Adds 1 to the counter while it is under the limit. False when the condition refuses it.
async function increment(pk: string, limit: number, expiresAt: number, deps: LimitDeps): Promise<boolean> {
  try {
    await deps.ddb.send(
      new UpdateCommand({
        TableName: deps.limitsTableName,
        Key: { pk },
        UpdateExpression: "ADD #n :one SET #expiresAt = :expiresAt",
        ConditionExpression: "attribute_not_exists(#n) OR #n < :limit",
        ExpressionAttributeNames: { "#n": "n", "#expiresAt": "expiresAt" },
        ExpressionAttributeValues: { ":one": 1, ":limit": limit, ":expiresAt": expiresAt },
      }),
    );
    return true;
  } catch (err) {
    if ((err as { name?: string } | undefined)?.name === "ConditionalCheckFailedException") return false;
    throw err;
  }
}

function refuse(error: string, nowS: number): JsonResponse {
  const res = json(429, { error });
  return { ...res, headers: { ...res.headers, "retry-after": String(retryAfterS(nowS)) } };
}
