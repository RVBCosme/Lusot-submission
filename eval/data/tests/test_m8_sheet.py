"""Tests for the M8 sheet command, eval/data/m8_sheet.py (C208).

Each log and photo is synthetic, under tmp_path. The command only stats a photo, and
synth.opened_paths proves that it never reads one (C201).
"""

import json
import os
import re
from pathlib import Path

import formats
import m8_sheet
import pytest
import synth

DATA = Path(__file__).resolve().parents[1]  # eval/data
COLUMNS = formats.TEMPLATES["set_a_log.csv"]
START = "M8.start(document, window, "
# The fixed line printed after the count, so that a remake never drops saved labels.
REMINDER = "Before the page is remade, export your labels from it, so none is lost."


def row(photo_id: str, photo_file: str | None = None) -> dict[str, str]:
    """A log row with its id and photo file, every other column blank."""
    if photo_file is None:
        photo_file = f"{photo_id}.jpg"
    return {"candidate_id": photo_id, "photo_file": photo_file}


def set_a(
    folder: Path, rows: list[dict[str, str]], photos: list[str]
) -> tuple[Path, Path]:
    """Write the log, and the named photos in raw beside the page, as Rene keeps them.
    Return the log's path and the page's."""
    raw = folder / "raw"
    raw.mkdir(exist_ok=True)
    for seed, name in enumerate(photos):
        (raw / name).write_bytes(synth.jpeg(seed))
    log = synth.write_csv(folder / "set_a_log.csv", COLUMNS, rows)
    return log, folder / "m8_sheet.html"


def run(log: Path, out: Path) -> int:
    return m8_sheet.main(["--set-a-log", str(log), "--out", str(out)])


def data_of(page: str) -> dict:
    """The data the page passes to M8.start, read back from the call's JSON. The call is
    the last one in the page: the script's own comments show it too."""
    start = page.rindex(START) + len(START)
    return json.loads(page[start : page.index(");\n</script>", start)])


def test_page_lists_each_photo_once(tmp_path):
    """An alert row repeats its photo's row (C223), so a photo with two rows is listed
    once, in id order. The data holds exactly what M8.start reads: the photos, Table
    5's lists and the storage key."""
    rows = [row("A002"), row("A001"), row("A002")]
    log, out = set_a(tmp_path, rows, ["A001.jpg", "A002.jpg"])
    assert run(log, out) == 0
    assert data_of(out.read_text(encoding="utf-8")) == {
        "photos": [
            {"id": "A001", "file": "A001.jpg"},
            {"id": "A002", "file": "A002.jpg"},
        ],
        "vehicleTypes": list(formats.VEHICLE_TYPES),
        "bodyWaterlines": list(formats.BODY_WATERLINES),
        "wheelWaterlines": list(formats.WHEEL_WATERLINES),
        "personWaterlines": list(formats.PERSON_WATERLINES),
        "storageKey": "lusot-m8-v1",
    }


def test_page_holds_no_log_text(tmp_path, capsys):
    """Only the ids and file names leave the log. No label, passability, link, spot or
    note reaches the page or the output (C201)."""
    cells = {column: f"SENTINEL-{column}" for column in COLUMNS}
    cells.update(
        spot_text="SENTINEL-SPOT",
        post_url="SENTINEL-LINK",
        level_label_raw="SENTINEL knee deep",
        notes="SENTINEL-NOTE",
    )
    rows = [{**cells, **row(photo_id)} for photo_id in ("A001", "A002")]
    log, out = set_a(tmp_path, rows, ["A001.jpg", "A002.jpg"])
    assert run(log, out) == 0
    printed = capsys.readouterr()
    assert "SENTINEL" not in out.read_text(encoding="utf-8")
    assert "SENTINEL" not in printed.out + printed.err


def test_page_needs_no_network():
    """The page loads nothing but its photos, which the script adds at run time from
    raw/ beside the page, so its text names no source at all. Task 4b's browser check,
    on a synthetic page, watched the requests themselves."""
    page = m8_sheet.build_page([("A001", "A001.jpg")])
    lowered = page.lower()
    words = (
        "http:",
        "https:",
        "<link",
        "@import",
        "src=",
        "<base",
        "<iframe",
        "<embed",
    )
    found = [word for word in words if word in lowered]
    calls = ("fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon")
    found += [call for call in calls if call in page]
    style = lowered[lowered.index("<style>") : lowered.index("</style>")]
    found += ["url("] if "url(" in style else []
    # A URL with a scheme, or one that starts with // after a quote, a bracket or an =.
    # The script's comments start with // too, but after a space or a line break.
    found += re.findall(r"[a-z][a-z0-9+.-]*://|[\"'(=]\s*//", lowered)
    assert found == []


def test_page_states_the_convention():
    """The page states Rene's final rule for a waterline between two marks (MS3b-Q5,
    C208), above the photos, which the script adds after itself."""
    assert m8_sheet.IN_BETWEEN_RULE == (
        "When the water sits between two marks, pick the higher mark. "
        "This holds for wheels, people and car bodies alike."
    )
    page = m8_sheet.build_page([("A001", "A001.jpg")])
    assert m8_sheet.IN_BETWEEN_RULE in page
    assert page.index(m8_sheet.IN_BETWEEN_RULE) < page.index("<script>")


def test_page_embeds_the_script():
    """The page's one classic script holds m8_sheet.js verbatim, then the start call, at
    the end of the body. A </ would end the element early, so the script holds none,
    and the data's < are escaped, so a file name can't end the element either."""
    script = (DATA / "m8_sheet.js").read_text(encoding="utf-8")
    assert "</" not in script
    name = "A001</script><!--<script>.jpg"
    page = m8_sheet.build_page([("A001", name)])
    assert page.count("<script") == page.count("</script") == 1
    inside = page[page.index("<script>") + len("<script>") : page.index("</script>")]
    # The call has a line of its own, so a script ending in a // comment can't swallow it.
    assert inside.startswith("\n" + script + "\n" + START)
    assert inside.endswith(");\n")
    assert "<!--" not in inside
    assert page.endswith("</script>\n</body>\n</html>\n")
    assert data_of(page)["photos"] == [{"id": "A001", "file": name}]


def test_sheet_reads_no_photo_bytes(tmp_path):
    """Before the split, a photo is only statted, never opened or listed (C201). The
    audit hook sees the tool's own opens, the log's among them."""
    log, out = set_a(tmp_path, [row("A001"), row("A002")], ["A001.jpg", "A002.jpg"])
    code, events = synth.opened_paths(
        DATA / "m8_sheet.py", ["--set-a-log", str(log), "--out", str(out)]
    )
    assert code == 0
    assert ("open", str(log)) in events
    raw = tmp_path / "raw"

    def in_raw(path: str) -> bool:
        absolute = Path(os.path.abspath(path))
        return absolute == raw or raw in absolute.parents

    assert [(event, path) for event, path in events if in_raw(path)] == []
    assert out.is_file()


def test_missing_photo_and_bad_ids(tmp_path, capsys):
    """Each problem names the photo's id, or its row when the id itself is bad, and
    never a cell's text. A blank photo_file names raw itself, which is no photo.
    Nothing is written, so an earlier page stays as it was."""
    rows = [row("A001"), row("Espana"), row("A003"), row("A004", "")]
    log, out = set_a(tmp_path, rows, ["A001.jpg"])
    out.write_bytes(b"earlier page")
    assert run(log, out) == 1
    assert capsys.readouterr().out == (
        "row 2 candidate_id: bad_id\n"
        "A003 photo_file: missing\n"
        "A004 photo_file: missing\n"
    )
    assert out.read_bytes() == b"earlier page"


@pytest.mark.parametrize("where", ["--set-a-log", "--out", "photo_file"])
def test_refuses_sealed_paths(tmp_path, capsys, where):
    """A path with a part named sealed is refused before it is used (C222): either
    flag's before the log is read, or a photo's that the log names before its stat.
    Each sealed folder here is a name only, and none is created."""
    rows = {
        "--set-a-log": [row("A001")],
        # With no row, only the flag's own check can refuse --out: each photo's path
        # lies under the page's folder, so its check would refuse it too.
        "--out": [],
        "photo_file": [row("A001", "../sealed/A001.jpg")],
    }[where]
    log, out = set_a(tmp_path, rows, ["A001.jpg"])
    if where == "--set-a-log":
        log = tmp_path / "sealed" / log.name
    elif where == "--out":
        out = tmp_path / "sealed" / out.name
    with pytest.raises(SystemExit) as stop:
        run(log, out)
    assert stop.value.code == 2
    assert capsys.readouterr().err == "refused: path inside a folder named sealed\n"
    assert not (tmp_path / "sealed").exists()
    assert not (tmp_path / "m8_sheet.html").exists()


@pytest.mark.parametrize("name", ["set_a_log.csv", "m8_labels.csv"])
def test_out_must_name_the_page(tmp_path, capsys, name):
    """--out must name the .html page, so a slip can't overwrite Rene's log or his
    export: either keeps its bytes. The check reads the string only."""
    log, _ = set_a(tmp_path, [row("A001")], ["A001.jpg"])
    target = tmp_path / name
    if target != log:
        target.write_bytes(b"photo_id,ref_id\nA001,P1\n")  # an earlier export
    before = target.read_bytes()
    with pytest.raises(SystemExit) as stop:
        run(log, target)
    assert stop.value.code == 2
    assert capsys.readouterr().err.endswith("error: --out must name the .html page\n")
    assert target.read_bytes() == before
    assert not (tmp_path / "m8_sheet.html").exists()


def test_photo_file_must_be_the_ids_own(tmp_path, capsys):
    """As the intake has it, a photo is <id>.<jpg|jpeg|png>, in any case, and an id's
    rows name one file. Saved labels follow the id, so a photo filed under another id
    would carry them onto the wrong photo, which the split can't undo. Each problem
    names the id once, never a file. Nothing is written."""
    rows = [
        row("A001", "A002.jpg"),  # another id's photo
        row("A003", "sub/A003.jpg"),  # not a bare name
        row("A004", "A004.jpg"),
        row("A004", "A004.png"),  # one id, two files
        row("A005", "a005.JPG"),  # any case is fine
        row("A006", "B001.jpg"),
        row("A006", "B001.jpg"),  # an alert row repeats the problem, printed once
    ]
    log, out = set_a(tmp_path, rows, ["A002.jpg", "A004.jpg", "A004.png", "a005.JPG"])
    assert run(log, out) == 1
    assert capsys.readouterr().out == (
        "A001 photo_file: id_file_mismatch\n"
        "A003 photo_file: id_file_mismatch\n"
        "A004 photo_file: differs\n"
        "A006 photo_file: id_file_mismatch\n"
    )
    assert not out.exists()


def test_missing_columns_write_nothing(tmp_path, capsys):
    """A log without candidate_id or photo_file, such as an M8 export given by mistake,
    is named as the intake names it, and nothing is written."""
    log = synth.write_csv(
        tmp_path / "m8_labels.csv", formats.M8_COLUMNS, [{"photo_id": "A001"}]
    )
    out = tmp_path / "m8_sheet.html"
    assert run(log, out) == 1
    assert capsys.readouterr().out == (
        "log candidate_id: missing_column\nlog photo_file: missing_column\n"
    )
    assert not out.exists()


def test_malformed_log_writes_nothing(tmp_path, capsys):
    """A log that can't be read whole stops the command with read_table's finding, which
    names the row by number, never its text."""
    log, out = set_a(tmp_path, [], ["A001.jpg"])
    log.write_bytes(b"candidate_id,photo_file\nA001,A001.jpg,SENTINEL-NOTE\n")
    assert run(log, out) == 1
    assert capsys.readouterr().out == "row 1 cells: too_many\n"
    assert not out.exists()


def test_rerun_overwrites_the_page(tmp_path, capsys):
    """Claude remakes the page as Rene logs more photos. Each run prints the photo
    count, then one fixed reminder: a page remade without a labelled photo would drop
    that photo's labels at Rene's next change, so he exports them first."""
    for ids in (["A001"], ["A001", "A002"]):
        rows = [row(photo_id) for photo_id in ids]
        log, out = set_a(tmp_path, rows, [f"{photo_id}.jpg" for photo_id in ids])
        assert run(log, out) == 0
        assert capsys.readouterr().out == f"photos={len(ids)}\n{REMINDER}\n"
        photos = data_of(out.read_text(encoding="utf-8"))["photos"]
        assert [photo["id"] for photo in photos] == ids
