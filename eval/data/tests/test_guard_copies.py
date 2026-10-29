"""The guards set_b_masks copies from guards.py (C200, C222; the plan's PF-C13).

backend/analysis can't import eval/, so backend/analysis/probes/set_b_masks.py holds
verbatim copies of seven guards. This test reads both files as text and parses them
with ast, importing neither, so the copies can't drift from their source.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GUARDS = ROOT / "eval" / "data" / "guards.py"
SET_B_MASKS = ROOT / "backend" / "analysis" / "probes" / "set_b_masks.py"
COPIED = (
    "is_sealed_name",
    "refuse_sealed",
    "require_sealed",
    "console_ok",
    "require_console",
    "confirm",
    "quiet",
)


def definitions(path: Path) -> dict[str, str]:
    """The ast.dump of each function the file defines at its top level, by name. The
    dump leaves out line numbers and comments, and keeps docstrings."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: ast.dump(node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def test_set_b_masks_guards_match_eval_guards():
    source, copies = definitions(GUARDS), definitions(SET_B_MASKS)
    for name in COPIED:
        assert name in source, name
        assert copies.get(name) == source[name], name
