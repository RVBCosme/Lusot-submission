import { GetParameterCommand, type SSMClient } from "@aws-sdk/client-ssm";
import { logError } from "./log";

const CACHE_MS = 30_000;

// Resolves true when the named switch under the prefix (for example "uploads") is on.
export type StopSwitch = (name: string, nowMs: number) => Promise<boolean>;

export function createStopSwitch(ssm: SSMClient, prefix: string): StopSwitch {
  const cache = new Map<string, { on: boolean; readAtMs: number }>();
  return async (name, nowMs) => {
    const hit = cache.get(name);
    if (hit && nowMs - hit.readAtMs < CACHE_MS) return hit.on;
    try {
      const { Parameter } = await ssm.send(new GetParameterCommand({ Name: prefix + name }));
      // Only an explicit "off" lets work through, so a mistyped value stops it.
      const on = Parameter?.Value !== "off";
      cache.set(name, { on, readAtMs: nowMs });
      return on;
    } catch (err) {
      // Fail closed. The failure isn't cached, so the next request reads SSM again.
      logError("stop_switch_unreadable", err, { name });
      return true;
    }
  };
}
