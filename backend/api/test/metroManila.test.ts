import { readFileSync, statSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { inBoundary, inMetroManila, parseBoundary } from "../src/metroManila";

const NCR_JSON = new URL("../src/data/ncr.json", import.meta.url);
const S2_JSON = new URL("./fixtures/s2-points.json", import.meta.url);

interface S2Point {
  name: string;
  lat: number;
  lng: number;
  inside: boolean;
  source: string;
  border_m: number;
}

const S2: S2Point[] = JSON.parse(readFileSync(S2_JSON, "utf8"));

// A 0.01-degree square around MS1's point, with a hole in its north-east quarter.
const SQUARE = [
  [120.98, 14.6],
  [121.0, 14.6],
  [121.0, 14.62],
  [120.98, 14.62],
  [120.98, 14.6],
];
const HOLE = [
  [120.995, 14.615],
  [120.998, 14.615],
  [120.998, 14.618],
  [120.995, 14.618],
  [120.995, 14.615],
];

describe("the Metro Manila test", () => {
  it("puts each S2 point on its side of the NCR border", () => {
    // Spec §7 S2: seven border pairs, one point a side, and a point in Manila Bay.
    expect(S2).toHaveLength(15);
    expect(S2.filter((p) => p.inside)).toHaveLength(7);
    for (const point of S2) {
      expect({ name: point.name, inside: inMetroManila(point.lat, point.lng) }).toEqual({ name: point.name, inside: point.inside });
    }
  });

  it("parses a malformed boundary to null, and a null boundary contains no point", () => {
    expect(parseBoundary({})).toBeNull();
    expect(parseBoundary({ type: "Polygon", coordinates: [SQUARE] })).toBeNull();
    expect(parseBoundary({ type: "MultiPolygon", coordinates: [[SQUARE.slice(0, 3)]] })).toBeNull();
    expect(parseBoundary({ type: "MultiPolygon", coordinates: [[[...SQUARE.slice(0, 4), [120.98, Number.NaN]]]] })).toBeNull();
    expect(parseBoundary(null)).toBeNull();
    expect(inBoundary(null, 14.6095, 120.9894)).toBe(false);

    // The same square, well formed, parses and holds MS1's point but not its hole.
    const square = parseBoundary({ type: "MultiPolygon", coordinates: [[SQUARE, HOLE]] });
    expect(inBoundary(square, 14.6095, 120.9894)).toBe(true);
    expect(inBoundary(square, 14.6165, 120.9965)).toBe(false);
    expect(inBoundary(square, 14.6095, 121.01)).toBe(false);
  });

  it("keeps the bundled boundary under 50 KB", () => {
    expect(statSync(NCR_JSON).size).toBeLessThan(50_000);
    expect(parseBoundary(JSON.parse(readFileSync(NCR_JSON, "utf8")))).not.toBeNull();
  });

  it("keeps every coordinate in ncr.json and s2-points.json to at most 6 decimals", () => {
    // F4: a longer float is a run of 12 or more digits, which the account-ID scan fails.
    expect(readFileSync(NCR_JSON, "utf8")).not.toMatch(/\.\d{7}/);
    expect(readFileSync(S2_JSON, "utf8")).not.toMatch(/\.\d{7}/);
  });
});
