import { writeFrames } from './frames'

// Runs once, before any browser starts: the fake camera's file has to exist when Chromium is launched.
export default function globalSetup(): void {
  writeFrames()
}
