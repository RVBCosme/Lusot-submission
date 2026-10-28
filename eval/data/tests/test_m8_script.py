"""Run the node tests of the M8 page's script, eval/data/m8_sheet.js (C208).

The script runs in Rene's browser, so its tests are node's own, in m8_sheet.test.mjs.
"""

import subprocess
from pathlib import Path

import synth

NODE_TESTS = Path(__file__).resolve().parent / "m8_sheet.test.mjs"


def test_m8_script_passes_its_node_tests():
    """node --test reads its arguments as glob(7) patterns, in which a backslash
    escapes the next character, so the path goes with forward slashes."""
    done = subprocess.run(
        ["node", "--test", NODE_TESTS.as_posix()],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=synth.TIMEOUT,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
