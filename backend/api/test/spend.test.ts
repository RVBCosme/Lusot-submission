import { readFileSync } from "node:fs";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, GetCommand, UpdateCommand, type UpdateCommandInput } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { LimitDeps } from "../src/limits";
import { PRICES, recordSpend, SPEND_ATTR, SPEND_PK, SPEND_SEEDED_ATTR, SpendUnseeded, spendTotal, toMicro } from "../src/spend";

// MS4's contract file, which spend.py's tests read too, so the two languages count the same way.
const CONTRACT: { key: string; attribute: string; seeded_attr: string; cases: [string, number][] } = JSON.parse(
  readFileSync(new URL("../../analysis/tests/fixtures/spend_contract.json", import.meta.url), "utf8"),
);

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
const ddbMock = mockClient(ddb);

function deps(): LimitDeps {
  return { ddb, limitsTableName: "limits" };
}

const ADD = (micro: number) => ({
  TableName: "limits",
  Key: { pk: "spend#meta" },
  UpdateExpression: "ADD #micro :n",
  ExpressionAttributeNames: { "#micro": "micro_usd" },
  ExpressionAttributeValues: { ":n": micro },
  ReturnValues: "UPDATED_NEW",
});
const READ = { TableName: "limits", Key: { pk: "spend#meta" }, ConsistentRead: true };

// The counter as DynamoDB keeps it: each ADD returns the new total.
let total: number;
function fakeCounter(): void {
  total = 0;
  ddbMock.on(UpdateCommand).callsFake((input: UpdateCommandInput) => {
    total += input.ExpressionAttributeValues?.[":n"];
    return { Attributes: { micro_usd: total } };
  });
}

function sent(): Record<string, unknown>[] {
  return ddbMock.calls().map((call) => call.args[0].input as Record<string, unknown>);
}

let logs: string[];
beforeEach(() => {
  ddbMock.reset();
  fakeCounter();
  logs = [];
  vi.spyOn(console, "log").mockImplementation((line: string) => void logs.push(line));
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("toMicro", () => {
  it("runs every spend_contract.json case, with its key and attributes", () => {
    expect([SPEND_PK, SPEND_ATTR, SPEND_SEEDED_ATTR]).toEqual([CONTRACT.key, CONTRACT.attribute, CONTRACT.seeded_attr]);
    expect(CONTRACT.cases.length).toBeGreaterThan(0);
    for (const [usd, micro] of CONTRACT.cases) expect(toMicro(usd), usd).toBe(micro);
  });

  it("rounds any fraction of a micro-dollar up, and only that", () => {
    expect(toMicro("0.000001000")).toBe(1);
    expect(toMicro("0.0000010000001")).toBe(2);
    expect(toMicro("0.124316")).toBe(124316);
    expect(toMicro("3.2044020000000000000001")).toBe(3204403);
    expect(toMicro("007")).toBe(7_000_000);
    expect(toMicro("9007199254.740991")).toBe(2 ** 53 - 1); // the largest integer a number holds exactly
  });

  it("refuses anything but a plain unsigned decimal, so a bad amount fails loud and never counts as less", () => {
    const bad = ["", " 0.37", "0.37 ", "-0.37", "+0.37", "1e-7", "1.25e-7", "NaN", "Infinity", "0x10", ".5", "5.", "1,000", "9007199254.740992"];
    for (const usd of bad) expect(() => toMicro(usd), usd).toThrow(RangeError);
  });
});

describe("PRICES", () => {
  it("are spend.py's, in USD per unit, as decimal strings", () => {
    // str() of spend.py's Decimals: 2.50 per 1,000 images, 1.25 and 4.25 per million tokens, 0.18 an hour.
    expect(PRICES).toEqual({
      sam_image: "0.0025",
      spark_input_token: "0.00000125",
      spark_output_token: "0.00000425",
      audio_second: "0.00005",
    });
  });
});

describe("recordSpend", () => {
  it("adds in one ADD #micro :n on spend#meta, with no expiresAt, and returns the new total in USD", async () => {
    expect(await recordSpend("0.0025", "test-a", deps())).toBe(0.0025);
    expect(await recordSpend("0.0025", "test-b", deps())).toBe(0.005);

    // One atomic ADD each, never a read and a write, so racing questions can't lose one.
    expect(sent()).toEqual([ADD(2500), ADD(2500)]);
    // The source goes to the log line only, as spend.py's does.
    expect(logs.map((line) => JSON.parse(line))).toEqual([
      { spend_source: "test-a", spend_usd: "0.0025", spend_total_usd: "0.0025" },
      { spend_source: "test-b", spend_usd: "0.0025", spend_total_usd: "0.005" },
    ]);
  });

  it("never undercounts: a fraction of a micro-dollar is counted as a whole one", async () => {
    expect(await recordSpend("0.0000001", "test", deps())).toBe(0.000001);
    expect(sent()).toEqual([ADD(1)]);
  });

  it("sends nothing for a bad amount, and throws on a DynamoDB error or a missing total, with no log line", async () => {
    await expect(recordSpend("1e-7", "test", deps())).rejects.toThrow(RangeError);
    expect(sent()).toEqual([]);

    ddbMock.reset();
    ddbMock.on(UpdateCommand).rejects(Object.assign(new Error("throttled"), { name: "ProvisionedThroughputExceededException" }));
    await expect(recordSpend("0.0025", "test", deps())).rejects.toThrow("throttled");

    // spend.py raises on a response without the total; so does this, never returning NaN.
    ddbMock.reset();
    ddbMock.on(UpdateCommand).resolves({});
    await expect(recordSpend("0.0025", "test", deps())).rejects.toThrow("no total");
    expect(logs).toEqual([]);
  });
});

describe("spendTotal", () => {
  it("throws SpendUnseeded for a missing or unseeded counter, never $0, and reads a seeded one", async () => {
    // A new or re-created table reads as unreadable, so Ask's check pauses until seed_spend.py has run.
    const unseeded = [
      undefined, // no item
      { pk: "spend#meta", micro_usd: 370000 }, // a question's ADD before the seed made it
      { pk: "spend#meta", seeded: true }, // seeded with no total
      { pk: "spend#meta", micro_usd: "370000", seeded: true }, // a total that isn't a number
    ];
    for (const Item of unseeded) {
      ddbMock.reset();
      ddbMock.on(GetCommand).resolves(Item === undefined ? {} : { Item });
      const err = await spendTotal(deps()).catch((e: unknown) => e);
      expect(err, JSON.stringify(Item)).toBeInstanceOf(SpendUnseeded);
      expect(err).toBeInstanceOf(Error);
      expect((err as Error).name).toBe("SpendUnseeded");
      expect((err as Error).message).toMatch(/^unseeded/);
    }

    ddbMock.reset();
    ddbMock.on(GetCommand).resolves({ Item: { pk: "spend#meta", micro_usd: 370000, seeded: true } });
    expect(await spendTotal(deps())).toBe(0.37);
    // Strongly consistent, so a check right after another question's ADD sees it, and reading never makes the item.
    expect(sent()).toEqual([READ]);
  });

  it("lets a DynamoDB error through", async () => {
    ddbMock.on(GetCommand).rejects(Object.assign(new Error("throttled"), { name: "ProvisionedThroughputExceededException" }));
    await expect(spendTotal(deps())).rejects.toThrow("throttled");
  });
});

// The check handler.test.ts makes of every route's commands (MS4's F5 rule), for spend.ts's own.
const EXPRESSIONS = ["KeyConditionExpression", "FilterExpression", "UpdateExpression", "ConditionExpression", "ProjectionExpression"] as const;
const KEYWORDS = /\b(AND|OR|NOT|SET|ADD|REMOVE|DELETE|BETWEEN|IN)\b/g;
const FUNCTIONS = /\b(attribute_exists|attribute_not_exists|attribute_type|begins_with|contains|size|if_not_exists|list_append)\s*\(/g;
const PLACEHOLDERS = /[#:][A-Za-z0-9_]+/g;

function bareNames(expression: string): string[] {
  const rest = expression.replace(PLACEHOLDERS, " ").replace(FUNCTIONS, " (").replace(KEYWORDS, " ");
  return rest.match(/[A-Za-z0-9_]+/g) ?? [];
}

describe("spend.ts's commands", () => {
  it("name every attribute in every expression through a placeholder, with none left over", async () => {
    await recordSpend("0.0025", "test", deps());
    ddbMock.on(GetCommand).resolves({ Item: { pk: "spend#meta", micro_usd: 2500, seeded: true } });
    await spendTotal(deps());

    const inputs = sent();
    expect(inputs).toHaveLength(2);
    for (const input of inputs) {
      const names = (input.ExpressionAttributeNames ?? {}) as Record<string, string>;
      const values = (input.ExpressionAttributeValues ?? {}) as Record<string, unknown>;
      const used: string[] = [];
      for (const field of EXPRESSIONS) {
        const expression = input[field];
        if (expression === undefined) continue;
        expect(bareNames(expression as string), `${field}: ${expression}`).toEqual([]);
        used.push(...((expression as string).match(PLACEHOLDERS) ?? []));
      }
      for (const token of used) expect(Object.keys(token.startsWith("#") ? names : values), token).toContain(token);
      expect([...Object.keys(names), ...Object.keys(values)].filter((token) => !used.includes(token))).toEqual([]);
    }
    // The read has no projection, so handler.test.ts's check (which knows no ProjectionExpression) needs no change.
    expect(inputs[1]).not.toHaveProperty("ProjectionExpression");
  });
});
