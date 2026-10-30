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
# What relabel prints when no credit line changed beyond its note, as expected.
PREFIX_SAME = "relabel: 0 entries have a credit line that changed beyond the note"
# What the first seed stored for four sources: the open manifest's place and event
# slugs, and a consented row's place words with no event.
FIRST_SEED = {
    "OL010": ("baliuag-bulacan", "rain"),
    "OL011": ("unknown", "ondoy"),
    "OL012": ("manila", "high-tide"),
    "S001": ("Espana Boulevard, Sampaloc, Manila", ""),
}
# Two consented photos whose donors wrote one lowercase word as the place.
LOWERCASE_PLACES = {"S003": ("manila", ""), "S004": ("sampaloc", "")}


def slug_row(source_id, n=0, **fields):
    """An open row as the open manifest holds one: its place and event are slugs."""
    return open_row(source_id, n, **({"place": "manila", "event": "rain"} | fields))


def slugged_rows(**first):
    """The three open rows with slugs, as the `data` fixture writes them; `first` changes
    the first."""
    return [
        slug_row("OL010", 10, **({"place": "baliuag-bulacan"} | first)),
        slug_row("OL011", 11, place="unknown", event="ondoy"),
        slug_row("OL012", 12, place="manila", event="high-tide"),
    ]


@pytest.fixture
def data(tmp_path, monkeypatch):
    """lusot-data with seven open-licensed rows and four consented ones, M9-v4 approved."""
    base = data_folder(
        tmp_path / "data",
        open_rows=[
            slug_row("OL001", 1),
            slug_row("OL002", 2, event=""),
            slug_row("OL003", 3),
            slug_row("OL009", 9, date_taken="undated"),
            *slugged_rows(),
        ],
        consent_rows=[
            consent_row("S001", 4),
            consent_row("S002", 5),
            consent_row("S003", 6, place_text="manila"),
            consent_row("S004", 7, place_text="sampaloc"),
        ],
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
        "Rain",
    )
    assert level["place"] == "Manila"
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


@pytest.mark.parametrize(
    ("name", "value", "shown"),
    [
        ("place", "calumpit-bulacan", "Calumpit, Bulacan"),
        ("event", "high-tide", "High tide"),
        ("place", "unknown", ""),  # the field is left out
        ("event", "Unknown", ""),  # in any case
        ("place", "UNKNOWN", ""),
        ("place", "", ""),
    ],
)
def test_an_open_value_is_a_table_key_unknown_or_nothing(name, value, shown):
    assert samples.open_words(name, value) == shown


@pytest.mark.parametrize(
    "value",
    # Not slugs the table holds, whatever they look like: none is shown as it is.
    ["pasig", "las-piñas", "hagonoy_bulacan", "Hagonoy-Bulacan", "Manila", "Rain"],
)
def test_any_other_open_value_is_refused(value):
    with pytest.raises(samples.UnmappedSlug) as raised:
        samples.open_words("place", value)
    assert (raised.value.name, raised.value.slug) == ("place", value)
    assert str(raised.value) == value


def test_known_words_map_only_what_needs_no_source():
    known = samples.known_words
    assert known("place", "manila") == "Manila"
    assert known("event", "high-tide") == "High tide"
    assert known("place", "unknown") == ""
    # Anything else stays as it is: words already shown, a donor's place text, and a
    # slug with no words, whose kind can't be told without its source.
    for value in ("Manila", "Baliuag, Bulacan", "sampaloc", "pasig", "Hagonoy-Bulacan"):
        assert known("place", value) == value


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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("place", "pasig"),
        ("place", "las-piñas"),
        ("place", "hagonoy_bulacan"),
        ("place", "Hagonoy-Bulacan"),
        ("event", "surge"),
        ("event", "Habagat 2023"),  # words, but not the table's
    ],
)
def test_seed_refuses_an_open_value_outside_the_table_before_any_run(
    tmp_path, monkeypatch, capsys, field, value
):
    base = data_folder(
        tmp_path / "data", open_rows=[slug_row("OL020", 1, **{field: value})]
    )
    monkeypatch.setenv("LUSOT_DATA_DIR", str(base))
    cloud = ScriptCloud([LEVEL])
    assert run(cloud, "seed", "--ids", "OL020") == 1
    assert cloud.called("dynamodb_put_item") == cloud.called("s3_put_object") == []
    assert cloud.keys("samples/") == []
    out = lines(capsys)
    assert "refused before any run: 1 unmapped_slug" in out
    assert out[-1] == "seed: 1 candidates given, 0 qualified"


def test_seed_leaves_out_an_unknown_open_value_in_any_case(tmp_path, monkeypatch):
    base = data_folder(
        tmp_path / "data",
        open_rows=[slug_row("OL020", 1, place="Unknown", event="UNKNOWN")],
    )
    monkeypatch.setenv("LUSOT_DATA_DIR", str(base))
    cloud = ScriptCloud([LEVEL])
    assert run(cloud, "seed", "--ids", "OL020") == 0
    [entry] = cloud.manifest()["samples"]
    assert "place" not in entry and "event" not in entry


def test_seed_shows_a_consented_place_as_its_donor_wrote_it(data):
    cloud = ScriptCloud([LEVEL, LEVEL])
    assert run(cloud, "seed", "--ids", *LOWERCASE_PLACES) == 0
    manila, sampaloc = cloud.manifest()["samples"]
    # Never through the table: "manila" doesn't become "Manila", and "sampaloc" isn't
    # refused as a slug.
    assert (manila["place"], sampaloc["place"]) == ("manila", "sampaloc")
    assert "event" not in manila and "event" not in sampaloc


def store(cloud, manifest):
    """Leave a manifest in the bucket, which isn't one of the script's own calls."""
    cloud.objects["samples/manifest.json"] = json.dumps(
        manifest, ensure_ascii=False, indent=2
    ).encode("utf-8")


def first_seeded(cloud, stored=FIRST_SEED):
    """Seed the sources in `stored`, then put the manifest back as the first seed wrote
    it: the full change note, and the place and event that `stored` gives for each.
    Returns the manifest the seed wrote."""
    assert run(cloud, "seed", "--ids", *stored) == 0
    new = cloud.manifest()
    old = []
    for source_id, entry in zip(stored, new["samples"], strict=True):
        place, event = stored[source_id]
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
    assert lines(capsys) == [
        PREFIX_SAME,
        "relabel: 4 entries read, 4 changed, 0 unchanged",
    ]


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
    assert lines(capsys) == [
        PREFIX_SAME,
        "relabel: 4 entries read, 0 changed, 4 unchanged",
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("place", "pasig"),
        ("place", "las-piñas"),
        ("place", "hagonoy_bulacan"),
        ("place", "Hagonoy-Bulacan"),
        ("event", "surge"),
    ],
)
def test_relabel_refuses_an_open_value_outside_the_table_before_any_write(
    data, capsys, field, value
):
    cloud = ScriptCloud([LEVEL, NO_FLOOD, LEVEL, LEVEL])
    first_seeded(cloud)
    # The open manifest's row for the first sample now holds a value with no words.
    data_folder(
        data,
        open_rows=slugged_rows(**{field: value}),
        consent_rows=[consent_row("S001", 4)],
    )
    stored = cloud.objects["samples/manifest.json"]
    writes = len(cloud.called("s3_put_object"))
    capsys.readouterr()
    assert run(cloud, "relabel") == 2
    assert len(cloud.called("s3_put_object")) == writes
    assert cloud.objects["samples/manifest.json"] == stored
    assert lines(capsys) == [f"refused: {field} slug outside the table: {value}"]


def test_relabel_leaves_out_an_unknown_open_value_in_any_case(data, capsys):
    cloud = ScriptCloud([LEVEL, NO_FLOOD, LEVEL, LEVEL])
    first_seeded(cloud)
    data_folder(
        data,
        open_rows=slugged_rows(place="Unknown", event="UNKNOWN"),
        consent_rows=[consent_row("S001", 4)],
    )
    assert run(cloud, "relabel") == 0
    one = cloud.manifest()["samples"][0]
    assert "place" not in one and "event" not in one


def test_relabel_keeps_a_consented_place_as_its_donor_wrote_it(data, capsys):
    cloud = ScriptCloud([LEVEL, LEVEL])
    new = first_seeded(cloud, LOWERCASE_PLACES)
    assert run(cloud, "relabel") == 0
    manila, sampaloc = cloud.manifest()["samples"]
    # Never through the table, and a lowercase word is no reason to refuse the run.
    assert (manila["place"], sampaloc["place"]) == ("manila", "sampaloc")
    assert cloud.manifest() == new  # only the credits' notes changed
    assert manila["credit"] == f"{guards.CONSENT_CREDIT} {SAMPLE_NOTE}"
    assert lines(capsys)[-1] == "relabel: 2 entries read, 2 changed, 0 unchanged"


def test_relabel_without_a_source_maps_the_table_slugs_and_the_note(data, capsys):
    cloud = ScriptCloud([LEVEL, NO_FLOOD, LEVEL, LEVEL])
    new = first_seeded(cloud)
    manifest = cloud.manifest()
    # Three entries with no row in lusot-data's source notes: one with the full note, one
    # already relabelled, and one whose place is a slug with no words.
    orphan = {
        "sampleId": "s0123456789",
        "credit": "Somebody, CC0. " + guards.CHANGE_NOTE,
        "license": "CC0",
        "place": "manila",
        "date": "2026-10-28",
        "event": "high-tide",
        "savedAt": "2026-10-28",
        "status": "done",
        "noFloodSeen": True,
    }
    shown = {"credit": "Somebody, CC0. " + SAMPLE_NOTE, "place": "Manila"}
    shown |= {"event": "High tide"}
    done = orphan | shown | {"sampleId": "s9876543210"}
    odd = orphan | {"sampleId": "s1111111111", "place": "pasig"}
    manifest["samples"] += [orphan, done, odd]
    store(cloud, manifest)
    capsys.readouterr()
    assert run(cloud, "relabel") == 0
    *_, mapped, same, left = cloud.manifest()["samples"]
    assert mapped == orphan | shown  # the table slugs need no source
    assert same == done
    assert left == odd | {"credit": shown["credit"], "event": "High tide"}
    assert left["place"] == "pasig"  # no words to give it, so it stays
    no_source = (
        "relabel: 3 entries have no source on the allow-list;"
        " only their change note and table slugs are rewritten"
    )
    assert lines(capsys) == [
        no_source,
        PREFIX_SAME,
        "relabel: 7 entries read, 6 changed, 1 unchanged",
    ]
    assert cloud.manifest()["samples"][:4] == new["samples"]


def test_relabel_says_there_is_no_source_before_it_writes(data, capsys, monkeypatch):
    cloud = ScriptCloud([LEVEL, NO_FLOOD, LEVEL, LEVEL])
    new = first_seeded(cloud)
    # The notes are gone, as when LUSOT_DATA_DIR points at another folder.
    (data / "samples" / "sample_sources.csv").unlink()
    capsys.readouterr()
    said_before_the_write = []
    write_manifest = samples.write_manifest

    def spy(s3, bucket, manifest):
        said_before_the_write.extend(lines(capsys))
        write_manifest(s3, bucket, manifest)

    monkeypatch.setattr(samples, "write_manifest", spy)
    assert run(cloud, "relabel") == 0
    assert said_before_the_write[0].startswith("relabel: 4 entries have no source")
    # The table slugs and the note are done without a source, so the half-relabelled
    # state the first run would have left is gone.
    assert cloud.manifest() == new
    assert lines(capsys) == ["relabel: 4 entries read, 4 changed, 0 unchanged"]


def test_relabel_ignores_a_notes_row_that_names_another_source(data, capsys):
    cloud = ScriptCloud([LEVEL, NO_FLOOD, LEVEL, LEVEL])
    new = first_seeded(cloud)
    # A hand edit or a merged file: the first two samples' rows swap their sources.
    path = data / "samples" / "sample_sources.csv"
    rows = samples.read_notes(path)
    one, two = (samples.sample_id(i) for i in ("OL010", "OL011"))
    rows[one]["source_id"], rows[two]["source_id"] = "OL011", "OL010"
    samples.write_notes(path, rows)
    capsys.readouterr()
    assert run(cloud, "relabel") == 0
    # Neither entry took the other's credit line, so no sample is credited to a wrong
    # author or beside a wrong licence.
    assert cloud.manifest() == new
    first, second = cloud.manifest()["samples"][:2]
    assert '"Flood OL010"' in first["credit"] and '"Flood OL011"' in second["credit"]
    no_source = (
        "relabel: 2 entries have no source on the allow-list;"
        " only their change note and table slugs are rewritten"
    )
    assert lines(capsys) == [
        no_source,
        PREFIX_SAME,
        "relabel: 4 entries read, 4 changed, 0 unchanged",
    ]


def test_relabel_counts_a_credit_line_that_changed_beyond_the_note(data, capsys):
    cloud = ScriptCloud([LEVEL, NO_FLOOD, LEVEL, LEVEL])
    first_seeded(cloud)
    # The open manifest's credit line for the first sample was edited after the seed.
    data_folder(
        data,
        open_rows=slugged_rows(
            credit_line='"Flood OL010" by B. Photographer, CC BY 2.0'
        ),
        consent_rows=[consent_row("S001", 4)],
    )
    capsys.readouterr()
    assert run(cloud, "relabel") == 0
    assert cloud.manifest()["samples"][0]["credit"] == (
        '"Flood OL010" by B. Photographer, CC BY 2.0. ' + SAMPLE_NOTE
    )
    assert lines(capsys) == [
        "relabel: 1 entries have a credit line that changed beyond the note",
        "relabel: 4 entries read, 4 changed, 0 unchanged",
    ]


def test_relabel_on_no_manifest_changes_nothing(data, capsys):
    cloud = ScriptCloud()
    assert run(cloud, "relabel") == 0
    assert cloud.called("s3_put_object") == []
    assert lines(capsys) == [
        PREFIX_SAME,
        "relabel: 0 entries read, 0 changed, 0 unchanged",
    ]


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
