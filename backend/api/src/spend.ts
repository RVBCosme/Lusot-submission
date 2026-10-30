import { GetCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import type { LimitDeps } from "./limits";

// The Meta spend counter (MS4's C527), the TypeScript twin of backend/analysis's spend.py (spec C736).
// Every paid Meta call adds its cost to one item in the limits table, as whole micro-dollars rounded
// up, so the count runs over, never under. The item has no expiresAt, so it never expires. Only a
// seeded counter is read: until seed_spend.py has run, spendTotal throws SpendUnseeded, so a new or
// re-created table reads as unreadable, never as $0. Both sides test against MS4's
// spend_contract.json. recordSpend's caller gives it its own client in deps.ddb (C736).

export const SPEND_PK = "spend#meta"; // the counter's key in the limits table
export const SPEND_ATTR = "micro_usd"; // its total, in whole micro-dollars
export const SPEND_SEEDED_ATTR = "seeded"; // set once by seed_spend.py; only a seeded total is read

// USD per unit: spend.py's PRICES (dev.meta.ai, Oct 26), as decimal strings, so no float rounds them.
// Transcription is charged by whole seconds.
export const PRICES = {
  sam_image: "0.0025",
  spark_input_token: "0.00000125",
  spark_output_token: "0.00000425",
  audio_second: "0.00005",
} as const;

const MICRO_DIGITS = 6;
const MAX_MICRO = 2n ** 53n - 1n; // the largest integer a number holds exactly
const PLAIN_USD = /^(\d+)(?:\.(\d+))?$/;

// The counter's item is missing or has no `seeded`: seed_spend.py hasn't run.
export class SpendUnseeded extends Error {
  constructor() {
    super("unseeded: the Meta spend counter has no seeded total; run seed_spend.py (docs/operations.md)");
    this.name = "SpendUnseeded";
  }
}

// `usd` in whole micro-dollars, rounded up, so a cost is never undercounted. It takes a plain unsigned
// decimal such as "0.0025" and works on its digits, never on a float. Anything else throws a
// RangeError, so a bad amount fails loud and never counts as less.
export function toMicro(usd: string): number {
  const match = PLAIN_USD.exec(usd);
  if (match === null) throw new RangeError("not a plain amount in USD");
  const [, whole, fraction = ""] = match;
  const kept = fraction.slice(0, MICRO_DIGITS).padEnd(MICRO_DIGITS, "0");
  const roundUp = /[1-9]/.test(fraction.slice(MICRO_DIGITS)) ? 1n : 0n;
  const micro = BigInt(whole + kept) + roundUp;
  if (micro > MAX_MICRO) throw new RangeError("amount in USD too large");
  return Number(micro);
}

function toUsd(micro: number): number {
  return micro / 1_000_000;
}

// Adds `usd` to the counter in one atomic ADD, and returns the new total in USD. `source` says who
// spent it, and goes to the log line only.
export async function recordSpend(usd: string, source: string, deps: LimitDeps): Promise<number> {
  const micro = toMicro(usd);
  const res = await deps.ddb.send(
    new UpdateCommand({
      TableName: deps.limitsTableName,
      Key: { pk: SPEND_PK },
      UpdateExpression: "ADD #micro :n",
      ExpressionAttributeNames: { "#micro": SPEND_ATTR },
      ExpressionAttributeValues: { ":n": micro },
      ReturnValues: "UPDATED_NEW",
    }),
  );
  const totalMicro = res.Attributes?.[SPEND_ATTR];
  if (typeof totalMicro !== "number") throw new Error("the spend counter gave back no total");
  const total = toUsd(totalMicro);
  console.log(JSON.stringify({ spend_source: source, spend_usd: String(toUsd(micro)), spend_total_usd: String(total) }));
  return total;
}

// The counter's total in USD, read strongly consistent. A missing item, or one with no `seeded` or no
// total, throws SpendUnseeded: never $0. spend.py projects the two attributes; this reads the small
// item whole, so the read has no ProjectionExpression for handler.test.ts's placeholder check to miss.
export async function spendTotal(deps: LimitDeps): Promise<number> {
  const { Item } = await deps.ddb.send(
    new GetCommand({ TableName: deps.limitsTableName, Key: { pk: SPEND_PK }, ConsistentRead: true }),
  );
  const micro = Item?.[SPEND_ATTR];
  if (Item === undefined || !(SPEND_SEEDED_ATTR in Item) || typeof micro !== "number") throw new SpendUnseeded();
  return toUsd(micro);
}
