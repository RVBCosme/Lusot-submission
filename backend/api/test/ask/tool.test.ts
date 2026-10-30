import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, QueryCommand, type QueryCommandInput } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import ngeohash from "ngeohash";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Deadline } from "../../src/ask/deadline";
import type { GeoResult, Geocoder, GeoTrace } from "../../src/ask/nominatim";
import type { Spot } from "../../src/ask/spots";
import {
  LEVELS,
  levelIndex,
  parseToolArgs,
  runGetReports,
  toModelOutput,
  type ToolArgs,
  type ToolCtx,
  type ToolResult,
} from "../../src/ask/tool";
import { distanceM, nearbyPins, type PinDeps, type PublicPin } from "../../src/pins";

const NOW_S = Date.parse("2026-10-30T10:06:40Z") / 1000;
const M_PER_DEG_LAT = 111_195;

function spot(fields: Partial<Spot> & { id: string }): Spot {
  return { name: fields.id, city: "Manila", lat: 14.6095, lng: 120.9894, roads: [], aliases: [], ...fields };
}

const ESPANA = spot({ id: "espana-maceda", name: "España Blvd cor. Maceda St", roads: ["España Boulevard", "Maceda Street"] });

// A point `metres` north of the spot.
const northOf = (metres: number) => ESPANA.lat + metres / M_PER_DEG_LAT;

// The capture time of a photo taken `minutes` before NOW_S.
const ago = (minutes: number) => new Date((NOW_S - minutes * 60) * 1000).toISOString();

let counter = 0;
// A live knee pin at the spot, taken `minutesAgo` before NOW_S.
function pin(fields: Partial<PublicPin> = {}, minutesAgo = 10): PublicPin {
  return {
    id: `r_${(counter++).toString(16).padStart(32, "0")}`,
    lat: ESPANA.lat,
    lng: ESPANA.lng,
    gpsAccuracyM: 12,
    capturedAt: ago(minutesAgo),
    mode: "live",
    level: "knee",
    landmark: "rim_three_quarters",
    passability: "NPLV",
    levelIsFloor: false,
    basis: { vehicles: 1, people: 0 },
    flags: 0,
    ...fields,
  };
}

function demoPin(fields: Partial<PublicPin> = {}): PublicPin {
  return pin({
    mode: "demo",
    capturedAt: "2009-09-26T02:30:00Z",
    credit: "Photo by a donor",
    place: "Rizal Avenue, Manila",
    ...fields,
  });
}

function args(fields: Partial<ToolArgs> = {}): ToolArgs {
  return { place: "", here: false, sinceMin: 180, kind: "depth", vehicle: "none", ...fields };
}

function found(fields: Partial<Extract<GeoResult, { status: "found" }>> = {}): GeoResult {
  return {
    status: "found",
    name: "Jollibee Maginhawa",
    lat: 14.6501,
    lng: 121.0501,
    box: { south: 14.65, north: 14.6502, west: 121.05, east: 121.0502 },
    spanM: 30,
    ...fields,
  };
}

function geocoder(result: GeoResult | undefined, trace: GeoTrace) {
  return { geocode: vi.fn<Geocoder["geocode"]>(async () => ({ result, trace })) };
}

// A context whose fakes record their calls. Every point is inside Metro Manila unless a test says otherwise.
function ctx(pins: PublicPin[] = [], fields: Partial<ToolCtx> = {}) {
  return {
    nearbyPins: vi.fn<ToolCtx["nearbyPins"]>(async () => pins),
    inMetroManila: vi.fn<ToolCtx["inMetroManila"]>(() => true),
    spots: [ESPANA],
    nowS: NOW_S,
    deadline: new Deadline(0, () => 0),
    ...fields,
  } satisfies ToolCtx;
}

const askArgs = (since: number, question: string): ToolArgs => {
  const parsed = parseToolArgs(
    JSON.stringify({ place: "España Blvd cor. Maceda St", here: false, since_minutes: since, kind: "depth", vehicle: "none" }),
    question,
  );
  if (parsed === undefined) throw new Error("the arguments should parse");
  return parsed;
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("the levels", () => {
  it("lists MS3a's nine in order, and indexes them", () => {
    expect(LEVELS).toEqual(["below_gutter", "gutter", "half_knee", "half_tire", "knee", "tire", "waist", "chest", "above_chest"]);
    expect(levelIndex("below_gutter")).toBe(0);
    expect(levelIndex("knee")).toBe(4);
    expect(levelIndex("above_chest")).toBe(8);
    expect(levelIndex("not_a_level")).toBe(-1);
  });
});

describe("parseToolArgs", () => {
  const call = (fields: Record<string, unknown> = {}) =>
    JSON.stringify({ place: "Jollibee Maginhawa", here: false, since_minutes: 180, kind: "depth", vehicle: "light", ...fields });

  it("reads a good call", () => {
    expect(parseToolArgs(call(), "gaano kalalim")).toEqual({
      place: "Jollibee Maginhawa",
      here: false,
      sinceMin: 180,
      kind: "depth",
      vehicle: "light",
    });
  });

  it("refuses bad JSON, a non-object and a missing field", () => {
    for (const text of ["", "{", "null", "[]", '"place"', "42"]) expect(parseToolArgs(text, ""), text).toBeUndefined();
    for (const field of ["place", "here", "since_minutes", "kind", "vehicle"]) {
      const { [field]: _, ...rest } = JSON.parse(call());
      expect(parseToolArgs(JSON.stringify(rest), ""), field).toBeUndefined();
    }
  });

  it("refuses wrong types", () => {
    const wrong: Record<string, unknown>[] = [
      { place: 7 },
      { place: null },
      { here: "true" },
      { here: 1 },
      { since_minutes: "60" },
      { since_minutes: 30.5 },
      { since_minutes: null },
      { kind: 1 },
      { vehicle: ["light"] },
    ];
    for (const fields of wrong) expect(parseToolArgs(call(fields), ""), JSON.stringify(fields)).toBeUndefined();
  });

  it("bad enums are refused", () => {
    expect(parseToolArgs(call({ vehicle: "suv" }), "")).toBeUndefined();
    expect(parseToolArgs(call({ kind: "off_topic" }), "")).toBeUndefined();
    expect(parseToolArgs(call({ kind: "Depth" }), "")).toBeUndefined();
    for (const vehicle of ["light", "heavy", "on_foot", "none"]) {
      expect(parseToolArgs(call({ vehicle }), "")?.vehicle).toBe(vehicle);
    }
    expect(parseToolArgs(call({ kind: "crossing" }), "")?.kind).toBe("crossing");
  });

  it("cleans the place as the geocoder does", () => {
    const messy = ` Jollibee\u0000  Maginhawa\n\t${"x".repeat(200)}`;
    const place = parseToolArgs(call({ place: messy }), "")?.place ?? "";
    expect(place.startsWith("Jollibee Maginhawa xxx")).toBe(true);
    expect(Array.from(place)).toHaveLength(100);
  });

  it("clamps since_minutes to 1 to 180", () => {
    expect(parseToolArgs(call({ since_minutes: 5000 }), "30 minuto")?.sinceMin).toBe(180);
    // 1 is the floor: a stated 0 minutes still leaves a window of 1.
    expect(parseToolArgs(call({ since_minutes: -20 }), "0 minutes")?.sinceMin).toBe(1);
  });

  it("keeps a window under 180 only for a stated time, and never below it (C732)", () => {
    const sinceMin = (since: number, question: string) => askArgs(since, question).sinceMin;
    expect(sinceMin(60, "in the last hour")).toBe(60);
    expect(sinceMin(60, "ngayon")).toBe(180);
    expect(sinceMin(60, "Gaano kalalim sa España cor. Maceda ngayon?")).toBe(180);
    expect(sinceMin(30, "in the last 2 hours")).toBe(120);
    expect(sinceMin(120, "30 minuto")).toBe(120);
    expect(sinceMin(30, "30 minuto")).toBe(30);
    expect(sinceMin(180, "30 minuto")).toBe(180);
    expect(sinceMin(60, "in the last 5 hours")).toBe(180);
  });
});

describe("the place", () => {
  it("here without a location gives no_location", async () => {
    const g = geocoder(found(), "called");
    const c = ctx([pin()], { geocoder: g });
    const result = await runGetReports(args({ here: true }), c);
    expect(result).toMatchObject({ status: "no_location", live: [], demo: [], count: 0, suggestions: [], geo: null });
    expect(c.nearbyPins).not.toHaveBeenCalled();
    expect(g.geocode).not.toHaveBeenCalled();
  });

  it("here outside Metro Manila gives outside_metro_manila", async () => {
    const c = ctx([pin()], { here: { lat: 10.3, lng: 123.9, accuracyM: 20 }, inMetroManila: vi.fn(() => false) });
    const result = await runGetReports(args({ here: true }), c);
    expect(result.status).toBe("outside_metro_manila");
    expect(c.inMetroManila).toHaveBeenCalledWith(10.3, 123.9);
    expect(c.nearbyPins).not.toHaveBeenCalled();
  });

  it("here inside Metro Manila reads the pins at the phone's point", async () => {
    const c = ctx([pin()], { here: { lat: 14.61, lng: 120.99, accuracyM: 20 } });
    const result = await runGetReports(args({ here: true, place: "ignored" }), c);
    expect(result).toMatchObject({
      status: "ok",
      place: { name: "here", source: "here" },
      point: { lat: 14.61, lng: 120.99 },
      geo: null,
    });
    expect(c.nearbyPins).toHaveBeenCalledWith(14.61, 120.99, 300);
  });

  it("a spot place resolves without the geocoder", async () => {
    const g = geocoder(found(), "called");
    const c = ctx([pin()], { geocoder: g });
    const result = await runGetReports(args({ place: "espana cor maceda" }), c);
    expect(result).toMatchObject({
      status: "ok",
      place: { name: ESPANA.name, source: "spots" },
      point: { lat: ESPANA.lat, lng: ESPANA.lng },
      geo: null,
      count: 1,
    });
    expect(g.geocode).not.toHaveBeenCalled();
    expect(c.inMetroManila).toHaveBeenCalledWith(ESPANA.lat, ESPANA.lng);
    expect(c.nearbyPins).toHaveBeenCalledWith(ESPANA.lat, ESPANA.lng, 300);
  });

  it("a listed spot whose point is outside Metro Manila gives outside_metro_manila", async () => {
    const c = ctx([pin()], { inMetroManila: vi.fn(() => false) });
    const result = await runGetReports(args({ place: "espana cor maceda" }), c);
    expect(result).toMatchObject({ status: "outside_metro_manila", place: { name: ESPANA.name, source: "spots" } });
    expect(result.point).toBeUndefined();
    expect(c.nearbyPins).not.toHaveBeenCalled();
  });

  it("an unknown place goes to the geocoder, with the deadline", async () => {
    const g = geocoder(found(), "called");
    const c = ctx([pin()], { geocoder: g });
    const result = await runGetReports(args({ place: "Jollibee Maginhawa" }), c);
    expect(g.geocode).toHaveBeenCalledWith("Jollibee Maginhawa", c.deadline);
    expect(result).toMatchObject({
      status: "ok",
      place: { name: "Jollibee Maginhawa", source: "nominatim" },
      point: { lat: 14.6501, lng: 121.0501 },
      geo: "called",
    });
    expect(c.nearbyPins).toHaveBeenCalledWith(14.6501, 121.0501, 300);
  });

  it("an answer from the geocoder's cache is read the same way", async () => {
    const result = await runGetReports(args({ place: "Jollibee Maginhawa" }), ctx([pin()], { geocoder: geocoder(found(), "cache") }));
    expect(result).toMatchObject({ status: "ok", geo: "cache", count: 1 });
  });

  it.each(["off", "busy", "failed"] as const)("a geocoder that is %s gives lookup_unavailable", async (trace) => {
    const c = ctx([pin()], { geocoder: geocoder(undefined, trace) });
    const result = await runGetReports(args({ place: "Jollibee Maginhawa" }), c);
    expect(result).toMatchObject({ status: "lookup_unavailable", geo: trace, live: [], demo: [], count: 0 });
    expect(c.nearbyPins).not.toHaveBeenCalled();
  });

  it("no geocoder at all gives lookup_unavailable", async () => {
    const c = ctx([pin()]);
    const result = await runGetReports(args({ place: "Jollibee Maginhawa" }), c);
    expect(result).toMatchObject({ status: "lookup_unavailable", geo: null });
    expect(c.nearbyPins).not.toHaveBeenCalled();
  });

  it("not_found gives place_not_found", async () => {
    const c = ctx([pin()], { geocoder: geocoder({ status: "not_found" }, "not_found") });
    const result = await runGetReports(args({ place: "Nowhere Plaza" }), c);
    expect(result).toMatchObject({ status: "place_not_found", geo: "not_found", live: [], count: 0 });
    expect(c.nearbyPins).not.toHaveBeenCalled();
  });

  it("an empty place is not found, and the geocoder is not asked", async () => {
    const g = geocoder(found(), "called");
    for (const place of ["", "  . , "]) {
      const result = await runGetReports(args({ place }), ctx([pin()], { geocoder: g }));
      expect(result).toMatchObject({ status: "place_not_found", geo: null });
    }
    expect(g.geocode).not.toHaveBeenCalled();
  });

  it("a found point outside Metro Manila gives outside_metro_manila", async () => {
    const c = ctx([pin()], { geocoder: geocoder(found({ lat: 10.31, lng: 123.89 }), "called"), inMetroManila: vi.fn(() => false) });
    const result = await runGetReports(args({ place: "Cebu Plaza" }), c);
    expect(result).toMatchObject({ status: "outside_metro_manila", place: { source: "nominatim" }, geo: "called" });
    expect(result.point).toBeUndefined();
    expect(c.inMetroManila).toHaveBeenCalledWith(10.31, 123.89);
    expect(c.nearbyPins).not.toHaveBeenCalled();
  });

  it("a wide result outside Metro Manila is outside, not too broad", async () => {
    const town = found({ name: "Bacoor", lat: 14.4624, lng: 120.9645, spanM: 9000 });
    const c = ctx([pin()], { geocoder: geocoder(town, "called"), inMetroManila: vi.fn(() => false) });
    const result = await runGetReports(args({ place: "Bacoor" }), c);
    expect(result.status).toBe("outside_metro_manila");
    expect(result.suggestions).toEqual([]);
  });

  describe("a wide place", () => {
    const inBox = (id: string, lat: number, lng: number) => spot({ id, name: `${id} corner`, lat, lng });
    const box = { south: 14.6, north: 14.61, west: 120.98, east: 121.0 };

    const street = found({ name: "Maginhawa Street", lat: 14.605, lng: 120.99, box, spanM: 1200 });

    it("a wide result is too broad, and offers the spots inside its box", async () => {
      // One spot just past each edge of the box, each nearer the result's point than the second spot inside.
      const spots = [
        inBox("inside-near", 14.602, 120.985),
        inBox("outside-north", 14.6101, 120.99),
        inBox("outside-south", 14.5999, 120.99),
        inBox("inside-far", 14.609, 120.996),
        inBox("outside-west", 14.605, 120.9799),
        inBox("outside-east", 14.605, 121.0001),
      ];
      const c = ctx([pin()], { geocoder: geocoder(street, "called"), spots });
      const result = await runGetReports(args({ place: "Maginhawa Street" }), c);
      expect(result).toMatchObject({
        status: "place_too_broad",
        place: { name: "Maginhawa Street", source: "nominatim" },
        suggestions: ["inside-near corner", "inside-far corner"],
        geo: "called",
        live: [],
        demo: [],
        count: 0,
      });
      expect(result.point).toBeUndefined();
      expect(c.nearbyPins).not.toHaveBeenCalled();
    });

    it("offers the three spots nearest the result's point, nearest first", async () => {
      // In list order they run one, two, three, four; by distance from (14.605, 120.99) they run two, one, four, three.
      const spots = [
        inBox("one", 14.601, 120.985),
        inBox("two", 14.605, 120.99),
        inBox("three", 14.609, 120.999),
        inBox("four", 14.602, 120.981),
      ];
      const result = await runGetReports(args({ place: "Maginhawa Street" }), ctx([], { geocoder: geocoder(street, "called"), spots }));
      expect(result.suggestions).toEqual(["two corner", "one corner", "four corner"]);
    });

    it("a wide result with no listed spot inside is still too broad", async () => {
      const result = await runGetReports(
        args({ place: "Maginhawa Street" }),
        ctx([pin()], { geocoder: geocoder(found({ box, spanM: 1200 }), "called"), spots: [] }),
      );
      expect(result).toMatchObject({ status: "place_too_broad", suggestions: [] });
    });

    it("over 300 m is too broad and 300 m is a point", async () => {
      const at = (spanM: number) =>
        runGetReports(args({ place: "Jollibee Maginhawa" }), ctx([pin()], { geocoder: geocoder(found({ spanM }), "called") }));
      expect((await at(300)).status).toBe("ok");
      expect((await at(301)).status).toBe("place_too_broad");
    });

    it("a road with two listed spots is too broad, and offers both", async () => {
      const spots = [
        spot({ id: "taft-pedro-gil", name: "Taft Ave cor. Pedro Gil St", roads: ["Taft Avenue", "Pedro Gil Street"] }),
        spot({ id: "un-taft", name: "UN Ave cor. Taft Ave", roads: ["Taft Avenue", "United Nations Avenue"] }),
        spot({ id: "other", name: "Aurora Blvd cor. Ramon Magsaysay", roads: ["Aurora Boulevard"] }),
      ];
      const g = geocoder(found(), "called");
      const c = ctx([pin()], { geocoder: g, spots });
      const result = await runGetReports(args({ place: "Taft Avenue" }), c);
      expect(result).toMatchObject({
        status: "place_too_broad",
        suggestions: ["Taft Ave cor. Pedro Gil St", "UN Ave cor. Taft Ave"],
        geo: null,
        live: [],
        count: 0,
      });
      expect(result.place).toBeUndefined();
      expect(g.geocode).not.toHaveBeenCalled();
      expect(c.nearbyPins).not.toHaveBeenCalled();
    });

    it("offers at most three spots on a road", async () => {
      const spots = ["a", "b", "c", "d"].map((id) => spot({ id, name: `${id} corner`, roads: ["Commonwealth Avenue"] }));
      const result = await runGetReports(args({ place: "Commonwealth Avenue" }), ctx([], { spots }));
      expect(result.suggestions).toEqual(["a corner", "b corner", "c corner"]);
    });
  });

  it("does not log the place, the point or anything else", async () => {
    const spies = (["log", "info", "warn", "error", "debug"] as const).map((name) => vi.spyOn(console, name).mockImplementation(() => {}));
    await runGetReports(args({ place: "espana cor maceda" }), ctx([pin()]));
    await runGetReports(args({ place: "Jollibee Maginhawa" }), ctx([pin()], { geocoder: geocoder(found(), "called") }));
    await runGetReports(args({ here: true }), ctx([pin()], { here: { lat: 14.61, lng: 120.99, accuracyM: 20 } }));
    for (const spy of spies) expect(spy).not.toHaveBeenCalled();
  });
});

describe("the window", () => {
  it("with 180, a 181-minute pin is out", async () => {
    const result = await runGetReports(askArgs(180, "gaano kalalim"), ctx([pin({}, 179), pin({}, 180), pin({}, 181)]));
    expect(result.windowMin).toBe(180);
    expect(result.count).toBe(2);
  });

  it("with 60 and 'in the last hour' in the question, a 61-minute pin is out", async () => {
    const result = await runGetReports(askArgs(60, "may baha ba in the last hour"), ctx([pin({}, 59), pin({}, 60), pin({}, 61)]));
    expect(result.windowMin).toBe(60);
    expect(result.count).toBe(2);
  });

  it("with 60 and 'ngayon', the window stays 180 (C732)", async () => {
    const result = await runGetReports(askArgs(60, "may baha ba ngayon"), ctx([pin({}, 61), pin({}, 179)]));
    expect(result.windowMin).toBe(180);
    expect(result.count).toBe(2);
  });

  it("with 30 and 'in the last 2 hours', the window is 120", async () => {
    const result = await runGetReports(askArgs(30, "in the last 2 hours"), ctx([pin({}, 119), pin({}, 121)]));
    expect(result.windowMin).toBe(120);
    expect(result.count).toBe(1);
  });

  it("a 2009 demo pin stays whatever the window", async () => {
    const result = await runGetReports(askArgs(60, "in the last hour"), ctx([pin({}, 61), demoPin()]));
    expect(result.count).toBe(0);
    expect(result.demo).toHaveLength(1);
    expect(result.status).toBe("ok");
  });
});

describe("ranking", () => {
  it("deepest first, a tie goes to the newer photo, and a floor ranks at its level", async () => {
    const knee10 = pin({ level: "knee" }, 10);
    const waist50 = pin({ level: "waist", passability: "NPATV" }, 50);
    const knee5 = pin({ level: "knee" }, 5);
    const halfTire1 = pin({ level: "half_tire" }, 1);
    // The floor (at least knee) is the oldest knee, so a ranking that gave it any bonus over the exact knees would put it
    // first among them. It still beats the newer half_tire, so it isn't ranked a level lower either.
    const kneeFloor20 = pin({ level: "knee", levelIsFloor: true }, 20);
    const result = await runGetReports(args({ place: ESPANA.name }), ctx([knee10, waist50, knee5, halfTire1, kneeFloor20]));
    expect(result.live.map((r) => r.pin.id)).toEqual([waist50, knee5, knee10, kneeFloor20, halfTire1].map((p) => p.id));
    expect(result.live.map((r) => r.ref)).toEqual(["r1", "r2", "r3", "r4", "r5"]);
    expect(result.count).toBe(5);
  });

  it("a newer floor does not outrank an older exact reading one level deeper", async () => {
    // The knee floor is 58 minutes newer than the tire. A bonus of a whole level would tie them, and the newer would win.
    const tire60 = pin({ level: "tire", passability: "NPATV" }, 60);
    const kneeFloor2 = pin({ level: "knee", levelIsFloor: true }, 2);
    const result = await runGetReports(args({ place: ESPANA.name }), ctx([kneeFloor2, tire60]));
    expect(result.live.map((r) => r.pin.id)).toEqual([tire60.id, kneeFloor2.id]);
  });

  it("a demo pin taken inside the window never joins the live list (C707)", async () => {
    // A donor photo from this week, seeded as a demo pin, deeper than the live reading.
    const live30 = pin({ level: "knee" }, 30);
    const demo20 = demoPin({ level: "chest", passability: "NPATV", capturedAt: ago(20) });
    const result = await runGetReports(args({ place: ESPANA.name }), ctx([demo20, live30]));
    expect(result.live.map((r) => [r.ref, r.pin.id])).toEqual([["r1", live30.id]]);
    expect(result.count).toBe(1);
    expect(result.demo.map((r) => [r.ref, r.pin.id])).toEqual([["d1", demo20.id]]);
    const output = JSON.parse(toModelOutput(result));
    expect(output.reports.map((r: { level: string }) => r.level)).toEqual(["knee"]);
    expect(output.demo_reports.map((r: { level: string }) => r.level)).toEqual(["chest"]);
  });

  it("the deepest of many is r1, and count is every live pin kept", async () => {
    const shallow = Array.from({ length: 6 }, (_, i) => pin({ level: "gutter" }, 10 + i));
    const chest = pin({ level: "chest", passability: "NPATV" }, 100);
    const stale = pin({ level: "above_chest" }, 181);
    const result = await runGetReports(args({ place: ESPANA.name }), ctx([...shallow, stale, chest]));
    expect(result.count).toBe(7);
    expect(result.live).toHaveLength(5);
    expect(result.live[0]).toMatchObject({ ref: "r1", pin: { id: chest.id } });
    expect(result.live.map((r) => r.ref)).toEqual(["r1", "r2", "r3", "r4", "r5"]);
    expect(result.live.map((r) => r.pin.id)).not.toContain(stale.id);
  });

  it("measures each pin from the point, in whole metres", async () => {
    const result = await runGetReports(args({ place: ESPANA.name }), ctx([pin({ lat: northOf(120) })]));
    const [first] = result.live;
    expect(first.distanceM).toBe(Math.round(distanceM({ lat: ESPANA.lat, lng: ESPANA.lng }, { lat: northOf(120), lng: ESPANA.lng })));
    expect(first.distanceM).toBeGreaterThanOrEqual(119);
    expect(first.distanceM).toBeLessThanOrEqual(121);
    expect(first.minutesAgo).toBe(10);
  });

  it("demo pins come nearest first from d1, at most three, with no window", async () => {
    const d250 = demoPin({ lat: northOf(250) });
    const d50 = demoPin({ lat: northOf(50) });
    const d150 = demoPin({ lat: northOf(150), capturedAt: "2012-08-07T00:00:00Z" });
    const d100 = demoPin({ lat: northOf(100) });
    const result = await runGetReports(args({ place: ESPANA.name, sinceMin: 1 }), ctx([d250, d50, d150, d100, pin({}, 30)]));
    expect(result.demo.map((r) => [r.ref, r.pin.id])).toEqual([
      ["d1", d50.id],
      ["d2", d100.id],
      ["d3", d150.id],
    ]);
    expect(result.demo[2].distanceM).toBeGreaterThanOrEqual(149);
    expect(result.live).toEqual([]);
    expect(result.count).toBe(0);
    expect(result.status).toBe("ok");
  });
});

describe("toModelOutput", () => {
  const SENTINEL_LAT = 14.123456;
  const SENTINEL_LNG = 120.654321;
  const sentinelSpot = spot({ id: "sentinel", name: "Sentinel Corner", lat: SENTINEL_LAT, lng: SENTINEL_LNG });

  async function sentinelResult(): Promise<ToolResult> {
    const live = [
      pin({ id: "r_SENTINEL_ID_LIVE_1", lat: SENTINEL_LAT, lng: SENTINEL_LNG, level: "waist", passability: "NPATV" }, 25),
      pin(
        { id: "r_SENTINEL_ID_LIVE_2", lat: SENTINEL_LAT, lng: SENTINEL_LNG, level: "knee", levelIsFloor: true, landmark: "SENTINEL_LANDMARK" },
        61,
      ),
    ];
    const demo = demoPin({
      id: "r_SENTINEL_ID_DEMO",
      lat: SENTINEL_LAT,
      lng: SENTINEL_LNG,
      level: "chest",
      passability: "NPATV",
      credit: "SENTINEL_CREDIT",
      place: "SENTINEL_PLACE",
      event: "SENTINEL_EVENT",
    });
    return runGetReports(args({ place: "Sentinel Corner" }), ctx([...live, demo], { spots: [sentinelSpot] }));
  }

  it("has the spec's fields and nothing else", async () => {
    const output = JSON.parse(toModelOutput(await sentinelResult()));
    expect(output).toEqual({
      status: "ok",
      place: "Sentinel Corner",
      window_minutes: 180,
      radius_m: 300,
      count: 2,
      reports: [
        { ref: "r1", level: "waist", level_is_floor: false, passability: "NPATV", minutes_ago: 25, distance_m: 0 },
        { ref: "r2", level: "knee", level_is_floor: true, passability: "NPLV", minutes_ago: 61, distance_m: 0 },
      ],
      demo_reports: [{ ref: "d1", level: "chest", level_is_floor: false, passability: "NPATV", year: 2009, distance_m: 0 }],
    });
  });

  it("gives a demo entry its floor and class beside its year, as spec 4.2 has it", async () => {
    // A demo reading that is a floor: "at least knee", class NPLV, taken in 2012, 100 m from the point.
    const demo = demoPin({ level: "knee", levelIsFloor: true, passability: "NPLV", capturedAt: "2012-08-07T00:00:00Z", lat: northOf(100) });
    const [entry] = JSON.parse(toModelOutput(await runGetReports(args({ place: ESPANA.name }), ctx([demo])))).demo_reports;
    expect(Object.keys(entry)).toEqual(["ref", "level", "level_is_floor", "passability", "year", "distance_m"]);
    expect(entry).toMatchObject({ ref: "d1", level: "knee", level_is_floor: true, passability: "NPLV", year: 2012 });
    expect(entry.distance_m).toBeGreaterThanOrEqual(99);
    expect(entry.distance_m).toBeLessThanOrEqual(101);
  });

  it("has no coordinates and no report ids", async () => {
    const text = toModelOutput(await sentinelResult());
    for (const secret of ["SENTINEL", "14.123456", "120.654321", "14.1235", "120.6543", '"lat"', '"lng"', '"id"', "credit", "capturedAt"]) {
      expect(text, secret).not.toContain(secret);
    }
  });

  it("gives at most 5 live and 3 demo reports, the ones the answer shows", async () => {
    const live = Array.from({ length: 8 }, (_, i) => pin({ level: "gutter" }, i + 1));
    const demo = Array.from({ length: 5 }, (_, i) => demoPin({ lat: northOf(10 * (i + 1)) }));
    const result = await runGetReports(args({ place: ESPANA.name }), ctx([...live, ...demo]));
    const output = JSON.parse(toModelOutput(result));
    expect(output.count).toBe(8);
    expect(output.reports.map((r: { ref: string }) => r.ref)).toEqual(["r1", "r2", "r3", "r4", "r5"]);
    expect(output.demo_reports.map((r: { ref: string }) => r.ref)).toEqual(["d1", "d2", "d3"]);
    expect(output.reports.map((r: { minutes_ago: number }) => r.minutes_ago)).toEqual([1, 2, 3, 4, 5]);
  });

  it("says only the status when there is no point", async () => {
    const output = JSON.parse(toModelOutput(await runGetReports(args({ here: true }), ctx())));
    expect(output).toEqual({
      status: "no_location",
      place: null,
      window_minutes: 180,
      radius_m: 300,
      count: 0,
      reports: [],
      demo_reports: [],
    });
  });

  it("gives the place's name for a too-broad place, with no suggestions or coordinates", async () => {
    const street = found({ name: "Maginhawa Street", spanM: 1200, box: { south: 14.6, north: 14.61, west: 120.98, east: 121.0 } });
    const result = await runGetReports(args({ place: "Maginhawa Street" }), ctx([], { geocoder: geocoder(street, "called"), spots: [] }));
    expect(JSON.parse(toModelOutput(result))).toEqual({
      status: "place_too_broad",
      place: "Maginhawa Street",
      window_minutes: 180,
      radius_m: 300,
      count: 0,
      reports: [],
      demo_reports: [],
    });
  });
});

describe("the publish switch (spec AK6)", () => {
  const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
  const ddbMock = mockClient(ddb);
  const CELL = ngeohash.encode(ESPANA.lat, ESPANA.lng, 6);
  const NOW_MS = NOW_S * 1000;

  function row(fields: Record<string, unknown>): Record<string, unknown> {
    return {
      reportId: `r_${(counter++).toString(16).padStart(32, "0")}`,
      lat: ESPANA.lat,
      lng: ESPANA.lng,
      gpsAccuracyM: 12,
      level: "knee",
      landmark: "rim_three_quarters",
      passability: "NPLV",
      levelIsFloor: false,
      basis: { vehicles: 1, people: 0 },
      flags: 0,
      published: true,
      visibleUntil: NOW_S + 3600,
      ...fields,
    };
  }

  function run(publishIsOn: boolean) {
    // The table never evaluates an expression, so it hands the spot's own cell every row it holds.
    const rows = [
      row({ mode: "live", capturedAt: new Date((NOW_S - 600) * 1000).toISOString(), level: "waist", passability: "NPATV" }),
      row({ mode: "demo", capturedAt: "2009-09-26T02:30:00Z", credit: "Photo by a donor", place: "Rizal Avenue, Manila" }),
    ];
    ddbMock.reset();
    ddbMock.on(QueryCommand).callsFake((input: QueryCommandInput) => ({
      Items: input.ExpressionAttributeValues?.[":pk"] === `GEO#${CELL}` ? rows : [],
    }));
    const deps: PinDeps = {
      ddb,
      tableName: "reports",
      feedIndexName: "feed-index",
      isStopped: async (name) => publishIsOn && name === "publish",
      inchesShown: false,
      now: () => NOW_MS,
    };
    const live = (lat: number, lng: number, radiusM: number) => nearbyPins({ lat, lng }, radiusM, deps);
    return runGetReports(args({ place: ESPANA.name }), ctx([], { nearbyPins: live }));
  }

  it("reads live and demo pins through MS4's nearbyPins while the switch is off", async () => {
    const result = await run(false);
    expect(result.status).toBe("ok");
    expect(result.live.map((r) => r.pin.level)).toEqual(["waist"]);
    expect(result.count).toBe(1);
    expect(result.demo).toHaveLength(1);
  });

  it("with the switch on, live pins are gone and the demo pin stays", async () => {
    const result = await run(true);
    expect(result.status).toBe("ok");
    expect(result.live).toEqual([]);
    expect(result.count).toBe(0);
    expect(result.demo).toHaveLength(1);
    expect(result.demo[0]).toMatchObject({ ref: "d1", pin: { mode: "demo" } });
  });
});
