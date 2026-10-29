"""Put eval/set_b, eval/data and eval/data/tests first on sys.path, in that order, so
Set B's tests import its tools, the shared helpers and synth."""

import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(EVAL / "set_b"), str(EVAL / "data"), str(EVAL / "data" / "tests")]
