"""Read eval/rules.md, so the drift tests check the code against the file (C408)."""

from __future__ import annotations

import re
from pathlib import Path

RULES_MD = Path(__file__).resolve().parents[1] / "rules.md"


def _lines() -> list[str]:
    return RULES_MD.read_text(encoding="utf-8").splitlines()


def section(number: int) -> str:
    """The text of rules.md's `## N.` section, after its heading and up to the next."""
    lines = _lines()
    starts = [i for i, line in enumerate(lines) if line.startswith(f"## {number}. ")]
    assert len(starts) == 1, f"rules.md has no single section {number}"
    body = []
    for line in lines[starts[0] + 1 :]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


def tables(text: str) -> list[list[list[str]]]:
    """Each Markdown table in `text`, as rows of stripped cells, without the header
    and separator rows."""
    found: list[list[list[str]]] = []
    block: list[str] = []
    for line in [*text.splitlines(), ""]:
        if line.strip().startswith("|"):
            block.append(line.strip())
        elif block:
            found.append([_cells(row) for row in block[2:]])
            block = []
    return found


def _cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip("|").split("|")]


def version() -> str:
    """The first `vX.Y` on rules.md's status line, without the `v`."""
    for line in _lines():
        if line.startswith("- **Status:**"):
            for token in line.split():
                found = re.fullmatch(r"v([0-9]+\.[0-9]+)", token.rstrip(",.;:"))
                if found:
                    return found[1]
    raise AssertionError("rules.md has no version on its status line")
