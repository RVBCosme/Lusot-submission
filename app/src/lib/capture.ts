// The camera and the GPS fix, through Capacitor: native plugins in the APK, and on the web
// a file picker (the camera's fallback without PWA Elements) and the browser's geolocation.
import { Camera } from '@capacitor/camera'
import { Geolocation } from '@capacitor/geolocation'

const MAX_SIDE_PX = 1600
const JPEG_QUALITY = 0.85

export async function capturePhoto(): Promise<{ blob: Blob; capturedAt: string }> {
  // takePhoto replaces the deprecated getPhoto (C11).
  const photo = await Camera.takePhoto({ quality: 85 })
  const capturedAt = new Date().toISOString()
  if (photo.webPath === undefined) throw new Error('The camera returned no photo')
  const original = await (await fetch(photo.webPath)).blob()
  return { blob: await toJpeg(original), capturedAt }
}

export async function getFix(): Promise<{ lat: number; lng: number; accuracyM: number }> {
  const { coords } = await Geolocation.getCurrentPosition({ enableHighAccuracy: true, timeout: 15_000 })
  return { lat: coords.latitude, lng: coords.longitude, accuracyM: coords.accuracy }
}

// Scales the photo down so its longest side is at most 1600 px, and encodes it as JPEG.
async function toJpeg(photo: Blob): Promise<Blob> {
  const bitmap = await createImageBitmap(photo)
  const scale = Math.min(1, MAX_SIDE_PX / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
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
