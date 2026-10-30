import { GetParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { mockClient } from "aws-sdk-client-mock";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createModelKey, MissingApiKey } from "../src/modelKey";
import { awsError } from "./awsError";

const ssm = new SSMClient({ region: "ap-southeast-1" });
const ssmMock = mockClient(ssm);
const NAME = "/lusot/test/model-key";
const KEY = "sentinel-model-key-00000000000000000000";
const SHORT = "sentinel-short-key"; // 18 characters

const reads = () => ssmMock.commandCalls(GetParameterCommand);

beforeEach(() => {
  ssmMock.reset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("the model key", () => {
  it("the key is read once, with decryption, by the name passed in", async () => {
    ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: KEY } });
    const key = createModelKey(ssm, NAME);

    expect(await key.get()).toBe(KEY);
    expect(await key.get()).toBe(KEY);
    expect(reads()).toHaveLength(1);
    expect(reads()[0].args[0].input).toEqual({ Name: NAME, WithDecryption: true });
  });

  it("drop() reads it again", async () => {
    const rotated = `${KEY}-rotated`;
    ssmMock.on(GetParameterCommand).resolvesOnce({ Parameter: { Value: KEY } }).resolves({ Parameter: { Value: rotated } });
    const key = createModelKey(ssm, NAME);

    expect(await key.get()).toBe(KEY);
    key.drop();
    expect(await key.get()).toBe(rotated);
    expect(reads()).toHaveLength(2);
  });

  it("a short key throws MissingApiKey without its value, and isn't kept", async () => {
    ssmMock.on(GetParameterCommand).resolvesOnce({ Parameter: { Value: SHORT } }).resolves({ Parameter: { Value: KEY } });
    const key = createModelKey(ssm, NAME);

    const err = await key.get().then(
      () => undefined,
      (e: unknown) => e,
    );
    expect(err).toBeInstanceOf(MissingApiKey);
    expect((err as Error).name).toBe("MissingApiKey");
    expect(`${String(err)} ${JSON.stringify(err)} ${(err as Error).stack}`).not.toContain(SHORT);

    expect(await key.get()).toBe(KEY);
    expect(reads()).toHaveLength(2);
  });

  it("a key of exactly 20 characters is accepted", async () => {
    ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: "k".repeat(20) } });

    expect(await createModelKey(ssm, NAME).get()).toHaveLength(20);
  });

  it("a parameter with no value throws MissingApiKey", async () => {
    ssmMock.on(GetParameterCommand).resolves({ Parameter: {} });

    await expect(createModelKey(ssm, NAME).get()).rejects.toBeInstanceOf(MissingApiKey);
  });

  it("the signal goes to SSM", async () => {
    ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: KEY } });
    const signal = new AbortController().signal;

    await createModelKey(ssm, NAME).get(signal);

    // The mock types send's arguments as the command alone, but it records the options too.
    expect((reads()[0].args as unknown[])[1]).toEqual({ abortSignal: signal });
  });

  it("a failed read throws SSM's error, and the next get reads again", async () => {
    ssmMock.on(GetParameterCommand).rejectsOnce(awsError("AccessDeniedException", 400)).resolves({ Parameter: { Value: KEY } });
    const key = createModelKey(ssm, NAME);

    await expect(key.get()).rejects.toMatchObject({ name: "AccessDeniedException" });
    expect(await key.get()).toBe(KEY);
    expect(reads()).toHaveLength(2);
  });

  it("logs nothing, so the key reaches no log line", async () => {
    const spies = (["error", "log", "warn", "info", "debug"] as const).map((level) =>
      vi.spyOn(console, level).mockImplementation(() => {}),
    );
    ssmMock.on(GetParameterCommand).resolvesOnce({ Parameter: { Value: SHORT } }).resolves({ Parameter: { Value: KEY } });
    const key = createModelKey(ssm, NAME);

    await key.get().catch(() => undefined);
    await key.get();
    key.drop();

    for (const spy of spies) expect(spy).not.toHaveBeenCalled();
  });
});
