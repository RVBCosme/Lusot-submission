import { GetParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { mockClient } from "aws-sdk-client-mock";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createModelKey, MissingApiKey } from "../src/modelKey";
import { awsError } from "./awsError";

const ssm = new SSMClient({ region: "ap-southeast-1" });
const ssmMock = mockClient(ssm);
const NAME = "/lusot/test/model-key";
const KEY = "sentinel-model-key-00000000000000000000";
// 19 characters. Each 4-character run holds a capital letter, so none can occur in the fixed, lowercase message
// by chance.
const SHORT = "QXZJ0WVK9PQY8RTB7MN";

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

  it.each(Array.from({ length: 20 }, (_, n) => n))(
    "a key of %i characters throws MissingApiKey, and its error holds no 4 characters of it",
    async (n) => {
      const value = SHORT.slice(0, n);
      ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: value } });

      const err = await createModelKey(ssm, NAME)
        .get()
        .then(
          () => undefined,
          (e: unknown) => e,
        );

      expect(err).toBeInstanceOf(MissingApiKey);
      expect((err as Error).name).toBe("MissingApiKey");
      const shown = `${(err as Error).message} ${String(err)} ${JSON.stringify(err)} ${(err as Error).stack}`;
      for (let i = 0; i + 4 <= value.length; i++) expect(shown).not.toContain(value.slice(i, i + 4));
    },
  );

  it("a short key isn't kept, so the next get reads again", async () => {
    ssmMock.on(GetParameterCommand).resolvesOnce({ Parameter: { Value: SHORT } }).resolves({ Parameter: { Value: KEY } });
    const key = createModelKey(ssm, NAME);

    await expect(key.get()).rejects.toBeInstanceOf(MissingApiKey);
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
