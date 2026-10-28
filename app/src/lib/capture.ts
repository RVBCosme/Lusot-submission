// The camera and the GPS fix, through Capacitor: native plugins in the APK, and on the web
// a file picker and the browser's geolocation.
import { Camera } from '@capacitor/camera'
import { Geolocation } from '@capacitor/geolocation'

const MAX_SIDE_PX = 1600
const JPEG_QUALITY = 0.85

export async function capturePhoto(): Promise<{ blob: Blob; capturedAt: string }> {
  // takePhoto replaces the deprecated getPhoto (C11). The orientation is applied once, by
  // createImageBitmap below, from the photo's EXIF (its default imageOrientation is 'from-image').
  // On Android, webPath is the camera's original file, and correctOrientation would only rotate
  // the plugin's thumbnail, which isn't used, so it is off. webUseInput opens the web's file
  // picker directly, without the missing-PWA-Elements error; native ignores it.
  const photo = await Camera.takePhoto({ quality: 85, correctOrientation: false, webUseInput: true })
  const capturedAt = new Date().toISOString()
  if (photo.webPath === undefined) throw new Error('The camera returned no photo')
  const original = await (await fetch(photo.webPath)).blob()
  return { blob: await toJpeg(original), capturedAt }
}

export async function getFix(): Promise<{ lat: number; lng: number; accuracyM: number }> {
  const { coords } = await Geolocation.getCurrentPosition({ enableHighAccuracy: true, timeout: 15_000 })
  return { lat: coords.latitude, lng: coords.longitude, accuracyM: coords.accuracy }
}

// The size with the longest side at most 1600 px and the same proportions. A smaller photo keeps its size.
export function scaledSize(width: number, height: number): { width: number; height: number } {
  const scale = Math.min(1, MAX_SIDE_PX / Math.max(width, height))
  return { width: Math.round(width * scale), height: Math.round(height * scale) }
}

// Scales the photo down to scaledSize and encodes it as JPEG.
async function toJpeg(photo: Blob): Promise<Blob> {
  const bitmap = await createImageBitmap(photo)
  const size = scaledSize(bitmap.width, bitmap.height)
  const canvas = document.createElement('canvas')
  canvas.width = size.width
  canvas.height = size.height
  const context = canvas.getContext('2d')
  if (context === null) throw new Error('Canvas 2D is not available')
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()
  return new Promise((resolve, reject) =>
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('Could not encode the photo as JPEG'))),
      'image/jpeg',
      JPEG_QUALITY,
    ),
  )
}
