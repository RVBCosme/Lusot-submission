import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { FunctionTool } from "openai/resources/responses/responses";

export const PROMPT_VERSION = "ask_v1";

export type AskPrompts = {
  instructions: string;
  tool: FunctionTool;
  // Sent only in turn 1's tools_only form (spec §4.3).
  offTopicTool: FunctionTool;
  answerSchema: Record<string, unknown>;
  // Each list is compiled case-insensitively and runs on normalized text.
  crossing: RegExp[];
  here: RegExp[];
  heavy: RegExp[];
  walking: RegExp[];
  time: RegExp[];
};

// In Lambda the build puts the prompts beside the bundle; locally Vitest runs from backend/api.
export function promptDir(): string {
  return join(process.env.LAMBDA_TASK_ROOT ?? process.cwd(), "prompts");
}

const cache = new Map<string, AskPrompts>();

export function loadPrompts(dir: string = promptDir()): AskPrompts {
  const hit = cache.get(dir);
  if (hit) return hit;
  const text = (name: string) => readFileSync(join(dir, `${PROMPT_VERSION}${name}`), "utf8");
  const json = <T>(name: string) => JSON.parse(text(name)) as T;
  const words = json<Record<"crossing" | "here" | "heavy" | "walking" | "time", string[]>>(".words.json");
  const compile = (patterns: string[]) => patterns.map((pattern) => new RegExp(pattern, "i"));
  const loaded: AskPrompts = {
    instructions: text(".md"),
    tool: json<FunctionTool>(".tools.json"),
    offTopicTool: json<FunctionTool>(".offtopic.json"),
    answerSchema: json<Record<string, unknown>>(".answer.json"),
    crossing: compile(words.crossing),
    here: compile(words.here),
    heavy: compile(words.heavy),
    walking: compile(words.walking),
    time: compile(words.time),
  };
  cache.set(dir, loaded);
  return loaded;
}
