import { describe, expect, it } from "vitest";
import { normalize } from "../../src/ask/text";
import { SPOTS, findSpotIn, matchPlace, roadKey, spotKeywords, type Spot } from "../../src/ask/spots";

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

  it("a road that several spots sit on gives exactly those spots, and any other road gives its one", () => {
    const sitting = new Map<string, string[]>();
    for (const s of SPOTS) {
      for (const road of new Set(s.roads.map(normalize))) sitting.set(road, [...(sitting.get(road) ?? []), s.id]);
    }
    const wrong: string[] = [];
    for (const [road, ids] of sitting) {
      const found = matchPlace(road);
      const got = found === undefined ? undefined : "spot" in found ? [found.spot.id] : found.roadSpots.map((s) => s.id);
      if (JSON.stringify(got) !== JSON.stringify(ids)) wrong.push(`"${road}" gave ${JSON.stringify(got)}, wanted ${JSON.stringify(ids)}`);
      if (ids.length > 1 && !(found && "roadSpots" in found)) wrong.push(`"${road}" is on ${ids.length} spots but gave no roadSpots`);
    }
    expect(wrong).toEqual([]);
    expect([...sitting.values()].some((ids) => ids.length > 1)).toBe(true);
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
    // The whole place must be the road: a road with extra words around it is not that road.
    expect(matchPlace("Lone Road cor. Z St", list)).toBeUndefined();
  });

  it("a corner written by its two roads finds the spot, in either order", () => {
    // Every pair of different road keys among a spot's roads, in both orders. When another spot holds the same two
    // keys (the three Araneta spots list three spellings of one street), no corner is chosen.
    const keysOf = (s: Spot) => new Set(s.roads.map(roadKey));
    const wrong: string[] = [];
    let found = 0;
    for (const s of SPOTS) {
      for (const a of s.roads) {
        for (const b of s.roads) {
          if (roadKey(a) === roadKey(b)) continue;
          const holders = SPOTS.filter((h) => keysOf(h).has(roadKey(a)) && keysOf(h).has(roadKey(b)));
          const want = holders.length === 1 ? holders[0].id : undefined;
          const place = `${a} cor. ${b}`;
          if (want !== undefined) found++;
          if (idOf(matchPlace(place)) !== want) wrong.push(`matchPlace: ${place} wanted ${want} (${s.id})`);
          if (findSpotIn(`Gaano kalalim sa ${place} ngayon?`)?.id !== want) wrong.push(`findSpotIn: ${place} wanted ${want} (${s.id})`);
        }
      }
    }
    expect(wrong).toEqual([]);
    expect(found).toBeGreaterThan(0);

    for (const [place, id] of [
      ["UN Ave cor. Taft", "un-ave-taft"],
      ["España Blvd cor. Maceda", "espana-maceda"],
      ["Maceda cor. España", "espana-maceda"],
      ["Aurora Blvd cor. EDSA", "edsa-aurora"],
      ["Roxas at EDSA", "roxas-edsa"],
    ]) {
      expect(idOf(matchPlace(place)), place).toBe(id);
      expect(findSpotIn(`May baha ba sa ${place}?`)?.id, place).toBe(id);
    }
  });

  it("two roads that no spot holds together, or one road alone, find no spot", () => {
    for (const place of ["Quezon Ave corner Araneta", "Taft Avenue cor. Pedro Gil", "Shaw Boulevard cor. Pioneer St"]) {
      expect(matchPlace(place), place).toBeUndefined();
      expect(findSpotIn(`Gaano kalalim sa ${place}?`), place).toBeUndefined();
    }
    for (const place of ["EDSA", "Taft Avenue", "España"]) {
      expect(matchPlace(place), place).toHaveProperty("roadSpots");
    }
  });

  it("EDSA and a word that is also a road's name, with nothing joining them, find no spot (north bound)", () => {
    expect(findSpotIn("may baha ba sa EDSA north bound?")).toBeUndefined();
    expect(matchPlace("EDSA north bound")).toBeUndefined();
  });

  it("EDSA and a word that is also a road's name, with nothing joining them, find no spot (the main road)", () => {
    expect(findSpotIn("the main road on EDSA")).toBeUndefined();
    expect(matchPlace("Taft Avenue Quirino Avenue")).toBeUndefined();
  });

  it("two roads joined by a corner word still find their spot", () => {
    // None of these is a name or an alias.
    expect(findSpotIn("may baha ba sa EDSA at North?")?.id).toBe("edsa-north-avenue");
    expect(findSpotIn("baha ba sa EDSA & Main?")?.id).toBe("edsa-main-avenue");
    for (const [place, id] of [
      ["Roxas at EDSA", "roxas-edsa"],
      ["UN Ave cor. Taft", "un-ave-taft"],
      ["Maceda cor. España", "espana-maceda"],
    ]) {
      expect(idOf(matchPlace(place)), place).toBe(id);
      expect(findSpotIn(`May baha ba sa ${place}?`)?.id, place).toBe(id);
    }
  });

  it("the two roads of a corner must be two roads, apart, and held by one spot", () => {
    const taftA = spot("taft-a", "Taft Ave cor. A St", ["Taft Avenue", "A Street"]);
    const taftB = spot("taft-b", "Taft Ave cor. B St", ["Taft Avenue", "B Street"]);
    const bonny = spot("bonny", "Bonny corner", ["Colonel Bonny Avenue", "Bonny Avenue"]);
    const twin1 = spot("twin-1", "Twin 1", ["Ridge Road", "Valley Road"]);
    const twin2 = spot("twin-2", "Twin 2", ["Valley Rd", "Ridge Rd"]);
    const list = [taftA, taftB, bonny, twin1, twin2];

    // Either order, whatever the type word.
    expect(idOf(matchPlace("A St cor. Taft", list))).toBe("taft-a");
    expect(idOf(matchPlace("B Street and Taft Ave", list))).toBe("taft-b");
    // One road written twice is one road.
    expect(matchPlace("Taft Avenue cor. Taft", list)).toBeUndefined();
    // A road inside the other's words is not a second road.
    expect(matchPlace("Colonel Bonny Avenue Extension", list)).toBeUndefined();
    // Two spots hold both roads: no corner is chosen.
    expect(matchPlace("Ridge Road cor. Valley Road", list)).toBeUndefined();
    expect(findSpotIn("flooded at Ridge Road cor. Valley Road", list)).toBeUndefined();
    // "Aurora Blvd" and "Aurora Boulevard" are one road when keyed.
    expect(roadKey("Aurora Blvd")).toBe(roadKey("Aurora Boulevard"));
    expect(roadKey("Aurora")).toBe("aurora");
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
