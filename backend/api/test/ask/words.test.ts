import { describe, expect, it } from "vitest";
import { hasCrossingWords, hasHeavyWords, hasHereWords, hasWalkingWords, statedMinutes } from "../../src/ask/words";

describe("the word lists", () => {
  it("crossing words", () => {
    for (const text of ["lusot ba sedan ko", "makakalusot ba", "ligtas bang tumawid", "is it safe to cross", "LIGTAS ba?"]) {
      expect(hasCrossingWords(text), text).toBe(true);
    }
    for (const text of ["Lusot, gaano kalalim?", "gaano kalalim sa España"]) {
      expect(hasCrossingWords(text), text).toBe(false);
    }
  });

  it("here words", () => {
    for (const text of ["may baha ba dito", "near me", "May baha ba rito?"]) {
      expect(hasHereWords(text), text).toBe(true);
    }
    expect(hasHereWords("Ditona St")).toBe(false);
  });

  it("heavy words", () => {
    for (const text of ["my truck", "10-wheeler", "Bus ba?"]) {
      expect(hasHeavyWords(text), text).toBe(true);
    }
    expect(hasHeavyWords("Fortuner")).toBe(false);
  });

  it("walking words", () => {
    for (const text of ["maglalakad ako", "I'm walking there", "on foot"]) {
      expect(hasWalkingWords(text), text).toBe(true);
    }
    expect(hasWalkingWords("sedan ko")).toBe(false);
  });
});

describe("statedMinutes", () => {
  it("reads the window a question states, in minutes", () => {
    expect(statedMinutes("in the last hour")).toBe(60);
    expect(statedMinutes("sa nakaraang 2 oras")).toBe(120);
    expect(statedMinutes("30 minuto")).toBe(30);
    expect(statedMinutes("Gaano kalalim sa España in the past 45 minutes?")).toBe(45);
    expect(statedMinutes("isang oras")).toBe(60);
    expect(statedMinutes("an hour ago")).toBe(60);
    expect(statedMinutes("3 hours")).toBe(180);
  });

  it("takes the largest when several are stated", () => {
    expect(statedMinutes("30 minutes or the last 2 hours")).toBe(120);
    expect(statedMinutes("90 minutes, not the last hour")).toBe(90);
  });

  it("gives undefined when no window is stated", () => {
    expect(statedMinutes("ngayon")).toBeUndefined();
    expect(statedMinutes("Gaano kalalim sa España?")).toBeUndefined();
    expect(statedMinutes("")).toBeUndefined();
  });
});
