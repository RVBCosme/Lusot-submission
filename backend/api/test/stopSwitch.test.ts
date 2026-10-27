import { GetParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { mockClient } from "aws-sdk-client-mock";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createStopSwitch } from "../src/stopSwitch";

const ssm = new SSMClient({ region: "ap-southeast-1" });
const ssmMock = mockClient(ssm);
const T0 = Date.parse("2026-10-30T10:00:00Z");

beforeEach(() => {
  ssmMock.reset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("stop switch", () => {
  it("stop switch reads are cached for 30 s", async () => {
    ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: "off" } });
    const isOn = createStopSwitch(ssm, "/lusot/stop/");

    expect(await isOn("uploads", T0)).toBe(false);
    expect(await isOn("uploads", T0 + 29_000)).toBe(false);
    expect(ssmMock.commandCalls(GetParameterCommand)).toHaveLength(1);

    expect(await isOn("uploads", T0 + 31_000)).toBe(false);
    const names = ssmMock.commandCalls(GetParameterCommand).map((call) => call.args[0].input.Name);
    expect(names).toEqual(["/lusot/stop/uploads", "/lusot/stop/uploads"]);
  });

  it("counts any value other than off as on", async () => {
    ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: "ON" } });

    expect(await createStopSwitch(ssm, "/lusot/stop/")("uploads", T0)).toBe(true);
  });

  it("counts a failed read as on and retries it on the next call", async () => {
    const logged = vi.spyOn(console, "error").mockImplementation(() => {});
    ssmMock
      .on(GetParameterCommand)
      .rejectsOnce(new Error("ssm unavailable"))
      .resolves({ Parameter: { Value: "off" } });
    const isOn = createStopSwitch(ssm, "/lusot/stop/");

    expect(await isOn("uploads", T0)).toBe(true);
    expect(await isOn("uploads", T0 + 1_000)).toBe(false);
    expect(ssmMock.commandCalls(GetParameterCommand)).toHaveLength(2);
    expect(logged).toHaveBeenCalledWith(expect.stringContaining("stop_switch_unreadable"));
  });
});
