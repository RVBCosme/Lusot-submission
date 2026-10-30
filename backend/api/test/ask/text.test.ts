import { describe, expect, it } from "vitest";
import { normalize } from "../../src/ask/text";

describe("normalize", () => {
  it("folds case and accents", () => {
    expect(normalize("España")).toBe("espana");
    expect(normalize("PARAÑAQUE")).toBe("paranaque");
  });

  it("turns every run of punctuation and spaces into one space, and trims", () => {
    expect(normalize("  EDSA,,   Aurora!! ")).toBe("edsa aurora");
    expect(normalize("Biak-na-Bato St.")).toBe("biak na bato st");
    expect(normalize("10-wheeler")).toBe("10 wheeler");
    expect(normalize("")).toBe("");
    expect(normalize(" ?! ")).toBe("");
  });

  it("reads cor., corner, &, and and at between two words as cor", () => {
    for (const joined of ["España cor. Maceda", "España corner Maceda", "España & Maceda", "España and Maceda", "España at Maceda", "ESPAÑA COR MACEDA!!"]) {
      expect(normalize(joined), joined).toBe("espana cor maceda");
    }
    expect(normalize("Roxas Blvd at the US Embassy")).toBe("roxas blvd cor the us embassy");
  });

  it("leaves those words as they are at the start and the end", () => {
    expect(normalize("at España")).toBe("at espana");
    expect(normalize("España and")).toBe("espana and");
    expect(normalize("Corner")).toBe("corner");
  });

  it("gives the same text when run twice", () => {
    for (const s of ["España & Maceda!", "Roxas Blvd at the US Embassy", "at España corner", "N.S. Amoranto cor. Don Jose"]) {
      expect(normalize(normalize(s)), s).toBe(normalize(s));
    }
  });
});
