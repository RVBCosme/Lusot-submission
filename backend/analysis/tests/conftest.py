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
def no_real_spend_counter(monkeypatch, tmp_path):
    monkeypatch.setattr(laptop_spend, "operator_session", _no_lusot_profile)
    # Any other route to AWS (spend.operator_session, a ddb=None call, a subprocess)
    # finds no profile and only dummy keys, so it fails to sign in rather than reach
    # the real counter. moto's mocks accept the dummy keys.
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "no-aws-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "no-aws-creds"))
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(name, "testing")
