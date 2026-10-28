"""Run the node tests of the M8 page's script, eval/data/m8_sheet.js (C208).

The script runs in Rene's browser, so its tests are node's own, in m8_sheet.test.mjs.
"""

import json
import subprocess
from pathlib import Path

import formats
import synth

TESTS = Path(__file__).resolve().parent
NODE_TESTS = TESTS / "m8_sheet.test.mjs"
SCRIPT = TESTS.parent / "m8_sheet.js"

# Prints the script's own qualities and subset tags as JSON. The script loads into a vm
# context without a document, as the node tests load it.
PRINT_MARKS = """
const { readFileSync } = require("node:fs");
const vm = require("node:vm");
const context = vm.createContext({});
vm.runInContext(readFileSync(process.argv[1], "utf8"), context);
console.log(JSON.stringify([context.M8.QUALITIES, context.M8.SUBSETS]));
"""


def run_node(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=synth.TIMEOUT,
        check=False,
    )


def test_m8_script_passes_its_node_tests():
    """node --test reads its arguments as glob(7) patterns, in which a backslash
    escapes the next character, so the path goes with forward slashes."""
    done = run_node("--test", NODE_TESTS.as_posix())
    assert done.returncode == 0, done.stdout + done.stderr


def test_m8_script_marks_match_formats():
    """The page's data carries only Table 5's lists, so the script holds the qualities
    and subset tags itself, and they must be formats.py's, in order: the intake checks
    the export against those."""
    done = run_node("-e", PRINT_MARKS, str(SCRIPT))
    assert done.returncode == 0, done.stdout + done.stderr
    qualities, subsets = json.loads(done.stdout)
    assert qualities == list(formats.QUALITIES)
    assert subsets == list(formats.SUBSET_TAGS)
