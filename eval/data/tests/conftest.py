"""Put eval/data and this folder first on sys.path, for the tools and synth."""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path[:0] = [str(TESTS.parent), str(TESTS)]
