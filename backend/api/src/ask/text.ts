// Between two words, these all read as one joiner, so "España & Maceda" and "España cor. Maceda" match.
const JOINERS = new Set(["cor", "corner", "and", "at", "&"]);

// NFD with combining marks removed ("ñ" becomes "n"), lowercase, every run of punctuation and spaces one space,
// a joiner between two words written "cor", trimmed. An "&" at the start or the end is punctuation and goes.
// Running it twice gives the same text.
export function normalize(s: string): string {
  const tokens =
    s
      .normalize("NFD")
      .replace(/\p{M}/gu, "")
      .toLowerCase()
      .match(/[\p{L}\p{N}]+|&/gu) ?? [];
  while (tokens[0] === "&") tokens.shift();
  while (tokens[tokens.length - 1] === "&") tokens.pop();
  return tokens.map((token, i) => (i > 0 && i < tokens.length - 1 && JOINERS.has(token) ? "cor" : token)).join(" ");
}
