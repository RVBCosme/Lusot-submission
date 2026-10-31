import { describe, expect, it } from 'vitest'
import buildGradle from '../android/app/build.gradle?raw'
import manifestXml from '../android/app/src/main/AndroidManifest.xml?raw'
import config from '../capacitor.config.ts'
import pkg from '../package.json' with { type: 'json' }

// The Android build's settings that only a manifest or a config file can hold. The manifest is read as text and
// parsed as XML, so no test needs a Gradle run. Task 17 sets all of them before the first APK stores anything.
const manifest = new DOMParser().parseFromString(manifestXml, 'application/xml')

function attr(element: Element, name: string): string | null {
  return element.getAttribute(`android:${name}`)
}

function usesFeature(name: string): Element {
  const found = [...manifest.getElementsByTagName('uses-feature')].find((e) => attr(e, 'name') === name)
  if (!found) throw new Error(`the manifest declares no ${name} feature`)
  return found
}

describe('package.json', () => {
  it('is version 0.5.0, the version of MS5', () => {
    expect(pkg.version).toBe('0.5.0')
  })
})

describe('capacitor.config.ts', () => {
  it('turns the plugin logging off, so a GPS fix is never written to the log', () => {
    expect(config.loggingBehavior).toBe('none')
  })

  it('names the app in the WebView user agent, with the version of package.json', () => {
    expect(config.appendUserAgent).toBe(`Lusot/${pkg.version}`)
    expect(config.appendUserAgent?.startsWith('Lusot/0.5')).toBe(true)
  })
})

describe('android/app/build.gradle', () => {
  it('names the app version 0.5.0, the version of package.json, and numbers this first build 1', () => {
    expect(buildGradle).toMatch(/^\s*versionName\s+"0\.5\.0"\s*$/m)
    expect(buildGradle).toContain(`versionName "${pkg.version}"`)
    expect(buildGradle).toMatch(/^\s*versionCode\s+1\s*$/m)
  })
})

describe('AndroidManifest.xml', () => {
  it('parses as XML', () => {
    expect(manifest.getElementsByTagName('parsererror')).toHaveLength(0)
    expect(manifest.documentElement.tagName).toBe('manifest')
  })

  it('allows no backup of the app data', () => {
    const application = manifest.getElementsByTagName('application')[0]
    expect(attr(application, 'allowBackup')).toBe('false')
    expect(manifestXml).toContain('android:allowBackup="false"')
  })

  it('asks for the camera, and does not require a camera', () => {
    const permissions = [...manifest.getElementsByTagName('uses-permission')].map((e) => attr(e, 'name'))
    expect(permissions).toContain('android.permission.CAMERA')
    expect(attr(usesFeature('android.hardware.camera'), 'required')).toBe('false')
  })

  it('asks for the microphone with RECORD_AUDIO and MODIFY_AUDIO_SETTINGS, and does not require a microphone', () => {
    // Capacitor's WebView client asks Android for both together when the page opens a microphone stream, and refuses
    // the stream if either is missing (Ask Lusot's Task 17).
    const permissions = [...manifest.getElementsByTagName('uses-permission')].map((e) => attr(e, 'name'))
    expect(permissions).toContain('android.permission.RECORD_AUDIO')
    expect(permissions).toContain('android.permission.MODIFY_AUDIO_SETTINGS')
    expect(attr(usesFeature('android.hardware.microphone'), 'required')).toBe('false')
  })

  it('does not require a GPS, so a store would not filter out a phone with network location only', () => {
    expect(attr(usesFeature('android.hardware.location.gps'), 'required')).toBe('false')
  })
})
