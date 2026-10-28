"""Put eval/ first on sys.path, so the tests import scoring and run_eval as the harness does."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
