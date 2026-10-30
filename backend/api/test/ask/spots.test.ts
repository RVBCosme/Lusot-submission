import { describe, expect, it } from "vitest";
import { normalize } from "../../src/ask/text";
import { SPOTS, findSpotIn, matchPlace, spotKeywords, type Spot } from "../../src/ask/spots";

function spot(id: string, name: string, roads: string[], aliases: string[] = []): Spot {
  return { id, name, city: "Manila", lat: 14.6, lng: 121, roads, aliases };
}

const idOf = (found: ReturnType<typeof matchPlace>) => (found && "spot" in found ? found.spot.id : undefined);

describe("the spot list", () => {
  it("holds spots.json's spots, each with a name and a point", () => {
    expect(SPOTS.length).toBeGreaterThan(0);
    for (const s of SPOTS) {
      expect(s.name, s.id).not.toBe("");
      expect(Number.isFinite(s.lat) && Number.isFinite(s.lng), s.id).toBe(true);
    }
  });

  it("no alias or name normalises to two different spots", () => {
    const owner = new Map<string, string>();
    const clashes: string[] = [];
    for (const s of SPOTS) {
      for (const form of [s.name, ...s.aliases]) {
        const key = normalize(form);
        const seen = owner.get(key);
        if (seen !== undefined && seen !== s.id) clashes.push(`"${key}" is in ${seen} and ${s.id}`);
        owner.set(key, s.id);
      }
    }
    expect(clashes).toEqual([]);
  });
});

describe("matchPlace", () => {
  it("spellings of one corner find one spot", () => {
    for (const place of ["ESPAÑA COR MACEDA!!", "espana cor maceda", "España corner Maceda", "España & Maceda"]) {
      expect(idOf(matchPlace(place)), place).toBe("espana-maceda");
    }
  });

  it("the longest alias wins", () => {
    expect(idOf(matchPlace("España cor. Maceda"))).toBe("espana-maceda");
    // A place with extra words still finds its spot.
    expect(idOf(matchPlace("EDSA Aurora Service Road southbound"))).toBe("edsa-aurora");

    const found = matchPlace("España");
    expect(found && "roadSpots" in found ? found.roadSpots.map((s) => s.id) : found).toEqual(["espana-maceda", "espana-antipolo"]);

    const short = spot("short", "Taft Short", ["Short Road"], ["Taft"]);
    const long = spot("long", "Taft Long", ["Long Road"], ["Taft PGH"]);
    expect(idOf(matchPlace("flooded at Taft PGH today", [short, long]))).toBe("long");
    expect(idOf(matchPlace("flooded at Taft today", [short, long]))).toBe("short");
  });

  it("a road with one spot finds it, and a road with several gives roadSpots", () => {
    const taftA = spot("taft-a", "Taft Ave cor. A St", ["Taft Avenue", "A Street"]);
    const taftB = spot("taft-b", "Taft Ave cor. B St", ["Taft Avenue", "B Street"]);
    const lone = spot("lone", "Lone Rd cor. C St", ["Lone Road"]);
    const list = [taftA, taftB, lone];
    expect(matchPlace("Taft Avenue", list)).toEqual({ roadSpots: [taftA, taftB] });
    expect(matchPlace("taft avenue!", list)).toEqual({ roadSpots: [taftA, taftB] });
    expect(matchPlace("Lone Road", list)).toEqual({ spot: lone });
    expect(matchPlace("B Street", list)).toEqual({ spot: taftB });
  });

  it("a word inside another word doesn't match", () => {
    expect(matchPlace("Oyster Plazas")).toBeUndefined();
    expect(matchPlace("Taftan")).toBeUndefined();
    expect(matchPlace("PGHQ")).toBeUndefined();
    expect(findSpotIn("is it flooded near PGHQ")).toBeUndefined();
    expect(findSpotIn("how deep at the Oyster Plazas")).toBeUndefined();
  });

  it("no spot gives undefined", () => {
    expect(matchPlace("Barangay Tatalon")).toBeUndefined();
    expect(matchPlace("")).toBeUndefined();
    expect(matchPlace("?!")).toBeUndefined();
    expect(findSpotIn("Gaano kalalim sa Bacoor?")).toBeUndefined();
    expect(matchPlace("España cor. Maceda", [])).toBeUndefined();
  });
});

describe("findSpotIn", () => {
  it("finds the longest alias in a question, on word boundaries", () => {
    expect(findSpotIn("Gaano kalalim ang baha sa España cor. Maceda?")?.id).toBe("espana-maceda");
    expect(findSpotIn("may baha ba sa EDSA & Shaw ngayon")?.id).toBe("edsa-shaw");
    expect(findSpotIn("is PGH flooded")?.id).toBe("taft-pgh");

    const short = spot("short", "Taft Short", [], ["Taft"]);
    const long = spot("long", "Taft Long", [], ["Taft PGH"]);
    expect(findSpotIn("flooded at Taft PGH today", [short, long])?.id).toBe("long");
  });

  it("does not guess a spot from a road alone", () => {
    expect(findSpotIn("Gaano kalalim sa España?")).toBeUndefined();
    expect(findSpotIn("baha sa EDSA?")).toBeUndefined();
  });
});

describe("spotKeywords", () => {
  it("gives the display names, for transcription", () => {
    const names = spotKeywords();
    expect(names).toEqual(SPOTS.map((s) => s.name));
    expect(names).toContain("España Blvd cor. Maceda St");
    expect(spotKeywords([spot("a", "A Place", [])])).toEqual(["A Place"]);
  });
});
