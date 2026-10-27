import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, QueryCommand } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { beforeEach, describe, expect, it } from "vitest";
import { getReport, type ReportDeps } from "../src/reports";

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
const ddbMock = mockClient(ddb);
const deps: ReportDeps = { ddb, tableName: "reports", indexName: "reportId-index" };
const ID = "r_0123456789abcdef0123456789abcdef";
const CAPTURED_AT = "2026-10-30T10:05:12Z";

beforeEach(() => {
  ddbMock.reset();
});

describe("GET /reports/{id}", () => {
  it("a known id queries reportId-index and returns its status", async () => {
    const stored = { pk: "GEO#wdw515", sk: `${CAPTURED_AT}#${ID}`, reportId: ID, mode: "live", capturedAt: CAPTURED_AT, lat: 14.6095, lng: 120.9894 };
    ddbMock
      .on(QueryCommand)
      .resolvesOnce({ Items: [{ ...stored, status: "failed", refusalReason: "pipeline_not_built" }] })
      .resolvesOnce({ Items: [{ ...stored, status: "pending" }] });

    const failed = await getReport(ID, deps);
    const pending = await getReport(ID, deps);

    expect(failed.statusCode).toBe(200);
    expect(JSON.parse(failed.body)).toEqual({ reportId: ID, status: "failed", refusalReason: "pipeline_not_built", capturedAt: CAPTURED_AT });
    expect(JSON.parse(pending.body)).toEqual({ reportId: ID, status: "pending", capturedAt: CAPTURED_AT });
    const queries = ddbMock.commandCalls(QueryCommand);
    expect(queries).toHaveLength(2);
    expect(queries[0].args[0].input).toMatchObject({
      TableName: "reports",
      IndexName: "reportId-index",
      KeyConditionExpression: "reportId = :id",
      ExpressionAttributeValues: { ":id": ID },
    });
  });

  it("an unknown id gives 404", async () => {
    ddbMock.on(QueryCommand).resolves({ Items: [] });

    const res = await getReport(ID, deps);

    expect(res.statusCode).toBe(404);
    expect(JSON.parse(res.body)).toEqual({ error: "not_found" });
  });

  it.each([undefined, "", "r_123", "r_0123456789ABCDEF0123456789abcdef", `${ID}0`, `../${ID}`])(
    "a malformed id gives 404 without querying: %s",
    async (id) => {
      const res = await getReport(id, deps);

      expect(res.statusCode).toBe(404);
      expect(JSON.parse(res.body)).toEqual({ error: "not_found" });
      expect(ddbMock.calls()).toHaveLength(0);
    },
  );
});
