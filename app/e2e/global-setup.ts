import { writeFrames } from './frames'
import { writeTone } from './tone'

// Runs once, before any browser starts: the fake camera's and the fake microphone's files have to exist when Chromium is
// launched.
export default function globalSetup(): void {
  writeFrames()
  writeTone()
}
