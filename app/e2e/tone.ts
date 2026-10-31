// The fake microphone's sound for Ask Lusot's end-to-end spec (its Task 16): Chromium's --use-file-for-fake-audio-capture
// plays a WAV file as the microphone, so this writes one, a 2 s 1 kHz tone at 16 kHz, mono, 16-bit, with no voice in it.
// It goes to the git-ignored e2e/.frames/, beside the fake camera's frame, before the browser starts (global-setup.ts).
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { FRAMES_DIR } from './frames'

export const TONE_WAV = fileURLToPath(new URL('./.frames/tone.wav', import.meta.url))

const RATE = 16000
const SECONDS = 2
const HZ = 1000

export function writeTone(): void {
  const samples = RATE * SECONDS
  const wav = Buffer.alloc(44 + samples * 2)
  wav.write('RIFF', 0, 'ascii')
  wav.writeUInt32LE(36 + samples * 2, 4)
  wav.write('WAVEfmt ', 8, 'ascii')
  wav.writeUInt32LE(16, 16)
  wav.writeUInt16LE(1, 20) // PCM
  wav.writeUInt16LE(1, 22) // mono
  wav.writeUInt32LE(RATE, 24)
  wav.writeUInt32LE(RATE * 2, 28)
  wav.writeUInt16LE(2, 32)
  wav.writeUInt16LE(16, 34)
  wav.write('data', 36, 'ascii')
  wav.writeUInt32LE(samples * 2, 40)
  for (let i = 0; i < samples; i++) wav.writeInt16LE(Math.round(0.4 * 32767 * Math.sin((2 * Math.PI * HZ * i) / RATE)), 44 + 2 * i)
  mkdirSync(FRAMES_DIR, { recursive: true })
  writeFileSync(TONE_WAV, wav)
}
