"""Load backend/analysis's spend.py by path, once, for the scripts in this folder.

seed_spend.py and set_spend_stop.py use it, and Task 9's smoke run and Window 3's
laptop runner (R126) will too, so the Lambda and the laptop count Meta spend with one
definition. spend.py needs only boto3, so a script's own PEP 723 environment loads it.
A script run as `uv run backend/scripts/<name>.py` finds this module because Python
puts the script's own folder on sys.path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SPEND_PY = Path(__file__).resolve().parents[1] / "analysis/src/lusot_analysis/spend.py"
MODULE_NAME = "lusot_spend"  # its one name in sys.modules


def load_spend() -> ModuleType:
    """spend.py as a module: loaded on the first call, the same object after it."""
    loaded = sys.modules.get(MODULE_NAME)
    if loaded is not None:
        return loaded
    spec = importlib.util.spec_from_file_location(MODULE_NAME, SPEND_PY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[MODULE_NAME]  # so a failed load isn't handed out later
        raise
    return module
