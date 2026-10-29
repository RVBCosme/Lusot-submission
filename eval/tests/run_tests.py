# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "pytest==9.1.1",
#     "scikit-learn==1.9.1",
# ]
# ///
"""Run the evaluation harness's tests (MS6).

From the repo root: uv run --locked --script eval/tests/run_tests.py [pytest arguments]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

if __name__ == "__main__":
    here = str(Path(__file__).resolve().parent)
    sys.exit(pytest.main([here, "-q", "-p", "no:cacheprovider", *sys.argv[1:]]))
