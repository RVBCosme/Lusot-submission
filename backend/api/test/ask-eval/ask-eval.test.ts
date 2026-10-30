// Ask Lusot's 10 typed questions with real Muse Spark calls (spec AK1, C728): paid, so skipped unless LUSOT_ASK_EVAL
// is 1. The Meta key comes from MODEL_API_KEY and is never printed. The spend counter, its stop and the stop switches
// are the deployed stack's, read and written with the lusot profile's `aws login` credentials in ap-southeast-1, so
// every question's cost reaches MS4's counter under the source "ask" (C527, C736). The limits table's name comes from
// LIMITS_TABLE_NAME. The answers go to LUSOT_DATA_DIR\ask\<date>\answers.jsonl; stdout gets counts and timings only.
// From the repo root, in PowerShell, after `aws login --profile lusot`:
//   $env:MODEL_API_KEY = [Environment]::GetEnvironmentVariable('MODEL_API_KEY','User'); $env:LUSOT_ASK_EVAL = '1'
//   $env:LIMITS_TABLE_NAME = aws cloudformation describe-stack-resource --stack-name lusot --logical-resource-id LimitsTable --query StackResourceDetail.PhysicalResourceId --output text --profile lusot --no-cli-pager
//   npm run ask:eval -w backend/api
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient } from "@aws-sdk/lib-dynamodb";
import { describe, expect, it } from "vitest";
import { SPEND_CLIENT_CONFIG } from "../../src/ask/handler";
import { localDate, runHarness } from "./harness";

const PAID = process.env.LUSOT_ASK_EVAL === "1";
// The handler's spend client bounds, always the lusot profile (a stray AWS_PROFILE could reach another account).
const AWS_CONFIG = { ...SPEND_CLIENT_CONFIG, region: "ap-southeast-1", profile: "lusot" };
const DATA_DIR = "C:\\Systems\\Lusot\\lusot-data"; // when LUSOT_DATA_DIR is unset
const MIN_KEY_CHARS = 20; // modelKey.ts's

describe.skipIf(!PAID)("Ask Lusot's 10 typed questions, with real Muse Spark calls (paid)", () => {
  it("answers every question within the rules", async () => {
    const key = process.env.MODEL_API_KEY ?? "";
    if (key.length < MIN_KEY_CHARS) throw new Error("MODEL_API_KEY is missing or too short");
    const limitsTableName = process.env.LIMITS_TABLE_NAME;
    if (!limitsTableName) throw new Error("LIMITS_TABLE_NAME is not set: the deployed stack's LimitsTable");

    const summary = await runHarness({
      dataDir: process.env.LUSOT_DATA_DIR || DATA_DIR,
      date: localDate(Date.now()),
      limitsTableName,
      spendDdb: DynamoDBDocumentClient.from(new DynamoDBClient(AWS_CONFIG)),
      ssm: new SSMClient(AWS_CONFIG),
      key,
      print: (line) => console.log(line),
    });

    expect(summary.failed).toBe(0);
  }, 600_000);
});
