// Between two words, these all read as one joiner, so "España & Maceda" and "España cor. Maceda" match.
const JOINERS = new Set(["cor", "corner", "and", "at"]);

// NFD with combining marks removed ("ñ" becomes "n"), lowercase, every run of punctuation and spaces one space,
// a joiner between two words written "cor", trimmed. Running it twice gives the same text.
export function normalize(s: string): string {
  const words = s
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .split(" ");
  return words.map((word, i) => (i > 0 && i < words.length - 1 && JOINERS.has(word) ? "cor" : word)).join(" ");
}
