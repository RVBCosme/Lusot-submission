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

import demo_pins
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
SAMPLE_NOTE = "Faces and plates blurred by Lusot."  # a sample's photo has no outlines
# What the first seed stored for four sources: the open manifest's place and event
# slugs, and a consented row's place words with no event.
FIRST_SEED = {
    "OL010": ("baliuag-bulacan", "rain"),
    "OL011": ("unknown", "ondoy"),
    "OL012": ("manila", "high-tide"),
    "S001": ("Espana Boulevard, Sampaloc, Manila", ""),
}


@pytest.fixture
def data(tmp_path, monkeypatch):
    """lusot-data with seven open-licensed rows and two consented ones, M9-v4 approved."""
    base = data_folder(
        tmp_path / "data",
        open_rows=[
            open_row("OL001", 1),
            open_row("OL002", 2, event=""),
            open_row("OL003", 3),
            open_row("OL009", 9, date_taken="undated"),
            open_row("OL010", 10, place="baliuag-bulacan", event="rain"),
            open_row("OL011", 11, place="unknown", event="ondoy"),
            open_row("OL012", 12, place="manila", event="high-tide"),
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
    # A refused seed keeps no copy at all (the tracker's ruling, Oct 30, 10:31 AM).
    refused_copy = f"blurred/{seeds[2]['reportId']['S']}.jpg"
    assert refused_copy not in cloud.objects
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
    # A sample's photo carries no outlines, so its credit says only the blur.
    assert level["credit"].endswith(" " + SAMPLE_NOTE)
    assert "outlines" not in level["credit"]
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


# The sample note and the display words (the tracker's ruling, Oct 30, 7:30 PM; M20).


def test_the_sample_note_and_the_display_words_are_the_approved_ones():
    assert guards.SAMPLE_CHANGE_NOTE == SAMPLE_NOTE
    # The demo pin's note still names the outlines its overlay carries.
    assert guards.CHANGE_NOTE == (
        "Faces and plates blurred, and outlines drawn, by Lusot."
    )
    assert samples.PLACE_WORDS == {
        "baliuag-bulacan": "Baliuag, Bulacan",
        "calumpit-bulacan": "Calumpit, Bulacan",
        "marilao-bulacan": "Marilao, Bulacan",
        "manila": "Manila",
    }
    assert samples.EVENT_WORDS == {
        "ondoy": "Typhoon Ondoy",
        "rain": "Rain",
        "flood": "Flood",
        "high-tide": "High tide",
    }


def test_display_words():
    words = samples.display_words
    assert words(samples.PLACE_WORDS, "calumpit-bulacan") == "Calumpit, Bulacan"
    assert words(samples.EVENT_WORDS, "high-tide") == "High tide"
    assert words(samples.PLACE_WORDS, "unknown") == ""  # the field is left out
    assert words(samples.PLACE_WORDS, "") == ""
    # Words already shown, and a consented photo's place text, pass through.
    assert words(samples.PLACE_WORDS, "Baliuag, Bulacan") == "Baliuag, Bulacan"
    assert words(samples.EVENT_WORDS, "Habagat 2023") == "Habagat 2023"
    assert words(samples.PLACE_WORDS, "Espana Boulevard, Manila") == (
        "Espana Boulevard, Manila"
    )
    # A slug outside the table is never shown as it is, and no word is made up.
    for value in ("pasig", "quezon-city"):
        with pytest.raises(samples.UnmappedSlug) as raised:
            words(samples.PLACE_WORDS, value)
        assert str(raised.value) == value


def test_seed_writes_the_sample_note_and_the_display_words(data):
    cloud = ScriptCloud([LEVEL, NO_FLOOD, LEVEL, LEVEL])
    assert run(cloud, "seed", "--ids", *FIRST_SEED) == 0
    one, two, three, consented = cloud.manifest()["samples"]
    for entry in (one, two, three, consented):
        assert entry["credit"].endswith(" " + SAMPLE_NOTE)
        assert "outlines" not in entry["credit"]
    assert one["credit"] == (
        '"Flood OL010" by A. Photographer, CC BY 2.0. ' + SAMPLE_NOTE
    )
    assert (one["place"], one["event"]) == ("Baliuag, Bulacan", "Rain")
    assert list(two) == [  # no place: "unknown" is left out
        "sampleId",
        "credit",
        "license",
        "date",
        "event",
        "savedAt",
        "status",
        "noFloodSeen",
    ]
    assert two["event"] == "Typhoon Ondoy"
    assert (three["place"], three["event"]) == ("Manila", "High tide")
    assert consented["place"] == "Espana Boulevard, Sampaloc, Manila"
    assert consented["credit"] == f"{guards.CONSENT_CREDIT} {SAMPLE_NOTE}"


def test_seed_refuses_a_slug_outside_the_table_before_any_run(
    tmp_path, monkeypatch, capsys
):
    base = data_folder(
        tmp_path / "data", open_rows=[open_row("OL020", 1, place="pasig")]
    )
    monkeypatch.setenv("LUSOT_DATA_DIR", str(base))
    cloud = ScriptCloud([LEVEL])
    assert run(cloud, "seed", "--ids", "OL020") == 1
    assert cloud.called("dynamodb_put_item") == cloud.called("s3_put_object") == []
    assert cloud.keys("samples/") == []
    out = lines(capsys)
    assert "refused before any run: 1 unmapped_slug" in out
    assert out[-1] == "seed: 1 candidates given, 0 qualified"


def store(cloud, manifest):
    """Leave a manifest in the bucket, which isn't one of the script's own calls."""
    cloud.objects["samples/manifest.json"] = json.dumps(
        manifest, ensure_ascii=False, indent=2
    ).encode("utf-8")


def first_seeded(cloud):
    """Seed the four sources, then put the manifest back as the first seed wrote it:
    the full change note, and the open manifest's slugs. Returns the seeded manifest."""
    assert run(cloud, "seed", "--ids", *FIRST_SEED) == 0
    new = cloud.manifest()
    old = []
    for source_id, entry in zip(FIRST_SEED, new["samples"], strict=True):
        place, event = FIRST_SEED[source_id]
        rest = {
            name: value
            for name, value in entry.items()
            if name not in ("sampleId", "credit", "license", "place", "date", "event")
        }
        before = {
            "sampleId": entry["sampleId"],
            "credit": entry["credit"].removesuffix(SAMPLE_NOTE) + guards.CHANGE_NOTE,
            "license": entry["license"],
            "place": place,
            "date": entry["date"],
        }
        if event:
            before["event"] = event
        old.append(before | rest)
    store(cloud, {"version": 1, "samples": old})
    return new


def test_relabel_rewrites_the_note_and_the_words(data, capsys):
    cloud = ScriptCloud([LEVEL, NO_FLOOD, LEVEL, LEVEL])
    new = first_seeded(cloud)
    old = cloud.manifest()
    assert old != new
    photos = {k: v for k, v in cloud.objects.items() if k.endswith(".jpg")}
    capsys.readouterr()
    seen = len(cloud.calls)
    assert run(cloud, "relabel") == 0
    # The manifest the new seed writes, key order and all.
    assert cloud.manifest() == new
    assert [list(e) for e in cloud.manifest()["samples"]] == [
        list(e) for e in new["samples"]
    ]
    one, two, three, consented = cloud.manifest()["samples"]
    assert one["credit"] == (
        '"Flood OL010" by A. Photographer, CC BY 2.0. ' + SAMPLE_NOTE
    )
    assert (one["place"], one["event"]) == ("Baliuag, Bulacan", "Rain")
    assert "place" not in two and two["event"] == "Typhoon Ondoy"  # "unknown" is gone
    assert (three["place"], three["event"]) == ("Manila", "High tide")
    assert consented["credit"] == f"{guards.CONSENT_CREDIT} {SAMPLE_NOTE}"
    assert consented["place"] == "Espana Boulevard, Sampaloc, Manila"
    # Every other field is kept, and no photo is touched.
    for before, after in zip(old["samples"], cloud.manifest()["samples"], strict=True):
        for name in set(before) - {"credit", "place", "event"}:
            assert after[name] == before[name]
    assert {k: v for k, v in cloud.objects.items() if k.endswith(".jpg")} == photos
    # It read the manifest and wrote it once, as JSON: no analysis, no Meta call.
    assert sorted(name for name, _ in cloud.calls[seen:]) == [
        "cloudformation_describe_stack_resource",
        "cloudformation_describe_stacks",
        "s3_get_object",
        "s3_put_object",
    ]
    put = cloud.called("s3_put_object")[-1]
    assert (put["Key"], put["ContentType"]) == (
        "samples/manifest.json",
        "application/json",
    )
    assert lines(capsys) == ["relabel: 4 entries read, 4 changed, 0 unchanged"]


def test_relabel_leaves_a_relabelled_manifest_alone(data, capsys):
    cloud = ScriptCloud([LEVEL, NO_FLOOD, LEVEL, LEVEL])
    first_seeded(cloud)
    assert run(cloud, "relabel") == 0
    writes = len(cloud.called("s3_put_object"))
    stored = cloud.objects["samples/manifest.json"]
    capsys.readouterr()
    assert run(cloud, "relabel") == 0
    assert len(cloud.called("s3_put_object")) == writes  # nothing written
    assert cloud.objects["samples/manifest.json"] == stored
    assert lines(capsys) == ["relabel: 4 entries read, 0 changed, 4 unchanged"]


@pytest.mark.parametrize(("field", "slug"), [("place", "pasig"), ("event", "surge")])
def test_relabel_refuses_a_slug_outside_the_table_before_any_write(
    data, capsys, field, slug
):
    cloud = ScriptCloud([LEVEL, NO_FLOOD, LEVEL, LEVEL])
    first_seeded(cloud)
    manifest = cloud.manifest()
    manifest["samples"][0][field] = slug
    store(cloud, manifest)
    stored = cloud.objects["samples/manifest.json"]
    writes = len(cloud.called("s3_put_object"))
    capsys.readouterr()
    assert run(cloud, "relabel") == 2
    assert len(cloud.called("s3_put_object")) == writes
    assert cloud.objects["samples/manifest.json"] == stored
    assert lines(capsys) == [f"refused: {field} slug outside the table: {slug}"]


def test_relabel_refuses_a_source_slug_outside_the_table(data, capsys):
    cloud = ScriptCloud([LEVEL, NO_FLOOD, LEVEL, LEVEL])
    first_seeded(cloud)
    # The open manifest's row for the first sample now holds a slug with no words.
    data_folder(
        data,
        open_rows=[open_row("OL010", 10, place="pasig", event="rain")],
        consent_rows=[consent_row("S001", 4)],
    )
    stored = cloud.objects["samples/manifest.json"]
    writes = len(cloud.called("s3_put_object"))
    capsys.readouterr()
    assert run(cloud, "relabel") == 2
    assert len(cloud.called("s3_put_object")) == writes
    assert cloud.objects["samples/manifest.json"] == stored
    assert lines(capsys) == ["refused: place slug outside the table: pasig"]


def test_relabel_without_a_source_changes_only_the_note(data, capsys):
    cloud = ScriptCloud([LEVEL, NO_FLOOD, LEVEL, LEVEL])
    first_seeded(cloud)
    manifest = cloud.manifest()
    # Two entries with no row in lusot-data's source notes: one with the full note, one
    # already relabelled.
    orphan = {
        "sampleId": "s0123456789",
        "credit": "Somebody, CC0. " + guards.CHANGE_NOTE,
        "license": "CC0",
        "place": "manila",
        "date": "2026-10-28",
        "savedAt": "2026-10-28",
        "status": "done",
        "noFloodSeen": True,
    }
    done = orphan | {"sampleId": "s9876543210", "credit": "Other, CC0. " + SAMPLE_NOTE}
    manifest["samples"] += [orphan, done]
    store(cloud, manifest)
    capsys.readouterr()
    assert run(cloud, "relabel") == 0
    *_, changed, same = cloud.manifest()["samples"]
    # The place stays, as it was.
    assert changed == orphan | {"credit": "Somebody, CC0. " + SAMPLE_NOTE}
    assert same == done
    no_source = (
        "relabel: 2 entries have no source on the allow-list;"
        " only their change note is rewritten"
    )
    assert lines(capsys) == [
        "relabel: 6 entries read, 5 changed, 1 unchanged",
        no_source,
    ]


def test_relabel_on_no_manifest_changes_nothing(data, capsys):
    cloud = ScriptCloud()
    assert run(cloud, "relabel") == 0
    assert cloud.called("s3_put_object") == []
    assert lines(capsys) == ["relabel: 0 entries read, 0 changed, 0 unchanged"]


def test_a_demo_pin_keeps_the_full_change_note(data):
    cloud = ScriptCloud([LEVEL])
    code = demo_pins.main(
        ["seed", "--until", "2026-12-20", "--ids", "S001"],
        session=FakeSession(cloud),
        http=cloud.http(),
        clock=cloud.clock,
        sleep=cloud.clock.sleep,
    )
    assert code == 0
    [pin] = [i for i in cloud.items.values() if i["mode"] == {"S": "demo"}]
    assert pin["credit"]["S"] == f"{guards.CONSENT_CREDIT} {guards.CHANGE_NOTE}"
