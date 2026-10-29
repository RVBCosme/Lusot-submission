import { type DynamoDBDocumentClient, QueryCommand } from "@aws-sdk/lib-dynamodb";
import { json, type JsonResponse } from "./http";

const REPORT_ID = /^r_[0-9a-f]{32}$/; // C32

export interface ReportDeps {
  ddb: DynamoDBDocumentClient;
  tableName: string;
  indexName: string;
}

export async function getReport(id: string | undefined, deps: ReportDeps): Promise<JsonResponse> {
  // A malformed id can't exist, so it costs no read.
  if (id === undefined || !REPORT_ID.test(id)) return json(404, { error: "not_found" });
  const { Items } = await deps.ddb.send(
    new QueryCommand({
      TableName: deps.tableName,
      IndexName: deps.indexName,
      KeyConditionExpression: "reportId = :id",
      ExpressionAttributeValues: { ":id": id },
    }),
  );
  const report = Items?.[0];
  if (report === undefined) return json(404, { error: "not_found" });
  // Only what the app needs: never the location, readings, photoKey or the claim (C67).
  const body: Record<string, unknown> = {
    reportId: report.reportId,
    status: report.status,
    refusalReason: report.refusalReason,
    capturedAt: report.capturedAt,
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
    }
  }
  return json(200, body);
}
