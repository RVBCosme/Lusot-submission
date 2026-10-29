"""Tests for hide_pin.py: one live or demo pin leaves the map, kept (MS9's N9).

Fakes only: ScriptCloud stands in for the stack, each AWS call held to botocore's own
model. Nothing reaches AWS.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_hide_pin.py
"""

import hide_pin
from fake_aws import FakeSession, ScriptCloud

LIVE, DEMO, PRIVATE = ("r_" + c * 32 for c in "abc")


def a_cloud():
    cloud = ScriptCloud()
    later = int(cloud.clock()) + 3600
    for report_id, mode in ((LIVE, "live"), (DEMO, "demo"), (PRIVATE, "private")):
        cloud.put(
            pk="GEO#wdw515",
            sk=f"2026-10-29T03:30:00Z#{report_id}",
            reportId=report_id,
            mode=mode,
            status="done",
            published=mode != "private",
            visibleUntil=later,
            expiresAt=later + 7 * 86400,
        )
    return cloud


def run(cloud, *argv):
    return hide_pin.main(list(argv), session=FakeSession(cloud), clock=cloud.clock)


def test_hide_pin_live_and_demo(capsys):
    cloud = a_cloud()
    now = str(int(cloud.clock()))
    for report_id, mode in ((LIVE, "live"), (DEMO, "demo")):
        assert run(cloud, report_id) == 0
        assert cloud.by_id(report_id)["visibleUntil"] == {"N": now}
        assert f"{report_id}: hidden ({mode}), visibleUntil set to now" in (
            capsys.readouterr().out
        )
    # Nothing is deleted.
    assert len(cloud.items) == 3
    assert cloud.called("dynamodb_delete_item") == []
    # A private report isn't a pin: refused, unchanged.
    before = cloud.by_id(PRIVATE)["visibleUntil"]
    assert run(cloud, PRIVATE) == 2
    assert cloud.by_id(PRIVATE)["visibleUntil"] == before
    assert len(cloud.called("dynamodb_update_item")) == 2
    # An unknown id is not found, and a malformed one is refused before any call.
    assert run(cloud, "r_" + "d" * 32) == 1
    cloud.calls.clear()
    assert run(cloud, "not-an-id") == 2
    assert cloud.calls == []
