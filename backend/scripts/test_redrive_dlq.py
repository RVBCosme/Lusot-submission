"""Tests for redrive_dlq.py: dead letters under a day old go back once (C525, MS4-Q5).

Fakes only: ScriptCloud's two queues, each call held to botocore's own model. Nothing
reaches AWS.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_redrive_dlq.py
"""

import json

import redrive_dlq
from fake_aws import (
    DEAD_LETTER_QUEUE,
    UPLOAD_QUEUE,
    FakeSession,
    ScriptCloud,
    dead_letter,
    s3_record_body,
)

HOUR = 3600


def letters(now):
    """A dead letter of each class, all sent to the dead-letter queue just now."""
    return [
        dead_letter(s3_record_body("r_" + "1" * 32, now - 2 * HOUR), n=1, sent_s=now),
        dead_letter(s3_record_body("r_" + "2" * 32, now - 25 * HOUR), n=2, sent_s=now),
        dead_letter(
            s3_record_body("r_" + "3" * 32, now - HOUR), n=3, sent_s=now, redriven=True
        ),
        dead_letter("not json {", n=4, sent_s=now),
        # Sent just now, but its upload was 30 h ago: the event time decides (C525).
        dead_letter(s3_record_body("r_" + "5" * 32, now - 30 * HOUR), n=5, sent_s=now),
    ]


def run(cloud, *argv):
    return redrive_dlq.main(list(argv), session=FakeSession(cloud), clock=cloud.clock)


def test_classify():
    now = 1_800_000_000
    one, two, three, four, five = letters(now)
    assert redrive_dlq.classify(one, now) == "move"
    assert redrive_dlq.classify(two, now) == "too_old"
    assert redrive_dlq.classify(three, now) == "already_redriven"
    assert redrive_dlq.classify(four, now) == "unreadable"
    assert redrive_dlq.classify(five, now) == "too_old"
    for body in (
        "[]",
        "{}",
        '{"Records": []}',
        '{"Records": [{"eventTime": "x"}]}',
        '{"Records": [{"eventTime": "2026-10-29T00:00:00"}]}',
    ):
        assert redrive_dlq.classify(one | {"Body": body}, now) == "unreadable", body


def test_redrive_classes(capsys):
    cloud = ScriptCloud()
    now = cloud.clock()
    cloud.queues[DEAD_LETTER_QUEUE] += letters(now)
    moved_body = cloud.queues[DEAD_LETTER_QUEUE][0]["Body"]
    assert run(cloud) == 0
    # The 2 h old letter is moved once, marked, and every dead letter is deleted.
    [moved] = cloud.called("sqs_send_message")
    assert moved["QueueUrl"] == UPLOAD_QUEUE
    assert moved["MessageBody"] == moved_body
    assert moved["MessageAttributes"] == {
        "lusot-redriven": {"DataType": "String", "StringValue": "1"}
    }
    assert cloud.queues[DEAD_LETTER_QUEUE] == []
    assert len(cloud.called("sqs_delete_message")) == 5
    assert capsys.readouterr().out.splitlines() == [
        "moved 1, deleted 4: 1 already_redriven, 2 too_old, 1 unreadable"
    ]
    # It fails again and lands back in the dead-letter queue: deleted, not redriven.
    [again] = [m for m in cloud.queues[UPLOAD_QUEUE]]
    cloud.queues[DEAD_LETTER_QUEUE].append(again | {"_visible_at": 0.0})
    assert run(cloud) == 0
    assert len(cloud.called("sqs_send_message")) == 1
    assert cloud.queues[DEAD_LETTER_QUEUE] == []
    assert capsys.readouterr().out.splitlines() == [
        "moved 0, deleted 1: 1 already_redriven"
    ]
    # The receives ask for the message attributes, so the mark can be seen.
    for receive in cloud.called("sqs_receive_message"):
        assert receive["QueueUrl"] == DEAD_LETTER_QUEUE
        assert receive["MessageAttributeNames"] == ["All"]


def test_redrive_dry_run_changes_nothing(capsys):
    cloud = ScriptCloud()
    now = cloud.clock()
    cloud.queues[DEAD_LETTER_QUEUE] += letters(now)[:4]
    before = json.dumps(
        [
            {k: v for k, v in m.items() if k != "_visible_at"}
            for m in cloud.queues[DEAD_LETTER_QUEUE]
        ]
    )
    assert run(cloud, "--dry-run") == 0
    assert cloud.called("sqs_send_message") == []
    assert cloud.called("sqs_delete_message") == []
    after = json.dumps(
        [
            {k: v for k, v in m.items() if k != "_visible_at"}
            for m in cloud.queues[DEAD_LETTER_QUEUE]
        ]
    )
    assert after == before
    assert {r["VisibilityTimeout"] for r in cloud.called("sqs_receive_message")} == {60}
    out = capsys.readouterr().out
    assert "would move 1, would delete 3" in out
    assert out.splitlines() == [
        (
            "dry run: would move 1, would delete 3: 1 already_redriven, 1 too_old,"
            " 1 unreadable"
        )
    ]
