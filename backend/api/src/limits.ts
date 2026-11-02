import { createHash } from "node:crypto";
import { type DynamoDBDocumentClient, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { json, type JsonResponse } from "./http";

export type Bucket = "upload" | "sample" | "try" | "question";

// Per UTC clock hour (C508, MS4-Q13): each device's count, then the count in all. A bucket with a
// day also has a cap in all per UTC day (C534), so judging can't drain the Meta credits.
export const LIMITS: Record<Bucket, { device: number; all: number; day?: number }> = {
  upload: { device: 10, all: 300 },
  sample: { device: 5, all: 30, day: 150 },
  try: { device: 3, all: 20, day: 120 },
  question: { device: 20, all: 60 },
};

// The refusal codes, in one place: C522's for uploads, samples and chosen photos, Ask Lusot's for questions.
export const LIMIT_CODES: Record<Bucket, { device: string; all: string }> = {
  upload: { device: "device_limit", all: "global_cap" },
  sample: { device: "device_limit", all: "global_cap" },
  try: { device: "device_limit", all: "global_cap" },
  question: { device: "question_limit", all: "question_cap" },
};
const DAY_CODE = "daily_cap"; // C534

const DEVICE_ID = /^[A-Za-z0-9_-]{8,64}$/;
const HOUR_S = 3600;
const DAY_S = 24 * HOUR_S;
const TTL_S = 2 * HOUR_S; // the counter outlives its hour by an hour
const DAY_TTL_S = 2 * DAY_S; // and the day's outlives its day by a day

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

// Counts one against the device's hour, then against the hour in all, then, for a bucket with a
// day cap, against the UTC day in all (C534). Null when all allow it, else the 429 that refuses it.
// The device goes first, so one device can't use up the hour's cap (spec §4.6).
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
    await decrement(device, deps);
    return refuse(LIMIT_CODES[bucket].all, nowS);
  }
  const day = LIMITS[bucket].day;
  if (day !== undefined) {
    const dayStartS = nowS - (nowS % DAY_S);
    const dayKey = `${bucket}#ALL#${new Date(dayStartS * 1000).toISOString().slice(0, 10)}`;
    if (!(await increment(dayKey, day, dayStartS + DAY_TTL_S, deps))) {
      // The day refused it, so the hour's two counts go back. Until they do, a request at the same moment
      // can be refused by the device or the hour instead of the day: a refusal either way, never a run.
      await decrement(device, deps);
      await decrement(`${bucket}#ALL#${hour}`, deps);
      return refuse(DAY_CODE, nowS, dayStartS + DAY_S - nowS);
    }
  }
  return null;
}

// Gives back one that `take` counted in the same hour, the device's and the hour's in all: Ask Lusot's spoken question
// that its spend stop pauses after it was counted, which its spec doesn't count (§5.4).
export async function giveBack(bucket: Bucket, deviceHeader: string | undefined, nowS: number, deps: LimitDeps): Promise<void> {
  const hour = utcHour(nowS);
  await decrement(`${bucket}#${hashDevice(deviceKey(deviceHeader))}#${hour}`, deps);
  await decrement(`${bucket}#ALL#${hour}`, deps);
}

async function decrement(pk: string, deps: LimitDeps): Promise<void> {
  await deps.ddb.send(
    new UpdateCommand({
      TableName: deps.limitsTableName,
      Key: { pk },
      UpdateExpression: "ADD #n :minusOne",
      ExpressionAttributeNames: { "#n": "n" },
      ExpressionAttributeValues: { ":minusOne": -1 },
    }),
  );
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

function refuse(error: string, nowS: number, afterS = retryAfterS(nowS)): JsonResponse {
  const res = json(429, { error });
  return { ...res, headers: { ...res.headers, "retry-after": String(afterS) } };
}
