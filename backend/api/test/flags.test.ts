// Flags (spec §4.6, C511, C522): counted once per device on a live published pin, never acted on.
// Two edge cases are accepted (F19), and neither changes a reading:
// - a live pin that the publish switch hides can still be flagged by its id, since flagReport reads
//   no switch;
// - a cancellation whose first reason isn't ConditionalCheckFailed, such as the report's
//   attribute_exists(#pk) failing, answers 500 through index.ts's handler.
import { createHash } from "node:crypto";
import { DynamoDBClient, TransactionCanceledException } from "@aws-sdk/client-dynamodb";
import {
  DynamoDBDocumentClient,
  PutCommand,
  QueryCommand,
  TransactWriteCommand,
  type TransactWriteCommandInput,
  UpdateCommand,
} from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { beforeEach, describe, expect, it } from "vitest";
import { type FlagDeps, flagReport } from "../src/flags";

const NOW = "2026-10-30T10:06:40Z";
const NOW_S = Date.parse(NOW) / 1000;
const ID = "r_0123456789abcdef0123456789abcdef";
const CAPTURED_AT = "2026-10-30T10:05:12Z";
// The upload's 3 h and 7 days after capture, each from an ISO string (F3).
const VISIBLE_UNTIL = Date.parse("2026-10-30T13:05:12Z") / 1000;
const EXPIRES_AT = Date.parse("2026-11-06T10:05:12Z") / 1000;
const DEVICE = "device-0123456789abcdef";
const OTHER = "device-fedcba9876543210";
// A published live pin as the analysis Lambda leaves it.
const PIN = {
  pk: "GEO#wdw515",
  sk: `${CAPTURED_AT}#${ID}`,
  reportId: ID,
  mode: "live",
  status: "done",
  capturedAt: CAPTURED_AT,
  lat: 14.6095,
  lng: 120.9894,
  gpsAccuracyM: 12,
  noFloodSeen: false,
  level: "knee",
  landmark: "rim_three_quarters",
  passability: "NPLV",
  levelIsFloor: false,
  basis: { vehicles: 1, people: 1 },
  published: true,
  feedPart: "live",
  flags: 0,
  visibleUntil: VISIBLE_UNTIL,
  expiresAt: EXPIRES_AT,
};

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
const ddbMock = mockClient(ddb);
const deps: FlagDeps = {
  ddb,
  tableName: "reports",
  indexName: "reportId-index",
  limitsTableName: "limits",
  now: () => Date.parse(NOW),
};

function sha256(text: string): string {
  return createHash("sha256").update(text).digest("hex");
}

// As DynamoDB words it: the reasons come in the order of the items, and "None" marks one that passed.
function cancelled(...codes: string[]): TransactionCanceledException {
  return new TransactionCanceledException({
    message: `Transaction cancelled, please refer cancellation reasons for specific reasons [${codes.join(", ")}]`,
    $metadata: { httpStatusCode: 400 },
    CancellationReasons: codes.map((Code) => (Code === "None" ? { Code } : { Code, Message: "The conditional request failed" })),
  });
}

// The mock never evaluates a ConditionExpression, so this fake does what DynamoDB would with the
// transaction flagReport sends, and its exact text is checked below (T5). A flag record already there
// cancels the whole transaction, with ConditionalCheckFailed first; otherwise both writes happen.
let stored: Record<string, unknown>;
let records: Map<string, Record<string, unknown>>;
function fakeTables(item: Record<string, unknown>): void {
  stored = { ...item };
  records = new Map();
  ddbMock.on(QueryCommand).callsFake(() => ({ Items: [{ ...stored }] }));
  ddbMock.on(TransactWriteCommand).callsFake((input: TransactWriteCommandInput) => {
    const [record, count] = input.TransactItems ?? [];
    const pk = record?.Put?.Item?.pk as string;
    if (records.has(pk)) throw cancelled("ConditionalCheckFailed", "None");
    records.set(pk, { ...record?.Put?.Item });
    stored = { ...stored, flags: (stored.flags as number) + count?.Update?.ExpressionAttributeValues?.[":one"] };
    return {};
  });
}

function transactions(): TransactWriteCommandInput[] {
  return ddbMock.commandCalls(TransactWriteCommand).map((call) => call.args[0].input);
}

async function flag(header: string | undefined): Promise<{ statusCode: number; body: unknown }> {
  const res = await flagReport(ID, header, deps);
  return { statusCode: res.statusCode, body: JSON.parse(res.body) };
}

beforeEach(() => {
  ddbMock.reset();
  fakeTables(PIN);
});

describe("POST /reports/{id}/flag", () => {
  it("counts a flag once per device, and a repeat answers 200 with the count unchanged", async () => {
    expect(await flag(DEVICE)).toEqual({ statusCode: 200, body: { flags: 1 } });
    expect(await flag(DEVICE)).toEqual({ statusCode: 200, body: { flags: 1 } });
    expect(await flag(OTHER)).toEqual({ statusCode: 200, body: { flags: 2 } });
    expect(await flag(OTHER)).toEqual({ statusCode: 200, body: { flags: 2 } });

    expect(stored.flags).toBe(2);
    expect([...records.keys()]).toEqual([`flag#${ID}#${sha256(DEVICE)}`, `flag#${ID}#${sha256(OTHER)}`]);
    // A repeat is the same request, so it is sent and DynamoDB refuses it (C522).
    expect(transactions()).toHaveLength(4);
  });

  it("refuses demo pins, unpublished, hidden, expired and unknown reports with 404", async () => {
    const refused = {
      demo: { ...PIN, mode: "demo", feedPart: "demo", credit: "Photo by a donor", place: "Rizal Avenue, Manila" },
      unpublished: { ...PIN, published: false, feedPart: undefined },
      // F3: each boundary is now itself, from the test's ISO NOW.
      hidden: { ...PIN, visibleUntil: NOW_S },
      expired: { ...PIN, expiresAt: NOW_S },
    };
    for (const [name, item] of Object.entries(refused)) {
      ddbMock.on(QueryCommand).resolves({ Items: [item] });

      expect([name, await flag(DEVICE)]).toEqual([name, { statusCode: 404, body: { error: "not_found" } }]);
    }
    ddbMock.on(QueryCommand).resolves({ Items: [] });
    expect(await flag(DEVICE)).toEqual({ statusCode: 404, body: { error: "not_found" } });
    // A malformed id can't exist, so it costs no read.
    const malformed = await flagReport("r_nope", DEVICE, deps);
    expect(malformed.statusCode).toBe(404);
    expect(JSON.parse(malformed.body)).toEqual({ error: "not_found" });

    expect(ddbMock.commandCalls(QueryCommand)).toHaveLength(5);
    expect(ddbMock.commandCalls(TransactWriteCommand)).toHaveLength(0);
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(0);
    expect(ddbMock.commandCalls(UpdateCommand)).toHaveLength(0);
  });

  it("writes the flag record and the count in one TransactWriteItems", async () => {
    await flag(DEVICE);

    // F5, T5: every name through a placeholder, and the exact expressions, since the mock parses none.
    expect(transactions()).toStrictEqual([
      {
        TransactItems: [
          {
            Put: {
              TableName: "limits",
              Item: { pk: `flag#${ID}#${sha256(DEVICE)}`, expiresAt: EXPIRES_AT },
              ConditionExpression: "attribute_not_exists(#pk)",
              ExpressionAttributeNames: { "#pk": "pk" },
            },
          },
          {
            Update: {
              TableName: "reports",
              Key: { pk: "GEO#wdw515", sk: `${CAPTURED_AT}#${ID}` },
              UpdateExpression: "ADD #flags :one",
              ConditionExpression: "attribute_exists(#pk)",
              ExpressionAttributeNames: { "#flags": "flags", "#pk": "pk" },
              ExpressionAttributeValues: { ":one": 1 },
            },
          },
        ],
      },
    ]);
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(0);
    expect(ddbMock.commandCalls(UpdateCommand)).toHaveLength(0);
    // The report's read, then the one write.
    expect(ddbMock.calls()).toHaveLength(2);
  });

  it("keys the flag record on the device id's SHA-256, never the raw id", async () => {
    await flag(DEVICE);

    expect(transactions()[0]?.TransactItems?.[0].Put?.Item?.pk).toBe(`flag#${ID}#${sha256(DEVICE)}`);
    // Important 10, S7: no input sent anywhere holds the raw id (C520).
    for (const call of ddbMock.calls()) expect(JSON.stringify(call.args[0].input)).not.toContain(DEVICE);
  });

  it("gives clients without an id one shared flag per pin", async () => {
    expect(await flag(undefined)).toEqual({ statusCode: 200, body: { flags: 1 } });
    expect(await flag(undefined)).toEqual({ statusCode: 200, body: { flags: 1 } });
    // A malformed id counts in the same none bucket (C508).
    expect(await flag("bad id")).toEqual({ statusCode: 200, body: { flags: 1 } });

    expect(stored.flags).toBe(1);
    expect([...records.keys()]).toEqual([`flag#${ID}#${sha256("none")}`]);
  });

  it("keeps the flag record until the report's expiresAt", async () => {
    await flag(DEVICE);

    // The report's own expiresAt, 7 days after capture, not a time counted from now (PRIV-Q7).
    expect(records.get(`flag#${ID}#${sha256(DEVICE)}`)).toStrictEqual({
      pk: `flag#${ID}#${sha256(DEVICE)}`,
      expiresAt: Date.parse("2026-11-06T10:05:12Z") / 1000,
    });
  });

  it("never changes visibleUntil", async () => {
    // However many devices flag it, the pin stays as visible as it was (C511, MS4-Q3).
    for (let i = 0; i < 5; i++) await flag(`device-${i}-0123456789`);

    expect(stored).toStrictEqual({ ...PIN, flags: 5 });
    for (const { TransactItems } of transactions()) {
      const update = TransactItems?.[1].Update;
      expect(update?.UpdateExpression).toBe("ADD #flags :one");
      expect(update?.ExpressionAttributeNames).toStrictEqual({ "#flags": "flags", "#pk": "pk" });
      expect(update?.ExpressionAttributeValues).toStrictEqual({ ":one": 1 });
      expect(JSON.stringify(TransactItems)).not.toContain("visibleUntil");
    }
  });

  it("answers any other cancellation with an error, never as a repeat", async () => {
    // F19: the report gone between the read and the write, then a conflicting transaction.
    for (const codes of [
      ["None", "ConditionalCheckFailed"],
      ["TransactionConflict", "None"],
    ]) {
      ddbMock.on(TransactWriteCommand).callsFake(() => {
        throw cancelled(...codes);
      });

      await expect(flagReport(ID, DEVICE, deps)).rejects.toThrow(TransactionCanceledException);
    }
  });
});
