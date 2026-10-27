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
  // Only what the app needs: never the location.
  return json(200, {
    reportId: report.reportId,
    status: report.status,
    refusalReason: report.refusalReason,
    capturedAt: report.capturedAt,
  });
}
