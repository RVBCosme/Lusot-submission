// Helpers for the location tests: a point some metres north and east of another, and the inverse. Flat-earth
// arithmetic is good to a few millimetres over a few hundred metres, far inside the 0.5 m the tests allow. The
// radius is the one lib/geo.ts uses, so a point placed here is that far away by its haversine too.
import type { LatLng } from '../lib/geo'

const EARTH_RADIUS_M = 6_371_008.8
const RAD = Math.PI / 180

export function offsetM(origin: LatLng, northM: number, eastM: number): LatLng {
  return {
    lat: origin.lat + northM / EARTH_RADIUS_M / RAD,
    lng: origin.lng + eastM / (EARTH_RADIUS_M * Math.cos(origin.lat * RAD)) / RAD,
  }
}

export function offsetOf(origin: LatLng, point: LatLng): { northM: number; eastM: number } {
  return {
    northM: (point.lat - origin.lat) * RAD * EARTH_RADIUS_M,
    eastM: (point.lng - origin.lng) * RAD * EARTH_RADIUS_M * Math.cos(origin.lat * RAD),
  }
}
