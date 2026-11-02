import { CopyObjectCommand, GetObjectCommand, type S3Client } from "@aws-sdk/client-s3";
import { type DynamoDBDocumentClient, PutCommand } from "@aws-sdk/lib-dynamodb";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { json, type JsonResponse } from "./http";
import { take } from "./limits";
import type { StopSwitch } from "./stopSwitch";
import { isoSeconds, newReportId } from "./uploads";

const MANIFEST_KEY = "samples/manifest.json"; // written only by samples.py (spec §4.5)
const MANIFEST_MEMO_MS = 60_000; // so a removed sample leaves the list within a minute
const LINK_EXPIRES_S = 300; // C503, C512: photo links last 5 minutes
const RETAIN_S = 7 * 24 * 60 * 60; // Table 14: the item is deleted 7 days after it is made
const LISTED = ["sampleId", "credit", "license", "place", "date", "event"] as const; // C512

// One entry of samples/manifest.json, as samples.py writes it (Task 8).
export interface SampleEntry {
  sampleId: string;
  credit: string;
  license: string;
  // Only a synthetic composite leaves out place and date, and event comes only when the source names one.
  place?: string;
  date?: string;
  event?: string;
  // The seeding run's date and final result (MS4-Q8 (b)), served only while model calls are stopped.
  // The result is GET /reports/{id}'s own fields, each present on its rule: noFloodSeen on a done
  // result, the level fields only with a level, refusalReason only when refused.
  savedAt: string;
  status: "done" | "refused";
  refusalReason?: string;
  noFloodSeen?: boolean;
  level?: string;
  landmark?: string;
  passability?: string;
  levelIsFloor?: boolean;
}

export interface Manifest {
  version: 1;
  samples: SampleEntry[];
}

export interface SampleDeps {
  ddb: DynamoDBDocumentClient;
  s3: S3Client;
  tableName: string;
  limitsTableName: string;
  bucketName: string;
  isStopped: StopSwitch;
  now: () => number;
  manifest: () => Promise<Manifest>;
}

// The manifest, read at most once a minute. Each call of the returned function shares one memo, so
// index.ts builds one per container (T9). A failed read isn't kept, so the next call reads again.
export function createManifest(deps: Pick<SampleDeps, "s3" | "bucketName" | "now">): () => Promise<Manifest> {
  let kept: { manifest: Manifest; readAtMs: number } | undefined;
  return async () => {
    const nowMs = deps.now();
    if (kept !== undefined && nowMs - kept.readAtMs < MANIFEST_MEMO_MS) return kept.manifest;
    const manifest = await readManifest(deps);
    kept = { manifest, readAtMs: nowMs };
    return manifest;
  };
}

// GET /samples (C512): each sample's public fields and a 5-minute link to its stored copy.
export async function listSamples(deps: SampleDeps): Promise<JsonResponse> {
  const { samples } = await deps.manifest();
  const listed = await Promise.all(
    samples.map(async (entry) => {
      // Field by field, so the saved result and anything else the manifest holds never get out.
      const sample: Record<string, unknown> = {};
      for (const name of LISTED) if (entry[name] !== undefined) sample[name] = entry[name];
      // Signed locally, with no S3 call.
      sample.photoUrl = await getSignedUrl(
        deps.s3,
        new GetObjectCommand({ Bucket: deps.bucketName, Key: `samples/${entry.sampleId}.jpg` }),
        { expiresIn: LINK_EXPIRES_S },
      );
      return sample;
    }),
  );
  return json(200, { samples: listed });
}

// POST /samples/{sampleId}: the checks run in the spec's order, the uploads switch, the sample id,
// then the device's limit, the hour's cap and the day's cap (C534). The run is the real pipeline on
// the stored copy (MS4-Q8).
export async function runSample(
  sampleId: string | undefined,
  deviceHeader: string | undefined,
  deps: SampleDeps,
): Promise<JsonResponse> {
  const nowMs = deps.now();
  const nowS = Math.floor(nowMs / 1000);
  if (await deps.isStopped("uploads", nowMs)) return json(503, { error: "uploads_paused" });
  const entry = (await deps.manifest()).samples.find((sample) => sample.sampleId === sampleId);
  if (entry === undefined) return json(404, { error: "not_found" });
  // MS4-Q8 (b), C527: while model calls are stopped, the seeding run's result, marked as saved and
  // dated, with no count and no run.
  if (await deps.isStopped("model-calls", nowMs)) return json(200, savedResult(entry));

  const refused = await take("sample", deviceHeader, nowS, deps);
  if (refused !== null) return refused;

  const reportId = newReportId();
  const receivedAt = isoSeconds(nowS);
  // F11, accepted: whenever the copy below fails, the count is spent and this pending item is left:
  // 404 for a sample removed within the manifest's 60 s memo, which passes the check above, and 500
  // for any other failure. A sample never pins, so the item is never shown, and it expires in 7 days.
  await deps.ddb.send(
    new PutCommand({
      TableName: deps.tableName,
      Item: {
        pk: "SAMPLE",
        sk: `${receivedAt}#${reportId}`,
        reportId,
        mode: "sample",
        status: "pending",
        sampleId: entry.sampleId,
        // A stored sample has no capture of its own, so the run's time stands in. No location, no
        // device field (C520) and no visibleUntil.
        capturedAt: receivedAt,
        receivedAt,
        expiresAt: nowS + RETAIN_S,
      },
    }),
  );
  try {
    // After the item, so the S3 event the copy raises finds it. CopySource is sent as given, so it is
    // URL-encoded here.
    await deps.s3.send(
      new CopyObjectCommand({
        Bucket: deps.bucketName,
        CopySource: `${deps.bucketName}/samples/${encodeURIComponent(entry.sampleId)}.jpg`,
        Key: `raw/${reportId}.jpg`,
      }),
    );
  } catch (err) {
    // F1: a listed sample whose stored copy is gone. Any other error, AccessDenied included, is the handler's 500.
    if (isNoSuchKey(err)) return json(404, { error: "not_found" });
    throw err;
  }
  return json(201, { reportId });
}

async function readManifest(deps: Pick<SampleDeps, "s3" | "bucketName">): Promise<Manifest> {
  try {
    const { Body } = await deps.s3.send(new GetObjectCommand({ Bucket: deps.bucketName, Key: MANIFEST_KEY }));
    return JSON.parse((await Body?.transformToString()) ?? "") as Manifest;
  } catch (err) {
    // F1: only NoSuchKey reads as missing. AccessDenied, like any other error, goes up to the handler's
    // 500, so an IAM fault on samples/ never quietly empties the list.
    if (isNoSuchKey(err)) return { version: 1, samples: [] };
    throw err;
  }
}

// A manifest entry whose saved result can't be served. The handler logs its name and answers 500.
class SavedResultError extends Error {
  override name = "SavedResultError";
}

// The stored fields as samples.py wrote them (Task 8), not re-derived here. JSON leaves out the absent ones.
function savedResult(entry: SampleEntry): Record<string, unknown> {
  const { savedAt, status, refusalReason, noFloodSeen, level, landmark, passability, levelIsFloor } = entry;
  // Never an empty "saved" answer from an entry that drifted from what samples.py writes.
  if (typeof savedAt !== "string" || (status !== "done" && status !== "refused")) {
    throw new SavedResultError("the manifest entry has no saved result to serve");
  }
  return {
    saved: true,
    savedAt,
    result: { status, refusalReason, noFloodSeen, level, landmark, passability, levelIsFloor },
  };
}

function isNoSuchKey(err: unknown): boolean {
  return (err as { name?: string } | undefined)?.name === "NoSuchKey";
}
