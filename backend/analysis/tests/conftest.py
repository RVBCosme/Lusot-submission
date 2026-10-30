"""A guard every test shares: no test reaches the real spend counter (C527).

The laptop tools read and add to MS4's counter with the lusot profile, through
laptop_spend.operator_session. On Rene's laptop that profile is signed in, so a test
that forgot its fake counter would read the real counter and then add a fake run's
cost to it. Every test gets a stand-in that fails instead; a test of the helper
gives check_before_paying a moto session of its own.
"""

import pytest

from lusot_analysis import laptop_spend


def _no_lusot_profile():
    raise AssertionError("a test reached the lusot profile's real AWS")


@pytest.fixture(autouse=True)
def no_real_spend_counter(monkeypatch):
    monkeypatch.setattr(laptop_spend, "operator_session", _no_lusot_profile)
