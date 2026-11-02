import { PutCommand } from "@aws-sdk/lib-dynamodb";
import { json, type JsonResponse } from "./http";
import { take } from "./limits";
import { CONSENT_VERSION, isoSeconds, newReportId, rawUpload, type UploadDeps } from "./uploads";

const RETAIN_S = 7 * 24 * 60 * 60; // Table 14: the item is deleted 7 days after it is made

// POST /try (C534): an upload link for a photo the person chose, run through the same pipeline as a report. The
// item has no location and no visibleUntil, and only live and demo results publish (C516), so it never pins: W20
// rests here, not on the app (C639). The checks run in this order: the uploads switch, the model-calls switch (no
// photo is taken while no run could follow), the body, then the device's limit, the hour's cap and the day's cap.
export async function createTry(
  rawBody: string | undefined,
  deviceHeader: string | undefined,
  deps: UploadDeps,
): Promise<JsonResponse> {
  const nowMs = deps.now();
  const nowS = Math.floor(nowMs / 1000);
  if (await deps.isStopped("uploads", nowMs)) return json(503, { error: "uploads_paused" });
  if (await deps.isStopped("model-calls", nowMs)) return json(503, { error: "model_calls_paused" });

  const consentVersion = parseRequest(rawBody);
  if (typeof consentVersion === "object") return json(400, { error: "bad_request", detail: consentVersion.detail });

  const refused = await take("try", deviceHeader, nowS, deps);
  if (refused !== null) return refused;

  const reportId = newReportId();
  const receivedAt = isoSeconds(nowS);
  await deps.ddb.send(
    new PutCommand({
      TableName: deps.tableName,
      Item: {
        pk: "TRY",
        sk: `${receivedAt}#${reportId}`,
        reportId,
        mode: "try",
        status: "pending",
        // Left out when absent: the document client refuses an undefined attribute.
        ...(consentVersion !== undefined && { consentVersion }),
        // A chosen photo's capture time isn't known, so the run's time stands in, as a sample's does. No location,
        // no device field (C520) and no visibleUntil.
        capturedAt: receivedAt,
        receivedAt,
        expiresAt: nowS + RETAIN_S,
      },
    }),
  );
  return json(201, await rawUpload(reportId, deps));
}

// The consent version, undefined when none is sent, or a detail for a 400. An absent or empty body is {}.
function parseRequest(rawBody: string | undefined): string | undefined | { detail: string } {
  if (rawBody === undefined || rawBody === "") return undefined;
  let body: unknown;
  try {
    body = JSON.parse(rawBody);
  } catch {
    return { detail: "body must be JSON" };
  }
  if (typeof body !== "object" || body === null || Array.isArray(body)) return { detail: "body must be a JSON object" };
  const { consentVersion } = body as Record<string, unknown>;
  if (consentVersion === undefined) return undefined;
  if (typeof consentVersion !== "string" || !CONSENT_VERSION.test(consentVersion)) {
    return { detail: "consentVersion must be 1 to 32 letters, digits, dots, dashes or underscores" };
  }
  return consentVersion;
}
