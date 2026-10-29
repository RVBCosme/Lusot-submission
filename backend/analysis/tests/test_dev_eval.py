"""Tests for the development tool, probes/dev_eval.py (C312, C315, C321, C327).

The tool isn't a package module, so it is loaded from its file, and it loads the
offline runner the same way. Every run is recorded with the runner's live() and a
FakeClient, so no Meta call is made. Manifests and M8 sheets are CSV in tmp_path, in
MS2's columns (its §5.9). LUSOT_DATA_DIR is tmp_path/data and MODEL_API_KEY is unset,
so no test reaches Meta or the real data folder. The harness's --label-words comes
from a stand-in script in tmp_path, since eval/run_eval.py isn't on this branch.
"""

import ast
import csv
import dataclasses
import importlib.util
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fakes import FakeClient, geometry_case

from lusot_analysis import rules
from lusot_analysis.pipeline import READING_PHRASES
from lusot_analysis.tuning import START

TOOL = Path(__file__).parents[1] / "probes" / "dev_eval.py"
EVAL = Path(__file__).parents[3] / "eval"  # MS6's harness, run, never imported
REASON = "REASON-MARKER-31"  # the reason fakes.answer gives every answer
DEFAULT = "default_boxes-v1"  # settings_name(START)
# The harness's --label-words, as printed on Window 4's branch at 1cafc88.
WORDS = [
    "above",
    "all",
    "and",
    "ankle",
    "any",
    "cars",
    "centimeter",
    "centimeters",
    "centimetre",
    "centimetres",
    "chest",
    "cm",
    "deep",
    "gutter",
    "half",
    "head",
    "in",
    "inch",
    "inches",
    "knee",
    "lagpas",
    "level",
    "light",
    "motorcycles",
    "not",
    "npatv",
    "nplv",
    "of",
    "passable",
    "patv",
    "sedan",
    "subsided",
    "tao",
    "tire",
    "to",
    "types",
    "vehicle",
    "vehicles",
    "waist",
]
# MS2's manifest.csv and m8.csv columns (its formats.py, on ms2-data).
MANIFEST_COLUMNS = (
    "photo_id",
    "set",
    "split",
    "event_id",
    "event_date",
    "city",
    "metro_manila",
    "spot_key",
    "same_spot_as",
    "poster_kind",
    "match",
    "level_label_raw",
    "passability_raw",
    "other_alerts_raw",
    "label_in_image",
    "reference_visible",
    "faces_or_plates",
    "surface",
    "duplicate",
    "duplicate_of",
    "decodes",
    "photo_file",
    "photo_sha256",
    "photo_dhash",
    "width",
    "height",
    "notes",
)
M8_COLUMNS = (
    "photo_id",
    "ref_id",
    "kind",
    "x",
    "y",
    "vehicle_type",
    "body_waterline",
    "waterline",
    "quality",
    "subsets",
)
# MS6's §4.3 fields of a Set A row and an A-neg row, as its loader checks them.
SET_A_FIELDS = {
    "photo_id",
    "event_id",
    "level_label_raw",
    "passability_raw",
    "other_alerts_raw",
    "poster_kind",
    "label_in_image",
    "match",
    "duplicate",
    "metro_manila",
    "decodes",
    "quality",
    "subsets",
    "outcomes",
    "answer",
    "wheel_inches",
    "m8",
}
A_NEG_FIELDS = SET_A_FIELDS - {
    "level_label_raw",
    "passability_raw",
    "other_alerts_raw",
    "m8",
} | {"surface"}
# Markers for the manifest's free text, which no written file may hold.
FREE_TEXT = ("NOTE-MARKER-17", "CITY-MARKER-23", "SPOT-MARKER-29")


def load_tool():
    spec = importlib.util.spec_from_file_location("dev_eval_script", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load_tool()


def no_client():
    raise AssertionError("a Meta client was built")


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(tool.runner, "make_client", no_client)


@pytest.fixture
def harness(tmp_path, monkeypatch):
    """A stand-in eval/run_eval.py that prints the label words, as the tool's
    subprocess runs it."""
    script = tmp_path / "harness" / "eval" / "run_eval.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        "import sys\n"
        f"WORDS = {WORDS!r}\n"
        "if sys.argv[1:] == ['--label-words']:\n"
        "    print('\\n'.join(WORDS))\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tool, "RUN_EVAL", script)
    return script


def manifest_row(photo_id: str, **cells: str) -> dict[str, str]:
    """A manifest row in MS2's columns. A Set A row unless `set` says otherwise."""
    a_neg = cells.get("set") == "A-neg"
    row = dict.fromkeys(MANIFEST_COLUMNS, "")
    row |= {
        "photo_id": photo_id,
        "set": "A",
        "split": "dev",
        "event_id": "E01",
        "event_date": "2026-10-20",
        "city": FREE_TEXT[1],
        "metro_manila": "yes",
        "spot_key": FREE_TEXT[2],
        "poster_kind": "other" if a_neg else "mmda",
        "match": "" if a_neg else "same_post",
        "level_label_raw": "none" if a_neg else "Knee deep",
        "passability_raw": "" if a_neg else "NPLV",
        "label_in_image": "no",
        "surface": "wet" if a_neg else "",
        "duplicate": "no",
        "decodes": "yes",
        "photo_file": f"{photo_id}.jpg",
        "photo_sha256": "ab" * 32,
        "width": "640",
        "height": "480",
        "notes": FREE_TEXT[0],
    }
    return row | cells


def csv_text(columns, rows) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


@dataclasses.dataclass
class Data:
    """A development data folder in tmp_path: the paths the tool is given."""

    root: Path
    set_a: Path
    a_neg: Path
    m8: Path
    rows: dict[str, dict[str, str]]

    def photo(self, photo_id: str) -> Path:
        row = self.rows[photo_id]
        side = self.set_a if row["set"] == "A" else self.a_neg
        return side.parent / "photos" / row["photo_file"]

    def run_dir(self, photo_id: str, settings: str = DEFAULT) -> Path:
        row = self.rows[photo_id]
        return self.root / "runs" / "dev" / row["set"] / settings / photo_id


def write_data(
    tmp_path: Path,
    set_a=("A001", "A002"),
    a_neg=("N001",),
    *,
    case=lambda: geometry_case("van"),
    cells=None,
) -> Data:
    """MS2's development side under tmp_path/data: both manifests, the M8 sheet
    and each row's photo, `case`'s. `cells` changes cells by photo id."""
    root = tmp_path / "data"
    rows = {}
    for number, photo_id in enumerate(set_a, start=1):
        rows[photo_id] = manifest_row(photo_id, event_id=f"E{number:02}")
    for number, photo_id in enumerate(a_neg, start=1):
        rows[photo_id] = manifest_row(photo_id, set="A-neg", event_id=f"E{number:02}")
    for photo_id, changes in (cells or {}).items():
        rows[photo_id] |= changes
    data = Data(
        root,
        root / "set_a" / "dev" / "manifest.csv",
        root / "a_neg" / "dev" / "manifest.csv",
        root / "set_a" / "dev" / "m8.csv",
        rows,
    )
    photo = case()[0]
    for path, ids in ((data.set_a, set_a), (data.a_neg, a_neg)):
        (path.parent / "photos").mkdir(parents=True)
        path.write_text(
            csv_text(MANIFEST_COLUMNS, [rows[i] for i in ids]), encoding="utf-8"
        )
        for photo_id in ids:
            data.photo(photo_id).write_bytes(photo)
    m8 = [
        {"photo_id": "A001", "ref_id": "P1", "kind": "photo", "quality": "dark"},
        # Wheel 2's hub and vehicle 1's body, in geometry_case's numbered boxes.
        {"photo_id": "A001", "ref_id": "R1", "kind": "wheel", "x": "0.5"}
        | {"y": "0.45", "waterline": "hub"},
        {"photo_id": "A001", "ref_id": "R2", "kind": "vehicle", "x": "0.5"}
        | {"y": "0.3", "vehicle_type": "van", "body_waterline": "door_sill"},
    ]
    data.m8.write_text(csv_text(M8_COLUMNS, m8), encoding="utf-8")
    return data


def record(
    monkeypatch, data: Data, photo_id: str, *, settings=DEFAULT, tuning=START, case=None
) -> Path:
    """`photo_id`'s run, recorded live through a FakeClient into its folder for
    `settings`, with `tuning` (START by default, R128)."""
    _, sam, given = (case or (lambda: geometry_case("van")))()
    monkeypatch.setattr(tool.runner, "make_client", lambda: FakeClient(sam, given))
    run_dir = data.run_dir(photo_id, settings)
    tool.runner.live(data.photo(photo_id), data.root, run_dir=run_dir, tuning=tuning)
    monkeypatch.setattr(tool.runner, "make_client", no_client)
    return run_dir


def record_all(monkeypatch, data: Data, **keywords) -> None:
    for photo_id in data.rows:
        record(monkeypatch, data, photo_id, **keywords)


def export_argv(data: Data, out: Path, *flags: str) -> list[str]:
    return [
        "export",
        "--set-a",
        str(data.set_a),
        "--m8",
        str(data.m8),
        "--a-neg",
        str(data.a_neg),
        "--out",
        str(out),
        "--rules-version",
        "0.6",
        *flags,
    ]


def read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_settings_and_run_folders():
    assert tool.settings_name(START) == DEFAULT
    low = dataclasses.replace(START, reasoning_effort="low", drawing="boxes-v2")
    assert tool.settings_name(low) == "low_boxes-v2"
    # Runs at different efforts or drawings never share a folder (finding 5).
    row = {"photo_id": "A001", "set": "A"}
    sets = Path("data") / "runs" / "dev" / "A"
    assert tool.run_dir_for(Path("data"), row, DEFAULT) == sets / DEFAULT / "A001"
    repeat = tool.run_dir_for(Path("data"), row, DEFAULT, repeat=2)
    assert repeat == sets / f"{DEFAULT}_r2" / "A001"


def test_export_writes_the_results_folder(tmp_path, monkeypatch, capsys, harness):
    data = write_data(tmp_path)
    record_all(monkeypatch, data)
    out = data.root / "results" / "dev-1"
    datasets = {"set_a": {"version": "v1", "split_seed": "7"}}
    argv = export_argv(data, out, "--datasets", json.dumps(datasets))
    # The fake makes no call during the export: make_client is no_client.
    assert tool.main(argv, tuning=START) == 0

    set_a, a_neg = read_lines(out / "set_a.jsonl"), read_lines(out / "a_neg.jsonl")
    assert (len(set_a), len(a_neg)) == (2, 1)
    assert [row["photo_id"] for row in set_a] == ["A001", "A002"]
    assert [set(row) for row in set_a] == [SET_A_FIELDS] * 2
    assert set(a_neg[0]) == A_NEG_FIELDS
    first = set_a[0]
    assert first["level_label_raw"] == "Knee deep"
    assert (first["quality"], first["subsets"]) == ("dark", [])
    assert first["duplicate"] is False and first["metro_manila"] is True
    assert first["m8"] == [
        {"box_id": 2, "kind": "wheel", "landmark": "hub", "vehicle_type": None},
        {
            "box_id": 1,
            "kind": "vehicle",
            "landmark": "door_sill",
            "vehicle_type": "van",
        },
    ]
    assert set_a[1]["m8"] == [] and set_a[1]["quality"] is None
    assert list(first["outcomes"]) == ["landmark", "geometry"]
    assert first["outcomes"]["geometry"]["levelFrom"] == "geometry"
    assert [inches["box_id"] for inches in first["wheel_inches"]] == [2]
    assert (a_neg[0]["match"], a_neg[0]["surface"]) == (None, "wet")
    assert (a_neg[0]["quality"], a_neg[0]["subsets"]) == (None, [])

    manifest = read_json(out / "run.json")
    assert manifest["kind"] == "development"
    assert manifest["rules_version"] == "0.6"
    assert manifest["datasets"] == datasets
    assert manifest["self_check"] == "off"
    assert manifest["geometry_default"] == "on"
    # v0.7 item 10.1's versions, in MS6's `frozen` map of short strings, with every
    # numeric cutoff at its start value (R153).
    assert manifest["frozen"] == {
        "sam_model": "sam-3.1",
        "spark_model": "muse-spark-1.3",
        "prompt": "muse_spark_photo_v1",
        "schema": "muse_spark_photo_v1",
        "drawing": "boxes-v1",
        "blur": manifest["frozen"]["blur"],
        "store": "false",
        "max_side": "1600",
        "sam_phrases": ",".join(READING_PHRASES),
        "tuning": "tuning-v1",
        "touch_tolerance_px": "5.0",
        "touch_share_min": "0.25",
        "ragged_iqr_share": "0.1",
        "daylight_brightness_min": "80.0",
        "rim_score_min": "0.5",
        "rim_size_low": "0.85",
        "rim_size_high": "1.15",
        "rim_edge_k": "1.0",
        "brightness_min": "40.0",
        "sharpness_min": "25.0",
        "min_wheel_side_px": "40",
        "max_vehicles": "6",
        "max_people": "6",
        "tire_codes": rules.TIRE_CODES_VERSION,
        "reasoning_effort": "default",
    }
    assert manifest["frozen"]["blur"].startswith("yunet")
    for key in ("freeze_commit", "baseline_level", "stops", "rerun_reason"):
        assert key not in manifest

    out_lines = capsys.readouterr().out.splitlines()
    assert out_lines == [
        "photos: set_a 2, a_neg 1",
        "g4_drops: 0",
        "wheels_measured: 3",
        "geometry_checks: {}",
        "labels_as_other_words: 0",
        "answers_withheld: 0",
        (
            'drops_before_numbering: {"person_cap": 0, "vehicle_cap": 0, "wheel_cap":'
            ' 0, "wheel_small": 0, "wheel_unlinked": 0}'
        ),
        (
            "next: python eval/run_eval.py --from-saved --results <the --out folder>"
            " --write"
        ),
    ]


def test_dropped_geometry_writes_only_landmark(tmp_path, monkeypatch, harness):
    # MS6's C418.
    data = write_data(tmp_path)
    record_all(monkeypatch, data)
    out = data.root / "results" / "dropped"
    flags = ("--geometry-default", "dropped", "--dropped-reason", "manila_check")
    assert tool.main(export_argv(data, out, *flags), tuning=START) == 0
    manifest = read_json(out / "run.json")
    assert manifest["geometry_default"] == "dropped"
    assert manifest["geometry_dropped_reason"] == "manila_check"
    for name in ("set_a.jsonl", "a_neg.jsonl"):
        for row in read_lines(out / name):
            assert list(row["outcomes"]) == ["landmark"]
            assert row["wheel_inches"] == []
    # Dropped needs its reason, and a reason needs dropped, each before any write.
    for flags in (("--geometry-default", "dropped"), ("--dropped-reason", "x")):
        other = data.root / "results" / "other"
        assert tool.main(export_argv(data, other, *flags), tuning=START) == 2
        assert not other.exists()


def write_replay(path: Path, photo_ids) -> dict:
    """Task 13's replay.jsonl: one line per photo, with both replay outcomes."""
    outcomes = {
        "landmark_replay": {"status": "refused", "refusalReason": "too_dark"},
        "geometry_replay": {"status": "done", "noFloodSeen": True},
    }
    path.write_text(
        "".join(json.dumps({"photo_id": i, **outcomes}) + "\n" for i in photo_ids),
        encoding="utf-8",
    )
    return outcomes


def test_replay_outcomes_join_every_set_a_row(tmp_path, monkeypatch, harness):
    # MS6's C425.
    data = write_data(tmp_path)
    record_all(monkeypatch, data)
    # An A-neg line is ignored: only Set A rows carry replays (MS6's C425).
    replay = write_replay(data.root / "replay.jsonl", ["A001", "A002", "N001"])
    out = data.root / "results" / "replayed"
    argv = export_argv(data, out, "--replay", str(data.root / "replay.jsonl"))
    assert tool.main(argv, tuning=START) == 0
    for row in read_lines(out / "set_a.jsonl"):
        outcomes = row["outcomes"]
        assert list(outcomes) == [
            "landmark",
            "geometry",
            "landmark_replay",
            "geometry_replay",
        ]
        assert {key: outcomes[key] for key in replay} == replay
    (a_neg,) = read_lines(out / "a_neg.jsonl")
    assert list(a_neg["outcomes"]) == ["landmark", "geometry"]
    # A Set A row missing from it: exit 2, with nothing written.
    write_replay(data.root / "short.jsonl", ["A001"])
    short = data.root / "results" / "short"
    argv = export_argv(data, short, "--replay", str(data.root / "short.jsonl"))
    assert tool.main(argv, tuning=START) == 2
    assert not short.exists()


def test_export_refuses_mixed_settings(tmp_path, monkeypatch, capsys, harness):
    # Review Focus 7 (finding 5): a run saved with effort low, in the folder the
    # default tuning reads, is refused, so efforts never mix in one ablation.
    data = write_data(tmp_path)
    record(monkeypatch, data, "A001")
    record(monkeypatch, data, "N001")
    low = dataclasses.replace(START, reasoning_effort="low")
    record(monkeypatch, data, "A002", tuning=low)
    out = data.root / "results" / "mixed"
    assert tool.main(export_argv(data, out), tuning=START) == 2
    assert "another effort or drawing" in capsys.readouterr().out
    assert not out.exists()
    # With the tuning's effort set to low, the same folder's default runs are
    # refused in turn.
    flags = ("--set", "reasoning_effort=low", "--runs", DEFAULT)
    assert tool.main(export_argv(data, out, *flags), tuning=START) == 2
    assert "another effort or drawing" in capsys.readouterr().out
    assert not out.exists()


def test_export_refuses_bad_paths(tmp_path, monkeypatch, capsys, harness):
    data = write_data(tmp_path)
    record_all(monkeypatch, data)
    # --out under a folder named sealed, in any case, is refused before anything.
    sealed_out = data.root / "Sealed" / "results"
    assert tool.main(export_argv(data, sealed_out), tuning=START) == 2
    assert capsys.readouterr().out == "refused: path inside a folder named sealed\n"
    assert not (data.root / "Sealed").exists()
    # --out inside the repo.
    repo_out = TOOL.parents[1] / "results-r131-test"
    assert tool.main(export_argv(data, repo_out), tuning=START) == 2
    assert capsys.readouterr().out == "refused: --out is inside the repo\n"
    assert not repo_out.exists()
    # --out outside LUSOT_DATA_DIR.
    elsewhere = tmp_path / "elsewhere"
    assert tool.main(export_argv(data, elsewhere), tuning=START) == 2
    assert capsys.readouterr().out == "refused: --out must lie under the data folder\n"
    assert not elsewhere.exists()
    # A manifest photo under a folder named sealed: refused before any photo is
    # read, and nothing is made. No photo is written there: only the manifest
    # names it.
    data = write_data(tmp_path / "other")
    data.rows["A001"]["photo_file"] = "../../sealed/A001.jpg"
    rows = [data.rows[photo_id] for photo_id in ("A001", "A002")]
    data.set_a.write_text(csv_text(MANIFEST_COLUMNS, rows), encoding="utf-8")
    monkeypatch.setenv("LUSOT_DATA_DIR", str(data.root))
    out = data.root / "results" / "x"
    assert tool.main(export_argv(data, out), tuning=START) == 2
    assert capsys.readouterr().out == "refused: path inside a folder named sealed\n"
    assert not out.exists()
    assert not (data.root / "set_a" / "sealed").exists()
    # --out under the runs folder, beside the raw outputs.
    beside = data.root / "runs" / "results"
    assert tool.main(export_argv(data, beside), tuning=START) == 2
    assert (
        capsys.readouterr().out == "refused: --out must lie outside the runs folder\n"
    )
    assert not beside.exists()
    # --runs and --sam-from are single folder names: argparse refuses the rest.
    for flags in (("--runs", "../x"), ("--runs", "a/b"), ("--runs", "..")):
        with pytest.raises(SystemExit) as exc:
            tool.main(export_argv(data, out, *flags), tuning=START)
        assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        tool.main(["run", "--manifest", str(data.set_a), "--sam-from", "..\\x"])
    assert exc.value.code == 2
    assert not out.exists()


@pytest.mark.parametrize(
    "parts",
    [
        ("sealed.",),
        ("sealed ",),
        ("SEALED. .",),
        ("sealed::$INDEX_ALLOCATION",),
        ("x", "Sealed..", "y"),
    ],
    ids=["dot", "space", "dots-and-spaces", "stream", "inside"],
)
def test_sealed_spelled_the_windows_way_is_refused(
    tmp_path, monkeypatch, capsys, harness, parts
):
    # R156: Windows strips a name's trailing dots and spaces, and reads a part's
    # name before any ":" (an NTFS stream), so each --out opens a folder named
    # sealed. Refused before anything is read, and nothing is made.
    data = write_data(tmp_path, set_a=("A001",), a_neg=())
    out = data.root.joinpath(*parts, "results")
    assert tool.main(export_argv(data, out), tuning=START) == 2
    assert capsys.readouterr().out == "refused: path inside a folder named sealed\n"
    assert sorted(path.name for path in data.root.iterdir()) == ["a_neg", "set_a"]
    # A settings name can't end in a dot, or hold a ":", either.
    for name in ("default_boxes-v1.", "x.", "sealed::$INDEX_ALLOCATION", "x:y"):
        with pytest.raises(SystemExit) as exc:
            tool.main(export_argv(data, out, "--runs", name), tuning=START)
        assert exc.value.code == 2


def test_a_folder_that_only_holds_sealed_is_allowed(tmp_path, monkeypatch, harness):
    data = write_data(tmp_path, set_a=("A001",), a_neg=())
    record_all(monkeypatch, data)
    for name in ("sealedx", "unsealed"):
        out = data.root / "results" / name
        assert tool.main(export_argv(data, out), tuning=START) == 0
        assert (out / "set_a.jsonl").is_file()


def test_run_folders_are_checked_for_sealed(tmp_path, monkeypatch, capsys, harness):
    # A photo id that leads its run folder into a folder named sealed is refused
    # before that folder is looked at, by run and by export (C66).
    data = write_data(tmp_path, set_a=("A001",), a_neg=("N001",))
    record_all(monkeypatch, data)
    data.rows["A001"]["photo_id"] = "../../../../sealed/A001"
    data.set_a.write_text(
        csv_text(MANIFEST_COLUMNS, [data.rows["A001"]]), encoding="utf-8"
    )
    for argv in (
        ["run", "--manifest", str(data.set_a), "--yes"],
        export_argv(data, data.root / "results" / "x"),
    ):
        assert tool.main(argv, tuning=START) == 2
        assert capsys.readouterr().out == "refused: path inside a folder named sealed\n"
    assert not (data.root / "sealed").exists()
    assert not (data.root / "results").exists()


def test_export_needs_every_run(tmp_path, monkeypatch, capsys, harness):
    data = write_data(tmp_path)
    record(monkeypatch, data, "A001")
    record(monkeypatch, data, "N001")
    out = data.root / "results" / "partial"
    assert tool.main(export_argv(data, out), tuning=START) == 2
    assert "run `dev_eval.py run` first" in capsys.readouterr().out
    assert not out.exists()


def test_export_without_the_harness_waits_for_set_a(tmp_path, monkeypatch, capsys):
    # R133: with no eval/run_eval.py there are no label words, so the Set A rows wait;
    # the A-neg rows carry no labels and still write.
    monkeypatch.setattr(tool, "RUN_EVAL", tmp_path / "missing" / "eval" / "run_eval.py")
    data = write_data(tmp_path)
    record_all(monkeypatch, data)
    out = data.root / "results" / "waiting"
    assert tool.main(export_argv(data, out), tuning=START) == 2
    printed = capsys.readouterr().out
    assert "--label-words" in printed
    assert "photos: a_neg 1" in printed.splitlines()
    assert len(read_lines(out / "a_neg.jsonl")) == 1
    assert read_json(out / "run.json")["kind"] == "development"
    assert not (out / "set_a.jsonl").exists()
    # A folder that still holds an earlier export's set_a.jsonl is refused, since the
    # harness would score those rows beside this run.json. Nothing is rewritten.
    stale = data.root / "results" / "stale"
    stale.mkdir()
    (stale / "set_a.jsonl").write_text("{}\n", encoding="utf-8")
    assert tool.main(export_argv(data, stale), tuning=START) == 2
    assert "earlier export's set_a.jsonl" in capsys.readouterr().out
    assert sorted(path.name for path in stale.iterdir()) == ["set_a.jsonl"]


def test_set_records_its_cutoffs(tmp_path, monkeypatch, harness):
    # R153: a --set candidate's run.json states the cutoff it ran with.
    data = write_data(tmp_path)
    record_all(monkeypatch, data)
    out = data.root / "results" / "candidate"
    argv = export_argv(data, out, "--set", "touch_tolerance_px=6")
    assert tool.main(argv, tuning=START) == 0
    frozen = read_json(out / "run.json")["frozen"]
    assert frozen["touch_tolerance_px"] == "6.0"
    assert frozen["touch_share_min"] == str(START.touch_share_min)
    for name in frozen:  # each an MS6 token of 32 characters or fewer
        assert re.fullmatch("[a-z][a-z0-9_]{0,31}", name), name


@pytest.mark.parametrize(
    "text",
    [
        "reasoning_effort=extreme",
        "drawing=boxes-v9",
        "touch_tolerance_px=nan",
        "touch_tolerance_px=inf",
        "touch_tolerance_px=-inf",
        "touch_tolerance_px=five",
        "max_vehicles=5",
        "untuned=x",
        "colour=red",
        "touch_tolerance_px",
    ],
)
def test_set_refuses_bad_values(tmp_path, monkeypatch, capsys, harness, text):
    # Each refused before any run is read or replayed, and nothing is written.
    data = write_data(tmp_path, set_a=("A001",), a_neg=())
    out = data.root / "results" / "bad-set"
    assert tool.main(export_argv(data, out, "--set", text), tuning=START) == 2
    assert capsys.readouterr().out.startswith("refused: --set")
    assert not out.exists()


def test_export_counts_withheld_answers(tmp_path, monkeypatch, capsys, harness):
    # R152: a saved answer whose ids MS6's loader would refuse passes the schema, so
    # its row carries no answer, and the export goes on and counts it. The saved
    # answer itself is left as it was.
    data = write_data(tmp_path)
    record_all(monkeypatch, data)
    spark_file = data.run_dir("A002") / "spark.json"
    spark = read_json(spark_file)
    spark["data"]["wheels"] *= 2  # wheel 2, twice in one list
    spark_file.write_text(json.dumps(spark), encoding="utf-8")
    out = data.root / "results" / "withheld"
    assert tool.main(export_argv(data, out), tuning=START) == 0
    first, second = read_lines(out / "set_a.jsonl")
    assert first["answer"] is not None and second["answer"] is None
    assert "answers_withheld: 1" in capsys.readouterr().out.splitlines()
    assert read_json(spark_file) == spark


@pytest.mark.parametrize(
    ("change", "printed"),
    [
        (lambda saved: saved["tuning"].update(max_people=5), "C56/C70"),
        (lambda saved: saved["tuning"].update(min_wheel_side_px=30), "C56/C70"),
        (lambda saved: saved.update(blur_version="other-blur"), "states once"),
        (lambda saved: saved.update(prompt_version="other_prompt"), "states once"),
        (lambda saved: saved["models"].update(sam="other-sam"), "states once"),
        (lambda saved: saved.update(phrases=["floodwater"]), "states once"),
    ],
    ids=["c70", "c56", "blur", "prompt", "models", "phrases"],
)
def test_saved_runs_must_agree(tmp_path, monkeypatch, capsys, harness, change, printed):
    # R144: a run numbered under other C56 or C70 values is refused, as the runner's
    # replay refuses it. Runs that differ in what `frozen` states once are refused,
    # so run.json can't misstate them. Nothing is written.
    data = write_data(tmp_path)
    record_all(monkeypatch, data)
    path = data.run_dir("A002") / "run.json"
    saved = read_json(path)
    change(saved)
    path.write_text(json.dumps(saved), encoding="utf-8")
    out = data.root / "results" / "mixed"
    assert tool.main(export_argv(data, out), tuning=START) == 2
    assert printed in capsys.readouterr().out
    assert not out.exists()


def test_failures_exit_3_with_the_class_only(tmp_path, monkeypatch, capsys, harness):
    # R110: a --label-words that times out, and a replay line that isn't an object,
    # end with exit 3 and the error's class, with no traceback.
    data = write_data(tmp_path)
    record_all(monkeypatch, data)
    out = data.root / "results" / "failed"

    def timed_out(*args, **kwargs):
        raise tool.subprocess.TimeoutExpired(cmd="run_eval.py", timeout=60)

    with monkeypatch.context() as patched:
        patched.setattr(tool.subprocess, "run", timed_out)
        assert tool.main(export_argv(data, out), tuning=START) == 3
    assert capsys.readouterr().out == "failed: TimeoutExpired\n"
    replay = data.root / "replay.jsonl"
    replay.write_text("[1, 2]\n", encoding="utf-8")
    argv = export_argv(data, out, "--replay", str(replay))
    assert tool.main(argv, tuning=START) == 3
    assert capsys.readouterr().out == "failed: ValueError\n"
    assert not out.exists()


def test_export_checks_its_datasets(tmp_path, monkeypatch, capsys, harness):
    # With every run saved, only --datasets can stop the export: MS6's shape is
    # checked before anything is read (an InputError) or written.
    data = write_data(tmp_path, set_a=("A001",), a_neg=())
    record_all(monkeypatch, data)
    out = data.root / "results" / "datasets"
    for given, printed in (
        ('{"set_c": {"version": "v1", "split_seed": "7"}}', "invalid: datasets may"),
        ('{"set_a": {"version": "v1"}}', "invalid: each dataset"),
        ('{"set_a": {"version": "a://b", "split_seed": "7"}}', "invalid: a dataset"),
        ("[]", "refused: --datasets"),
        ("not json", "refused: --datasets"),
    ):
        argv = export_argv(data, out, "--datasets", given)
        assert tool.main(argv, tuning=START) == 2
        assert capsys.readouterr().out.startswith(printed)
    assert not out.exists()


def rules_version() -> str:
    """The harness's RULES_VERSION, read from eval/scoring/__init__.py as text, so
    eval/ is never imported (C321)."""
    tree = ast.parse((EVAL / "scoring" / "__init__.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign | ast.Assign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(getattr(t, "id", None) == "RULES_VERSION" for t in targets):
                return ast.literal_eval(node.value)
    raise AssertionError("eval/scoring/__init__.py sets no RULES_VERSION")


def test_the_harness_loads_the_export(tmp_path, monkeypatch):
    # End to end, once MS6's harness is in the tree: an export holding a withheld
    # answer (R152), with the real --label-words, loads under MS6's allow-list and
    # writes its report.
    if not (EVAL / "run_eval.py").is_file():
        pytest.skip("eval/run_eval.py isn't in the tree: MS6 hasn't merged")
    data = write_data(tmp_path)
    record_all(monkeypatch, data)
    spark_file = data.run_dir("A001") / "spark.json"
    spark = read_json(spark_file)
    spark["data"]["wheels"][0]["id"] = 2.0  # passes the schema, not the loader
    spark_file.write_text(json.dumps(spark), encoding="utf-8")
    out = data.root / "results" / "end-to-end"
    argv = export_argv(data, out)
    argv[argv.index("--rules-version") + 1] = rules_version()
    assert tool.main(argv, tuning=START) == 0
    done = subprocess.run(
        [sys.executable, "-I", "-B", str(EVAL / "run_eval.py"), "--from-saved"]
        + ["--results", str(out), "--write"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert done.returncode == 0, done.stdout[-2000:]


def test_rows_hold_no_free_text(tmp_path, monkeypatch, capsys, harness):
    data = write_data(
        tmp_path, cells={"A002": {"level_label_raw": "Knee deep near SPOT-MARKER-29"}}
    )
    record_all(monkeypatch, data)
    out = data.root / "results" / "clean"
    assert tool.main(export_argv(data, out), tuning=START) == 0
    printed = capsys.readouterr().out
    written = "".join(
        (out / name).read_text(encoding="utf-8")
        for name in ("run.json", "set_a.jsonl", "a_neg.jsonl")
    )
    for text in (written, printed):
        assert REASON not in text
        for marker in FREE_TEXT:
            assert marker not in text
        for photo_id in data.rows:
            assert data.photo(photo_id).name not in text
        assert str(tmp_path) not in text
        assert str(tmp_path).replace("\\", "\\\\") not in text
    # The label with a word outside the list is written as the marker, and counted.
    (_, second) = read_lines(out / "set_a.jsonl")
    assert second["level_label_raw"] == "(other words)"
    assert "labels_as_other_words: 1" in printed.splitlines()


def test_run_prints_cost_first_and_needs_yes(tmp_path, monkeypatch, capsys):
    data = write_data(tmp_path, set_a=("A001", "A002", "A003"), a_neg=())
    first = record(monkeypatch, data, "A001")
    kept = (first / "run.json").read_bytes()
    argv = ["run", "--manifest", str(data.set_a)]
    # Without --yes: the counts and the cost, then exit 2, with no client built.
    assert tool.main(argv, tuning=START) == 2
    assert capsys.readouterr().out.splitlines() == [
        "photos: 3 in the manifest, 1 already saved",
        "to run: 2 (2 full, 0 Muse Spark only), estimated cost $0.060",
        "stopped: add --yes to pay for these runs",
    ]
    assert not data.run_dir("A002").exists()
    # With it: a run folder for each row that lacked one; the existing run is kept.
    _, sam, given = geometry_case("van")
    fake = FakeClient(sam, given)
    monkeypatch.setattr(tool.runner, "make_client", lambda: fake)
    assert tool.main([*argv, "--yes"], tuning=START) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[-1] == "runs saved: 2"
    assert all("outcome" not in line and "level" not in line for line in out)
    for photo_id in ("A002", "A003"):
        assert (data.run_dir(photo_id) / "run.json").is_file()
    assert (first / "run.json").read_bytes() == kept
    assert [kind for kind, _, _ in fake.calls].count("judge") == 2
    # --limit runs only that many of the rows still to run.
    data = write_data(tmp_path / "limited", set_a=("A001", "A002"), a_neg=())
    monkeypatch.setenv("LUSOT_DATA_DIR", str(data.root))
    argv = ["run", "--manifest", str(data.set_a), "--limit", "1", "--yes"]
    assert tool.main(argv, tuning=START) == 0
    assert (data.run_dir("A001") / "run.json").is_file()
    assert not data.run_dir("A002").exists()


def no_segment(phrase: str) -> None:
    raise AssertionError("a SAM call was made")


def test_runs_at_other_settings_go_to_their_own_folder(tmp_path, monkeypatch, capsys):
    data = write_data(tmp_path, set_a=("A001", "A002"), a_neg=())
    record_all(monkeypatch, data)
    _, sam, given = geometry_case("van")
    fake = FakeClient(sam, given, on_segment=no_segment)
    monkeypatch.setattr(tool.runner, "make_client", lambda: fake)
    argv = ["run", "--manifest", str(data.set_a), "--effort", "low"]
    argv += ["--sam-from", DEFAULT, "--yes"]
    assert tool.main(argv, tuning=START) == 0
    assert capsys.readouterr().out.splitlines()[:2] == [
        "photos: 2 in the manifest, 0 already saved",
        "to run: 2 (0 full, 2 Muse Spark only), estimated cost $0.030",
    ]
    # Only judge was paid for, at effort low, and each run went to low_boxes-v1.
    assert [kind for kind, _, _ in fake.calls] == ["judge", "judge"]
    assert [keywords["reasoning_effort"] for keywords in fake.keywords] == ["low"] * 2
    for photo_id in ("A001", "A002"):
        saved = read_json(data.run_dir(photo_id, "low_boxes-v1") / "run.json")
        assert (saved["reasoning_effort"], saved["sam_from"]) == ("low", True)
        default = read_json(data.run_dir(photo_id) / "run.json")
        assert default["reasoning_effort"] is None


def test_run_refuses_sealed_and_repo_folders(tmp_path, monkeypatch, capsys):
    # R131: the paid command's data folder passes refuse_sealed and
    # refuse_data_in_repo, before anything is read or paid for.
    data = write_data(tmp_path, set_a=("A001",), a_neg=())
    monkeypatch.setenv("LUSOT_DATA_DIR", str(tmp_path / "sealed" / "data"))
    assert tool.main(["run", "--manifest", str(data.set_a), "--yes"]) == 2
    assert capsys.readouterr().out == "refused: path inside a folder named sealed\n"
    monkeypatch.setenv("LUSOT_DATA_DIR", str(TOOL.parents[1] / "data-r131-test"))
    assert tool.main(["run", "--manifest", str(data.set_a), "--yes"]) == 2
    assert capsys.readouterr().out == "refused: the data folder is inside the repo\n"
    assert not (TOOL.parents[1] / "data-r131-test").exists()
