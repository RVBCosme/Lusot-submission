import ncr from "./data/ncr.json";

// A GeoJSON MultiPolygon's coordinates: polygons, their rings, and each point as [lng, lat].
export type Boundary = number[][][][];

// The boundary, or null for anything but a MultiPolygon whose rings each have at least 4 finite points.
export function parseBoundary(data: unknown): Boundary | null {
  if (typeof data !== "object" || data === null) return null;
  const { type, coordinates } = data as { type?: unknown; coordinates?: unknown };
  if (type !== "MultiPolygon" || !nonEmptyArray(coordinates)) return null;
  const ok = coordinates.every(
    (polygon) =>
      nonEmptyArray(polygon) &&
      polygon.every(
        (ring) =>
          Array.isArray(ring) &&
          ring.length >= 4 &&
          ring.every((point) => Array.isArray(point) && point.length >= 2 && point.every(Number.isFinite)),
      ),
  );
  return ok ? (coordinates as Boundary) : null;
}

// Even-odd ray casting over every ring of every polygon, so holes count as outside.
export function inBoundary(boundary: Boundary | null, lat: number, lng: number): boolean {
  if (boundary === null) return false;
  let inside = false;
  for (const polygon of boundary) {
    for (const ring of polygon) {
      for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const [xi, yi] = ring[i];
        const [xj, yj] = ring[j];
        if (yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
      }
    }
  }
  return inside;
}

// OpenStreetMap's Metro Manila, clipped to the coastline (data/NCR_SOURCE.md). If it ever fails
// to parse, no point is inside, so every upload is private and none becomes a pin (spec §4.3).
const NCR = parseBoundary(ncr);

export function inMetroManila(lat: number, lng: number): boolean {
  return inBoundary(NCR, lat, lng);
}

function nonEmptyArray(value: unknown): value is unknown[] {
  return Array.isArray(value) && value.length > 0;
}
