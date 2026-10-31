import { describe, expect, it } from "vitest";
import { checkWav, decodeAudio } from "../../src/ask/wav";

type Spec = {
  rate?: number;
  channels?: number;
  bits?: number;
  format?: number;
  seconds?: number;
  dataBytes?: number;
  // The header's block size, when it should disagree with channels × bits / 8 (the byte rate follows it).
  block?: number;
  before?: { id: string; body: Uint8Array }[];
};

// A RIFF/WAVE file: the chunks in `before`, then `fmt `, then `data` of silence. Each chunk is padded to even.
function wav(spec: Spec = {}): Uint8Array {
  const { rate = 16000, channels = 1, bits = 16, format = 1, seconds = 2, before = [] } = spec;
  const block = spec.block ?? channels * (bits / 8);
  const dataBytes = spec.dataBytes ?? Math.round(seconds * rate) * block;
  const fmt = { id: "fmt ", body: fmtBody({ format, channels, rate, byteRate: rate * block, block, bits }) };
  return riff([...before, fmt, { id: "data", body: new Uint8Array(dataBytes) }]);
}

function fmtBody(f: { format: number; channels: number; rate: number; byteRate: number; block: number; bits: number }): Uint8Array {
  const body = new Uint8Array(16);
  const view = new DataView(body.buffer);
  view.setUint16(0, f.format, true);
  view.setUint16(2, f.channels, true);
  view.setUint32(4, f.rate, true);
  view.setUint32(8, f.byteRate, true);
  view.setUint16(12, f.block, true);
  view.setUint16(14, f.bits, true);
  return body;
}

function riff(chunks: { id: string; body: Uint8Array }[]): Uint8Array {
  const parts = chunks.map(({ id, body }) => {
    const out = new Uint8Array(8 + body.length + (body.length % 2));
    out.set(ascii(id), 0);
    new DataView(out.buffer).setUint32(4, body.length, true);
    out.set(body, 8);
    return out;
  });
  const size = 4 + parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(8 + size);
  out.set(ascii("RIFF"), 0);
  new DataView(out.buffer).setUint32(4, size, true);
  out.set(ascii("WAVE"), 8);
  let at = 12;
  for (const p of parts) {
    out.set(p, at);
    at += p.length;
  }
  return out;
}

function ascii(s: string): Uint8Array {
  return Uint8Array.from(s, (c) => c.charCodeAt(0));
}

describe("checkWav", () => {
  it("16 kHz and 24 kHz mono pass", () => {
    expect(checkWav(wav({ rate: 16000, seconds: 2 }))).toEqual({ ok: true, sampleRate: 16000, durationMs: 2000 });
    expect(checkWav(wav({ rate: 24000, seconds: 3.7 }))).toEqual({ ok: true, sampleRate: 24000, durationMs: 3700 });
  });

  it("stereo, 8-bit, 44.1 kHz and float are bad_audio", () => {
    expect(checkWav(wav({ channels: 2 }))).toEqual({ ok: false, code: "bad_audio" });
    expect(checkWav(wav({ bits: 8 }))).toEqual({ ok: false, code: "bad_audio" });
    expect(checkWav(wav({ rate: 44100 }))).toEqual({ ok: false, code: "bad_audio" });
    expect(checkWav(wav({ format: 3, bits: 32 }))).toEqual({ ok: false, code: "bad_audio" });
    // WAVE_FORMAT_EXTENSIBLE isn't format 1, whatever its subformat.
    expect(checkWav(wav({ format: 0xfffe }))).toEqual({ ok: false, code: "bad_audio" });
  });

  it("refuses stereo and 8-bit by those fields alone, with a block size and byte rate that agree with mono 16-bit", () => {
    expect(checkWav(wav({ channels: 2, bits: 8, block: 2 }))).toEqual({ ok: false, code: "bad_audio" });
    expect(checkWav(wav({ channels: 2, bits: 16, block: 2 }))).toEqual({ ok: false, code: "bad_audio" });
    expect(checkWav(wav({ channels: 1, bits: 8, block: 2 }))).toEqual({ ok: false, code: "bad_audio" });
    // The same header with 1 channel and 16 bits passes, so only the field under test refuses each.
    expect(checkWav(wav({ channels: 1, bits: 16, block: 2 }))).toMatchObject({ ok: true });
  });

  it("0.4 s is too short and 15.1 s too long", () => {
    expect(checkWav(wav({ seconds: 0.4 }))).toEqual({ ok: false, code: "audio_too_short" });
    expect(checkWav(wav({ seconds: 15.1 }))).toEqual({ ok: false, code: "audio_too_long" });
    expect(checkWav(wav({ rate: 24000, seconds: 15.1 }))).toEqual({ ok: false, code: "audio_too_long" });
    expect(checkWav(wav({ dataBytes: 0 }))).toEqual({ ok: false, code: "audio_too_short" });
  });

  it("the app's 14.9 s cap and exactly 15.0 s pass", () => {
    expect(checkWav(wav({ seconds: 14.9 }))).toEqual({ ok: true, sampleRate: 16000, durationMs: 14900 });
    expect(checkWav(wav({ seconds: 15 }))).toEqual({ ok: true, sampleRate: 16000, durationMs: 15000 });
    expect(checkWav(wav({ rate: 24000, seconds: 15 }))).toEqual({ ok: true, sampleRate: 24000, durationMs: 15000 });
    // One sample past 15 s is too long.
    expect(checkWav(wav({ dataBytes: 15 * 16000 * 2 + 2 }))).toEqual({ ok: false, code: "audio_too_long" });
  });

  it("exactly 0.5 s passes, and one sample less is too short", () => {
    expect(checkWav(wav({ seconds: 0.5 }))).toEqual({ ok: true, sampleRate: 16000, durationMs: 500 });
    expect(checkWav(wav({ dataBytes: 0.5 * 16000 * 2 - 2 }))).toEqual({ ok: false, code: "audio_too_short" });
  });

  it("a LIST chunk before data is fine", () => {
    const list = { id: "LIST", body: ascii("INFOISFT\x05\x00\x00\x00Lavf\x00") };
    expect(checkWav(wav({ before: [list] }))).toEqual({ ok: true, sampleRate: 16000, durationMs: 2000 });
  });

  it("an odd-sized chunk is skipped with its pad byte", () => {
    const odd = { id: "junk", body: new Uint8Array(3) };
    expect(checkWav(wav({ before: [odd] }))).toEqual({ ok: true, sampleRate: 16000, durationMs: 2000 });
  });

  it("a second fmt chunk is bad_audio", () => {
    const at16k = { id: "fmt ", body: fmtBody({ format: 1, channels: 1, rate: 16000, byteRate: 32000, block: 2, bits: 16 }) };
    // 720,000 bytes read as 15 s at 24 kHz, the second fmt, but as 22.5 s at 16 kHz, the first.
    expect(checkWav(wav({ rate: 24000, dataBytes: 720_000, before: [at16k] }))).toEqual({ ok: false, code: "bad_audio" });
  });

  it("reads a view that starts inside a larger buffer, as a pooled Buffer's slice does", () => {
    const good = wav();
    const padded = new Uint8Array(good.length + 7);
    padded.fill(0xff);
    padded.set(good, 7);
    expect(checkWav(padded.subarray(7))).toEqual({ ok: true, sampleRate: 16000, durationMs: 2000 });
  });

  it("a LIST chunk between fmt and data is fine, and bytes after data are ignored", () => {
    const good = wav();
    const fmtEnd = 12 + 8 + 16;
    const list = riff([{ id: "LIST", body: new Uint8Array(10) }]).slice(12);
    const withList = new Uint8Array(good.length + list.length + 6);
    withList.set(good.slice(0, fmtEnd), 0);
    withList.set(list, fmtEnd);
    withList.set(good.slice(fmtEnd), fmtEnd + list.length);
    expect(checkWav(withList)).toEqual({ ok: true, sampleRate: 16000, durationMs: 2000 });
  });

  it("a truncated header is bad_audio", () => {
    const good = wav();
    for (const n of [0, 4, 11, 12, 20, 30, 43]) {
      expect(checkWav(good.slice(0, n)), `${n} bytes`).toEqual({ ok: false, code: "bad_audio" });
    }
    // The data chunk says more bytes than the file holds.
    expect(checkWav(good.slice(0, good.length - 2))).toEqual({ ok: false, code: "bad_audio" });
  });

  it("anything but RIFF/WAVE with fmt before data is bad_audio", () => {
    const notRiff = wav();
    notRiff.set(ascii("RIFX"), 0);
    expect(checkWav(notRiff)).toEqual({ ok: false, code: "bad_audio" });
    const notWave = wav();
    notWave.set(ascii("AVI "), 8);
    expect(checkWav(notWave)).toEqual({ ok: false, code: "bad_audio" });
    const fmt = wav().slice(12, 12 + 24);
    const data = riff([{ id: "data", body: new Uint8Array(32000) }]).slice(12);
    const dataFirst = riff([]);
    const out = new Uint8Array(dataFirst.length + data.length + fmt.length);
    out.set(dataFirst, 0);
    out.set(data, 12);
    out.set(fmt, 12 + data.length);
    expect(checkWav(out)).toEqual({ ok: false, code: "bad_audio" });
    expect(checkWav(riff([{ id: "LIST", body: new Uint8Array(4) }]))).toEqual({ ok: false, code: "bad_audio" });
  });

  it("a header whose byte rate or block size disagrees, or an odd data size, is bad_audio", () => {
    const badRate = wav();
    new DataView(badRate.buffer).setUint32(12 + 8 + 8, 48000, true);
    expect(checkWav(badRate)).toEqual({ ok: false, code: "bad_audio" });
    const badBlock = wav();
    new DataView(badBlock.buffer).setUint16(12 + 8 + 12, 4, true);
    expect(checkWav(badBlock)).toEqual({ ok: false, code: "bad_audio" });
    expect(checkWav(wav({ dataBytes: 32001 }))).toEqual({ ok: false, code: "bad_audio" });
    const shortFmt = riff([{ id: "fmt ", body: new Uint8Array(14) }, { id: "data", body: new Uint8Array(32000) }]);
    expect(checkWav(shortFmt)).toEqual({ ok: false, code: "bad_audio" });
  });
});

describe("decodeAudio", () => {
  it("decodes strict base64 to its bytes", () => {
    const bytes = wav({ seconds: 0.6 });
    expect(decodeAudio(Buffer.from(bytes).toString("base64"))).toEqual(bytes);
    expect(decodeAudio("AAEC")).toEqual(Uint8Array.from([0, 1, 2]));
    expect(decodeAudio("AAE=")).toEqual(Uint8Array.from([0, 1]));
    expect(decodeAudio("AA==")).toEqual(Uint8Array.from([0]));
  });

  it("bad base64 is undefined", () => {
    for (const bad of ["", "AAE", "AA=", "A===", "AA==AA==", "AA E", "AAE\n", "AA-_", "AAE*", "AB==", "AAF=", "ÀÁÂÃ"]) {
      expect(decodeAudio(bad), JSON.stringify(bad)).toBeUndefined();
    }
  });

  it("a body of several MB is decoded or refused without throwing", () => {
    const big = Buffer.alloc(3_750_000).toString("base64"); // 5,000,000 characters
    expect(decodeAudio(big)?.length).toBe(3_750_000);
    expect(decodeAudio(`${big.slice(0, -1)}*`)).toBeUndefined();
  });

  it("anything but a string is undefined", () => {
    for (const bad of [undefined, null, 0, ["AAEC"], { audio: "AAEC" }, true]) {
      expect(decodeAudio(bad), JSON.stringify(bad)).toBeUndefined();
    }
  });
});
