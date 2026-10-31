// A spoken question's audio (spec §4.7, C719): checked here before any Meta call, so a bad clip costs nothing.
// Meta's transcription takes WAV only: mono 16-bit PCM at 16 or 24 kHz (F5). A clip runs 0.5 to 15 s (§5.4).

const RATES = new Set([16000, 24000]);
const BYTES_PER_SAMPLE = 2; // mono, 16-bit
const MIN_MS = 500;
const MAX_MS = 15000;

export type WavCheck =
  | { ok: true; sampleRate: 16000 | 24000; durationMs: number }
  | { ok: false; code: "bad_audio" | "audio_too_short" | "audio_too_long" };

// The audio field's bytes, or undefined unless it is a non-empty string of canonical base64: the standard alphabet,
// padded, with no whitespace and no stray padding bits. Node's decoder skips what it can't read, so the round trip
// refuses anything it changed. (No regex: one over a body of several MB overflows the stack.)
export function decodeAudio(field: unknown): Uint8Array | undefined {
  if (typeof field !== "string" || field === "") return undefined;
  const bytes = Buffer.from(field, "base64");
  if (bytes.toString("base64") !== field) return undefined;
  return new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.length);
}

// Walks the RIFF chunks from the start, so a LIST (or any other) chunk before `data` is fine. One `fmt ` must come
// before `data` and say format 1 (PCM), 1 channel, 16 bits, 16,000 or 24,000 Hz, with the byte rate and block size
// those give; a second one is refused, since decoders differ on which they read. `data` must fit in the file and
// hold whole samples; anything after it is ignored.
export function checkWav(bytes: Uint8Array): WavCheck {
  const bad = { ok: false, code: "bad_audio" } as const;
  if (bytes.length < 12 || tag(bytes, 0) !== "RIFF" || tag(bytes, 8) !== "WAVE") return bad;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.length);

  let rate: number | undefined;
  for (let at = 12; at + 8 <= bytes.length; ) {
    const id = tag(bytes, at);
    const size = view.getUint32(at + 4, true);
    const body = at + 8;
    if (id === "fmt ") {
      if (rate !== undefined || size < 16 || body + size > bytes.length) return bad;
      const format = view.getUint16(body, true);
      const channels = view.getUint16(body + 2, true);
      const sampleRate = view.getUint32(body + 4, true);
      const byteRate = view.getUint32(body + 8, true);
      const blockAlign = view.getUint16(body + 12, true);
      const bits = view.getUint16(body + 14, true);
      const pcm = format === 1 && channels === 1 && bits === 16 && RATES.has(sampleRate);
      if (!pcm || blockAlign !== BYTES_PER_SAMPLE || byteRate !== sampleRate * BYTES_PER_SAMPLE) return bad;
      rate = sampleRate;
    } else if (id === "data") {
      if (rate === undefined || body + size > bytes.length || size % BYTES_PER_SAMPLE !== 0) return bad;
      const samples = size / BYTES_PER_SAMPLE;
      // Compared in samples, so exactly 0.5 s and exactly 15.0 s pass at both rates.
      if (samples * 1000 < MIN_MS * rate) return { ok: false, code: "audio_too_short" };
      if (samples * 1000 > MAX_MS * rate) return { ok: false, code: "audio_too_long" };
      return { ok: true, sampleRate: rate as 16000 | 24000, durationMs: Math.round((samples * 1000) / rate) };
    }
    at = body + size + (size % 2); // chunks are padded to an even length
  }
  return bad; // no data chunk, or a header cut short
}

function tag(bytes: Uint8Array, at: number): string {
  return String.fromCharCode(bytes[at], bytes[at + 1], bytes[at + 2], bytes[at + 3]);
}
