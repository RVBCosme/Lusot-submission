import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PROMPT_VERSION, loadPrompts, promptDir } from "../../src/ask/prompts";

// Test-only stand-in for Task 4's normalize, doing what it does for these samples: NFD, combining
// marks removed, lowercase, punctuation and spaces collapsed to one space, trimmed.
function normaliseSampleForThisTest(s: string): string {
  return s
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

function matches(patterns: RegExp[], sample: string): boolean {
  const text = normaliseSampleForThisTest(sample);
  return patterns.some((re) => re.test(text));
}

// Every object schema must set additionalProperties false and require every key (spec F4's strict rules).
function strictViolations(schema: unknown, path: string): string[] {
  if (typeof schema !== "object" || schema === null) return [];
  const node = schema as Record<string, unknown>;
  const found: string[] = [];
  if (node.type === "object") {
    const properties = (node.properties ?? {}) as Record<string, unknown>;
    if (node.additionalProperties !== false) found.push(`${path}: additionalProperties is not false`);
    const required = [...((node.required as string[] | undefined) ?? [])].sort();
    if (JSON.stringify(required) !== JSON.stringify(Object.keys(properties).sort())) {
      found.push(`${path}: required does not list every key`);
    }
    for (const [key, child] of Object.entries(properties)) found.push(...strictViolations(child, `${path}.${key}`));
  }
  if (node.type === "array") found.push(...strictViolations(node.items, `${path}[]`));
  return found;
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("Ask Lusot's prompt files", () => {
  const prompts = loadPrompts();

  it("the prompt version is ask_v1, and the instructions are the file's text", () => {
    expect(PROMPT_VERSION).toBe("ask_v1");
    expect(prompts.instructions).toBe(readFileSync(join(promptDir(), "ask_v1.md"), "utf8"));
    expect(prompts.instructions).toContain("get_reports");
  });

  it("the tool is get_reports, strict, with place, here, since_minutes, kind and vehicle", () => {
    const { tool } = prompts;
    expect(tool.type).toBe("function");
    expect(tool.name).toBe("get_reports");
    expect(tool.strict).toBe(true);
    const parameters = tool.parameters as { properties: Record<string, { type: string; enum?: string[] }> };
    expect(Object.keys(parameters.properties)).toEqual(["place", "here", "since_minutes", "kind", "vehicle"]);
    expect(parameters.properties.place.type).toBe("string");
    expect(parameters.properties.here.type).toBe("boolean");
    expect(parameters.properties.since_minutes.type).toBe("integer");
    expect(parameters.properties.kind.enum).toEqual(["depth", "crossing"]);
    expect(parameters.properties.vehicle.enum).toEqual(["light", "heavy", "on_foot", "none"]);
  });

  it("the off-topic tool is not_about_flood_depth, strict, with no arguments", () => {
    const { offTopicTool } = prompts;
    expect(offTopicTool.type).toBe("function");
    expect(offTopicTool.name).toBe("not_about_flood_depth");
    expect(offTopicTool.strict).toBe(true);
    expect(offTopicTool.parameters).toEqual({
      type: "object",
      additionalProperties: false,
      required: [],
      properties: {},
    });
  });

  it("every schema object sets additionalProperties false and requires every key", () => {
    expect(strictViolations(prompts.tool.parameters, "get_reports")).toEqual([]);
    expect(strictViolations(prompts.offTopicTool.parameters, "not_about_flood_depth")).toEqual([]);
    expect(strictViolations(prompts.answerSchema, "answer")).toEqual([]);
  });

  it("the answer schema's enums are exactly the spec's", () => {
    const properties = prompts.answerSchema.properties as Record<string, { enum?: string[]; type: string }>;
    expect(properties.kind.enum).toEqual(["depth", "crossing", "off_topic"]);
    expect(properties.vehicle.enum).toEqual(["light", "heavy", "on_foot", "none"]);
    expect(properties.cited.type).toBe("array");
    expect(prompts.answerSchema.required).toEqual(["kind", "vehicle", "cited"]);
  });

  it("the word lists compile, and match on normalised text", () => {
    for (const list of [prompts.crossing, prompts.here, prompts.heavy, prompts.walking, prompts.time]) {
      expect(list.length).toBeGreaterThan(0);
      for (const re of list) {
        expect(re).toBeInstanceOf(RegExp);
        expect(re.flags).toContain("i");
      }
    }

    expect(matches(prompts.crossing, "Lusot ba sedan ko?")).toBe(true);
    expect(matches(prompts.crossing, "LIGTAS ba")).toBe(true);
    expect(matches(prompts.crossing, "Lusot, gaano kalalim sa España?")).toBe(false);

    expect(matches(prompts.here, "May baha ba dito?")).toBe(true);

    expect(matches(prompts.heavy, "my truck")).toBe(true);
    expect(matches(prompts.heavy, "10-wheeler")).toBe(true);
    expect(matches(prompts.heavy, "Fortuner")).toBe(false);

    expect(matches(prompts.walking, "maglalakad ako")).toBe(true);

    expect(matches(prompts.time, "in the last hour")).toBe(true);
    expect(matches(prompts.time, "30 minuto")).toBe(true);
    expect(matches(prompts.time, "ngayon")).toBe(false);
  });

  it("loads once per folder, and finds the folder under LAMBDA_TASK_ROOT in Lambda", () => {
    expect(loadPrompts()).toBe(prompts);
    expect(promptDir()).toBe(join(process.cwd(), "prompts"));
    vi.stubEnv("LAMBDA_TASK_ROOT", "/var/task");
    expect(promptDir()).toBe(join("/var/task", "prompts"));
  });

  it("the build copies the prompts", () => {
    execFileSync(process.execPath, ["build.mjs"], { cwd: process.cwd(), stdio: "pipe" });
    const copied = readFileSync(join(process.cwd(), "dist", "prompts", "ask_v1.md"), "utf8");
    expect(copied).toBe(readFileSync(join(process.cwd(), "prompts", "ask_v1.md"), "utf8"));
  }, 60_000);
});
