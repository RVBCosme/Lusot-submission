import { readFileSync } from "node:fs";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, GetCommand, UpdateCommand, type UpdateCommandInput } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MAX_OUTPUT_TOKENS } from "../src/ask/agent";
import type { LimitDeps } from "../src/limits";
import {
  costOf,
  PRICES,
  recordSpend,
  SPEND_ATTR,
  SPEND_PK,
  SPEND_SEEDED_ATTR,
  SpendUnseeded,
  sparkUsage,
  spendTotal,
  toMicro,
  UNREPORTED_USAGE,
  type Usage,
} from "../src/spend";

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

// Usage, spend.py's cost_of of it (normalized) and to_micro of that, from running spend.py on Oct 30, 2026.
// spend_contract.json has no cost cases, so these pin the two sides together. Floats get some wrong:
// the level case comes to 19,601 micro-dollars, and the probe's total to 0.12431525000000002.
const COSTS: [Usage, string, number][] = [
  [{ spark_input_tokens: 1 }, "0.00000125", 2], // one Spark input token
  [{ spark_output_tokens: 1 }, "0.00000425", 5],
  [{ spark_input_tokens: 1250 }, "0.0015625", 1563],
  [{ spark_input_tokens: 1234, spark_output_tokens: 567 }, "0.00395225", 3953], // a mixed call
  [{ sam_images: 7, spark_input_tokens: 1000, spark_output_tokens: 200 }, "0.0196", 19600], // test_spend.py's level case
  [{ audio_seconds: 7, spark_input_tokens: 3, spark_output_tokens: 3 }, "0.0003665", 367],
  // The most one question can use: 3 turns of 2,000 input and MAX_OUTPUT_TOKENS (1,200, C739) output
  // tokens. max_output_tokens covers reasoning, which Meta bills as output, so reasoning has no price of its own.
  [{ spark_input_tokens: 6000, spark_output_tokens: 3 * MAX_OUTPUT_TOKENS }, "0.0228", 22800],
  // Task 2's probe: 65,918 in and 9,863 out (6,021 of them reasoning); the counter went up $0.124316.
  [{ spark_input_tokens: 65918, spark_output_tokens: 9863 }, "0.12431525", 124316],
];

describe("costOf", () => {
  it("gives what spend.py's cost_of gives, as test_spend.py checks it", () => {
    expect(costOf({ sam_images: 1 })).toBe("0.0025");
    expect(costOf({ spark_input_tokens: 1_000_000 })).toBe("1.25");
    expect(costOf({ spark_output_tokens: 1_000_000 })).toBe("4.25");
    expect(costOf({ audio_seconds: 3600 })).toBe("0.18");
    expect(costOf({ audio_seconds: 1 })).toBe("0.00005");
    expect(costOf({})).toBe("0");
    // The unreported judge (spend.py's SPARK_TOKENS_IF_UNREPORTED).
    expect(costOf({ spark_input_tokens: 20_000, spark_output_tokens: 4_000 })).toBe("0.042");
  });

  it("prices the cases floats get wrong exactly, and toMicro rounds them up as to_micro does", () => {
    for (const [usage, usd, micro] of COSTS) {
      expect(costOf(usage), JSON.stringify(usage)).toBe(usd);
      expect(toMicro(costOf(usage)), JSON.stringify(usage)).toBe(micro);
    }
  });

  it("refuses a count it can't read, never pricing it at $0, and an unknown name, as cost_of raises", () => {
    // Present but undefined or null, not a number, not whole, negative or not finite.
    const bad: unknown[] = [undefined, null, "5", 1.5, -1, Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY];
    for (const count of bad) {
      for (const name of ["sam_images", "spark_input_tokens", "spark_output_tokens", "audio_seconds"]) {
        expect(() => costOf({ [name]: count } as Usage), `${name}: ${String(count)}`).toThrow(RangeError);
      }
    }
    // A name cost_of doesn't take, such as PRICES' singular one, or one only the prototype has.
    for (const name of ["sam_image", "spark_reasoning_tokens", "toString"]) {
      expect(() => costOf({ [name]: 5 } as Usage), name).toThrow(RangeError);
    }
    // Only an absent count is 0, as cost_of defaults only an absent keyword.
    expect(costOf({ spark_output_tokens: 4_000 })).toBe("0.017");
  });

  it("exports spend.py's unreported counts, priced at $0.042", () => {
    expect(UNREPORTED_USAGE).toEqual({ spark_input_tokens: 20_000, spark_output_tokens: 4_000 });
    expect(Object.isFrozen(UNREPORTED_USAGE)).toBe(true);
    expect(costOf(UNREPORTED_USAGE)).toBe("0.042");
    expect(toMicro(costOf(UNREPORTED_USAGE))).toBe(42_000);
  });

  it("with recordSpend, adds exactly cost_of's micro-dollars, rounded up, to the counter", async () => {
    let sum = 0;
    for (const [usage, , micro] of COSTS) {
      sum += micro;
      expect(await recordSpend(costOf(usage), "ask", deps())).toBe(sum / 1_000_000);
    }
    expect(sent()).toEqual(COSTS.map(([, , micro]) => ADD(micro)));
    expect(total).toBe(sum);
  });
});

// A Muse Spark reply as the Meta client returns it (Task 7's fixture, from Task 2's probe).
type Reply = { usage?: { input_tokens?: number | null; output_tokens?: number | null } };
const REPLY: Reply = JSON.parse(readFileSync(new URL("./fixtures/meta/ask_answer.json", import.meta.url), "utf8"));

describe("sparkUsage", () => {
  it("takes a reply's own counts", () => {
    expect(REPLY.usage).toMatchObject({ input_tokens: 1897, output_tokens: 320 });
    expect(sparkUsage(REPLY.usage)).toEqual({ spark_input_tokens: 1897, spark_output_tokens: 320 });
  });

  it("charges each count a reply leaves out at UNREPORTED_USAGE's, as handler.py's judge does", () => {
    expect(sparkUsage(undefined)).toEqual(UNREPORTED_USAGE);
    expect(sparkUsage(null)).toEqual(UNREPORTED_USAGE);
    expect(sparkUsage({})).toEqual(UNREPORTED_USAGE);
    expect(sparkUsage({ input_tokens: 1897, output_tokens: null })).toEqual({ spark_input_tokens: 1897, spark_output_tokens: 4_000 });
    expect(sparkUsage({ output_tokens: 320 })).toEqual({ spark_input_tokens: 20_000, spark_output_tokens: 320 });
  });

  it("charges a reply without usage $0.042 on the counter, not $0", async () => {
    const { usage, ...withoutUsage }: Reply = REPLY;
    expect(usage).toBeDefined();
    const reply: Reply = withoutUsage;

    expect(await recordSpend(costOf(sparkUsage(reply.usage)), "ask", deps())).toBe(0.042);
    expect(sent()).toEqual([ADD(42_000)]);
    // Read straight off the reply, the missing counts throw rather than price at $0.
    expect(() => costOf({ spark_input_tokens: reply.usage?.input_tokens, spark_output_tokens: reply.usage?.output_tokens } as Usage)).toThrow(RangeError);
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
