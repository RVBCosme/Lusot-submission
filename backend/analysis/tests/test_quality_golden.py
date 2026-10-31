"""The phone's quality check stays the server's (MS5 Task 10, C604).

probes/make_quality_golden.py writes app/src/lib/quality.golden.json from quality_scores and
the live cutoffs; the app's own test reads that file. This checks the committed file is what
the generator writes now, so a retuned cutoff or a changed score fails here first.
"""

import importlib.util
from pathlib import Path

PROBE = Path(__file__).resolve().parents[1] / "probes" / "make_quality_golden.py"


def load_probe():
    spec = importlib.util.spec_from_file_location("make_quality_golden", PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_committed_golden_file_is_what_the_server_writes_now():
    probe = load_probe()
    assert probe.OUT.read_text(encoding="utf-8") == probe.render(probe.build())


def test_the_golden_file_holds_the_live_cutoffs():
    from lusot_analysis.tuning import TUNING

    golden = load_probe().build()
    assert golden["brightness_min"] == TUNING.brightness_min
    assert golden["sharpness_min"] == TUNING.sharpness_min
