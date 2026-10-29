"""Tests for samples.py: seeding, removing and checking samples (C512, S5, MS4-Q8).

Fakes only: ScriptCloud stands in for the stack, each AWS call held to botocore's own
model, and tmp_path for lusot-data. Nothing reaches AWS or Meta.

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_samples.py
"""

import csv
import json
import re

import guards
import httpx
import pytest
import samples
from fake_aws import (
    LEVEL,
    NO_COPY,
    NO_FLOOD,
    PHOTO_MISSING,
    REFUSED,
    FakeSession,
    ScriptCloud,
    consent_row,
    data_folder,
    formats_py,
    open_row,
)

DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


@pytest.fixture
def data(tmp_path, monkeypatch):
    """lusot-data with four open-licensed rows and two consented ones, M9-v4 approved."""
    base = data_folder(
        tmp_path / "data",
        open_rows=[
            open_row("OL001", 1),
            open_row("OL002", 2, event=""),
            open_row("OL003", 3),
            open_row("OL009", 9, date_taken="undated"),
        ],
        consent_rows=[consent_row("S001", 4), consent_row("S002", 5)],
    )
    monkeypatch.setenv("LUSOT_DATA_DIR", str(base))
    approved = formats_py(tmp_path / "formats.py", {"M9-v4"})
    monkeypatch.setattr(guards, "FORMATS_PY", approved)
    return base


def run(cloud, *argv):
    return samples.main(
        list(argv),
        session=FakeSession(cloud),
        http=cloud.http(),
        clock=cloud.clock,
        sleep=cloud.clock.sleep,
    )


def lines(capsys):
    return capsys.readouterr().out.splitlines()


def test_sample_ids_are_stable():
    one = samples.sample_id("OL001")
    assert re.fullmatch(r"s[0-9a-f]{10}", one)
    assert samples.sample_id("OL001") == one != samples.sample_id("OL002")


def test_samples_qualify_on_a_level_or_no_flood_seen(data, capsys):
    cloud = ScriptCloud([LEVEL, NO_FLOOD, REFUSED, PHOTO_MISSING])
    assert run(cloud, "seed", "--ids", "OL001", "OL002", "OL003", "S001") == 0
    kept = [samples.sample_id(i) for i in ("OL001", "OL002")]
    assert cloud.keys("samples/") == sorted(
        [*(f"samples/{s}.jpg" for s in kept), "samples/manifest.json"]
    )
    # Each copy is the seed's stored, blurred copy, untagged; the refused seed's
    # stored copy is never copied, and the original is never put under samples/.
    seeds = [p["Item"] for p in cloud.called("dynamodb_put_item")]
    copies = cloud.called("s3_copy_object")
    assert [c["CopySource"] for c in copies] == [
        f"lusot-uploads-test/blurred/{seeds[n]['reportId']['S']}.jpg" for n in (0, 1)
    ]
    assert [c["Key"] for c in copies] == [f"samples/{s}.jpg" for s in kept]
    assert {c["TaggingDirective"] for c in copies} == {"REPLACE"}
    refused_copy = f"blurred/{seeds[2]['reportId']['S']}.jpg"
    assert refused_copy in cloud.objects
    put_under_samples = [
        p["Key"]
        for p in cloud.called("s3_put_object")
        if p["Key"].startswith("samples/")
    ]
    assert put_under_samples == ["samples/manifest.json"] * 2
    # T11: each seed item, as the validated put_item received it, is an eval seed.
    for seed in seeds:
        assert seed["seed"] == {"BOOL": True}
        assert (seed["pk"], seed["mode"], seed["status"]) == (
            {"S": "EVAL"},
            {"S": "eval"},
            {"S": "pending"},
        )
    entries = cloud.manifest()["samples"]
    assert [e["sampleId"] for e in entries] == kept
    out = lines(capsys)
    assert out[-2:] == [
        (
            "skipped: refused 1 (1 no_usable_reference), failed 1 (1 photo_missing),"
            " no_copy 0"
        ),
        "seed: 4 candidates given, 2 qualified",
    ]


def test_a_seed_without_a_copy_is_skipped(data, capsys):
    cloud = ScriptCloud([NO_COPY])
    assert run(cloud, "seed", "--ids", "OL001") == 1
    assert cloud.keys("samples/") == []
    assert lines(capsys)[-2:] == [
        "skipped: refused 0, failed 0, no_copy 1",
        "seed: 1 candidates given, 0 qualified",
    ]


def test_manifest_entries(data, capsys, tmp_path):
    cloud = ScriptCloud([LEVEL, NO_FLOOD])
    # An entry from an earlier run stays.
    earlier = {
        "sampleId": "s0123456789",
        "credit": "c",
        "license": "CC0",
        "savedAt": "2026-10-28",
        "status": "done",
        "noFloodSeen": True,
    }
    cloud.objects["samples/manifest.json"] = json.dumps(
        {"version": 1, "samples": [earlier]}
    ).encode()
    assert run(cloud, "seed", "--ids", "OL001", "S001", "OL009") == 0
    manifest = cloud.manifest()
    assert manifest["version"] == 1
    old, level, dry = manifest["samples"]
    assert old == earlier
    assert set(level) == {
        "sampleId",
        "credit",
        "license",
        "place",
        "date",
        "event",
        "savedAt",
        "status",
        "noFloodSeen",
        "level",
        "landmark",
        "passability",
        "levelIsFloor",
    }
    assert level["sampleId"] == samples.sample_id("OL001")
    assert level["credit"].endswith(guards.CHANGE_NOTE)
    assert (level["license"], level["date"], level["event"]) == (
        "CC BY 2.0",
        "2023-09-23",
        "Habagat 2023",
    )
    assert (level["status"], level["noFloodSeen"], level["level"]) == (
        "done",
        False,
        "knee",
    )
    assert (level["landmark"], level["passability"], level["levelIsFloor"]) == (
        "rim_three_quarters",
        "NPLV",
        False,
    )
    # A consented photo: no event, and the exact licence value MS5 keeps.
    assert set(dry) == {
        "sampleId",
        "credit",
        "license",
        "place",
        "date",
        "savedAt",
        "status",
        "noFloodSeen",
    }
    assert (dry["license"], dry["date"], dry["noFloodSeen"]) == (
        "used with permission",
        "2026-10-20",
        True,
    )
    assert dry["place"] == "Espana Boulevard, Sampaloc, Manila"
    for entry in (level, dry):
        assert DAY.fullmatch(entry["date"]) and entry["savedAt"] == "2026-10-29"
    # The source notes go to lusot-data only, never to the bucket or the output.
    assert all(b"NOTE-SENTINEL" not in body for body in cloud.objects.values())
    assert all(b"commons.test.invalid" not in body for body in cloud.objects.values())
    with (data / "samples" / "sample_sources.csv").open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows == [
        {
            "sampleId": samples.sample_id("OL001"),
            "source_id": "OL001",
            "note": "https://commons.test.invalid/OL001",
        },
        {
            "sampleId": samples.sample_id("S001"),
            "source_id": "S001",
            "note": "NOTE-SENTINEL S001: from a donor's message",
        },
    ]
    out = lines(capsys)
    assert all("NOTE-SENTINEL" not in line for line in out)
    assert "refused before any run: 1 no_date" in out


def test_remove_one_sample(data, capsys):
    cloud = ScriptCloud([LEVEL, NO_FLOOD])
    assert run(cloud, "seed", "--ids", "OL001", "OL002") == 0
    one, two = samples.sample_id("OL001"), samples.sample_id("OL002")
    assert noted(data) == [one, two]
    assert run(cloud, "remove", one) == 0
    assert cloud.keys("samples/") == sorted(
        [f"samples/{two}.jpg", "samples/manifest.json"]
    )
    assert [e["sampleId"] for e in cloud.manifest()["samples"]] == [two]
    # A donor's withdrawal takes the source note too (review, Minor 6).
    assert noted(data) == [two]
    assert run(cloud, "remove", one) == 1  # already gone
    assert run(cloud, "remove", "../x") == 2
    # With no id, every samples/ object goes, the manifest and every note with them.
    assert run(cloud, "remove") == 0
    assert cloud.keys("samples/") == []
    assert noted(data) == []
    assert lines(capsys)[-1] == "removed 2 samples/ objects, the manifest among them"


def noted(data):
    """The sample ids in lusot-data's sample_sources.csv."""
    with (data / "samples" / "sample_sources.csv").open(encoding="utf-8-sig") as file:
        return [row["sampleId"] for row in csv.DictReader(file)]


def test_unexpected_data_ends_in_a_failed_line(data, capsys):
    # Review, Minor 8: a corrupt manifest or a non-JSON 201 is one failed: line, with
    # no traceback.
    cloud = ScriptCloud([LEVEL])
    assert run(cloud, "seed", "--ids", "OL001") == 0
    cloud.objects["samples/manifest.json"] = b"{not json"
    assert run(cloud, "remove", samples.sample_id("OL001")) == 1
    out, err = capsys.readouterr()
    assert out.splitlines()[-1] == "failed: JSONDecodeError" and err == ""
    cloud.objects["samples/manifest.json"] = json.dumps(
        {"version": 1, "samples": [{"sampleId": samples.sample_id("OL001")}]}
    ).encode()
    cloud.run_sample = lambda sample_id, request: httpx.Response(201, text="oops")
    assert run(cloud, "check", "--run") == 1
    out, err = capsys.readouterr()
    assert out.splitlines()[-1] == "failed: JSONDecodeError" and err == ""


def test_a_photo_named_as_sealed_exits_2_not_unreadable(tmp_path, monkeypatch, capsys):
    # Review, Minor 2. The row carries no _photo, so nothing is written under the name.
    row = open_row("OL009", filename="sealed.")
    row.pop("_photo")
    monkeypatch.setenv(
        "LUSOT_DATA_DIR", str(data_folder(tmp_path / "data", open_rows=[row]))
    )
    cloud = ScriptCloud([LEVEL])
    assert run(cloud, "seed", "--ids", "OL009") == 2
    assert cloud.called("dynamodb_put_item") == cloud.called("s3_put_object") == []
    assert "unreadable" not in capsys.readouterr().out


def test_check_counts_working_photos_and_runs_one(data, capsys):
    cloud = ScriptCloud([LEVEL, NO_FLOOD, LEVEL])
    assert run(cloud, "seed", "--ids", "OL001", "OL002") == 0
    capsys.readouterr()
    assert run(cloud, "check") == 0
    assert lines(capsys) == ["check: 2 samples listed, 2 photos answer 200"]
    assert run(cloud, "check", "--run") == 0
    out = lines(capsys)
    report = re.fullmatch(
        r"(r_[0-9a-f]{32}): mode sample, done/level, on the map: no", out[1]
    )
    assert report is not None
    # A fresh uuid4 device id, so the run never uses the shared none bucket.
    [post] = [r for r in cloud.requests if r[0] == "POST"]
    assert re.fullmatch(r"[0-9a-f-]{36}", post[2]["x-lusot-device"])
    del cloud.objects[f"samples/{samples.sample_id('OL002')}.jpg"]
    assert run(cloud, "check") == 1
    assert lines(capsys) == ["check: 2 samples listed, 1 photos answer 200"]
