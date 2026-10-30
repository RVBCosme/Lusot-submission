"""Tests for guards.py, and for what every operator script owes them (plan Task 8).

The sealed-path rule, the output mask and the one allow-list; then that each script
that reads lusot-data refuses a sealed data folder before reading anything, and that no
script prints a message body, a receipt handle, an uploader's address, a queue URL, a
coordinate or a path. Fakes only: nothing reaches AWS or Meta, and no folder named
sealed is ever made (F12).

check:py runs this file with the scripts' dependencies. Alone, from the repo root:
    uv run --python 3.13 --with pytest --with boto3 --with httpx --with numpy
        --with "opencv-python-headless<5" pytest -q backend/scripts/test_guards.py
"""

import demo_pins
import eval_runs
import guards
import hide_pin
import pytest
import redrive_dlq
import samples
from fake_aws import (
    DEAD_LETTER_QUEUE,
    LEVEL,
    MANILA,
    SENTINEL_IP,
    FakeSession,
    ScriptCloud,
    commons_folder,
    consent_row,
    data_folder,
    dead_letter,
    formats_py,
    open_row,
    s3_record_body,
)


class LinkedPath:
    """Stands in for a link: as written it names no sealed folder, but it resolves
    into one. Nothing is made on disk, so no symlink and no sealed folder is needed.
    """

    def __init__(self, written, resolved):
        self.written, self.resolved = written, resolved

    def absolute(self):
        return self.written

    def resolve(self):
        return self.resolved


def test_refuse_sealed_resolves_dots_and_links(tmp_path, capsys):
    link = LinkedPath(tmp_path / "a" / "x.jpg", tmp_path / "SEALED" / "x.jpg")
    for path in (
        tmp_path / "sealed" / "x.jpg",
        tmp_path / "set_b" / "Sealed" / "x.jpg",
        tmp_path / "sealed" / ".." / "x.jpg",
        link,
    ):
        assert guards.is_sealed(path) is True
        with pytest.raises(SystemExit) as exc:
            guards.refuse_sealed(tmp_path / "fine", path)
        assert exc.value.code == 2
    # A part must equal "sealed", in any case.
    assert guards.is_sealed(tmp_path / "unsealed" / "sealed.jpg") is False
    guards.refuse_sealed(tmp_path / "unsealed" / "sealed.jpg", tmp_path / "b")
    assert str(tmp_path) not in capsys.readouterr().out  # a refusal names no path
    assert list(tmp_path.iterdir()) == []


def refused(path):
    assert guards.is_sealed(path) is True
    with pytest.raises(SystemExit) as exc:
        guards.refuse_sealed(path)
    assert exc.value.code == 2


@pytest.mark.parametrize("name", ["sealed.", "sealed ", "SEALED.", "Sealed .."])
def test_trailing_dots_and_spaces_still_name_sealed(tmp_path, name):
    # R156 (the controller's addition): Windows strips a part's trailing dots and
    # spaces, so "sealed." opens the real sealed folder. Each form is refused as a
    # middle part and as the last, as written and as resolved. Stand-ins, so neither
    # check can lean on the other and nothing is opened or made on disk.
    plain = tmp_path / "a" / "b"
    for named in (tmp_path / "a" / name / "x.jpg", tmp_path / "a" / name):
        refused(LinkedPath(named, plain))
        refused(LinkedPath(plain, named))
    assert list(tmp_path.iterdir()) == []


def test_an_ntfs_stream_suffix_still_names_sealed(tmp_path):
    # As MS2's guard and the MS6 harness read it (48cdaf3): "sealed::$INDEX_ALLOCATION"
    # opens the folder itself, so the stream part goes before the comparison.
    plain = tmp_path / "a" / "b"
    named = tmp_path / "a" / "sealed::$INDEX_ALLOCATION" / "x.jpg"
    refused(LinkedPath(named, plain))
    refused(LinkedPath(plain, named))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "name", ["sealedx", "unsealed", "sealed_notes", "sealed.txt", "notes:sealed"]
)
def test_other_names_are_not_sealed(tmp_path, name):
    plain = tmp_path / "a" / "b"
    for other in (tmp_path / "a" / name / "x.jpg", tmp_path / "a" / name):
        for path in (LinkedPath(other, plain), LinkedPath(plain, other)):
            assert guards.is_sealed(path) is False
            guards.refuse_sealed(path)
    assert list(tmp_path.iterdir()) == []


def test_say_masks_twelve_digit_runs(capsys):
    # Built at run time, so no file holds a 12-digit run for the account-ID scan.
    twelve, eleven = "1234567890" + "12", "1234567890" + "1"
    assert guards.mask(f"in {twelve} and {twelve}3") == "in <account> and <account>3"
    assert guards.mask(f"an 11-digit run {eleven} stays") == (
        f"an 11-digit run {eleven} stays"
    )
    guards.say("account " + "2109876543" + "21")
    assert capsys.readouterr().out == "account <account>\n"
    # A report id is random hex, so about 1 in 14 holds a 12-digit run: it is printed
    # whole, while a run beside it is still masked.
    report_id = "r_fbee9945140b41349998430065abe84c"
    assert guards.mask(f"{report_id}: done, {twelve}") == (
        f"{report_id}: done, <account>"
    )
    assert guards.mask(f"x{report_id[2:]}") == "xfbee9945140b<account>65abe84c"
    # Only a standalone id is exempt (review, Important 1). An id run straight into
    # digits, and an r_ inside a word before 32 hex, keep their 12-digit run masked.
    straddle = "r_" + "a" * 26 + twelve + ": x"
    assert guards.mask(straddle) == "r_" + "a" * 26 + "<account>: x"
    embedded = "for_" + twelve + "abcdef0123456789abcd"
    assert guards.mask(embedded) == "for_<account>abcdef0123456789abcd"


def test_a_photo_named_as_sealed_is_refused(tmp_path, monkeypatch):
    # Review, Minor 2: each photo path is checked before its Source exists, so a base
    # name Windows opens as the sealed folder exits 2. No photo file is written: the
    # rows carry no _photo, so nothing named this way is made on disk.
    open_one = open_row("OL001", filename="sealed.")
    consented = consent_row("S001", file="sealed::$INDEX_ALLOCATION")
    for row in (open_one, consented):
        row.pop("_photo")
    data = data_folder(
        tmp_path / "data", open_rows=[open_one], consent_rows=[consented]
    )
    monkeypatch.setenv("LUSOT_DATA_DIR", str(data))
    for source_id in ("OL001", "S001"):
        with pytest.raises(SystemExit) as exc:
            guards.allowed_sources([source_id], frozenset({"M9-v4"}))
        assert exc.value.code == 2
    assert not [p for p in data.rglob("*") if p.name.lower().startswith("sealed")]


@pytest.mark.parametrize(
    ("fields", "passes"),
    [
        ({"license": "CC0"}, True),
        ({"license": "CC0 1.0"}, True),
        ({"license": "CC BY 2.0"}, True),
        ({"license": "CC BY 4.0"}, True),
        ({"license": "Public domain"}, False),
        ({"license": "PDM 1.0"}, False),
        ({"license": "CC BY-SA 4.0"}, False),
        ({"license": "Attribution-ShareAlike 4.0"}, False),
        ({"license": "CC BY-NC 2.0"}, False),
        ({"license": "CC BY 4.0\n"}, False),
        ({"demo_use": "check first"}, False),
        ({"demo_use": "avoid"}, False),
        ({"share_alike": "yes"}, False),
    ],
)
def test_the_allow_list(fields, passes):
    assert guards.open_licence_ok(open_row("OL001") | fields) is passes


def test_the_allow_list_for_consented_rows():
    approved = frozenset({"M9-v4"})
    assert guards.consent_ok(consent_row("S001"), approved) is True
    for fields in (
        {"consent_version": "M9-v2"},
        {"consent_file": ""},
        {"consent_file": "   "},
        {"kind": "clip"},
    ):
        assert guards.consent_ok(consent_row("S001") | fields, approved) is False


def test_consent_needs_rene_and_every_use(tmp_path):
    v4 = consent_row("S001")
    assert guards.consent_ok(v4, frozenset({"M9-v4"})) is True
    assert guards.consent_ok(v4, frozenset()) is False
    assert guards.FOUR_USE_VERSIONS == frozenset({"M9-v4"})
    # Earlier versions don't state every use, so approval alone never lets them in.
    every = frozenset({"M9-v1", "M9-v2", "M9-v3", "M9-v4"})
    for version in ("M9-v1", "M9-v2", "M9-v3"):
        assert guards.consent_ok(v4 | {"consent_version": version}, every) is False
    copy = formats_py(tmp_path / "formats.py", {"M9-v4"})
    assert guards.approved_m9_versions(copy) == frozenset({"M9-v4"})
    assert guards.approved_m9_versions(tmp_path / "missing.py") == frozenset()


def test_allowed_sources_reads_both_files_and_counts_refusals(tmp_path, monkeypatch):
    data = data_folder(
        tmp_path / "data",
        open_rows=[
            open_row("OL001", 1),
            open_row("OL002", 2, license="CC BY-SA 4.0"),
            open_row("OL003", 3, credit_line=" "),
        ],
        consent_rows=[
            consent_row("S001", 4),
            consent_row("S002", 5, consent_version="M9-v2"),
        ],
    )
    monkeypatch.setenv("LUSOT_DATA_DIR", str(data))
    ids = ["OL001", "OL002", "OL003", "S001", "S002", "X999"]
    found, refused = guards.allowed_sources(ids, frozenset({"M9-v4"}))
    assert sorted(found) == ["OL001", "S001"]
    assert found["OL001"].kind == "open"
    assert found["OL001"].photo == (
        data
        / "set_c"
        / "open-licensed-ph"
        / "OL001_2023-09-23_quezon-city_rain_bus.jpg"
    )
    assert found["S001"].kind == "consented"
    assert found["S001"].photo == data / "consented" / "S001.jpg"
    assert refused == {"not_on_allow_list": 3, "no_credit": 1}
    # Before Rene approves M9-v4, a v4 reply counts under its own cause.
    _, refused = guards.allowed_sources(["S001"], frozenset())
    assert refused == {"consent_not_approved": 1}


def test_source_fields(tmp_path, monkeypatch):
    data = data_folder(
        tmp_path / "data",
        open_rows=[open_row("OL001"), open_row("OL002", date_taken="undated")],
        consent_rows=[consent_row("S001")],
    )
    monkeypatch.setenv("LUSOT_DATA_DIR", str(data))
    found, _ = guards.allowed_sources(["OL001", "OL002", "S001"], frozenset({"M9-v4"}))
    assert sorted(found) == ["OL001", "OL002", "S001"]
    open_one, undated, consented = found["OL001"], found["OL002"], found["S001"]
    assert open_one.credit == (
        '"Flood OL001" by A. Photographer, CC BY 2.0. ' + guards.CHANGE_NOTE
    )
    assert (open_one.license, open_one.date) == ("CC BY 2.0", "2023-09-23")
    assert (open_one.place, open_one.event) == (
        "Commonwealth Avenue, Quezon City",
        "Habagat 2023",
    )
    assert undated.date == ""
    assert consented.credit == f"{guards.CONSENT_CREDIT} {guards.CHANGE_NOTE}"
    assert (consented.license, consented.date) == ("used with permission", "2026-10-20")
    assert (consented.place, consented.event) == (
        "Espana Boulevard, Sampaloc, Manila",
        "",
    )
    assert consented.note.startswith("NOTE-SENTINEL S001")
    assert open_one.note == "https://commons.test.invalid/OL001"
    assert guards.CHANGE_NOTE == (
        "Faces and plates blurred, and outlines drawn, by Lusot."
    )


def sealed_runs():
    return [
        (demo_pins, ["seed", "--until", "2026-12-20", "--ids", "S001"]),
        (samples, ["seed", "--ids", "OL001"]),
        (samples, ["relabel"]),
        (eval_runs, ["duplicate", "--position", "0"]),
    ]


@pytest.mark.parametrize(("script", "argv"), sealed_runs(), ids=lambda v: str(v)[:20])
def test_scripts_refuse_a_sealed_data_dir(tmp_path, monkeypatch, capsys, script, argv):
    # F12: the folder is named, never made.
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "sealed"))
    cloud = ScriptCloud()
    code = script.main(
        argv,
        session=FakeSession(cloud),
        http=cloud.http(),
        clock=cloud.clock,
        sleep=cloud.clock.sleep,
    )
    assert code == 2
    assert cloud.calls == [] and cloud.requests == []
    assert "sealed" in capsys.readouterr().out
    assert not (tmp_path / "sealed").exists()
    assert list(tmp_path.iterdir()) == []


def test_scripts_print_counts_and_ids_only(tmp_path, monkeypatch, capsys):
    data = data_folder(
        tmp_path / "data",
        # Slugs, as the open manifest holds them: samples.py refuses any other place.
        open_rows=[open_row("OL001", 1, place="manila", event="rain")],
        consent_rows=[consent_row("S001", 2)],
    )
    commons_folder(data, [f"Flood_in_Manila_{n:02d}.jpg" for n in range(5)])
    monkeypatch.setenv("LUSOT_DATA_DIR", str(data))
    monkeypatch.setattr(
        guards, "FORMATS_PY", formats_py(tmp_path / "formats.py", {"M9-v4"})
    )
    cloud = ScriptCloud([LEVEL] * 5)
    session, http = FakeSession(cloud), cloud.http()
    timing = {"clock": cloud.clock, "sleep": cloud.clock.sleep}
    pin = demo_pins.demo_report_id("S001")
    old = cloud.clock() - 2 * 3600
    for n, (event_s, redriven) in enumerate(
        [(old, False), (old - 86400, False), (old, True)]
    ):
        body = s3_record_body(f"r_{n:032x}", event_s)
        cloud.queues[DEAD_LETTER_QUEUE].append(
            dead_letter(body, n=n, sent_s=old, redriven=redriven)
        )
    runs = [
        lambda: demo_pins.main(
            ["seed", "--until", "2026-12-20", "--ids", "S001", "OL001"],
            session=session,
            http=http,
            **timing,
        ),
        lambda: demo_pins.main(["check", pin], session=session, http=http, **timing),
        lambda: samples.main(
            ["seed", "--ids", "OL001", "S001"], session=session, http=http, **timing
        ),
        lambda: samples.main(["check", "--run"], session=session, http=http, **timing),
        lambda: hide_pin.main([pin], session=session, clock=cloud.clock),
        lambda: redrive_dlq.main(["--dry-run"], session=session, clock=cloud.clock),
        lambda: eval_runs.main(
            ["duplicate", "--position", "1"], session=session, http=http, **timing
        ),
    ]
    for run in runs:
        assert run() == 0
    cloud.clock.sleep(61)  # the dry run's 60 s visibility timeout
    assert redrive_dlq.main([], session=session, clock=cloud.clock) == 0
    assert len(cloud.called("sqs_send_message")) >= 2  # eval's duplicate, the move
    out = capsys.readouterr().out
    assert pin in out  # report ids are printed
    bodies = [m["Body"] for q in cloud.queues.values() for m in q]
    for private in (
        str(tmp_path),
        "lusot-data",
        "test.invalid",  # the API's, the links' and the queues' URLs
        SENTINEL_IP,
        "handle-",  # a receipt handle
        "Records",
        "NOTE-SENTINEL",
        *MANILA,
        "14.61",
        "120.99",
        "Flood_in_Manila",
        *bodies,
    ):
        assert private not in out, private
