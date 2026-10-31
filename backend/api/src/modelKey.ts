import { GetParameterCommand, type SSMClient } from "@aws-sdk/client-ssm";

const MIN_KEY_CHARS = 20;

// Its message never holds the value it found.
export class MissingApiKey extends Error {
  constructor() {
    super(`the model key is missing or shorter than ${MIN_KEY_CHARS} characters`);
    this.name = "MissingApiKey";
  }
}

export type ModelKey = {
  get(signal?: AbortSignal): Promise<string>;
  // Forgets the key, so the next get reads SSM again (after Meta rejects it).
  drop(): void;
};

// The Meta key, read from SSM with decryption on first use and kept for the container's life. It is only ever
// returned to the caller: this module never logs it, puts it in an error or writes it anywhere.
export function createModelKey(ssm: SSMClient, name: string): ModelKey {
  let key: string | undefined;
  return {
    async get(signal) {
      if (key !== undefined) return key;
      const { Parameter } = await ssm.send(new GetParameterCommand({ Name: name, WithDecryption: true }), { abortSignal: signal });
      const value = Parameter?.Value;
      // A short value isn't kept, so the next get reads SSM again.
      if (value === undefined || value.length < MIN_KEY_CHARS) throw new MissingApiKey();
      key = value;
      return key;
    },
    drop() {
      key = undefined;
    },
  };
}
