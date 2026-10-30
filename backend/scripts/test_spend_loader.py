"""Tests for spend_loader.py: the scripts share one copy of spend.py (Minor 5).

check:py runs this file with the scripts' dependencies.
"""

import sys

import seed_spend
import set_spend_stop


def test_both_scripts_share_one_spend_module():
    assert seed_spend.spend is set_spend_stop.spend
    from spend_loader import load_spend

    # Loaded once, under one name, and handed out again after that.
    assert load_spend() is seed_spend.spend
    assert load_spend() is load_spend()
    assert sys.modules["lusot_spend"] is seed_spend.spend
    # It is backend/analysis's spend.py.
    assert seed_spend.spend.SPEND_PK == "spend#meta"
    assert seed_spend.spend.__file__.endswith("spend.py")
