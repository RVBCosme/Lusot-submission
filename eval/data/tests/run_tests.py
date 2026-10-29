# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["pytest==9.1.1", "numpy==2.5.4", "opencv-python-headless==4.14.0.94", "py7zr==1.1.4"]
# ///
"""Run the tests of MS2's data tools, in eval/data/tests and eval/set_b/tests.

Usage, from the repo root:
    uv run --locked --script eval/data/tests/run_tests.py [pytest arguments]
Any arguments go on to pytest, and the run exits with pytest's code. The cache plugin is
off, so a run writes no .pytest_cache. pytest's default import mode loads each test file
as a top-level module, so test file names must be unique across both folders.
"""

import sys
from pathlib import Path

import pytest

DATA_TESTS = Path(__file__).resolve().parent
SET_B_TESTS = DATA_TESTS.parents[1] / "set_b" / "tests"

if __name__ == "__main__":
    args = [str(DATA_TESTS), str(SET_B_TESTS), "-q", "-p", "no:cacheprovider"]
    sys.exit(pytest.main([*args, *sys.argv[1:]]))
