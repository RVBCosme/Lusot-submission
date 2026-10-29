"""Tests for demo_pins.py: seeding, removing and checking demo pins (G1, C510, C523).

Fakes only: ScriptCloud stands in for the stack, each AWS call held to botocore's own
model, and tmp_path for lusot-data. Nothing reaches AWS or Meta.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_demo_pins.py
"""

import re
from datetime import datetime

import demo_pins
import guards
import httpx
import pytest
from fake_aws import (
    BAGUIO,
    LEVEL,
    NO_FLOOD,
    PUBLISH,
    REFUSED,
    FakeSession,
    ScriptCloud,
    consent_row,
    data_folder,
    formats_py,
    open_row,
    plain,
)

UNTIL = "2026-12-20"
END = int(datetime.fromisoformat("2026-12-20T23:59:59+08:00").timestamp())


@pytest.fixture
def data(tmp_path, monkeypatch):
    """lusot-data with five consented rows and one open-licensed row, M9-v4 approved."""
    base = data_folder(
        tmp_path / "data",
        open_rows=[open_row("OL001", 9)],
        consent_rows=[
            consent_row("S001", 1),
            consent_row("S002", 2, lat="", lon=""),
            consent_row("S003", 3, lat=BAGUIO[0], lon=BAGUIO[1]),
            consent_row("S004", 4, consent_version="M9-v2"),
            consent_row("S005", 5, taken_pht=""),
            consent_row("S006", 6, taken_pht="2026-10-21 08:05"),
        ],
    )
    monkeypatch.setenv("LUSOT_DATA_DIR", str(base))
    approved = formats_py(tmp_path / "formats.py", {"M9-v4"})
    monkeypatch.setattr(guards, "FORMATS_PY", approved)
    return base


def run(cloud, *argv):
    return demo_pins.main(
        list(argv),
        session=FakeSession(cloud),
        http=cloud.http(),
        clock=cloud.clock,
        sleep=cloud.clock.sleep,
    )


def lines(capsys):
    return capsys.readouterr().out.splitlines()


def demo_items(cloud):
    return [i for i in cloud.items.values() if i["mode"] == {"S": "demo"}]


def test_demo_ids_follow_c32_and_the_source():
    one = demo_pins.demo_report_id("S001")
    assert re.fullmatch(r"r_[0-9a-f]{32}", one)
    assert demo_pins.demo_report_id("S001") == one
    assert demo_pins.demo_report_id("S002") != one
    # Not a sample's id for the same source: the prefix differs.
    assert one[2:12] != demo_pins.demo_report_id("sample:S001")[2:12]


def test_until_is_the_end_of_a_manila_day(data, capsys):
    now = int(ScriptCloud().clock())  # 2026-10-29T12:00:00+08:00
    assert demo_pins.demo_times(UNTIL, now) == (END, END + 604_800)
    for bad in ("2026-12-21", "2026-10-28", "2026-12-32", "20 Dec"):
        with pytest.raises(ValueError):
            demo_pins.demo_times(bad, now)
    # Through main: 2026-12-21 is more than 53 days ahead, so nothing is written.
    cloud = ScriptCloud([LEVEL])
    assert run(cloud, "seed", "--until", "2026-12-21", "--ids", "S001") == 2
    assert cloud.calls == []
    assert lines(capsys)[-1].startswith("refused: --until")
    assert run(cloud, "seed", "--until", UNTIL, "--ids", "S001") == 0
    [item] = demo_items(cloud)
    assert (item["visibleUntil"], item["expiresAt"]) == (
        {"N": str(END)},
        {"N": str(END + 604_800)},
    )


def test_demo_seed_refuses_while_publish_is_set(data, capsys):
    for value in ("on", "maybe"):
        cloud = ScriptCloud([LEVEL])
        cloud.params[PUBLISH] = value
        assert run(cloud, "seed", "--until", UNTIL, "--ids", "S001") == 2
        assert cloud.called("dynamodb_put_item") == []
        assert cloud.called("s3_put_object") == []
        assert cloud.items == {} and cloud.objects == {}
        assert "publish" in lines(capsys)[-1]


def test_demo_seed_rules(data, capsys):
    cloud = ScriptCloud([LEVEL])
    ids = ["S001", "S002", "S003", "S004", "S005", "OL001"]
    assert run(cloud, "seed", "--until", UNTIL, "--ids", *ids) == 0
    [item] = demo_items(cloud)
    pin = demo_pins.demo_report_id("S001")
    item = {name: plain(value) for name, value in item.items()}
    # The real spot and capture time: 14:30 in Manila is 06:30 UTC.
    assert item["capturedAt"] == "2026-10-20T06:30:00Z"
    assert (item["lat"], item["lng"]) == (14.6095, 120.9894)
    assert item["pk"] == "GEO#wdw515"
    assert item["sk"] == f"2026-10-20T06:30:00Z#{pin}"
    assert item["reportId"] == pin
    assert item["receivedAt"] == "2026-10-29T04:00:00Z"
    assert (item["mode"], item["flags"], item["demoSource"]) == ("demo", 0, "S001")
    assert item["credit"].endswith(guards.CHANGE_NOTE)
    assert item["place"] == "Espana Boulevard, Sampaloc, Manila"
    assert "event" not in item  # MS2's log names none
    # It went through the pipeline: a level, published, with its three demo/ keys.
    assert (item["status"], item["published"]) == ("done", True)
    assert cloud.keys("demo/") == sorted(demo_pins.demo_keys(pin))
    # The item went in pending, before its photo, which is the app's JPEG.
    [put] = cloud.called("dynamodb_put_item")
    assert put["Item"]["status"] == {"S": "pending"}
    [photo_put] = cloud.called("s3_put_object")
    assert photo_put["Key"] == f"raw/{pin}.jpg"
    assert photo_put["ContentType"] == "image/jpeg"
    assert photo_put["Body"][:3] == b"\xff\xd8\xff"
    out = lines(capsys)
    assert out == [
        f"{pin}: pinned, done/level",
        (
            "refused: 1 no_capture_time, 2 no_spot, 1 not_on_allow_list,"
            " 1 outside_metro_manila"
        ),
        "seed: 6 given, 1 pinned",
    ]
    for coordinate in ("14.6", "120.9", "16.4", "120.5"):
        assert all(coordinate not in line for line in out)


def test_demo_seed_pins_only_a_level(data, capsys):
    cloud = ScriptCloud([REFUSED, NO_FLOOD])
    pins = [demo_pins.demo_report_id(i) for i in ("S001", "S006")]
    # An earlier attempt left keys behind, so their deletion shows.
    for pin in pins:
        for key in demo_pins.demo_keys(pin):
            cloud.objects[key] = b"left"
    assert run(cloud, "seed", "--until", UNTIL, "--ids", "S001", "S006") == 1
    assert demo_items(cloud) == []
    assert cloud.keys("demo/") == []
    out = lines(capsys)
    assert out[-2:] == [
        "not_level: 1 done/no_flood_seen, 1 refused/no_usable_reference",
        "seed: 2 given, 0 pinned",
    ]
    assert f"{pins[0]}: not pinned, refused/no_usable_reference" in out


def test_a_level_written_while_publish_was_set_is_no_pin(data, capsys):
    cloud = ScriptCloud([LEVEL])

    def flip_then_put(**params):
        cloud.params[PUBLISH] = "on"
        return original(**params)

    original = cloud.s3_put_object
    cloud.s3_put_object = flip_then_put
    assert run(cloud, "seed", "--until", UNTIL, "--ids", "S001") == 1
    assert demo_items(cloud) == [] and cloud.keys("demo/") == []
    assert "not_level: 1 done/level unpublished" in lines(capsys)


def test_a_reseed_replaces_its_pin(data, capsys):
    cloud = ScriptCloud([LEVEL, LEVEL])
    pin = demo_pins.demo_report_id("S001")
    assert run(cloud, "seed", "--until", UNTIL, "--ids", "S001") == 0
    # An interrupted run under the same id left another item and a stray key.
    cloud.put(
        pk="GEO#wdw515",
        sk=f"2026-10-19T00:00:00Z#{pin}",
        reportId=pin,
        mode="demo",
        status="processing",
    )
    cloud.calls.clear()
    assert run(cloud, "seed", "--until", UNTIL, "--ids", "S001") == 0
    [item] = demo_items(cloud)
    assert item["reportId"] == {"S": pin} and item["status"] == {"S": "done"}
    # The old items and the three keys go first, then the new item and photo.
    names = [name for name, _ in cloud.calls]
    first_put = names.index("dynamodb_put_item")
    deleted = [p["Key"]["sk"]["S"] for p in cloud.called("dynamodb_delete_item")]
    assert sorted(deleted) == sorted(
        [f"2026-10-20T06:30:00Z#{pin}", f"2026-10-19T00:00:00Z#{pin}"]
    )
    assert names[:first_put].count("dynamodb_delete_item") == 2
    removed = [p["Key"] for p in cloud.called("s3_delete_object")]
    assert sorted(removed) == sorted(demo_pins.demo_keys(pin))
    assert names[:first_put].count("s3_delete_object") == 3


def test_remove_deletes_whatever_is_left(data, capsys):
    cloud = ScriptCloud([LEVEL, LEVEL])
    assert run(cloud, "seed", "--until", UNTIL, "--ids", "S001", "S006") == 0
    one, two = (demo_pins.demo_report_id(i) for i in ("S001", "S006"))
    cloud.put(
        pk="GEO#wdw515",
        sk="2026-10-29T03:00:00Z#r_live",
        reportId="r_live",
        mode="live",
        status="done",
    )
    cloud.objects["blurred/r_live.jpg"] = b"live"
    # remove <id>: one pin and its three keys only.
    assert run(cloud, "remove", one) == 0
    assert [i["reportId"]["S"] for i in demo_items(cloud)] == [two]
    assert cloud.keys("demo/") == sorted(demo_pins.demo_keys(two))
    # An interrupted remove deleted the item and left its photos: remove takes them.
    for key in [k for k, i in cloud.items.items() if i["mode"] == {"S": "demo"}]:
        del cloud.items[key]
    cloud.objects["demo/blurred/r_stray.jpg"] = b"stray"
    assert run(cloud, "remove") == 0
    assert demo_items(cloud) == [] and cloud.keys("demo/") == []
    assert cloud.by_id("r_live") is not None
    assert cloud.keys("blurred/") == ["blurred/r_live.jpg"]
    assert lines(capsys)[-1] == "removed 0 demo items and 4 demo/ objects"


def test_remove_refuses_a_pin_that_isnt_demo(data, capsys):
    cloud = ScriptCloud()
    live = "r_" + "a" * 32
    cloud.put(pk="GEO#wdw515", sk=f"x#{live}", reportId=live, mode="live")
    assert run(cloud, "remove", live) == 2
    assert cloud.by_id(live) is not None
    assert cloud.called("s3_delete_object") == []
    assert run(cloud, "remove", "not-an-id") == 2


def test_check_prints_no_location(data, capsys):
    cloud = ScriptCloud([LEVEL])
    pin = demo_pins.demo_report_id("S001")
    assert run(cloud, "seed", "--until", UNTIL, "--ids", "S001") == 0
    capsys.readouterr()
    assert run(cloud, "check", pin) == 0
    assert lines(capsys) == [
        f"{pin}: mode demo",
        "nearby at its rounded spot: yes",
        "on the map: yes",
        "links: photo 200, overlay 200, layers 200",
        "visibleUntil past capture plus 3 h: yes",
        "flag refused: yes (HTTP 404)",
        "check: passed",
    ]
    # The nearby query used the pin's spot rounded to 4 places (C514).
    [nearby] = [
        r
        for r in cloud.requests
        if r[1].startswith("https://api.test.invalid/reports?")
    ]
    assert "lat=14.6095" in nearby[1] and "lng=120.9894" in nearby[1]
    # A missing layers file fails the check.
    del cloud.objects[f"demo/overlay/{pin}.json"]
    assert run(cloud, "check", pin) == 1
    assert "links: photo 200, overlay 200, layers 403" in lines(capsys)


def test_check_refuses_a_pin_that_isnt_demo_before_any_request(data, capsys):
    # Review, Minor 1: a live id typed by mistake is never flagged.
    cloud = ScriptCloud()
    live, eval_id = "r_" + "a" * 32, "r_" + "b" * 32
    cloud.put(
        pk="GEO#wdw515",
        sk=f"x#{live}",
        reportId=live,
        mode="live",
        status="pending",
        published=True,
        lat=14.6095,
        lng=120.9894,
        capturedAt="2026-10-29T03:30:00Z",
        visibleUntil=END,
        expiresAt=END,
    )
    cloud.put(pk="EVAL", sk=f"x#{eval_id}", reportId=eval_id, mode="eval")
    for report_id in (live, eval_id):
        assert run(cloud, "check", report_id) == 2
    assert cloud.requests == []
    assert lines(capsys)[-1] == f"refused: {eval_id} isn't a demo pin"


def test_check_needs_exactly_404_from_the_flag(data, capsys):
    cloud = ScriptCloud([LEVEL])
    pin = demo_pins.demo_report_id("S001")
    assert run(cloud, "seed", "--until", UNTIL, "--ids", "S001") == 0
    capsys.readouterr()
    cloud.flag = lambda report_id, request: httpx.Response(429, json={})
    assert run(cloud, "check", pin) == 1
    assert "flag refused: no (HTTP 429)" in lines(capsys)


def test_check_of_a_demo_item_without_a_spot_doesnt_raise(data, capsys):
    cloud = ScriptCloud()
    pin = "r_" + "c" * 32
    cloud.put(
        pk="GEO#wdw515",
        sk=f"2026-10-20T06:30:00Z#{pin}",
        reportId=pin,
        mode="demo",
        status="refused",
        refusalReason="no_usable_reference",
        capturedAt="2026-10-20T06:30:00Z",
        visibleUntil=END,
        expiresAt=END + 604_800,
    )
    assert run(cloud, "check", pin) == 1
    out = lines(capsys)
    assert "nearby at its rounded spot: no" in out and out[-1] == "check: failed"
    assert not [r for r in cloud.requests if "/reports?" in r[1]]


def test_a_photo_named_as_sealed_exits_2_not_unreadable(tmp_path, monkeypatch, capsys):
    # Review, Minor 2: the refusal is never counted as unreadable.
    row = consent_row("S009", file="sealed::$INDEX_ALLOCATION")
    row.pop("_photo")  # nothing is written under this name
    base = data_folder(tmp_path / "data", consent_rows=[row])
    monkeypatch.setenv("LUSOT_DATA_DIR", str(base))
    approved = formats_py(tmp_path / "formats.py", {"M9-v4"})
    monkeypatch.setattr(guards, "FORMATS_PY", approved)
    cloud = ScriptCloud([LEVEL])
    assert run(cloud, "seed", "--until", UNTIL, "--ids", "S009") == 2
    assert cloud.called("dynamodb_put_item") == cloud.called("s3_put_object") == []
    assert "unreadable" not in capsys.readouterr().out


def test_a_seed_that_times_out_is_left_for_remove(data, capsys):
    # Review, Minor 3: the handler may still be writing, so nothing is cleared.
    cloud = ScriptCloud([LEVEL], processing_s=200)
    pin = demo_pins.demo_report_id("S001")
    assert run(cloud, "seed", "--until", UNTIL, "--ids", "S001") == 1
    assert cloud.called("dynamodb_delete_item") == []
    assert [i["reportId"]["S"] for i in demo_items(cloud)] == [pin]
    assert lines(capsys) == [
        (
            f"{pin}: not pinned, still processing after 180 s; run"
            f" `demo_pins.py remove {pin}` once it has ended"
        ),
        "timed_out: 1",
        "seed: 1 given, 0 pinned",
    ]
