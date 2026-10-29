import { type DynamoDBDocumentClient, TransactWriteCommand } from "@aws-sdk/lib-dynamodb";
import { json, type JsonResponse } from "./http";
import { deviceKey, hashDevice } from "./limits";
import type { ReportItem } from "./pins";
import { findReport } from "./reports";

export interface FlagDeps {
  ddb: DynamoDBDocumentClient;
  tableName: string;
  indexName: string;
  limitsTableName: string;
  now: () => number;
}

// POST /reports/{id}/flag (C511): adds 1 to a live published pin's flags, once per device. Flags are
// counted and shown, never acted on, so nothing here changes visibleUntil (MS4-Q3).
export async function flagReport(id: string | undefined, deviceHeader: string | undefined, deps: FlagDeps): Promise<JsonResponse> {
  const report = await findReport(id, deps);
  const nowS = Math.floor(deps.now() / 1000);
  if (report === undefined || !flaggable(report, nowS)) return json(404, { error: "not_found" });
  const flags: number = report.flags ?? 0; // as ADD counts a missing attribute
  try {
    // The flag record and the count change together or not at all (spec §4.6).
    await deps.ddb.send(
      new TransactWriteCommand({
        TransactItems: [
          {
            Put: {
              TableName: deps.limitsTableName,
              // Only the device id's hash is stored (C520), kept as long as the pin (PRIV-Q7).
              Item: { pk: `flag#${report.reportId}#${hashDevice(deviceKey(deviceHeader))}`, expiresAt: report.expiresAt },
              ConditionExpression: "attribute_not_exists(#pk)",
              ExpressionAttributeNames: { "#pk": "pk" },
            },
          },
          {
            Update: {
              TableName: deps.tableName,
              Key: { pk: report.pk, sk: report.sk },
              UpdateExpression: "ADD #flags :one",
              ConditionExpression: "attribute_exists(#pk)",
              ExpressionAttributeNames: { "#flags": "flags", "#pk": "pk" },
              ExpressionAttributeValues: { ":one": 1 },
            },
          },
        ],
      }),
    );
  } catch (err) {
    // C522: this device's flag record is already there, so it is the same request and gets the same answer.
    if (isRepeat(err)) return json(200, { flags });
    throw err;
  }
  return json(200, { flags: flags + 1 });
}

// A live pin that is published, visible and not yet expired. Demo pins can't be flagged (C511).
function flaggable(report: ReportItem, nowS: number): boolean {
  return (
    report.mode === "live" &&
    report.published === true &&
    typeof report.visibleUntil === "number" &&
    report.visibleUntil > nowS &&
    typeof report.expiresAt === "number" &&
    report.expiresAt > nowS
  );
}

// The reasons come in the order of the items, so the first is the flag record's condition.
function isRepeat(err: unknown): boolean {
  const cancelled = err as { name?: string; CancellationReasons?: { Code?: string }[] } | undefined;
  return cancelled?.name === "TransactionCanceledException" && cancelled.CancellationReasons?.[0]?.Code === "ConditionalCheckFailed";
}
