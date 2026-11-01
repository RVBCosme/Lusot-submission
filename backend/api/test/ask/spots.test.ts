import { describe, expect, it } from "vitest";
import { normalize } from "../../src/ask/text";
import { SHORT_FORMS, SPOTS, findSpotIn, matchPlace, roadKey, spotKeywords, type Spot } from "../../src/ask/spots";

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

// The exact list Meta took on Nov 1 (a test call: HTTP 200 with these 97). A spot or road added to spots.json changes
// it, so this fails before a deploy could send Meta a list it hasn't been shown to take. Update it only after Meta has
// taken the new list in a test call. Oct 31's list was the same without the three short forms (call 6, 94 keywords).
const TESTED_KEYWORDS = [
  "F. Ortigas St cor. Boni Ave", "EDSA cor. Aurora Blvd", "EDSA cor. Kamuning Rd", "EDSA cor. North Ave",
  "EDSA cor. Main Ave", "Taft Ave in front of PGH", "España Blvd cor. Maceda St", "España Blvd cor. Antipolo St",
  "Marcos Highway at SM Marikina", "EDSA cor. Shaw Blvd", "EDSA cor. P. Tuazon Blvd", "Roxas Blvd cor. EDSA",
  "Roxas Blvd cor. Pedro Gil St", "UN Ave cor. Taft Ave", "G. Araneta Ave cor. Baloy St", "Samat St cor. Don Jose St",
  "Taft Ave cor. Quirino Ave", "Roxas Blvd at the US Embassy", "Roxas Blvd cor. T.M. Kalaw Ave", "3S Center, Dalandanan",
  "Toyota Dalandanan", "EDSA Santolan", "Oyster Plaza", "SM Sucat", "F. Ortigas Street", "Boni Avenue", "F. Ortigas", "Boni", "EDSA", "Aurora Boulevard",
  "Kamuning Road", "Kamuning", "Gregorio Araneta Avenue", "E. Rodriguez Sr. Avenue", "G. Araneta Avenue", "Araneta",
  "E. Rodriguez", "Colonel Bonny Serrano Avenue", "Col. Bonny Serrano Avenue", "Bonny Serrano Avenue", "North Avenue",
  "North Ave", "Quezon Avenue", "Biak na Bato Street", "Quezon Ave", "Biak na Bato", "Main Avenue", "Main Ave",
  "Taft Avenue", "Taft Ave", "Taft", "España Boulevard", "A. Maceda Street", "España", "España Blvd", "Maceda",
  "Antipolo Street", "Marcos Highway", "Shaw Boulevard", "Shaw", "P. Tuazon Boulevard", "P. Tuazon",
  "Ninoy Aquino Avenue", "Dr. A. Santos Avenue", "Dr. Arcadio Santos Avenue", "Sucat Road", "Roxas Boulevard",
  "Roxas Blvd", "Roxas", "Pedro Gil Street", "Pedro Gil", "United Nations Avenue", "UN Avenue", "UN Ave",
  "Baloy Street", "Santo Domingo Avenue", "Calamba Street", "Sto. Domingo Avenue", "Sto. Domingo", "Samat Street",
  "Don Jose Street", "Samat", "Don Jose", "N. S. Amoranto Sr. Avenue", "Amoranto", "NS Amoranto", "Quirino Avenue",
  "Kalaw Avenue", "Kalaw", "T.M. Kalaw Avenue", "Senator Gil J. Puyat Avenue", "Gil Puyat Avenue", "Buendia",
  "Maria Clara Street", "Ma. Clara", "Victor Medina Street", "Kabihasnan",
];

describe("spotKeywords", () => {
  it("sends no keyword over Meta's 30-character limit (its 400 on Oct 31)", () => {
    expect(spotKeywords().filter((k) => k.length > 30)).toEqual([]);
    expect(spotKeywords([spot("a", "A Place Name That Is Over Thirty Chars", ["A Road Name That Is Over Thirty Chars"])])).toEqual([]);
  });

  it("counts a keyword's length in UTF-8 bytes, so a ñ counts twice", () => {
    const thirtyChars = "España Blvd cor. Maceda Street"; // 30 characters, 31 bytes
    expect(thirtyChars).toHaveLength(30);
    expect(spotKeywords([spot("a", thirtyChars, ["Espana Blvd cor. Maceda Street"])])).toEqual(["Espana Blvd cor. Maceda Street"]);
  });

  it("gives the list Meta took on Nov 1, in that order, and no more than its 97", () => {
    expect(TESTED_KEYWORDS).toHaveLength(97);
    expect(spotKeywords()).toEqual(TESTED_KEYWORDS);
  });

  it("names Santolan, Oyster Plaza and SM Sucat by short forms, since no road of theirs holds the landmark", () => {
    const keywords = spotKeywords();
    const firstRoad = keywords.indexOf("F. Ortigas Street");
    for (const form of ["EDSA Santolan", "Oyster Plaza", "SM Sucat"]) {
      expect(keywords.indexOf(form), form).toBeGreaterThan(-1);
      expect(keywords.indexOf(form), form).toBeLessThan(firstRoad);
    }
  });

  it("takes each short form from its own spot's aliases, so a transcript holding it finds the spot", () => {
    expect([...SHORT_FORMS.keys()]).toEqual(["edsa-santolan", "oyster-plaza", "sucat-sm"]);
    for (const [id, form] of SHORT_FORMS) {
      expect(SPOTS.find((s) => s.id === id)?.aliases, id).toContain(form);
      expect(Buffer.byteLength(form, "utf8"), id).toBeLessThanOrEqual(30);
      expect(findSpotIn(`baha ba sa ${form}?`)?.id, id).toBe(id);
    }
  });

  it("puts a long-named spot's short form after the names that fit and before the roads", () => {
    // The short form comes from SHORT_FORMS by the spot's id, so this spot borrows sucat-sm's id and real entry.
    const spots = [
      spot("a", "A Place", ["Main Road"]),
      spot("sucat-sm", "A Corner Whose Name Is Over Thirty Chars", ["Side St"], ["SM Sucat"]),
    ];
    expect(spotKeywords(spots)).toEqual(["A Place", "SM Sucat", "Main Road", "Side St"]);
  });

  it("gives the names that fit first, then each spot's roads, each once", () => {
    const spots = [
      spot("a", "A Place", ["Main Road", "Side St"]),
      spot("b", "A Corner Whose Name Is Over Thirty Chars", ["Side St", "Far Road"]),
      spot("c", "Far Road", ["Last Road"]),
    ];
    expect(spotKeywords(spots)).toEqual(["A Place", "Far Road", "Main Road", "Side St", "Last Road"]);
  });

  it("keeps at most 97, dropping roads before names", () => {
    const many = Array.from({ length: 100 }, (_, i) => spot(`s${i}`, `Place ${i}`, [`Road ${i}`]));
    const keywords = spotKeywords(many);
    expect(keywords).toHaveLength(97);
    expect(keywords.every((k) => k.startsWith("Place "))).toBe(true);
  });
});
