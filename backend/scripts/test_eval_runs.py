"""Tests for eval_runs.py: the recovery checks' cloud runs (MS4 spec §4.8, C513).

Fakes only: ScriptCloud stands in for the stack and its analysis, each AWS call held
to botocore's own model, and tmp_path for C87's Commons folder. Nothing reaches AWS or
Meta.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_eval_runs.py
"""

import re

import cv2
import eval_runs
import numpy as np
import pytest
import smoke_upload
from fake_aws import (
    LEVEL,
    MODEL_CALLS,
    NOON,
    FakeSession,
    ScriptCloud,
    commons_folder,
)

NAMES = [f"Flood_in_Manila_{n:02d}.jpg" for n in range(8)]
REPORT_ID = re.compile(r"r_[0-9a-f]{32}")


@pytest.fixture
def folder(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("LUSOT_DATA_DIR", str(data))
    return commons_folder(data, NAMES)


def run(cloud, *argv):
    return eval_runs.main(
        list(argv),
        session=FakeSession(cloud),
        http=cloud.http(),
        clock=cloud.clock,
        sleep=cloud.clock.sleep,
    )


def test_eval_items_use_the_eval_key(folder):
    now = int(NOON)  # 2026-10-29T04:00:00Z
    item = eval_runs.eval_item("r_" + "0" * 32, now)
    assert item == {
        "pk": {"S": "EVAL"},
        "sk": {"S": f"2026-10-29T04:00:00Z#r_{'0' * 32}"},
        "reportId": {"S": "r_" + "0" * 32},
        "mode": {"S": "eval"},
        "status": {"S": "pending"},
        "capturedAt": {"S": "2026-10-29T04:00:00Z"},
        "receivedAt": {"S": "2026-10-29T04:00:00Z"},
        "expiresAt": {"N": str(now + 604_800)},
    }
    assert eval_runs.eval_item("r_" + "0" * 32, now, seed=True)["seed"] == {
        "BOOL": True
    }
    ids = {eval_runs.new_report_id() for _ in range(5)}
    assert len(ids) == 5 and all(REPORT_ID.fullmatch(i) for i in ids)
    # dead-holder: written already processing, under a live lease with no worker.
    cloud = ScriptCloud([LEVEL])
    assert run(cloud, "dead-holder", "--position", "0") == 0
    [put] = cloud.called("dynamodb_put_item")
    item = put["Item"]
    assert REPORT_ID.fullmatch(item["reportId"]["S"])
    assert (item["pk"], item["mode"], item["status"]) == (
        {"S": "EVAL"},
        {"S": "eval"},
        {"S": "processing"},
    )
    assert item["claimedAt"] == {"N": str(now)}
    assert re.fullmatch(r"[0-9a-f]{32}", item["claimToken"]["S"])


def width(jpeg):
    return cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR).shape[1]


def test_eval_runs_take_the_photo_at_its_position(folder, capsys):
    order = smoke_upload.seeded_photo_order(folder)
    cloud = ScriptCloud([LEVEL])
    assert run(cloud, "duplicate", "--position", "2") == 0
    [photo_put] = cloud.called("s3_put_object")
    assert width(photo_put["Body"]) == 100 + NAMES.index(order[2].name)
    # A photo `credited` skips is never sent: no write, no upload, no AWS call.
    commons_folder(folder.parents[1], NAMES, credited=set(NAMES) - {order[3].name})
    cloud = ScriptCloud([LEVEL])
    assert run(cloud, "race", "--position", "3") == 1
    assert cloud.calls == []
    assert run(cloud, "race", "--position", "99") == 1
    assert cloud.calls == []


@pytest.mark.parametrize(
    ("case", "logged", "slept"),
    [
        ("duplicate", ["done/level", "already_finished"], 0),
        ("race", ["done/level", "already_finished"], 0),
        ("dead-holder", ["lease_held", "done/level"], 1080),
    ],
)
def test_the_cases_end_as_expected(folder, capsys, case, logged, slept):
    cloud = ScriptCloud([LEVEL])
    assert run(cloud, case, "--position", "0") == 0
    out = capsys.readouterr().out.splitlines()
    [put] = cloud.called("dynamodb_put_item")
    report_id = put["Item"]["reportId"]["S"]
    took = "1080.0" if slept else "0.0"
    log = ", ".join(f"1 {outcome}" for outcome in sorted(logged))
    assert out == [
        f"{report_id}: {case}, done/level in {took} s, 8 Meta calls; log: {log}",
        "EVAL OK",
    ]
    assert sum(cloud.clock.slept) >= slept
    # Only the duplicate cases send a second notification.
    sent = cloud.called("sqs_send_message")
    assert len(sent) == (0 if case == "dead-holder" else 1)


def test_paused_expects_the_model_calls_switch_on(folder, capsys):
    cloud = ScriptCloud()
    assert run(cloud, "paused", "--position", "0") == 2
    assert cloud.called("dynamodb_put_item") == []
    cloud.params[MODEL_CALLS] = "on"
    assert run(cloud, "paused", "--position", "0") == 0
    out = capsys.readouterr().out.splitlines()
    assert re.fullmatch(
        r"r_[0-9a-f]{32}: paused, failed/model_calls_paused in 0\.0 s, 0 Meta calls;"
        r" log: 1 failed/model_calls_paused",
        out[-2],
    )
    assert out[-1] == "EVAL OK"


def test_a_second_paid_line_fails_the_duplicate_case(folder, capsys):
    cloud = ScriptCloud([LEVEL, LEVEL])
    original = cloud.deliver

    def pays_twice(key):
        item = cloud.by_id(key.removeprefix("raw/").removesuffix(".jpg"))
        if item is not None and item["status"]["S"] == "done":
            # As if the claim never held: the duplicate finds a photo and pays again.
            item["status"] = {"S": "pending"}
            cloud.objects[key] = b"\xff\xd8\xff again"
        original(key)

    cloud.deliver = pays_twice
    assert run(cloud, "duplicate", "--position", "0") == 1
    assert capsys.readouterr().out.splitlines()[-1] == (
        "EVAL FAILED: 2 log lines with Meta calls, expected at most 1"
    )
